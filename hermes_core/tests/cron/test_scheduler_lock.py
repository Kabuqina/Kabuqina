# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Pin the extracted single-owner cron lock (Goal Runner Task 8, Step 3a).

These characterize the behaviour that `scheduler.tick` relied on inline, so the
extraction into `scheduler_lock` cannot silently change acquisition semantics.
"""

from __future__ import annotations

import pytest

import cron.scheduler_lock as scheduler_lock
from cron.scheduler_lock import tick_lock

_HAS_PRIMITIVE = scheduler_lock.fcntl is not None or scheduler_lock.msvcrt is not None


def test_acquires_and_creates_lock_file_when_uncontended(tmp_path):
    lock = tmp_path / ".tick.lock"

    with tick_lock(lock) as acquired:
        assert acquired is True

    assert lock.exists()


def test_creates_missing_parent_directory(tmp_path):
    lock = tmp_path / "cron" / ".tick.lock"

    with tick_lock(lock) as acquired:
        assert acquired is True

    assert lock.parent.is_dir()


def test_releases_so_a_later_owner_can_reacquire(tmp_path):
    lock = tmp_path / ".tick.lock"

    with tick_lock(lock) as first:
        assert first is True
    with tick_lock(lock) as second:
        assert second is True


@pytest.mark.skipif(not _HAS_PRIMITIVE, reason="no OS file-lock primitive available")
def test_second_owner_is_blocked_while_held(tmp_path):
    lock = tmp_path / ".tick.lock"

    with tick_lock(lock) as first:
        assert first is True
        with tick_lock(lock) as second:
            assert second is False


def test_busy_path_yields_false_and_never_releases(tmp_path, monkeypatch):
    # Force contention deterministically, independent of the OS primitive.
    monkeypatch.setattr(scheduler_lock, "_try_lock", lambda handle: False)
    released = []
    monkeypatch.setattr(scheduler_lock, "_unlock", lambda handle: released.append(handle))

    with tick_lock(tmp_path / ".tick.lock") as acquired:
        assert acquired is False

    assert released == []
