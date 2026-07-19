"""Persistent cross-process fences for composite learning data operations.

Every guard owns a ``BEGIN IMMEDIATE`` transaction for its full lifetime.  A
normal read/write therefore cannot pass its fence check and then race an
operation installing a fence in another Python process.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import threading
import time
from datetime import datetime, timezone
from types import TracebackType
from typing import Any, Mapping
import uuid

from .tutor_contract import canonical_json_bytes


COORDINATION_SCHEMA_VERSION = 1
MAX_RECOVERED_OPERATIONS = 100
MAX_ROLLBACK_MANIFEST_BYTES = 64 * 1024
OPERATION_KINDS = frozenset({"delete", "full_import", "runtime_restore"})

_OPAQUE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_PHASE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ACL_LOCK = threading.Lock()
_SECURED_ROOTS: set[Path] = set()
_SECURED_FILES: set[Path] = set()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS learning_operation_fences (
    operation_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    space_id TEXT NOT NULL DEFAULT '',
    operation TEXT NOT NULL CHECK (
        operation IN ('delete', 'full_import', 'runtime_restore')
    ),
    phase TEXT NOT NULL,
    bundle_sha256 TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (owner_id, space_id)
);

CREATE TABLE IF NOT EXISTS learning_operation_journal (
    operation_id TEXT PRIMARY KEY,
    phase TEXT NOT NULL,
    rollback_manifest_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (operation_id)
        REFERENCES learning_operation_fences(operation_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_learning_operation_fences_owner_scope
    ON learning_operation_fences(owner_id, space_id);
"""


class LearningCoordinationError(RuntimeError):
    def __init__(self, message: str, *, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


class LearningCoordinationSchemaError(LearningCoordinationError):
    def __init__(self, version: int) -> None:
        super().__init__(
            f"unsupported learning coordination schema version: {version}",
            reason_code="learning_coordination_schema_unsupported",
        )
        self.version = version


class LearningOperationInProgressError(LearningCoordinationError):
    def __init__(self) -> None:
        super().__init__(
            "a matching learning data operation is in progress",
            reason_code="learning_operation_in_progress",
        )


class LearningOperationTimeoutError(LearningCoordinationError):
    def __init__(self) -> None:
        super().__init__(
            "timed out acquiring the learning operation coordinator",
            reason_code="learning_operation_timeout",
        )


class LearningOperationConflictError(LearningCoordinationError):
    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code, reason_code=reason_code)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_owner_id(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 256:
        raise ValueError("owner_id is invalid")
    return value


def _require_space_id(value: Any) -> str:
    if value == "":
        return ""
    if not isinstance(value, str) or not _OPAQUE_ID_RE.fullmatch(value):
        raise ValueError("space_id is invalid")
    return value


def _require_phase(value: Any) -> str:
    if not isinstance(value, str) or not _PHASE_RE.fullmatch(value):
        raise ValueError("operation phase is invalid")
    return value


def _require_bundle_sha256(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError("bundle_sha256 must be lowercase SHA-256 hex")
    return value


def _manifest_json(value: Mapping[str, Any]) -> str:
    if not isinstance(value, Mapping):
        raise ValueError("rollback_manifest must be an object")
    encoded = canonical_json_bytes(value)
    if len(encoded) > MAX_ROLLBACK_MANIFEST_BYTES:
        raise ValueError("rollback_manifest exceeds 64 KiB")
    return encoded.decode("utf-8")


def _windows_identity() -> str:
    result = subprocess.run(
        ["whoami"],
        check=True,
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    identity = result.stdout.strip()
    if not identity:
        raise PermissionError("cannot resolve Windows identity for coordination DB ACL")
    return identity


def secure_coordination_db(db_path: Path) -> None:
    """Apply a user-only ACL to a production coordination DB and sidecars."""

    path = db_path.resolve()
    root = path.parent
    identity: str | None = None
    with _ACL_LOCK:
        if root not in _SECURED_ROOTS:
            if os.name == "nt":
                identity = _windows_identity()
                result = subprocess.run(
                    [
                        "icacls",
                        str(root),
                        "/inheritance:r",
                        "/grant:r",
                        f"{identity}:(OI)(CI)F",
                        "/Q",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if result.returncode != 0:
                    detail = (result.stderr or result.stdout or "icacls failed").strip()
                    raise PermissionError(
                        f"cannot secure coordination DB directory ACL: {detail}"
                    )
            else:
                os.chmod(root, 0o700)
            _SECURED_ROOTS.add(root)
        if path not in _SECURED_FILES and path.exists():
            if os.name == "nt":
                identity = identity or _windows_identity()
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
                        detail = (
                            result.stderr or result.stdout or "icacls failed"
                        ).strip()
                        raise PermissionError(
                            f"cannot secure coordination DB file ACL: {detail}"
                        )
            else:
                os.chmod(path, 0o600)
            _SECURED_FILES.add(path)


class OperationLease:
    """Opaque authority for writes performed inside a persistent fence."""

    __slots__ = (
        "operation_id",
        "owner_id",
        "space_id",
        "operation",
        "phase",
        "bundle_sha256",
        "rollback_manifest",
        "__issuer_token",
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("OperationLease values are issued by LearningOperationCoordinator")

    @classmethod
    def _issue(
        cls,
        *,
        operation_id: str,
        owner_id: str,
        space_id: str,
        operation: str,
        phase: str,
        bundle_sha256: str | None,
        rollback_manifest: Mapping[str, Any],
        issuer_token: str,
    ) -> "OperationLease":
        lease = object.__new__(cls)
        lease.operation_id = operation_id
        lease.owner_id = owner_id
        lease.space_id = space_id
        lease.operation = operation
        lease.phase = phase
        lease.bundle_sha256 = bundle_sha256
        lease.rollback_manifest = dict(rollback_manifest)
        lease.__issuer_token = issuer_token
        return lease

    def _issued_by(self, token: str) -> bool:
        return secrets.compare_digest(self.__issuer_token, token)

    def __repr__(self) -> str:
        return (
            "OperationLease(operation_id={!r}, owner_id={!r}, space_id={!r}, "
            "operation={!r}, phase={!r})"
        ).format(
            self.operation_id,
            self.owner_id,
            self.space_id,
            self.operation,
            self.phase,
        )


class LearningOperationGuard:
    """A held coordination transaction; release after the business DB work."""

    __slots__ = ("_connection", "mode", "owner_id", "space_id", "_closed")

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        mode: str,
        owner_id: str,
        space_id: str,
    ) -> None:
        self._connection = connection
        self.mode = mode
        self.owner_id = owner_id
        self.space_id = space_id
        self._closed = False

    def __enter__(self) -> "LearningOperationGuard":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close(success=exc_type is None)

    def close(self, *, success: bool = True) -> None:
        if self._closed:
            return
        try:
            if success:
                self._connection.commit()
            else:
                self._connection.rollback()
        finally:
            self._connection.close()
            self._closed = True


class LearningOperationCoordinator:
    def __init__(
        self,
        db_path: Path | str,
        *,
        timeout_s: float = 1.0,
        secure_permissions: bool = False,
    ) -> None:
        if timeout_s <= 0 or timeout_s > 30:
            raise ValueError("timeout_s must be greater than zero and at most 30")
        self.db_path = Path(db_path).expanduser().resolve()
        self.timeout_s = float(timeout_s)
        self._issuer_token = secrets.token_hex(32)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if secure_permissions:
            # Protect the directory before SQLite can create WAL/SHM files.
            secure_coordination_db(self.db_path)
        self._initialize()
        if secure_permissions:
            secure_coordination_db(self.db_path)

    @classmethod
    def from_learning_db_path(
        cls,
        learning_db_path: Path | str,
        *,
        timeout_s: float = 1.0,
        secure_permissions: bool = False,
    ) -> "LearningOperationCoordinator":
        learning_path = Path(learning_db_path).expanduser().resolve()
        return cls(
            learning_path.parent / "learning_coordination.db",
            timeout_s=timeout_s,
            secure_permissions=secure_permissions,
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.db_path,
            timeout=0,
            isolation_level=None,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA secure_delete=ON")
        connection.execute("PRAGMA busy_timeout=0")
        return connection

    def _initialize(self) -> None:
        deadline = time.monotonic() + self.timeout_s
        while True:
            connection = self._connect()
            try:
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version > COORDINATION_SCHEMA_VERSION:
                    raise LearningCoordinationSchemaError(version)
                connection.execute("PRAGMA journal_mode=WAL")
                self._begin_immediate(connection, deadline)
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version > COORDINATION_SCHEMA_VERSION:
                    raise LearningCoordinationSchemaError(version)
                connection.executescript(SCHEMA_SQL)
                if version == 0:
                    connection.execute(
                        f"PRAGMA user_version={COORDINATION_SCHEMA_VERSION}"
                    )
                connection.commit()
                return
            except LearningCoordinationSchemaError:
                connection.rollback()
                raise
            except sqlite3.OperationalError as exc:
                connection.rollback()
                if not self._is_busy(exc) or time.monotonic() >= deadline:
                    if self._is_busy(exc):
                        raise LearningOperationTimeoutError() from exc
                    raise
                time.sleep(0.01)
            finally:
                connection.close()

    @staticmethod
    def _is_busy(exc: sqlite3.OperationalError) -> bool:
        message = str(exc).lower()
        return "locked" in message or "busy" in message

    def _begin_immediate(
        self, connection: sqlite3.Connection, deadline: float
    ) -> None:
        while True:
            try:
                connection.execute("BEGIN IMMEDIATE")
                return
            except sqlite3.OperationalError as exc:
                if not self._is_busy(exc):
                    raise
                if time.monotonic() >= deadline:
                    raise LearningOperationTimeoutError() from exc
                time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))

    def _acquire_connection(self) -> sqlite3.Connection:
        connection = self._connect()
        try:
            self._begin_immediate(connection, time.monotonic() + self.timeout_s)
            return connection
        except Exception:
            connection.close()
            raise

    @staticmethod
    def _matching_fence(
        connection: sqlite3.Connection, owner_id: str, space_id: str
    ) -> sqlite3.Row | None:
        if space_id == "":
            return connection.execute(
                """
                SELECT * FROM learning_operation_fences
                WHERE owner_id = ?
                ORDER BY CASE WHEN space_id = '' THEN 0 ELSE 1 END, space_id
                LIMIT 1
                """,
                (owner_id,),
            ).fetchone()
        return connection.execute(
            """
            SELECT * FROM learning_operation_fences
            WHERE owner_id = ? AND space_id IN ('', ?)
            ORDER BY CASE WHEN space_id = '' THEN 0 ELSE 1 END
            LIMIT 1
            """,
            (owner_id, space_id),
        ).fetchone()

    def _validate_lease(
        self,
        connection: sqlite3.Connection,
        lease: OperationLease,
        owner_id: str,
        space_id: str,
    ) -> None:
        if not isinstance(lease, OperationLease) or not lease._issued_by(
            self._issuer_token
        ):
            raise LearningOperationConflictError("invalid_operation_lease")
        if lease.owner_id != owner_id or lease.space_id != space_id:
            raise LearningOperationConflictError("operation_lease_scope_mismatch")
        row = connection.execute(
            "SELECT * FROM learning_operation_fences WHERE operation_id = ?",
            (lease.operation_id,),
        ).fetchone()
        if row is None:
            raise LearningOperationConflictError("operation_lease_not_found")
        if (
            row["owner_id"] != lease.owner_id
            or row["space_id"] != lease.space_id
            or row["operation"] != lease.operation
            or row["phase"] != lease.phase
        ):
            raise LearningOperationConflictError("stale_operation_phase")

    def _begin_guard(
        self,
        mode: str,
        owner_id: str,
        space_id: str,
        operation_lease: OperationLease | None,
    ) -> LearningOperationGuard:
        owner_id = _require_owner_id(owner_id)
        space_id = _require_space_id(space_id)
        connection = self._acquire_connection()
        try:
            if operation_lease is None:
                if self._matching_fence(connection, owner_id, space_id) is not None:
                    raise LearningOperationInProgressError()
            else:
                self._validate_lease(
                    connection, operation_lease, owner_id, space_id
                )
            return LearningOperationGuard(
                connection, mode=mode, owner_id=owner_id, space_id=space_id
            )
        except Exception:
            connection.rollback()
            connection.close()
            raise

    def begin_write(
        self,
        owner_id: str,
        space_id: str,
        operation_lease: OperationLease | None = None,
    ) -> LearningOperationGuard:
        return self._begin_guard("write", owner_id, space_id, operation_lease)

    def begin_read(
        self,
        owner_id: str,
        space_id: str,
        operation_lease: OperationLease | None = None,
    ) -> LearningOperationGuard:
        return self._begin_guard("read", owner_id, space_id, operation_lease)

    def _issue_from_row(
        self, row: sqlite3.Row, rollback_manifest: Mapping[str, Any]
    ) -> OperationLease:
        return OperationLease._issue(
            operation_id=row["operation_id"],
            owner_id=row["owner_id"],
            space_id=row["space_id"],
            operation=row["operation"],
            phase=row["phase"],
            bundle_sha256=row["bundle_sha256"],
            rollback_manifest=rollback_manifest,
            issuer_token=self._issuer_token,
        )

    def begin_operation(
        self,
        owner_id: str,
        space_id: str,
        kind: str,
        bundle_sha256: str | None = None,
    ) -> OperationLease:
        owner_id = _require_owner_id(owner_id)
        space_id = _require_space_id(space_id)
        if kind not in OPERATION_KINDS:
            raise ValueError("operation kind is invalid")
        bundle_sha256 = _require_bundle_sha256(bundle_sha256)
        connection = self._acquire_connection()
        try:
            if self._matching_fence(connection, owner_id, space_id) is not None:
                raise LearningOperationInProgressError()
            operation_id = f"lop_{uuid.uuid4().hex}"
            now = _utc_now()
            connection.execute(
                """
                INSERT INTO learning_operation_fences
                    (operation_id, owner_id, space_id, operation, phase,
                     bundle_sha256, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'fenced', ?, ?, ?)
                """,
                (
                    operation_id,
                    owner_id,
                    space_id,
                    kind,
                    bundle_sha256,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO learning_operation_journal
                    (operation_id, phase, rollback_manifest_json,
                     created_at, updated_at)
                VALUES (?, 'fenced', '{}', ?, ?)
                """,
                (operation_id, now, now),
            )
            row = connection.execute(
                "SELECT * FROM learning_operation_fences WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
            connection.commit()
            return self._issue_from_row(row, {})
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def advance_operation(
        self,
        lease: OperationLease,
        phase: str,
        rollback_manifest: Mapping[str, Any],
    ) -> OperationLease:
        phase = _require_phase(phase)
        manifest_json = _manifest_json(rollback_manifest)
        connection = self._acquire_connection()
        try:
            self._validate_lease(
                connection, lease, lease.owner_id, lease.space_id
            )
            now = _utc_now()
            cursor = connection.execute(
                """
                UPDATE learning_operation_fences
                SET phase = ?, updated_at = ?
                WHERE operation_id = ? AND phase = ?
                """,
                (phase, now, lease.operation_id, lease.phase),
            )
            if cursor.rowcount != 1:
                raise LearningOperationConflictError("stale_operation_phase")
            cursor = connection.execute(
                """
                UPDATE learning_operation_journal
                SET phase = ?, rollback_manifest_json = ?, updated_at = ?
                WHERE operation_id = ? AND phase = ?
                """,
                (phase, manifest_json, now, lease.operation_id, lease.phase),
            )
            if cursor.rowcount != 1:
                raise LearningOperationConflictError("stale_operation_phase")
            row = connection.execute(
                "SELECT * FROM learning_operation_fences WHERE operation_id = ?",
                (lease.operation_id,),
            ).fetchone()
            connection.commit()
            return self._issue_from_row(row, json.loads(manifest_json))
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def finish_operation(self, lease: OperationLease) -> None:
        connection = self._acquire_connection()
        try:
            self._validate_lease(
                connection, lease, lease.owner_id, lease.space_id
            )
            cursor = connection.execute(
                "DELETE FROM learning_operation_journal WHERE operation_id = ? AND phase = ?",
                (lease.operation_id, lease.phase),
            )
            if cursor.rowcount != 1:
                raise LearningOperationConflictError("stale_operation_phase")
            cursor = connection.execute(
                "DELETE FROM learning_operation_fences WHERE operation_id = ? AND phase = ?",
                (lease.operation_id, lease.phase),
            )
            if cursor.rowcount != 1:
                raise LearningOperationConflictError("stale_operation_phase")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def recover_operations(self) -> tuple[OperationLease, ...]:
        connection = self._acquire_connection()
        try:
            rows = connection.execute(
                """
                SELECT f.*, j.rollback_manifest_json, j.phase AS journal_phase
                FROM learning_operation_fences AS f
                JOIN learning_operation_journal AS j
                  ON j.operation_id = f.operation_id
                ORDER BY f.created_at, f.operation_id
                LIMIT ?
                """,
                (MAX_RECOVERED_OPERATIONS,),
            ).fetchall()
            leases: list[OperationLease] = []
            for row in rows:
                if row["journal_phase"] != row["phase"]:
                    raise LearningOperationConflictError(
                        "operation_journal_phase_mismatch"
                    )
                manifest = json.loads(row["rollback_manifest_json"])
                leases.append(self._issue_from_row(row, manifest))
            connection.commit()
            return tuple(leases)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


__all__ = [
    "COORDINATION_SCHEMA_VERSION",
    "LearningCoordinationError",
    "LearningCoordinationSchemaError",
    "LearningOperationConflictError",
    "LearningOperationCoordinator",
    "LearningOperationGuard",
    "LearningOperationInProgressError",
    "LearningOperationTimeoutError",
    "OPERATION_KINDS",
    "OperationLease",
    "secure_coordination_db",
]

