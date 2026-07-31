"""Durable runtime store for non-conversational knowledge-core compilation.

Compilation is not a Tutor activity and never becomes learning evidence.  The
small dedicated database owns only resumable execution metadata; artifacts stay
in ``learning.db`` under the existing draft/review/activate lifecycle.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import threading
import uuid
from typing import Any, Iterable, Mapping, Optional

from kabuqina_constants import get_default_kabuqina_root


POLICY_VERSION = "knowledge-core-compiler-v1"
RUN_STATUSES = frozenset(
    {
        "queued",
        "reading",
        "generating",
        "validating",
        "draft_ready",
        "needs_source",
        "failed",
        "cancelled",
    }
)
ACTIVE_STATUSES = frozenset({"queued", "reading", "generating", "validating"})
TERMINAL_STATUSES = RUN_STATUSES - ACTIVE_STATUSES
TRIGGERS = frozenset({"plan_activated", "start_learning", "prefetch", "retry"})
_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_compilation_db_path() -> Path:
    return get_default_kabuqina_root().resolve() / "knowledge_core_compilations.db"


def _text(value: Any, name: str, *, maximum: int = 500) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    result = value.strip()
    if len(result) > maximum:
        raise ValueError(f"{name} is too long")
    return result


def _opaque(value: Any, name: str) -> str:
    result = _text(value, name, maximum=200)
    if not _ID_RE.fullmatch(result):
        raise ValueError(f"{name} is invalid")
    return result


def _fingerprint(value: Any, name: str) -> str:
    result = _text(value, name, maximum=64)
    if not _SHA256_RE.fullmatch(result):
        raise ValueError(f"{name} must be a sha256 digest")
    return result


def validate_compilation_request(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("compilation request must be an object")
    allowed = {
        "space_id",
        "outline_node_id",
        "plan_item_id",
        "trigger",
        "expected_map_revision",
        "idempotency_key",
    }
    if set(value) - allowed:
        raise ValueError("compilation request fields are invalid")
    trigger = _text(value.get("trigger"), "trigger", maximum=40)
    if trigger not in TRIGGERS:
        raise ValueError("compilation trigger is invalid")
    expected = value.get("expected_map_revision")
    if type(expected) is not int or expected < 1:
        raise ValueError("expected_map_revision must be a positive integer")
    plan_item_id = value.get("plan_item_id")
    return {
        "space_id": _opaque(value.get("space_id"), "space_id"),
        "outline_node_id": _opaque(value.get("outline_node_id"), "outline_node_id"),
        "plan_item_id": (
            ""
            if plan_item_id is None
            or (isinstance(plan_item_id, str) and not plan_item_id.strip())
            else _opaque(plan_item_id, "plan_item_id")
        ),
        "trigger": trigger,
        "expected_map_revision": expected,
        "idempotency_key": _opaque(value.get("idempotency_key"), "idempotency_key"),
    }


SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_core_compilation_runs (
    owner_id            TEXT NOT NULL,
    space_id            TEXT NOT NULL,
    run_id              TEXT NOT NULL,
    outline_node_id     TEXT NOT NULL,
    plan_item_id        TEXT NOT NULL DEFAULT '',
    trigger             TEXT NOT NULL,
    status              TEXT NOT NULL,
    priority            INTEGER NOT NULL DEFAULT 0,
    source_fingerprint  TEXT NOT NULL,
    compilation_key     TEXT NOT NULL,
    policy_version      TEXT NOT NULL,
    idempotency_key     TEXT NOT NULL,
    request_json        TEXT NOT NULL DEFAULT '{}',
    windows_json        TEXT NOT NULL DEFAULT '[]',
    draft_artifact_id   TEXT NOT NULL DEFAULT '',
    reason_code         TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    PRIMARY KEY (owner_id, space_id, run_id),
    UNIQUE (owner_id, space_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_kcc_runs_compilation
    ON knowledge_core_compilation_runs
       (owner_id, space_id, compilation_key, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_kcc_runs_owner_status
    ON knowledge_core_compilation_runs (owner_id, status, updated_at DESC);
"""


class KnowledgeCoreCompilationStore:
    """Thread-safe SQLite store with idempotent enqueue and explicit transitions."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path or default_compilation_db_path()).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=5.0,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA secure_delete=ON")
        self._conn.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def _row(row: sqlite3.Row | None) -> Optional[dict[str, Any]]:
        if row is None:
            return None
        result = dict(row)
        result["priority"] = int(result["priority"])
        result["request"] = json.loads(result.pop("request_json") or "{}")
        result["windows"] = json.loads(result.pop("windows_json") or "[]")
        return result

    def get_run(self, owner_id: str, space_id: str, run_id: str) -> Optional[dict[str, Any]]:
        _text(owner_id, "owner_id", maximum=200)
        _opaque(space_id, "space_id")
        _opaque(run_id, "run_id")
        with self._lock:
            return self._row(
                self._conn.execute(
                    "SELECT * FROM knowledge_core_compilation_runs "
                    "WHERE owner_id=? AND space_id=? AND run_id=?",
                    (owner_id, space_id, run_id),
                ).fetchone()
            )

    def create_or_reuse(
        self,
        owner_id: str,
        request: Mapping[str, Any],
        *,
        source_fingerprint: str,
        compilation_key: str,
        priority: int = 0,
        initial_status: str = "queued",
        draft_artifact_id: str = "",
        reason_code: str = "",
    ) -> tuple[dict[str, Any], bool]:
        owner_id = _text(owner_id, "owner_id", maximum=200)
        normalized = validate_compilation_request(request)
        source_fingerprint = _fingerprint(source_fingerprint, "source_fingerprint")
        compilation_key = _fingerprint(compilation_key, "compilation_key")
        if initial_status not in RUN_STATUSES:
            raise ValueError("initial_status is invalid")
        if type(priority) is not int or not -10 <= priority <= 10:
            raise ValueError("priority must be within -10..10")
        now = _now()
        run_id = uuid.uuid4().hex
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._conn.execute(
                    "SELECT * FROM knowledge_core_compilation_runs "
                    "WHERE owner_id=? AND space_id=? AND idempotency_key=?",
                    (
                        owner_id,
                        normalized["space_id"],
                        normalized["idempotency_key"],
                    ),
                ).fetchone()
                if existing is None:
                    existing = self._conn.execute(
                        "SELECT * FROM knowledge_core_compilation_runs "
                        "WHERE owner_id=? AND space_id=? AND compilation_key=? "
                        "AND status IN ('queued','reading','generating','validating','draft_ready') "
                        "ORDER BY updated_at DESC LIMIT 1",
                        (
                            owner_id,
                            normalized["space_id"],
                            compilation_key,
                        ),
                    ).fetchone()
                if existing is not None:
                    self._conn.commit()
                    return self._row(existing) or {}, False
                self._conn.execute(
                    "INSERT INTO knowledge_core_compilation_runs "
                    "(owner_id,space_id,run_id,outline_node_id,plan_item_id,trigger,"
                    "status,priority,source_fingerprint,compilation_key,policy_version,"
                    "idempotency_key,request_json,windows_json,draft_artifact_id,"
                    "reason_code,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        owner_id,
                        normalized["space_id"],
                        run_id,
                        normalized["outline_node_id"],
                        normalized["plan_item_id"],
                        normalized["trigger"],
                        initial_status,
                        priority,
                        source_fingerprint,
                        compilation_key,
                        POLICY_VERSION,
                        normalized["idempotency_key"],
                        json.dumps(normalized, ensure_ascii=False, sort_keys=True),
                        "[]",
                        str(draft_artifact_id or ""),
                        str(reason_code or ""),
                        now,
                        now,
                    ),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return self.get_run(owner_id, normalized["space_id"], run_id) or {}, True

    def transition(
        self,
        owner_id: str,
        space_id: str,
        run_id: str,
        status: str,
        *,
        allowed_from: Optional[Iterable[str]] = None,
        windows: Optional[list[dict[str, Any]]] = None,
        draft_artifact_id: Optional[str] = None,
        reason_code: Optional[str] = None,
    ) -> dict[str, Any]:
        if status not in RUN_STATUSES:
            raise ValueError("compilation status is invalid")
        allowed = set(allowed_from or RUN_STATUSES)
        if not allowed.issubset(RUN_STATUSES):
            raise ValueError("allowed_from contains an invalid status")
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT * FROM knowledge_core_compilation_runs "
                    "WHERE owner_id=? AND space_id=? AND run_id=?",
                    (owner_id, space_id, run_id),
                ).fetchone()
                if row is None:
                    raise KeyError("compilation run is unavailable")
                if row["status"] not in allowed:
                    raise ValueError(
                        f"cannot transition compilation from {row['status']} to {status}"
                    )
                next_windows = (
                    json.dumps(windows, ensure_ascii=False)
                    if windows is not None
                    else row["windows_json"]
                )
                next_draft = (
                    str(draft_artifact_id)
                    if draft_artifact_id is not None
                    else row["draft_artifact_id"]
                )
                next_reason = (
                    str(reason_code)
                    if reason_code is not None
                    else row["reason_code"]
                )
                self._conn.execute(
                    "UPDATE knowledge_core_compilation_runs SET "
                    "status=?,windows_json=?,draft_artifact_id=?,reason_code=?,updated_at=? "
                    "WHERE owner_id=? AND space_id=? AND run_id=?",
                    (
                        status,
                        next_windows,
                        next_draft,
                        next_reason,
                        _now(),
                        owner_id,
                        space_id,
                        run_id,
                    ),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return self.get_run(owner_id, space_id, run_id) or {}

    def cancel(self, owner_id: str, space_id: str, run_id: str) -> dict[str, Any]:
        run = self.get_run(owner_id, space_id, run_id)
        if not run:
            raise KeyError("compilation run is unavailable")
        if run["status"] in TERMINAL_STATUSES:
            return run
        return self.transition(
            owner_id,
            space_id,
            run_id,
            "cancelled",
            allowed_from=ACTIVE_STATUSES,
            reason_code="cancelled_by_user",
        )

    def list_runs(
        self,
        owner_id: str,
        *,
        space_id: Optional[str] = None,
        outline_node_id: Optional[str] = None,
        statuses: Optional[Iterable[str]] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("limit must be within 1..500")
        params: list[Any] = [owner_id]
        where = ["owner_id=?"]
        if space_id is not None:
            where.append("space_id=?")
            params.append(space_id)
        if outline_node_id is not None:
            where.append("outline_node_id=?")
            params.append(outline_node_id)
        status_set = set(statuses or [])
        if status_set:
            if not status_set.issubset(RUN_STATUSES):
                raise ValueError("compilation statuses are invalid")
            where.append("status IN (" + ",".join("?" for _ in status_set) + ")")
            params.extend(sorted(status_set))
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM knowledge_core_compilation_runs WHERE "
                + " AND ".join(where)
                + " ORDER BY priority DESC, updated_at DESC, run_id DESC LIMIT ?",
                params,
            ).fetchall()
        return [self._row(row) or {} for row in rows]

    def reconcile_abandoned(self, owner_id: Optional[str] = None) -> int:
        """Fail process-owned running stages; queued work remains safe to resume."""
        params: list[Any] = [_now()]
        owner_clause = ""
        if owner_id is not None:
            owner_clause = " AND owner_id=?"
            params.append(owner_id)
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE knowledge_core_compilation_runs SET "
                "status='failed',reason_code='process_restarted',updated_at=? "
                "WHERE status IN ('reading','generating','validating')" + owner_clause,
                params,
            )
            return int(cursor.rowcount)

    def delete_owner(self, owner_id: str) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM knowledge_core_compilation_runs WHERE owner_id=?",
                (owner_id,),
            )
            return int(cursor.rowcount)


__all__ = [
    "ACTIVE_STATUSES",
    "KnowledgeCoreCompilationStore",
    "POLICY_VERSION",
    "RUN_STATUSES",
    "TERMINAL_STATUSES",
    "TRIGGERS",
    "default_compilation_db_path",
    "validate_compilation_request",
]
