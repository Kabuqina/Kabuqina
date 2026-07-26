# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""S-3 constrained Tutor-to-whiteboard command port.

The model-facing side of Tutor may propose only this exact element command
batch.  Trusted host code previews the complete prospective scene, then echoes
its fingerprint into ``apply``.  Tutor and whiteboard identity/revisions are
rechecked under their shared cross-process operation guard before whiteboard
CAS; this port never mutates Tutor checkpoint truth.
"""

from __future__ import annotations

import copy
import hashlib
from typing import Any, Mapping, Sequence

from learning.tutor_contract import (
    LearningActivityKeyV1,
    TutorConflictError,
    TutorContractError,
)
from learning.tutor_runtime_store import TutorRuntimeStore
from learning.whiteboard import WhiteboardService
from learning.whiteboard_contract import (
    WhiteboardContractError,
    canonical_json_bytes,
    canonical_sha256,
    require_opaque_id,
    require_sha256,
    validate_whiteboard_element,
    validate_whiteboard_scene,
)


TUTOR_WHITEBOARD_COMMAND_SCHEMA_VERSION = 1
MAX_TUTOR_WHITEBOARD_COMMANDS = 32
MAX_TUTOR_WHITEBOARD_COMMAND_BYTES = 64 * 1024

_PUT_FIELDS = frozenset({"op", "element"})
_DELETE_FIELDS = frozenset({"op", "element_id"})


def _revision(value: Any, label: str) -> int:
    if type(value) is not int or not 0 <= value < 2_147_483_647:
        raise TutorContractError(f"{label} must be a non-negative integer")
    return value


def validate_tutor_whiteboard_commands(value: Any) -> tuple[dict[str, Any], ...]:
    """Validate one exact, bounded, versioned element-command batch."""

    if not isinstance(value, Mapping) or set(value) != {
        "schema_version",
        "commands",
    }:
        raise TutorContractError("Tutor whiteboard command batch fields are invalid")
    commands = value.get("commands")
    if (
        value.get("schema_version") != TUTOR_WHITEBOARD_COMMAND_SCHEMA_VERSION
        or not isinstance(commands, list)
        or not 1 <= len(commands) <= MAX_TUTOR_WHITEBOARD_COMMANDS
    ):
        raise TutorContractError("Tutor whiteboard command batch is invalid")
    if len(canonical_json_bytes(value)) > MAX_TUTOR_WHITEBOARD_COMMAND_BYTES:
        raise TutorContractError("Tutor whiteboard command batch exceeds 64 KiB")

    normalized: list[dict[str, Any]] = []
    touched: set[str] = set()
    for raw in commands:
        if not isinstance(raw, Mapping):
            raise TutorContractError("Tutor whiteboard command must be an object")
        op = raw.get("op")
        if op == "put_element" and set(raw) == _PUT_FIELDS:
            try:
                element = validate_whiteboard_element(raw.get("element"))
            except WhiteboardContractError as exc:
                raise TutorContractError(
                    "Tutor whiteboard element command is invalid"
                ) from exc
            element_id = element["element_id"]
            command = {"op": "put_element", "element": element}
        elif op == "delete_element" and set(raw) == _DELETE_FIELDS:
            try:
                element_id = require_opaque_id(raw.get("element_id"), "element_id")
            except WhiteboardContractError as exc:
                raise TutorContractError(
                    "Tutor whiteboard delete command is invalid"
                ) from exc
            command = {"op": "delete_element", "element_id": element_id}
        else:
            raise TutorContractError("Tutor whiteboard command is not allowlisted")
        if element_id in touched:
            raise TutorContractError(
                "Tutor whiteboard batch may touch an element only once"
            )
        touched.add(element_id)
        normalized.append(command)
    return tuple(copy.deepcopy(normalized))


def preview_tutor_whiteboard_scene(
    scene: Any, commands: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Apply validated commands to a copy and validate the complete result."""

    current = validate_whiteboard_scene(scene)
    batch = validate_tutor_whiteboard_commands(
        {"schema_version": 1, "commands": list(commands)}
    )
    elements = copy.deepcopy(current["elements"])
    positions = {item["element_id"]: index for index, item in enumerate(elements)}
    changed = False
    for command in batch:
        if command["op"] == "put_element":
            element = command["element"]
            element_id = element["element_id"]
            if element_id in positions:
                index = positions[element_id]
                changed = changed or elements[index] != element
                elements[index] = copy.deepcopy(element)
            else:
                positions[element_id] = len(elements)
                elements.append(copy.deepcopy(element))
                changed = True
        else:
            element_id = command["element_id"]
            if element_id not in positions:
                raise TutorContractError(
                    "Tutor whiteboard delete target does not exist"
                )
            index = positions[element_id]
            elements.pop(index)
            positions = {
                item["element_id"]: item_index
                for item_index, item in enumerate(elements)
            }
            changed = True
    if not changed:
        raise TutorContractError("Tutor whiteboard command batch has no effect")
    return validate_whiteboard_scene({"schema_version": 1, "elements": elements})


def _scoped_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha256(canonical_json_bytes(list(parts))).hexdigest()
    return f"{prefix}_{digest[:48]}"


class TutorWhiteboardPort:
    """Trusted host port binding one Tutor run to its S-2 whiteboard state."""

    def __init__(
        self,
        runtime_store: TutorRuntimeStore,
        whiteboard: WhiteboardService,
    ) -> None:
        if (
            runtime_store.coordinator.db_path
            != whiteboard.store.coordinator.db_path
        ):
            raise ValueError("Tutor and whiteboard must share one coordinator")
        self.runtime_store = runtime_store
        self.whiteboard = whiteboard

    def _require_key(self, key: LearningActivityKeyV1) -> None:
        if not isinstance(key, LearningActivityKeyV1) or key.activity_kind != "tutor":
            raise TutorContractError("Tutor whiteboard requires activity_kind=tutor")
        if (
            key.owner_id != self.whiteboard.owner_id
            or key.space_id != self.whiteboard.space_id
        ):
            raise TutorContractError("Tutor whiteboard scope mismatch")

    def _require_tutor_revision(
        self, key: LearningActivityKeyV1, expected_revision: int, guard: Any
    ) -> Any:
        self._require_key(key)
        expected = _revision(expected_revision, "expected_tutor_revision")
        record = self.runtime_store.load(key, coordination_guard=guard)
        if record is None:
            raise TutorConflictError("activity_not_found")
        if record.revision != expected:
            raise TutorConflictError("stale_revision")
        return record

    @staticmethod
    def _base_scene(working: Mapping[str, Any] | None) -> dict[str, Any]:
        if working is None:
            return {"schema_version": 1, "elements": []}
        state = working.get("state")
        if not isinstance(state, Mapping):
            raise TutorContractError("whiteboard working state is invalid")
        return validate_whiteboard_scene(state.get("scene"))

    def _preview_under_guard(
        self,
        key: LearningActivityKeyV1,
        *,
        expected_tutor_revision: int,
        expected_working_revision: int,
        command_batch: Any,
        guard: Any,
        allow_applied_replay: bool = False,
    ) -> dict[str, Any]:
        self._require_tutor_revision(key, expected_tutor_revision, guard)
        expected_working = _revision(
            expected_working_revision, "expected_working_revision"
        )
        commands = validate_tutor_whiteboard_commands(command_batch)
        working = self.whiteboard.load_working(
            key.activity_id, coordination_guard=guard
        )
        current_revision = 0 if working is None else working["state"]["revision"]
        replay_candidate = (
            allow_applied_replay and current_revision == expected_working + 1
        )
        if current_revision != expected_working and not replay_candidate:
            raise TutorConflictError("whiteboard_stale_revision")
        command_sha256 = canonical_sha256(
            {"schema_version": 1, "commands": list(commands)}
        )
        scene = (
            self._base_scene(working)
            if replay_candidate
            else preview_tutor_whiteboard_scene(self._base_scene(working), commands)
        )
        preview_identity = {
            "schema_version": 1,
            "owner_id": key.owner_id,
            "space_id": key.space_id,
            "activity_id": key.activity_id,
            "tutor_revision": expected_tutor_revision,
            "base_working_revision": expected_working,
            "result_working_revision": expected_working + 1,
            "command_sha256": command_sha256,
            "scene_sha256": canonical_sha256(scene),
        }
        return {
            "schema_version": 1,
            "activity_id": key.activity_id,
            "tutor_revision": expected_tutor_revision,
            "base_working_revision": expected_working,
            "result_working_revision": expected_working + 1,
            "command_sha256": command_sha256,
            "scene_sha256": preview_identity["scene_sha256"],
            "preview_sha256": canonical_sha256(preview_identity),
            "scene": scene,
        }

    def preview(
        self,
        key: LearningActivityKeyV1,
        *,
        expected_tutor_revision: int,
        expected_working_revision: int,
        command_batch: Any,
    ) -> dict[str, Any]:
        self._require_key(key)
        with self.runtime_store.coordinator.begin_read(
            key.owner_id, key.space_id
        ) as guard:
            return self._preview_under_guard(
                key,
                expected_tutor_revision=expected_tutor_revision,
                expected_working_revision=expected_working_revision,
                command_batch=command_batch,
                guard=guard,
            )

    def apply(
        self,
        key: LearningActivityKeyV1,
        *,
        expected_tutor_revision: int,
        expected_working_revision: int,
        command_batch: Any,
        preview_sha256: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self._require_key(key)
        try:
            preview_hash = require_sha256(preview_sha256, "preview_sha256")
            caller_key = require_opaque_id(idempotency_key, "idempotency_key")
        except WhiteboardContractError as exc:
            raise TutorContractError("Tutor whiteboard apply identity is invalid") from exc
        with self.runtime_store.coordinator.begin_write(
            key.owner_id, key.space_id
        ) as guard:
            preview = self._preview_under_guard(
                key,
                expected_tutor_revision=expected_tutor_revision,
                expected_working_revision=expected_working_revision,
                command_batch=command_batch,
                guard=guard,
                allow_applied_replay=True,
            )
            if preview["preview_sha256"] != preview_hash:
                raise TutorConflictError("whiteboard_preview_mismatch")
            result = self.whiteboard.save_working(
                activity_id=key.activity_id,
                lineage_id=_scoped_id("twl", key.space_id, key.activity_id),
                expected_revision=expected_working_revision,
                idempotency_key=_scoped_id(
                    "tws",
                    key.activity_id,
                    expected_tutor_revision,
                    caller_key,
                    preview["command_sha256"],
                ),
                scene=preview["scene"],
                coordination_guard=guard,
            )
            return {
                "schema_version": 1,
                "status": "saved",
                "tutor_revision": expected_tutor_revision,
                "preview_sha256": preview_hash,
                "working": result,
            }

    def snapshot(
        self,
        key: LearningActivityKeyV1,
        *,
        expected_tutor_revision: int,
        expected_working_revision: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._lifecycle(
            key,
            operation="snapshot",
            expected_tutor_revision=expected_tutor_revision,
            expected_working_revision=expected_working_revision,
            idempotency_key=idempotency_key,
        )

    def cancel(
        self,
        key: LearningActivityKeyV1,
        *,
        expected_tutor_revision: int,
        expected_working_revision: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._lifecycle(
            key,
            operation="cancel",
            expected_tutor_revision=expected_tutor_revision,
            expected_working_revision=expected_working_revision,
            idempotency_key=idempotency_key,
        )

    def _lifecycle(
        self,
        key: LearningActivityKeyV1,
        *,
        operation: str,
        expected_tutor_revision: int,
        expected_working_revision: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self._require_key(key)
        expected_working = _revision(
            expected_working_revision, "expected_working_revision"
        )
        try:
            caller_key = require_opaque_id(idempotency_key, "idempotency_key")
        except WhiteboardContractError as exc:
            raise TutorContractError("Tutor whiteboard lifecycle identity is invalid") from exc
        with self.runtime_store.coordinator.begin_write(
            key.owner_id, key.space_id
        ) as guard:
            self._require_tutor_revision(key, expected_tutor_revision, guard)
            scoped = _scoped_id(
                "twl",
                operation,
                key.activity_id,
                expected_tutor_revision,
                caller_key,
            )
            if operation == "snapshot":
                result = self.whiteboard.create_snapshot(
                    activity_id=key.activity_id,
                    expected_working_revision=expected_working,
                    idempotency_key=scoped,
                    tutor_checkpoint_revision=expected_tutor_revision,
                    coordination_guard=guard,
                )
            elif operation == "cancel":
                result = self.whiteboard.delete_working(
                    key.activity_id,
                    expected_revision=expected_working,
                    idempotency_key=scoped,
                    coordination_guard=guard,
                )
            else:
                raise AssertionError("unsupported Tutor whiteboard lifecycle operation")
            return {
                "schema_version": 1,
                "operation": operation,
                "tutor_revision": expected_tutor_revision,
                "result": result,
            }

    def attach(
        self,
        key: LearningActivityKeyV1,
        artifact_id: str,
        *,
        expected_tutor_revision: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._snapshot_action(
            key,
            artifact_id,
            operation="attach",
            expected_tutor_revision=expected_tutor_revision,
            expected_working_revision=None,
            idempotency_key=idempotency_key,
        )

    def recover(
        self,
        key: LearningActivityKeyV1,
        artifact_id: str,
        *,
        expected_tutor_revision: int,
        expected_working_revision: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._snapshot_action(
            key,
            artifact_id,
            operation="recover",
            expected_tutor_revision=expected_tutor_revision,
            expected_working_revision=expected_working_revision,
            idempotency_key=idempotency_key,
        )

    def _snapshot_action(
        self,
        key: LearningActivityKeyV1,
        artifact_id: str,
        *,
        operation: str,
        expected_tutor_revision: int,
        expected_working_revision: int | None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self._require_key(key)
        try:
            artifact = require_opaque_id(artifact_id, "artifact_id")
            caller_key = require_opaque_id(idempotency_key, "idempotency_key")
        except WhiteboardContractError as exc:
            raise TutorContractError("Tutor whiteboard lifecycle identity is invalid") from exc
        if expected_working_revision is not None:
            _revision(expected_working_revision, "expected_working_revision")
        with self.runtime_store.coordinator.begin_write(
            key.owner_id, key.space_id
        ) as guard:
            self._require_tutor_revision(key, expected_tutor_revision, guard)
            snapshot = self.whiteboard.get_snapshot(
                artifact, coordination_guard=guard
            )
            payload = snapshot["envelope"]["payload"]
            if payload["activity_id"] != key.activity_id:
                raise TutorConflictError("whiteboard_activity_mismatch")
            scoped = _scoped_id(
                "twl",
                operation,
                key.activity_id,
                expected_tutor_revision,
                caller_key,
            )
            if operation == "attach":
                result = self.whiteboard.attach_snapshot(
                    artifact,
                    idempotency_key=scoped,
                    coordination_guard=guard,
                )
            elif operation == "recover":
                assert expected_working_revision is not None
                result = self.whiteboard.restore_snapshot(
                    artifact,
                    expected_working_revision=expected_working_revision,
                    idempotency_key=scoped,
                    coordination_guard=guard,
                )
            else:
                raise AssertionError("unsupported Tutor whiteboard snapshot operation")
            return {
                "schema_version": 1,
                "operation": operation,
                "tutor_revision": expected_tutor_revision,
                "result": result,
            }

    def fallback_projection(self, key: LearningActivityKeyV1) -> dict[str, Any]:
        """Return only readable Tutor/check state after a whiteboard failure."""

        self._require_key(key)
        source = self.runtime_store.load_projection_source(key)
        if source is None:
            raise TutorConflictError("activity_not_found")
        record, _run = source
        state = record.checkpoint.state if record.checkpoint is not None else {}
        latest = state.get("latest_output")
        pending = state.get("pending_interrupt")
        public_pending = None
        if isinstance(pending, dict):
            public_pending = {
                field: copy.deepcopy(pending[field])
                for field in (
                    "schema_version",
                    "interrupt_id",
                    "kind",
                    "checkpoint_revision",
                    "prompt",
                    "expected_input",
                    "created_at",
                )
                if field in pending
            }
        return {
            "schema_version": 1,
            "activity_id": key.activity_id,
            "tutor_revision": record.revision,
            "tutor_status": record.status,
            "latest_output": copy.deepcopy(latest) if isinstance(latest, dict) else None,
            "pending_interrupt": public_pending,
        }


__all__ = [
    "MAX_TUTOR_WHITEBOARD_COMMANDS",
    "TUTOR_WHITEBOARD_COMMAND_SCHEMA_VERSION",
    "TutorWhiteboardPort",
    "preview_tutor_whiteboard_scene",
    "validate_tutor_whiteboard_commands",
]
