from __future__ import annotations

import copy

import pytest

from agent.graph_engine.tutor_contracts import TutorProviderPlanV1, TutorProviderResult
from agent.graph_engine.tutor_engine import TutorActivityExecutor
from agent.graph_engine.tutor_ports import TutorProviderBinding
from learning.learning_store import LearningStore
from learning.tutor_activity import TutorActivityService
from learning.tutor_contract import (
    TutorConflictError,
    TutorContractError,
)
from learning.tutor_runtime_store import TutorRuntimeStore
from learning.tutor_whiteboard import (
    TutorWhiteboardPort,
    preview_tutor_whiteboard_scene,
    validate_tutor_whiteboard_commands,
)
from learning.whiteboard import WhiteboardService


OWNER = "desktop:owner-test"
SPACE = "space-1"


def _element(element_id: str = "e1", content: str = "One bounded fact") -> dict:
    return {
        "element_id": element_id,
        "type": "text",
        "x": 10,
        "y": 20,
        "tone": "ink",
        "stroke_width": 1,
        "width": 240,
        "height": 50,
        "content": content,
    }


def _batch(*commands: dict) -> dict:
    return {"schema_version": 1, "commands": list(commands)}


class _Resolver:
    def __init__(self) -> None:
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
    def execute_once(self, reservation, request, *, timeout_s):
        del reservation, request, timeout_s
        return TutorProviderResult(
            markdown="Readable Tutor explanation",
            actual_input_tokens=10,
            actual_output_tokens=5,
            actual_latency_ms=20,
        )


@pytest.fixture()
def runtime(tmp_path):
    learning = LearningStore(tmp_path / "learning.db")
    learning.create_space(OWNER, title="Course", space_id=SPACE)
    tutor = TutorRuntimeStore(
        tmp_path / "tutor_runtime.db", coordinator=learning.coordinator
    )
    executor = TutorActivityExecutor(
        tutor,
        resolver=_Resolver(),
        provider_factory=lambda _binding: _Provider(),
    )
    activity = TutorActivityService(tutor, executor).start(
        OWNER,
        {
            "schema_version": 1,
            "space_id": SPACE,
            "activity_kind": "tutor",
            "idempotency_key": "start-whiteboard",
            "goal": "Explain one bounded idea",
            "input_refs": [],
        },
    )
    key = activity.key
    port = TutorWhiteboardPort(
        tutor, WhiteboardService(learning, OWNER, SPACE)
    )
    try:
        yield learning, tutor, key, activity, port
    finally:
        tutor.close()
        learning.close()


def test_command_contract_is_exact_bounded_and_non_executable():
    commands = validate_tutor_whiteboard_commands(
        _batch({"op": "put_element", "element": _element()})
    )
    assert commands[0]["element"]["element_id"] == "e1"

    for rejected in (
        _batch({"op": "run_javascript", "script": "alert(1)"}),
        _batch(
            {
                "op": "put_element",
                "element": _element(content='<svg onload="alert(1)">'),
            }
        ),
        _batch(
            {"op": "put_element", "element": _element()},
            {"op": "delete_element", "element_id": "e1"},
        ),
    ):
        with pytest.raises(TutorContractError):
            validate_tutor_whiteboard_commands(rejected)


def test_preview_is_pure_and_delete_requires_an_existing_element():
    empty = {"schema_version": 1, "elements": []}
    preview = preview_tutor_whiteboard_scene(
        empty, [{"op": "put_element", "element": _element()}]
    )
    assert empty["elements"] == []
    assert preview["elements"] == [_element()]
    with pytest.raises(TutorContractError, match="does not exist"):
        preview_tutor_whiteboard_scene(
            empty, [{"op": "delete_element", "element_id": "missing"}]
        )


def test_preview_then_apply_binds_tutor_revision_and_replays(runtime):
    _learning, tutor, key, activity, port = runtime
    batch = _batch({"op": "put_element", "element": _element()})
    before = tutor.load(key)

    preview = port.preview(
        key,
        expected_tutor_revision=activity.revision,
        expected_working_revision=0,
        command_batch=batch,
    )
    assert port.whiteboard.load_working(key.activity_id) is None
    applied = port.apply(
        key,
        expected_tutor_revision=activity.revision,
        expected_working_revision=0,
        command_batch=batch,
        preview_sha256=preview["preview_sha256"],
        idempotency_key="apply-1",
    )
    replay = port.apply(
        key,
        expected_tutor_revision=activity.revision,
        expected_working_revision=0,
        command_batch=batch,
        preview_sha256=preview["preview_sha256"],
        idempotency_key="apply-1",
    )

    assert applied["status"] == "saved"
    assert applied["working"]["revision"] == 1
    assert replay["working"]["replayed"] is True
    after = tutor.load(key)
    assert after == before


def test_rejected_preview_or_stale_binding_writes_neither_store(runtime):
    _learning, tutor, key, activity, port = runtime
    batch = _batch({"op": "put_element", "element": _element()})
    original = tutor.load(key)
    preview = port.preview(
        key,
        expected_tutor_revision=activity.revision,
        expected_working_revision=0,
        command_batch=batch,
    )
    with pytest.raises(TutorConflictError, match="whiteboard_preview_mismatch"):
        port.apply(
            key,
            expected_tutor_revision=activity.revision,
            expected_working_revision=0,
            command_batch=batch,
            preview_sha256="0" * 64,
            idempotency_key="apply-tampered",
        )
    with pytest.raises(TutorConflictError, match="stale_revision"):
        port.apply(
            key,
            expected_tutor_revision=activity.revision + 1,
            expected_working_revision=0,
            command_batch=batch,
            preview_sha256=preview["preview_sha256"],
            idempotency_key="apply-stale",
        )
    assert port.whiteboard.load_working(key.activity_id) is None
    assert tutor.load(key) == original


def test_snapshot_attach_recover_cancel_share_tutor_identity(runtime):
    _learning, tutor, key, activity, port = runtime
    first_batch = _batch({"op": "put_element", "element": _element()})
    first_preview = port.preview(
        key,
        expected_tutor_revision=activity.revision,
        expected_working_revision=0,
        command_batch=first_batch,
    )
    port.apply(
        key,
        expected_tutor_revision=activity.revision,
        expected_working_revision=0,
        command_batch=first_batch,
        preview_sha256=first_preview["preview_sha256"],
        idempotency_key="apply-1",
    )
    snapshot = port.snapshot(
        key,
        expected_tutor_revision=activity.revision,
        expected_working_revision=1,
        idempotency_key="snapshot-1",
    )
    artifact_id = snapshot["result"]["artifact_id"]
    persisted_snapshot = port.whiteboard.get_snapshot(artifact_id)
    assert persisted_snapshot["envelope"]["source_refs"][0][
        "tutor_checkpoint_revision"
    ] == activity.revision
    attached = port.attach(
        key,
        artifact_id,
        expected_tutor_revision=activity.revision,
        idempotency_key="attach-1",
    )
    assert attached["result"]["status"] == "active"

    second_batch = _batch(
        {"op": "put_element", "element": _element(content="Changed")}
    )
    second_preview = port.preview(
        key,
        expected_tutor_revision=activity.revision,
        expected_working_revision=1,
        command_batch=second_batch,
    )
    port.apply(
        key,
        expected_tutor_revision=activity.revision,
        expected_working_revision=1,
        command_batch=second_batch,
        preview_sha256=second_preview["preview_sha256"],
        idempotency_key="apply-2",
    )
    recovered = port.recover(
        key,
        artifact_id,
        expected_tutor_revision=activity.revision,
        expected_working_revision=2,
        idempotency_key="recover-1",
    )
    assert recovered["result"]["revision"] == 3
    assert recovered["result"]["scene_sha256"] == snapshot["result"]["scene_sha256"]
    cancelled = port.cancel(
        key,
        expected_tutor_revision=activity.revision,
        expected_working_revision=3,
        idempotency_key="cancel-1",
    )
    assert cancelled["result"]["deleted"] is True
    assert tutor.load(key).revision == activity.revision


def test_whiteboard_failure_fallback_preserves_readable_tutor_check(runtime):
    _learning, tutor, key, _activity, port = runtime
    waiting = tutor.load(key)
    answer = {"type": "choice", "selected": ["continue"]}
    claimed = tutor.claim_answer(
        key,
        expected_revision=waiting.revision,
        execution_id="whiteboard-fallback-test",
        interrupt_id=waiting.checkpoint.state["pending_interrupt"]["interrupt_id"],
        answer=answer,
    )
    original = copy.deepcopy(claimed)
    invalid = _batch(
        {
            "op": "put_element",
            "element": _element(content="javascript:alert(1)"),
        }
    )
    with pytest.raises(TutorContractError):
        port.preview(
            key,
            expected_tutor_revision=claimed.revision,
            expected_working_revision=0,
            command_batch=invalid,
        )
    fallback = port.fallback_projection(key)
    assert fallback["latest_output"] == {
        "kind": "explanation",
        "markdown": "Readable Tutor explanation",
    }
    assert fallback["pending_interrupt"] is None
    assert tutor.load(key).checkpoint.state["learner_answer"] == answer
    assert tutor.load(key) == original
