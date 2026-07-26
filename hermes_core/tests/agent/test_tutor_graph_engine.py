from __future__ import annotations

import copy

import pytest

from agent.graph_engine.tutor_engine import TutorActivityExecutor
from agent.graph_engine.tutor_ports import (
    TutorProviderBinding,
    TutorProviderOutputError,
)
from agent.graph_engine.tutor_contracts import TutorProviderPlanV1, TutorProviderResult
from learning.tutor_activity import TutorActivityService
from learning.tutor_runtime_store import TutorRuntimeStore


def _body(idempotency="start-1"):
    return {
        "schema_version": 1,
        "space_id": "space-1",
        "activity_kind": "tutor",
        "idempotency_key": idempotency,
        "goal": "Explain fractions",
        "input_refs": [],
    }


class _Resolver:
    def __init__(self):
        self.binding = TutorProviderBinding(
            plan=TutorProviderPlanV1(
                provider_id="custom",
                model_id="model-1",
                api_mode="chat_completions",
                endpoint_identity="https://example.invalid/v1",
            ),
            api_key="secret",
        )

    def resolve_current(self):
        return self.binding

    def bind_saved(self, plan):
        assert plan.plan_hash == self.binding.plan.plan_hash
        return self.binding


class _Provider:
    def __init__(self, outputs=None, error=None):
        self.outputs = list(outputs or ["explanation", "remediation"])
        self.error = error
        self.calls = []

    def execute_once(self, reservation, request, *, timeout_s):
        self.calls.append((copy.deepcopy(reservation), request, timeout_s))
        if self.error is not None:
            raise self.error
        return TutorProviderResult(
            markdown=self.outputs.pop(0),
            actual_input_tokens=10,
            actual_output_tokens=5,
            actual_latency_ms=20,
        )


@pytest.fixture()
def runtime(tmp_path):
    store = TutorRuntimeStore(tmp_path / "tutor_runtime.db")
    yield store
    store.close()


def _service(runtime, provider):
    executor = TutorActivityExecutor(
        runtime,
        resolver=_Resolver(),
        provider_factory=lambda _binding: provider,
    )
    return TutorActivityService(runtime, executor)


def _answer(snapshot, selected):
    public = snapshot.to_public_dict()
    return {
        "schema_version": 1,
        "space_id": "space-1",
        "expected_revision": public["revision"],
        "mode": "answer",
        "interrupt_id": public["interrupt"]["interrupt_id"],
        "answer": {"type": "choice", "selected": [selected]},
    }


def test_start_interrupt_continue_complete_uses_one_attempt(runtime) -> None:
    provider = _Provider()
    service = _service(runtime, provider)

    waiting = service.start("owner-1", _body())
    assert waiting.status == "waiting_for_learner"
    assert waiting.latest_output == {
        "kind": "explanation",
        "markdown": "explanation",
    }
    assert waiting.interrupt.prompt["template"] == "check_1"
    assert len(provider.calls) == 1

    completed = service.resume(
        "owner-1", "tutor", waiting.key.activity_id, _answer(waiting, "continue")
    )
    assert completed.status == "completed"
    assert completed.terminal["completion_basis"] == "participation_only"
    assert completed.terminal["budget_summary"]["attempts_used"] == 1
    assert len(provider.calls) == 1


def test_explain_again_is_the_only_second_attempt(runtime) -> None:
    provider = _Provider()
    service = _service(runtime, provider)
    first = service.start("owner-1", _body())

    second = service.resume(
        "owner-1",
        "tutor",
        first.key.activity_id,
        _answer(first, "explain_again"),
    )
    assert second.status == "waiting_for_learner"
    assert second.latest_output == {"kind": "feedback", "markdown": "remediation"}
    assert second.interrupt.prompt["template"] == "check_2"
    assert [call[1].purpose for call in provider.calls] == ["explain", "remediate"]

    completed = service.resume(
        "owner-1", "tutor", second.key.activity_id, _answer(second, "continue")
    )
    assert completed.status == "completed"
    assert completed.terminal["budget_summary"]["attempts_used"] == 2
    assert len(provider.calls) == 2


def test_invalid_second_check_reissues_interrupt_without_provider(runtime) -> None:
    provider = _Provider()
    service = _service(runtime, provider)
    first = service.start("owner-1", _body())
    second = service.resume(
        "owner-1", "tutor", first.key.activity_id, _answer(first, "explain_again")
    )

    invalid = service.resume(
        "owner-1",
        "tutor",
        second.key.activity_id,
        _answer(second, "explain_again"),
    )
    assert invalid.status == "waiting_for_learner"
    assert invalid.interrupt.prompt["template"] == "check_2"
    assert invalid.interrupt.interrupt_id != second.interrupt.interrupt_id
    assert len(provider.calls) == 2


def test_provider_invalid_output_becomes_durable_blocked_terminal(runtime) -> None:
    provider = _Provider(error=TutorProviderOutputError())
    service = _service(runtime, provider)

    blocked = service.start("owner-1", _body())

    assert blocked.status == "blocked"
    assert blocked.terminal["reason_code"] == "invalid_model_output"
    assert blocked.terminal["budget_summary"]["attempts_used"] == 1
    assert len(provider.calls) == 1


def test_idempotent_start_returns_existing_activity_without_second_call(runtime) -> None:
    provider = _Provider()
    service = _service(runtime, provider)
    first = service.start("owner-1", _body())
    duplicate = service.start("owner-1", _body())

    assert duplicate.key == first.key
    assert duplicate.revision == first.revision
    assert len(provider.calls) == 1


def test_crash_after_reservation_is_unknown_and_recover_cannot_reissue(runtime) -> None:
    class SimulatedProcessCrash(BaseException):
        pass

    provider = _Provider(error=SimulatedProcessCrash())
    service = _service(runtime, provider)

    with pytest.raises(SimulatedProcessCrash):
        service.start("owner-1", _body())

    [running] = runtime.list("owner-1", "space-1", "tutor")
    assert running.status == "running"
    [reserved] = runtime.list_attempts(running.key)
    assert reserved["status"] == "reserved"
    assert len(provider.calls) == 1

    assert runtime.reconcile_abandoned("owner-1", set()) == 1
    interrupted = runtime.load(running.key)
    assert interrupted.status == "interrupted"
    [unknown] = runtime.list_attempts(running.key)
    assert unknown["status"] == "unknown"

    recovered = service.resume(
        "owner-1",
        "tutor",
        running.key.activity_id,
        {
            "schema_version": 1,
            "space_id": "space-1",
            "expected_revision": interrupted.revision,
            "mode": "recover",
        },
    )
    assert recovered.status == "blocked"
    assert recovered.terminal["reason_code"] == "provider_attempt_exhausted"
    assert recovered.terminal["budget_summary"]["attempts_used"] == 1
    assert len(provider.calls) == 1


def test_segment_provider_timeout_reserves_finalize_headroom(runtime) -> None:
    provider = _Provider()
    service = _service(runtime, provider)

    service.start("owner-1", _body())

    [_reservation, _request, timeout_s] = provider.calls[0]
    assert 0 < timeout_s <= 35
