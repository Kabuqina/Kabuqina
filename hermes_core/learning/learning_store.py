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
import os
import random
import sqlite3
import subprocess
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
    LIFECYCLE_STATUSES,
    is_allowed_transition,
    validate_envelope,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")
SPACE_STATUSES = frozenset({"active", "archived"})

_ACL_LOCK = threading.Lock()
_ACL_SECURED_ROOTS: set[Path] = set()
_ACL_SECURED_DATABASES: set[Path] = set()


def _windows_identity() -> str:
    identity = subprocess.run(
        ["whoami"],
        check=True,
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    ).stdout.strip()
    if not identity:
        raise PermissionError("cannot resolve Windows identity for learning.db ACL")
    return identity


def default_learning_db_path() -> Path:
    """Path to the shared ``learning.db`` under the common Hermes root.

    Uses :func:`get_default_hermes_root` (not ``HERMES_HOME``) so Desktop and
    Gateway profiles converge on one database — see design §8.2.
    """
    return get_default_hermes_root() / "learning.db"


def secure_default_learning_db(db_path: Path) -> None:
    """Restrict the production learning DB root to the current OS user.

    Windows uses ``icacls`` to remove inherited access and grant the current
    principal full control with inheritable child permissions. This covers
    SQLite's transient ``-wal``/``-shm`` files as well as ``learning.db``.
    POSIX uses the equivalent 0700 directory / 0600 file modes.

    The operation is cached per process and intentionally runs only for the
    default production path; callers that inject an explicit test/custom path
    retain responsibility for that path's policy.
    """
    path = Path(db_path).resolve()
    root = path.parent
    with _ACL_LOCK:
        if root in _ACL_SECURED_ROOTS:
            return
        if os.name == "nt":
            identity = _windows_identity()
            command = [
                "icacls",
                str(root),
                "/inheritance:r",
                "/grant:r",
                f"{identity}:(OI)(CI)F",
                "/Q",
            ]
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "icacls failed").strip()
                raise PermissionError(f"cannot secure learning.db ACL: {detail}")
        else:
            os.chmod(root, 0o700)
        _ACL_SECURED_ROOTS.add(root)


def secure_default_learning_db_files(db_path: Path) -> None:
    """Protect an existing DB and SQLite sidecars after schema setup."""
    path = Path(db_path).resolve()
    with _ACL_LOCK:
        if path in _ACL_SECURED_DATABASES:
            return
        if os.name == "nt":
            identity = _windows_identity()
            for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
                if not candidate.exists():
                    continue
                result = subprocess.run(
                    [
                        "icacls",
                        str(candidate),
                        "/inheritance:r",
                        "/grant:r",
                        f"{identity}:F",
                        "/Q",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if result.returncode != 0:
                    detail = (result.stderr or result.stdout or "icacls failed").strip()
                    raise PermissionError(f"cannot secure learning.db file ACL: {detail}")
        else:
            os.chmod(path, 0o600)
        _ACL_SECURED_DATABASES.add(path)


def audit_default_learning_db_acl(db_path: Path) -> bool:
    """Return whether the production DB has a non-inherited user-only ACL."""
    path = Path(db_path).resolve()
    if os.name == "nt":
        identity = _windows_identity().casefold()
        for candidate in (path.parent, path):
            result = subprocess.run(
                ["icacls", str(candidate)],
                check=False,
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if (
                result.returncode != 0
                or "(I)" in result.stdout
                or identity not in result.stdout.casefold()
                or "(F)" not in result.stdout
            ):
                return False
        return True
    root_mode = path.parent.stat().st_mode & 0o777
    file_mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    return root_mode == 0o700 and file_mode == 0o600


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


def _bundle_timestamp(row: Dict[str, Any], key: str) -> str:
    value = row.get(key)
    return _now() if value is None else _require(value, key)


def _bundle_optional_id(value: Any, name: str) -> Optional[str]:
    if value is None:
        return None
    return _require(value, name)


class LearningStore:
    """SQLite-backed store for the learning spine.

    Thread-safe for the common shape (multiple connections/processes, WAL).
    Each instance owns one connection; open a fresh instance per process/child.
    """

    _WRITE_MAX_RETRIES = 15
    _WRITE_RETRY_MIN_S = 0.020
    _WRITE_RETRY_MAX_S = 0.150

    def __init__(self, db_path: Optional[Path] = None):
        is_default_path = db_path is None
        self.db_path = Path(db_path) if db_path else default_learning_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if is_default_path:
            secure_default_learning_db(self.db_path)

        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=1.0,
            isolation_level=None,  # we manage transactions via BEGIN IMMEDIATE
        )
        self._conn.row_factory = sqlite3.Row
        self._setup_connection_with_retry()
        if is_default_path:
            secure_default_learning_db_files(self.db_path)

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
                # This is deliberately connection-local.  It makes DELETE and
                # UPDATE overwrite removed cell content instead of leaving it
                # recoverable in free pages or the WAL.
                self._conn.execute("PRAGMA secure_delete=ON")
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

    def artifact_summary_page(
        self,
        owner_id: str,
        space_id: str,
        *,
        kind: Optional[str],
        status: Optional[str],
        limit: int,
        offset: int,
    ) -> Dict[str, Any]:
        """Read one bounded page without loading artifact envelopes."""
        _require(owner_id, "owner_id")
        _require(space_id, "space_id")

        base = " FROM learning_artifacts WHERE owner_id = ? AND space_id = ?"
        base_params: List[Any] = [owner_id, space_id]
        if kind is not None:
            base += " AND kind = ?"
            base_params.append(kind)

        counts = {
            row["status"]: row["total"]
            for row in self._conn.execute(
                "SELECT status, COUNT(*) AS total" + base + " GROUP BY status",
                base_params,
            ).fetchall()
        }

        page_where = base
        page_params = list(base_params)
        if status is not None:
            page_where += " AND status = ?"
            page_params.append(status)
        kind_counts = {
            row["kind"]: row["total"]
            for row in self._conn.execute(
                "SELECT kind, COUNT(*) AS total" + page_where + " GROUP BY kind",
                page_params,
            ).fetchall()
        }
        rows = self._conn.execute(
            "SELECT artifact_id, kind, title, status, review_mode, "
            "review_status, updated_at"
            + page_where
            + " ORDER BY updated_at DESC, artifact_id DESC LIMIT ? OFFSET ?",
            [*page_params, limit, offset],
        ).fetchall()
        total = counts.get(status, 0) if status is not None else sum(counts.values())
        return {
            "rows": [dict(row) for row in rows],
            "count": total,
            "counts": counts,
            "kind_counts": kind_counts,
        }

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

    def update_artifact_review(
        self, owner_id: str, space_id: str, artifact_id: str, review_status: str,
        *, review_mode: Optional[str] = None,
    ) -> None:
        """Persist a trusted semantic-review conclusion for one owned draft."""
        if review_status not in {"pending", "passed", "failed"}:
            raise ValueError("invalid review status")
        now = _now()
        def _op(conn: sqlite3.Connection) -> None:
            row = conn.execute(
                "SELECT envelope_json FROM learning_artifacts WHERE owner_id = ? AND space_id = ? AND artifact_id = ?",
                (owner_id, space_id, artifact_id),
            ).fetchone()
            if not row:
                raise KeyError(f"artifact {artifact_id!r} not found")
            envelope = json.loads(row["envelope_json"])
            current_review = envelope.get("review") or {}
            mode = review_mode or current_review.get("mode") or "deterministic"
            envelope["review"] = {"mode": mode, "status": review_status}
            conn.execute(
                "UPDATE learning_artifacts SET review_mode = ?, review_status = ?, envelope_json = ?, updated_at = ? "
                "WHERE owner_id = ? AND space_id = ? AND artifact_id = ?",
                (mode, review_status, json.dumps(envelope, ensure_ascii=False), now, owner_id, space_id, artifact_id),
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

    # ── owner governance / portability ───────────────────────────────── #

    def export_owner_bundle(self, owner_id: str) -> Dict[str, Any]:
        """Return a self-contained JSON-safe bundle without repeating owner_id."""
        _require(owner_id, "owner_id")
        tables = {
            "spaces": (
                "learning_spaces",
                ("space_id", "title", "status", "is_current", "created_at", "updated_at"),
            ),
            "artifacts": (
                "learning_artifacts",
                (
                    "space_id", "artifact_id", "kind", "title", "version", "status",
                    "review_mode", "review_status", "envelope_json", "created_at",
                    "updated_at",
                ),
            ),
            "items": (
                "learning_items",
                (
                    "space_id", "item_id", "artifact_id", "item_type", "state_json",
                    "created_at", "updated_at",
                ),
            ),
            "activities": (
                "learning_activities",
                (
                    "space_id", "activity_id", "activity_type", "artifact_id", "item_id",
                    "detail_json", "created_at",
                ),
            ),
            "migrations": (
                "learning_migrations",
                ("migration_key", "status", "detail_json", "created_at"),
            ),
        }
        bundle: Dict[str, Any] = {"version": 1}
        for key, (table, columns) in tables.items():
            sql = f"SELECT {', '.join(columns)} FROM {table} WHERE owner_id = ?"
            rows = [dict(row) for row in self._conn.execute(sql, (owner_id,)).fetchall()]
            for row in rows:
                for field in ("envelope_json", "state_json", "detail_json"):
                    if field in row:
                        row[field.removesuffix("_json")] = json.loads(row.pop(field))
            bundle[key] = rows
        return bundle

    def delete_owner_data(self, owner_id: str) -> Dict[str, int]:
        _require(owner_id, "owner_id")
        counts: Dict[str, int] = {}

        def _op(conn: sqlite3.Connection) -> None:
            for table in (
                "learning_activities",
                "learning_items",
                "learning_artifacts",
                "learning_spaces",
                "learning_migrations",
            ):
                cur = conn.execute(f"DELETE FROM {table} WHERE owner_id = ?", (owner_id,))
                counts[table] = cur.rowcount

        self._execute_write(_op)
        self._compact_after_sensitive_delete()
        return counts

    def _compact_after_sensitive_delete(self) -> None:
        """Remove deleted learning content from the database and WAL files.

        ``secure_delete`` clears deleted cells, while the checkpoint/VACUUM/
        checkpoint sequence removes historical WAL frames and free pages.  A
        caller must not report a successful "delete all" until this completes.
        """
        last_err: Optional[Exception] = None
        for attempt in range(self._WRITE_MAX_RETRIES):
            try:
                with self._lock:
                    before = self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                    if before and before[0] != 0:
                        raise sqlite3.OperationalError("WAL checkpoint remained busy")
                    self._conn.execute("VACUUM")
                    after = self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                    if after and after[0] != 0:
                        raise sqlite3.OperationalError("WAL checkpoint remained busy")
                return
            except sqlite3.OperationalError as exc:
                if attempt < self._WRITE_MAX_RETRIES - 1:
                    last_err = exc
                    time.sleep(
                        random.uniform(
                            self._WRITE_RETRY_MIN_S, self._WRITE_RETRY_MAX_S
                        )
                    )
                    continue
                raise RuntimeError(
                    "learning data was deleted but physical database cleanup failed"
                ) from exc
        raise RuntimeError("learning database cleanup failed") from last_err

    def import_owner_bundle(self, owner_id: str, bundle: Dict[str, Any]) -> Dict[str, int]:
        """Restore a v1 owner bundle into an empty owner scope, forcing ownership."""
        _require(owner_id, "owner_id")
        if not isinstance(bundle, dict) or bundle.get("version") != 1:
            raise ValueError("unsupported learning bundle")
        if (
            len(json.dumps(bundle, ensure_ascii=False).encode("utf-8"))
            > 16 * 1024 * 1024
        ):
            raise ValueError("learning bundle exceeds 16 MiB")
        sections = ("spaces", "artifacts", "items", "activities", "migrations")
        rows_by_section: Dict[str, List[Any]] = {}
        for section in sections:
            rows = bundle.get(section, [])
            if not isinstance(rows, list):
                raise ValueError(f"bundle {section} must be an array")
            rows_by_section[section] = rows
        counts = {key: 0 for key in sections}

        def _op(conn: sqlite3.Connection) -> None:
            for table in (
                "learning_spaces",
                "learning_artifacts",
                "learning_items",
                "learning_activities",
                "learning_migrations",
            ):
                if conn.execute(
                    f"SELECT 1 FROM {table} WHERE owner_id = ? LIMIT 1",
                    (owner_id,),
                ).fetchone():
                    raise ValueError(
                        "owner already has learning data; delete it before import"
                    )

            space_ids: set[str] = set()
            current_spaces = 0
            for row in rows_by_section["spaces"]:
                if not isinstance(row, dict):
                    raise ValueError("bundle space must be an object")
                sid = _require(row.get("space_id"), "space_id")
                if sid in space_ids:
                    raise ValueError("bundle contains duplicate space_id")
                space_ids.add(sid)
                title = _require(row.get("title"), "title")
                if len(title) > 300:
                    raise ValueError("title exceeds 300 chars")
                status = row.get("status", "active")
                if not isinstance(status, str) or status not in SPACE_STATUSES:
                    raise ValueError("invalid space status")
                raw_current = row.get("is_current", False)
                if type(raw_current) is bool:
                    is_current = int(raw_current)
                elif type(raw_current) is int and raw_current in {0, 1}:
                    is_current = raw_current
                else:
                    raise ValueError("is_current must be a boolean or 0/1")
                current_spaces += is_current
                if current_spaces > 1:
                    raise ValueError("bundle may contain at most one current space")
                conn.execute(
                    "INSERT INTO learning_spaces (owner_id,space_id,title,status,is_current,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                    (
                        owner_id,
                        sid,
                        title,
                        status,
                        is_current,
                        _bundle_timestamp(row, "created_at"),
                        _bundle_timestamp(row, "updated_at"),
                    ),
                )
                counts["spaces"] += 1

            artifact_keys: set[tuple[str, str]] = set()
            for row in rows_by_section["artifacts"]:
                if not isinstance(row, dict):
                    raise ValueError("bundle artifact must be an object")
                sid = _require(row.get("space_id"), "space_id")
                if sid not in space_ids:
                    raise ValueError("artifact references unknown space")
                envelope = row.get("envelope") or {}
                if not isinstance(envelope, dict):
                    raise ValueError("artifact envelope must be an object")
                env = validate_envelope({**envelope, "space_id": sid})
                aid = _require(row.get("artifact_id"), "artifact_id")
                artifact_key = (sid, aid)
                if artifact_key in artifact_keys:
                    raise ValueError("bundle contains duplicate artifact_id within a space")
                artifact_keys.add(artifact_key)
                status = row.get("status", INITIAL_STATUS)
                if not isinstance(status, str) or status not in LIFECYCLE_STATUSES:
                    raise ValueError("invalid artifact status")
                for key, expected in (
                    ("kind", env.kind),
                    ("title", env.title),
                    ("version", env.version),
                    ("review_mode", env.review["mode"]),
                    ("review_status", env.review["status"]),
                ):
                    if key in row and row[key] != expected:
                        raise ValueError(f"artifact {key} disagrees with envelope")
                env_dict = env.to_dict()
                conn.execute(
                    "INSERT INTO learning_artifacts (owner_id,space_id,artifact_id,kind,title,version,status,review_mode,review_status,envelope_json,source_refs_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        owner_id,
                        sid,
                        aid,
                        env.kind,
                        env.title,
                        env.version,
                        status,
                        env.review["mode"],
                        env.review["status"],
                        json.dumps(env_dict, ensure_ascii=False),
                        json.dumps(env.source_refs, ensure_ascii=False),
                        _bundle_timestamp(row, "created_at"),
                        _bundle_timestamp(row, "updated_at"),
                    ),
                )
                counts["artifacts"] += 1

            item_keys: set[tuple[str, str]] = set()
            for row in rows_by_section["items"]:
                if not isinstance(row, dict):
                    raise ValueError("bundle item must be an object")
                sid = _require(row.get("space_id"), "space_id")
                if sid not in space_ids:
                    raise ValueError("item references unknown space")
                artifact_id = _bundle_optional_id(row.get("artifact_id"), "artifact_id")
                if artifact_id and (sid, artifact_id) not in artifact_keys:
                    raise ValueError("item references unknown artifact")
                item_id = _require(row.get("item_id"), "item_id")
                item_key = (sid, item_id)
                if item_key in item_keys:
                    raise ValueError("bundle contains duplicate item_id within a space")
                item_keys.add(item_key)
                state = row.get("state") or {}
                if not isinstance(state, dict):
                    raise ValueError("item state must be an object")
                conn.execute(
                    "INSERT INTO learning_items (owner_id,space_id,item_id,artifact_id,item_type,state_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        owner_id,
                        sid,
                        item_id,
                        artifact_id,
                        _require(row.get("item_type"), "item_type"),
                        json.dumps(state, ensure_ascii=False),
                        _bundle_timestamp(row, "created_at"),
                        _bundle_timestamp(row, "updated_at"),
                    ),
                )
                counts["items"] += 1

            activity_keys: set[tuple[str, str]] = set()
            for row in rows_by_section["activities"]:
                if not isinstance(row, dict):
                    raise ValueError("bundle activity must be an object")
                sid = _require(row.get("space_id"), "space_id")
                if sid not in space_ids:
                    raise ValueError("activity references unknown space")
                artifact_id = _bundle_optional_id(row.get("artifact_id"), "artifact_id")
                item_id = _bundle_optional_id(row.get("item_id"), "item_id")
                activity_id = _require(row.get("activity_id"), "activity_id")
                activity_key = (sid, activity_id)
                if activity_key in activity_keys:
                    raise ValueError("bundle contains duplicate activity_id within a space")
                activity_keys.add(activity_key)
                # Activity evidence intentionally survives artifact/item cleanup,
                # so these two references are weak and may be dangling in a
                # valid exported bundle.
                detail = row.get("detail") or {}
                if not isinstance(detail, dict):
                    raise ValueError("activity detail must be an object")
                conn.execute(
                    "INSERT INTO learning_activities (owner_id,space_id,activity_id,activity_type,artifact_id,item_id,detail_json,created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        owner_id,
                        sid,
                        activity_id,
                        _require(row.get("activity_type"), "activity_type"),
                        artifact_id,
                        item_id,
                        json.dumps(detail, ensure_ascii=False),
                        _bundle_timestamp(row, "created_at"),
                    ),
                )
                counts["activities"] += 1

            migration_keys: set[str] = set()
            for row in rows_by_section["migrations"]:
                if not isinstance(row, dict):
                    raise ValueError("bundle migration must be an object")
                status = row.get("status", "done")
                if not isinstance(status, str) or status not in {"done", "failed"}:
                    raise ValueError("invalid migration status")
                detail = row.get("detail") or {}
                if not isinstance(detail, dict):
                    raise ValueError("migration detail must be an object")
                migration_key = _require(row.get("migration_key"), "migration_key")
                if migration_key in migration_keys:
                    raise ValueError("bundle contains duplicate migration_key")
                migration_keys.add(migration_key)
                conn.execute(
                    "INSERT INTO learning_migrations (owner_id,migration_key,status,detail_json,created_at) VALUES (?,?,?,?,?)",
                    (
                        owner_id,
                        migration_key,
                        status,
                        json.dumps(detail, ensure_ascii=False),
                        _bundle_timestamp(row, "created_at"),
                    ),
                )
                counts["migrations"] += 1

        self._execute_write(_op)
        return counts

    def list_migrations(
        self, owner_id: str, *, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        _require(owner_id, "owner_id")
        sql = (
            "SELECT migration_key, status, detail_json, created_at "
            "FROM learning_migrations WHERE owner_id = ?"
        )
        params: List[Any] = [owner_id]
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC"
        out = []
        for row in self._conn.execute(sql, params).fetchall():
            item = dict(row)
            item["detail"] = json.loads(item.pop("detail_json"))
            out.append(item)
        return out

    def activity_summary_page(
        self, owner_id: str, space_id: str, *, limit: int
    ) -> Dict[str, Any]:
        """Return a bounded newest-first activity page without detail content."""
        _require(owner_id, "owner_id")
        _require(space_id, "space_id")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit must be within 1..100")
        where = " FROM learning_activities WHERE owner_id = ? AND space_id = ?"
        params = (owner_id, space_id)
        total = self._conn.execute("SELECT COUNT(*)" + where, params).fetchone()[0]
        rows = self._conn.execute(
            "SELECT activity_id, activity_type, artifact_id, item_id, created_at"
            + where
            + " ORDER BY created_at DESC, activity_id DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        return {
            "rows": [dict(row) for row in rows],
            "count": total,
        }

    def quiz_attempt_page(
        self, owner_id: str, space_id: str, *, limit: int
    ) -> Dict[str, Any]:
        """Return one newest-first bounded quiz-attempt evidence page."""
        _require(owner_id, "owner_id")
        _require(space_id, "space_id")
        where = (
            " FROM learning_activities WHERE owner_id = ? AND space_id = ? "
            "AND activity_type = 'quiz.attempt'"
        )
        params = (owner_id, space_id)
        total = self._conn.execute("SELECT COUNT(*)" + where, params).fetchone()[0]
        rows = self._conn.execute(
            "SELECT activity_id, artifact_id, created_at, detail_json"
            + where
            + " ORDER BY created_at DESC, activity_id DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        return {
            "rows": [
                {
                    "activity_id": row["activity_id"],
                    "artifact_id": row["artifact_id"],
                    "created_at": row["created_at"],
                    "detail": json.loads(row["detail_json"]),
                }
                for row in rows
            ],
            "count": total,
        }

    def quiz_attempt_by_id(
        self, owner_id: str, space_id: str, activity_id: str
    ) -> Optional[Dict[str, Any]]:
        """Return one scoped quiz-attempt row for retry routing only."""
        _require(owner_id, "owner_id")
        _require(space_id, "space_id")
        _require(activity_id, "activity_id")
        row = self._conn.execute(
            "SELECT activity_id, artifact_id, detail_json "
            "FROM learning_activities "
            "WHERE owner_id = ? AND space_id = ? AND activity_id = ? "
            "AND activity_type = 'quiz.attempt'",
            (owner_id, space_id, activity_id),
        ).fetchone()
        if not row:
            return None
        return {
            "activity_id": row["activity_id"],
            "artifact_id": row["artifact_id"],
            "detail": json.loads(row["detail_json"]),
        }

    def mark_migration_failure(
        self, owner_id: str, migration_key: str, detail: Dict[str, Any]
    ) -> None:
        _require(owner_id, "owner_id")
        _require(migration_key, "migration_key")
        now = _now()

        def _op(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT OR REPLACE INTO learning_migrations (owner_id, migration_key, status, detail_json, created_at) VALUES (?, ?, 'failed', ?, ?)",
                (owner_id, migration_key, json.dumps(detail, ensure_ascii=False), now),
            )
        self._execute_write(_op)
