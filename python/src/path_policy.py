# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""PathPolicy — confine file operations to allowed directories.

Extracted from ``overlays/workspace_jail.py`` and ``overlays/path_guard.py``.
This is the target replacement: a single policy object that knows which
paths are readable/writable, without monkey-patching ``builtins.open``.
"""

from __future__ import annotations

import os
import os.path
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Iterable, Iterator


# Sentinel file that bots must never write to.
_HOST_PREFS_FILENAME = "_host_prefs.md"

# Windows NUL device — libraries (e.g. Docling/RapidOCR) probe or redirect to it during init.
_WIN_NULL_DEVICE_NAMES = frozenset({"nul"})

# Exact, read-only paths explicitly chosen through a trusted desktop file
# picker. ContextVar keeps the exception scoped to one request and is copied by
# ``asyncio.to_thread``; it never becomes a process-wide directory allowlist.
_TEMPORARY_READ_PATHS: ContextVar[tuple[Path, ...]] = ContextVar(
    "kabuqina_temporary_read_paths",
    default=(),
)


@contextmanager
def temporary_read_access(path: str | os.PathLike) -> Iterator[Path]:
    """Allow one exact user-selected file to be read for this call context."""
    selected = PathPolicy._norm(path)
    token = _TEMPORARY_READ_PATHS.set((*_TEMPORARY_READ_PATHS.get(), selected))
    try:
        yield selected
    finally:
        _TEMPORARY_READ_PATHS.reset(token)


def _windows_device_basename(path: str | bytes | os.PathLike) -> str | None:
    """Return the Windows device basename for NUL-style paths, or None."""
    if os.name != "nt":
        return None
    raw = os.fsdecode(path).strip().strip('"')
    normalized = raw.replace("/", "\\").lower()
    if normalized.startswith("\\\\.\\") or normalized.startswith("\\\\?\\"):
        normalized = normalized[4:].lstrip("\\")
    tail = normalized.rstrip("\\")
    if not tail or "\\" in tail:
        return None
    return tail.split(":", 1)[0].split(".", 1)[0]


def _is_allowed_windows_device(path: str | os.PathLike, *, write: bool) -> bool:
    """Allow harmless Windows device paths that third-party libs touch during init."""
    _ = write  # NUL is safe for read and write (data sink).
    name = _windows_device_basename(path)
    return name in _WIN_NULL_DEVICE_NAMES


class PathPolicyError(PermissionError):
    """Raised when a path escapes the permitted allowlist."""


class PathPolicy:
    """Resolve and validate a path against the configured root + extra dirs.

    If the process is a gateway child (``HERMESDESK_GATEWAY_PLATFORM`` set),
    writes to ``_host_prefs.md`` are unconditionally rejected — that file is
    host-write-only and serves as the read-only shared-preferences preamble
    for all bots.
    """

    _is_gateway_child: bool | None = None

    @classmethod
    def _check_gateway_child(cls) -> bool:
        if cls._is_gateway_child is None:
            cls._is_gateway_child = bool(os.environ.get("HERMESDESK_GATEWAY_PLATFORM"))
        return cls._is_gateway_child

    def __init__(
        self,
        workspace_root: Path,
        *,
        extra_read: Iterable[Path] = (),
        extra_write: Iterable[Path] = (),
    ) -> None:
        self._root = self._norm(workspace_root)
        self._extra_read = [self._norm(p) for p in extra_read]
        self._extra_write = [self._norm(p) for p in extra_write]

    @staticmethod
    def _norm(path: str | os.PathLike) -> Path:
        return Path(os.path.realpath(os.path.abspath(os.fspath(path))))

    def enforce(self, path: str | os.PathLike, *, write: bool = False) -> Path:
        raw = os.fspath(path)
        if _is_allowed_windows_device(raw, write=write):
            return Path("NUL")

        p = self._norm(path)

        if not write and p in _TEMPORARY_READ_PATHS.get():
            return p

        # Gateway children must never write to _host_prefs.md (host-only file).
        if write and p.name == _HOST_PREFS_FILENAME and self._check_gateway_child():
            raise PathPolicyError(
                f"Kabuqina path policy blocked write to {_HOST_PREFS_FILENAME!r} "
                f"from gateway child (host-only shared preferences file)."
            )

        roots = [self._root] + self._extra_write
        if not write:
            roots = roots + self._extra_read
        for r in roots:
            try:
                p.relative_to(r)
                return p
            except ValueError:
                pass
        action = "write" if write else "read"
        raise PathPolicyError(
            f"Kabuqina path policy blocked {action} "
            f"to {p!s} (allowed root: {self._root!s})"
        )

    @property
    def workspace_root(self) -> Path:
        return self._root
