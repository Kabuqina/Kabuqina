"""Composite two-business-DB operations and StudyOwnerBundleV2 tests."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

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
