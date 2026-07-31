# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Global Activity aggregation and restart-recovery contracts."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "python" / "src", ROOT / "hermes_core"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from learning.checkpoint_store import LearningCheckpointV1  # noqa: E402
from learning.learning_context import LearningExecutionContext  # noqa: E402
from learning.knowledge_core_compilation_store import (  # noqa: E402
    KnowledgeCoreCompilationStore,
)
from learning.learning_store import LearningStore  # noqa: E402
from learning.tutor_contract import validate_start_request  # noqa: E402
from learning.tutor_runtime_store import TutorRuntimeStore  # noqa: E402


OWNER = "desktop:global-activity-owner"
SECRET = "global-activity-secret"


@pytest.fixture()
def activity_client(tmp_path):
    from fastapi.testclient import TestClient
    from desk_server.app import create_app

    learning_db = tmp_path / "learning.db"
    studio_db = tmp_path / "studio.db"
    with patch.dict(os.environ, {"HERMESDESK_BRIDGE_SECRET": SECRET}, clear=False):
        with patch("learning.learning_store.default_learning_db_path", return_value=learning_db):
            with patch("studio_store.default_studio_db_path", return_value=studio_db):
                with patch("learning_owner.desktop_owner_id", return_value=OWNER):
                    yield TestClient(create_app()), learning_db


def _headers():
    return {"X-HermesDesk-Auth": SECRET}


def _seed_interrupted(learning_db: Path, space_id: str, title: str, activity_id: str):
    learning_store = LearningStore(learning_db)
    runtime_store = TutorRuntimeStore(
        learning_db.parent / "tutor_runtime.db",
        coordinator=learning_store.coordinator,
        secure_permissions=False,
    )
    try:
        context = LearningExecutionContext(learning_store, OWNER)
        context.create_space(title=title, space_id=space_id)
        request = validate_start_request(
            {
                "schema_version": 1,
                "space_id": space_id,
                "activity_kind": "tutor",
                "idempotency_key": f"start-{activity_id}",
                "goal": f"Learn {title}",
                "input_refs": [],
            },
            owner_id=OWNER,
            activity_id=activity_id,
        )
        runtime_store.create(
            request,
            LearningCheckpointV1(
                request.key,
                0,
                "created",
                {
                    "schema_version": 1,
                    "phase": "start",
                    "goal": request.goal,
                    "input_refs": [],
                },
            ),
            label=f"{title} lesson",
        )
        runtime_store.claim_execution(
            request.key,
            expected_revision=0,
            execution_id=f"exec-{activity_id}",
        )
    finally:
        runtime_store.close()
        learning_store.close()


def test_new_install_returns_empty_global_activity(activity_client):
    client, _learning_db = activity_client
    response = client.get("/api/desk/activity", headers=_headers())
    assert response.status_code == 200
    assert response.json() == {"items": [], "count": 0, "limit": 100}


def test_restart_projects_two_courses_and_project_without_fake_running(activity_client):
    client, learning_db = activity_client
    _seed_interrupted(learning_db, "course-a", "Algebra", "activity-a")
    _seed_interrupted(learning_db, "course-b", "Calculus", "activity-b")
    project = client.post(
        "/api/desk/studio/projects",
        json={"title": "Explain limits"},
        headers=_headers(),
    ).json()

    first = client.get("/api/desk/activity", headers=_headers())
    second = client.get("/api/desk/activity", headers=_headers())
    assert first.status_code == second.status_code == 200
    items = first.json()["items"]
    assert {item["id"] for item in items} == {
        "study:tutor:activity-a",
        "study:tutor:activity-b",
        f"studio:project:{project['id']}",
    }
    assert [item["id"] for item in second.json()["items"]] == [
        item["id"] for item in items
    ]

    study = [item for item in items if item["domain"] == "study"]
    assert {item["scopeTitle"] for item in study} == {"Algebra", "Calculus"}
    assert {item["status"] for item in study} == {"interrupted"}
    assert all(item["canResume"] and not item["canRetry"] for item in study)
    assert all(item["returnTarget"].startswith("/study/course-") for item in study)

    studio = next(item for item in items if item["domain"] == "studio")
    assert studio["kind"] == "project_scene"
    assert studio["status"] == "recoverable"
    assert studio["canResume"] is studio["canRetry"] is False
    assert studio["returnTarget"] == f"/studio/{project['id']}"

    filtered = client.get(
        "/api/desk/activity?statuses=recoverable&limit=10", headers=_headers()
    )
    assert [item["id"] for item in filtered.json()["items"]] == [
        f"studio:project:{project['id']}"
    ]


def test_global_activity_rejects_unknown_public_status(activity_client):
    client, _learning_db = activity_client
    response = client.get(
        "/api/desk/activity?statuses=waiting_for_learner", headers=_headers()
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "activity_invalid_request"


def test_global_activity_projects_retryable_knowledge_core_compilation(
    activity_client,
):
    client, learning_db = activity_client
    learning_store = LearningStore(learning_db)
    try:
        context = LearningExecutionContext(learning_store, OWNER)
        context.create_space(title="Calculus", space_id="course-calculus")
    finally:
        learning_store.close()
    runtime = KnowledgeCoreCompilationStore(
        learning_db.parent / "knowledge_core_compilations.db"
    )
    try:
        run, _created = runtime.create_or_reuse(
            OWNER,
            {
                "space_id": "course-calculus",
                "outline_node_id": "limits",
                "trigger": "start_learning",
                "expected_map_revision": 1,
                "idempotency_key": "compile-limits",
            },
            source_fingerprint="1" * 64,
            compilation_key="2" * 64,
            initial_status="needs_source",
            reason_code="outline_locator_missing",
        )
    finally:
        runtime.close()

    response = client.get("/api/desk/activity", headers=_headers())

    assert response.status_code == 200
    item = next(
        row
        for row in response.json()["items"]
        if row["kind"] == "knowledge_core_compilation"
    )
    assert item["id"] == (
        f"study:knowledge_core_compilation:{run['run_id']}"
    )
    assert item["status"] == "waiting"
    assert item["canRetry"] is True
    assert item["canResume"] is False
    assert item["outlineNodeId"] == "limits"
    assert item["reasonCode"] == "outline_locator_missing"
    assert item["returnTarget"] == (
        "/study/course-calculus/plan?outlineNodeId=limits"
    )
