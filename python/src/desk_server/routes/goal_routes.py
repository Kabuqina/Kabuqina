# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Desk routes for Goal Task human controls (Goal Runner Task 9, Step 4).

These endpoints delegate *only* to the core `cron.goal_controls` service — no
goal-state transition logic lives here (nor in Rust or React). They validate the
host-profile job id, map control errors to HTTP status, and return sanitized
state. Authentication is handled by the shared desk auth middleware.
"""

from __future__ import annotations

import logging
import re
from contextlib import contextmanager

from fastapi import APIRouter, HTTPException

from hermes_time import now as _hermes_now
from cron.goal_controls import (
    GoalControlBusy,
    GoalControlNotFound,
    InvalidGoalControl,
    cancel_goal,
    delete_goal,
    pause_goal,
    resume_goal,
)

log = logging.getLogger(__name__)
router = APIRouter()

_JOB_ID_RE = re.compile(r"^[a-f0-9]{12}$")


def _sanitized_state(state) -> dict:
    """Return only host-safe scheduling fields — never provider text."""
    return {
        "job_id": state.job_id,
        "status": state.status,
        "iteration": state.iteration,
        "pause_reason": state.pause_reason,
        "updated_at": state.updated_at.isoformat() if state.updated_at else None,
    }


@contextmanager
def _mapped(job_id: str):
    """Validate the id and map control errors to HTTP; a busy lock is 409."""
    if not _JOB_ID_RE.match(job_id or ""):
        raise HTTPException(status_code=400, detail="invalid goal job id")
    try:
        yield
    except GoalControlBusy as exc:
        raise HTTPException(status_code=409, detail="goal is busy") from exc
    except GoalControlNotFound as exc:
        raise HTTPException(status_code=404, detail="goal not found") from exc
    except InvalidGoalControl as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/api/desk/goals/{job_id}/pause")
async def pause_goal_route(job_id: str):
    with _mapped(job_id):
        return _sanitized_state(pause_goal(job_id, now=_hermes_now()))


@router.post("/api/desk/goals/{job_id}/resume")
async def resume_goal_route(job_id: str):
    with _mapped(job_id):
        return _sanitized_state(resume_goal(job_id, now=_hermes_now()))


@router.post("/api/desk/goals/{job_id}/cancel")
async def cancel_goal_route(job_id: str):
    with _mapped(job_id):
        return _sanitized_state(cancel_goal(job_id, now=_hermes_now()))


@router.delete("/api/desk/goals/{job_id}")
async def delete_goal_route(job_id: str):
    with _mapped(job_id):
        return {"deleted": bool(delete_goal(job_id))}
