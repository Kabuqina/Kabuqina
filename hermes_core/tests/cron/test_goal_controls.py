# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Goal Runner Task 9 Step 3 — crash-safe human controls.

State is authoritative, the cron job is its scheduling mirror. Every control
locks the profile scheduler lock; write ordering makes partial failures fail
closed and repairable on retry.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

import cron.goal_controls as gc
import cron.scheduler_lock as scheduler_lock
from cron.goal_controls import (
    GoalControlBusy,
    GoalControlNotFound,
    InvalidGoalControl,
    cancel_goal,
    delete_goal,
    pause_goal,
    resume_goal,
)
from cron.goal_state import goal_run_dir, load_goal_state, new_goal_state, save_goal_state
from cron.jobs import create_job, get_job

NOW = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)
_HAS_PRIMITIVE = scheduler_lock.fcntl is not None or scheduler_lock.msvcrt is not None


def _make_goal(tmp_path, status="scheduled"):
    """Create a mirror goal job plus a committed goal state in ``status``."""
    workdir = tmp_path / "wd"
    workdir.mkdir(exist_ok=True)
    job = create_job(
        prompt="do one unit",
        schedule="every 1h",
        mode="goal",
        goal="complete the inventory",
        workdir=str(workdir),
        verifier={"kind": "artifact_exists", "config": {}},
        limits={"max_runs": 5, "max_wall_seconds": 600},
    )
    save_goal_state(replace(new_goal_state(job["id"], now=NOW), status=status, updated_at=NOW))
    return job


def _raise(*_args, **_kwargs):
    raise RuntimeError("injected mid-control crash")


class TestPause:
    def test_pauses_state_then_disables_mirror(self, tmp_path):
        job = _make_goal(tmp_path, "scheduled")

        result = pause_goal(job["id"], now=NOW)

        assert result.status == "paused"
        assert result.pause_reason == "user_paused"
        assert load_goal_state(job["id"]).status == "paused"
        mirror = get_job(job["id"])
        assert mirror["enabled"] is False
        assert mirror["goal_status"] == "paused"

    def test_rejects_terminal_state(self, tmp_path):
        job = _make_goal(tmp_path, "completed")

        with pytest.raises(InvalidGoalControl):
            pause_goal(job["id"], now=NOW)

    def test_is_idempotent(self, tmp_path):
        job = _make_goal(tmp_path, "scheduled")

        pause_goal(job["id"], now=NOW)
        again = pause_goal(job["id"], now=NOW)

        assert again.status == "paused"
        assert get_job(job["id"])["enabled"] is False


class TestResume:
    def test_enables_and_schedules_then_marks_runnable(self, tmp_path):
        job = _make_goal(tmp_path, "paused")

        result = resume_goal(job["id"], now=NOW)

        assert result.status == "scheduled"
        assert result.pause_reason is None
        mirror = get_job(job["id"])
        assert mirror["enabled"] is True
        assert mirror["state"] == "scheduled"
        assert mirror["next_run_at"]

    def test_rejects_non_paused_state(self, tmp_path):
        job = _make_goal(tmp_path, "scheduled")

        with pytest.raises(InvalidGoalControl):
            resume_goal(job["id"], now=NOW)


class TestCancel:
    def test_cancels_state_then_disables_mirror(self, tmp_path):
        job = _make_goal(tmp_path, "paused")

        result = cancel_goal(job["id"], now=NOW)

        assert result.status == "cancelled"
        assert load_goal_state(job["id"]).status == "cancelled"
        assert get_job(job["id"])["enabled"] is False

    def test_rejects_finished_state(self, tmp_path):
        job = _make_goal(tmp_path, "completed")

        with pytest.raises(InvalidGoalControl):
            cancel_goal(job["id"], now=NOW)


class TestDelete:
    def test_deletes_terminal_job_but_retains_goal_run_dir(self, tmp_path):
        job = _make_goal(tmp_path, "cancelled")

        removed = delete_goal(job["id"])

        assert removed is True
        assert get_job(job["id"]) is None
        # Evidence is deliberately retained for inspection.
        assert goal_run_dir(job["id"]).exists()
        assert load_goal_state(job["id"]).status == "cancelled"

    def test_rejects_active_goal(self, tmp_path):
        job = _make_goal(tmp_path, "scheduled")

        with pytest.raises(InvalidGoalControl):
            delete_goal(job["id"])

    def test_is_idempotent_after_mirror_gone(self, tmp_path):
        job = _make_goal(tmp_path, "failed")

        assert delete_goal(job["id"]) is True
        assert delete_goal(job["id"]) is False


class TestNotFoundAndBusy:
    def test_missing_state_raises_not_found(self, tmp_path):
        # A job mirror with no committed goal state.
        job = create_job(prompt="x", schedule="every 1h", mode="notify", message="x")

        with pytest.raises(GoalControlNotFound):
            pause_goal(job["id"], now=NOW)

    @pytest.mark.skipif(not _HAS_PRIMITIVE, reason="no OS file-lock primitive")
    def test_busy_lock_raises_and_writes_nothing(self, tmp_path):
        from kabuqina_constants import get_kabuqina_home
        from cron.scheduler_lock import tick_lock

        job = _make_goal(tmp_path, "scheduled")
        lock_file = get_kabuqina_home() / "cron" / ".tick.lock"

        with tick_lock(lock_file) as held:
            assert held
            with pytest.raises(GoalControlBusy):
                pause_goal(job["id"], now=NOW)

        assert load_goal_state(job["id"]).status == "scheduled"
        assert get_job(job["id"])["enabled"] is True


class TestCrashSafety:
    def test_partial_pause_persists_state_and_repairs_on_retry(self, tmp_path, monkeypatch):
        job = _make_goal(tmp_path, "scheduled")

        # Crash between the state write and the mirror disable. Restore the
        # specific attr (not monkeypatch.undo(), which would also revert the
        # conftest's KABUQINA_HOME isolation on the shared monkeypatch).
        real_update_job = gc.update_job
        monkeypatch.setattr(gc, "update_job", _raise)
        with pytest.raises(RuntimeError):
            pause_goal(job["id"], now=NOW)

        assert load_goal_state(job["id"]).status == "paused"
        assert get_job(job["id"])["enabled"] is True  # mirror not yet disabled

        monkeypatch.setattr(gc, "update_job", real_update_job)
        pause_goal(job["id"], now=NOW)  # retry repairs the mirror
        assert get_job(job["id"])["enabled"] is False

    def test_partial_resume_stays_blocked_and_repairs_on_retry(self, tmp_path, monkeypatch):
        job = _make_goal(tmp_path, "paused")

        # Crash between enabling the mirror and writing the runnable state.
        real_save_goal_state = gc.save_goal_state
        monkeypatch.setattr(gc, "save_goal_state", _raise)
        with pytest.raises(RuntimeError):
            resume_goal(job["id"], now=NOW)

        assert get_job(job["id"])["enabled"] is True
        assert load_goal_state(job["id"]).status == "paused"  # still blocked

        monkeypatch.setattr(gc, "save_goal_state", real_save_goal_state)
        resume_goal(job["id"], now=NOW)  # retry repairs the state
        assert load_goal_state(job["id"]).status == "scheduled"
