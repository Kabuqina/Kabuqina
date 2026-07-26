# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Owner/space-scoped S-2 whiteboard runtime over ``learning.db``.

The public service is the only supported whiteboard mutation seam. It uses the
LearningStore coordinator and transaction helpers so saves, quota checks,
idempotency, snapshots, attachments and deletes are atomic across Desktop and
Gateway processes. No model, renderer, file, URL or browser state is accepted.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any, Mapping, Sequence

from learning.learning_contract import validate_envelope
from learning.learning_store import LearningStore
from learning.operation_coordinator import LearningOperationGuard
from learning.whiteboard_contract import (
    MAX_WHITEBOARD_ACTIVITY_BYTES,
    MAX_WHITEBOARD_ENVELOPE_BYTES,
    MAX_WHITEBOARD_OWNER_BYTES,
    MAX_WHITEBOARD_SNAPSHOTS_PER_ACTIVITY,
    MAX_WHITEBOARD_SPACE_BYTES,
    MAX_WORKING_IDEMPOTENCY_RECORDS,
    WHITEBOARD_SCHEMA_VERSION,
    WhiteboardContractError,
    canonical_json_bytes,
    canonical_sha256,
    require_opaque_id,
    require_sha256,
    validate_whiteboard_scene,
    validate_whiteboard_snapshot_payload,
    validate_whiteboard_working_state,
    whiteboard_working_item_id,
)


WHITEBOARD_WORKING_ITEM_TYPE = "whiteboard_working"
WHITEBOARD_ATTACH_ACTIVITY = "whiteboard.attach"
WHITEBOARD_DELETE_ACTIVITY = "whiteboard.delete"


class WhiteboardConflictError(WhiteboardContractError):
    """A valid request conflicts with persisted whiteboard state."""


class WhiteboardQuotaError(WhiteboardContractError):
    """A valid whiteboard write exceeds a frozen quota."""


def _utc_now(connection: sqlite3.Connection) -> str:
    return connection.execute(
        "SELECT strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"
    ).fetchone()[0]


def _require_expected_revision(value: Any) -> int:
    if type(value) is not int or not 0 <= value < 2_147_483_647:
        raise WhiteboardContractError("expected_revision must be a non-negative integer")
    return value


def _request_sha256(operation: str, body: Mapping[str, Any]) -> str:
    return canonical_sha256(
        {
            "schema_version": WHITEBOARD_SCHEMA_VERSION,
            "operation": operation,
            **dict(body),
        }
    )


def _derived_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256(canonical_json_bytes(list(parts))).hexdigest()
    return f"{prefix}_{digest[:48]}"


def _json_loads(raw: Any, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise WhiteboardContractError(f"persisted {label} is invalid JSON") from exc
    if not isinstance(value, dict):
        raise WhiteboardContractError(f"persisted {label} is not an object")
    return value


def _snapshot_from_row(row: sqlite3.Row) -> dict[str, Any]:
    envelope = _json_loads(row["envelope_json"], "whiteboard envelope")
    validated = validate_envelope(envelope).to_dict()
    if validated["kind"] != "whiteboard_snapshot":
        raise WhiteboardContractError("persisted artifact is not a whiteboard snapshot")
    return {
        "artifact_id": row["artifact_id"],
        "space_id": row["space_id"],
        "status": row["status"],
        "envelope": validated,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _working_from_row(row: sqlite3.Row) -> dict[str, Any]:
    state = validate_whiteboard_working_state(
        _json_loads(row["state_json"], "whiteboard working state")
    )
    return {
        "item_id": row["item_id"],
        "space_id": row["space_id"],
        "state": state,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _whiteboard_delete_details(
    connection: sqlite3.Connection, owner_id: str, space_id: str
) -> list[dict[str, Any]]:
    return [
        _json_loads(row["detail_json"], "whiteboard delete evidence")
        for row in connection.execute(
            "SELECT detail_json FROM learning_activities WHERE owner_id=? "
            "AND space_id=? AND activity_type=?",
            (owner_id, space_id, WHITEBOARD_DELETE_ACTIVITY),
        ).fetchall()
    ]


def assert_whiteboard_quotas(
    connection: sqlite3.Connection, owner_id: str
) -> None:
    """Validate count/byte quotas inside an existing write transaction."""
    owner_total = 0
    space_totals: dict[str, int] = {}
    activity_totals: dict[tuple[str, str], int] = {}
    snapshot_counts: dict[tuple[str, str], int] = {}

    artifact_rows = connection.execute(
        "SELECT space_id, envelope_json FROM learning_artifacts "
        "WHERE owner_id=? AND kind='whiteboard_snapshot'",
        (owner_id,),
    ).fetchall()
    for row in artifact_rows:
        envelope = validate_envelope(
            _json_loads(row["envelope_json"], "whiteboard envelope")
        ).to_dict()
        payload = validate_whiteboard_snapshot_payload(envelope["payload"])
        size = len(canonical_json_bytes(envelope))
        space_id = row["space_id"]
        activity_key = (space_id, payload["activity_id"])
        owner_total += size
        space_totals[space_id] = space_totals.get(space_id, 0) + size
        activity_totals[activity_key] = activity_totals.get(activity_key, 0) + size
        snapshot_counts[activity_key] = snapshot_counts.get(activity_key, 0) + 1

    item_rows = connection.execute(
        "SELECT space_id, state_json FROM learning_items "
        "WHERE owner_id=? AND item_type=?",
        (owner_id, WHITEBOARD_WORKING_ITEM_TYPE),
    ).fetchall()
    for row in item_rows:
        state = validate_whiteboard_working_state(
            _json_loads(row["state_json"], "whiteboard working state")
        )
        size = len(canonical_json_bytes(state))
        space_id = row["space_id"]
        activity_key = (space_id, state["activity_id"])
        owner_total += size
        space_totals[space_id] = space_totals.get(space_id, 0) + size
        activity_totals[activity_key] = activity_totals.get(activity_key, 0) + size

    if owner_total > MAX_WHITEBOARD_OWNER_BYTES:
        raise WhiteboardQuotaError("whiteboard owner quota exceeded")
    if any(value > MAX_WHITEBOARD_SPACE_BYTES for value in space_totals.values()):
        raise WhiteboardQuotaError("whiteboard space quota exceeded")
    if any(value > MAX_WHITEBOARD_ACTIVITY_BYTES for value in activity_totals.values()):
        raise WhiteboardQuotaError("whiteboard activity quota exceeded")
    if any(
        value > MAX_WHITEBOARD_SNAPSHOTS_PER_ACTIVITY
        for value in snapshot_counts.values()
    ):
        raise WhiteboardQuotaError("whiteboard snapshot count quota exceeded")


def validate_whiteboard_persistence(
    connection: sqlite3.Connection, owner_id: str
) -> None:
    """Validate imported/persisted whiteboard identities and lineage atomically."""
    snapshots: dict[tuple[str, str], dict[str, Any]] = {}
    revision_keys: set[tuple[str, str, str, int]] = set()
    for row in connection.execute(
        "SELECT * FROM learning_artifacts WHERE owner_id=? "
        "AND kind='whiteboard_snapshot'",
        (owner_id,),
    ).fetchall():
        artifact_id = require_opaque_id(row["artifact_id"], "artifact_id")
        snapshot = _snapshot_from_row(row)
        if snapshot["status"] not in {"draft", "active"}:
            raise WhiteboardContractError("whiteboard snapshot status is invalid")
        envelope = snapshot["envelope"]
        if len(canonical_json_bytes(envelope)) > MAX_WHITEBOARD_ENVELOPE_BYTES:
            raise WhiteboardQuotaError("whiteboard envelope quota exceeded")
        payload = envelope["payload"]
        key = (row["space_id"], artifact_id)
        snapshots[key] = snapshot
        revision_key = (
            row["space_id"],
            payload["activity_id"],
            payload["lineage_id"],
            payload["revision"],
        )
        if revision_key in revision_keys:
            raise WhiteboardContractError("whiteboard snapshot revision is duplicated")
        revision_keys.add(revision_key)

    for (space_id, _artifact_id), snapshot in snapshots.items():
        payload = snapshot["envelope"]["payload"]
        parent_id = payload["parent_artifact_id"]
        if payload["revision"] == 1:
            if parent_id is not None:
                raise WhiteboardContractError("whiteboard first snapshot has a parent")
            continue
        if parent_id is None:
            raise WhiteboardContractError("whiteboard snapshot parent is missing")
        parent = snapshots.get((space_id, parent_id))
        if parent is None:
            raise WhiteboardContractError("whiteboard snapshot parent is unavailable")
        parent_payload = parent["envelope"]["payload"]
        if (
            parent_payload["activity_id"] != payload["activity_id"]
            or parent_payload["lineage_id"] != payload["lineage_id"]
            or parent_payload["revision"] != payload["revision"] - 1
        ):
            raise WhiteboardContractError("whiteboard snapshot parent lineage is invalid")

    working_identities: set[tuple[str, str]] = set()
    for row in connection.execute(
        "SELECT * FROM learning_items WHERE owner_id=? AND item_type=?",
        (owner_id, WHITEBOARD_WORKING_ITEM_TYPE),
    ).fetchall():
        state = validate_whiteboard_working_state(
            _json_loads(row["state_json"], "whiteboard working state")
        )
        expected_item_id = whiteboard_working_item_id(
            owner_id, row["space_id"], state["activity_id"]
        )
        if row["item_id"] != expected_item_id or row["artifact_id"] is not None:
            raise WhiteboardContractError("whiteboard working item identity is invalid")
        identity = (row["space_id"], state["activity_id"])
        if identity in working_identities:
            raise WhiteboardContractError("whiteboard working activity is duplicated")
        working_identities.add(identity)
        for record in state["request_ledger"]:
            request_body = {
                "activity_id": state["activity_id"],
                "lineage_id": state["lineage_id"],
                "expected_revision": record["result_revision"] - 1,
                "scene_sha256": record["result_scene_sha256"],
            }
            if record["operation"] == "restore":
                request_body = {
                    "artifact_id": record["source_artifact_id"],
                    **request_body,
                }
            expected_request = _request_sha256(record["operation"], request_body)
            if record["request_sha256"] != expected_request:
                raise WhiteboardContractError(
                    "whiteboard working request hash is invalid"
                )

    deleted_snapshot_ids: set[tuple[str, str]] = set()
    attach_counts: dict[tuple[str, str], int] = {}
    evidence_rows = connection.execute(
        "SELECT * FROM learning_activities WHERE owner_id=? "
        "AND activity_type LIKE 'whiteboard.%'",
        (owner_id,),
    ).fetchall()
    for row in evidence_rows:
        detail = _json_loads(row["detail_json"], "whiteboard evidence")
        if detail.get("schema_version") != WHITEBOARD_SCHEMA_VERSION:
            raise WhiteboardContractError("whiteboard evidence version is invalid")
        if row["artifact_id"] is not None or row["item_id"] is not None:
            if row["activity_type"] != WHITEBOARD_ATTACH_ACTIVITY:
                raise WhiteboardContractError("whiteboard delete evidence has references")
        if row["activity_type"] == WHITEBOARD_DELETE_ACTIVITY:
            operation = detail.get("operation")
            idempotency_key = require_opaque_id(
                detail.get("idempotency_key"), "idempotency_key"
            )
            require_sha256(detail.get("request_sha256"), "request_sha256")
            if operation == "snapshot_delete":
                if set(detail) != {
                    "schema_version",
                    "operation",
                    "idempotency_key",
                    "target_artifact_ids",
                    "target_sha256",
                    "request_sha256",
                }:
                    raise WhiteboardContractError("whiteboard delete evidence fields are invalid")
                targets = detail["target_artifact_ids"]
                if (
                    not isinstance(targets, list)
                    or not targets
                    or len(targets) > MAX_WHITEBOARD_SNAPSHOTS_PER_ACTIVITY
                ):
                    raise WhiteboardContractError("whiteboard delete targets are invalid")
                normalized_targets = [
                    require_opaque_id(value, "target_artifact_id") for value in targets
                ]
                if len(normalized_targets) != len(set(normalized_targets)):
                    raise WhiteboardContractError("whiteboard delete targets are duplicated")
                if detail["target_sha256"] != canonical_sha256(normalized_targets):
                    raise WhiteboardContractError("whiteboard delete target hash is invalid")
                expected_request = _request_sha256(
                    "snapshot_delete",
                    {
                        "artifact_id": normalized_targets[-1],
                        "target_artifact_ids": normalized_targets,
                    },
                )
                if detail["request_sha256"] != expected_request:
                    raise WhiteboardContractError("whiteboard delete request hash is invalid")
                expected_id = _derived_id(
                    "wbd", row["space_id"], "snapshot-delete", idempotency_key
                )
                if row["activity_id"] != expected_id:
                    raise WhiteboardContractError("whiteboard delete identity is invalid")
                deleted_snapshot_ids.update(
                    (row["space_id"], value) for value in normalized_targets
                )
            elif operation == "working_delete":
                if set(detail) != {
                    "schema_version",
                    "operation",
                    "activity_id",
                    "expected_revision",
                    "idempotency_key",
                    "scene_sha256",
                    "request_sha256",
                }:
                    raise WhiteboardContractError("whiteboard delete evidence fields are invalid")
                activity_id = require_opaque_id(detail["activity_id"], "activity_id")
                expected_revision = _require_expected_revision(detail["expected_revision"])
                if expected_revision == 0:
                    raise WhiteboardContractError("whiteboard delete revision is invalid")
                require_sha256(detail["scene_sha256"], "scene_sha256")
                expected_request = _request_sha256(
                    "working_delete",
                    {
                        "activity_id": activity_id,
                        "expected_revision": expected_revision,
                    },
                )
                if detail["request_sha256"] != expected_request:
                    raise WhiteboardContractError("whiteboard delete request hash is invalid")
                expected_id = _derived_id(
                    "wbd", row["space_id"], "working-delete", idempotency_key
                )
                if row["activity_id"] != expected_id:
                    raise WhiteboardContractError("whiteboard delete identity is invalid")
            else:
                raise WhiteboardContractError("whiteboard delete operation is invalid")
        elif row["activity_type"] != WHITEBOARD_ATTACH_ACTIVITY:
            raise WhiteboardContractError("whiteboard activity type is invalid")

    for row in evidence_rows:
        if row["activity_type"] != WHITEBOARD_ATTACH_ACTIVITY:
            continue
        detail = _json_loads(row["detail_json"], "whiteboard attach evidence")
        if set(detail) != {
            "schema_version",
            "operation",
            "artifact_id",
            "idempotency_key",
            "scene_sha256",
            "request_sha256",
        } or detail.get("operation") != "attach":
            raise WhiteboardContractError("whiteboard attach evidence fields are invalid")
        artifact_id = require_opaque_id(detail["artifact_id"], "artifact_id")
        idempotency_key = require_opaque_id(
            detail["idempotency_key"], "idempotency_key"
        )
        require_sha256(detail["scene_sha256"], "scene_sha256")
        request_sha256 = _request_sha256("attach", {"artifact_id": artifact_id})
        expected_id = _derived_id(
            "wba", row["space_id"], "attach", idempotency_key
        )
        if (
            row["artifact_id"] != artifact_id
            or row["item_id"] is not None
            or row["activity_id"] != expected_id
            or detail["request_sha256"] != request_sha256
        ):
            raise WhiteboardContractError("whiteboard attach identity is invalid")
        snapshot = snapshots.get((row["space_id"], artifact_id))
        if snapshot is None:
            if (row["space_id"], artifact_id) not in deleted_snapshot_ids:
                raise WhiteboardContractError("whiteboard attach target is unavailable")
            continue
        if (
            snapshot["status"] != "active"
            or snapshot["envelope"]["payload"]["scene_sha256"]
            != detail["scene_sha256"]
        ):
            raise WhiteboardContractError("whiteboard attach target is inconsistent")
        key = (row["space_id"], artifact_id)
        attach_counts[key] = attach_counts.get(key, 0) + 1

    for key, snapshot in snapshots.items():
        expected_count = 1 if snapshot["status"] == "active" else 0
        if attach_counts.get(key, 0) != expected_count:
            raise WhiteboardContractError("whiteboard attachment evidence is inconsistent")

    assert_whiteboard_quotas(connection, owner_id)


class WhiteboardService:
    """Exact trusted whiteboard API for one owner and one learning space."""

    def __init__(
        self, store: LearningStore, owner_id: str, space_id: str
    ) -> None:
        self.store = store
        self.owner_id = require_opaque_id(owner_id, "owner_id")
        self.space_id = require_opaque_id(space_id, "space_id")

    def _require_space(self, connection: sqlite3.Connection) -> None:
        if not connection.execute(
            "SELECT 1 FROM learning_spaces WHERE owner_id=? AND space_id=?",
            (self.owner_id, self.space_id),
        ).fetchone():
            raise KeyError("learning space is unavailable")

    def _working_row(
        self, connection: sqlite3.Connection, activity_id: str
    ) -> sqlite3.Row | None:
        item_id = whiteboard_working_item_id(
            self.owner_id, self.space_id, activity_id
        )
        return connection.execute(
            "SELECT * FROM learning_items WHERE owner_id=? AND space_id=? "
            "AND item_id=? AND item_type=?",
            (
                self.owner_id,
                self.space_id,
                item_id,
                WHITEBOARD_WORKING_ITEM_TYPE,
            ),
        ).fetchone()

    @staticmethod
    def _find_replay(
        state: Mapping[str, Any], operation: str, idempotency_key: str
    ) -> dict[str, Any] | None:
        for record in state["request_ledger"]:
            if (
                record["operation"] == operation
                and record["idempotency_key"] == idempotency_key
            ):
                return record
        return None

    def _commit_working(
        self,
        connection: sqlite3.Connection,
        *,
        operation: str,
        activity_id: str,
        lineage_id: str,
        expected_revision: int,
        idempotency_key: str,
        scene: dict[str, Any],
        request_sha256: str,
        source_artifact_id: str | None,
    ) -> dict[str, Any]:
        row = self._working_row(connection, activity_id)
        existing: dict[str, Any] | None = None
        if row is not None:
            existing = _working_from_row(row)["state"]
            if (
                existing["activity_id"] != activity_id
                or existing["lineage_id"] != lineage_id
            ):
                raise WhiteboardConflictError("whiteboard working identity conflict")
            replay = self._find_replay(existing, operation, idempotency_key)
            if replay is not None:
                if replay["request_sha256"] != request_sha256:
                    raise WhiteboardConflictError("whiteboard idempotency conflict")
                return {
                    "item_id": row["item_id"],
                    "activity_id": activity_id,
                    "lineage_id": lineage_id,
                    "revision": replay["result_revision"],
                    "scene_sha256": replay["result_scene_sha256"],
                    "replayed": True,
                }
            if existing["revision"] != expected_revision:
                raise WhiteboardConflictError("whiteboard revision conflict")
        elif expected_revision != 0:
            raise WhiteboardConflictError("whiteboard revision conflict")
        else:
            for detail in _whiteboard_delete_details(
                connection, self.owner_id, self.space_id
            ):
                if (
                    detail.get("operation") == "working_delete"
                    and detail.get("activity_id") == activity_id
                ):
                    raise WhiteboardConflictError(
                        "whiteboard deleted activity cannot be recreated"
                    )

        result_revision = expected_revision + 1
        scene_sha256 = canonical_sha256(scene)
        ledger = list(existing["request_ledger"] if existing else [])
        ledger.append(
            {
                "operation": operation,
                "idempotency_key": idempotency_key,
                "request_sha256": request_sha256,
                "source_artifact_id": source_artifact_id,
                "result_revision": result_revision,
                "result_scene_sha256": scene_sha256,
            }
        )
        ledger = ledger[-MAX_WORKING_IDEMPOTENCY_RECORDS:]
        state = validate_whiteboard_working_state(
            {
                "schema_version": WHITEBOARD_SCHEMA_VERSION,
                "activity_id": activity_id,
                "lineage_id": lineage_id,
                "revision": result_revision,
                "scene": scene,
                "scene_sha256": scene_sha256,
                "request_ledger": ledger,
            }
        )
        state_json = canonical_json_bytes(state).decode("utf-8")
        item_id = whiteboard_working_item_id(
            self.owner_id, self.space_id, activity_id
        )
        now = _utc_now(connection)
        connection.execute(
            "INSERT INTO learning_items "
            "(owner_id,space_id,item_id,artifact_id,item_type,state_json,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(owner_id,space_id,item_id) DO UPDATE SET "
            "state_json=excluded.state_json, updated_at=excluded.updated_at",
            (
                self.owner_id,
                self.space_id,
                item_id,
                None,
                WHITEBOARD_WORKING_ITEM_TYPE,
                state_json,
                now,
                now,
            ),
        )
        assert_whiteboard_quotas(connection, self.owner_id)
        return {
            "item_id": item_id,
            "activity_id": activity_id,
            "lineage_id": lineage_id,
            "revision": result_revision,
            "scene_sha256": scene_sha256,
            "replayed": False,
        }

    def save_working(
        self,
        *,
        activity_id: str,
        lineage_id: str,
        expected_revision: int,
        idempotency_key: str,
        scene: Any,
        coordination_guard: LearningOperationGuard | None = None,
    ) -> dict[str, Any]:
        activity_id = require_opaque_id(activity_id, "activity_id")
        lineage_id = require_opaque_id(lineage_id, "lineage_id")
        expected_revision = _require_expected_revision(expected_revision)
        idempotency_key = require_opaque_id(idempotency_key, "idempotency_key")
        validated_scene = validate_whiteboard_scene(scene)
        request_sha256 = _request_sha256(
            "save",
            {
                "activity_id": activity_id,
                "lineage_id": lineage_id,
                "expected_revision": expected_revision,
                "scene_sha256": canonical_sha256(validated_scene),
            },
        )

        def _op(connection: sqlite3.Connection) -> dict[str, Any]:
            self._require_space(connection)
            return self._commit_working(
                connection,
                operation="save",
                activity_id=activity_id,
                lineage_id=lineage_id,
                expected_revision=expected_revision,
                idempotency_key=idempotency_key,
                scene=validated_scene,
                request_sha256=request_sha256,
                source_artifact_id=None,
            )

        return self.store._execute_write(
            self.owner_id,
            self.space_id,
            _op,
            coordination_guard=coordination_guard,
        )

    def load_working(
        self,
        activity_id: str,
        *,
        coordination_guard: LearningOperationGuard | None = None,
    ) -> dict[str, Any] | None:
        activity_id = require_opaque_id(activity_id, "activity_id")

        def _op(connection: sqlite3.Connection) -> dict[str, Any] | None:
            row = self._working_row(connection, activity_id)
            if row is None:
                return None
            working = _working_from_row(row)
            state = working["state"]
            return {
                **{key: value for key, value in working.items() if key != "state"},
                "state": {
                    key: value
                    for key, value in state.items()
                    if key != "request_ledger"
                },
            }

        return self.store._execute_read(
            self.owner_id,
            self.space_id,
            _op,
            coordination_guard=coordination_guard,
        )

    def list_working(self, *, limit: int = 50) -> list[dict[str, Any]]:
        if type(limit) is not int or not 1 <= limit <= 50:
            raise WhiteboardContractError("whiteboard list limit must be 1..50")

        def _op(connection: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = connection.execute(
                "SELECT * FROM learning_items WHERE owner_id=? AND space_id=? "
                "AND item_type=? ORDER BY updated_at DESC,item_id DESC LIMIT ?",
                (
                    self.owner_id,
                    self.space_id,
                    WHITEBOARD_WORKING_ITEM_TYPE,
                    limit,
                ),
            ).fetchall()
            summaries = []
            for row in rows:
                item = _working_from_row(row)
                state = item["state"]
                summaries.append(
                    {
                        "item_id": item["item_id"],
                        "activity_id": state["activity_id"],
                        "lineage_id": state["lineage_id"],
                        "revision": state["revision"],
                        "element_count": len(state["scene"]["elements"]),
                        "canonical_bytes": len(canonical_json_bytes(state)),
                        "scene_sha256": state["scene_sha256"],
                        "updated_at": item["updated_at"],
                    }
                )
            return summaries

        return self.store._execute_read(self.owner_id, self.space_id, _op)

    def create_snapshot(
        self,
        *,
        activity_id: str,
        expected_working_revision: int,
        idempotency_key: str,
        tutor_checkpoint_revision: int | None = None,
        coordination_guard: LearningOperationGuard | None = None,
    ) -> dict[str, Any]:
        activity_id = require_opaque_id(activity_id, "activity_id")
        expected = _require_expected_revision(expected_working_revision)
        if expected == 0:
            raise WhiteboardContractError("snapshot requires a committed working state")
        if tutor_checkpoint_revision is not None:
            tutor_checkpoint_revision = _require_expected_revision(
                tutor_checkpoint_revision
            )
        idempotency_key = require_opaque_id(idempotency_key, "idempotency_key")
        artifact_id = _derived_id(
            "wbs", self.space_id, "snapshot", idempotency_key
        )

        def _op(connection: sqlite3.Connection) -> dict[str, Any]:
            self._require_space(connection)
            existing = connection.execute(
                "SELECT * FROM learning_artifacts WHERE owner_id=? AND space_id=? "
                "AND artifact_id=?",
                (self.owner_id, self.space_id, artifact_id),
            ).fetchone()
            if existing is not None:
                snapshot = _snapshot_from_row(existing)
                refs = snapshot["envelope"]["source_refs"]
                ref = refs[0] if refs and isinstance(refs[0], dict) else {}
                if (
                    ref.get("operation") != "snapshot"
                    or ref.get("activity_id") != activity_id
                    or ref.get("working_revision") != expected
                    or ref.get("tutor_checkpoint_revision")
                    != tutor_checkpoint_revision
                ):
                    raise WhiteboardConflictError("whiteboard idempotency conflict")
                return self._snapshot_summary(snapshot, replayed=True)
            for detail in _whiteboard_delete_details(
                connection, self.owner_id, self.space_id
            ):
                if (
                    detail.get("operation") == "snapshot_delete"
                    and artifact_id in detail.get("target_artifact_ids", [])
                ):
                    raise WhiteboardConflictError(
                        "whiteboard deleted snapshot cannot be recreated"
                    )
            working_row = self._working_row(connection, activity_id)
            if working_row is None:
                raise KeyError("whiteboard working state is unavailable")
            working = _working_from_row(working_row)["state"]
            request_sha256 = _request_sha256(
                "snapshot",
                {
                    "activity_id": activity_id,
                    "lineage_id": working["lineage_id"],
                    "working_revision": expected,
                    "scene_sha256": working["scene_sha256"],
                },
            )
            if working["revision"] != expected:
                raise WhiteboardConflictError("whiteboard revision conflict")

            rows = connection.execute(
                "SELECT * FROM learning_artifacts WHERE owner_id=? AND space_id=? "
                "AND kind='whiteboard_snapshot' ORDER BY created_at,artifact_id",
                (self.owner_id, self.space_id),
            ).fetchall()
            lineage = []
            for row in rows:
                snapshot = _snapshot_from_row(row)
                payload = snapshot["envelope"]["payload"]
                if (
                    payload["activity_id"] == activity_id
                    and payload["lineage_id"] == working["lineage_id"]
                ):
                    lineage.append(snapshot)
            if len(lineage) >= MAX_WHITEBOARD_SNAPSHOTS_PER_ACTIVITY:
                raise WhiteboardQuotaError("whiteboard snapshot count quota exceeded")
            lineage.sort(key=lambda item: item["envelope"]["payload"]["revision"])
            parent = lineage[-1] if lineage else None
            revision = len(lineage) + 1
            if parent is not None and parent["envelope"]["payload"]["revision"] != revision - 1:
                raise WhiteboardConflictError("whiteboard snapshot lineage is invalid")
            payload = validate_whiteboard_snapshot_payload(
                {
                    "schema_version": WHITEBOARD_SCHEMA_VERSION,
                    "activity_id": activity_id,
                    "lineage_id": working["lineage_id"],
                    "revision": revision,
                    "parent_artifact_id": parent["artifact_id"] if parent else None,
                    "scene": working["scene"],
                    "scene_sha256": working["scene_sha256"],
                }
            )
            source_ref = {
                "origin": "whiteboard",
                "operation": "snapshot",
                "activity_id": activity_id,
                "request_sha256": request_sha256,
                "working_revision": expected,
            }
            if tutor_checkpoint_revision is not None:
                source_ref["tutor_checkpoint_revision"] = tutor_checkpoint_revision
            envelope = validate_envelope(
                {
                    "version": 1,
                    "kind": "whiteboard_snapshot",
                    "space_id": self.space_id,
                    "title": f"Whiteboard snapshot {revision}",
                    "source_refs": [source_ref],
                    "payload": payload,
                    "review": {"mode": "deterministic", "status": "passed"},
                }
            ).to_dict()
            envelope_json = canonical_json_bytes(envelope)
            if len(envelope_json) > MAX_WHITEBOARD_ENVELOPE_BYTES:
                raise WhiteboardQuotaError("whiteboard envelope quota exceeded")
            now = _utc_now(connection)
            connection.execute(
                "INSERT INTO learning_artifacts "
                "(owner_id,space_id,artifact_id,kind,title,version,status,review_mode,"
                "review_status,envelope_json,source_refs_json,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    self.owner_id,
                    self.space_id,
                    artifact_id,
                    "whiteboard_snapshot",
                    envelope["title"],
                    1,
                    "draft",
                    "deterministic",
                    "passed",
                    envelope_json.decode("utf-8"),
                    canonical_json_bytes(envelope["source_refs"]).decode("utf-8"),
                    now,
                    now,
                ),
            )
            assert_whiteboard_quotas(connection, self.owner_id)
            row = connection.execute(
                "SELECT * FROM learning_artifacts WHERE owner_id=? AND space_id=? "
                "AND artifact_id=?",
                (self.owner_id, self.space_id, artifact_id),
            ).fetchone()
            return self._snapshot_summary(_snapshot_from_row(row), replayed=False)

        return self.store._execute_write(
            self.owner_id,
            self.space_id,
            _op,
            coordination_guard=coordination_guard,
        )

    @staticmethod
    def _snapshot_summary(
        snapshot: Mapping[str, Any], *, replayed: bool = False
    ) -> dict[str, Any]:
        payload = snapshot["envelope"]["payload"]
        return {
            "artifact_id": snapshot["artifact_id"],
            "activity_id": payload["activity_id"],
            "lineage_id": payload["lineage_id"],
            "revision": payload["revision"],
            "parent_artifact_id": payload["parent_artifact_id"],
            "element_count": len(payload["scene"]["elements"]),
            "canonical_bytes": len(canonical_json_bytes(snapshot["envelope"])),
            "scene_sha256": payload["scene_sha256"],
            "status": snapshot["status"],
            "created_at": snapshot["created_at"],
            "updated_at": snapshot["updated_at"],
            "replayed": replayed,
        }

    def list_snapshots(self, activity_id: str) -> list[dict[str, Any]]:
        activity_id = require_opaque_id(activity_id, "activity_id")

        def _op(connection: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = connection.execute(
                "SELECT * FROM learning_artifacts WHERE owner_id=? AND space_id=? "
                "AND kind='whiteboard_snapshot' ORDER BY created_at,artifact_id",
                (self.owner_id, self.space_id),
            ).fetchall()
            snapshots = [
                _snapshot_from_row(row)
                for row in rows
                if _json_loads(row["envelope_json"], "whiteboard envelope")
                .get("payload", {})
                .get("activity_id")
                == activity_id
            ]
            snapshots.sort(key=lambda item: item["envelope"]["payload"]["revision"])
            return [self._snapshot_summary(item) for item in snapshots]

        return self.store._execute_read(self.owner_id, self.space_id, _op)

    def get_snapshot(
        self,
        artifact_id: str,
        *,
        coordination_guard: LearningOperationGuard | None = None,
    ) -> dict[str, Any]:
        artifact_id = require_opaque_id(artifact_id, "artifact_id")

        def _op(connection: sqlite3.Connection) -> dict[str, Any]:
            row = connection.execute(
                "SELECT * FROM learning_artifacts WHERE owner_id=? AND space_id=? "
                "AND artifact_id=? AND kind='whiteboard_snapshot'",
                (self.owner_id, self.space_id, artifact_id),
            ).fetchone()
            if row is None:
                raise KeyError("whiteboard snapshot is unavailable")
            return _snapshot_from_row(row)

        return self.store._execute_read(
            self.owner_id,
            self.space_id,
            _op,
            coordination_guard=coordination_guard,
        )

    def restore_snapshot(
        self,
        artifact_id: str,
        *,
        expected_working_revision: int,
        idempotency_key: str,
        coordination_guard: LearningOperationGuard | None = None,
    ) -> dict[str, Any]:
        artifact_id = require_opaque_id(artifact_id, "artifact_id")
        expected = _require_expected_revision(expected_working_revision)
        idempotency_key = require_opaque_id(idempotency_key, "idempotency_key")

        def _op(connection: sqlite3.Connection) -> dict[str, Any]:
            row = connection.execute(
                "SELECT * FROM learning_artifacts WHERE owner_id=? AND space_id=? "
                "AND artifact_id=? AND kind='whiteboard_snapshot'",
                (self.owner_id, self.space_id, artifact_id),
            ).fetchone()
            if row is None:
                raise KeyError("whiteboard snapshot is unavailable")
            snapshot = _snapshot_from_row(row)
            payload = snapshot["envelope"]["payload"]
            request_sha256 = _request_sha256(
                "restore",
                {
                    "artifact_id": artifact_id,
                    "activity_id": payload["activity_id"],
                    "lineage_id": payload["lineage_id"],
                    "expected_revision": expected,
                    "scene_sha256": payload["scene_sha256"],
                },
            )
            return self._commit_working(
                connection,
                operation="restore",
                activity_id=payload["activity_id"],
                lineage_id=payload["lineage_id"],
                expected_revision=expected,
                idempotency_key=idempotency_key,
                scene=payload["scene"],
                request_sha256=request_sha256,
                source_artifact_id=artifact_id,
            )

        return self.store._execute_write(
            self.owner_id,
            self.space_id,
            _op,
            coordination_guard=coordination_guard,
        )

    def attach_snapshot(
        self,
        artifact_id: str,
        *,
        idempotency_key: str,
        coordination_guard: LearningOperationGuard | None = None,
    ) -> dict[str, Any]:
        artifact_id = require_opaque_id(artifact_id, "artifact_id")
        idempotency_key = require_opaque_id(idempotency_key, "idempotency_key")
        activity_evidence_id = _derived_id(
            "wba", self.space_id, "attach", idempotency_key
        )
        request_sha256 = _request_sha256(
            "attach", {"artifact_id": artifact_id}
        )

        def _op(connection: sqlite3.Connection) -> dict[str, Any]:
            row = connection.execute(
                "SELECT * FROM learning_artifacts WHERE owner_id=? AND space_id=? "
                "AND artifact_id=? AND kind='whiteboard_snapshot'",
                (self.owner_id, self.space_id, artifact_id),
            ).fetchone()
            if row is None:
                raise KeyError("whiteboard snapshot is unavailable")
            existing = connection.execute(
                "SELECT * FROM learning_activities WHERE owner_id=? AND space_id=? "
                "AND activity_id=?",
                (self.owner_id, self.space_id, activity_evidence_id),
            ).fetchone()
            if existing is not None:
                detail = _json_loads(existing["detail_json"], "attach evidence")
                if detail.get("request_sha256") != request_sha256:
                    raise WhiteboardConflictError("whiteboard idempotency conflict")
                return {"artifact_id": artifact_id, "status": "active", "replayed": True}
            if connection.execute(
                "SELECT 1 FROM learning_activities WHERE owner_id=? AND space_id=? "
                "AND activity_type=? AND artifact_id=? LIMIT 1",
                (
                    self.owner_id,
                    self.space_id,
                    WHITEBOARD_ATTACH_ACTIVITY,
                    artifact_id,
                ),
            ).fetchone():
                raise WhiteboardConflictError("whiteboard snapshot is already attached")
            snapshot = _snapshot_from_row(row)
            if snapshot["status"] != "draft":
                raise WhiteboardConflictError("whiteboard snapshot is not attachable")
            detail = {
                "schema_version": WHITEBOARD_SCHEMA_VERSION,
                "operation": "attach",
                "artifact_id": artifact_id,
                "idempotency_key": idempotency_key,
                "scene_sha256": snapshot["envelope"]["payload"]["scene_sha256"],
                "request_sha256": request_sha256,
            }
            now = _utc_now(connection)
            connection.execute(
                "UPDATE learning_artifacts SET status='active',updated_at=? "
                "WHERE owner_id=? AND space_id=? AND artifact_id=?",
                (now, self.owner_id, self.space_id, artifact_id),
            )
            connection.execute(
                "INSERT INTO learning_activities "
                "(owner_id,space_id,activity_id,activity_type,artifact_id,item_id,"
                "detail_json,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    self.owner_id,
                    self.space_id,
                    activity_evidence_id,
                    WHITEBOARD_ATTACH_ACTIVITY,
                    artifact_id,
                    None,
                    canonical_json_bytes(detail).decode("utf-8"),
                    now,
                ),
            )
            return {"artifact_id": artifact_id, "status": "active", "replayed": False}

        return self.store._execute_write(
            self.owner_id,
            self.space_id,
            _op,
            coordination_guard=coordination_guard,
        )

    def export_snapshot(self, artifact_id: str) -> dict[str, Any]:
        snapshot = self.get_snapshot(artifact_id)
        return {
            "schema_version": WHITEBOARD_SCHEMA_VERSION,
            "artifact_id": snapshot["artifact_id"],
            "envelope": snapshot["envelope"],
            "canonical_sha256": canonical_sha256(snapshot["envelope"]),
        }

    @staticmethod
    def _descendant_ids(
        snapshots: Sequence[Mapping[str, Any]], artifact_id: str
    ) -> list[str]:
        by_parent: dict[str, list[str]] = {}
        for snapshot in snapshots:
            parent = snapshot["envelope"]["payload"]["parent_artifact_id"]
            if parent is not None:
                by_parent.setdefault(parent, []).append(snapshot["artifact_id"])
        found: list[str] = []
        pending = [artifact_id]
        while pending:
            current = pending.pop()
            if current in found:
                raise WhiteboardConflictError("whiteboard snapshot lineage cycle")
            found.append(current)
            pending.extend(sorted(by_parent.get(current, ()), reverse=True))
        return found

    def preview_snapshot_delete(self, artifact_id: str) -> dict[str, Any]:
        artifact_id = require_opaque_id(artifact_id, "artifact_id")

        def _op(connection: sqlite3.Connection) -> dict[str, Any]:
            rows = connection.execute(
                "SELECT * FROM learning_artifacts WHERE owner_id=? AND space_id=? "
                "AND kind='whiteboard_snapshot'",
                (self.owner_id, self.space_id),
            ).fetchall()
            snapshots = [_snapshot_from_row(row) for row in rows]
            target = next(
                (item for item in snapshots if item["artifact_id"] == artifact_id), None
            )
            if target is None:
                raise KeyError("whiteboard snapshot is unavailable")
            lineage = target["envelope"]["payload"]["lineage_id"]
            same_lineage = [
                item
                for item in snapshots
                if item["envelope"]["payload"]["lineage_id"] == lineage
            ]
            targets = self._descendant_ids(same_lineage, artifact_id)
            active = sorted(
                item["artifact_id"]
                for item in same_lineage
                if item["artifact_id"] in targets and item["status"] == "active"
            )
            ordered = sorted(
                targets,
                key=lambda item_id: next(
                    item["envelope"]["payload"]["revision"]
                    for item in same_lineage
                    if item["artifact_id"] == item_id
                ),
                reverse=True,
            )
            return {
                "artifact_id": artifact_id,
                "target_artifact_ids": ordered,
                "active_attachment_ids": active,
                "requires_cascade": len(ordered) > 1 or bool(active),
            }

        return self.store._execute_read(self.owner_id, self.space_id, _op)

    def delete_snapshots(
        self,
        artifact_id: str,
        *,
        target_artifact_ids: Sequence[str],
        idempotency_key: str,
    ) -> dict[str, Any]:
        artifact_id = require_opaque_id(artifact_id, "artifact_id")
        idempotency_key = require_opaque_id(idempotency_key, "idempotency_key")
        if not isinstance(target_artifact_ids, (list, tuple)):
            raise WhiteboardContractError("target_artifact_ids must be an array")
        requested = [
            require_opaque_id(value, "target_artifact_id")
            for value in target_artifact_ids
        ]
        if (
            not requested
            or len(requested) != len(set(requested))
            or len(requested) > 8
        ):
            raise WhiteboardContractError("target_artifact_ids are invalid")
        activity_evidence_id = _derived_id(
            "wbd", self.space_id, "snapshot-delete", idempotency_key
        )
        request_sha256 = _request_sha256(
            "snapshot_delete",
            {"artifact_id": artifact_id, "target_artifact_ids": requested},
        )

        def _op(connection: sqlite3.Connection) -> dict[str, Any]:
            existing = connection.execute(
                "SELECT detail_json FROM learning_activities WHERE owner_id=? "
                "AND space_id=? AND activity_id=?",
                (self.owner_id, self.space_id, activity_evidence_id),
            ).fetchone()
            if existing is not None:
                detail = _json_loads(existing["detail_json"], "delete evidence")
                if detail.get("request_sha256") != request_sha256:
                    raise WhiteboardConflictError("whiteboard idempotency conflict")
                return {"deleted_artifact_ids": detail["target_artifact_ids"], "replayed": True}
            rows = connection.execute(
                "SELECT * FROM learning_artifacts WHERE owner_id=? AND space_id=? "
                "AND kind='whiteboard_snapshot'",
                (self.owner_id, self.space_id),
            ).fetchall()
            snapshots = [_snapshot_from_row(row) for row in rows]
            target = next(
                (item for item in snapshots if item["artifact_id"] == artifact_id), None
            )
            if target is None:
                raise KeyError("whiteboard snapshot is unavailable")
            lineage = target["envelope"]["payload"]["lineage_id"]
            same_lineage = [
                item
                for item in snapshots
                if item["envelope"]["payload"]["lineage_id"] == lineage
            ]
            exact = self._descendant_ids(same_lineage, artifact_id)
            exact.sort(
                key=lambda item_id: next(
                    item["envelope"]["payload"]["revision"]
                    for item in same_lineage
                    if item["artifact_id"] == item_id
                ),
                reverse=True,
            )
            if requested != exact:
                raise WhiteboardConflictError("whiteboard delete preview is stale")
            placeholders = ",".join("?" for _ in exact)
            connection.execute(
                f"DELETE FROM learning_artifacts WHERE owner_id=? AND space_id=? "
                f"AND artifact_id IN ({placeholders})",
                (self.owner_id, self.space_id, *exact),
            )
            target_hash = canonical_sha256(exact)
            detail = {
                "schema_version": WHITEBOARD_SCHEMA_VERSION,
                "operation": "snapshot_delete",
                "idempotency_key": idempotency_key,
                "target_artifact_ids": exact,
                "target_sha256": target_hash,
                "request_sha256": request_sha256,
            }
            now = _utc_now(connection)
            connection.execute(
                "INSERT INTO learning_activities "
                "(owner_id,space_id,activity_id,activity_type,artifact_id,item_id,"
                "detail_json,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    self.owner_id,
                    self.space_id,
                    activity_evidence_id,
                    WHITEBOARD_DELETE_ACTIVITY,
                    None,
                    None,
                    canonical_json_bytes(detail).decode("utf-8"),
                    now,
                ),
            )
            return {"deleted_artifact_ids": exact, "replayed": False}

        with self.store.coordinator.begin_write(
            self.owner_id, self.space_id
        ) as guard:
            result = self.store._execute_write(
                self.owner_id,
                self.space_id,
                _op,
                coordination_guard=guard,
            )
            self.store._compact_after_sensitive_delete()
            return result

    def delete_working(
        self,
        activity_id: str,
        *,
        expected_revision: int,
        idempotency_key: str,
        coordination_guard: LearningOperationGuard | None = None,
    ) -> dict[str, Any]:
        activity_id = require_opaque_id(activity_id, "activity_id")
        expected = _require_expected_revision(expected_revision)
        if expected == 0:
            raise WhiteboardContractError("working delete requires a committed revision")
        idempotency_key = require_opaque_id(idempotency_key, "idempotency_key")
        evidence_id = _derived_id(
            "wbd", self.space_id, "working-delete", idempotency_key
        )
        request_sha256 = _request_sha256(
            "working_delete",
            {"activity_id": activity_id, "expected_revision": expected},
        )

        def _op(connection: sqlite3.Connection) -> dict[str, Any]:
            evidence = connection.execute(
                "SELECT detail_json FROM learning_activities WHERE owner_id=? "
                "AND space_id=? AND activity_id=?",
                (self.owner_id, self.space_id, evidence_id),
            ).fetchone()
            if evidence is not None:
                detail = _json_loads(evidence["detail_json"], "delete evidence")
                if detail.get("request_sha256") != request_sha256:
                    raise WhiteboardConflictError("whiteboard idempotency conflict")
                return {"activity_id": activity_id, "deleted": True, "replayed": True}
            row = self._working_row(connection, activity_id)
            if row is None:
                raise KeyError("whiteboard working state is unavailable")
            working = _working_from_row(row)["state"]
            if working["revision"] != expected:
                raise WhiteboardConflictError("whiteboard revision conflict")
            connection.execute(
                "DELETE FROM learning_items WHERE owner_id=? AND space_id=? AND item_id=?",
                (self.owner_id, self.space_id, row["item_id"]),
            )
            detail = {
                "schema_version": WHITEBOARD_SCHEMA_VERSION,
                "operation": "working_delete",
                "activity_id": activity_id,
                "expected_revision": expected,
                "idempotency_key": idempotency_key,
                "scene_sha256": working["scene_sha256"],
                "request_sha256": request_sha256,
            }
            now = _utc_now(connection)
            connection.execute(
                "INSERT INTO learning_activities "
                "(owner_id,space_id,activity_id,activity_type,artifact_id,item_id,"
                "detail_json,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    self.owner_id,
                    self.space_id,
                    evidence_id,
                    WHITEBOARD_DELETE_ACTIVITY,
                    None,
                    None,
                    canonical_json_bytes(detail).decode("utf-8"),
                    now,
                ),
            )
            return {"activity_id": activity_id, "deleted": True, "replayed": False}

        if coordination_guard is not None:
            result = self.store._execute_write(
                self.owner_id,
                self.space_id,
                _op,
                coordination_guard=coordination_guard,
            )
            self.store._compact_after_sensitive_delete()
            return result
        with self.store.coordinator.begin_write(
            self.owner_id, self.space_id
        ) as guard:
            result = self.store._execute_write(
                self.owner_id,
                self.space_id,
                _op,
                coordination_guard=guard,
            )
            self.store._compact_after_sensitive_delete()
            return result


__all__ = [
    "WHITEBOARD_ATTACH_ACTIVITY",
    "WHITEBOARD_DELETE_ACTIVITY",
    "WHITEBOARD_WORKING_ITEM_TYPE",
    "WhiteboardConflictError",
    "WhiteboardQuotaError",
    "WhiteboardService",
    "assert_whiteboard_quotas",
    "validate_whiteboard_persistence",
]
