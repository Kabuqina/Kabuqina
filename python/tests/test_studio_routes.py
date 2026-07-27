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


OWNER = "desktop:studio-test-owner"
SECRET = "studio-route-secret"


@pytest.fixture()
def studio_client(tmp_path):
    from fastapi.testclient import TestClient
    from desk_server.app import create_app

    learning_db = tmp_path / "learning.db"
    studio_db = tmp_path / "studio.db"
    with patch.dict(os.environ, {"HERMESDESK_BRIDGE_SECRET": SECRET}, clear=False):
        with patch("learning.learning_store.default_learning_db_path", return_value=learning_db):
            with patch("studio_store.default_studio_db_path", return_value=studio_db):
                with patch("learning_owner.desktop_owner_id", return_value=OWNER):
                    yield TestClient(create_app()), learning_db, studio_db


def _headers():
    return {"X-HermesDesk-Auth": SECRET}


def _seed_active_artifact(learning_db: Path, *, artifact_id: str | None = None) -> str:
    store = LearningStore(db_path=learning_db)
    try:
        ctx = LearningExecutionContext(store, owner_id=OWNER)
        ctx.create_space(title="Algebra", space_id="space-1")
        created = OutputWriter(ctx).write_artifact(
            kind="knowledge_base",
            title="Limits",
            payload={
                "concepts": [
                    {
                        "term": "limit",
                        "explanation": "A limit describes approaching a value.",
                    }
                ]
            },
        )
        result_id = created["artifact_id"]
        ctx.set_artifact_status(result_id, "active")
        return result_id
    finally:
        store.close()


def _create_project(client) -> dict:
    response = client.post(
        "/api/desk/studio/projects",
        json={"title": "Explain limits"},
        headers=_headers(),
    )
    assert response.status_code == 200
    return response.json()


def test_new_install_lists_empty_projects(studio_client):
    client, _learning_db, _studio_db = studio_client
    response = client.get("/api/desk/studio/projects", headers=_headers())
    assert response.status_code == 200
    assert response.json() == {"projects": []}


def test_project_and_brief_survive_store_restart(studio_client):
    client, _learning_db, _studio_db = studio_client
    created = _create_project(client)
    assert created["stage"] == "brief"
    assert created["sources"] == []

    saved = client.post(
        f"/api/desk/studio/projects/{created['id']}/brief",
        json={"brief": "Explain limits to someone seeing calculus for the first time."},
        headers=_headers(),
    )
    assert saved.status_code == 200
    assert saved.json()["stage"] == "gathering"

    listed = client.get("/api/desk/studio/projects", headers=_headers())
    assert listed.status_code == 200
    assert listed.json()["projects"][0]["brief"].startswith("Explain limits")


def test_gather_creates_read_only_study_snapshot(studio_client):
    client, learning_db, _studio_db = studio_client
    artifact_id = _seed_active_artifact(learning_db)
    project = _create_project(client)

    gathered = client.post(
        f"/api/desk/studio/projects/{project['id']}/sources",
        json={
            "refs": [
                {
                    "kind": "study_artifact",
                    "spaceId": "space-1",
                    "artifactId": artifact_id,
                }
            ]
        },
        headers=_headers(),
    )
    assert gathered.status_code == 200
    payload = gathered.json()
    assert payload["stage"] == "shaping"
    assert len(payload["sources"]) == 1
    source = payload["sources"][0]
    assert source["kind"] == "study_artifact"
    assert source["title"] == "Limits"
    assert source["origin"] == "Algebra · knowledge_base"
    assert "approaching a value" in source["excerpt"]
    assert source["returnTarget"] == "/study/space-1/learn"
    assert source["fallbackTarget"] == "/study/space-1"

    edited = client.post(
        f"/api/desk/studio/projects/{project['id']}/brief",
        json={"brief": "A refined audience and purpose."},
        headers=_headers(),
    )
    assert edited.status_code == 200
    assert edited.json()["stage"] == "shaping"
    assert len(edited.json()["sources"]) == 1

    learning = LearningStore(db_path=learning_db)
    try:
        original = learning.get_artifact(OWNER, "space-1", artifact_id)
        assert original is not None
        assert original["status"] == "active"
        assert original["version"] == source["revision"]
    finally:
        learning.close()


def test_gather_is_atomic_when_any_reference_is_missing(studio_client):
    client, learning_db, _studio_db = studio_client
    artifact_id = _seed_active_artifact(learning_db)
    project = _create_project(client)

    failed = client.post(
        f"/api/desk/studio/projects/{project['id']}/sources",
        json={
            "refs": [
                {
                    "kind": "study_artifact",
                    "spaceId": "space-1",
                    "artifactId": artifact_id,
                },
                {
                    "kind": "study_artifact",
                    "spaceId": "space-1",
                    "artifactId": "missing-artifact",
                },
            ]
        },
        headers=_headers(),
    )
    assert failed.status_code == 404

    listed = client.get("/api/desk/studio/projects", headers=_headers()).json()
    restored = next(item for item in listed["projects"] if item["id"] == project["id"])
    assert restored["sources"] == []
    assert restored["stage"] == "brief"
