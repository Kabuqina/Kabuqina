"""Composite two-business-DB operations and StudyOwnerBundleV2 tests."""

from __future__ import annotations

import copy
import hashlib
import json
import multiprocessing
import time

import pytest

import learning.tutor_runtime_store as runtime_store_module
from learning.checkpoint_store import LearningCheckpointV1
from learning.learning_data_service import (
    OWNER_BUNDLE_MAX_BYTES,
    CompositeLearningDataService,
    canonical_sha256,
)
from learning.learning_store import LearningConflictError
from learning.tutor_contract import (
    TutorConflictError,
    TutorContractError,
    canonical_json_bytes,
    validate_start_request,
)


def _spawn_project_with_barrier(root, owner, listed, release, output):
    service = CompositeLearningDataService.from_root(root)
    original = service.runtime_store.list_pending_outbox

    def list_then_wait(*args, **kwargs):
        events = original(*args, **kwargs)
        listed.set()
        release.wait(10)
        return events

    service.runtime_store.list_pending_outbox = list_then_wait
    try:
        output.put(("projection", service.project_pending_outbox(owner)))
    except BaseException as exc:
        output.put(("projection_error", type(exc).__name__))
    finally:
        service.close()


def _spawn_delete_after_projection(root, owner, space, output):
    service = CompositeLearningDataService.from_root(root)
    try:
        if space is None:
            result = service.delete_owner_data(owner)
        else:
            result = service.delete_space_data(owner, space)
        output.put(("delete", result))
    except BaseException as exc:
        output.put(("delete_error", type(exc).__name__))
    finally:
        service.close()


def _checkpoint(request):
    return LearningCheckpointV1(
        key=request.key,
        revision=0,
        status="created",
        state={
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
        },
    )


def _seed_space(service, owner, space, *, suffix="1", with_runtime=True):
    service.learning_store.create_space(
        owner, title=f"Course {suffix}", space_id=space, make_current=suffix == "1"
    )
    artifact = service.learning_store.insert_artifact(
        owner,
        space,
        {
            "version": 1,
            "kind": "tutoring_note",
            "space_id": space,
            "title": f"Note {suffix}",
            "source_refs": [],
            "payload": {
                "goal": "Understand the topic",
                "hints": ["Start from the definition"],
                "misconceptions": [],
                "next_steps": ["Try one example"],
            },
        },
    )["artifact_id"]
    service.learning_store.upsert_item(
        owner,
        space,
        item_id=f"item-{suffix}",
        item_type="fixture",
        artifact_id=artifact,
        state={"value": suffix},
    )
    service.learning_store.insert_activity(
        owner, space, activity_type="fixture.activity", detail={"suffix": suffix}
    )
    if not with_runtime:
        return artifact, None
    request = validate_start_request(
        {
            "schema_version": 1,
            "space_id": space,
            "activity_kind": "tutor",
            "idempotency_key": f"start-{suffix}",
            "goal": f"Learn {suffix}",
            "input_refs": [{"kind": "artifact", "id": artifact}],
        },
        owner_id=owner,
        activity_id=f"activity-{suffix}",
    )
    service.runtime_store.create(request, _checkpoint(request), label=f"Tutor {suffix}")
    return artifact, request


def _active_runtime_bundle(
    template,
    *,
    count,
    prefix,
    space_for_index,
    padding=0,
    attempts_per_run=0,
):
    active_run = copy.deepcopy(template["runs"][0])
    active_checkpoint = copy.deepcopy(template["checkpoints"][0])
    runs = []
    checkpoints = []
    attempts = []
    for index in range(count):
        space_id = space_for_index(index)
        activity_id = f"{prefix}-activity-{index:04d}"
        run = copy.deepcopy(active_run)
        run.update(
            {
                "space_id": space_id,
                "activity_id": activity_id,
                "idempotency_key": f"{prefix}-start-{index:04d}",
                "request_fingerprint": hashlib.sha256(
                    f"{prefix}-request-{index}".encode()
                ).hexdigest(),
            }
        )
        checkpoint = copy.deepcopy(active_checkpoint)
        checkpoint.update({"space_id": space_id, "activity_id": activity_id})
        checkpoint["state"]["input_refs"] = []
        if padding:
            checkpoint["state"]["padding"] = "x" * padding
        checkpoint["state_sha256"] = hashlib.sha256(
            canonical_json_bytes(checkpoint["state"])
        ).hexdigest()
        run["budget_attempts_used"] = attempts_per_run
        run["budget_reserved_input_tokens"] = attempts_per_run
        run["budget_reserved_output_tokens"] = attempts_per_run
        run["budget_reserved_wall_ms"] = attempts_per_run
        checkpoint["state"]["budget"].update(
            {
                "attempts_used": attempts_per_run,
                "reserved_input_tokens": attempts_per_run,
                "reserved_output_tokens": attempts_per_run,
                "reserved_wall_ms": attempts_per_run,
            }
        )
        checkpoint["state_sha256"] = hashlib.sha256(
            canonical_json_bytes(checkpoint["state"])
        ).hexdigest()
        for attempt_index in range(attempts_per_run):
            attempts.append(
                {
                    "space_id": space_id,
                    "activity_kind": run["activity_kind"],
                    "activity_id": activity_id,
                    "attempt_id": f"{prefix}-attempt-{index:04d}-{attempt_index + 1}",
                    "segment_id": f"{prefix}-segment-{index:04d}-{attempt_index + 1}",
                    "ordinal": attempt_index + 1,
                    "provider_id": "fixture-provider",
                    "model_id": "fixture-model",
                    "api_mode": "chat_completions",
                    "status": "unknown",
                    "reserved_input_tokens": 1,
                    "reserved_output_tokens": 1,
                    "reserved_wall_ms": 1,
                    "actual_input_tokens": None,
                    "actual_output_tokens": None,
                    "actual_latency_ms": None,
                    "reason_code": "crash_recovery",
                    "reserved_at": run["created_at"],
                    "completed_at": run["updated_at"],
                }
            )
        runs.append(run)
        checkpoints.append(checkpoint)
    return {
        "schema_version": 1,
        "runs": runs,
        "checkpoints": checkpoints,
        "attempts": attempts,
        "outbox": [],
    }


def _terminal_event_id(owner_id, run):
    identity = (
        owner_id,
        run["space_id"],
        run["activity_kind"],
        run["activity_id"],
    )
    return "tproj_" + hashlib.sha256("\x1f".join(identity).encode("utf-8")).hexdigest()


def _terminal_runtime_bundle(
    template, *, count, prefix, outbox_per_run=0, owner_id="owner-1"
):
    assert outbox_per_run in {0, 1}
    terminal_run = copy.deepcopy(template["runs"][0])
    terminal_event = copy.deepcopy(template["outbox"][0])
    runs = []
    outbox = []
    for index in range(count):
        activity_id = f"{prefix}-activity-{index:04d}"
        run = copy.deepcopy(terminal_run)
        run.update(
            {
                "activity_id": activity_id,
                "idempotency_key": f"{prefix}-start-{index:04d}",
                "request_fingerprint": hashlib.sha256(
                    f"{prefix}-request-{index}".encode()
                ).hexdigest(),
            }
        )
        runs.append(run)
        for _event_index in range(outbox_per_run):
            event = copy.deepcopy(terminal_event)
            event.update(
                {
                    "event_id": _terminal_event_id(owner_id, run),
                    "activity_id": activity_id,
                }
            )
            outbox.append(event)
    return {
        "schema_version": 1,
        "runs": runs,
        "checkpoints": [],
        "attempts": [],
        "outbox": outbox,
    }


@pytest.fixture()
def service(tmp_path):
    instance = CompositeLearningDataService.from_root(tmp_path)
    yield instance
    instance.close()


def test_bundle_v2_export_delete_import_round_trip_is_canonical(service):
    owner = "owner-1"
    _, active = _seed_space(service, owner, "space-1")
    _, terminal = _seed_space(service, owner, "space-2", suffix="2")
    service.runtime_store.cancel(terminal.key, expected_revision=0)

    before = service.export_owner_bundle(owner)
    assert before["version"] == 2
    assert before["manifest"]["learning_v1"]["counts"]["spaces"] == 2
    assert before["manifest"]["tutor_runtime"]["counts"] == {
        "runs": 2,
        "checkpoints": 1,
        "attempts": 0,
        "outbox": 1,
    }
    assert canonical_sha256(before["learning_v1"]) == before["manifest"][
        "learning_v1"
    ]["sha256"]

    service.delete_owner_data(owner)
    assert service.learning_store.list_spaces(owner) == []
    assert service.runtime_store.owner_is_empty(owner)
    result = service.import_owner_bundle(owner, before, mode="replace_empty_owner")
    assert result["tutor_runtime"]["runs"] == 2
    assert service.export_owner_bundle(owner) == before
    assert service.runtime_store.load(active.key).status == "created"


def test_space_delete_removes_both_databases_without_touching_sibling(service):
    owner = "owner-1"
    _, first = _seed_space(service, owner, "space-1")
    _, second = _seed_space(service, owner, "space-2", suffix="2")
    service.delete_space_data(owner, "space-1")
    assert service.learning_store.get_space(owner, "space-1") is None
    assert service.runtime_store.load(first.key) is None
    assert service.learning_store.get_space(owner, "space-2") is not None
    assert service.runtime_store.load(second.key) is not None


def test_terminal_projection_is_idempotent_across_crash_and_outbox_replay(service):
    owner = "owner-1"
    _, request = _seed_space(service, owner, "space-1")
    service.runtime_store.cancel(request.key, expected_revision=0)
    event = service.runtime_store.list_pending_outbox(owner)[0]
    payload = json.loads(event["payload_json"])
    # Simulate crash after learning.db commit but before outbox acknowledgement.
    assert service.learning_store.insert_projection_activity_once(
        owner,
        "space-1",
        projection_event_id=event["event_id"],
        activity_kind="tutor",
        source_activity_id=request.key.activity_id,
        outcome=payload["outcome"],
        terminal_code=payload["terminal_code"],
    ) is True
    assert service.project_pending_outbox(owner) == 1
    assert service.project_pending_outbox(owner) == 0
    projections = [
        row
        for row in service.learning_store.list_activities(owner, "space-1")
        if row["activity_type"] == "tutor.terminal"
    ]
    assert len(projections) == 1


@pytest.mark.parametrize("delete_scope", ["owner", "space"])
def test_projection_sequence_cannot_resurrect_data_after_delete(tmp_path, delete_scope):
    root = tmp_path / delete_scope
    owner = "owner-1"
    seeded = CompositeLearningDataService.from_root(root)
    try:
        _, request = _seed_space(seeded, owner, "space-1")
        seeded.runtime_store.cancel(request.key, expected_revision=0)
    finally:
        seeded.close()

    context = multiprocessing.get_context("spawn")
    listed = context.Event()
    release = context.Event()
    output = context.Queue()
    projection = context.Process(
        target=_spawn_project_with_barrier,
        args=(str(root), owner, listed, release, output),
    )
    projection.start()
    assert listed.wait(10)
    deletion = context.Process(
        target=_spawn_delete_after_projection,
        args=(
            str(root),
            owner,
            None if delete_scope == "owner" else "space-1",
            output,
        ),
    )
    deletion.start()
    time.sleep(0.2)
    assert deletion.is_alive()
    release.set()
    projection.join(15)
    deletion.join(15)
    assert projection.exitcode == deletion.exitcode == 0
    results = {output.get(timeout=2)[0] for _ in range(2)}
    assert results == {"projection", "delete"}

    verified = CompositeLearningDataService.from_root(root)
    try:
        assert verified.learning_store.list_spaces(owner) == []
        assert verified.learning_store.list_activities(owner, "space-1") == []
        assert verified.runtime_store.list(owner, "space-1", "tutor") == []
        assert verified.runtime_store.list_pending_outbox(owner) == []
    finally:
        verified.close()


def test_replace_requires_both_databases_empty_and_is_zero_write(service):
    owner = "owner-1"
    _seed_space(service, owner, "space-1")
    bundle = service.export_owner_bundle(owner)
    before = copy.deepcopy(bundle)
    with pytest.raises(LearningConflictError):
        service.import_owner_bundle(owner, bundle, mode="replace_empty_owner")
    assert service.export_owner_bundle(owner) == before
    assert service.coordinator.recover_operations() == ()


def test_runtime_merge_preserves_v04_learning_rows_and_is_idempotent(service):
    owner = "owner-1"
    _, request = _seed_space(service, owner, "space-1")
    service.runtime_store.claim_execution(
        request.key, expected_revision=0, execution_id="exec-before-downgrade"
    )
    prepared = service.prepare_downgrade(owner)
    service.commit_prepare_downgrade(owner, prepared["bundle_sha256"])
    assert service.runtime_store.owner_is_empty(owner)
    _seed_space(service, owner, "v04-new", suffix="v04", with_runtime=False)
    learning_before = service.learning_store.export_owner_bundle(owner)

    first = service.import_owner_bundle(
        owner, prepared["bundle"], mode="tutor_runtime_merge"
    )
    assert first["tutor_runtime"]["runs"] == 1
    restored = service.runtime_store.load(request.key)
    assert restored.status == "interrupted"
    assert restored.checkpoint.state["budget"]["active_elapsed_ms"] == 45_000
    assert service.learning_store.export_owner_bundle(owner) == learning_before
    repeated = service.import_owner_bundle(
        owner, prepared["bundle"], mode="tutor_runtime_merge"
    )
    assert repeated["tutor_runtime"] == {
        "runs": 0,
        "checkpoints": 0,
        "attempts": 0,
        "outbox": 0,
    }
    assert service.learning_store.export_owner_bundle(owner) == learning_before


def test_runtime_merge_conflict_rolls_back_whole_batch(service):
    owner = "owner-1"
    _, request = _seed_space(service, owner, "space-1")
    bundle = service.export_owner_bundle(owner)
    service.runtime_store.delete_owner_data(owner)
    changed = validate_start_request(
        {
            "schema_version": 1,
            "space_id": "space-1",
            "activity_kind": "tutor",
            "idempotency_key": "changed-key",
            "goal": "Conflicting payload",
            "input_refs": [],
        },
        owner_id=owner,
        activity_id=request.key.activity_id,
    )
    service.runtime_store.create(changed, _checkpoint(changed))
    before = service.runtime_store.export_owner_bundle(owner)
    with pytest.raises(TutorConflictError) as caught:
        service.import_owner_bundle(owner, bundle, mode="tutor_runtime_merge")
    assert caught.value.reason_code == "runtime_merge_identity_conflict"
    assert service.runtime_store.export_owner_bundle(owner) == before
    assert service.coordinator.recover_operations() == ()


@pytest.mark.parametrize(
    ("mutation", "reason_code"),
    [
        (
            lambda bundle: bundle["outbox"][0].update(
                {"event_id": "tproj_" + "f" * 64}
            ),
            "runtime_outbox_event_id_mismatch",
        ),
        (
            lambda bundle: bundle["outbox"][0].update(
                {"event_type": "tutor.terminal.forged"}
            ),
            "runtime_outbox_event_type_mismatch",
        ),
        (
            lambda bundle: bundle["outbox"][0]["payload"].update(
                {"terminal_code": "provider_timeout"}
            ),
            "runtime_outbox_payload_mismatch",
        ),
        (
            lambda bundle: bundle["outbox"][0]["payload"]["budget_summary"].update(
                {"nodes_used": 999}
            ),
            "runtime_outbox_payload_mismatch",
        ),
        (
            lambda bundle: bundle["outbox"][0].update(
                {"created_at": "2099-01-01T00:00:00Z"}
            ),
            "runtime_outbox_created_at_mismatch",
        ),
    ],
)
def test_runtime_merge_rejects_forged_terminal_outbox_without_new_history(
    service, mutation, reason_code
):
    owner = "owner-1"
    _, request = _seed_space(service, owner, "space-1")
    service.runtime_store.cancel(request.key, expected_revision=0)
    forged = service.runtime_store.export_owner_bundle(owner)
    before = copy.deepcopy(forged)
    mutation(forged)

    with pytest.raises(TutorConflictError) as caught:
        service.runtime_store.import_owner_bundle(
            owner, forged, mode="tutor_runtime_merge"
        )
    assert caught.value.reason_code == reason_code
    assert service.runtime_store.export_owner_bundle(owner) == before
    assert len(service.runtime_store.list_pending_outbox(owner)) == 1
    assert service.project_pending_outbox(owner) == 1
    projections = [
        row
        for row in service.learning_store.list_activities(owner, "space-1")
        if row["activity_type"] == "tutor.terminal"
    ]
    assert [row["detail"]["source_activity_id"] for row in projections] == [
        request.key.activity_id
    ]


def test_runtime_import_rejects_outbox_for_nonterminal_run(service):
    owner = "owner-1"
    _, request = _seed_space(service, owner, "space-1")
    bundle = service.runtime_store.export_owner_bundle(owner)
    run = bundle["runs"][0]
    bundle["outbox"] = [
        {
            "event_id": _terminal_event_id(owner, run),
            "space_id": run["space_id"],
            "activity_kind": run["activity_kind"],
            "activity_id": run["activity_id"],
            "event_type": "tutor.terminal",
            "payload": {
                "schema_version": 1,
                "outcome": "cancelled",
                "terminal_code": "user_cancelled",
                "completion_basis": None,
                "remediation_count": 0,
                "budget_summary": {
                    "nodes_used": 0,
                    "attempts_used": 0,
                    "reserved_input_tokens": 0,
                    "reserved_output_tokens": 0,
                    "reserved_wall_ms": 0,
                    "active_elapsed_ms": 0,
                },
            },
            "created_at": run["updated_at"],
            "delivered_at": None,
        }
    ]
    service.runtime_store.delete_owner_data(owner)

    with pytest.raises(TutorConflictError) as caught:
        service.runtime_store.import_owner_bundle(
            owner, bundle, mode="tutor_runtime_merge"
        )
    assert caught.value.reason_code == "runtime_outbox_requires_terminal_run"
    assert service.runtime_store.owner_is_empty(owner)


def test_runtime_merge_terminal_outbox_retry_uses_one_projection_identity(service):
    owner = "owner-1"
    _, request = _seed_space(service, owner, "space-1")
    service.runtime_store.cancel(request.key, expected_revision=0)
    backup = service.runtime_store.export_owner_bundle(owner)
    service.runtime_store.delete_owner_data(owner)

    first = service.runtime_store.import_owner_bundle(
        owner, backup, mode="tutor_runtime_merge"
    )
    assert first == {"runs": 1, "checkpoints": 0, "attempts": 0, "outbox": 1}
    repeated_pending = service.runtime_store.import_owner_bundle(
        owner, backup, mode="tutor_runtime_merge"
    )
    assert repeated_pending == {
        "runs": 0,
        "checkpoints": 0,
        "attempts": 0,
        "outbox": 0,
    }
    assert service.project_pending_outbox(owner) == 1

    repeated_delivered = service.runtime_store.import_owner_bundle(
        owner, backup, mode="tutor_runtime_merge"
    )
    assert repeated_delivered == {
        "runs": 0,
        "checkpoints": 0,
        "attempts": 0,
        "outbox": 1,
    }
    assert service.project_pending_outbox(owner) == 1
    projections = [
        row
        for row in service.learning_store.list_activities(owner, "space-1")
        if row["activity_type"] == "tutor.terminal"
    ]
    assert [row["detail"]["source_activity_id"] for row in projections] == [
        request.key.activity_id
    ]


def test_runtime_merge_rejects_combined_owner_and_space_nonterminal_quota(service):
    owner = "owner-1"
    _seed_space(service, owner, "template-space")
    template = service.runtime_store.export_owner_bundle(owner)
    service.runtime_store.delete_owner_data(owner)
    existing = _active_runtime_bundle(
        template,
        count=12,
        prefix="existing",
        space_for_index=lambda index: "space-a" if index < 6 else "space-b",
    )
    service.runtime_store.import_owner_bundle(
        owner, existing, mode="replace_empty_owner"
    )
    before = service.runtime_store.export_owner_bundle(owner)

    owner_overflow = _active_runtime_bundle(
        template,
        count=1,
        prefix="owner-overflow",
        space_for_index=lambda _index: "space-c",
    )
    with pytest.raises(TutorConflictError) as caught:
        service.runtime_store.import_owner_bundle(
            owner, owner_overflow, mode="tutor_runtime_merge"
        )
    assert caught.value.reason_code == "activity_quota_exceeded"
    assert service.runtime_store.export_owner_bundle(owner) == before

    service.runtime_store.delete_owner_data(owner)
    existing_batch = _active_runtime_bundle(
        template,
        count=11,
        prefix="existing-batch",
        space_for_index=lambda index: f"batch-space-{index // 6}",
    )
    service.runtime_store.import_owner_bundle(
        owner, existing_batch, mode="replace_empty_owner"
    )
    before = service.runtime_store.export_owner_bundle(owner)
    batch_overflow = _active_runtime_bundle(
        template,
        count=2,
        prefix="batch-overflow",
        space_for_index=lambda _index: "batch-space-2",
    )
    with pytest.raises(TutorConflictError):
        service.runtime_store.import_owner_bundle(
            owner, batch_overflow, mode="tutor_runtime_merge"
        )
    assert service.runtime_store.export_owner_bundle(owner) == before

    service.runtime_store.delete_owner_data(owner)
    existing_space = _active_runtime_bundle(
        template,
        count=6,
        prefix="existing-space",
        space_for_index=lambda _index: "space-a",
    )
    service.runtime_store.import_owner_bundle(
        owner, existing_space, mode="replace_empty_owner"
    )
    before = service.runtime_store.export_owner_bundle(owner)
    space_overflow = _active_runtime_bundle(
        template,
        count=1,
        prefix="space-overflow",
        space_for_index=lambda _index: "space-a",
    )
    with pytest.raises(TutorConflictError) as caught:
        service.runtime_store.import_owner_bundle(
            owner, space_overflow, mode="tutor_runtime_merge"
        )
    assert caught.value.reason_code == "activity_quota_exceeded"
    assert service.runtime_store.export_owner_bundle(owner) == before


def test_runtime_merge_rejects_combined_checkpoint_bytes_and_rolls_back(
    service, monkeypatch
):
    owner = "owner-1"
    _seed_space(service, owner, "template-space")
    template = service.runtime_store.export_owner_bundle(owner)
    service.runtime_store.delete_owner_data(owner)
    existing = _active_runtime_bundle(
        template,
        count=11,
        prefix="existing-large",
        space_for_index=lambda index: f"space-{index // 6}",
        padding=261_700,
    )
    service.runtime_store.import_owner_bundle(
        owner, existing, mode="replace_empty_owner"
    )
    before = service.runtime_store.export_owner_bundle(owner)
    incoming = _active_runtime_bundle(
        template,
        count=1,
        prefix="incoming-large",
        space_for_index=lambda _index: "space-2",
        padding=261_700,
    )
    existing_bytes = sum(
        len(canonical_json_bytes(row["state"])) for row in before["checkpoints"]
    )
    incoming_bytes = sum(
        len(canonical_json_bytes(row["state"])) for row in incoming["checkpoints"]
    )
    monkeypatch.setattr(
        runtime_store_module,
        "MAX_OWNER_CHECKPOINT_BYTES",
        existing_bytes + incoming_bytes - 1,
    )
    with pytest.raises(TutorConflictError) as caught:
        service.runtime_store.import_owner_bundle(
            owner, incoming, mode="tutor_runtime_merge"
        )
    assert caught.value.reason_code == "checkpoint_owner_quota"
    assert service.runtime_store.export_owner_bundle(owner) == before


def test_runtime_merge_exact_duplicate_at_quota_is_zero_write(service):
    owner = "owner-1"
    _seed_space(service, owner, "template-space")
    template = service.runtime_store.export_owner_bundle(owner)
    service.runtime_store.delete_owner_data(owner)
    at_cap = _active_runtime_bundle(
        template,
        count=12,
        prefix="at-cap",
        space_for_index=lambda index: "space-a" if index < 6 else "space-b",
    )
    service.runtime_store.import_owner_bundle(
        owner, at_cap, mode="replace_empty_owner"
    )
    before = service.runtime_store.export_owner_bundle(owner)
    assert service.runtime_store.import_owner_bundle(
        owner, at_cap, mode="tutor_runtime_merge"
    ) == {"runs": 0, "checkpoints": 0, "attempts": 0, "outbox": 0}
    assert service.runtime_store.export_owner_bundle(owner) == before


def test_runtime_merge_rejects_combined_terminal_and_outbox_quotas(service):
    owner = "owner-1"
    _, request = _seed_space(service, owner, "template-space")
    service.runtime_store.cancel(request.key, expected_revision=0)
    template = service.runtime_store.export_owner_bundle(owner)
    service.runtime_store.delete_owner_data(owner)

    terminal_cap = _terminal_runtime_bundle(
        template,
        count=1_000,
        prefix="terminal-cap",
    )
    service.runtime_store.import_owner_bundle(
        owner, terminal_cap, mode="replace_empty_owner"
    )
    before = service.runtime_store.export_owner_bundle(owner)
    terminal_overflow = _terminal_runtime_bundle(
        template,
        count=1,
        prefix="terminal-overflow",
    )
    with pytest.raises(TutorConflictError) as caught:
        service.runtime_store.import_owner_bundle(
            owner, terminal_overflow, mode="tutor_runtime_merge"
        )
    assert caught.value.reason_code == "terminal_run_quota"
    assert service.runtime_store.export_owner_bundle(owner) == before

    service.runtime_store.delete_owner_data(owner)
    outbox_cap = _terminal_runtime_bundle(
        template, count=44, prefix="outbox-cap", outbox_per_run=1
    )
    service.runtime_store.import_owner_bundle(
        owner, outbox_cap, mode="replace_empty_owner"
    )
    before = service.runtime_store.export_owner_bundle(owner)
    outbox_overflow = _terminal_runtime_bundle(
        template, count=1, prefix="outbox-overflow", outbox_per_run=1
    )
    with pytest.raises(TutorConflictError) as caught:
        service.runtime_store.import_owner_bundle(
            owner, outbox_overflow, mode="tutor_runtime_merge"
        )
    assert caught.value.reason_code == "tutor_runtime_outbox_quota"
    assert service.runtime_store.export_owner_bundle(owner) == before


def test_runtime_merge_rejects_combined_attempt_quota_without_partial_write(service):
    owner = "owner-1"
    _seed_space(service, owner, "template-space")
    template = service.runtime_store.export_owner_bundle(owner)
    service.runtime_store.delete_owner_data(owner)
    existing = _active_runtime_bundle(
        template,
        count=12,
        prefix="attempt-cap",
        space_for_index=lambda index: "space-a" if index < 6 else "space-b",
        attempts_per_run=2,
    )
    service.runtime_store.import_owner_bundle(
        owner, existing, mode="replace_empty_owner"
    )
    # A valid runtime cannot exceed the attempt cap independently because it
    # is 12 activities * 2 attempts. Preserve a pre-fix/externally-corrupt
    # terminal row with attempts to prove merge checks persisted + incoming
    # truth rather than trusting the incoming bundle alone.
    with service.runtime_store._lock:
        service.runtime_store._conn.execute("BEGIN IMMEDIATE")
        service.runtime_store._conn.execute(
            "UPDATE tutor_activity_runs SET status='cancelled' "
            "WHERE owner_id=? AND activity_id=?",
            (owner, "attempt-cap-activity-0000"),
        )
        service.runtime_store._conn.commit()
    before = service.runtime_store.export_owner_bundle(owner)
    incoming = _active_runtime_bundle(
        template,
        count=1,
        prefix="attempt-overflow",
        space_for_index=lambda _index: "space-c",
        attempts_per_run=1,
    )
    with pytest.raises(TutorConflictError) as caught:
        service.runtime_store.import_owner_bundle(
            owner, incoming, mode="tutor_runtime_merge"
        )
    assert caught.value.reason_code == "tutor_runtime_attempts_quota"
    assert service.runtime_store.export_owner_bundle(owner) == before


def test_runtime_merge_keeps_missing_source_as_blocked_recovery_row(service):
    owner = "owner-1"
    _, request = _seed_space(service, owner, "old-space")
    prepared = service.prepare_downgrade(owner)
    service.commit_prepare_downgrade(owner, prepared["bundle_sha256"])
    service.learning_store.delete_owner_data(owner)
    _seed_space(service, owner, "v04-new", suffix="v04", with_runtime=False)

    service.import_owner_bundle(owner, prepared["bundle"], mode="tutor_runtime_merge")
    restored = service.runtime_store.load(request.key)
    assert restored.status == "blocked"
    assert restored.checkpoint is None
    assert service.runtime_store.raw_run(request.key)["terminal_code"] == "source_missing"
    assert service.learning_store.get_space(owner, "v04-new") is not None


def test_manifest_or_outer_size_error_is_rejected_before_target_write(tmp_path):
    source = CompositeLearningDataService.from_root(tmp_path / "source")
    target = CompositeLearningDataService.from_root(tmp_path / "target")
    try:
        _seed_space(source, "owner-1", "space-1")
        bundle = source.export_owner_bundle("owner-1")
        tampered = copy.deepcopy(bundle)
        tampered["manifest"]["tutor_runtime"]["counts"]["runs"] = 99
        with pytest.raises(TutorConflictError) as caught:
            target.import_owner_bundle(
                "owner-1", tampered, mode="replace_empty_owner"
            )
        assert caught.value.reason_code == "bundle_manifest_mismatch"
        assert target.learning_store.list_spaces("owner-1") == []

        oversized = copy.deepcopy(bundle)
        oversized["padding"] = "x" * (OWNER_BUNDLE_MAX_BYTES + 1)
        with pytest.raises(TutorContractError, match="24 MiB"):
            target.import_owner_bundle(
                "owner-1", oversized, mode="replace_empty_owner"
            )
        assert target.runtime_store.owner_is_empty("owner-1")
    finally:
        source.close()
        target.close()


def test_v1_learning_bundle_import_remains_compatible(tmp_path):
    source = CompositeLearningDataService.from_root(tmp_path / "source")
    target = CompositeLearningDataService.from_root(tmp_path / "target")
    try:
        _seed_space(source, "owner-1", "space-1", with_runtime=False)
        v1 = source.learning_store.export_owner_bundle("owner-1")
        target.import_owner_bundle("owner-1", v1, mode="replace_empty_owner")
        assert target.learning_store.export_owner_bundle("owner-1") == v1
        assert target.runtime_store.owner_is_empty("owner-1")
    finally:
        source.close()
        target.close()


def test_prepare_hash_drift_never_deletes_runtime(service):
    owner = "owner-1"
    _, request = _seed_space(service, owner, "space-1")
    prepared = service.prepare_downgrade(owner)
    service.learning_store.insert_activity(
        owner, "space-1", activity_type="v04.drift", detail={}
    )
    with pytest.raises(TutorConflictError) as caught:
        service.commit_prepare_downgrade(owner, prepared["bundle_sha256"])
    assert caught.value.reason_code == "bundle_hash_drift"
    assert service.runtime_store.load(request.key) is not None
    assert service.coordinator.recover_operations() == ()


def test_crashed_delete_keeps_fence_and_recovery_finishes(service, monkeypatch):
    owner = "owner-1"
    _seed_space(service, owner, "space-1")
    original = service.runtime_store.delete_owner_data

    def fail_once(*args, **kwargs):
        raise RuntimeError("simulated runtime delete crash")

    monkeypatch.setattr(service.runtime_store, "delete_owner_data", fail_once)
    with pytest.raises(RuntimeError, match="simulated"):
        service.delete_owner_data(owner)
    assert service.learning_store.list_spaces(
        owner,
        operation_lease=service.coordinator.recover_operations()[0],
    ) == []
    monkeypatch.setattr(service.runtime_store, "delete_owner_data", original)
    assert service.recover_operations() == 1
    assert service.runtime_store.owner_is_empty(owner)
    assert service.coordinator.recover_operations() == ()


@pytest.mark.parametrize(
    "crash_phase",
    ["fenced", "learning_deleted", "runtime_deleted", "compacted"],
)
def test_delete_restart_recovery_phase_matrix(tmp_path, crash_phase):
    root = tmp_path / crash_phase
    owner = "owner-1"
    original = CompositeLearningDataService.from_root(root)
    _seed_space(original, owner, "space-1")
    lease = original.coordinator.begin_operation(owner, "", "delete")
    current = lease
    if crash_phase != "fenced":
        original.learning_store.delete_owner_data(owner, operation_lease=current)
        current = original.coordinator.advance_operation(
            current, "learning_deleted", {"injected_crash_phase": crash_phase}
        )
    if crash_phase in {"runtime_deleted", "compacted"}:
        original.runtime_store.delete_owner_data(owner, operation_lease=current)
        current = original.coordinator.advance_operation(
            current, "runtime_deleted", {"injected_crash_phase": crash_phase}
        )
    if crash_phase == "compacted":
        original.runtime_store.compact(owner, operation_lease=current)
        original.coordinator.advance_operation(
            current, "compacted", {"injected_crash_phase": crash_phase}
        )
    original.close()

    restarted = CompositeLearningDataService.from_root(root)
    try:
        assert restarted.recover_operations() == 1
        assert restarted.learning_store.export_owner_bundle(owner) == {
            "version": 1,
            "spaces": [],
            "artifacts": [],
            "items": [],
            "activities": [],
            "migrations": [],
        }
        assert restarted.runtime_store.owner_is_empty(owner)
        assert restarted.coordinator.recover_operations() == ()
    finally:
        restarted.close()


@pytest.mark.parametrize(
    "crash_phase",
    ["fenced", "validated_empty", "learning_imported", "runtime_imported"],
)
def test_full_import_restart_rollback_phase_matrix(tmp_path, crash_phase):
    owner = "owner-1"
    source = CompositeLearningDataService.from_root(tmp_path / "source")
    target_root = tmp_path / f"target-{crash_phase}"
    target = CompositeLearningDataService.from_root(target_root)
    try:
        _seed_space(source, owner, "space-1")
        bundle = source.export_owner_bundle(owner)
        lease = target.coordinator.begin_operation(
            owner, "", "full_import", target.bundle_sha256(bundle)
        )
        current = lease
        if crash_phase != "fenced":
            current = target.coordinator.advance_operation(
                current, "validated_empty", {"target_was_empty": True}
            )
        if crash_phase in {"learning_imported", "runtime_imported"}:
            target.learning_store.import_owner_bundle(
                owner, bundle["learning_v1"], operation_lease=current
            )
            current = target.coordinator.advance_operation(
                current, "learning_imported", {"target_was_empty": True}
            )
        if crash_phase == "runtime_imported":
            target.runtime_store.import_owner_bundle(
                owner,
                bundle["tutor_runtime"],
                mode="replace_empty_owner",
                operation_lease=current,
            )
            target.coordinator.advance_operation(
                current, "runtime_imported", {"target_was_empty": True}
            )
    finally:
        source.close()
        target.close()

    restarted = CompositeLearningDataService.from_root(target_root)
    try:
        assert restarted.recover_operations() == 1
        assert restarted.learning_store.export_owner_bundle(owner) == {
            "version": 1,
            "spaces": [],
            "artifacts": [],
            "items": [],
            "activities": [],
            "migrations": [],
        }
        assert restarted.runtime_store.owner_is_empty(owner)
        assert restarted.coordinator.recover_operations() == ()
    finally:
        restarted.close()


def test_near_cap_12_checkpoints_and_1000_terminal_summaries_round_trip(service):
    owner = "owner-1"
    _seed_space(service, owner, "space-1")
    _, terminal_request = _seed_space(service, owner, "space-2", suffix="2")
    service.runtime_store.cancel(terminal_request.key, expected_revision=0)
    source = service.export_owner_bundle(owner)
    runtime_source = source["tutor_runtime"]
    active_run = next(row for row in runtime_source["runs"] if row["status"] == "created")
    active_checkpoint = runtime_source["checkpoints"][0]
    terminal_run = next(
        row for row in runtime_source["runs"] if row["status"] == "cancelled"
    )

    runs = []
    checkpoints = []
    for index in range(12):
        space_id = "space-1" if index < 6 else "space-2"
        activity_id = f"bulk-active-{index:02d}"
        run = copy.deepcopy(active_run)
        run.update(
            {
                "space_id": space_id,
                "activity_id": activity_id,
                "idempotency_key": f"bulk-start-{index:02d}",
                "request_fingerprint": hashlib.sha256(
                    f"active-{index}".encode()
                ).hexdigest(),
            }
        )
        checkpoint = copy.deepcopy(active_checkpoint)
        checkpoint.update(
            {
                "space_id": space_id,
                "activity_id": activity_id,
            }
        )
        checkpoint["state"]["input_refs"] = []
        checkpoint["state"]["padding"] = "x" * 250_000
        checkpoint["state_sha256"] = hashlib.sha256(
            canonical_json_bytes(checkpoint["state"])
        ).hexdigest()
        runs.append(run)
        checkpoints.append(checkpoint)
    for index in range(1_000):
        run = copy.deepcopy(terminal_run)
        run.update(
            {
                "space_id": "space-1" if index % 2 == 0 else "space-2",
                "activity_id": f"bulk-terminal-{index:04d}",
                "idempotency_key": f"bulk-terminal-start-{index:04d}",
                "request_fingerprint": hashlib.sha256(
                    f"terminal-{index}".encode()
                ).hexdigest(),
            }
        )
        runs.append(run)
    runtime = {
        "schema_version": 1,
        "runs": runs,
        "checkpoints": checkpoints,
        "attempts": [],
        "outbox": [],
    }
    near_cap = service._assemble_bundle(source["learning_v1"], runtime)
    assert len(canonical_json_bytes(runtime)) < 6 * 1024 * 1024
    assert len(canonical_json_bytes(near_cap)) < OWNER_BUNDLE_MAX_BYTES

    service.delete_owner_data(owner)
    service.import_owner_bundle(owner, near_cap, mode="replace_empty_owner")
    exported = service.export_owner_bundle(owner)
    assert exported["manifest"]["tutor_runtime"]["counts"] == {
        "runs": 1_012,
        "checkpoints": 12,
        "attempts": 0,
        "outbox": 0,
    }
    service.delete_owner_data(owner)
    service.import_owner_bundle(owner, exported, mode="replace_empty_owner")
    assert service.export_owner_bundle(owner) == exported
