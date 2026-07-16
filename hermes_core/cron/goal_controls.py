# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Crash-safe human controls for Goal Tasks (Goal Runner Task 9, Step 3).

Goal state is authoritative; the cron job record is only its *scheduling
mirror*. Every control acquires the same nonblocking profile scheduler lock used
by ``scheduler.tick`` — if an iteration or another tick owns it, the control
returns :class:`GoalControlBusy` and writes nothing (the desk route maps that to
HTTP 409). This cancels *future* iterations, never an already-executing turn.

Write ordering makes any interrupted control fail closed:

* **pause / cancel** — persist the goal state first, then disable the job
  mirror. A partial pause/cancel leaves runnable-looking scheduling but
  non-runnable goal state, so the next tick cannot run it.
* **resume** — enable the job and compute its next wake first, then persist
  ``scheduled`` goal state. A partial resume leaves the goal state paused, so it
  stays blocked until a retry repairs it.
* **delete** — allowed only from a terminal state; removes the job record and
  deliberately retains the goal-run directory for inspection.

Retrying the same control is idempotent and repairs a half-applied mirror.
Rust and React contain no goal-state transition logic; they proxy here.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

from kabuqina_constants import get_kabuqina_home
from cron.goal_state import GoalRunState, load_goal_state, save_goal_state
from cron.jobs import compute_next_run, get_job, remove_job, update_job
from cron.scheduler_lock import tick_lock

__all__ = [
    "GoalControlError",
    "GoalControlBusy",
    "GoalControlNotFound",
    "InvalidGoalControl",
    "pause_goal",
    "resume_goal",
    "cancel_goal",
    "delete_goal",
]

_TERMINAL_STATES = frozenset({"completed", "failed", "cancelled"})
# Truly finished — cancel cannot re-open these, but may re-assert "cancelled".
_FINISHED_STATES = frozenset({"completed", "failed"})


class GoalControlError(RuntimeError):
    """Base error for a rejected goal control."""


class GoalControlBusy(GoalControlError):
    """The profile scheduler lock is held by an active iteration or tick."""


class GoalControlNotFound(GoalControlError):
    """No committed goal state (or mirror job) exists for the id."""


class InvalidGoalControl(GoalControlError):
    """The control is not allowed from the goal's current state."""


def _lock_file() -> Path:
    """The active profile's scheduler lock — the same file ``tick`` uses."""
    return get_kabuqina_home() / "cron" / ".tick.lock"


def _require_state(job_id: str) -> GoalRunState:
    state = load_goal_state(job_id)
    if state is None:
        raise GoalControlNotFound(f"no committed goal state for {job_id!r}")
    return state


def _require_job(job_id: str) -> dict:
    job = get_job(job_id)
    if job is None:
        raise GoalControlNotFound(f"no cron job record for {job_id!r}")
    return job


def _disable_mirror(job_id: str, goal_status: str) -> None:
    """Disable future wakes and mirror the terminal/paused status (idempotent)."""
    update_job(
        job_id,
        {
            "enabled": False,
            "state": goal_status,
            "goal_status": goal_status,
        },
    )


def pause_goal(
    job_id: str, *, now: datetime, reason: str = "user_paused"
) -> GoalRunState:
    """Pause a non-terminal goal: authoritative state first, then disable wakes."""
    with tick_lock(_lock_file()) as acquired:
        if not acquired:
            raise GoalControlBusy(f"goal {job_id!r} is busy")
        state = _require_state(job_id)
        _require_job(job_id)
        if state.status in _TERMINAL_STATES:
            raise InvalidGoalControl(
                f"cannot pause goal {job_id!r} in terminal state {state.status!r}"
            )
        if state.status != "paused":
            state = replace(state, status="paused", pause_reason=reason, updated_at=now)
            save_goal_state(state)
        _disable_mirror(job_id, "paused")
        return state


def resume_goal(job_id: str, *, now: datetime) -> GoalRunState:
    """Resume a paused goal: enable + schedule the next wake, then runnable state."""
    with tick_lock(_lock_file()) as acquired:
        if not acquired:
            raise GoalControlBusy(f"goal {job_id!r} is busy")
        state = _require_state(job_id)
        job = _require_job(job_id)
        if state.status != "paused":
            raise InvalidGoalControl(
                f"can only resume a paused goal; {job_id!r} is {state.status!r}"
            )
        update_job(
            job_id,
            {
                "enabled": True,
                "state": "scheduled",
                "goal_status": "scheduled",
                "paused_at": None,
                "paused_reason": None,
                "next_run_at": compute_next_run(job["schedule"]),
            },
        )
        state = replace(state, status="scheduled", pause_reason=None, updated_at=now)
        save_goal_state(state)
        return state


def cancel_goal(job_id: str, *, now: datetime) -> GoalRunState:
    """Cancel a non-finished goal: authoritative state first, then disable wakes.

    Distinct from delete — the cancelled job and its state are retained for
    inspection.
    """
    with tick_lock(_lock_file()) as acquired:
        if not acquired:
            raise GoalControlBusy(f"goal {job_id!r} is busy")
        state = _require_state(job_id)
        _require_job(job_id)
        if state.status in _FINISHED_STATES:
            raise InvalidGoalControl(
                f"cannot cancel goal {job_id!r} in finished state {state.status!r}"
            )
        if state.status != "cancelled":
            state = replace(state, status="cancelled", pause_reason=None, updated_at=now)
            save_goal_state(state)
        _disable_mirror(job_id, "cancelled")
        return state


def delete_goal(job_id: str) -> bool:
    """Delete a *terminal* goal's job record; retain the goal-run directory.

    Returns whether a job record was removed. Idempotent: re-deleting a goal
    whose mirror is already gone returns ``False`` without error. The committed
    goal-run evidence is deliberately kept until a later retention decision.
    """
    with tick_lock(_lock_file()) as acquired:
        if not acquired:
            raise GoalControlBusy(f"goal {job_id!r} is busy")
        state = _require_state(job_id)
        if state.status not in _TERMINAL_STATES:
            raise InvalidGoalControl(
                f"cannot delete active goal {job_id!r} in state {state.status!r}; "
                "cancel it first"
            )
        return remove_job(job_id)
