from __future__ import annotations

import copy

import pytest

from agent.graph_engine.tutor_engine import TutorActivityExecutor, TutorGraphEngine
from agent.graph_engine.tutor_ports import (
    TutorProviderBinding,
    TutorProviderOutputError,
)
from agent.graph_engine.tutor_contracts import TutorProviderPlanV1, TutorProviderResult
from learning.tutor_activity import TutorActivityService
from learning.tutor_contract import TutorConflictError
from learning.tutor_runtime_store import TutorRuntimeStore
from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningStore
from learning.output_writer import OutputWriter
from learning.quizzes import QuizService
from learning.tutor_practice import TutorPracticeAdapter


def _body(idempotency="start-1"):
    return {
        "schema_version": 1,
        "space_id": "space-1",
        "activity_kind": "tutor",
        "idempotency_key": idempotency,
        "goal": "Explain fractions",
        "input_refs": [],
    }


def _practice_body(artifact_id, item_id, idempotency="practice-start-1"):
    return {
        **_body(idempotency),
        "goal": "Practice one trusted question",
        "tutor_mode": "deterministic_practice",
        "practice_ref": {"artifact_id": artifact_id, "item_id": item_id},
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


def _service(runtime, provider, *, started=None, finished=None):
    executor = TutorActivityExecutor(
        runtime,
        resolver=_Resolver(),
        provider_factory=lambda _binding: provider,
        execution_started=(started or (lambda _execution_id: None)),
        execution_finished=(finished or (lambda _execution_id: None)),
    )
    return TutorActivityService(runtime, executor)


def _practice_service(runtime, provider, context, *, graph=None):
    executor = TutorActivityExecutor(
        runtime,
        resolver=_Resolver(),
        graph=graph,
        provider_factory=lambda _binding: provider,
        practice_adapter_factory=lambda _key: TutorPracticeAdapter(
            context,
            now=lambda: "2026-07-26T12:00:00Z",
        ),
    )
    return TutorActivityService(runtime, executor)


@pytest.fixture()
def practice_context(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    context = LearningExecutionContext(store, owner_id="owner-1")
    context.create_space(title="Practice", space_id="space-1")
    artifact_id = OutputWriter(context).write_artifact(
        kind="quiz",
        title="Trusted quiz",
        payload={
            "questions": [
                {
                    "type": "choice",
                    "prompt": "2 + 2 = ?",
                    "options": ["3", "4"],
                    "answer": 1,
                }
            ]
        },
    )["artifact_id"]
    quiz = QuizService(context)
    quiz.activate_quiz(artifact_id)
    item_id = quiz.list_questions(artifact_id=artifact_id)[0]["item_id"]
    try:
        yield context, artifact_id, item_id
    finally:
        store.close()


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


def test_practice_correct_completes_from_trusted_grader_without_quiz_activity(
    runtime, practice_context
) -> None:
    context, artifact_id, item_id = practice_context
    provider = _Provider()
    service = _practice_service(runtime, provider, context)

    waiting = service.start("owner-1", _practice_body(artifact_id, item_id))
    assert waiting.status == "waiting_for_learner"
    assert waiting.interrupt.expected_input == "choice"
    assert waiting.interrupt.prompt == {
        "schema_version": 1,
        "template": "practice-v1",
        "message": "2 + 2 = ?",
        "options": [
            {"id": "0", "label": "3"},
            {"id": "1", "label": "4"},
        ],
    }

    completed = service.resume(
        "owner-1",
        "tutor",
        waiting.key.activity_id,
        _answer(waiting, "1"),
    )

    assert completed.status == "completed"
    assert completed.terminal["completion_basis"] == "deterministic_correct"
    assert completed.terminal["budget_summary"]["attempts_used"] == 1
    assert len(provider.calls) == 1
    assert context.list_activities() == []


def test_practice_incorrect_remediates_once_then_blocks(runtime, practice_context):
    context, artifact_id, item_id = practice_context
    provider = _Provider()
    service = _practice_service(runtime, provider, context)
    first = service.start("owner-1", _practice_body(artifact_id, item_id))

    second = service.resume(
        "owner-1", "tutor", first.key.activity_id, _answer(first, "0")
    )
    assert second.status == "waiting_for_learner"
    assert second.latest_output == {"kind": "feedback", "markdown": "remediation"}
    assert [call[1].purpose for call in provider.calls] == ["explain", "remediate"]
    remediation = provider.calls[1][1].remediation_context
    assert remediation["branch_reason"] == "deterministic_incorrect"
    assert remediation["learner_excerpt"] == '{"selected":["0"],"type":"choice"}'
    checkpoint = runtime.load(second.key).checkpoint.state
    assert checkpoint["current_remediation"] == remediation

    blocked = service.resume(
        "owner-1", "tutor", second.key.activity_id, _answer(second, "0")
    )
    assert blocked.status == "blocked"
    assert blocked.terminal["reason_code"] == "remediation_exhausted"
    assert blocked.terminal["budget_summary"]["attempts_used"] == 2
    assert len(provider.calls) == 2


def test_practice_invalid_answer_reissues_without_provider(runtime, practice_context):
    context, artifact_id, item_id = practice_context
    provider = _Provider()
    service = _practice_service(runtime, provider, context)
    first = service.start("owner-1", _practice_body(artifact_id, item_id))

    invalid = service.resume(
        "owner-1", "tutor", first.key.activity_id, _answer(first, "7")
    )
    assert invalid.status == "waiting_for_learner"
    assert invalid.interrupt.interrupt_id != first.interrupt.interrupt_id
    assert len(provider.calls) == 1

    completed = service.resume(
        "owner-1", "tutor", invalid.key.activity_id, _answer(invalid, "1")
    )
    assert completed.status == "completed"
    assert completed.terminal["completion_basis"] == "deterministic_correct"
    assert len(provider.calls) == 1


def test_practice_source_drift_blocks_before_grading(runtime, practice_context):
    context, artifact_id, item_id = practice_context
    provider = _Provider()
    service = _practice_service(runtime, provider, context)
    waiting = service.start("owner-1", _practice_body(artifact_id, item_id))
    row = next(row for row in context.list_items() if row["item_id"] == item_id)
    state = dict(row["state"])
    state["answer"] = 0
    context.update_item_state(item_id, state)

    blocked = service.resume(
        "owner-1", "tutor", waiting.key.activity_id, _answer(waiting, "0")
    )

    assert blocked.status == "blocked"
    assert blocked.terminal["reason_code"] == "source_missing"
    assert len(provider.calls) == 1


def test_practice_start_replay_precedes_source_resolution_and_payload_drift_conflicts(
    runtime, practice_context
):
    context, artifact_id, item_id = practice_context
    provider = _Provider()
    service = _practice_service(runtime, provider, context)
    body = _practice_body(artifact_id, item_id)
    first = service.start("owner-1", body)
    row = next(row for row in context.list_items() if row["item_id"] == item_id)
    state = dict(row["state"])
    state["answer"] = 0
    context.update_item_state(item_id, state)

    replay = service.start("owner-1", body)
    assert replay.key == first.key
    assert replay.revision == first.revision
    assert len(provider.calls) == 1

    with pytest.raises(TutorConflictError) as conflict:
        service.start("owner-1", {**body, "goal": "different payload"})
    assert conflict.value.reason_code == "idempotency_payload_mismatch"


def test_practice_answer_claim_crash_recovers_same_evaluation_identity(
    runtime, practice_context
):
    class SimulatedProcessCrash(BaseException):
        pass

    class CrashBeforeFirstResume:
        def __init__(self):
            self.real = TutorGraphEngine()
            self.calls = 0

        def run_segment(self, state, services):
            self.calls += 1
            if self.calls == 2:
                raise SimulatedProcessCrash()
            return self.real.run_segment(state, services)

    context, artifact_id, item_id = practice_context
    provider = _Provider()
    graph = CrashBeforeFirstResume()
    service = _practice_service(runtime, provider, context, graph=graph)
    waiting = service.start("owner-1", _practice_body(artifact_id, item_id))

    with pytest.raises(SimulatedProcessCrash):
        service.resume(
            "owner-1", "tutor", waiting.key.activity_id, _answer(waiting, "1")
        )

    running = runtime.load(waiting.key)
    assert running.status == "running"
    assert (
        running.checkpoint.state["learner_answer_checkpoint_revision"]
        == waiting.revision
    )
    assert runtime.reconcile_abandoned("owner-1", set()) == 1
    interrupted = runtime.load(waiting.key)

    completed = service.resume(
        "owner-1",
        "tutor",
        waiting.key.activity_id,
        {
            "schema_version": 1,
            "space_id": "space-1",
            "expected_revision": interrupted.revision,
            "mode": "recover",
        },
    )

    assert completed.status == "completed"
    assert completed.terminal["completion_basis"] == "deterministic_correct"
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


def test_nonconforming_provider_error_is_settled_before_block(runtime) -> None:
    provider = _Provider(error=ValueError("must not escape or remain reserved"))
    service = _service(runtime, provider)

    blocked = service.start("owner-1", _body())

    assert blocked.status == "blocked"
    assert blocked.terminal["reason_code"] == "provider_unavailable"
    assert blocked.terminal["budget_summary"]["attempts_used"] == 1
    assert runtime.list_attempts(blocked.key) == []


def test_idempotent_start_returns_existing_activity_without_second_call(
    runtime,
) -> None:
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
    started = []
    finished = []
    service = _service(
        runtime,
        provider,
        started=started.append,
        finished=finished.append,
    )

    with pytest.raises(SimulatedProcessCrash):
        service.start("owner-1", _body())

    [running] = runtime.list("owner-1", "space-1", "tutor")
    assert running.status == "running"
    [reserved] = runtime.list_attempts(running.key)
    assert reserved["status"] == "reserved"
    assert len(provider.calls) == 1
    assert started == finished
    assert len(started) == 1

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


def test_less_than_finalize_reserve_blocks_before_attempt(runtime) -> None:
    class Clock:
        def __init__(self):
            self.values = iter([0.0, 0.0, 36.0, 36.0, 36.0])

        def __call__(self):
            return next(self.values, 36.0)

    provider = _Provider()
    executor = TutorActivityExecutor(
        runtime,
        resolver=_Resolver(),
        provider_factory=lambda _binding: provider,
        monotonic=Clock(),
    )
    service = TutorActivityService(runtime, executor)

    blocked = service.start("owner-1", _body())

    assert blocked.status == "blocked"
    assert blocked.terminal["reason_code"] == "budget_exhausted"
    assert blocked.terminal["budget_summary"]["attempts_used"] == 0
    assert provider.calls == []


def test_waiting_activity_can_cancel_without_another_provider_call(runtime) -> None:
    provider = _Provider()
    service = _service(runtime, provider)
    waiting = service.start("owner-1", _body())

    cancelled = service.cancel(
        "owner-1",
        "tutor",
        waiting.key.activity_id,
        {
            "schema_version": 1,
            "space_id": "space-1",
            "expected_revision": waiting.revision,
        },
    )

    assert cancelled.status == "cancelled"
    assert cancelled.terminal["reason_code"] == "user_cancelled"
    assert cancelled.terminal["budget_summary"]["attempts_used"] == 1
    assert len(provider.calls) == 1


def test_stale_duplicate_answer_loses_cas_without_provider_call(runtime) -> None:
    provider = _Provider()
    service = _service(runtime, provider)
    waiting = service.start("owner-1", _body())
    request = _answer(waiting, "continue")

    completed = service.resume("owner-1", "tutor", waiting.key.activity_id, request)
    assert completed.status == "completed"

    with pytest.raises(TutorConflictError) as exc:
        service.resume("owner-1", "tutor", waiting.key.activity_id, request)
    assert exc.value.reason_code == "terminal_immutable"
    assert len(provider.calls) == 1
