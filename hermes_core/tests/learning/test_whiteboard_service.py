# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""S-2 whiteboard transactional runtime tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import copy

import pytest

import learning.whiteboard as whiteboard_module
from learning.learning_store import LearningStore
from learning.learning_contract import ContractError
from learning.whiteboard import (
    WhiteboardConflictError,
    WhiteboardQuotaError,
    WhiteboardService,
)
from learning.whiteboard_contract import (
    MAX_WHITEBOARD_OWNER_BYTES,
    MAX_WORKING_IDEMPOTENCY_RECORDS,
    WhiteboardContractError,
    canonical_json_bytes,
    canonical_sha256,
    whiteboard_working_item_id,
)


OWNER = "desktop:owner-test"
SPACE = "space-1"
ACTIVITY = "activity-1"
LINEAGE = "lineage-1"


def _scene(label: str = "one") -> dict:
    return {
        "schema_version": 1,
        "elements": [
            {
                "element_id": "e1",
                "type": "text",
                "x": 0,
                "y": 0,
                "tone": "ink",
                "stroke_width": 1,
                "width": 200,
                "height": 40,
                "content": f"bounded whiteboard content {label}",
            }
        ],
    }


@pytest.fixture
def runtime(tmp_path):
    db_path = tmp_path / "learning.db"
    store = LearningStore(db_path)
    store.create_space(OWNER, title="Course", space_id=SPACE)
    service = WhiteboardService(store, OWNER, SPACE)
    try:
        yield db_path, store, service
    finally:
        store.close()


def test_working_save_is_cas_idempotent_and_restart_recoverable(runtime):
    db_path, store, service = runtime

    first = service.save_working(
        activity_id=ACTIVITY,
        lineage_id=LINEAGE,
        expected_revision=0,
        idempotency_key="save-1",
        scene=_scene(),
    )
    replay = service.save_working(
        activity_id=ACTIVITY,
        lineage_id=LINEAGE,
        expected_revision=0,
        idempotency_key="save-1",
        scene=_scene(),
    )

    assert first["revision"] == 1
    assert first["replayed"] is False
    assert replay == {**first, "replayed": True}
    with pytest.raises(WhiteboardConflictError, match="idempotency"):
        service.save_working(
            activity_id=ACTIVITY,
            lineage_id=LINEAGE,
            expected_revision=0,
            idempotency_key="save-1",
            scene=_scene("drift"),
        )
    with pytest.raises(WhiteboardConflictError, match="revision"):
        service.save_working(
            activity_id=ACTIVITY,
            lineage_id=LINEAGE,
            expected_revision=0,
            idempotency_key="save-stale",
            scene=_scene("stale"),
        )

    store.close()
    reopened = LearningStore(db_path)
    try:
        recovered = WhiteboardService(reopened, OWNER, SPACE).load_working(ACTIVITY)
        assert recovered is not None
        assert recovered["state"]["revision"] == 1
        assert recovered["state"]["scene"] == _scene()
    finally:
        reopened.close()


def test_generic_artifact_writer_cannot_bypass_whiteboard_service(runtime):
    _, store, service = runtime
    scene = {"schema_version": 1, "elements": []}
    with pytest.raises(ContractError, match="WhiteboardService"):
        store.insert_artifact(
            OWNER,
            SPACE,
            {
                "version": 1,
                "kind": "whiteboard_snapshot",
                "space_id": SPACE,
                "title": "Bypass",
                "source_refs": [],
                "payload": {
                    "schema_version": 1,
                    "activity_id": ACTIVITY,
                    "lineage_id": LINEAGE,
                    "revision": 1,
                    "parent_artifact_id": None,
                    "scene": scene,
                    "scene_sha256": "7035e16cfe81bfbf5f16fe9b83d67bc69ccf76e2946e546fe2c456a5866c2837",
                },
                "review": {"mode": "deterministic", "status": "passed"},
            },
        )
    with pytest.raises(ContractError, match="WhiteboardService"):
        store.upsert_item(
            OWNER,
            SPACE,
            item_id="raw-whiteboard",
            item_type="whiteboard_working",
            state={},
        )
    with pytest.raises(ContractError, match="WhiteboardService"):
        store.insert_activity(
            OWNER,
            SPACE,
            activity_type="whiteboard.attach",
            detail={},
        )
    saved = service.save_working(
        activity_id=ACTIVITY,
        lineage_id=LINEAGE,
        expected_revision=0,
        idempotency_key="trusted-save",
        scene=_scene(),
    )
    with pytest.raises(ContractError, match="WhiteboardService"):
        store.update_item_state(OWNER, SPACE, saved["item_id"], {})
    snapshot = service.create_snapshot(
        activity_id=ACTIVITY,
        expected_working_revision=1,
        idempotency_key="trusted-snapshot",
    )
    with pytest.raises(ContractError, match="WhiteboardService"):
        store.update_artifact_status(
            OWNER, SPACE, snapshot["artifact_id"], "active"
        )


def test_two_store_writers_have_one_cas_winner(runtime):
    db_path, _, service = runtime
    service.save_working(
        activity_id=ACTIVITY,
        lineage_id=LINEAGE,
        expected_revision=0,
        idempotency_key="seed",
        scene=_scene("seed"),
    )

    def write(index: int):
        contender = LearningStore(db_path)
        try:
            return WhiteboardService(contender, OWNER, SPACE).save_working(
                activity_id=ACTIVITY,
                lineage_id=LINEAGE,
                expected_revision=1,
                idempotency_key=f"concurrent-{index}",
                scene=_scene(f"writer-{index}"),
            )
        finally:
            contender.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(write, index) for index in range(2)]
        results, failures = [], []
        for future in futures:
            try:
                results.append(future.result())
            except Exception as exc:  # the exact loser is scheduler-dependent
                failures.append(exc)

    assert len(results) == 1
    assert results[0]["revision"] == 2
    assert len(failures) == 1
    assert isinstance(failures[0], WhiteboardConflictError)


def test_working_idempotency_ledger_is_bounded_and_eviction_fails_safe(runtime):
    _, _, service = runtime
    revision = 0
    for index in range(MAX_WORKING_IDEMPOTENCY_RECORDS + 1):
        result = service.save_working(
            activity_id=ACTIVITY,
            lineage_id=LINEAGE,
            expected_revision=revision,
            idempotency_key=f"save-{index}",
            scene=_scene(str(index)),
        )
        revision = result["revision"]

    public_working = service.load_working(ACTIVITY)
    assert public_working is not None
    assert "request_ledger" not in public_working["state"]
    exported = service.store.export_owner_bundle(OWNER)
    working_state = next(
        row["state"]
        for row in exported["items"]
        if row["item_type"] == "whiteboard_working"
    )
    assert len(working_state["request_ledger"]) == MAX_WORKING_IDEMPOTENCY_RECORDS
    assert working_state["request_ledger"][0]["idempotency_key"] == "save-1"
    with pytest.raises(WhiteboardConflictError, match="revision"):
        service.save_working(
            activity_id=ACTIVITY,
            lineage_id=LINEAGE,
            expected_revision=0,
            idempotency_key="save-0",
            scene=_scene("0"),
        )


def test_snapshot_lineage_restore_attach_export_and_delete(runtime):
    _, _, service = runtime
    service.save_working(
        activity_id=ACTIVITY,
        lineage_id=LINEAGE,
        expected_revision=0,
        idempotency_key="save-1",
        scene=_scene("first"),
    )
    first = service.create_snapshot(
        activity_id=ACTIVITY,
        expected_working_revision=1,
        idempotency_key="snapshot-1",
    )
    assert service.create_snapshot(
        activity_id=ACTIVITY,
        expected_working_revision=1,
        idempotency_key="snapshot-1",
    )["replayed"] is True
    service.save_working(
        activity_id=ACTIVITY,
        lineage_id=LINEAGE,
        expected_revision=1,
        idempotency_key="save-2",
        scene=_scene("second"),
    )
    second = service.create_snapshot(
        activity_id=ACTIVITY,
        expected_working_revision=2,
        idempotency_key="snapshot-2",
    )

    assert first["revision"] == 1
    assert second["revision"] == 2
    assert second["parent_artifact_id"] == first["artifact_id"]
    exported = service.export_snapshot(first["artifact_id"])
    assert exported["envelope"]["payload"]["scene"] == _scene("first")
    assert len(exported["canonical_sha256"]) == 64

    restored = service.restore_snapshot(
        first["artifact_id"],
        expected_working_revision=2,
        idempotency_key="restore-1",
    )
    assert restored["revision"] == 3
    assert service.load_working(ACTIVITY)["state"]["scene"] == _scene("first")
    assert service.restore_snapshot(
        first["artifact_id"],
        expected_working_revision=2,
        idempotency_key="restore-1",
    )["replayed"] is True

    assert service.attach_snapshot(
        first["artifact_id"], idempotency_key="attach-1"
    ) == {"artifact_id": first["artifact_id"], "status": "active", "replayed": False}
    assert service.attach_snapshot(
        first["artifact_id"], idempotency_key="attach-1"
    )["replayed"] is True

    preview = service.preview_snapshot_delete(first["artifact_id"])
    assert preview["target_artifact_ids"] == [
        second["artifact_id"],
        first["artifact_id"],
    ]
    assert preview["active_attachment_ids"] == [first["artifact_id"]]
    with pytest.raises(WhiteboardContractError, match="target_artifact_ids"):
        service.delete_snapshots(
            first["artifact_id"],
            target_artifact_ids=[],
            idempotency_key="delete-empty",
        )
    with pytest.raises(WhiteboardConflictError, match="preview"):
        service.delete_snapshots(
            first["artifact_id"],
            target_artifact_ids=[first["artifact_id"]],
            idempotency_key="delete-wrong",
        )
    deleted = service.delete_snapshots(
        first["artifact_id"],
        target_artifact_ids=preview["target_artifact_ids"],
        idempotency_key="delete-lineage",
    )
    assert deleted["deleted_artifact_ids"] == preview["target_artifact_ids"]
    assert service.delete_snapshots(
        first["artifact_id"],
        target_artifact_ids=preview["target_artifact_ids"],
        idempotency_key="delete-lineage",
    )["replayed"] is True
    assert service.list_snapshots(ACTIVITY) == []
    with pytest.raises(WhiteboardConflictError, match="cannot be recreated"):
        service.create_snapshot(
            activity_id=ACTIVITY,
            expected_working_revision=3,
            idempotency_key="snapshot-1",
        )


def test_snapshot_count_and_byte_quota_fail_with_zero_write(runtime, monkeypatch):
    _, _, service = runtime
    service.save_working(
        activity_id=ACTIVITY,
        lineage_id=LINEAGE,
        expected_revision=0,
        idempotency_key="save",
        scene=_scene(),
    )
    for index in range(8):
        service.create_snapshot(
            activity_id=ACTIVITY,
            expected_working_revision=1,
            idempotency_key=f"snapshot-{index}",
        )
    with pytest.raises(WhiteboardQuotaError, match="count"):
        service.create_snapshot(
            activity_id=ACTIVITY,
            expected_working_revision=1,
            idempotency_key="snapshot-over",
        )
    assert len(service.list_snapshots(ACTIVITY)) == 8

    monkeypatch.setattr(whiteboard_module, "MAX_WHITEBOARD_OWNER_BYTES", 1)
    with pytest.raises(WhiteboardQuotaError, match="owner"):
        service.save_working(
            activity_id="activity-2",
            lineage_id="lineage-2",
            expected_revision=0,
            idempotency_key="quota-fail",
            scene=_scene("quota"),
        )
    assert service.load_working("activity-2") is None


def test_working_delete_is_revision_bound_idempotent_and_compacted(runtime):
    _, _, service = runtime
    service.save_working(
        activity_id=ACTIVITY,
        lineage_id=LINEAGE,
        expected_revision=0,
        idempotency_key="save",
        scene=_scene(),
    )
    with pytest.raises(WhiteboardConflictError, match="revision"):
        service.delete_working(
            ACTIVITY, expected_revision=2, idempotency_key="delete-stale"
        )
    deleted = service.delete_working(
        ACTIVITY, expected_revision=1, idempotency_key="delete-working"
    )
    assert deleted["deleted"] is True
    assert service.load_working(ACTIVITY) is None
    assert service.delete_working(
        ACTIVITY, expected_revision=1, idempotency_key="delete-working"
    )["replayed"] is True
    with pytest.raises(WhiteboardConflictError, match="cannot be recreated"):
        service.save_working(
            activity_id=ACTIVITY,
            lineage_id=LINEAGE,
            expected_revision=0,
            idempotency_key="recreate",
            scene=_scene("recreate"),
        )


def test_owner_bundle_round_trip_preserves_whiteboard_replay_and_lineage(runtime):
    _, store, service = runtime
    saved = service.save_working(
        activity_id=ACTIVITY,
        lineage_id=LINEAGE,
        expected_revision=0,
        idempotency_key="save-roundtrip",
        scene=_scene("roundtrip"),
    )
    snapshot = service.create_snapshot(
        activity_id=ACTIVITY,
        expected_working_revision=1,
        idempotency_key="snapshot-roundtrip",
    )
    service.save_working(
        activity_id=ACTIVITY,
        lineage_id=LINEAGE,
        expected_revision=1,
        idempotency_key="save-roundtrip-2",
        scene=_scene("changed-before-restore"),
    )
    service.restore_snapshot(
        snapshot["artifact_id"],
        expected_working_revision=2,
        idempotency_key="restore-roundtrip",
    )
    service.attach_snapshot(
        snapshot["artifact_id"], idempotency_key="attach-roundtrip"
    )
    bundle = store.export_owner_bundle(OWNER)

    restored_owner = "desktop:restored-owner"
    counts = store.import_owner_bundle(restored_owner, bundle)
    restored = WhiteboardService(store, restored_owner, SPACE)

    assert counts["items"] == 1
    assert counts["artifacts"] == 1
    assert restored.load_working(ACTIVITY)["state"]["scene"] == _scene("roundtrip")
    assert restored.save_working(
        activity_id=ACTIVITY,
        lineage_id=LINEAGE,
        expected_revision=0,
        idempotency_key="save-roundtrip",
        scene=_scene("roundtrip"),
    ) == {**saved, "replayed": True}
    assert restored.create_snapshot(
        activity_id=ACTIVITY,
        expected_working_revision=1,
        idempotency_key="snapshot-roundtrip",
    )["artifact_id"] == snapshot["artifact_id"]
    assert restored.restore_snapshot(
        snapshot["artifact_id"],
        expected_working_revision=2,
        idempotency_key="restore-roundtrip",
    )["replayed"] is True
    assert restored.get_snapshot(snapshot["artifact_id"])["status"] == "active"


def test_owner_bundle_rejects_forged_snapshot_parent_with_zero_write(runtime):
    _, store, service = runtime
    service.save_working(
        activity_id=ACTIVITY,
        lineage_id=LINEAGE,
        expected_revision=0,
        idempotency_key="save",
        scene=_scene(),
    )
    service.create_snapshot(
        activity_id=ACTIVITY,
        expected_working_revision=1,
        idempotency_key="snapshot-1",
    )
    service.create_snapshot(
        activity_id=ACTIVITY,
        expected_working_revision=1,
        idempotency_key="snapshot-2",
    )
    bundle = copy.deepcopy(store.export_owner_bundle(OWNER))
    second = max(
        bundle["artifacts"], key=lambda row: row["envelope"]["payload"]["revision"]
    )
    second["envelope"]["payload"]["parent_artifact_id"] = "missing-parent"

    forged_owner = "desktop:forged-owner"
    with pytest.raises(WhiteboardContractError):
        store.import_owner_bundle(forged_owner, bundle)
    assert store.list_spaces(forged_owner) == []


def _large_scene() -> dict:
    return {
        "schema_version": 1,
        "elements": [
            {
                "element_id": f"text-{index}",
                "type": "text",
                "x": index,
                "y": index,
                "tone": "ink",
                "stroke_width": 1,
                "width": 200,
                "height": 40,
                "content": "学" * 2_000,
            }
            for index in range(16)
        ],
    }


def _near_cap_whiteboard_bundle(owner_id: str) -> tuple[dict, dict]:
    scene = _large_scene()
    scene_sha256 = canonical_sha256(scene)
    bundle = {
        "version": 1,
        "spaces": [
            {
                "space_id": f"near-space-{space_index}",
                "title": f"Near cap {space_index}",
                "status": "active",
                "is_current": int(space_index == 0),
                "created_at": "2026-07-26T00:00:00Z",
                "updated_at": "2026-07-26T00:00:00Z",
            }
            for space_index in range(3)
        ],
        "artifacts": [],
        "items": [],
        "activities": [],
        "migrations": [],
    }
    next_unit = None
    total = 0
    index = 0
    while True:
        space_id = f"near-space-{index % 3}"
        activity_id = f"near-activity-{index}"
        lineage_id = f"near-lineage-{index}"
        artifacts = []
        parent = None
        for revision in range(1, 9):
            artifact_id = f"near-a{index}-s{revision}"
            payload = {
                "schema_version": 1,
                "activity_id": activity_id,
                "lineage_id": lineage_id,
                "revision": revision,
                "parent_artifact_id": parent,
                "scene": scene,
                "scene_sha256": scene_sha256,
            }
            envelope = {
                "version": 1,
                "kind": "whiteboard_snapshot",
                "space_id": space_id,
                "title": f"Whiteboard snapshot {revision}",
                "source_refs": [],
                "payload": payload,
                "review": {"mode": "deterministic", "status": "passed"},
            }
            artifacts.append(
                {
                    "space_id": space_id,
                    "artifact_id": artifact_id,
                    "kind": "whiteboard_snapshot",
                    "title": envelope["title"],
                    "version": 1,
                    "status": "draft",
                    "review_mode": "deterministic",
                    "review_status": "passed",
                    "envelope": envelope,
                    "created_at": "2026-07-26T00:00:00Z",
                    "updated_at": "2026-07-26T00:00:00Z",
                }
            )
            parent = artifact_id
        state = {
            "schema_version": 1,
            "activity_id": activity_id,
            "lineage_id": lineage_id,
            "revision": 1,
            "scene": scene,
            "scene_sha256": scene_sha256,
            "request_ledger": [
                {
                    "operation": "save",
                    "idempotency_key": f"near-save-{index}",
                    "request_sha256": canonical_sha256(
                        {
                            "schema_version": 1,
                            "operation": "save",
                            "activity_id": activity_id,
                            "lineage_id": lineage_id,
                            "expected_revision": 0,
                            "scene_sha256": scene_sha256,
                        }
                    ),
                    "source_artifact_id": None,
                    "result_revision": 1,
                    "result_scene_sha256": scene_sha256,
                }
            ],
        }
        item = {
            "space_id": space_id,
            "item_id": whiteboard_working_item_id(owner_id, space_id, activity_id),
            "artifact_id": None,
            "item_type": "whiteboard_working",
            "state": state,
            "created_at": "2026-07-26T00:00:00Z",
            "updated_at": "2026-07-26T00:00:00Z",
        }
        unit_size = len(canonical_json_bytes(state)) + sum(
            len(canonical_json_bytes(row["envelope"])) for row in artifacts
        )
        next_unit = {"artifacts": artifacts, "item": item, "bytes": unit_size}
        if total + unit_size > MAX_WHITEBOARD_OWNER_BYTES:
            break
        bundle["artifacts"].extend(artifacts)
        bundle["items"].append(item)
        total += unit_size
        index += 1
    assert total <= MAX_WHITEBOARD_OWNER_BYTES
    assert total > MAX_WHITEBOARD_OWNER_BYTES - next_unit["bytes"]
    return bundle, next_unit


def test_actual_near_owner_cap_export_import_round_trip_and_over_cap_zero_write(
    runtime,
):
    _, store, _ = runtime
    source_owner = "desktop:near-cap-source"
    bundle, next_unit = _near_cap_whiteboard_bundle(source_owner)

    store.import_owner_bundle(source_owner, bundle)
    exported = store.export_owner_bundle(source_owner)
    restored_owner = "desktop:near-cap-restored"
    restored = store.import_owner_bundle(restored_owner, exported)

    assert restored["artifacts"] == len(bundle["artifacts"])
    assert restored["items"] == len(bundle["items"])
    over_cap = copy.deepcopy(bundle)
    over_cap["artifacts"].extend(next_unit["artifacts"])
    over_cap["items"].append(next_unit["item"])
    over_owner = "desktop:over-cap-owner"
    with pytest.raises(WhiteboardQuotaError, match="owner"):
        store.import_owner_bundle(over_owner, over_cap)
    assert store.list_spaces(over_owner) == []
