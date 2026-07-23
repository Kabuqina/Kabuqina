"""Composite Study/Tutor owner data operations and BundleV2 validation."""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Mapping

from .learning_store import LearningConflictError, LearningStore, default_learning_db_path
from .operation_coordinator import (
    LearningOperationCoordinator,
    OperationLease,
)
from .tutor_contract import TutorConflictError, TutorContractError, canonical_json_bytes
from .tutor_runtime_store import TutorRuntimeStore


LEARNING_SECTION_MAX_BYTES = 16 * 1024 * 1024
RUNTIME_SECTION_MAX_BYTES = 6 * 1024 * 1024
BUNDLE_OVERHEAD_MAX_BYTES = 1 * 1024 * 1024
OWNER_BUNDLE_MAX_BYTES = 24 * 1024 * 1024
logger = logging.getLogger(__name__)


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _learning_counts(bundle: Mapping[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for section in ("spaces", "artifacts", "items", "activities", "migrations"):
        rows = bundle.get(section)
        if not isinstance(rows, list):
            raise TutorContractError(f"learning_v1.{section} must be an array")
        counts[section] = len(rows)
    return counts


def _runtime_counts(bundle: Mapping[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for section in ("runs", "checkpoints", "attempts", "outbox"):
        rows = bundle.get(section)
        if not isinstance(rows, list):
            raise TutorContractError(f"tutor_runtime.{section} must be an array")
        counts[section] = len(rows)
    return counts


class CompositeLearningDataService:
    """The only owner/space delete/import/restore orchestrator."""

    def __init__(
        self,
        learning_store: LearningStore,
        runtime_store: TutorRuntimeStore,
        coordinator: LearningOperationCoordinator,
        *,
        owns_stores: bool = False,
    ) -> None:
        if learning_store.coordinator is not coordinator:
            raise ValueError("LearningStore must share the service coordinator instance")
        if runtime_store.coordinator is not coordinator:
            raise ValueError("TutorRuntimeStore must share the service coordinator instance")
        if learning_store.db_path.parent != runtime_store.db_path.parent:
            raise ValueError("learning and runtime databases must share one root")
        self.learning_store = learning_store
        self.runtime_store = runtime_store
        self.coordinator = coordinator
        self._owns_stores = owns_stores

    @classmethod
    def from_root(
        cls, root: Path | str | None = None
    ) -> "CompositeLearningDataService":
        if root is None:
            learning_path = default_learning_db_path().resolve()
            secure = True
        else:
            learning_path = Path(root).resolve() / "learning.db"
            secure = False
        coordinator = LearningOperationCoordinator.from_learning_db_path(
            learning_path, secure_permissions=secure
        )
        learning_store = LearningStore(
            learning_path, coordinator=coordinator
        )
        runtime_store = TutorRuntimeStore(
            learning_path.parent / "tutor_runtime.db",
            coordinator=coordinator,
            secure_permissions=secure,
        )
        return cls(
            learning_store,
            runtime_store,
            coordinator,
            owns_stores=True,
        )

    def close(self) -> None:
        if self._owns_stores:
            self.runtime_store.close()
            self.learning_store.close()
            self.coordinator.close()
            self._owns_stores = False

    def _export_sections(
        self, owner_id: str, operation_lease: OperationLease | None = None
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if operation_lease is not None:
            return (
                self.learning_store.export_owner_bundle(
                    owner_id, operation_lease=operation_lease
                ),
                self.runtime_store.export_owner_bundle(
                    owner_id, operation_lease=operation_lease
                ),
            )
        with self.coordinator.begin_read(owner_id, "") as guard:
            learning = self.learning_store.export_owner_bundle(
                owner_id, coordination_guard=guard
            )
            runtime = self.runtime_store.export_owner_bundle(
                owner_id, coordination_guard=guard
            )
            return learning, runtime

    @staticmethod
    def _assemble_bundle(
        learning: dict[str, Any], runtime: dict[str, Any]
    ) -> dict[str, Any]:
        manifest = {
            "schema_version": 1,
            "learning_v1": {
                "sha256": canonical_sha256(learning),
                "counts": _learning_counts(learning),
            },
            "tutor_runtime": {
                "sha256": canonical_sha256(runtime),
                "counts": _runtime_counts(runtime),
            },
        }
        return {
            "version": 2,
            "learning_v1": learning,
            "tutor_runtime": runtime,
            "manifest": manifest,
        }

    def export_owner_bundle(self, owner_id: str) -> dict[str, Any]:
        learning, runtime = self._export_sections(owner_id)
        bundle = self._assemble_bundle(learning, runtime)
        self.validate_owner_bundle(owner_id, bundle)
        return bundle

    def validate_owner_bundle(
        self, owner_id: str, bundle: Mapping[str, Any]
    ) -> dict[str, Any]:
        if not isinstance(bundle, Mapping):
            raise TutorContractError("StudyOwnerBundle must be an object")
        outer_bytes = canonical_json_bytes(bundle)
        if len(outer_bytes) > OWNER_BUNDLE_MAX_BYTES:
            raise TutorContractError("StudyOwnerBundle exceeds 24 MiB")
        if set(bundle) != {"version", "learning_v1", "tutor_runtime", "manifest"}:
            raise TutorContractError("StudyOwnerBundleV2 shape is invalid")
        if bundle.get("version") != 2:
            raise TutorContractError("unsupported StudyOwnerBundle version")
        learning = bundle.get("learning_v1")
        runtime = bundle.get("tutor_runtime")
        manifest = bundle.get("manifest")
        if (
            not isinstance(learning, Mapping)
            or learning.get("version") != 1
            or set(learning)
            != {"version", "spaces", "artifacts", "items", "activities", "migrations"}
        ):
            raise TutorContractError("learning_v1 section is invalid")
        if not isinstance(runtime, Mapping) or runtime.get("schema_version") != 1:
            raise TutorContractError("tutor_runtime section is invalid")
        learning_bytes = canonical_json_bytes(learning)
        runtime_bytes = canonical_json_bytes(runtime)
        if len(learning_bytes) > LEARNING_SECTION_MAX_BYTES:
            raise TutorContractError("learning_v1 section exceeds 16 MiB")
        if len(runtime_bytes) > RUNTIME_SECTION_MAX_BYTES:
            raise TutorContractError("tutor_runtime section exceeds 6 MiB")
        overhead = len(outer_bytes) - len(learning_bytes) - len(runtime_bytes)
        if overhead > BUNDLE_OVERHEAD_MAX_BYTES:
            raise TutorContractError("StudyOwnerBundle structural overhead exceeds 1 MiB")
        if not isinstance(manifest, Mapping) or set(manifest) != {
            "schema_version",
            "learning_v1",
            "tutor_runtime",
        }:
            raise TutorContractError("StudyOwnerBundle manifest is invalid")
        if manifest.get("schema_version") != 1:
            raise TutorContractError("StudyOwnerBundle manifest version is invalid")
        expected = self._assemble_bundle(dict(learning), dict(runtime))["manifest"]
        if manifest != expected:
            raise TutorConflictError("bundle_manifest_mismatch")
        # Runtime validation is pure and includes checkpoint/hash/quota checks.
        self.runtime_store._normalize_import_bundle(owner_id, runtime)
        _learning_counts(learning)
        return copy.deepcopy(dict(bundle))

    @staticmethod
    def bundle_sha256(bundle: Mapping[str, Any]) -> str:
        return canonical_sha256(bundle)

    @staticmethod
    def _learning_bundle_empty(bundle: Mapping[str, Any]) -> bool:
        return all(
            not bundle.get(section)
            for section in ("spaces", "artifacts", "items", "activities", "migrations")
        )

    def delete_owner_data(self, owner_id: str) -> dict[str, Any]:
        lease = self.coordinator.begin_operation(owner_id, "", "delete")
        return self._continue_delete(lease)

    def delete_space_data(self, owner_id: str, space_id: str) -> dict[str, Any]:
        lease = self.coordinator.begin_operation(owner_id, space_id, "delete")
        return self._continue_delete(lease)

    def _continue_delete(self, lease: OperationLease) -> dict[str, Any]:
        learning_counts: dict[str, int] = {}
        runtime_counts: dict[str, int] = {}
        current = lease
        if current.phase == "fenced":
            if current.space_id == "":
                learning_counts = self.learning_store.delete_owner_data(
                    current.owner_id, operation_lease=current
                )
            else:
                learning_counts = self.learning_store.delete_space_data(
                    current.owner_id,
                    current.space_id,
                    operation_lease=current,
                )
            current = self.coordinator.advance_operation(
                current,
                "learning_deleted",
                {"scope": "owner" if current.space_id == "" else "space"},
            )
        if current.phase == "learning_deleted":
            if current.space_id == "":
                runtime_counts = self.runtime_store.delete_owner_data(
                    current.owner_id, operation_lease=current
                )
            else:
                runtime_counts = self.runtime_store.delete_space_data(
                    current.owner_id,
                    current.space_id,
                    operation_lease=current,
                )
            current = self.coordinator.advance_operation(
                current,
                "runtime_deleted",
                {"scope": "owner" if current.space_id == "" else "space"},
            )
        if current.phase == "runtime_deleted":
            self.runtime_store.compact(
                current.owner_id,
                current.space_id,
                operation_lease=current,
            )
            current = self.coordinator.advance_operation(
                current,
                "compacted",
                {"scope": "owner" if current.space_id == "" else "space"},
            )
        if current.phase != "compacted":
            raise TutorConflictError("unknown_delete_recovery_phase")
        self.coordinator.finish_operation(current)
        return {"learning": learning_counts, "tutor_runtime": runtime_counts}

    def import_owner_bundle(
        self,
        owner_id: str,
        bundle: Mapping[str, Any],
        *,
        mode: str,
    ) -> dict[str, Any]:
        if mode == "tutor_runtime_merge":
            if not isinstance(bundle, Mapping) or bundle.get("version") != 2:
                raise TutorContractError("runtime merge requires StudyOwnerBundleV2")
            validated = self.validate_owner_bundle(owner_id, bundle)
            return self._merge_runtime(owner_id, validated)
        if mode != "replace_empty_owner":
            raise TutorContractError("Study owner import mode is invalid")
        if isinstance(bundle, Mapping) and bundle.get("version") == 1:
            learning = copy.deepcopy(dict(bundle))
            if len(canonical_json_bytes(learning)) > LEARNING_SECTION_MAX_BYTES:
                raise TutorContractError("learning v1 bundle exceeds 16 MiB")
            runtime = {
                "schema_version": 1,
                "runs": [],
                "checkpoints": [],
                "attempts": [],
                "outbox": [],
            }
            validated = self._assemble_bundle(learning, runtime)
            self.validate_owner_bundle(owner_id, validated)
        else:
            validated = self.validate_owner_bundle(owner_id, bundle)
        bundle_hash = self.bundle_sha256(validated)
        lease = self.coordinator.begin_operation(
            owner_id, "", "full_import", bundle_hash
        )
        current = lease
        writes_started = False
        try:
            current_learning = self.learning_store.export_owner_bundle(
                owner_id, operation_lease=current
            )
            if not self._learning_bundle_empty(current_learning) or not self.runtime_store.owner_is_empty(
                owner_id, operation_lease=current
            ):
                raise LearningConflictError("owner is not empty in both learning databases")
            current = self.coordinator.advance_operation(
                current, "validated_empty", {"target_was_empty": True}
            )
            writes_started = True
            learning_counts = self.learning_store.import_owner_bundle(
                owner_id,
                validated["learning_v1"],
                operation_lease=current,
            )
            current = self.coordinator.advance_operation(
                current, "learning_imported", {"target_was_empty": True}
            )
            runtime_counts = self.runtime_store.import_owner_bundle(
                owner_id,
                validated["tutor_runtime"],
                mode="replace_empty_owner",
                operation_lease=current,
            )
            current = self.coordinator.advance_operation(
                current, "runtime_imported", {"target_was_empty": True}
            )
            self.coordinator.finish_operation(current)
            return {
                "learning": learning_counts,
                "tutor_runtime": runtime_counts,
                "bundle_sha256": bundle_hash,
            }
        except BaseException:
            if writes_started:
                try:
                    self.runtime_store.delete_owner_data(
                        owner_id, operation_lease=current
                    )
                    self.learning_store.delete_owner_data(
                        owner_id, operation_lease=current
                    )
                    self.runtime_store.compact(owner_id, operation_lease=current)
                    self.coordinator.finish_operation(current)
                except BaseException:
                    # The durable journal/fence intentionally remains for
                    # restart recovery if synchronous cleanup itself fails.
                    pass
            else:
                self.coordinator.finish_operation(current)
            raise

    @staticmethod
    def _mark_missing_sources(
        owner_id: str,
        runtime_bundle: Mapping[str, Any],
        learning_bundle: Mapping[str, Any],
    ) -> dict[str, Any]:
        runtime = copy.deepcopy(dict(runtime_bundle))
        spaces = {row["space_id"] for row in learning_bundle.get("spaces", [])}
        artifacts = {
            (row["space_id"], row["artifact_id"])
            for row in learning_bundle.get("artifacts", [])
        }
        items = {
            (row["space_id"], row["item_id"])
            for row in learning_bundle.get("items", [])
        }
        checkpoints = {
            (row["space_id"], row["activity_kind"], row["activity_id"]): row
            for row in runtime["checkpoints"]
        }
        blocked_keys: set[tuple[str, str, str]] = set()
        for run in runtime["runs"]:
            if run["status"] in {"completed", "blocked", "cancelled"}:
                continue
            short_key = (run["space_id"], run["activity_kind"], run["activity_id"])
            checkpoint = checkpoints.get(short_key)
            missing = run["space_id"] not in spaces or checkpoint is None
            if checkpoint is not None:
                refs = checkpoint.get("state", {}).get("input_refs", [])
                for ref in refs if isinstance(refs, list) else []:
                    if not isinstance(ref, dict):
                        missing = True
                        break
                    if ref.get("kind") == "artifact" and (
                        run["space_id"], ref.get("id")
                    ) not in artifacts:
                        missing = True
                    if ref.get("kind") == "item" and (
                        run["space_id"], ref.get("id")
                    ) not in items:
                        missing = True
            if not missing:
                continue
            blocked_keys.add(short_key)
            was_running = run["status"] == "running"
            run["status"] = "blocked"
            run["revision"] += 1
            run["current_interrupt_id"] = None
            run["execution_id"] = None
            run["terminal_code"] = "source_missing"
            run["completion_basis"] = None
            run["terminal_at"] = run["updated_at"]
            if was_running:
                run["budget_active_elapsed_ms"] = min(
                    120_000, run["budget_active_elapsed_ms"] + 45_000
                )
            identity = (owner_id, *short_key)
            event_id = "tproj_" + hashlib.sha256(
                "\x1f".join(identity).encode("utf-8")
            ).hexdigest()
            payload = {
                "schema_version": 1,
                "outcome": "blocked",
                "terminal_code": "source_missing",
                "completion_basis": None,
                "remediation_count": run["remediation_count"],
                "budget_summary": {
                    "nodes_used": run["budget_nodes_used"],
                    "attempts_used": run["budget_attempts_used"],
                    "reserved_input_tokens": run["budget_reserved_input_tokens"],
                    "reserved_output_tokens": run["budget_reserved_output_tokens"],
                    "reserved_wall_ms": run["budget_reserved_wall_ms"],
                    "active_elapsed_ms": run["budget_active_elapsed_ms"],
                },
            }
            if not any(row["event_id"] == event_id for row in runtime["outbox"]):
                runtime["outbox"].append(
                    {
                        "event_id": event_id,
                        "space_id": run["space_id"],
                        "activity_kind": run["activity_kind"],
                        "activity_id": run["activity_id"],
                        "event_type": "tutor.terminal",
                        "payload": payload,
                        "created_at": run["updated_at"],
                        "delivered_at": None,
                    }
                )
        runtime["checkpoints"] = [
            row
            for row in runtime["checkpoints"]
            if (row["space_id"], row["activity_kind"], row["activity_id"])
            not in blocked_keys
        ]
        runtime["attempts"] = [
            row
            for row in runtime["attempts"]
            if (row["space_id"], row["activity_kind"], row["activity_id"])
            not in blocked_keys
        ]
        return runtime

    def _merge_runtime(
        self, owner_id: str, bundle: Mapping[str, Any]
    ) -> dict[str, Any]:
        bundle_hash = self.bundle_sha256(bundle)
        lease = self.coordinator.begin_operation(
            owner_id, "", "runtime_restore", bundle_hash
        )
        current = lease
        try:
            learning = self.learning_store.export_owner_bundle(
                owner_id, operation_lease=current
            )
            runtime = self._mark_missing_sources(
                owner_id, bundle["tutor_runtime"], learning
            )
            counts = self.runtime_store.import_owner_bundle(
                owner_id,
                runtime,
                mode="tutor_runtime_merge",
                operation_lease=current,
            )
            current = self.coordinator.advance_operation(
                current, "runtime_merged", {"bundle_sha256": bundle_hash}
            )
            self.coordinator.finish_operation(current)
            return {"tutor_runtime": counts, "bundle_sha256": bundle_hash}
        except BaseException:
            # Runtime merge is a single SQLite transaction and never touches
            # learning.db, so failure is already zero-write for the batch.
            self.coordinator.finish_operation(current)
            raise

    def prepare_downgrade(self, owner_id: str) -> dict[str, Any]:
        bundle = self.export_owner_bundle(owner_id)
        return {"bundle": bundle, "bundle_sha256": self.bundle_sha256(bundle)}

    def project_pending_outbox(self, owner_id: str, *, limit: int = 32) -> int:
        if type(limit) is not int or not 1 <= limit <= 32:
            raise TutorContractError("outbox projection limit must be within 1..32")
        with self.coordinator.begin_write(owner_id, "") as guard:
            events = self.runtime_store.list_pending_outbox(
                owner_id, coordination_guard=guard
            )[:limit]
            delivered = 0
            for event in events:
                payload = event["payload_json"]
                payload = payload if isinstance(payload, dict) else json.loads(payload)
                self.learning_store.insert_projection_activity_once(
                    owner_id,
                    event["space_id"],
                    projection_event_id=event["event_id"],
                    activity_kind=event["activity_kind"],
                    source_activity_id=event["activity_id"],
                    outcome=payload["outcome"],
                    terminal_code=payload["terminal_code"],
                    coordination_guard=guard,
                )
                if self.runtime_store.mark_outbox_delivered(
                    owner_id,
                    event["event_id"],
                    coordination_guard=guard,
                ):
                    delivered += 1
            return delivered

    def commit_prepare_downgrade(
        self, owner_id: str, expected_bundle_sha256: str
    ) -> dict[str, Any]:
        lease = self.coordinator.begin_operation(
            owner_id, "", "runtime_restore", expected_bundle_sha256
        )
        current = lease
        try:
            learning, runtime = self._export_sections(owner_id, current)
            current_bundle = self._assemble_bundle(learning, runtime)
            actual_hash = self.bundle_sha256(current_bundle)
            if actual_hash != expected_bundle_sha256:
                raise TutorConflictError("bundle_hash_drift")
            counts = self.runtime_store.delete_owner_data(
                owner_id, operation_lease=current
            )
            self.runtime_store.compact(owner_id, operation_lease=current)
            current = self.coordinator.advance_operation(
                current,
                "runtime_deleted",
                {"verified_bundle_sha256": expected_bundle_sha256},
            )
            self.coordinator.finish_operation(current)
            return {"tutor_runtime": counts, "bundle_sha256": actual_hash}
        except BaseException:
            self.coordinator.finish_operation(current)
            raise

    def recover_operations(self) -> int:
        recovered = 0
        for lease in self.coordinator.recover_operations():
            try:
                if lease.operation == "delete":
                    self._continue_delete(lease)
                elif lease.operation == "full_import":
                    if lease.phase == "fenced":
                        # No write is allowed before validated_empty is durable.
                        self.coordinator.finish_operation(lease)
                    else:
                        self.runtime_store.delete_owner_data(
                            lease.owner_id, operation_lease=lease
                        )
                        self.learning_store.delete_owner_data(
                            lease.owner_id, operation_lease=lease
                        )
                        self.runtime_store.compact(
                            lease.owner_id, operation_lease=lease
                        )
                        self.coordinator.finish_operation(lease)
                elif lease.operation == "runtime_restore":
                    # Merge is one runtime transaction; prepare cleanup is also
                    # a committed valid state. Clearing the journal exposes
                    # either the complete before or complete after state.
                    self.coordinator.finish_operation(lease)
                else:
                    raise TutorConflictError("unknown_learning_operation")
            except BaseException as exc:
                logger.warning(
                    "learning operation recovery failed operation_id=%s "
                    "kind=%s phase=%s reason=%s",
                    lease.operation_id,
                    lease.operation,
                    lease.phase,
                    getattr(exc, "reason_code", type(exc).__name__),
                )
                raise
            logger.info(
                "learning operation recovery completed operation_id=%s "
                "kind=%s phase=%s",
                lease.operation_id,
                lease.operation,
                lease.phase,
            )
            recovered += 1
        return recovered


__all__ = [
    "BUNDLE_OVERHEAD_MAX_BYTES",
    "CompositeLearningDataService",
    "LEARNING_SECTION_MAX_BYTES",
    "OWNER_BUNDLE_MAX_BYTES",
    "RUNTIME_SECTION_MAX_BYTES",
    "canonical_sha256",
]
