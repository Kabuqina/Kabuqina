# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Desk goal-control routes (Goal Runner Task 9, Step 4).

The routes must delegate to `cron.goal_controls` and map its errors to HTTP
status, returning only sanitized state.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
_HERMES_CORE = Path(__file__).resolve().parents[2] / "hermes_core"
for _p in (_SRC, _HERMES_CORE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

NOW = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    return tmp_path


@pytest.fixture
def client(home):
    from fastapi.testclient import TestClient
    from desk_server.app import create_app
    from desk_server.auth import SESSION_TOKEN

    c = TestClient(create_app())
    c.headers.update({"X-Hermes-Session-Token": SESSION_TOKEN})
    return c


def _make_goal(home, status="scheduled"):
    from cron.goal_state import new_goal_state, save_goal_state
    from cron.jobs import create_job

    workdir = home / "wd"
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
    save_goal_state(
        replace(new_goal_state(job["id"], now=NOW), status=status, updated_at=NOW)
    )
    return job


def test_pause_returns_sanitized_paused_state(client, home):
    job = _make_goal(home, "scheduled")

    resp = client.post(f"/api/desk/goals/{job['id']}/pause")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "paused"
    assert body["job_id"] == job["id"]
    assert set(body) == {"job_id", "status", "iteration", "pause_reason", "updated_at"}


def test_resume_returns_scheduled(client, home):
    job = _make_goal(home, "paused")

    resp = client.post(f"/api/desk/goals/{job['id']}/resume")

    assert resp.status_code == 200
    assert resp.json()["status"] == "scheduled"


def test_cancel_returns_cancelled(client, home):
    job = _make_goal(home, "paused")

    resp = client.post(f"/api/desk/goals/{job['id']}/cancel")

    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_delete_terminal_goal(client, home):
    job = _make_goal(home, "cancelled")

    resp = client.delete(f"/api/desk/goals/{job['id']}")

    assert resp.status_code == 200
    assert resp.json() == {"deleted": True}


def test_invalid_job_id_is_400(client, home):
    resp = client.post("/api/desk/goals/NOT-HEX/pause")
    assert resp.status_code == 400


def test_missing_goal_is_404(client, home):
    resp = client.post("/api/desk/goals/aaaaaaaaaaaa/pause")
    assert resp.status_code == 404


def test_deleting_active_goal_is_409(client, home):
    job = _make_goal(home, "scheduled")

    resp = client.delete(f"/api/desk/goals/{job['id']}")

    assert resp.status_code == 409


def test_routes_require_auth(home):
    from fastapi.testclient import TestClient
    from desk_server.app import create_app

    job = _make_goal(home, "scheduled")
    unauthed = TestClient(create_app())

    resp = unauthed.post(f"/api/desk/goals/{job['id']}/pause")

    assert resp.status_code in (401, 403)
