"""Ports and a deterministic in-memory fake for Tutor lifecycle persistence."""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from .tutor_contract import (
    ACTIVITY_STATUSES,
    TERMINAL_ACTIVITY_STATUSES,
    LearningActivityKeyV1,
    LearningActivityStartV1,
    TutorConflictError,
    TutorContractError,
    canonical_json_bytes,
    is_allowed_activity_transition,
)


MAX_CHECKPOINT_BYTES = 256 * 1024
_FORBIDDEN_CHECKPOINT_KEYS = frozenset(
    {
        "api_key",
        "api-key",
        "apikey",
        "browser_tab_id",
        "callback",
        "chain_of_thought",
        "client",
        "credential",
        "credentials",
        "db_handle",
        "exception",
        "full_provider_response",
        "gateway_id",
        "raw_source",
        "raw_source_bytes",
        "tool_credential",
    }
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _scan_forbidden_checkpoint_fields(value: Any, path: str = "checkpoint") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = key.strip().lower() if isinstance(key, str) else ""
            if normalized in _FORBIDDEN_CHECKPOINT_KEYS:
                raise TutorContractError(f"{path} contains forbidden field: {key}")
            _scan_forbidden_checkpoint_fields(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _scan_forbidden_checkpoint_fields(item, f"{path}[{index}]")


def validate_checkpoint_state(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise TutorContractError("checkpoint state must be an object")
    _scan_forbidden_checkpoint_fields(state)
    encoded = canonical_json_bytes(state)
    if len(encoded) > MAX_CHECKPOINT_BYTES:
        raise TutorContractError(
            "checkpoint exceeds 256 KiB", reason_code="checkpoint_too_large"
        )
    return copy.deepcopy(state)


@dataclass(frozen=True)
class LearningCheckpointV1:
    key: LearningActivityKeyV1
    revision: int
    status: str
    state: dict[str, Any]
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise TutorContractError("unsupported checkpoint schema_version")
        if type(self.revision) is not int or self.revision < 0:
            raise TutorContractError("checkpoint revision must be non-negative")
        if self.status not in ACTIVITY_STATUSES:
            raise TutorContractError("checkpoint status is invalid")
        object.__setattr__(self, "state", validate_checkpoint_state(self.state))


@dataclass(frozen=True)
class LearningActivityRecordV1:
    key: LearningActivityKeyV1
    status: str
    revision: int
    idempotency_key: str
    request_fingerprint: str
    goal: str
    input_refs: tuple[dict[str, Any], ...]
    checkpoint: LearningCheckpointV1 | None
    created_at: str
    updated_at: str


@runtime_checkable
class LearningCheckpointStore(Protocol):
    def load_checkpoint(
        self, key: LearningActivityKeyV1
    ) -> LearningCheckpointV1 | None: ...

    def save_checkpoint(
        self, checkpoint: LearningCheckpointV1, *, expected_revision: int
    ) -> LearningCheckpointV1: ...

    def clear_checkpoint(
        self, key: LearningActivityKeyV1, *, expected_revision: int
    ) -> int: ...


@runtime_checkable
class LearningActivityRepository(Protocol):
    def create(
        self,
        request: LearningActivityStartV1,
        checkpoint: LearningCheckpointV1,
    ) -> tuple[LearningActivityRecordV1, bool]: ...

    def load(self, key: LearningActivityKeyV1) -> LearningActivityRecordV1 | None: ...

    def save(
        self, checkpoint: LearningCheckpointV1, *, expected_revision: int
    ) -> LearningActivityRecordV1: ...

    def list(
        self, owner_id: str, space_id: str, activity_kind: str
    ) -> list[LearningActivityRecordV1]: ...


class InMemoryLearningActivityRepository:
    """Port fake with production-equivalent identity/idempotency/CAS semantics."""

    def __init__(self) -> None:
        self._records: dict[
            tuple[str, str, str, str], LearningActivityRecordV1
        ] = {}
        self._idempotency: dict[
            tuple[str, str, str, str], tuple[tuple[str, str, str, str], str]
        ] = {}

    @staticmethod
    def _clone(record: LearningActivityRecordV1) -> LearningActivityRecordV1:
        return copy.deepcopy(record)

    def create(
        self,
        request: LearningActivityStartV1,
        checkpoint: LearningCheckpointV1,
    ) -> tuple[LearningActivityRecordV1, bool]:
        if checkpoint.key != request.key:
            raise TutorContractError("checkpoint key does not match start request")
        if checkpoint.revision != 0 or checkpoint.status != "created":
            raise TutorContractError("initial checkpoint must be created at revision 0")
        namespace = request.idempotency_namespace
        existing = self._idempotency.get(namespace)
        if existing is not None:
            existing_key, fingerprint = existing
            if fingerprint != request.request_fingerprint:
                raise TutorConflictError("idempotency_payload_mismatch")
            return self._clone(self._records[existing_key]), False
        key_tuple = request.key.as_tuple()
        if key_tuple in self._records:
            raise TutorConflictError("activity_id_conflict")
        now = _utc_now()
        record = LearningActivityRecordV1(
            key=request.key,
            status="created",
            revision=0,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            goal=request.goal,
            input_refs=copy.deepcopy(request.input_refs),
            checkpoint=copy.deepcopy(checkpoint),
            created_at=now,
            updated_at=now,
        )
        self._records[key_tuple] = record
        self._idempotency[namespace] = (key_tuple, request.request_fingerprint)
        return self._clone(record), True

    def load(self, key: LearningActivityKeyV1) -> LearningActivityRecordV1 | None:
        record = self._records.get(key.as_tuple())
        return None if record is None else self._clone(record)

    def load_checkpoint(
        self, key: LearningActivityKeyV1
    ) -> LearningCheckpointV1 | None:
        record = self._records.get(key.as_tuple())
        if record is None or record.checkpoint is None:
            return None
        return copy.deepcopy(record.checkpoint)

    def save(
        self, checkpoint: LearningCheckpointV1, *, expected_revision: int
    ) -> LearningActivityRecordV1:
        key_tuple = checkpoint.key.as_tuple()
        current = self._records.get(key_tuple)
        if current is None:
            raise TutorConflictError("activity_not_found")
        if current.status in TERMINAL_ACTIVITY_STATUSES:
            raise TutorConflictError("terminal_immutable")
        if current.revision != expected_revision or checkpoint.revision != expected_revision:
            raise TutorConflictError("stale_revision")
        if not is_allowed_activity_transition(current.status, checkpoint.status):
            raise TutorConflictError("invalid_transition")
        new_revision = expected_revision + 1
        stored_checkpoint = None
        if checkpoint.status not in TERMINAL_ACTIVITY_STATUSES:
            stored_checkpoint = replace(checkpoint, revision=new_revision)
        updated = replace(
            current,
            status=checkpoint.status,
            revision=new_revision,
            checkpoint=stored_checkpoint,
            updated_at=_utc_now(),
        )
        self._records[key_tuple] = updated
        return self._clone(updated)

    def save_checkpoint(
        self, checkpoint: LearningCheckpointV1, *, expected_revision: int
    ) -> LearningCheckpointV1:
        record = self.save(checkpoint, expected_revision=expected_revision)
        if record.checkpoint is None:
            raise TutorContractError("terminal transition clears checkpoint")
        return record.checkpoint

    def clear_checkpoint(
        self, key: LearningActivityKeyV1, *, expected_revision: int
    ) -> int:
        current = self._records.get(key.as_tuple())
        if current is None:
            raise TutorConflictError("activity_not_found")
        if current.revision != expected_revision:
            raise TutorConflictError("stale_revision")
        if current.status not in TERMINAL_ACTIVITY_STATUSES:
            raise TutorConflictError("checkpoint_clear_requires_terminal")
        self._records[key.as_tuple()] = replace(current, checkpoint=None)
        return expected_revision

    def list(
        self, owner_id: str, space_id: str, activity_kind: str
    ) -> list[LearningActivityRecordV1]:
        records = [
            self._clone(record)
            for key, record in self._records.items()
            if key[0] == owner_id and key[1] == space_id and key[2] == activity_kind
        ]
        records.sort(key=lambda item: (item.created_at, item.key.activity_id))
        return records


__all__ = [
    "InMemoryLearningActivityRepository",
    "LearningActivityRecordV1",
    "LearningActivityRepository",
    "LearningCheckpointStore",
    "LearningCheckpointV1",
    "MAX_CHECKPOINT_BYTES",
    "validate_checkpoint_state",
]

