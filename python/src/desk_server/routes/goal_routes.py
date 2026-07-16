# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Desk routes for Goal Task creation and human controls.

The creation endpoint derives the host workspace and calls the fixed Pilot 1
core template. Control endpoints delegate *only* to `cron.goal_controls` — no
goal-state transition logic lives here (nor in Rust or React). They validate the
host-profile job id, map control errors to HTTP status, and return sanitized
state. Authentication is handled by the shared desk auth middleware.
"""

from __future__ import annotations

import logging
import os
import re
from contextlib import contextmanager
from pathlib import Path

from fastapi import APIRouter, HTTPException

from kabuqina_time import now as _hermes_now
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


def _desktop_workspace() -> str:
    """Return the spawned desktop child's workspace, never client input."""
    raw = (
        os.environ.get("HERMESDESK_WORKSPACE")
        or os.environ.get("HERMES_WORKSPACE")
        or ""
    ).strip()
    if not raw:
        raise ValueError("desktop workspace is not configured")
    workspace = Path(raw).expanduser().resolve()
    if not workspace.is_dir():
        raise ValueError("desktop workspace is unavailable")
    return str(workspace)


def _sanitized_created_goal(job: dict) -> dict:
    """Return the fixed Pilot 1 projection, never its prompt or verifier body."""
    return {
        "job_id": job["id"],
        "name": job["name"],
        "mode": "goal",
        "status": "scheduled",
        "schedule": job["schedule_display"],
        "workdir": job["workdir"],
        "max_runs": job["goal"]["limits"]["max_runs"],
        "max_wall_seconds": job["goal"]["limits"]["max_wall_seconds"],
        "max_cost_usd": job["goal"]["limits"]["max_cost_usd"],
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


@router.post("/api/desk/goals")
async def create_pilot_goal_route():
    """Create the one fixed, host-only Goal Task template for Pilot 1.

    There is intentionally no request body: the authenticated desktop route
    derives its workspace from the spawned host process, and the core template
    supplies the verifier, limits, local delivery, and file-only toolset.
    """
    try:
        from cron.goal_pilot import create_pilot_manifest_goal

        return _sanitized_created_goal(create_pilot_manifest_goal(_desktop_workspace()))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
