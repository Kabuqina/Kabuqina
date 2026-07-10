# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "python" / "src"
CORE_DIR = ROOT / "hermes_core"
for path in (SRC_DIR, CORE_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from learning.learning_context import LearningExecutionContext  # noqa: E402
from learning.learning_store import LearningStore  # noqa: E402
from learning.output_writer import OutputWriter  # noqa: E402

OWNER = "desktop:test-owner"
SECRET = "study-m4-route-secret"


@pytest.fixture()
def study_client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from desk_server.app import create_app

    import cron.jobs as jobs

    db_path = tmp_path / "learning.db"
    monkeypatch.setattr(jobs, "CRON_DIR", tmp_path / "cron")
    monkeypatch.setattr(jobs, "JOBS_FILE", tmp_path / "cron" / "jobs.json")
    monkeypatch.setattr(jobs, "OUTPUT_DIR", tmp_path / "cron" / "output")
    with patch.dict(os.environ, {"HERMESDESK_BRIDGE_SECRET": SECRET}, clear=False):
        with patch("learning.learning_store.default_learning_db_path", return_value=db_path):
            with patch("learning_owner.desktop_owner_id", return_value=OWNER):
                yield TestClient(create_app()), db_path


def _headers():
    return {"X-HermesDesk-Auth": SECRET}


def _seed_m4_drafts(db_path: Path):
    store = LearningStore(db_path=db_path)
    try:
        ctx = LearningExecutionContext(store, owner_id=OWNER)
        ctx.create_space(title="Algebra", space_id="s1")
        writer = OutputWriter(ctx)
        evaluation_id = writer.write_artifact(
            kind="evaluation",
            title="Eval",
            payload={"observations": ["Missed primes"], "weak_points": ["prime numbers"]},
        )["artifact_id"]
        plan_id = writer.write_artifact(
            kind="learning_plan",
            title="Plan",
            payload={"phases": [{"title": "P1", "tasks": [{"title": "Drill", "order": 1}]}]},
        )["artifact_id"]
        return evaluation_id, plan_id
    finally:
        store.close()


def test_student_state_save_and_context_migration_are_idempotent(study_client):
    client, _db_path = study_client
    saved = client.put(
        "/api/desk/study/student-state",
        json={"state": {"course": "Algebra", "goals": ["Midterm"]}},
        headers=_headers(),
    )
    assert saved.status_code == 200
    assert saved.json()["state"]["payload"]["course"] == "Algebra"

    loaded = client.get("/api/desk/study/student-state", headers=_headers())
    assert loaded.json()["state"]["payload"]["goals"] == ["Midterm"]

    migrated = client.post(
        "/api/desk/study/migrations/context",
        json={"context": {"course": "Calculus", "goal": "Pass", "weakPoints": "limits"}},
        headers=_headers(),
    )
    assert migrated.status_code == 200
    assert migrated.json()["migrated"] is True
    assert migrated.json()["student_state"]["payload"]["course"] == "Calculus"
    assert migrated.json()["evaluation"]["status"] == "active"

    second = client.post(
        "/api/desk/study/migrations/context",
        json={"context": {"course": "Ignored"}},
        headers=_headers(),
    )
    assert second.json() == {"migrated": False}


def test_context_migration_omits_empty_evaluation(study_client):
    client, _db_path = study_client
    migrated = client.post(
        "/api/desk/study/migrations/context",
        json={"context": {"course": "Algebra", "goal": "Pass"}},
        headers=_headers(),
    )
    assert migrated.status_code == 200
    assert migrated.json()["evaluation"] is None


def test_evaluation_and_learning_plan_routes(study_client):
    client, db_path = study_client
    evaluation_id, plan_id = _seed_m4_drafts(db_path)

    activated_eval = client.post(
        f"/api/desk/study/artifacts/{evaluation_id}/activate", headers=_headers()
    )
    assert activated_eval.status_code == 200
    evaluations = client.get("/api/desk/study/evaluations", headers=_headers())
    assert [row["artifact_id"] for row in evaluations.json()["evaluations"]] == [evaluation_id]
    detail = client.get(
        f"/api/desk/study/evaluations/{evaluation_id}", headers=_headers()
    )
    assert detail.json()["evaluation"]["payload"]["weak_points"] == ["prime numbers"]

    activated_plan = client.post(
        f"/api/desk/study/artifacts/{plan_id}/activate", headers=_headers()
    )
    assert activated_plan.status_code == 200
    assert activated_plan.json()["materialized"] == 1
    plans = client.get("/api/desk/study/learning-plans", headers=_headers())
    assert [row["artifact_id"] for row in plans.json()["plans"]] == [plan_id]
    items = client.get(
        f"/api/desk/study/learning-plans/{plan_id}/items", headers=_headers()
    )
    item_id = items.json()["items"][0]["item_id"]
    completed = client.post(
        f"/api/desk/study/learning-plans/items/{item_id}/complete",
        json={"note": "done"},
        headers=_headers(),
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    repeated = client.post(
        f"/api/desk/study/learning-plans/items/{item_id}/complete",
        json={},
        headers=_headers(),
    )
    assert repeated.status_code == 400


def test_contract_errors_map_to_conflict(study_client):
    client, db_path = study_client
    evaluation_id, _plan_id = _seed_m4_drafts(db_path)
    rejected = client.post(
        f"/api/desk/study/artifacts/{evaluation_id}/reject", headers=_headers()
    )
    assert rejected.status_code == 200
    response = client.post(
        f"/api/desk/study/artifacts/{evaluation_id}/activate", headers=_headers()
    )
    assert response.status_code == 409


def test_review_reminder_routes_are_opt_in(study_client):
    client, _db_path = study_client
    initial = client.get("/api/desk/study/review-reminder", headers=_headers())
    assert initial.status_code == 200
    assert initial.json()["enabled"] is False

    enabled = client.put(
        "/api/desk/study/review-reminder",
        json={"enabled": True, "time_of_day": "19:30"},
        headers=_headers(),
    )
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True
    assert enabled.json()["time_of_day"] == "19:30"

    disabled = client.put(
        "/api/desk/study/review-reminder",
        json={"enabled": False, "time_of_day": "19:30"},
        headers=_headers(),
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
