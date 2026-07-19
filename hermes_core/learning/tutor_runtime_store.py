"""SQLite v1 adapter for resumable Tutor run/checkpoint truth.

The runtime database is intentionally separate from ``learning.db`` so v0.4
never opens or mutates these tables.  Every business read/write first acquires
the shared operation coordinator, preserving the fixed lock order
``coordination -> runtime`` (and ``coordination -> learning -> runtime`` for
composite services).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import sqlite3
import threading
import time
from typing import Any, Callable, Mapping, Optional, TypeVar

from kabuqina_constants import get_default_kabuqina_root

from .checkpoint_store import (
    MAX_CHECKPOINT_BYTES,
    LearningActivityRecordV1,
    LearningCheckpointV1,
    validate_checkpoint_state,
)
from .operation_coordinator import (
    LearningOperationCoordinator,
    OperationLease,
    secure_coordination_db,
)
from .tutor_contract import (
    ACTIVITY_KINDS,
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
            raise TutorContractError("reserved_output_tokens exceeds per-attempt budget")
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
    ) -> None:
        is_default = db_path is None
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
                    ("locked" in message or "busy" in message)
                    and attempt < self._MAX_RETRIES - 1
                ):
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
                "journal_mode": self._conn.execute("PRAGMA journal_mode").fetchone()[0].lower(),
                "secure_delete": self._conn.execute("PRAGMA secure_delete").fetchone()[0],
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
                    ("locked" in message or "busy" in message)
                    and attempt < self._MAX_RETRIES - 1
                ):
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
    ) -> T:
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
    ) -> T:
        with self.coordinator.begin_read(
            owner_id, space_id, operation_lease=operation_lease
        ):
            with self._lock:
                self._conn.execute("BEGIN")
                try:
                    result = function(self._conn)
                    self._conn.commit()
                    return result
                except BaseException:
                    self._conn.rollback()
                    raise

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
                raise TutorContractError("waiting checkpoint requires pending_interrupt")
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
        if not isinstance(prompt, dict) or not isinstance(created_at, str) or not created_at:
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
    ) -> LearningActivityRecordV1 | None:
        return self._read(
            key.owner_id,
            key.space_id,
            lambda connection: self._record_by_key_tx(connection, key),
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
                    run["owner_id"], run["space_id"], run["activity_kind"], run["activity_id"]
                )
                records.append(self._record(run, self._fetch_checkpoint(connection, key)))
            return records

        return self._read(
            owner_id, space_id, _op, operation_lease=operation_lease
        )

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
            run = self._require_mutable_run(connection, checkpoint.key, expected_revision)
            status_unchanged_checkpoint = (
                checkpoint.status == run["status"]
                and checkpoint.status in {"running", "waiting_for_learner"}
            )
            allowed_graph_transition = (
                run["status"] == "running"
                and checkpoint.status in {"waiting_for_learner", "interrupted"}
            )
            if not status_unchanged_checkpoint and not allowed_graph_transition:
                raise TutorConflictError("invalid_transition")
            existing_checkpoint = self._fetch_checkpoint(connection, checkpoint.key)
            if existing_checkpoint is None or existing_checkpoint["revision"] != expected_revision:
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
            if checkpoint_row is None or checkpoint_row["revision"] != expected_revision:
                raise TutorConflictError("stale_revision")
            state = json.loads(checkpoint_row["state_json"])
            interrupt = self._validate_pending_interrupt(
                state, key, expected_revision, required=True
            )
            if interrupt is None or interrupt.interrupt_id != interrupt_id:
                raise TutorConflictError("interrupt_mismatch")
            state.pop("pending_interrupt", None)
            state["learner_answer"] = copy.deepcopy(normalized_resume.answer)
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
                or int(run["budget_reserved_wall_ms"])
                + reservation.reserved_wall_ms
                > MAX_RESERVED_WALL_MS_PER_ACTIVITY
            ):
                raise TutorConflictError("budget_exhausted")
            checkpoint_row = self._fetch_checkpoint(connection, key)
            if checkpoint_row is None or checkpoint_row["revision"] != expected_revision:
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
                raise TutorContractError("non-completed outcome cannot have completion_basis")
        if type(remediation_count) is not int or remediation_count not in {0, 1}:
            raise TutorContractError("remediation_count must be 0 or 1")
        if not isinstance(terminal_code, str) or not terminal_code or len(terminal_code) > 128:
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
        if not permit_reserved_attempts and connection.execute(
            "SELECT 1 FROM tutor_provider_attempts WHERE owner_id=? AND space_id=? "
            "AND activity_kind=? AND activity_id=? AND status='reserved' LIMIT 1",
            key.as_tuple(),
        ).fetchone():
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
        payload = {
            "schema_version": 1,
            "outcome": outcome,
            "terminal_code": terminal_code,
            "completion_basis": completion_basis,
            "remediation_count": remediation_count,
            "budget_summary": normalized,
        }
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
                    run["owner_id"], run["space_id"], run["activity_kind"], run["activity_id"]
                )
                revision = int(run["revision"]) + 1
                active_elapsed_ms = min(
                    MAX_ACTIVE_ELAPSED_MS_PER_ACTIVITY,
                    int(run["budget_active_elapsed_ms"])
                    + ABANDONED_SEGMENT_CHARGE_MS,
                )
                checkpoint_row = self._fetch_checkpoint(connection, key)
                if checkpoint_row is None or checkpoint_row["revision"] != run["revision"]:
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

    def list_pending_outbox(
        self,
        owner_id: str,
        *,
        operation_lease: OperationLease | None = None,
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
        )

    def mark_outbox_delivered(
        self,
        owner_id: str,
        event_id: str,
        *,
        operation_lease: OperationLease | None = None,
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
            owner_id, "", _op, operation_lease=operation_lease
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
