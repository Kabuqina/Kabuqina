"""SQLite adapter tests for the Tutor runtime truth database."""

from __future__ import annotations

import copy
import multiprocessing
from pathlib import Path
import sqlite3

import pytest

from learning.checkpoint_store import LearningCheckpointV1
from learning.operation_coordinator import LearningOperationInProgressError
from learning.tutor_contract import (
    TutorConflictError,
    TutorContractError,
    validate_start_request,
)
from learning.tutor_runtime_store import (
    RUNTIME_SCHEMA_VERSION,
    ProviderAttemptReservationV1,
    TutorRuntimeBusyError,
    TutorRuntimeSchemaError,
    TutorRuntimeStore,
)


def _spawn_runtime_create(path: str, activity_id: str, ready, output) -> None:
    store = TutorRuntimeStore(Path(path))
    try:
        request = _request(activity=activity_id)
        ready.wait(10)
        record, created = store.create(request, _checkpoint(request))
        output.put((created, record.key.activity_id))
    except Exception as exc:
        output.put((type(exc).__name__, getattr(exc, "reason_code", None)))
    finally:
        store.close()


def _request(
    *,
    owner="owner-1",
    space="space-1",
    kind="tutor",
    activity="activity-1",
    idempotency="start-1",
    goal="Learn quadratics",
):
    return validate_start_request(
        {
            "schema_version": 1,
            "space_id": space,
            "activity_kind": kind,
            "idempotency_key": idempotency,
            "goal": goal,
            "input_refs": [],
        },
        owner_id=owner,
        activity_id=activity,
    )


def _checkpoint(request, *, revision=0, status="created", extra=None):
    state = {
        "schema_version": 1,
        "phase": "start",
        "goal": request.goal,
        "input_refs": list(request.input_refs),
        "budget": {
            "nodes_used": 0,
            "attempts_used": 0,
            "reserved_input_tokens": 0,
            "reserved_output_tokens": 0,
            "reserved_wall_ms": 0,
            "active_elapsed_ms": 0,
        },
    }
    if extra:
        state.update(extra)
    return LearningCheckpointV1(
        key=request.key,
        revision=revision,
        status=status,
        state=state,
    )


@pytest.fixture()
def runtime(tmp_path):
    store = TutorRuntimeStore(tmp_path / "tutor_runtime.db")
    yield store
    store.close()


def test_fresh_runtime_schema_is_independent_v1_wal_and_secure(runtime):
    assert RUNTIME_SCHEMA_VERSION == 1
    assert runtime.connection_settings() == {
        "journal_mode": "wal",
        "secure_delete": 1,
    }
    assert runtime.table_names() >= {
        "tutor_runtime_schema_version",
        "tutor_activity_runs",
        "tutor_checkpoints",
        "tutor_provider_attempts",
        "tutor_projection_outbox",
    }
    with sqlite3.connect(runtime.db_path) as connection:
        assert connection.execute(
            "SELECT version FROM tutor_runtime_schema_version WHERE singleton=1"
        ).fetchone()[0] == 1


def test_unknown_newer_runtime_schema_fails_closed(tmp_path):
    path = tmp_path / "tutor_runtime.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE tutor_runtime_schema_version "
            "(singleton INTEGER PRIMARY KEY, version INTEGER NOT NULL)"
        )
        connection.execute(
            "INSERT INTO tutor_runtime_schema_version VALUES (1, 2)"
        )
        assert connection.execute("PRAGMA journal_mode=DELETE").fetchone()[0] == "delete"
    with pytest.raises(TutorRuntimeSchemaError) as caught:
        TutorRuntimeStore(path)
    assert caught.value.version == 2
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT version FROM tutor_runtime_schema_version"
        ).fetchone()[0] == 2
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"


def test_default_runtime_database_acl_is_user_only(tmp_path, monkeypatch):
    import learning.tutor_runtime_store as runtime_module
    from learning.learning_store import audit_default_learning_db_acl

    path = tmp_path / "private" / "tutor_runtime.db"
    monkeypatch.setattr(runtime_module, "default_tutor_runtime_db_path", lambda: path)
    store = TutorRuntimeStore()
    store.close()
    assert audit_default_learning_db_acl(path) is True


def test_create_idempotency_uses_kind_namespace_and_payload_fingerprint(runtime):
    original = _request(activity="activity-1")
    first, created = runtime.create(original, _checkpoint(original), label="Algebra")
    retry = _request(activity="activity-on-retry")
    repeated, repeated_created = runtime.create(retry, _checkpoint(retry))
    assert created is True
    assert repeated_created is False
    assert repeated.key == first.key == original.key

    changed = _request(activity="activity-2", goal="Different")
    with pytest.raises(TutorConflictError) as caught:
        runtime.create(changed, _checkpoint(changed))
    assert caught.value.reason_code == "idempotency_payload_mismatch"

    review = _request(kind="review", activity="activity-1")
    runtime.create(review, _checkpoint(review))
    assert runtime.load(original.key).key.activity_kind == "tutor"
    assert runtime.load(review.key).key.activity_kind == "review"


def test_create_enforces_per_space_nonterminal_quota_without_partial_row(runtime):
    for index in range(6):
        request = _request(activity=f"activity-{index}", idempotency=f"start-{index}")
        runtime.create(request, _checkpoint(request))
    overflow = _request(activity="overflow", idempotency="overflow")
    with pytest.raises(TutorConflictError) as caught:
        runtime.create(overflow, _checkpoint(overflow))
    assert caught.value.reason_code == "nonterminal_space_quota"
    assert runtime.load(overflow.key) is None


def test_checkpoint_cap_is_checked_before_any_runtime_write(runtime):
    request = _request()
    with pytest.raises(Exception) as caught:
        runtime.create(
            request,
            _checkpoint(request, extra={"large": "界" * (256 * 1024)}),
        )
    assert getattr(caught.value, "reason_code", None) == "checkpoint_too_large"
    assert runtime.load(request.key) is None


def test_revision_cas_is_shared_across_two_store_instances(tmp_path):
    path = tmp_path / "tutor_runtime.db"
    first = TutorRuntimeStore(path)
    second = TutorRuntimeStore(path)
    try:
        request = _request()
        first.create(request, _checkpoint(request))
        claimed = first.claim_execution(
            request.key, expected_revision=0, execution_id="exec-1"
        )
        assert claimed.status == "running"
        assert claimed.revision == 1
        with pytest.raises(TutorConflictError) as caught:
            second.claim_execution(
                request.key, expected_revision=0, execution_id="exec-stale"
            )
        assert caught.value.reason_code == "stale_revision"
    finally:
        first.close()
        second.close()


def test_two_spawned_processes_share_idempotency_and_create_one_row(tmp_path):
    path = tmp_path / "tutor_runtime.db"
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    output = context.Queue()
    processes = [
        context.Process(
            target=_spawn_runtime_create,
            args=(str(path), f"activity-{index}", ready, output),
        )
        for index in range(2)
    ]
    for process in processes:
        process.start()
    ready.set()
    for process in processes:
        process.join(15)
        assert process.exitcode == 0
    results = [output.get(timeout=2) for _ in processes]
    assert sorted(created for created, _ in results) == [False, True]
    assert len({activity_id for _, activity_id in results}) == 1
    verifier = TutorRuntimeStore(path)
    try:
        assert len(verifier.list("owner-1", "space-1", "tutor")) == 1
    finally:
        verifier.close()


def test_runtime_busy_failure_is_bounded_typed_and_zero_write(runtime):
    request = _request()
    blocker = sqlite3.connect(runtime.db_path, timeout=0, isolation_level=None)
    blocker.execute("BEGIN IMMEDIATE")
    runtime._MAX_RETRIES = 2
    runtime._RETRY_MIN_S = 0.01
    runtime._RETRY_MAX_S = 0.01
    try:
        with pytest.raises(TutorRuntimeBusyError) as caught:
            runtime.create(request, _checkpoint(request))
        assert caught.value.reason_code == "tutor_runtime_busy"
    finally:
        blocker.rollback()
        blocker.close()
    assert runtime.load(request.key) is None


def test_wait_interrupt_is_saved_atomically_with_run_revision(runtime):
    request = _request()
    runtime.create(request, _checkpoint(request))
    runtime.claim_execution(request.key, expected_revision=0, execution_id="exec-1")
    waiting = _checkpoint(
        request,
        revision=1,
        status="waiting_for_learner",
        extra={
            "pending_interrupt": {
                "schema_version": 1,
                "interrupt_id": "lint_1",
                "kind": "learner_check",
                "owner_id": "owner-1",
                "space_id": "space-1",
                "activity_kind": "tutor",
                "activity_id": "activity-1",
                "checkpoint_revision": 2,
                "prompt": {"markdown": "Continue?"},
                "expected_input": "choice",
                "created_at": "2026-07-19T00:00:00Z",
            }
        },
    )
    saved = runtime.save(waiting, expected_revision=1)
    assert saved.revision == 2
    assert saved.checkpoint.revision == 2
    assert saved.status == "waiting_for_learner"
    assert runtime.raw_run(request.key)["current_interrupt_id"] == "lint_1"


def test_answer_claim_binds_interrupt_and_revision_before_writing_answer(runtime):
    request = _request()
    runtime.create(request, _checkpoint(request))
    runtime.claim_execution(request.key, expected_revision=0, execution_id="exec-1")
    waiting = _checkpoint(
        request,
        revision=1,
        status="waiting_for_learner",
        extra={
            "pending_interrupt": {
                "schema_version": 1,
                "interrupt_id": "lint_1",
                "kind": "learner_check",
                "owner_id": "owner-1",
                "space_id": "space-1",
                "activity_kind": "tutor",
                "activity_id": "activity-1",
                "checkpoint_revision": 2,
                "prompt": {
                    "markdown": "Continue?",
                    "options": [{"id": "continue", "label": "Continue"}],
                },
                "expected_input": "choice",
                "created_at": "2026-07-19T00:00:00Z",
            }
        },
    )
    runtime.save(waiting, expected_revision=1)
    with pytest.raises(TutorConflictError) as caught:
        runtime.claim_execution(
            request.key, expected_revision=2, execution_id="bypass-answer"
        )
    assert caught.value.reason_code == "interrupt_answer_required"
    with pytest.raises(TutorConflictError) as caught:
        runtime.claim_answer(
            request.key,
            expected_revision=2,
            execution_id="exec-wrong",
            interrupt_id="lint_wrong",
            answer={"type": "choice", "selected": ["continue"]},
        )
    assert caught.value.reason_code == "interrupt_mismatch"
    assert runtime.load(request.key).revision == 2

    claimed = runtime.claim_answer(
        request.key,
        expected_revision=2,
        execution_id="exec-2",
        interrupt_id="lint_1",
        answer={"type": "choice", "selected": ["continue"]},
    )
    assert claimed.status == "running"
    assert claimed.revision == 3
    assert "pending_interrupt" not in claimed.checkpoint.state
    assert claimed.checkpoint.state["learner_answer"] == {
        "type": "choice",
        "selected": ["continue"],
    }
    with pytest.raises(TutorConflictError) as caught:
        runtime.claim_answer(
            request.key,
            expected_revision=2,
            execution_id="exec-stale",
            interrupt_id="lint_1",
            answer={"type": "choice", "selected": ["continue"]},
        )
    assert caught.value.reason_code == "stale_revision"


def test_provider_reservation_settlement_and_terminal_fold_are_atomic(runtime):
    request = _request()
    runtime.create(request, _checkpoint(request))
    runtime.claim_execution(request.key, expected_revision=0, execution_id="exec-1")
    reserved = runtime.reserve_provider_attempt(
        request.key,
        expected_revision=1,
        reservation=ProviderAttemptReservationV1(
            attempt_id="attempt-1",
            segment_id="segment-1",
            ordinal=1,
            provider_id="provider-1",
            model_id="model-1",
            api_mode="chat_completions",
            reserved_input_tokens=10,
            reserved_output_tokens=20,
            reserved_wall_ms=100,
        ),
    )
    assert reserved.revision == 2
    assert runtime.list_attempts(request.key)[0]["status"] == "reserved"
    settled = runtime.settle_provider_attempt(
        request.key,
        attempt_id="attempt-1",
        expected_revision=2,
        status="succeeded",
        actual_input_tokens=8,
        actual_output_tokens=12,
        actual_latency_ms=50,
    )
    assert settled.revision == 3

    progress_state = copy.deepcopy(settled.checkpoint.state)
    progress_state["budget"]["nodes_used"] = 1
    progress_state["budget"]["active_elapsed_ms"] = 50
    progress = runtime.save(
        LearningCheckpointV1(
            key=request.key,
            revision=3,
            status="running",
            state=progress_state,
        ),
        expected_revision=3,
    )
    assert progress.revision == 4

    terminal = runtime.commit_terminal(
        request.key,
        expected_revision=4,
        outcome="completed",
        terminal_code="completed",
        completion_basis="participation_only",
        remediation_count=0,
        budget_summary={
            "nodes_used": 1,
            "attempts_used": 1,
            "reserved_input_tokens": 10,
            "reserved_output_tokens": 20,
            "reserved_wall_ms": 100,
            "active_elapsed_ms": 50,
        },
    )
    assert terminal.status == "completed"
    assert terminal.revision == 5
    assert runtime.load_checkpoint(request.key) is None
    assert runtime.list_attempts(request.key) == []
    outbox = runtime.list_pending_outbox("owner-1")
    assert len(outbox) == 1
    assert outbox[0]["activity_id"] == "activity-1"
    assert len(outbox[0]["payload_json"].encode("utf-8")) <= 512
    row = runtime.raw_run(request.key)
    assert row["budget_attempts_used"] == 1
    assert row["budget_reserved_output_tokens"] == 20

    with pytest.raises(TutorConflictError) as caught:
        runtime.claim_execution(
            request.key, expected_revision=5, execution_id="cannot-revive"
        )
    assert caught.value.reason_code == "terminal_immutable"


def test_token_usage_aggregates_only_successful_measured_attempts(runtime):
    request = _request()
    runtime.create(request, _checkpoint(request))
    runtime.claim_execution(request.key, expected_revision=0, execution_id="exec-1")

    revision = 1
    for ordinal, actual in (
        (1, (8, 12)),
        (2, (None, None)),
    ):
        runtime.reserve_provider_attempt(
            request.key,
            expected_revision=revision,
            reservation=ProviderAttemptReservationV1(
                attempt_id=f"attempt-{ordinal}",
                segment_id=f"segment-{ordinal}",
                ordinal=ordinal,
                provider_id="provider-1",
                model_id="model-1",
                api_mode="chat_completions",
                reserved_input_tokens=10,
                reserved_output_tokens=20,
                reserved_wall_ms=100,
            ),
        )
        revision += 1
        runtime.settle_provider_attempt(
            request.key,
            attempt_id=f"attempt-{ordinal}",
            expected_revision=revision,
            status="succeeded",
            actual_input_tokens=actual[0],
            actual_output_tokens=actual[1],
            actual_latency_ms=50,
        )
        revision += 1

    failed = _request(activity="activity-2", idempotency="start-2")
    runtime.create(failed, _checkpoint(failed))
    runtime.claim_execution(failed.key, expected_revision=0, execution_id="exec-2")
    runtime.reserve_provider_attempt(
        failed.key,
        expected_revision=1,
        reservation=ProviderAttemptReservationV1(
            attempt_id="failed-attempt",
            segment_id="failed-segment",
            ordinal=1,
            provider_id="provider-1",
            model_id="model-1",
            api_mode="chat_completions",
            reserved_input_tokens=50,
            reserved_output_tokens=60,
            reserved_wall_ms=100,
        ),
    )
    runtime.settle_provider_attempt(
        failed.key,
        attempt_id="failed-attempt",
        expected_revision=2,
        status="failed",
        actual_input_tokens=50,
        actual_output_tokens=60,
        actual_latency_ms=50,
    )

    rows = runtime.aggregate_token_usage(
        "owner-1",
        starts_at="2000-01-01T00:00:00Z",
        ends_at="2100-01-01T00:00:00Z",
    )
    assert rows == [
        {
            "space_id": "space-1",
            "provider_id": "provider-1",
            "model_id": "model-1",
            "succeeded_attempts": 2,
            "input_measured_attempts": 1,
            "output_measured_attempts": 1,
            "input_tokens": 8,
            "output_tokens": 12,
        }
    ]
    assert runtime.aggregate_token_usage(
        "owner-1",
        starts_at="2100-01-01T00:00:00Z",
        ends_at="2101-01-01T00:00:00Z",
    ) == []


def test_terminal_budget_mismatch_is_zero_write(runtime):
    request = _request()
    runtime.create(request, _checkpoint(request))
    runtime.claim_execution(request.key, expected_revision=0, execution_id="exec-1")
    with pytest.raises(TutorConflictError) as caught:
        runtime.commit_terminal(
            request.key,
            expected_revision=1,
            outcome="completed",
            terminal_code="completed",
            completion_basis="participation_only",
            remediation_count=0,
            budget_summary={
                "nodes_used": 1,
                "attempts_used": 1,
                "reserved_input_tokens": 10,
                "reserved_output_tokens": 10,
                "reserved_wall_ms": 10,
                "active_elapsed_ms": 1,
            },
        )
    assert caught.value.reason_code == "budget_summary_mismatch"
    assert runtime.load(request.key).status == "running"
    assert runtime.load_checkpoint(request.key) is not None
    assert runtime.list_pending_outbox("owner-1") == []


def test_cancel_wins_cas_clears_checkpoint_and_emits_one_stable_event(runtime):
    request = _request()
    runtime.create(request, _checkpoint(request))
    cancelled = runtime.cancel(request.key, expected_revision=0)
    assert cancelled.status == "cancelled"
    assert cancelled.checkpoint is None
    outbox = runtime.list_pending_outbox("owner-1")
    assert len(outbox) == 1
    assert runtime.mark_outbox_delivered("owner-1", outbox[0]["event_id"]) is True
    assert runtime.list_pending_outbox("owner-1") == []
    assert runtime.clear_checkpoint(request.key, expected_revision=1) == 1
    with pytest.raises(TutorConflictError) as caught:
        runtime.cancel(request.key, expected_revision=0)
    assert caught.value.reason_code == "terminal_immutable"
    assert runtime.list_pending_outbox("owner-1") == []


def test_reconcile_marks_abandoned_execution_and_reserved_attempt_unknown(runtime):
    request = _request()
    runtime.create(request, _checkpoint(request))
    runtime.claim_execution(request.key, expected_revision=0, execution_id="dead-exec")
    runtime.reserve_provider_attempt(
        request.key,
        expected_revision=1,
        reservation=ProviderAttemptReservationV1(
            attempt_id="attempt-1",
            segment_id="segment-1",
            ordinal=1,
            provider_id="provider-1",
            model_id="model-1",
            api_mode="chat_completions",
            reserved_input_tokens=1,
            reserved_output_tokens=1,
            reserved_wall_ms=35_000,
        ),
    )
    assert runtime.reconcile_abandoned("owner-1", live_execution_ids=set()) == 1
    recovered = runtime.load(request.key)
    assert recovered.status == "interrupted"
    assert recovered.revision == 3
    assert runtime.list_attempts(request.key)[0]["status"] == "unknown"
    assert runtime.raw_run(request.key)["budget_active_elapsed_ms"] == 45_000
    assert recovered.checkpoint.state["budget"]["active_elapsed_ms"] == 45_000


def test_reservation_and_checkpoint_budget_caps_fail_before_attempt_write(runtime):
    with pytest.raises(TutorContractError, match="per-attempt budget"):
        ProviderAttemptReservationV1(
            attempt_id="attempt-1",
            segment_id="segment-1",
            ordinal=1,
            provider_id="provider-1",
            model_id="model-1",
            api_mode="chat_completions",
            reserved_input_tokens=16_385,
            reserved_output_tokens=1,
            reserved_wall_ms=1,
        )
    request = _request()
    runtime.create(request, _checkpoint(request))
    runtime.claim_execution(request.key, expected_revision=0, execution_id="exec-1")
    state = copy.deepcopy(runtime.load_checkpoint(request.key).state)
    state["budget"]["nodes_used"] = 15
    with pytest.raises(TutorConflictError) as caught:
        runtime.save(
            LearningCheckpointV1(
                key=request.key,
                revision=1,
                status="running",
                state=state,
            ),
            expected_revision=1,
        )
    assert caught.value.reason_code == "budget_exhausted"
    assert runtime.load(request.key).revision == 1


def test_runtime_reads_and_writes_obey_same_coordination_fence(runtime):
    request = _request()
    runtime.create(request, _checkpoint(request))
    lease = runtime.coordinator.begin_operation("owner-1", "space-1", "delete")
    try:
        with pytest.raises(LearningOperationInProgressError):
            runtime.load(request.key)
        with pytest.raises(LearningOperationInProgressError):
            runtime.cancel(request.key, expected_revision=0)
        assert runtime.load(request.key, operation_lease=lease) is not None
    finally:
        runtime.coordinator.finish_operation(lease)
