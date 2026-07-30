"""SQLite v1 adapter for resumable Tutor run/checkpoint truth.

The runtime database is intentionally separate from ``learning.db`` so v0.4
never opens or mutates these tables.  Every business read/write first acquires
the shared operation coordinator, preserving the fixed lock order
``coordination -> runtime`` (and ``coordination -> learning -> runtime`` for
composite services).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import sqlite3
import threading
import time
from typing import Any, Callable, Mapping, TypeVar

from kabuqina_constants import get_default_kabuqina_root

from .checkpoint_store import (
    MAX_CHECKPOINT_BYTES,
    LearningActivityRecordV1,
    LearningCheckpointV1,
    validate_checkpoint_state,
)
from .operation_coordinator import (
    LearningOperationCoordinator,
    LearningOperationGuard,
    OperationLease,
    secure_coordination_db,
)
from .tutor_contract import (
    ACTIVITY_KINDS,
    ACTIVITY_STATUSES,
    TERMINAL_ACTIVITY_STATUSES,
    LearningActivityKeyV1,
    LearningActivityStartV1,
    LearningInterruptV1,
    TutorConflictError,
    TutorContractError,
    canonical_json_bytes,
    is_allowed_activity_transition,
    validate_resume_request,
)


T = TypeVar("T")
RUNTIME_SCHEMA_VERSION = 1
MAX_NONTERMINAL_PER_OWNER = 12
MAX_NONTERMINAL_PER_SPACE = 6
MAX_OWNER_CHECKPOINT_BYTES = 3 * 1024 * 1024
MAX_TERMINAL_RUNS_PER_OWNER = 1_000
MAX_PENDING_OUTBOX_FOR_START = 32
MAX_PENDING_OUTBOX_PER_OWNER = MAX_PENDING_OUTBOX_FOR_START + MAX_NONTERMINAL_PER_OWNER
MAX_OUTBOX_PAYLOAD_BYTES = 512
MAX_PROVIDER_ATTEMPTS_PER_ACTIVITY = 2
MAX_RESERVED_INPUT_TOKENS_PER_ATTEMPT = 16_384
MAX_RESERVED_OUTPUT_TOKENS_PER_ATTEMPT = 2_048
MAX_RESERVED_WALL_MS_PER_ATTEMPT = 35_000
MAX_RESERVED_INPUT_TOKENS_PER_ACTIVITY = 32_768
MAX_RESERVED_OUTPUT_TOKENS_PER_ACTIVITY = 4_096
MAX_RESERVED_WALL_MS_PER_ACTIVITY = 70_000
MAX_GRAPH_NODES_PER_ACTIVITY = 14
MAX_ACTIVE_ELAPSED_MS_PER_ACTIVITY = 120_000
ABANDONED_SEGMENT_CHARGE_MS = 45_000

_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_NONTERMINAL_SQL = "'created','running','waiting_for_learner','interrupted'"

_RUN_EXPORT_FIELDS = (
    "space_id",
    "activity_kind",
    "activity_id",
    "schema_version",
    "idempotency_key",
    "request_fingerprint",
    "label",
    "status",
    "revision",
    "current_interrupt_id",
    "execution_id",
    "provider_plan_hash",
    "policy_version",
    "terminal_code",
    "completion_basis",
    "remediation_count",
    "budget_nodes_used",
    "budget_attempts_used",
    "budget_reserved_input_tokens",
    "budget_reserved_output_tokens",
    "budget_reserved_wall_ms",
    "budget_active_elapsed_ms",
    "created_at",
    "updated_at",
    "terminal_at",
)
_CHECKPOINT_EXPORT_FIELDS = (
    "space_id",
    "activity_kind",
    "activity_id",
    "revision",
    "graph_schema_version",
    "state",
    "interrupt",
    "state_sha256",
    "created_at",
    "updated_at",
)
_ATTEMPT_EXPORT_FIELDS = (
    "space_id",
    "activity_kind",
    "activity_id",
    "attempt_id",
    "segment_id",
    "ordinal",
    "provider_id",
    "model_id",
    "api_mode",
    "status",
    "reserved_input_tokens",
    "reserved_output_tokens",
    "reserved_wall_ms",
    "actual_input_tokens",
    "actual_output_tokens",
    "actual_latency_ms",
    "reason_code",
    "reserved_at",
    "completed_at",
)
_OUTBOX_EXPORT_FIELDS = (
    "event_id",
    "space_id",
    "activity_kind",
    "activity_id",
    "event_type",
    "payload",
    "created_at",
    "delivered_at",
)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tutor_runtime_schema_version (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS tutor_activity_runs (
    owner_id TEXT NOT NULL,
    space_id TEXT NOT NULL,
    activity_kind TEXT NOT NULL CHECK (activity_kind IN ('tutor','review','practice')),
    activity_id TEXT NOT NULL,
    schema_version INTEGER NOT NULL DEFAULT 1 CHECK (schema_version = 1),
    idempotency_key TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL CHECK (status IN
        ('created','running','waiting_for_learner','interrupted',
         'completed','blocked','cancelled')),
    revision INTEGER NOT NULL DEFAULT 0 CHECK (revision >= 0),
    current_interrupt_id TEXT,
    execution_id TEXT,
    provider_plan_hash TEXT,
    policy_version TEXT NOT NULL DEFAULT 'tutor-v1',
    terminal_code TEXT,
    completion_basis TEXT,
    remediation_count INTEGER NOT NULL DEFAULT 0,
    budget_nodes_used INTEGER NOT NULL DEFAULT 0,
    budget_attempts_used INTEGER NOT NULL DEFAULT 0,
    budget_reserved_input_tokens INTEGER NOT NULL DEFAULT 0,
    budget_reserved_output_tokens INTEGER NOT NULL DEFAULT 0,
    budget_reserved_wall_ms INTEGER NOT NULL DEFAULT 0,
    budget_active_elapsed_ms INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    terminal_at TEXT,
    CHECK (completion_basis IS NULL OR completion_basis IN
           ('participation_only', 'deterministic_correct')),
    CHECK (remediation_count BETWEEN 0 AND 1),
    CHECK (budget_nodes_used >= 0 AND budget_attempts_used >= 0 AND
           budget_reserved_input_tokens >= 0 AND
           budget_reserved_output_tokens >= 0 AND
           budget_reserved_wall_ms >= 0 AND budget_active_elapsed_ms >= 0),
    PRIMARY KEY (owner_id, space_id, activity_kind, activity_id),
    UNIQUE (owner_id, space_id, activity_kind, idempotency_key)
);

CREATE TABLE IF NOT EXISTS tutor_checkpoints (
    owner_id TEXT NOT NULL,
    space_id TEXT NOT NULL,
    activity_kind TEXT NOT NULL,
    activity_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 0),
    graph_schema_version INTEGER NOT NULL DEFAULT 1 CHECK (graph_schema_version = 1),
    state_json TEXT NOT NULL,
    interrupt_json TEXT,
    state_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, space_id, activity_kind, activity_id),
    FOREIGN KEY (owner_id, space_id, activity_kind, activity_id)
      REFERENCES tutor_activity_runs(owner_id, space_id, activity_kind, activity_id)
      ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tutor_provider_attempts (
    owner_id TEXT NOT NULL,
    space_id TEXT NOT NULL,
    activity_kind TEXT NOT NULL,
    activity_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    segment_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 1),
    provider_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    api_mode TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('reserved','succeeded','failed','unknown')),
    reserved_input_tokens INTEGER NOT NULL CHECK (reserved_input_tokens >= 0),
    reserved_output_tokens INTEGER NOT NULL CHECK (reserved_output_tokens >= 0),
    reserved_wall_ms INTEGER NOT NULL CHECK (reserved_wall_ms >= 0),
    actual_input_tokens INTEGER CHECK (actual_input_tokens IS NULL OR actual_input_tokens >= 0),
    actual_output_tokens INTEGER CHECK (actual_output_tokens IS NULL OR actual_output_tokens >= 0),
    actual_latency_ms INTEGER CHECK (actual_latency_ms IS NULL OR actual_latency_ms >= 0),
    reason_code TEXT,
    reserved_at TEXT NOT NULL,
    completed_at TEXT,
    PRIMARY KEY (owner_id, space_id, activity_kind, activity_id, attempt_id),
    UNIQUE (owner_id, space_id, activity_kind, activity_id, ordinal),
    FOREIGN KEY (owner_id, space_id, activity_kind, activity_id)
      REFERENCES tutor_activity_runs(owner_id, space_id, activity_kind, activity_id)
      ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS tutor_provider_attempts_usage_window
ON tutor_provider_attempts(owner_id, status, completed_at, space_id, provider_id, model_id);

CREATE TABLE IF NOT EXISTS tutor_projection_outbox (
    event_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    space_id TEXT NOT NULL,
    activity_kind TEXT NOT NULL,
    activity_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    delivered_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_tutor_runs_scope_status_updated
  ON tutor_activity_runs(owner_id, space_id, activity_kind, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_tutor_runs_owner_status_updated
  ON tutor_activity_runs(owner_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_tutor_attempts_scope_status
  ON tutor_provider_attempts(owner_id, space_id, activity_kind, activity_id, status);
CREATE INDEX IF NOT EXISTS idx_tutor_outbox_owner_pending
  ON tutor_projection_outbox(owner_id, delivered_at, created_at);
"""


class TutorRuntimeError(RuntimeError):
    def __init__(self, message: str, *, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


class TutorRuntimeSchemaError(TutorRuntimeError):
    def __init__(self, version: int) -> None:
        super().__init__(
            f"unsupported Tutor runtime schema version: {version}",
            reason_code="tutor_runtime_schema_unsupported",
        )
        self.version = version


class TutorRuntimeBusyError(TutorRuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "Tutor runtime database remained busy",
            reason_code="tutor_runtime_busy",
        )


@dataclass(frozen=True)
class ProviderAttemptReservationV1:
    attempt_id: str
    segment_id: str
    ordinal: int
    provider_id: str
    model_id: str
    api_mode: str
    reserved_input_tokens: int
    reserved_output_tokens: int
    reserved_wall_ms: int

    def __post_init__(self) -> None:
        for field in ("attempt_id", "segment_id"):
            value = getattr(self, field)
            if not isinstance(value, str) or not _ID_RE.fullmatch(value):
                raise TutorContractError(f"{field} is invalid")
        for field in ("provider_id", "model_id", "api_mode"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value or len(value) > 256:
                raise TutorContractError(f"{field} is invalid")
        if type(self.ordinal) is not int or self.ordinal < 1:
            raise TutorContractError("ordinal must be a positive integer")
        for field in (
            "reserved_input_tokens",
            "reserved_output_tokens",
            "reserved_wall_ms",
        ):
            value = getattr(self, field)
            if type(value) is not int or value < 0:
                raise TutorContractError(f"{field} must be non-negative")
        if self.reserved_input_tokens > MAX_RESERVED_INPUT_TOKENS_PER_ATTEMPT:
            raise TutorContractError("reserved_input_tokens exceeds per-attempt budget")
        if self.reserved_output_tokens > MAX_RESERVED_OUTPUT_TOKENS_PER_ATTEMPT:
            raise TutorContractError(
                "reserved_output_tokens exceeds per-attempt budget"
            )
        if self.reserved_wall_ms > MAX_RESERVED_WALL_MS_PER_ATTEMPT:
            raise TutorContractError("reserved_wall_ms exceeds per-attempt budget")


def default_tutor_runtime_db_path() -> Path:
    return get_default_kabuqina_root().resolve() / "tutor_runtime.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _key_params(key: LearningActivityKeyV1) -> tuple[str, str, str, str]:
    return key.as_tuple()


def _non_negative_int(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise TutorContractError(f"{field} must be a non-negative integer")
    return value


class TutorRuntimeStore:
    _MAX_RETRIES = 15
    _RETRY_MIN_S = 0.020
    _RETRY_MAX_S = 0.150

    def __init__(
        self,
        db_path: Path | str | None = None,
        *,
        coordinator: LearningOperationCoordinator | None = None,
        secure_permissions: bool | None = None,
    ) -> None:
        is_default = (
            db_path is None if secure_permissions is None else secure_permissions
        )
        self.db_path = Path(db_path or default_tutor_runtime_db_path()).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        expected_coordination = self.db_path.parent / "learning_coordination.db"
        if coordinator is None:
            coordinator = LearningOperationCoordinator(
                expected_coordination, secure_permissions=is_default
            )
        elif coordinator.db_path != expected_coordination.resolve():
            raise ValueError("coordinator path does not match tutor_runtime.db path")
        self.coordinator = coordinator
        if is_default:
            secure_coordination_db(self.db_path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=1.0,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        self._setup()
        if is_default:
            secure_coordination_db(self.db_path)

    def _setup(self) -> None:
        last_error: Exception | None = None
        for attempt in range(self._MAX_RETRIES):
            try:
                self._conn.execute("PRAGMA foreign_keys=ON")
                self._conn.execute("PRAGMA secure_delete=ON")
                table = self._conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' "
                    "AND name='tutor_runtime_schema_version'"
                ).fetchone()
                if table:
                    row = self._conn.execute(
                        "SELECT version FROM tutor_runtime_schema_version WHERE singleton=1"
                    ).fetchone()
                    if row is None:
                        raise TutorRuntimeSchemaError(-1)
                    if int(row[0]) != RUNTIME_SCHEMA_VERSION:
                        raise TutorRuntimeSchemaError(int(row[0]))
                # Journal mode changes the database file, so it is deliberately
                # applied only after an existing schema version is accepted.
                self._conn.execute("PRAGMA journal_mode=WAL")
                self._conn.executescript(SCHEMA_SQL)
                self._conn.execute(
                    "INSERT OR IGNORE INTO tutor_runtime_schema_version "
                    "(singleton, version) VALUES (1, ?)",
                    (RUNTIME_SCHEMA_VERSION,),
                )
                row = self._conn.execute(
                    "SELECT version FROM tutor_runtime_schema_version WHERE singleton=1"
                ).fetchone()
                if row is None or int(row[0]) != RUNTIME_SCHEMA_VERSION:
                    raise TutorRuntimeSchemaError(-1 if row is None else int(row[0]))
                self._conn.commit()
                return
            except TutorRuntimeSchemaError:
                self._conn.rollback()
                raise
            except sqlite3.OperationalError as exc:
                self._conn.rollback()
                message = str(exc).lower()
                if (
                    "locked" in message or "busy" in message
                ) and attempt < self._MAX_RETRIES - 1:
                    last_error = exc
                    time.sleep(random.uniform(self._RETRY_MIN_S, self._RETRY_MAX_S))
                    continue
                if "locked" in message or "busy" in message:
                    raise TutorRuntimeBusyError() from exc
                raise
        if last_error is not None:
            raise TutorRuntimeBusyError() from last_error
        raise TutorRuntimeBusyError()

    def close(self) -> None:
        with self._lock:
            if self._conn is None:
                return
            try:
                self._conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            except Exception:
                pass
            self._conn.close()
            self._conn = None

    def connection_settings(self) -> dict[str, Any]:
        with self._lock:
            return {
                "journal_mode": self._conn.execute("PRAGMA journal_mode")
                .fetchone()[0]
                .lower(),
                "secure_delete": self._conn.execute("PRAGMA secure_delete").fetchone()[
                    0
                ],
            }

    def table_names(self) -> set[str]:
        with self._lock:
            return {
                row[0]
                for row in self._conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }

    def _sqlite_write(self, function: Callable[[sqlite3.Connection], T]) -> T:
        last_error: Exception | None = None
        for attempt in range(self._MAX_RETRIES):
            try:
                with self._lock:
                    self._conn.execute("BEGIN IMMEDIATE")
                    try:
                        result = function(self._conn)
                        self._conn.commit()
                    except BaseException:
                        self._conn.rollback()
                        raise
                return result
            except sqlite3.OperationalError as exc:
                message = str(exc).lower()
                if (
                    "locked" in message or "busy" in message
                ) and attempt < self._MAX_RETRIES - 1:
                    last_error = exc
                    time.sleep(random.uniform(self._RETRY_MIN_S, self._RETRY_MAX_S))
                    continue
                if "locked" in message or "busy" in message:
                    raise TutorRuntimeBusyError() from exc
                raise
        if last_error is not None:
            raise TutorRuntimeBusyError() from last_error
        raise TutorRuntimeBusyError()

    def _write(
        self,
        owner_id: str,
        space_id: str,
        function: Callable[[sqlite3.Connection], T],
        *,
        operation_lease: OperationLease | None = None,
        coordination_guard: LearningOperationGuard | None = None,
    ) -> T:
        if coordination_guard is not None:
            if (
                coordination_guard.owner_id != owner_id
                or coordination_guard.space_id not in {"", space_id}
                or coordination_guard.mode != "write"
            ):
                raise ValueError(
                    "coordination guard scope does not match runtime write"
                )
            return self._sqlite_write(function)
        with self.coordinator.begin_write(
            owner_id, space_id, operation_lease=operation_lease
        ):
            return self._sqlite_write(function)

    def _read(
        self,
        owner_id: str,
        space_id: str,
        function: Callable[[sqlite3.Connection], T],
        *,
        operation_lease: OperationLease | None = None,
        coordination_guard: LearningOperationGuard | None = None,
    ) -> T:
        if coordination_guard is not None and (
            coordination_guard.owner_id != owner_id
            or coordination_guard.space_id not in {"", space_id}
            or coordination_guard.mode not in {"read", "write"}
        ):
            raise ValueError("coordination guard scope does not match runtime read")
        guard = coordination_guard or self.coordinator.begin_read(
            owner_id, space_id, operation_lease=operation_lease
        )
        try:
            with self._lock:
                self._conn.execute("BEGIN")
                try:
                    result = function(self._conn)
                    self._conn.commit()
                    return result
                except BaseException:
                    self._conn.rollback()
                    raise
        finally:
            if coordination_guard is None:
                guard.close()

    @staticmethod
    def _checkpoint_values(
        checkpoint: LearningCheckpointV1,
    ) -> tuple[str, str | None, str]:
        state = validate_checkpoint_state(checkpoint.state)
        state_bytes = canonical_json_bytes(state)
        if len(state_bytes) > MAX_CHECKPOINT_BYTES:
            raise TutorContractError(
                "checkpoint exceeds 256 KiB", reason_code="checkpoint_too_large"
            )
        pending = state.get("pending_interrupt")
        interrupt_json = None
        if pending is not None:
            if not isinstance(pending, Mapping):
                raise TutorContractError("pending_interrupt must be an object")
            interrupt_json = canonical_json_bytes(pending).decode("utf-8")
        return (
            state_bytes.decode("utf-8"),
            interrupt_json,
            hashlib.sha256(state_bytes).hexdigest(),
        )

    @staticmethod
    def _current_interrupt_id(state: Mapping[str, Any]) -> str | None:
        pending = state.get("pending_interrupt")
        if pending is None:
            return None
        if not isinstance(pending, Mapping):
            raise TutorContractError("pending_interrupt must be an object")
        interrupt_id = pending.get("interrupt_id")
        if not isinstance(interrupt_id, str) or not _ID_RE.fullmatch(interrupt_id):
            raise TutorContractError("pending interrupt_id is invalid")
        return interrupt_id

    @staticmethod
    def _validate_pending_interrupt(
        state: Mapping[str, Any],
        key: LearningActivityKeyV1,
        checkpoint_revision: int,
        *,
        required: bool,
    ) -> LearningInterruptV1 | None:
        pending = state.get("pending_interrupt")
        if pending is None:
            if required:
                raise TutorContractError(
                    "waiting checkpoint requires pending_interrupt"
                )
            return None
        if not required:
            raise TutorContractError(
                "pending_interrupt is only allowed while waiting_for_learner"
            )
        if not isinstance(pending, Mapping):
            raise TutorContractError("pending_interrupt must be an object")
        allowed = {
            "schema_version",
            "interrupt_id",
            "kind",
            "owner_id",
            "space_id",
            "activity_kind",
            "activity_id",
            "checkpoint_revision",
            "prompt",
            "expected_input",
            "created_at",
        }
        unknown = set(pending) - allowed
        if unknown:
            raise TutorContractError(
                f"pending_interrupt contains unknown field: {sorted(unknown)[0]}"
            )
        if pending.get("schema_version") != 1:
            raise TutorContractError("unsupported pending_interrupt schema_version")
        interrupt_id = pending.get("interrupt_id")
        if not isinstance(interrupt_id, str) or not interrupt_id.startswith("lint_"):
            raise TutorContractError("learner interrupt_id must use lint_ namespace")
        if (
            pending.get("owner_id") != key.owner_id
            or pending.get("space_id") != key.space_id
            or pending.get("activity_kind") != key.activity_kind
            or pending.get("activity_id") != key.activity_id
        ):
            raise TutorContractError("pending_interrupt identity mismatch")
        if pending.get("checkpoint_revision") != checkpoint_revision:
            raise TutorContractError("pending_interrupt revision mismatch")
        prompt = pending.get("prompt")
        created_at = pending.get("created_at")
        if (
            not isinstance(prompt, dict)
            or not isinstance(created_at, str)
            or not created_at
        ):
            raise TutorContractError("pending_interrupt prompt/created_at is invalid")
        return LearningInterruptV1(
            interrupt_id=interrupt_id,
            key=key,
            checkpoint_revision=checkpoint_revision,
            prompt=copy.deepcopy(prompt),
            expected_input=pending.get("expected_input"),
            created_at=created_at,
            kind=pending.get("kind"),
        )

    @staticmethod
    def _fetch_checkpoint(
        connection: sqlite3.Connection, key: LearningActivityKeyV1
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM tutor_checkpoints WHERE owner_id=? AND space_id=? "
            "AND activity_kind=? AND activity_id=?",
            _key_params(key),
        ).fetchone()

    @staticmethod
    def _fetch_run(
        connection: sqlite3.Connection, key: LearningActivityKeyV1
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM tutor_activity_runs WHERE owner_id=? AND space_id=? "
            "AND activity_kind=? AND activity_id=?",
            _key_params(key),
        ).fetchone()

    @classmethod
    def _record(
        cls, run: sqlite3.Row, checkpoint_row: sqlite3.Row | None
    ) -> LearningActivityRecordV1:
        key = LearningActivityKeyV1(
            run["owner_id"], run["space_id"], run["activity_kind"], run["activity_id"]
        )
        checkpoint = None
        goal = ""
        input_refs: tuple[dict[str, Any], ...] = ()
        if checkpoint_row is not None:
            state = json.loads(checkpoint_row["state_json"])
            goal_value = state.get("goal")
            if isinstance(goal_value, str):
                goal = goal_value
            refs = state.get("input_refs")
            if isinstance(refs, list) and all(isinstance(item, dict) for item in refs):
                input_refs = tuple(copy.deepcopy(refs))
            checkpoint = LearningCheckpointV1(
                key=key,
                revision=checkpoint_row["revision"],
                status=run["status"],
                state=state,
            )
        return LearningActivityRecordV1(
            key=key,
            status=run["status"],
            revision=run["revision"],
            idempotency_key=run["idempotency_key"],
            request_fingerprint=run["request_fingerprint"],
            goal=goal,
            input_refs=input_refs,
            checkpoint=checkpoint,
            created_at=run["created_at"],
            updated_at=run["updated_at"],
        )

    def _record_by_key_tx(
        self, connection: sqlite3.Connection, key: LearningActivityKeyV1
    ) -> LearningActivityRecordV1 | None:
        run = self._fetch_run(connection, key)
        if run is None:
            return None
        return self._record(run, self._fetch_checkpoint(connection, key))

    @staticmethod
    def _check_checkpoint_aggregate(
        connection: sqlite3.Connection,
        owner_id: str,
        state_json: str,
        *,
        excluding_key: LearningActivityKeyV1 | None = None,
    ) -> None:
        sql = (
            "SELECT COALESCE(SUM(LENGTH(CAST(state_json AS BLOB))),0) "
            "FROM tutor_checkpoints WHERE owner_id=?"
        )
        params: list[Any] = [owner_id]
        if excluding_key is not None:
            sql += " AND NOT (space_id=? AND activity_kind=? AND activity_id=?)"
            params.extend(
                [
                    excluding_key.space_id,
                    excluding_key.activity_kind,
                    excluding_key.activity_id,
                ]
            )
        current = int(connection.execute(sql, params).fetchone()[0])
        if current + len(state_json.encode("utf-8")) > MAX_OWNER_CHECKPOINT_BYTES:
            raise TutorConflictError("checkpoint_owner_quota")

    def create(
        self,
        request: LearningActivityStartV1,
        checkpoint: LearningCheckpointV1,
        *,
        label: str = "",
        provider_plan_hash: str | None = None,
        operation_lease: OperationLease | None = None,
    ) -> tuple[LearningActivityRecordV1, bool]:
        if checkpoint.key != request.key:
            raise TutorContractError("checkpoint key does not match start request")
        if checkpoint.revision != 0 or checkpoint.status != "created":
            raise TutorContractError("initial checkpoint must be created at revision 0")
        if not isinstance(label, str) or len(label) > 300:
            raise TutorContractError("label exceeds 300 characters")
        if provider_plan_hash is not None and (
            not isinstance(provider_plan_hash, str)
            or not _SHA256_RE.fullmatch(provider_plan_hash)
        ):
            raise TutorContractError("provider_plan_hash is invalid")
        self._validate_pending_interrupt(
            checkpoint.state, request.key, 0, required=False
        )
        state_json, interrupt_json, state_sha256 = self._checkpoint_values(checkpoint)

        def _op(connection: sqlite3.Connection):
            existing = connection.execute(
                "SELECT * FROM tutor_activity_runs WHERE owner_id=? AND space_id=? "
                "AND activity_kind=? AND idempotency_key=?",
                request.idempotency_namespace,
            ).fetchone()
            if existing is not None:
                if existing["request_fingerprint"] != request.request_fingerprint:
                    raise TutorConflictError("idempotency_payload_mismatch")
                existing_key = LearningActivityKeyV1(
                    existing["owner_id"],
                    existing["space_id"],
                    existing["activity_kind"],
                    existing["activity_id"],
                )
                return self._record_by_key_tx(connection, existing_key), False
            owner_count = connection.execute(
                f"SELECT COUNT(*) FROM tutor_activity_runs WHERE owner_id=? "
                f"AND status IN ({_NONTERMINAL_SQL})",
                (request.key.owner_id,),
            ).fetchone()[0]
            if owner_count >= MAX_NONTERMINAL_PER_OWNER:
                raise TutorConflictError("nonterminal_owner_quota")
            space_count = connection.execute(
                f"SELECT COUNT(*) FROM tutor_activity_runs WHERE owner_id=? "
                f"AND space_id=? AND status IN ({_NONTERMINAL_SQL})",
                (request.key.owner_id, request.key.space_id),
            ).fetchone()[0]
            if space_count >= MAX_NONTERMINAL_PER_SPACE:
                raise TutorConflictError("nonterminal_space_quota")
            pending = connection.execute(
                "SELECT COUNT(*) FROM tutor_projection_outbox "
                "WHERE owner_id=? AND delivered_at IS NULL",
                (request.key.owner_id,),
            ).fetchone()[0]
            if pending >= MAX_PENDING_OUTBOX_FOR_START:
                raise TutorConflictError("pending_outbox_quota")
            self._check_checkpoint_aggregate(
                connection, request.key.owner_id, state_json
            )
            now = _now()
            connection.execute(
                """
                INSERT INTO tutor_activity_runs
                    (owner_id,space_id,activity_kind,activity_id,schema_version,
                     idempotency_key,request_fingerprint,label,status,revision,
                     current_interrupt_id,provider_plan_hash,created_at,updated_at)
                VALUES (?,?,?,?,1,?,?,?,'created',0,?,?,?,?)
                """,
                (
                    *request.key.as_tuple(),
                    request.idempotency_key,
                    request.request_fingerprint,
                    label or request.goal[:120],
                    self._current_interrupt_id(checkpoint.state),
                    provider_plan_hash,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO tutor_checkpoints
                    (owner_id,space_id,activity_kind,activity_id,revision,
                     graph_schema_version,state_json,interrupt_json,state_sha256,
                     created_at,updated_at)
                VALUES (?,?,?,?,0,1,?,?,?,?,?)
                """,
                (
                    *request.key.as_tuple(),
                    state_json,
                    interrupt_json,
                    state_sha256,
                    now,
                    now,
                ),
            )
            return self._record_by_key_tx(connection, request.key), True

        try:
            return self._write(
                request.key.owner_id,
                request.key.space_id,
                _op,
                operation_lease=operation_lease,
            )
        except sqlite3.IntegrityError as exc:
            raise TutorConflictError("activity_id_conflict") from exc

    def load(
        self,
        key: LearningActivityKeyV1,
        *,
        operation_lease: OperationLease | None = None,
        coordination_guard: LearningOperationGuard | None = None,
    ) -> LearningActivityRecordV1 | None:
        return self._read(
            key.owner_id,
            key.space_id,
            lambda connection: self._record_by_key_tx(connection, key),
            operation_lease=operation_lease,
            coordination_guard=coordination_guard,
        )

    def load_idempotent(
        self,
        request: LearningActivityStartV1,
        *,
        operation_lease: OperationLease | None = None,
    ) -> LearningActivityRecordV1 | None:
        """Return an exact start replay before resolving ephemeral dependencies."""

        def _op(connection: sqlite3.Connection):
            existing = connection.execute(
                "SELECT * FROM tutor_activity_runs WHERE owner_id=? AND space_id=? "
                "AND activity_kind=? AND idempotency_key=?",
                request.idempotency_namespace,
            ).fetchone()
            if existing is None:
                return None
            if existing["request_fingerprint"] != request.request_fingerprint:
                raise TutorConflictError("idempotency_payload_mismatch")
            key = LearningActivityKeyV1(
                existing["owner_id"],
                existing["space_id"],
                existing["activity_kind"],
                existing["activity_id"],
            )
            return self._record_by_key_tx(connection, key)

        return self._read(
            request.key.owner_id,
            request.key.space_id,
            _op,
            operation_lease=operation_lease,
        )

    def load_checkpoint(
        self,
        key: LearningActivityKeyV1,
        *,
        operation_lease: OperationLease | None = None,
    ) -> LearningCheckpointV1 | None:
        record = self.load(key, operation_lease=operation_lease)
        return None if record is None else record.checkpoint

    def list(
        self,
        owner_id: str,
        space_id: str,
        activity_kind: str,
        *,
        status: str | None = None,
        limit: int = 100,
        operation_lease: OperationLease | None = None,
    ) -> list[LearningActivityRecordV1]:
        if activity_kind not in ACTIVITY_KINDS:
            raise TutorContractError("activity_kind is invalid")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise TutorContractError("limit must be within 1..100")

        def _op(connection: sqlite3.Connection):
            sql = (
                "SELECT * FROM tutor_activity_runs WHERE owner_id=? AND space_id=? "
                "AND activity_kind=?"
            )
            params: list[Any] = [owner_id, space_id, activity_kind]
            if status is not None:
                sql += " AND status=?"
                params.append(status)
            sql += " ORDER BY updated_at DESC, activity_id DESC LIMIT ?"
            params.append(limit)
            records = []
            for run in connection.execute(sql, params).fetchall():
                key = LearningActivityKeyV1(
                    run["owner_id"],
                    run["space_id"],
                    run["activity_kind"],
                    run["activity_id"],
                )
                records.append(
                    self._record(run, self._fetch_checkpoint(connection, key))
                )
            return records

        return self._read(owner_id, space_id, _op, operation_lease=operation_lease)

    def _require_mutable_run(
        self,
        connection: sqlite3.Connection,
        key: LearningActivityKeyV1,
        expected_revision: int,
    ) -> sqlite3.Row:
        run = self._fetch_run(connection, key)
        if run is None:
            raise TutorConflictError("activity_not_found")
        if run["status"] in TERMINAL_ACTIVITY_STATUSES:
            raise TutorConflictError("terminal_immutable")
        if run["revision"] != expected_revision:
            raise TutorConflictError("stale_revision")
        return run

    @staticmethod
    def _budget_from_state(
        state: Mapping[str, Any], run: sqlite3.Row
    ) -> dict[str, int]:
        raw = state.get("budget")
        if not isinstance(raw, Mapping):
            raise TutorContractError("checkpoint budget must be an object")
        fields = (
            "nodes_used",
            "attempts_used",
            "reserved_input_tokens",
            "reserved_output_tokens",
            "reserved_wall_ms",
            "active_elapsed_ms",
        )
        budget = {
            field: _non_negative_int(raw.get(field), f"budget.{field}")
            for field in fields
        }
        if budget["nodes_used"] > MAX_GRAPH_NODES_PER_ACTIVITY:
            raise TutorConflictError("budget_exhausted")
        if budget["attempts_used"] > MAX_PROVIDER_ATTEMPTS_PER_ACTIVITY:
            raise TutorConflictError("budget_exhausted")
        if budget["reserved_input_tokens"] > MAX_RESERVED_INPUT_TOKENS_PER_ACTIVITY:
            raise TutorConflictError("budget_exhausted")
        if budget["reserved_output_tokens"] > MAX_RESERVED_OUTPUT_TOKENS_PER_ACTIVITY:
            raise TutorConflictError("budget_exhausted")
        if budget["reserved_wall_ms"] > MAX_RESERVED_WALL_MS_PER_ACTIVITY:
            raise TutorConflictError("budget_exhausted")
        if budget["active_elapsed_ms"] > MAX_ACTIVE_ELAPSED_MS_PER_ACTIVITY:
            raise TutorConflictError("budget_exhausted")
        persisted = {
            "nodes_used": int(run["budget_nodes_used"]),
            "attempts_used": int(run["budget_attempts_used"]),
            "reserved_input_tokens": int(run["budget_reserved_input_tokens"]),
            "reserved_output_tokens": int(run["budget_reserved_output_tokens"]),
            "reserved_wall_ms": int(run["budget_reserved_wall_ms"]),
            "active_elapsed_ms": int(run["budget_active_elapsed_ms"]),
        }
        for field in (
            "attempts_used",
            "reserved_input_tokens",
            "reserved_output_tokens",
            "reserved_wall_ms",
        ):
            if budget[field] != persisted[field]:
                raise TutorConflictError("budget_state_mismatch")
        for field in ("nodes_used", "active_elapsed_ms"):
            if budget[field] < persisted[field]:
                raise TutorConflictError("budget_counter_regression")
        return budget

    def save(
        self,
        checkpoint: LearningCheckpointV1,
        *,
        expected_revision: int,
        operation_lease: OperationLease | None = None,
    ) -> LearningActivityRecordV1:
        if checkpoint.revision != expected_revision:
            raise TutorConflictError("stale_revision")
        if checkpoint.status in TERMINAL_ACTIVITY_STATUSES:
            raise TutorConflictError("terminal_requires_commit")
        self._validate_pending_interrupt(
            checkpoint.state,
            checkpoint.key,
            expected_revision + 1,
            required=checkpoint.status == "waiting_for_learner",
        )
        state_json, interrupt_json, state_sha256 = self._checkpoint_values(checkpoint)

        def _op(connection: sqlite3.Connection):
            run = self._require_mutable_run(
                connection, checkpoint.key, expected_revision
            )
            status_unchanged_checkpoint = checkpoint.status == run[
                "status"
            ] and checkpoint.status in {"running", "waiting_for_learner"}
            allowed_graph_transition = run[
                "status"
            ] == "running" and checkpoint.status in {
                "waiting_for_learner",
                "interrupted",
            }
            if not status_unchanged_checkpoint and not allowed_graph_transition:
                raise TutorConflictError("invalid_transition")
            existing_checkpoint = self._fetch_checkpoint(connection, checkpoint.key)
            if (
                existing_checkpoint is None
                or existing_checkpoint["revision"] != expected_revision
            ):
                raise TutorConflictError("stale_revision")
            self._check_checkpoint_aggregate(
                connection,
                checkpoint.key.owner_id,
                state_json,
                excluding_key=checkpoint.key,
            )
            revision = expected_revision + 1
            now = _now()
            budget = self._budget_from_state(checkpoint.state, run)
            remediation_count = checkpoint.state.get(
                "remediation_count", run["remediation_count"]
            )
            if type(remediation_count) is not int or remediation_count not in {0, 1}:
                raise TutorContractError("remediation_count must be 0 or 1")
            cursor = connection.execute(
                """
                UPDATE tutor_activity_runs
                SET status=?,revision=?,current_interrupt_id=?,
                    execution_id=CASE WHEN ?='running' THEN execution_id ELSE NULL END,
                    remediation_count=?,budget_nodes_used=?,
                    budget_attempts_used=?,budget_reserved_input_tokens=?,
                    budget_reserved_output_tokens=?,budget_reserved_wall_ms=?,
                    budget_active_elapsed_ms=?,
                    updated_at=?
                WHERE owner_id=? AND space_id=? AND activity_kind=? AND activity_id=?
                  AND revision=?
                """,
                (
                    checkpoint.status,
                    revision,
                    self._current_interrupt_id(checkpoint.state),
                    checkpoint.status,
                    remediation_count,
                    budget["nodes_used"],
                    budget["attempts_used"],
                    budget["reserved_input_tokens"],
                    budget["reserved_output_tokens"],
                    budget["reserved_wall_ms"],
                    budget["active_elapsed_ms"],
                    now,
                    *checkpoint.key.as_tuple(),
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise TutorConflictError("stale_revision")
            cursor = connection.execute(
                """
                UPDATE tutor_checkpoints
                SET revision=?,state_json=?,interrupt_json=?,state_sha256=?,updated_at=?
                WHERE owner_id=? AND space_id=? AND activity_kind=? AND activity_id=?
                  AND revision=?
                """,
                (
                    revision,
                    state_json,
                    interrupt_json,
                    state_sha256,
                    now,
                    *checkpoint.key.as_tuple(),
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise TutorConflictError("stale_revision")
            return self._record_by_key_tx(connection, checkpoint.key)

        return self._write(
            checkpoint.key.owner_id,
            checkpoint.key.space_id,
            _op,
            operation_lease=operation_lease,
        )

    def save_checkpoint(
        self,
        checkpoint: LearningCheckpointV1,
        *,
        expected_revision: int,
        operation_lease: OperationLease | None = None,
    ) -> LearningCheckpointV1:
        record = self.save(
            checkpoint,
            expected_revision=expected_revision,
            operation_lease=operation_lease,
        )
        return record.checkpoint

    def claim_execution(
        self,
        key: LearningActivityKeyV1,
        *,
        expected_revision: int,
        execution_id: str,
        operation_lease: OperationLease | None = None,
    ) -> LearningActivityRecordV1:
        if not isinstance(execution_id, str) or not _ID_RE.fullmatch(execution_id):
            raise TutorContractError("execution_id is invalid")

        def _op(connection: sqlite3.Connection):
            run = self._require_mutable_run(connection, key, expected_revision)
            if run["status"] == "waiting_for_learner":
                raise TutorConflictError("interrupt_answer_required")
            if run["status"] not in {"created", "interrupted"}:
                raise TutorConflictError("invalid_transition")
            checkpoint = self._fetch_checkpoint(connection, key)
            if checkpoint is None or checkpoint["revision"] != expected_revision:
                raise TutorConflictError("stale_revision")
            revision = expected_revision + 1
            now = _now()
            cursor = connection.execute(
                """
                UPDATE tutor_activity_runs SET status='running',revision=?,
                    execution_id=?,current_interrupt_id=NULL,updated_at=?
                WHERE owner_id=? AND space_id=? AND activity_kind=? AND activity_id=?
                  AND revision=?
                """,
                (revision, execution_id, now, *key.as_tuple(), expected_revision),
            )
            if cursor.rowcount != 1:
                raise TutorConflictError("stale_revision")
            connection.execute(
                "UPDATE tutor_checkpoints SET revision=?,interrupt_json=NULL,updated_at=? "
                "WHERE owner_id=? AND space_id=? AND activity_kind=? AND activity_id=? "
                "AND revision=?",
                (revision, now, *key.as_tuple(), expected_revision),
            )
            return self._record_by_key_tx(connection, key)

        return self._write(
            key.owner_id, key.space_id, _op, operation_lease=operation_lease
        )

    def claim_answer(
        self,
        key: LearningActivityKeyV1,
        *,
        expected_revision: int,
        execution_id: str,
        interrupt_id: str,
        answer: Mapping[str, Any],
        operation_lease: OperationLease | None = None,
    ) -> LearningActivityRecordV1:
        if not isinstance(execution_id, str) or not _ID_RE.fullmatch(execution_id):
            raise TutorContractError("execution_id is invalid")
        if not isinstance(answer, Mapping):
            raise TutorContractError("answer must be an object")
        normalized_resume = validate_resume_request(
            {
                "schema_version": 1,
                "space_id": key.space_id,
                "expected_revision": expected_revision,
                "mode": "answer",
                "interrupt_id": interrupt_id,
                "answer": dict(answer),
            }
        )

        def _op(connection: sqlite3.Connection):
            run = self._require_mutable_run(connection, key, expected_revision)
            if run["status"] != "waiting_for_learner":
                raise TutorConflictError("answer_requires_waiting")
            if run["current_interrupt_id"] != interrupt_id:
                raise TutorConflictError("interrupt_mismatch")
            checkpoint_row = self._fetch_checkpoint(connection, key)
            if (
                checkpoint_row is None
                or checkpoint_row["revision"] != expected_revision
            ):
                raise TutorConflictError("stale_revision")
            state = json.loads(checkpoint_row["state_json"])
            interrupt = self._validate_pending_interrupt(
                state, key, expected_revision, required=True
            )
            if interrupt is None or interrupt.interrupt_id != interrupt_id:
                raise TutorConflictError("interrupt_mismatch")
            state.pop("pending_interrupt", None)
            state["learner_answer"] = copy.deepcopy(normalized_resume.answer)
            state["learner_answer_checkpoint_revision"] = expected_revision
            claimed = LearningCheckpointV1(
                key=key,
                revision=expected_revision,
                status="running",
                state=state,
            )
            state_json, _, state_sha256 = self._checkpoint_values(claimed)
            self._check_checkpoint_aggregate(
                connection, key.owner_id, state_json, excluding_key=key
            )
            revision = expected_revision + 1
            now = _now()
            cursor = connection.execute(
                "UPDATE tutor_activity_runs SET status='running',revision=?,"
                "current_interrupt_id=NULL,execution_id=?,updated_at=? "
                "WHERE owner_id=? AND space_id=? AND activity_kind=? AND activity_id=? "
                "AND revision=? AND status='waiting_for_learner' "
                "AND current_interrupt_id=?",
                (
                    revision,
                    execution_id,
                    now,
                    *key.as_tuple(),
                    expected_revision,
                    interrupt_id,
                ),
            )
            if cursor.rowcount != 1:
                raise TutorConflictError("stale_revision")
            cursor = connection.execute(
                "UPDATE tutor_checkpoints SET revision=?,state_json=?,"
                "interrupt_json=NULL,state_sha256=?,updated_at=? "
                "WHERE owner_id=? AND space_id=? AND activity_kind=? AND activity_id=? "
                "AND revision=?",
                (
                    revision,
                    state_json,
                    state_sha256,
                    now,
                    *key.as_tuple(),
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise TutorConflictError("stale_revision")
            return self._record_by_key_tx(connection, key)

        return self._write(
            key.owner_id, key.space_id, _op, operation_lease=operation_lease
        )

    def mark_interrupted(
        self,
        key: LearningActivityKeyV1,
        *,
        expected_revision: int,
        operation_lease: OperationLease | None = None,
    ) -> LearningActivityRecordV1:
        def _op(connection: sqlite3.Connection):
            run = self._require_mutable_run(connection, key, expected_revision)
            if not is_allowed_activity_transition(run["status"], "interrupted"):
                raise TutorConflictError("invalid_transition")
            revision = expected_revision + 1
            now = _now()
            connection.execute(
                "UPDATE tutor_activity_runs SET status='interrupted',revision=?,"
                "execution_id=NULL,current_interrupt_id=NULL,updated_at=? "
                "WHERE owner_id=? AND space_id=? AND activity_kind=? AND activity_id=? "
                "AND revision=?",
                (revision, now, *key.as_tuple(), expected_revision),
            )
            connection.execute(
                "UPDATE tutor_checkpoints SET revision=?,updated_at=? "
                "WHERE owner_id=? AND space_id=? AND activity_kind=? AND activity_id=? "
                "AND revision=?",
                (revision, now, *key.as_tuple(), expected_revision),
            )
            connection.execute(
                "UPDATE tutor_provider_attempts SET status='unknown',completed_at=? "
                "WHERE owner_id=? AND space_id=? AND activity_kind=? AND activity_id=? "
                "AND status='reserved'",
                (now, *key.as_tuple()),
            )
            return self._record_by_key_tx(connection, key)

        return self._write(
            key.owner_id, key.space_id, _op, operation_lease=operation_lease
        )

    @staticmethod
    def _update_checkpoint_budget(
        state: dict[str, Any], reservation: ProviderAttemptReservationV1
    ) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        budget = updated.setdefault("budget", {})
        if not isinstance(budget, dict):
            raise TutorContractError("checkpoint budget must be an object")
        increments = {
            "attempts_used": 1,
            "reserved_input_tokens": reservation.reserved_input_tokens,
            "reserved_output_tokens": reservation.reserved_output_tokens,
            "reserved_wall_ms": reservation.reserved_wall_ms,
        }
        for field, increment in increments.items():
            current = budget.get(field, 0)
            if type(current) is not int or current < 0:
                raise TutorContractError(f"checkpoint budget {field} is invalid")
            budget[field] = current + increment
        return validate_checkpoint_state(updated)

    def reserve_provider_attempt(
        self,
        key: LearningActivityKeyV1,
        *,
        expected_revision: int,
        reservation: ProviderAttemptReservationV1,
        operation_lease: OperationLease | None = None,
    ) -> LearningActivityRecordV1:
        def _op(connection: sqlite3.Connection):
            run = self._require_mutable_run(connection, key, expected_revision)
            if run["status"] != "running":
                raise TutorConflictError("attempt_requires_running")
            count = connection.execute(
                "SELECT COUNT(*) FROM tutor_provider_attempts WHERE owner_id=? "
                "AND space_id=? AND activity_kind=? AND activity_id=?",
                key.as_tuple(),
            ).fetchone()[0]
            if count >= MAX_PROVIDER_ATTEMPTS_PER_ACTIVITY:
                raise TutorConflictError("provider_attempt_exhausted")
            if reservation.ordinal != count + 1:
                raise TutorConflictError("provider_attempt_ordinal_mismatch")
            if connection.execute(
                "SELECT 1 FROM tutor_provider_attempts WHERE owner_id=? "
                "AND space_id=? AND activity_kind=? AND activity_id=? "
                "AND segment_id=? LIMIT 1",
                (*key.as_tuple(), reservation.segment_id),
            ).fetchone():
                raise TutorConflictError("provider_attempt_segment_conflict")
            if (
                int(run["budget_reserved_input_tokens"])
                + reservation.reserved_input_tokens
                > MAX_RESERVED_INPUT_TOKENS_PER_ACTIVITY
                or int(run["budget_reserved_output_tokens"])
                + reservation.reserved_output_tokens
                > MAX_RESERVED_OUTPUT_TOKENS_PER_ACTIVITY
                or int(run["budget_reserved_wall_ms"]) + reservation.reserved_wall_ms
                > MAX_RESERVED_WALL_MS_PER_ACTIVITY
            ):
                raise TutorConflictError("budget_exhausted")
            checkpoint_row = self._fetch_checkpoint(connection, key)
            if (
                checkpoint_row is None
                or checkpoint_row["revision"] != expected_revision
            ):
                raise TutorConflictError("stale_revision")
            state = self._update_checkpoint_budget(
                json.loads(checkpoint_row["state_json"]), reservation
            )
            next_checkpoint = LearningCheckpointV1(
                key=key,
                revision=expected_revision,
                status="running",
                state=state,
            )
            state_json, interrupt_json, state_sha256 = self._checkpoint_values(
                next_checkpoint
            )
            self._check_checkpoint_aggregate(
                connection, key.owner_id, state_json, excluding_key=key
            )
            now = _now()
            connection.execute(
                """
                INSERT INTO tutor_provider_attempts
                    (owner_id,space_id,activity_kind,activity_id,attempt_id,
                     segment_id,ordinal,provider_id,model_id,api_mode,status,
                     reserved_input_tokens,reserved_output_tokens,reserved_wall_ms,
                     reserved_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,'reserved',?,?,?,?)
                """,
                (
                    *key.as_tuple(),
                    reservation.attempt_id,
                    reservation.segment_id,
                    reservation.ordinal,
                    reservation.provider_id,
                    reservation.model_id,
                    reservation.api_mode,
                    reservation.reserved_input_tokens,
                    reservation.reserved_output_tokens,
                    reservation.reserved_wall_ms,
                    now,
                ),
            )
            revision = expected_revision + 1
            cursor = connection.execute(
                """
                UPDATE tutor_activity_runs SET revision=?,updated_at=?,
                    budget_attempts_used=budget_attempts_used+1,
                    budget_reserved_input_tokens=budget_reserved_input_tokens+?,
                    budget_reserved_output_tokens=budget_reserved_output_tokens+?,
                    budget_reserved_wall_ms=budget_reserved_wall_ms+?
                WHERE owner_id=? AND space_id=? AND activity_kind=? AND activity_id=?
                  AND revision=?
                """,
                (
                    revision,
                    now,
                    reservation.reserved_input_tokens,
                    reservation.reserved_output_tokens,
                    reservation.reserved_wall_ms,
                    *key.as_tuple(),
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise TutorConflictError("stale_revision")
            connection.execute(
                """
                UPDATE tutor_checkpoints SET revision=?,state_json=?,interrupt_json=?,
                    state_sha256=?,updated_at=?
                WHERE owner_id=? AND space_id=? AND activity_kind=? AND activity_id=?
                  AND revision=?
                """,
                (
                    revision,
                    state_json,
                    interrupt_json,
                    state_sha256,
                    now,
                    *key.as_tuple(),
                    expected_revision,
                ),
            )
            return self._record_by_key_tx(connection, key)

        try:
            return self._write(
                key.owner_id, key.space_id, _op, operation_lease=operation_lease
            )
        except sqlite3.IntegrityError as exc:
            raise TutorConflictError("provider_attempt_conflict") from exc

    def settle_provider_attempt(
        self,
        key: LearningActivityKeyV1,
        *,
        attempt_id: str,
        expected_revision: int,
        status: str,
        actual_input_tokens: int | None = None,
        actual_output_tokens: int | None = None,
        actual_latency_ms: int | None = None,
        reason_code: str | None = None,
        operation_lease: OperationLease | None = None,
    ) -> LearningActivityRecordV1:
        if status not in {"succeeded", "failed", "unknown"}:
            raise TutorContractError("attempt settlement status is invalid")
        if not isinstance(attempt_id, str) or not _ID_RE.fullmatch(attempt_id):
            raise TutorContractError("attempt_id is invalid")
        for field, value in (
            ("actual_input_tokens", actual_input_tokens),
            ("actual_output_tokens", actual_output_tokens),
            ("actual_latency_ms", actual_latency_ms),
        ):
            if value is not None:
                _non_negative_int(value, field)
        if reason_code is not None and (
            not isinstance(reason_code, str) or len(reason_code) > 128
        ):
            raise TutorContractError("reason_code is invalid")

        def _op(connection: sqlite3.Connection):
            self._require_mutable_run(connection, key, expected_revision)
            checkpoint = self._fetch_checkpoint(connection, key)
            if checkpoint is None or checkpoint["revision"] != expected_revision:
                raise TutorConflictError("stale_revision")
            now = _now()
            cursor = connection.execute(
                """
                UPDATE tutor_provider_attempts
                SET status=?,actual_input_tokens=?,actual_output_tokens=?,
                    actual_latency_ms=?,reason_code=?,completed_at=?
                WHERE owner_id=? AND space_id=? AND activity_kind=? AND activity_id=?
                  AND attempt_id=? AND status='reserved'
                """,
                (
                    status,
                    actual_input_tokens,
                    actual_output_tokens,
                    actual_latency_ms,
                    reason_code,
                    now,
                    *key.as_tuple(),
                    attempt_id,
                ),
            )
            if cursor.rowcount != 1:
                raise TutorConflictError("attempt_not_reserved")
            revision = expected_revision + 1
            connection.execute(
                "UPDATE tutor_activity_runs SET revision=?,updated_at=? "
                "WHERE owner_id=? AND space_id=? AND activity_kind=? AND activity_id=? "
                "AND revision=?",
                (revision, now, *key.as_tuple(), expected_revision),
            )
            connection.execute(
                "UPDATE tutor_checkpoints SET revision=?,updated_at=? "
                "WHERE owner_id=? AND space_id=? AND activity_kind=? AND activity_id=? "
                "AND revision=?",
                (revision, now, *key.as_tuple(), expected_revision),
            )
            return self._record_by_key_tx(connection, key)

        return self._write(
            key.owner_id, key.space_id, _op, operation_lease=operation_lease
        )

    @staticmethod
    def _attempt_fold(
        connection: sqlite3.Connection, key: LearningActivityKeyV1
    ) -> dict[str, int]:
        row = connection.execute(
            """
            SELECT COUNT(*) AS attempts_used,
                   COALESCE(SUM(reserved_input_tokens),0) AS reserved_input_tokens,
                   COALESCE(SUM(reserved_output_tokens),0) AS reserved_output_tokens,
                   COALESCE(SUM(reserved_wall_ms),0) AS reserved_wall_ms
            FROM tutor_provider_attempts
            WHERE owner_id=? AND space_id=? AND activity_kind=? AND activity_id=?
            """,
            key.as_tuple(),
        ).fetchone()
        return {field: int(row[field]) for field in row.keys()}

    @staticmethod
    def _terminal_event_id(key: LearningActivityKeyV1) -> str:
        digest = hashlib.sha256("\x1f".join(key.as_tuple()).encode("utf-8")).hexdigest()
        return f"tproj_{digest}"

    @staticmethod
    def _terminal_event_payload(
        *,
        outcome: str,
        terminal_code: str,
        completion_basis: str | None,
        remediation_count: int,
        budget_summary: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "outcome": outcome,
            "terminal_code": terminal_code,
            "completion_basis": completion_basis,
            "remediation_count": remediation_count,
            "budget_summary": {
                "nodes_used": budget_summary["nodes_used"],
                "attempts_used": budget_summary["attempts_used"],
                "reserved_input_tokens": budget_summary["reserved_input_tokens"],
                "reserved_output_tokens": budget_summary["reserved_output_tokens"],
                "reserved_wall_ms": budget_summary["reserved_wall_ms"],
                "active_elapsed_ms": budget_summary["active_elapsed_ms"],
            },
        }

    @classmethod
    def _terminal_event_payload_from_run(cls, run: Mapping[str, Any]) -> dict[str, Any]:
        return cls._terminal_event_payload(
            outcome=run["status"],
            terminal_code=run["terminal_code"],
            completion_basis=run["completion_basis"],
            remediation_count=run["remediation_count"],
            budget_summary={
                "nodes_used": run["budget_nodes_used"],
                "attempts_used": run["budget_attempts_used"],
                "reserved_input_tokens": run["budget_reserved_input_tokens"],
                "reserved_output_tokens": run["budget_reserved_output_tokens"],
                "reserved_wall_ms": run["budget_reserved_wall_ms"],
                "active_elapsed_ms": run["budget_active_elapsed_ms"],
            },
        )

    def _commit_terminal_tx(
        self,
        connection: sqlite3.Connection,
        key: LearningActivityKeyV1,
        *,
        expected_revision: int,
        outcome: str,
        terminal_code: str,
        completion_basis: str | None,
        remediation_count: int,
        budget_summary: Mapping[str, Any],
        permit_reserved_attempts: bool = False,
    ) -> LearningActivityRecordV1:
        run = self._require_mutable_run(connection, key, expected_revision)
        if not is_allowed_activity_transition(run["status"], outcome):
            raise TutorConflictError("invalid_transition")
        if outcome not in TERMINAL_ACTIVITY_STATUSES:
            raise TutorContractError("terminal outcome is invalid")
        if outcome == "completed":
            if terminal_code != "completed":
                raise TutorContractError("completed terminal_code is invalid")
            if completion_basis not in {"participation_only", "deterministic_correct"}:
                raise TutorContractError("completed outcome requires completion_basis")
        elif outcome == "blocked":
            if terminal_code not in {
                "provider_unavailable",
                "provider_timeout",
                "provider_attempt_exhausted",
                "invalid_model_output",
                "budget_exhausted",
                "source_missing",
                "remediation_exhausted",
                "checkpoint_too_large",
                "policy_rejected",
                "internal_error",
            }:
                raise TutorContractError("blocked terminal_code is invalid")
        elif terminal_code != "user_cancelled":
            raise TutorContractError("cancelled terminal_code is invalid")
        if outcome != "completed":
            if completion_basis is not None:
                raise TutorContractError(
                    "non-completed outcome cannot have completion_basis"
                )
        if type(remediation_count) is not int or remediation_count not in {0, 1}:
            raise TutorContractError("remediation_count must be 0 or 1")
        if (
            not isinstance(terminal_code, str)
            or not terminal_code
            or len(terminal_code) > 128
        ):
            raise TutorContractError("terminal_code is invalid")
        fields = (
            "nodes_used",
            "attempts_used",
            "reserved_input_tokens",
            "reserved_output_tokens",
            "reserved_wall_ms",
            "active_elapsed_ms",
        )
        normalized = {
            field: _non_negative_int(budget_summary.get(field), field)
            for field in fields
        }
        if (
            not permit_reserved_attempts
            and connection.execute(
                "SELECT 1 FROM tutor_provider_attempts WHERE owner_id=? AND space_id=? "
                "AND activity_kind=? AND activity_id=? AND status='reserved' LIMIT 1",
                key.as_tuple(),
            ).fetchone()
        ):
            raise TutorConflictError("attempt_not_settled")
        fold = self._attempt_fold(connection, key)
        for field in (
            "attempts_used",
            "reserved_input_tokens",
            "reserved_output_tokens",
            "reserved_wall_ms",
        ):
            if normalized[field] != fold[field]:
                raise TutorConflictError("budget_summary_mismatch")
        now = _now()
        revision = expected_revision + 1
        cursor = connection.execute(
            """
            UPDATE tutor_activity_runs
            SET status=?,revision=?,current_interrupt_id=NULL,execution_id=NULL,
                terminal_code=?,completion_basis=?,remediation_count=?,
                budget_nodes_used=?,budget_attempts_used=?,
                budget_reserved_input_tokens=?,budget_reserved_output_tokens=?,
                budget_reserved_wall_ms=?,budget_active_elapsed_ms=?,
                updated_at=?,terminal_at=?
            WHERE owner_id=? AND space_id=? AND activity_kind=? AND activity_id=?
              AND revision=?
            """,
            (
                outcome,
                revision,
                terminal_code,
                completion_basis,
                remediation_count,
                normalized["nodes_used"],
                normalized["attempts_used"],
                normalized["reserved_input_tokens"],
                normalized["reserved_output_tokens"],
                normalized["reserved_wall_ms"],
                normalized["active_elapsed_ms"],
                now,
                now,
                *key.as_tuple(),
                expected_revision,
            ),
        )
        if cursor.rowcount != 1:
            raise TutorConflictError("stale_revision")
        connection.execute(
            "DELETE FROM tutor_checkpoints WHERE owner_id=? AND space_id=? "
            "AND activity_kind=? AND activity_id=?",
            key.as_tuple(),
        )
        connection.execute(
            "DELETE FROM tutor_provider_attempts WHERE owner_id=? AND space_id=? "
            "AND activity_kind=? AND activity_id=?",
            key.as_tuple(),
        )
        payload = self._terminal_event_payload(
            outcome=outcome,
            terminal_code=terminal_code,
            completion_basis=completion_basis,
            remediation_count=remediation_count,
            budget_summary=normalized,
        )
        payload_json = canonical_json_bytes(payload).decode("utf-8")
        if len(payload_json.encode("utf-8")) > MAX_OUTBOX_PAYLOAD_BYTES:
            raise TutorConflictError("outbox_payload_too_large")
        connection.execute(
            """
            INSERT OR IGNORE INTO tutor_projection_outbox
                (event_id,owner_id,space_id,activity_kind,activity_id,event_type,
                 payload_json,created_at)
            VALUES (?,?,?,?,?,'tutor.terminal',?,?)
            """,
            (
                self._terminal_event_id(key),
                *key.as_tuple(),
                payload_json,
                now,
            ),
        )
        connection.execute(
            """
            DELETE FROM tutor_activity_runs
            WHERE rowid IN (
                SELECT rowid FROM tutor_activity_runs
                WHERE owner_id=? AND status IN ('completed','blocked','cancelled')
                ORDER BY updated_at DESC, activity_id DESC
                LIMIT -1 OFFSET ?
            )
            AND NOT EXISTS (
                SELECT 1 FROM tutor_projection_outbox AS pending
                WHERE pending.owner_id=tutor_activity_runs.owner_id
                  AND pending.space_id=tutor_activity_runs.space_id
                  AND pending.activity_kind=tutor_activity_runs.activity_kind
                  AND pending.activity_id=tutor_activity_runs.activity_id
                  AND pending.delivered_at IS NULL
            )
            """,
            (key.owner_id, MAX_TERMINAL_RUNS_PER_OWNER),
        )
        return self._record_by_key_tx(connection, key)

    def commit_terminal(
        self,
        key: LearningActivityKeyV1,
        *,
        expected_revision: int,
        outcome: str,
        terminal_code: str,
        completion_basis: str | None,
        remediation_count: int,
        budget_summary: Mapping[str, Any],
        operation_lease: OperationLease | None = None,
    ) -> LearningActivityRecordV1:
        if outcome == "cancelled":
            raise TutorContractError("cancelled outcome must use cancel()")
        return self._write(
            key.owner_id,
            key.space_id,
            lambda connection: self._commit_terminal_tx(
                connection,
                key,
                expected_revision=expected_revision,
                outcome=outcome,
                terminal_code=terminal_code,
                completion_basis=completion_basis,
                remediation_count=remediation_count,
                budget_summary=budget_summary,
            ),
            operation_lease=operation_lease,
        )

    def cancel(
        self,
        key: LearningActivityKeyV1,
        *,
        expected_revision: int,
        operation_lease: OperationLease | None = None,
    ) -> LearningActivityRecordV1:
        def _op(connection: sqlite3.Connection):
            run = self._require_mutable_run(connection, key, expected_revision)
            now = _now()
            connection.execute(
                "UPDATE tutor_provider_attempts SET status='unknown',completed_at=? "
                "WHERE owner_id=? AND space_id=? AND activity_kind=? AND activity_id=? "
                "AND status='reserved'",
                (now, *key.as_tuple()),
            )
            fold = self._attempt_fold(connection, key)
            return self._commit_terminal_tx(
                connection,
                key,
                expected_revision=expected_revision,
                outcome="cancelled",
                terminal_code="user_cancelled",
                completion_basis=None,
                remediation_count=int(run["remediation_count"]),
                budget_summary={
                    "nodes_used": int(run["budget_nodes_used"]),
                    **fold,
                    "active_elapsed_ms": int(run["budget_active_elapsed_ms"]),
                },
                permit_reserved_attempts=True,
            )

        return self._write(
            key.owner_id, key.space_id, _op, operation_lease=operation_lease
        )

    def clear_checkpoint(
        self,
        key: LearningActivityKeyV1,
        *,
        expected_revision: int,
        operation_lease: OperationLease | None = None,
    ) -> int:
        def _op(connection: sqlite3.Connection):
            run = self._fetch_run(connection, key)
            if run is None:
                raise TutorConflictError("activity_not_found")
            if run["revision"] != expected_revision:
                raise TutorConflictError("stale_revision")
            if run["status"] not in TERMINAL_ACTIVITY_STATUSES:
                raise TutorConflictError("checkpoint_clear_requires_terminal")
            connection.execute(
                "DELETE FROM tutor_checkpoints WHERE owner_id=? AND space_id=? "
                "AND activity_kind=? AND activity_id=?",
                key.as_tuple(),
            )
            return expected_revision

        return self._write(
            key.owner_id, key.space_id, _op, operation_lease=operation_lease
        )

    def reconcile_abandoned(
        self,
        owner_id: str,
        live_execution_ids: set[str],
        *,
        operation_lease: OperationLease | None = None,
    ) -> int:
        if not isinstance(live_execution_ids, set) or not all(
            isinstance(item, str) for item in live_execution_ids
        ):
            raise TutorContractError("live_execution_ids must be a set of strings")

        def _op(connection: sqlite3.Connection):
            rows = connection.execute(
                "SELECT * FROM tutor_activity_runs WHERE owner_id=? "
                "AND status='running' AND execution_id IS NOT NULL",
                (owner_id,),
            ).fetchall()
            count = 0
            now = _now()
            for run in rows:
                if run["execution_id"] in live_execution_ids:
                    continue
                key = LearningActivityKeyV1(
                    run["owner_id"],
                    run["space_id"],
                    run["activity_kind"],
                    run["activity_id"],
                )
                revision = int(run["revision"]) + 1
                active_elapsed_ms = min(
                    MAX_ACTIVE_ELAPSED_MS_PER_ACTIVITY,
                    int(run["budget_active_elapsed_ms"]) + ABANDONED_SEGMENT_CHARGE_MS,
                )
                checkpoint_row = self._fetch_checkpoint(connection, key)
                if (
                    checkpoint_row is None
                    or checkpoint_row["revision"] != run["revision"]
                ):
                    raise TutorConflictError("stale_revision")
                state = json.loads(checkpoint_row["state_json"])
                budget = state.setdefault("budget", {})
                if not isinstance(budget, dict):
                    raise TutorContractError("checkpoint budget must be an object")
                budget["active_elapsed_ms"] = active_elapsed_ms
                checkpoint = LearningCheckpointV1(
                    key=key,
                    revision=int(run["revision"]),
                    status="interrupted",
                    state=state,
                )
                state_json, interrupt_json, state_sha256 = self._checkpoint_values(
                    checkpoint
                )
                connection.execute(
                    "UPDATE tutor_activity_runs SET status='interrupted',revision=?,"
                    "execution_id=NULL,current_interrupt_id=NULL,"
                    "budget_active_elapsed_ms=?,updated_at=? "
                    "WHERE owner_id=? AND space_id=? AND activity_kind=? AND activity_id=? "
                    "AND revision=?",
                    (
                        revision,
                        active_elapsed_ms,
                        now,
                        *key.as_tuple(),
                        run["revision"],
                    ),
                )
                connection.execute(
                    "UPDATE tutor_checkpoints SET revision=?,state_json=?,"
                    "interrupt_json=?,state_sha256=?,updated_at=? "
                    "WHERE owner_id=? AND space_id=? AND activity_kind=? AND activity_id=? "
                    "AND revision=?",
                    (
                        revision,
                        state_json,
                        interrupt_json,
                        state_sha256,
                        now,
                        *key.as_tuple(),
                        run["revision"],
                    ),
                )
                connection.execute(
                    "UPDATE tutor_provider_attempts SET status='unknown',completed_at=? "
                    "WHERE owner_id=? AND space_id=? AND activity_kind=? AND activity_id=? "
                    "AND status='reserved'",
                    (now, *key.as_tuple()),
                )
                count += 1
            return count

        return self._write(owner_id, "", _op, operation_lease=operation_lease)

    def raw_run(
        self,
        key: LearningActivityKeyV1,
        *,
        operation_lease: OperationLease | None = None,
    ) -> dict[str, Any] | None:
        return self._read(
            key.owner_id,
            key.space_id,
            lambda connection: (
                dict(row) if (row := self._fetch_run(connection, key)) else None
            ),
            operation_lease=operation_lease,
        )

    def load_projection_source(
        self,
        key: LearningActivityKeyV1,
        *,
        operation_lease: OperationLease | None = None,
        coordination_guard: LearningOperationGuard | None = None,
    ) -> tuple[LearningActivityRecordV1, dict[str, Any]] | None:
        """Load checkpoint truth and run metadata in one coordinated snapshot."""

        def _op(connection: sqlite3.Connection):
            run = self._fetch_run(connection, key)
            if run is None:
                return None
            return (
                self._record(run, self._fetch_checkpoint(connection, key)),
                dict(run),
            )

        return self._read(
            key.owner_id,
            key.space_id,
            _op,
            operation_lease=operation_lease,
            coordination_guard=coordination_guard,
        )

    def list_projection_sources(
        self,
        owner_id: str,
        space_id: str,
        activity_kind: str,
        *,
        status: str | None = None,
        limit: int = 100,
        operation_lease: OperationLease | None = None,
    ) -> list[tuple[LearningActivityRecordV1, dict[str, Any]]]:
        """List projection inputs without exposing checkpoint content to callers."""

        if activity_kind not in ACTIVITY_KINDS:
            raise TutorContractError("activity_kind is invalid")
        if status is not None and status not in ACTIVITY_STATUSES:
            raise TutorContractError("activity status is invalid")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise TutorContractError("limit must be within 1..100")

        def _op(connection: sqlite3.Connection):
            sql = (
                "SELECT * FROM tutor_activity_runs WHERE owner_id=? AND space_id=? "
                "AND activity_kind=?"
            )
            params: list[Any] = [owner_id, space_id, activity_kind]
            if status is not None:
                sql += " AND status=?"
                params.append(status)
            sql += " ORDER BY updated_at DESC,activity_id DESC LIMIT ?"
            params.append(limit)
            return [
                (
                    self._record(
                        run,
                        self._fetch_checkpoint(
                            connection,
                            LearningActivityKeyV1(
                                run["owner_id"],
                                run["space_id"],
                                run["activity_kind"],
                                run["activity_id"],
                            ),
                        ),
                    ),
                    dict(run),
                )
                for run in connection.execute(sql, params).fetchall()
            ]

        return self._read(
            owner_id,
            space_id,
            _op,
            operation_lease=operation_lease,
        )

    def list_owner_projection_runs(
        self,
        owner_id: str,
        *,
        statuses: set[str] | None = None,
        limit: int = 300,
        operation_lease: OperationLease | None = None,
    ) -> list[dict[str, Any]]:
        """Return owner-wide lifecycle metadata for a read-only global view.

        This deliberately returns run rows rather than checkpoint state.  The
        global Activity surface may project persisted status, label, revision,
        and scope, but it must continue to use the domain resume/cancel commands
        for mutation and checkpoint validation.
        """
        if statuses is not None:
            if not isinstance(statuses, set) or not statuses.issubset(ACTIVITY_STATUSES):
                raise TutorContractError("activity statuses are invalid")
        if type(limit) is not int or not 1 <= limit <= 500:
            raise TutorContractError("limit must be within 1..500")

        def _op(connection: sqlite3.Connection) -> list[dict[str, Any]]:
            sql = "SELECT * FROM tutor_activity_runs WHERE owner_id=?"
            params: list[Any] = [owner_id]
            if statuses:
                placeholders = ",".join("?" for _ in statuses)
                sql += f" AND status IN ({placeholders})"
                params.extend(sorted(statuses))
            sql += " ORDER BY updated_at DESC,activity_id DESC LIMIT ?"
            params.append(limit)
            return [dict(row) for row in connection.execute(sql, params).fetchall()]

        return self._read(
            owner_id,
            "",
            _op,
            operation_lease=operation_lease,
        )

    def list_attempts(
        self,
        key: LearningActivityKeyV1,
        *,
        operation_lease: OperationLease | None = None,
    ) -> list[dict[str, Any]]:
        return self._read(
            key.owner_id,
            key.space_id,
            lambda connection: [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM tutor_provider_attempts WHERE owner_id=? "
                    "AND space_id=? AND activity_kind=? AND activity_id=? "
                    "ORDER BY ordinal",
                    key.as_tuple(),
                ).fetchall()
            ],
            operation_lease=operation_lease,
        )

    def aggregate_token_usage(
        self,
        owner_id: str,
        *,
        starts_at: str,
        ends_at: str,
        operation_lease: OperationLease | None = None,
    ) -> list[dict[str, Any]]:
        """Aggregate measured tokens for successful attempts in a UTC window.

        NULL actual-token values remain observable through the measured-attempt
        counts; they are never silently converted into zero-valued samples.
        """

        if not isinstance(owner_id, str) or not owner_id.strip():
            raise TutorContractError("owner_id is required")
        if not isinstance(starts_at, str) or not starts_at.strip():
            raise TutorContractError("starts_at is required")
        if not isinstance(ends_at, str) or not ends_at.strip():
            raise TutorContractError("ends_at is required")

        def _op(connection: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = connection.execute(
                """
                SELECT space_id, provider_id, model_id,
                       COUNT(*) AS succeeded_attempts,
                       COUNT(actual_input_tokens) AS input_measured_attempts,
                       COUNT(actual_output_tokens) AS output_measured_attempts,
                       COALESCE(SUM(actual_input_tokens), 0) AS input_tokens,
                       COALESCE(SUM(actual_output_tokens), 0) AS output_tokens
                FROM tutor_provider_attempts
                WHERE owner_id=? AND status='succeeded'
                  AND completed_at IS NOT NULL
                  AND completed_at>=? AND completed_at<?
                GROUP BY space_id, provider_id, model_id
                ORDER BY space_id, provider_id, model_id
                """,
                (owner_id, starts_at, ends_at),
            ).fetchall()
            return [dict(row) for row in rows]

        return self._read(
            owner_id,
            "",
            _op,
            operation_lease=operation_lease,
        )

    def list_pending_outbox(
        self,
        owner_id: str,
        *,
        operation_lease: OperationLease | None = None,
        coordination_guard: LearningOperationGuard | None = None,
    ) -> list[dict[str, Any]]:
        return self._read(
            owner_id,
            "",
            lambda connection: [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM tutor_projection_outbox WHERE owner_id=? "
                    "AND delivered_at IS NULL ORDER BY created_at,event_id",
                    (owner_id,),
                ).fetchall()
            ],
            operation_lease=operation_lease,
            coordination_guard=coordination_guard,
        )

    @staticmethod
    def _export_rows_tx(
        connection: sqlite3.Connection, owner_id: str
    ) -> dict[str, list[dict[str, Any]]]:
        runs = [
            {field: row[field] for field in _RUN_EXPORT_FIELDS}
            for row in connection.execute(
                "SELECT * FROM tutor_activity_runs WHERE owner_id=? "
                "ORDER BY space_id,activity_kind,activity_id",
                (owner_id,),
            ).fetchall()
        ]
        checkpoints: list[dict[str, Any]] = []
        for row in connection.execute(
            "SELECT * FROM tutor_checkpoints WHERE owner_id=? "
            "ORDER BY space_id,activity_kind,activity_id",
            (owner_id,),
        ).fetchall():
            item = {
                field: row[field]
                for field in _CHECKPOINT_EXPORT_FIELDS
                if field not in {"state", "interrupt"}
            }
            item["state"] = json.loads(row["state_json"])
            item["interrupt"] = (
                None
                if row["interrupt_json"] is None
                else json.loads(row["interrupt_json"])
            )
            checkpoints.append(item)
        attempts = [
            {field: row[field] for field in _ATTEMPT_EXPORT_FIELDS}
            for row in connection.execute(
                "SELECT * FROM tutor_provider_attempts WHERE owner_id=? "
                "ORDER BY space_id,activity_kind,activity_id,ordinal",
                (owner_id,),
            ).fetchall()
        ]
        outbox: list[dict[str, Any]] = []
        for row in connection.execute(
            "SELECT * FROM tutor_projection_outbox WHERE owner_id=? "
            "ORDER BY created_at,event_id",
            (owner_id,),
        ).fetchall():
            item = {
                field: row[field]
                for field in _OUTBOX_EXPORT_FIELDS
                if field != "payload"
            }
            item["payload"] = json.loads(row["payload_json"])
            outbox.append(item)
        return {
            "runs": runs,
            "checkpoints": checkpoints,
            "attempts": attempts,
            "outbox": outbox,
        }

    def export_owner_bundle(
        self,
        owner_id: str,
        *,
        operation_lease: OperationLease | None = None,
        coordination_guard: LearningOperationGuard | None = None,
    ) -> dict[str, Any]:
        payload = self._read(
            owner_id,
            "",
            lambda connection: self._export_rows_tx(connection, owner_id),
            operation_lease=operation_lease,
            coordination_guard=coordination_guard,
        )
        bundle = {"schema_version": 1, **payload}
        if len(canonical_json_bytes(bundle)) > 6 * 1024 * 1024:
            raise TutorConflictError("tutor_runtime_bundle_too_large")
        return bundle

    def owner_is_empty(
        self,
        owner_id: str,
        *,
        operation_lease: OperationLease | None = None,
    ) -> bool:
        def _op(connection: sqlite3.Connection) -> bool:
            for table in (
                "tutor_activity_runs",
                "tutor_checkpoints",
                "tutor_provider_attempts",
                "tutor_projection_outbox",
            ):
                if connection.execute(
                    f"SELECT 1 FROM {table} WHERE owner_id=? LIMIT 1", (owner_id,)
                ).fetchone():
                    return False
            return True

        return self._read(owner_id, "", _op, operation_lease=operation_lease)

    @staticmethod
    def _require_exact_row_fields(
        row: Any, fields: tuple[str, ...], section: str
    ) -> dict[str, Any]:
        if not isinstance(row, dict):
            raise TutorContractError(f"runtime {section} row must be an object")
        missing = set(fields) - set(row)
        unknown = set(row) - set(fields)
        if missing:
            raise TutorContractError(
                f"runtime {section} row is missing field: {sorted(missing)[0]}"
            )
        if unknown:
            raise TutorContractError(
                f"runtime {section} row has unknown field: {sorted(unknown)[0]}"
            )
        return copy.deepcopy(row)

    def _normalize_import_bundle(
        self, owner_id: str, bundle: Mapping[str, Any]
    ) -> dict[str, list[dict[str, Any]]]:
        if not isinstance(bundle, Mapping) or set(bundle) != {
            "schema_version",
            "runs",
            "checkpoints",
            "attempts",
            "outbox",
        }:
            raise TutorContractError("invalid TutorRuntimeBundleV1 shape")
        if bundle.get("schema_version") != 1:
            raise TutorContractError("unsupported TutorRuntimeBundle schema_version")
        if len(canonical_json_bytes(bundle)) > 6 * 1024 * 1024:
            raise TutorConflictError("tutor_runtime_bundle_too_large")
        limits = {
            "runs": MAX_TERMINAL_RUNS_PER_OWNER + MAX_NONTERMINAL_PER_OWNER,
            "checkpoints": MAX_NONTERMINAL_PER_OWNER,
            "attempts": MAX_NONTERMINAL_PER_OWNER * MAX_PROVIDER_ATTEMPTS_PER_ACTIVITY,
            "outbox": MAX_PENDING_OUTBOX_PER_OWNER,
        }
        normalized: dict[str, list[dict[str, Any]]] = {}
        field_sets = {
            "runs": _RUN_EXPORT_FIELDS,
            "checkpoints": _CHECKPOINT_EXPORT_FIELDS,
            "attempts": _ATTEMPT_EXPORT_FIELDS,
            "outbox": _OUTBOX_EXPORT_FIELDS,
        }
        for section, fields in field_sets.items():
            rows = bundle.get(section)
            if not isinstance(rows, list) or len(rows) > limits[section]:
                raise TutorConflictError(f"tutor_runtime_{section}_quota")
            normalized[section] = [
                self._require_exact_row_fields(row, fields, section) for row in rows
            ]

        run_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
        converted_running_keys: set[tuple[str, str, str]] = set()
        idempotency: dict[tuple[str, str, str], tuple[str, str]] = {}
        nonterminal_owner = 0
        nonterminal_spaces: dict[str, int] = {}
        for run in normalized["runs"]:
            key = LearningActivityKeyV1(
                owner_id,
                run["space_id"],
                run["activity_kind"],
                run["activity_id"],
            )
            short_key = (key.space_id, key.activity_kind, key.activity_id)
            if short_key in run_by_key:
                raise TutorConflictError("runtime_duplicate_identity")
            if run["schema_version"] != 1:
                raise TutorContractError("run schema_version is unsupported")
            if run["status"] not in {
                "created",
                "running",
                "waiting_for_learner",
                "interrupted",
                "completed",
                "blocked",
                "cancelled",
            }:
                raise TutorContractError("run status is invalid")
            if type(run["revision"]) is not int or run["revision"] < 0:
                raise TutorContractError("run revision is invalid")
            for field in ("idempotency_key", "activity_id"):
                if not isinstance(run[field], str) or not _ID_RE.fullmatch(run[field]):
                    raise TutorContractError(f"run {field} is invalid")
            if not isinstance(
                run["request_fingerprint"], str
            ) or not _SHA256_RE.fullmatch(run["request_fingerprint"]):
                raise TutorContractError("run request_fingerprint is invalid")
            namespace = (
                key.space_id,
                key.activity_kind,
                run["idempotency_key"],
            )
            prior = idempotency.get(namespace)
            identity_and_fingerprint = (key.activity_id, run["request_fingerprint"])
            if prior is not None and prior != identity_and_fingerprint:
                raise TutorConflictError("runtime_duplicate_idempotency_namespace")
            idempotency[namespace] = identity_and_fingerprint
            for field in (
                "remediation_count",
                "budget_nodes_used",
                "budget_attempts_used",
                "budget_reserved_input_tokens",
                "budget_reserved_output_tokens",
                "budget_reserved_wall_ms",
                "budget_active_elapsed_ms",
            ):
                _non_negative_int(run[field], f"run.{field}")
            if run["remediation_count"] not in {0, 1}:
                raise TutorContractError("run remediation_count is invalid")
            if not isinstance(run["label"], str) or len(run["label"]) > 300:
                raise TutorContractError("run label is invalid")
            if (
                run["budget_nodes_used"] > MAX_GRAPH_NODES_PER_ACTIVITY
                or run["budget_attempts_used"] > MAX_PROVIDER_ATTEMPTS_PER_ACTIVITY
                or run["budget_reserved_input_tokens"]
                > MAX_RESERVED_INPUT_TOKENS_PER_ACTIVITY
                or run["budget_reserved_output_tokens"]
                > MAX_RESERVED_OUTPUT_TOKENS_PER_ACTIVITY
                or run["budget_reserved_wall_ms"] > MAX_RESERVED_WALL_MS_PER_ACTIVITY
                or run["budget_active_elapsed_ms"] > MAX_ACTIVE_ELAPSED_MS_PER_ACTIVITY
            ):
                raise TutorConflictError("budget_exhausted")
            if run["status"] in {
                "created",
                "running",
                "waiting_for_learner",
                "interrupted",
            }:
                nonterminal_owner += 1
                nonterminal_spaces[key.space_id] = (
                    nonterminal_spaces.get(key.space_id, 0) + 1
                )
            if run["status"] == "running":
                # A restored worker cannot still own an execution.  The
                # conversion is deterministic so repeated restore is idempotent.
                run["status"] = "interrupted"
                run["revision"] += 1
                run["execution_id"] = None
                run["current_interrupt_id"] = None
                run["budget_active_elapsed_ms"] = min(
                    MAX_ACTIVE_ELAPSED_MS_PER_ACTIVITY,
                    run["budget_active_elapsed_ms"] + ABANDONED_SEGMENT_CHARGE_MS,
                )
                converted_running_keys.add(short_key)
            run_by_key[short_key] = run
        if nonterminal_owner > MAX_NONTERMINAL_PER_OWNER or any(
            count > MAX_NONTERMINAL_PER_SPACE for count in nonterminal_spaces.values()
        ):
            raise TutorConflictError("activity_quota_exceeded")
        if (
            sum(
                1
                for run in normalized["runs"]
                if run["status"] in TERMINAL_ACTIVITY_STATUSES
            )
            > MAX_TERMINAL_RUNS_PER_OWNER
        ):
            raise TutorConflictError("terminal_run_quota")

        checkpoint_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
        checkpoint_bytes = 0
        for checkpoint in normalized["checkpoints"]:
            key = LearningActivityKeyV1(
                owner_id,
                checkpoint["space_id"],
                checkpoint["activity_kind"],
                checkpoint["activity_id"],
            )
            short_key = (key.space_id, key.activity_kind, key.activity_id)
            run = run_by_key.get(short_key)
            if run is None or short_key in checkpoint_by_key:
                raise TutorConflictError("runtime_checkpoint_identity_conflict")
            state = validate_checkpoint_state(checkpoint["state"])
            state_bytes = canonical_json_bytes(state)
            checkpoint_bytes += len(state_bytes)
            if hashlib.sha256(state_bytes).hexdigest() != checkpoint["state_sha256"]:
                raise TutorConflictError("runtime_checkpoint_hash_mismatch")
            if short_key in converted_running_keys:
                original_state_size = len(state_bytes)
                budget = state.setdefault("budget", {})
                if not isinstance(budget, dict):
                    raise TutorContractError("checkpoint budget must be an object")
                budget["active_elapsed_ms"] = run["budget_active_elapsed_ms"]
                state = validate_checkpoint_state(state)
                state_bytes = canonical_json_bytes(state)
                checkpoint_bytes += len(state_bytes) - original_state_size
                checkpoint["state_sha256"] = hashlib.sha256(state_bytes).hexdigest()
            expected_revision = run["revision"]
            if (
                run["status"] == "interrupted"
                and checkpoint["revision"] + 1 == expected_revision
            ):
                checkpoint["revision"] = expected_revision
            if checkpoint["revision"] != expected_revision:
                raise TutorConflictError("runtime_checkpoint_revision_mismatch")
            if run["status"] in TERMINAL_ACTIVITY_STATUSES:
                raise TutorConflictError("terminal_run_has_checkpoint")
            checkpoint["state"] = state
            checkpoint_by_key[short_key] = checkpoint
        if checkpoint_bytes > MAX_OWNER_CHECKPOINT_BYTES:
            raise TutorConflictError("checkpoint_owner_quota")
        for short_key, run in run_by_key.items():
            has_checkpoint = short_key in checkpoint_by_key
            if run["status"] not in TERMINAL_ACTIVITY_STATUSES and not has_checkpoint:
                raise TutorConflictError("nonterminal_run_missing_checkpoint")

        attempt_ids: set[tuple[str, str, str, str]] = set()
        attempt_counts: dict[tuple[str, str, str], int] = {}
        for attempt in normalized["attempts"]:
            key = LearningActivityKeyV1(
                owner_id,
                attempt["space_id"],
                attempt["activity_kind"],
                attempt["activity_id"],
            )
            short_key = (key.space_id, key.activity_kind, key.activity_id)
            run = run_by_key.get(short_key)
            if run is None or run["status"] in TERMINAL_ACTIVITY_STATUSES:
                raise TutorConflictError("runtime_attempt_identity_conflict")
            attempt_key = (*short_key, attempt["attempt_id"])
            if attempt_key in attempt_ids:
                raise TutorConflictError("runtime_duplicate_attempt")
            attempt_ids.add(attempt_key)
            attempt_counts[short_key] = attempt_counts.get(short_key, 0) + 1
            if attempt_counts[short_key] > MAX_PROVIDER_ATTEMPTS_PER_ACTIVITY:
                raise TutorConflictError("provider_attempt_exhausted")
            if attempt["status"] == "reserved":
                attempt["status"] = "unknown"
                attempt["completed_at"] = attempt["reserved_at"]
            for field in (
                "ordinal",
                "reserved_input_tokens",
                "reserved_output_tokens",
                "reserved_wall_ms",
            ):
                _non_negative_int(attempt[field], f"attempt.{field}")
            if (
                attempt["reserved_input_tokens"] > MAX_RESERVED_INPUT_TOKENS_PER_ATTEMPT
                or attempt["reserved_output_tokens"]
                > MAX_RESERVED_OUTPUT_TOKENS_PER_ATTEMPT
                or attempt["reserved_wall_ms"] > MAX_RESERVED_WALL_MS_PER_ATTEMPT
            ):
                raise TutorConflictError("budget_exhausted")

        outbox_ids: set[str] = set()
        for event in normalized["outbox"]:
            key = LearningActivityKeyV1(
                owner_id,
                event["space_id"],
                event["activity_kind"],
                event["activity_id"],
            )
            run = run_by_key.get((key.space_id, key.activity_kind, key.activity_id))
            if run is None:
                raise TutorConflictError("runtime_outbox_identity_conflict")
            if not isinstance(event["event_id"], str) or not _ID_RE.fullmatch(
                event["event_id"]
            ):
                raise TutorContractError("outbox event_id is invalid")
            if event["event_id"] in outbox_ids:
                raise TutorConflictError("runtime_duplicate_outbox_event")
            outbox_ids.add(event["event_id"])
            if event["event_id"] != self._terminal_event_id(key):
                raise TutorConflictError("runtime_outbox_event_id_mismatch")
            if run["status"] not in TERMINAL_ACTIVITY_STATUSES:
                raise TutorConflictError("runtime_outbox_requires_terminal_run")
            if event["event_type"] != "tutor.terminal":
                raise TutorConflictError("runtime_outbox_event_type_mismatch")
            if (
                not isinstance(event["payload"], dict)
                or len(canonical_json_bytes(event["payload"]))
                > MAX_OUTBOX_PAYLOAD_BYTES
            ):
                raise TutorConflictError("outbox_payload_too_large")
            if canonical_json_bytes(event["payload"]) != canonical_json_bytes(
                self._terminal_event_payload_from_run(run)
            ):
                raise TutorConflictError("runtime_outbox_payload_mismatch")
            if event["created_at"] != run["terminal_at"]:
                raise TutorConflictError("runtime_outbox_created_at_mismatch")
            if event["delivered_at"] is not None:
                raise TutorContractError("delivered outbox rows must not be bundled")
        return normalized

    @staticmethod
    def _incoming_group(
        normalized: Mapping[str, list[dict[str, Any]]],
        short_key: tuple[str, str, str],
    ) -> dict[str, Any]:
        return {
            "run": next(
                row
                for row in normalized["runs"]
                if (row["space_id"], row["activity_kind"], row["activity_id"])
                == short_key
            ),
            "checkpoint": next(
                (
                    row
                    for row in normalized["checkpoints"]
                    if (row["space_id"], row["activity_kind"], row["activity_id"])
                    == short_key
                ),
                None,
            ),
            "attempts": [
                row
                for row in normalized["attempts"]
                if (row["space_id"], row["activity_kind"], row["activity_id"])
                == short_key
            ],
        }

    @staticmethod
    def _insert_import_group_tx(
        connection: sqlite3.Connection,
        owner_id: str,
        group: Mapping[str, Any],
    ) -> None:
        run = group["run"]
        columns = ",".join(("owner_id", *_RUN_EXPORT_FIELDS))
        placeholders = ",".join("?" for _ in range(1 + len(_RUN_EXPORT_FIELDS)))
        connection.execute(
            f"INSERT INTO tutor_activity_runs ({columns}) VALUES ({placeholders})",
            (owner_id, *(run[field] for field in _RUN_EXPORT_FIELDS)),
        )
        checkpoint = group["checkpoint"]
        if checkpoint is not None:
            connection.execute(
                """
                INSERT INTO tutor_checkpoints
                    (owner_id,space_id,activity_kind,activity_id,revision,
                     graph_schema_version,state_json,interrupt_json,state_sha256,
                     created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    owner_id,
                    checkpoint["space_id"],
                    checkpoint["activity_kind"],
                    checkpoint["activity_id"],
                    checkpoint["revision"],
                    checkpoint["graph_schema_version"],
                    canonical_json_bytes(checkpoint["state"]).decode("utf-8"),
                    None
                    if checkpoint["interrupt"] is None
                    else canonical_json_bytes(checkpoint["interrupt"]).decode("utf-8"),
                    checkpoint["state_sha256"],
                    checkpoint["created_at"],
                    checkpoint["updated_at"],
                ),
            )
        for attempt in group["attempts"]:
            columns = ",".join(("owner_id", *_ATTEMPT_EXPORT_FIELDS))
            placeholders = ",".join("?" for _ in range(1 + len(_ATTEMPT_EXPORT_FIELDS)))
            connection.execute(
                f"INSERT INTO tutor_provider_attempts ({columns}) VALUES ({placeholders})",
                (owner_id, *(attempt[field] for field in _ATTEMPT_EXPORT_FIELDS)),
            )

    @staticmethod
    def _validate_merged_quotas_tx(
        connection: sqlite3.Connection,
        owner_id: str,
        new_groups: list[Mapping[str, Any]],
        new_events: list[Mapping[str, Any]],
    ) -> None:
        """Validate the post-merge state inside the importing write transaction."""

        if not new_groups and not new_events:
            return
        existing_nonterminal = int(
            connection.execute(
                "SELECT COUNT(*) FROM tutor_activity_runs WHERE owner_id=? "
                f"AND status IN ({_NONTERMINAL_SQL})",
                (owner_id,),
            ).fetchone()[0]
        )
        added_nonterminal = sum(
            group["run"]["status"] not in TERMINAL_ACTIVITY_STATUSES
            for group in new_groups
        )
        if existing_nonterminal + added_nonterminal > MAX_NONTERMINAL_PER_OWNER:
            raise TutorConflictError("activity_quota_exceeded")

        existing_by_space = {
            row["space_id"]: int(row["count"])
            for row in connection.execute(
                "SELECT space_id,COUNT(*) AS count FROM tutor_activity_runs "
                f"WHERE owner_id=? AND status IN ({_NONTERMINAL_SQL}) "
                "GROUP BY space_id",
                (owner_id,),
            ).fetchall()
        }
        for group in new_groups:
            run = group["run"]
            if run["status"] in TERMINAL_ACTIVITY_STATUSES:
                continue
            space_id = run["space_id"]
            existing_by_space[space_id] = existing_by_space.get(space_id, 0) + 1
        if any(
            count > MAX_NONTERMINAL_PER_SPACE for count in existing_by_space.values()
        ):
            raise TutorConflictError("activity_quota_exceeded")

        existing_terminal = int(
            connection.execute(
                "SELECT COUNT(*) FROM tutor_activity_runs WHERE owner_id=? "
                "AND status IN ('completed','blocked','cancelled')",
                (owner_id,),
            ).fetchone()[0]
        )
        added_terminal = sum(
            group["run"]["status"] in TERMINAL_ACTIVITY_STATUSES for group in new_groups
        )
        if existing_terminal + added_terminal > MAX_TERMINAL_RUNS_PER_OWNER:
            raise TutorConflictError("terminal_run_quota")

        existing_checkpoint_bytes = int(
            connection.execute(
                "SELECT COALESCE(SUM(length(CAST(state_json AS BLOB))),0) "
                "FROM tutor_checkpoints WHERE owner_id=?",
                (owner_id,),
            ).fetchone()[0]
        )
        added_checkpoint_bytes = sum(
            len(canonical_json_bytes(group["checkpoint"]["state"]))
            for group in new_groups
            if group["checkpoint"] is not None
        )
        if (
            existing_checkpoint_bytes + added_checkpoint_bytes
            > MAX_OWNER_CHECKPOINT_BYTES
        ):
            raise TutorConflictError("checkpoint_owner_quota")

        existing_attempts = int(
            connection.execute(
                "SELECT COUNT(*) FROM tutor_provider_attempts WHERE owner_id=?",
                (owner_id,),
            ).fetchone()[0]
        )
        added_attempts = sum(len(group["attempts"]) for group in new_groups)
        if (
            existing_attempts + added_attempts
            > MAX_NONTERMINAL_PER_OWNER * MAX_PROVIDER_ATTEMPTS_PER_ACTIVITY
        ):
            raise TutorConflictError("tutor_runtime_attempts_quota")

        existing_outbox = int(
            connection.execute(
                "SELECT COUNT(*) FROM tutor_projection_outbox "
                "WHERE owner_id=? AND delivered_at IS NULL",
                (owner_id,),
            ).fetchone()[0]
        )
        if existing_outbox + len(new_events) > MAX_PENDING_OUTBOX_PER_OWNER:
            raise TutorConflictError("tutor_runtime_outbox_quota")

    def import_owner_bundle(
        self,
        owner_id: str,
        bundle: Mapping[str, Any],
        *,
        mode: str,
        operation_lease: OperationLease | None = None,
    ) -> dict[str, int]:
        if mode not in {"replace_empty_owner", "tutor_runtime_merge"}:
            raise TutorContractError("runtime import mode is invalid")
        normalized = self._normalize_import_bundle(owner_id, bundle)

        def _op(connection: sqlite3.Connection) -> dict[str, int]:
            if mode == "replace_empty_owner":
                for table in (
                    "tutor_activity_runs",
                    "tutor_checkpoints",
                    "tutor_provider_attempts",
                    "tutor_projection_outbox",
                ):
                    if connection.execute(
                        f"SELECT 1 FROM {table} WHERE owner_id=? LIMIT 1", (owner_id,)
                    ).fetchone():
                        raise TutorConflictError("runtime_owner_not_empty")
            inserted = {"runs": 0, "checkpoints": 0, "attempts": 0, "outbox": 0}
            skipped_keys: set[tuple[str, str, str]] = set()
            new_groups: list[dict[str, Any]] = []
            for run in normalized["runs"]:
                short_key = (run["space_id"], run["activity_kind"], run["activity_id"])
                key = LearningActivityKeyV1(owner_id, *short_key)
                existing = self._fetch_run(connection, key)
                idempotent = False
                if existing is not None:
                    existing_payload = self._export_rows_tx(connection, owner_id)
                    existing_group = self._incoming_group(existing_payload, short_key)
                    incoming_group = self._incoming_group(normalized, short_key)
                    if canonical_json_bytes(existing_group) != canonical_json_bytes(
                        incoming_group
                    ):
                        raise TutorConflictError("runtime_merge_identity_conflict")
                    idempotent = True
                namespace_row = connection.execute(
                    "SELECT activity_id,request_fingerprint FROM tutor_activity_runs "
                    "WHERE owner_id=? AND space_id=? AND activity_kind=? "
                    "AND idempotency_key=?",
                    (
                        owner_id,
                        run["space_id"],
                        run["activity_kind"],
                        run["idempotency_key"],
                    ),
                ).fetchone()
                if namespace_row is not None and (
                    namespace_row["activity_id"] != run["activity_id"]
                    or namespace_row["request_fingerprint"]
                    != run["request_fingerprint"]
                ):
                    raise TutorConflictError("runtime_merge_idempotency_conflict")
                if idempotent:
                    skipped_keys.add(short_key)
                    continue
                group = self._incoming_group(normalized, short_key)
                new_groups.append(group)
            new_events: list[dict[str, Any]] = []
            for event in normalized["outbox"]:
                existing_event = connection.execute(
                    "SELECT * FROM tutor_projection_outbox WHERE event_id=?",
                    (event["event_id"],),
                ).fetchone()
                if existing_event is not None:
                    existing_payload = {
                        field: (
                            json.loads(existing_event["payload_json"])
                            if field == "payload"
                            else existing_event[field]
                        )
                        for field in _OUTBOX_EXPORT_FIELDS
                    }
                    if existing_event["owner_id"] != owner_id or canonical_json_bytes(
                        existing_payload
                    ) != canonical_json_bytes(event):
                        raise TutorConflictError("runtime_merge_outbox_conflict")
                    continue
                new_events.append(event)

            if mode == "tutor_runtime_merge":
                self._validate_merged_quotas_tx(
                    connection, owner_id, new_groups, new_events
                )

            for group in new_groups:
                self._insert_import_group_tx(connection, owner_id, group)
                inserted["runs"] += 1
                inserted["checkpoints"] += int(group["checkpoint"] is not None)
                inserted["attempts"] += len(group["attempts"])
            for event in new_events:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO tutor_projection_outbox
                        (event_id,owner_id,space_id,activity_kind,activity_id,
                         event_type,payload_json,created_at,delivered_at)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        event["event_id"],
                        owner_id,
                        event["space_id"],
                        event["activity_kind"],
                        event["activity_id"],
                        event["event_type"],
                        canonical_json_bytes(event["payload"]).decode("utf-8"),
                        event["created_at"],
                        event["delivered_at"],
                    ),
                )
                inserted["outbox"] += int(cursor.rowcount == 1)
            return inserted

        try:
            return self._write(owner_id, "", _op, operation_lease=operation_lease)
        except sqlite3.IntegrityError as exc:
            raise TutorConflictError("runtime_import_conflict") from exc

    def delete_owner_data(
        self,
        owner_id: str,
        *,
        operation_lease: OperationLease | None = None,
    ) -> dict[str, int]:
        counts: dict[str, int] = {}

        def _op(connection: sqlite3.Connection) -> dict[str, int]:
            for table in (
                "tutor_projection_outbox",
                "tutor_provider_attempts",
                "tutor_checkpoints",
                "tutor_activity_runs",
            ):
                cursor = connection.execute(
                    f"DELETE FROM {table} WHERE owner_id=?", (owner_id,)
                )
                counts[table] = cursor.rowcount
            return counts

        return self._write(owner_id, "", _op, operation_lease=operation_lease)

    def delete_space_data(
        self,
        owner_id: str,
        space_id: str,
        *,
        operation_lease: OperationLease | None = None,
    ) -> dict[str, int]:
        counts: dict[str, int] = {}

        def _op(connection: sqlite3.Connection) -> dict[str, int]:
            for table in (
                "tutor_projection_outbox",
                "tutor_provider_attempts",
                "tutor_checkpoints",
                "tutor_activity_runs",
            ):
                cursor = connection.execute(
                    f"DELETE FROM {table} WHERE owner_id=? AND space_id=?",
                    (owner_id, space_id),
                )
                counts[table] = cursor.rowcount
            return counts

        return self._write(owner_id, space_id, _op, operation_lease=operation_lease)

    def compact(
        self,
        owner_id: str,
        space_id: str = "",
        *,
        operation_lease: OperationLease | None = None,
    ) -> None:
        with self.coordinator.begin_write(
            owner_id, space_id, operation_lease=operation_lease
        ):
            last_error: Exception | None = None
            for attempt in range(self._MAX_RETRIES):
                try:
                    with self._lock:
                        before = self._conn.execute(
                            "PRAGMA wal_checkpoint(TRUNCATE)"
                        ).fetchone()
                        if before and before[0] != 0:
                            raise sqlite3.OperationalError(
                                "runtime WAL checkpoint remained busy"
                            )
                        self._conn.execute("VACUUM")
                        after = self._conn.execute(
                            "PRAGMA wal_checkpoint(TRUNCATE)"
                        ).fetchone()
                        if after and after[0] != 0:
                            raise sqlite3.OperationalError(
                                "runtime WAL checkpoint remained busy"
                            )
                    return
                except sqlite3.OperationalError as exc:
                    last_error = exc
                    if attempt < self._MAX_RETRIES - 1:
                        time.sleep(random.uniform(self._RETRY_MIN_S, self._RETRY_MAX_S))
                        continue
                    raise TutorRuntimeBusyError() from exc
            raise TutorRuntimeBusyError() from last_error

    def mark_outbox_delivered(
        self,
        owner_id: str,
        event_id: str,
        *,
        operation_lease: OperationLease | None = None,
        coordination_guard: LearningOperationGuard | None = None,
    ) -> bool:
        if not isinstance(event_id, str) or not _ID_RE.fullmatch(event_id):
            raise TutorContractError("event_id is invalid")

        def _op(connection: sqlite3.Connection) -> bool:
            cursor = connection.execute(
                "DELETE FROM tutor_projection_outbox "
                "WHERE event_id=? AND owner_id=? AND delivered_at IS NULL",
                (event_id, owner_id),
            )
            return cursor.rowcount == 1

        return self._write(
            owner_id,
            "",
            _op,
            operation_lease=operation_lease,
            coordination_guard=coordination_guard,
        )


__all__ = [
    "ProviderAttemptReservationV1",
    "RUNTIME_SCHEMA_VERSION",
    "TutorRuntimeError",
    "TutorRuntimeBusyError",
    "TutorRuntimeSchemaError",
    "TutorRuntimeStore",
    "default_tutor_runtime_db_path",
]
