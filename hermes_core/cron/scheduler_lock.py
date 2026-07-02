# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Cross-platform single-owner file lock for the cron scheduler.

Extracted verbatim (behaviour-preserving) from ``scheduler.tick`` so the same
nonblocking, single-owner acquisition can be reused by the Goal Runner control
service without racing an active ``tick()``. The lock scope is unchanged: a
caller holds it across the entire critical section and releases on exit.

Semantics, identical to the original inline logic:

* Nonblocking: acquisition never waits — if another owner holds the lock the
  context yields ``False`` and the caller must skip its lock-scoped work.
* Cross-platform: ``fcntl`` on Unix, ``msvcrt`` on Windows. When neither
  primitive is importable the lock is a best-effort no-op that always
  "acquires" — matching the previous behaviour exactly.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# fcntl is Unix-only; on Windows use msvcrt for file locking.
try:
    import fcntl
except ImportError:
    fcntl = None
    try:
        import msvcrt
    except ImportError:
        msvcrt = None

__all__ = ["tick_lock"]


def _try_lock(handle) -> bool:
    """Attempt a nonblocking exclusive lock; return whether it was acquired."""
    try:
        if fcntl is not None:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        elif msvcrt is not None:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        # No primitive available → best-effort single owner (unchanged).
        return True
    except (OSError, IOError):
        return False


def _unlock(handle) -> None:
    if fcntl is not None:
        fcntl.flock(handle, fcntl.LOCK_UN)
    elif msvcrt is not None:
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except (OSError, IOError):
            pass


@contextmanager
def tick_lock(lock_file: Path) -> Iterator[bool]:
    """Hold the scheduler's single-owner lock for the duration of the block.

    Yields ``True`` when the lock is held (released automatically on exit), or
    ``False`` when another owner already holds it — in which case the caller
    must not perform any lock-scoped work.
    """
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    handle = None
    acquired = False
    try:
        handle = open(lock_file, "w")
        acquired = _try_lock(handle)
        if not acquired:
            handle.close()
            handle = None
            yield False
            return
        yield True
    finally:
        if handle is not None:
            if acquired:
                _unlock(handle)
            handle.close()
