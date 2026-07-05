"""Isolated ``learning.db`` store for the STUDY learning foundation.

A separate SQLite database under the *common* Hermes root (not ``state.db`` and
not the profile-specific ``HERMES_HOME``), so Desktop and Gateway share one
learning spine. Reuses SessionDB's concurrency principles: WAL journal, short
SQLite timeout with application-level ``BEGIN IMMEDIATE`` + jittered retry, and
declarative startup column reconciliation.

Every space-scoped read and write is constrained by **both** ``owner_id`` and
``space_id``. Owner isolation is structural: cross-owner or cross-space reads
return nothing. This layer is trusted infrastructure — the owner is supplied by
:class:`~learning.learning_context.LearningExecutionContext`, never by a model.
"""

from __future__ import annotations

import json
import logging
import random
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

from hermes_constants import get_default_hermes_root
from learning.learning_contract import (
    ContractError,
    INITIAL_STATUS,
    is_allowed_transition,
    validate_envelope,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


def default_learning_db_path() -> Path:
    """Path to the shared ``learning.db`` under the common Hermes root.

    Uses :func:`get_default_hermes_root` (not ``HERMES_HOME``) so Desktop and
    Gateway profiles converge on one database — see design §8.2.
    """
    return get_default_hermes_root() / "learning.db"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS learning_spaces (
    owner_id   TEXT NOT NULL,
    space_id   TEXT NOT NULL,
    title      TEXT NOT NULL DEFAULT '',
    status     TEXT NOT NULL DEFAULT 'active',
    is_current INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (owner_id, space_id)
);

CREATE TABLE IF NOT EXISTS learning_artifacts (
    owner_id         TEXT NOT NULL,
    space_id         TEXT NOT NULL,
    artifact_id      TEXT NOT NULL,
    kind             TEXT NOT NULL DEFAULT '',
    title            TEXT NOT NULL DEFAULT '',
    version          INTEGER NOT NULL DEFAULT 1,
    status           TEXT NOT NULL DEFAULT 'draft',
    review_mode      TEXT NOT NULL DEFAULT 'deterministic',
    review_status    TEXT NOT NULL DEFAULT 'pending',
    envelope_json    TEXT NOT NULL DEFAULT '{}',
    source_refs_json TEXT NOT NULL DEFAULT '[]',
    created_at       TEXT NOT NULL DEFAULT '',
    updated_at       TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (owner_id, space_id, artifact_id)
);

CREATE TABLE IF NOT EXISTS learning_items (
    owner_id    TEXT NOT NULL,
    space_id    TEXT NOT NULL,
    item_id     TEXT NOT NULL,
    artifact_id TEXT,
    item_type   TEXT NOT NULL DEFAULT '',
    state_json  TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL DEFAULT '',
    updated_at  TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (owner_id, space_id, item_id)
);

CREATE TABLE IF NOT EXISTS learning_activities (
    owner_id      TEXT NOT NULL,
    space_id      TEXT NOT NULL,
    activity_id   TEXT NOT NULL,
    activity_type TEXT NOT NULL DEFAULT '',
    artifact_id   TEXT,
    item_id       TEXT,
    detail_json   TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (owner_id, space_id, activity_id)
);

CREATE TABLE IF NOT EXISTS learning_migrations (
    owner_id      TEXT NOT NULL,
    migration_key TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'done',
    detail_json   TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (owner_id, migration_key)
);

CREATE TABLE IF NOT EXISTS learning_schema_version (
    version INTEGER NOT NULL DEFAULT 1
);
"""

# Indexes are created *after* column reconciliation so that opening an older db
# (missing an indexed column) reconciles the column first instead of failing.
INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_learning_artifacts_kind
    ON learning_artifacts (owner_id, space_id, kind);
CREATE INDEX IF NOT EXISTS idx_learning_artifacts_status
    ON learning_artifacts (owner_id, space_id, status);
CREATE INDEX IF NOT EXISTS idx_learning_items_artifact
    ON learning_items (owner_id, space_id, artifact_id);
CREATE INDEX IF NOT EXISTS idx_learning_activities_scope
    ON learning_activities (owner_id, space_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


class LearningStore:
    """SQLite-backed store for the learning spine.

    Thread-safe for the common shape (multiple connections/processes, WAL).
    Each instance owns one connection; open a fresh instance per process/child.
    """

    _WRITE_MAX_RETRIES = 15
    _WRITE_RETRY_MIN_S = 0.020
    _WRITE_RETRY_MAX_S = 0.150

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else default_learning_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=1.0,
            isolation_level=None,  # we manage transactions via BEGIN IMMEDIATE
        )
        self._conn.row_factory = sqlite3.Row
        self._setup_connection_with_retry()

    # ── connection / schema ────────────────────────────────────────────── #

    def journal_mode(self) -> str:
        return self._conn.execute("PRAGMA journal_mode").fetchone()[0]

    def table_columns(self, table: str) -> set:
        return {
            r[1] for r in self._conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        }

    def _setup_connection_with_retry(self) -> None:
        """Set WAL/foreign-keys pragmas and initialize the schema, tolerating
        concurrent first-time setup.

        When two children open the *same fresh* ``learning.db`` at once, the
        contended step is ``PRAGMA journal_mode=WAL`` (switching journal mode
        needs exclusive access) — and the schema writes that follow. All of it
        is idempotent: WAL is a persistent db property so the loser sees WAL
        already set on retry, ``CREATE/INDEX IF NOT EXISTS`` are no-ops,
        reconcile checks existence, and the version row is guarded. So we retry
        the whole setup with jitter — the convoy-avoiding strategy used for
        writes — and it converges once any child wins.
        """
        last_err: Optional[Exception] = None
        for attempt in range(self._WRITE_MAX_RETRIES):
            try:
                self._conn.execute("PRAGMA journal_mode=WAL")
                self._conn.execute("PRAGMA foreign_keys=ON")
                self._init_schema()
                return
            except sqlite3.OperationalError as exc:
                msg = str(exc).lower()
                if ("locked" in msg or "busy" in msg) and attempt < self._WRITE_MAX_RETRIES - 1:
                    last_err = exc
                    try:
                        self._conn.rollback()
                    except Exception:
                        pass
                    time.sleep(random.uniform(self._WRITE_RETRY_MIN_S, self._WRITE_RETRY_MAX_S))
                    continue
                raise
        raise last_err or sqlite3.OperationalError("schema setup locked after max retries")

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.executescript(SCHEMA_SQL)
        self._reconcile_columns(cur)
        cur.executescript(INDEXES_SQL)
        # Seed the schema version row exactly once.
        if not cur.execute("SELECT 1 FROM learning_schema_version").fetchone():
            cur.execute("INSERT INTO learning_schema_version (version) VALUES (1)")
        self._conn.commit()

    def _reconcile_columns(self, cursor: sqlite3.Cursor) -> None:
        """Add any column declared in SCHEMA_SQL that is missing from a live
        table. Declarative, idempotent, self-healing (Beets/sqlite-utils
        pattern). All NOT NULL columns carry DEFAULTs so ADD COLUMN is safe.
        """
        for table, declared in self._parse_schema_columns(SCHEMA_SQL).items():
            try:
                rows = cursor.execute(f'PRAGMA table_info("{table}")').fetchall()
            except sqlite3.OperationalError:
                continue
            live = {r[1] for r in rows}
            for col_name, col_decl in declared.items():
                if col_name not in live:
                    safe = col_name.replace('"', '""')
                    try:
                        cursor.execute(
                            f'ALTER TABLE "{table}" ADD COLUMN "{safe}" {col_decl}'
                        )
                    except sqlite3.OperationalError as exc:
                        logger.debug("reconcile %s.%s: %s", table, col_name, exc)

    @staticmethod
    def _parse_schema_columns(schema_sql: str) -> Dict[str, Dict[str, str]]:
        ref = sqlite3.connect(":memory:")
        try:
            ref.executescript(schema_sql)
            out: Dict[str, Dict[str, str]] = {}
            for (tbl,) in ref.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            ).fetchall():
                cols: Dict[str, str] = {}
                for row in ref.execute(f'PRAGMA table_info("{tbl}")').fetchall():
                    _, name, ctype, notnull, default, pk = row
                    parts = [ctype] if ctype else []
                    if notnull and not pk:
                        parts.append("NOT NULL")
                    if default is not None:
                        parts.append(f"DEFAULT {default}")
                    cols[name] = " ".join(parts)
                out[tbl] = cols
            return out
        finally:
            ref.close()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
                except Exception:
                    pass
                self._conn.close()
                self._conn = None

    # ── write helper ───────────────────────────────────────────────────── #

    def _execute_write(self, fn: Callable[[sqlite3.Connection], T]) -> T:
        """Run a write inside ``BEGIN IMMEDIATE`` with jittered retry on lock."""
        last_err: Optional[Exception] = None
        for attempt in range(self._WRITE_MAX_RETRIES):
            try:
                with self._lock:
                    self._conn.execute("BEGIN IMMEDIATE")
                    try:
                        result = fn(self._conn)
                        self._conn.commit()
                    except BaseException:
                        try:
                            self._conn.rollback()
                        except Exception:
                            pass
                        raise
                return result
            except sqlite3.OperationalError as exc:
                msg = str(exc).lower()
                if ("locked" in msg or "busy" in msg) and attempt < self._WRITE_MAX_RETRIES - 1:
                    last_err = exc
                    time.sleep(random.uniform(self._WRITE_RETRY_MIN_S, self._WRITE_RETRY_MAX_S))
                    continue
                raise
        raise last_err or sqlite3.OperationalError("database is locked after max retries")

    # ── spaces ─────────────────────────────────────────────────────────── #

    def create_space(
        self,
        owner_id: str,
        *,
        title: str,
        space_id: Optional[str] = None,
        make_current: bool = True,
    ) -> str:
        _require(owner_id, "owner_id")
        _require(title, "title")
        sid = space_id or uuid.uuid4().hex
        now = _now()

        def _op(conn: sqlite3.Connection) -> str:
            conn.execute(
                "INSERT OR REPLACE INTO learning_spaces "
                "(owner_id, space_id, title, status, is_current, created_at, updated_at) "
                "VALUES (?, ?, ?, 'active', 0, ?, ?)",
                (owner_id, sid, title, now, now),
            )
            if make_current:
                conn.execute(
                    "UPDATE learning_spaces SET is_current = 0 WHERE owner_id = ?",
                    (owner_id,),
                )
                conn.execute(
                    "UPDATE learning_spaces SET is_current = 1 "
                    "WHERE owner_id = ? AND space_id = ?",
                    (owner_id, sid),
                )
            return sid

        return self._execute_write(_op)

    def get_space(self, owner_id: str, space_id: str) -> Optional[Dict[str, Any]]:
        _require(owner_id, "owner_id")
        _require(space_id, "space_id")
        row = self._conn.execute(
            "SELECT * FROM learning_spaces WHERE owner_id = ? AND space_id = ?",
            (owner_id, space_id),
        ).fetchone()
        return dict(row) if row else None

    def list_spaces(self, owner_id: str) -> List[Dict[str, Any]]:
        _require(owner_id, "owner_id")
        return [
            dict(r)
            for r in self._conn.execute(
                "SELECT * FROM learning_spaces WHERE owner_id = ? ORDER BY created_at",
                (owner_id,),
            ).fetchall()
        ]

    def set_current_space(self, owner_id: str, space_id: str) -> None:
        _require(owner_id, "owner_id")
        _require(space_id, "space_id")

        def _op(conn: sqlite3.Connection) -> None:
            row = conn.execute(
                "SELECT 1 FROM learning_spaces WHERE owner_id = ? AND space_id = ?",
                (owner_id, space_id),
            ).fetchone()
            if not row:
                raise KeyError(f"space {space_id!r} not found for owner")
            conn.execute(
                "UPDATE learning_spaces SET is_current = 0 WHERE owner_id = ?",
                (owner_id,),
            )
            conn.execute(
                "UPDATE learning_spaces SET is_current = 1 "
                "WHERE owner_id = ? AND space_id = ?",
                (owner_id, space_id),
            )

        self._execute_write(_op)

    def get_current_space(self, owner_id: str) -> Optional[str]:
        _require(owner_id, "owner_id")
        row = self._conn.execute(
            "SELECT space_id FROM learning_spaces "
            "WHERE owner_id = ? AND is_current = 1",
            (owner_id,),
        ).fetchone()
        return row[0] if row else None

    # ── artifacts ──────────────────────────────────────────────────────── #

    def insert_artifact(
        self, owner_id: str, space_id: str, envelope: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate + persist a new artifact as ``draft`` under (owner, space).

        The envelope's ``space_id`` is forced to the scoping argument; any
        model-supplied identity fields in the envelope are ignored.
        """
        _require(owner_id, "owner_id")
        _require(space_id, "space_id")
        if not isinstance(envelope, dict):
            raise ContractError("envelope must be an object")

        env = validate_envelope({**envelope, "space_id": space_id})
        artifact_id = uuid.uuid4().hex
        now = _now()
        env_dict = env.to_dict()

        def _op(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT INTO learning_artifacts "
                "(owner_id, space_id, artifact_id, kind, title, version, status, "
                " review_mode, review_status, envelope_json, source_refs_json, "
                " created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)",
                (
                    owner_id,
                    space_id,
                    artifact_id,
                    env.kind,
                    env.title,
                    INITIAL_STATUS,
                    env.review["mode"],
                    env.review["status"],
                    json.dumps(env_dict, ensure_ascii=False),
                    json.dumps(env.source_refs, ensure_ascii=False),
                    now,
                    now,
                ),
            )

        self._execute_write(_op)
        return {"artifact_id": artifact_id, "version": 1}

    def _row_to_artifact(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "artifact_id": row["artifact_id"],
            "space_id": row["space_id"],
            "kind": row["kind"],
            "title": row["title"],
            "version": row["version"],
            "status": row["status"],
            "review": {"mode": row["review_mode"], "status": row["review_status"]},
            "envelope": json.loads(row["envelope_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_artifact(
        self, owner_id: str, space_id: str, artifact_id: str
    ) -> Optional[Dict[str, Any]]:
        _require(owner_id, "owner_id")
        _require(space_id, "space_id")
        _require(artifact_id, "artifact_id")
        row = self._conn.execute(
            "SELECT * FROM learning_artifacts "
            "WHERE owner_id = ? AND space_id = ? AND artifact_id = ?",
            (owner_id, space_id, artifact_id),
        ).fetchone()
        return self._row_to_artifact(row) if row else None

    def list_artifacts(
        self,
        owner_id: str,
        space_id: str,
        *,
        kind: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        _require(owner_id, "owner_id")
        _require(space_id, "space_id")
        sql = "SELECT * FROM learning_artifacts WHERE owner_id = ? AND space_id = ?"
        params: List[Any] = [owner_id, space_id]
        if kind is not None:
            sql += " AND kind = ?"
            params.append(kind)
        if status is not None:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY created_at"
        return [
            self._row_to_artifact(r)
            for r in self._conn.execute(sql, params).fetchall()
        ]

    def update_artifact_status(
        self, owner_id: str, space_id: str, artifact_id: str, new_status: str
    ) -> None:
        """Enforce an allowed lifecycle transition on an owned artifact.

        Trusted-caller operation (activate/reject/archive) — never exposed as a
        model tool. Raises :class:`KeyError` if the artifact is not owned/scoped,
        :class:`ContractError` on an illegal transition.
        """
        _require(owner_id, "owner_id")
        _require(space_id, "space_id")
        _require(artifact_id, "artifact_id")
        now = _now()

        def _op(conn: sqlite3.Connection) -> None:
            row = conn.execute(
                "SELECT status FROM learning_artifacts "
                "WHERE owner_id = ? AND space_id = ? AND artifact_id = ?",
                (owner_id, space_id, artifact_id),
            ).fetchone()
            if not row:
                raise KeyError(f"artifact {artifact_id!r} not found for owner/space")
            current = row["status"]
            if not is_allowed_transition(current, new_status):
                raise ContractError(
                    f"illegal transition {current!r} -> {new_status!r}"
                )
            conn.execute(
                "UPDATE learning_artifacts SET status = ?, updated_at = ? "
                "WHERE owner_id = ? AND space_id = ? AND artifact_id = ?",
                (new_status, now, owner_id, space_id, artifact_id),
            )

        self._execute_write(_op)

    # ── items ─────────────────────────────────────────────────────────── #

    def upsert_item(
        self,
        owner_id: str,
        space_id: str,
        *,
        item_id: str,
        item_type: str,
        artifact_id: Optional[str] = None,
        state: Optional[Dict[str, Any]] = None,
    ) -> str:
        _require(owner_id, "owner_id")
        _require(space_id, "space_id")
        _require(item_id, "item_id")
        _require(item_type, "item_type")
        state_json = json.dumps(state or {}, ensure_ascii=False)
        now = _now()

        def _op(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT INTO learning_items "
                "(owner_id, space_id, item_id, artifact_id, item_type, state_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(owner_id, space_id, item_id) DO UPDATE SET "
                "artifact_id = excluded.artifact_id, "
                "item_type = excluded.item_type, "
                "state_json = excluded.state_json, "
                "updated_at = excluded.updated_at",
                (
                    owner_id,
                    space_id,
                    item_id,
                    artifact_id,
                    item_type,
                    state_json,
                    now,
                    now,
                ),
            )

        self._execute_write(_op)
        return item_id

    def _row_to_item(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        d["state"] = json.loads(d.pop("state_json") or "{}")
        return d

    def list_items(
        self,
        owner_id: str,
        space_id: str,
        *,
        item_type: Optional[str] = None,
        artifact_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        _require(owner_id, "owner_id")
        _require(space_id, "space_id")
        sql = "SELECT * FROM learning_items WHERE owner_id = ? AND space_id = ?"
        params: List[Any] = [owner_id, space_id]
        if item_type is not None:
            sql += " AND item_type = ?"
            params.append(item_type)
        if artifact_id is not None:
            sql += " AND artifact_id = ?"
            params.append(artifact_id)
        sql += " ORDER BY created_at, item_id"
        return [
            self._row_to_item(r)
            for r in self._conn.execute(sql, params).fetchall()
        ]

    def update_item_state(
        self,
        owner_id: str,
        space_id: str,
        item_id: str,
        state: Dict[str, Any],
    ) -> None:
        _require(owner_id, "owner_id")
        _require(space_id, "space_id")
        _require(item_id, "item_id")
        state_json = json.dumps(state or {}, ensure_ascii=False)
        now = _now()

        def _op(conn: sqlite3.Connection) -> None:
            cur = conn.execute(
                "UPDATE learning_items SET state_json = ?, updated_at = ? "
                "WHERE owner_id = ? AND space_id = ? AND item_id = ?",
                (state_json, now, owner_id, space_id, item_id),
            )
            if cur.rowcount == 0:
                raise KeyError(f"item {item_id!r} not found for owner/space")

        self._execute_write(_op)

    # ── activities ─────────────────────────────────────────────────────── #

    def insert_activity(
        self,
        owner_id: str,
        space_id: str,
        *,
        activity_type: str,
        artifact_id: Optional[str] = None,
        item_id: Optional[str] = None,
        detail: Optional[Dict[str, Any]] = None,
    ) -> str:
        _require(owner_id, "owner_id")
        _require(space_id, "space_id")
        _require(activity_type, "activity_type")
        activity_id = uuid.uuid4().hex
        now = _now()

        def _op(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT INTO learning_activities "
                "(owner_id, space_id, activity_id, activity_type, artifact_id, "
                " item_id, detail_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    owner_id,
                    space_id,
                    activity_id,
                    activity_type,
                    artifact_id,
                    item_id,
                    json.dumps(detail or {}, ensure_ascii=False),
                    now,
                ),
            )

        self._execute_write(_op)
        return activity_id

    def list_activities(self, owner_id: str, space_id: str) -> List[Dict[str, Any]]:
        _require(owner_id, "owner_id")
        _require(space_id, "space_id")
        rows = self._conn.execute(
            "SELECT * FROM learning_activities "
            "WHERE owner_id = ? AND space_id = ? ORDER BY created_at",
            (owner_id, space_id),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["detail"] = json.loads(d.pop("detail_json"))
            out.append(d)
        return out

    # ── migrations ─────────────────────────────────────────────────────── #

    def mark_migration(
        self, owner_id: str, migration_key: str, *, detail: Optional[Dict[str, Any]] = None
    ) -> None:
        _require(owner_id, "owner_id")
        _require(migration_key, "migration_key")
        now = _now()

        def _op(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT OR REPLACE INTO learning_migrations "
                "(owner_id, migration_key, status, detail_json, created_at) "
                "VALUES (?, ?, 'done', ?, ?)",
                (owner_id, migration_key, json.dumps(detail or {}, ensure_ascii=False), now),
            )

        self._execute_write(_op)

    def is_migrated(self, owner_id: str, migration_key: str) -> bool:
        _require(owner_id, "owner_id")
        _require(migration_key, "migration_key")
        row = self._conn.execute(
            "SELECT 1 FROM learning_migrations "
            "WHERE owner_id = ? AND migration_key = ? AND status = 'done'",
            (owner_id, migration_key),
        ).fetchone()
        return row is not None
