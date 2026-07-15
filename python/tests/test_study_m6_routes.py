from __future__ import annotations
from copy import deepcopy
import os, sys
from pathlib import Path
from unittest.mock import patch
import pytest

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "python" / "src", ROOT / "hermes_core"):
    if str(path) not in sys.path: sys.path.insert(0, str(path))

from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningStore
from learning.output_writer import OutputWriter

OWNER, SECRET = "desktop:m6-owner", "m6-secret"

@pytest.fixture()
def client(tmp_path):
    from fastapi.testclient import TestClient
    from desk_server.app import create_app
    db = tmp_path / "learning.db"
    with patch.dict(os.environ, {"HERMESDESK_BRIDGE_SECRET": SECRET}, clear=False):
        with patch("learning.learning_store.default_learning_db_path", return_value=db):
            with patch("learning_owner.desktop_owner_id", return_value=OWNER):
                yield TestClient(create_app()), db

def headers(): return {"X-HermesDesk-Auth": SECRET}

def seed(db):
    store = LearningStore(db_path=db)
    try:
        ctx = LearningExecutionContext(store, OWNER)
        ctx.create_space(title="Course", space_id="s")
        for index in range(3):
            OutputWriter(ctx).write_artifact(kind="tutoring_note", title=f"N{index}", payload={"goal":"g","hints":[f"secret-{index}"]})
        ctx.record_activity(activity_type="quiz.attempt", artifact_id="quiz", detail={"score":0,"maxScore":1,"percent":0,"weakTags":["algebra"],"response":"SECRET"})
    finally: store.close()

def test_bounded_drafts_and_wrongbook_routes(client):
    http, db = client; seed(db)
    drafts = http.get("/api/desk/study/drafts?limit=2", headers=headers()).json()
    assert drafts["count"] == 3 and drafts["returned"] == 2 and drafts["truncated"] is True
    assert drafts["kind_counts"] == {"tutoring_note": 3}
    assert "secret-" not in str(drafts)
    assert set(drafts["items"][0]) == {
        "artifact_id", "kind", "title", "status", "review", "updated_at",
    }
    assert drafts["items"][0]["review"] == {"mode": "deterministic", "status": "pending"}
    detail = http.get(
        f"/api/desk/study/artifacts/{drafts['items'][0]['artifact_id']}?space_id=s",
        headers=headers(),
    ).json()
    assert "secret-" in str(detail["artifact"]["envelope"])
    wrong = http.get("/api/desk/study/wrongbook?space_id=s&limit=1", headers=headers()).json()
    assert wrong["weak_points"] == ["algebra"]
    assert "SECRET" not in str(wrong)

def test_artifact_filter_and_status_transition(client):
    http, db = client; seed(db)
    listed = http.get(
        "/api/desk/study/artifacts?space_id=s&kind=tutoring_note&status=draft&limit=1",
        headers=headers(),
    ).json()
    assert listed["count"] == 3 and listed["returned"] == 1
    artifact_id = listed["items"][0]["artifact_id"]
    active = http.post(
        f"/api/desk/study/artifacts/{artifact_id}/status",
        json={"space_id":"s", "status":"active"}, headers=headers(),
    )
    assert active.json()["status"] == "active"
    archived = http.post(
        f"/api/desk/study/artifacts/{artifact_id}/status",
        json={"space_id":"s", "status":"archived"}, headers=headers(),
    )
    assert archived.json()["status"] == "archived"

def test_export_delete_import_roundtrip(client):
    http, db = client; seed(db)
    bundle = http.get("/api/desk/study/data/export", headers=headers()).json()["bundle"]
    denied = http.request("DELETE", "/api/desk/study/data", json={"confirm":"no"}, headers=headers())
    assert denied.status_code == 400
    assert denied.json()["detail"]["code"] == "study_invalid_request"
    deleted = http.request("DELETE", "/api/desk/study/data", json={"confirm":"DELETE ALL LEARNING DATA"}, headers=headers())
    assert deleted.json()["deleted"] is True
    invalid = deepcopy(bundle)
    invalid["artifacts"].append(deepcopy(invalid["artifacts"][0]))
    rejected = http.post("/api/desk/study/data/import", json={"bundle": invalid}, headers=headers())
    assert rejected.status_code == 400
    assert rejected.json()["detail"]["code"] == "study_invalid_request"
    assert http.get("/api/desk/study/drafts", headers=headers()).json()["count"] == 0
    imported = http.post("/api/desk/study/data/import", json={"bundle":bundle}, headers=headers())
    assert imported.json()["imported"]["artifacts"] == 3
    assert http.get("/api/desk/study/drafts", headers=headers()).json()["count"] == 3

def test_import_nonempty_owner_returns_structured_conflict(client):
    http, db = client
    seed(db)
    response = http.post(
        "/api/desk/study/data/import",
        json={"bundle": {"version": 1, "spaces": []}},
        headers=headers(),
    )
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "study_conflict",
        "message": "owner already has learning data; delete it before import",
    }

def test_governance_routes_preserve_the_study_error_contract(client):
    http, _db = client
    with patch("desk_server.routes.study_routes._desktop_ctx", side_effect=ValueError("unavailable")):
        responses = [
            http.get("/api/desk/study/data/export", headers=headers()),
            http.request("DELETE", "/api/desk/study/data", json={"confirm":"DELETE ALL LEARNING DATA"}, headers=headers()),
            http.get("/api/desk/study/migrations/status", headers=headers()),
            http.get("/api/desk/study/migrations/failures/export", headers=headers()),
        ]
    for response in responses:
        assert response.status_code == 400
        assert response.json()["detail"] == {
            "code": "study_invalid_request",
            "message": "unavailable",
        }

def test_failed_migration_is_exportable(client):
    http, _db = client
    response = http.post(
        "/api/desk/study/migrations/flashcards",
        json={"deck":{"cards":[{"front": 7, "back":"bad"}]}}, headers=headers(),
    )
    assert response.status_code == 409
    failures = http.get("/api/desk/study/migrations/failures/export", headers=headers()).json()
    assert failures["count"] == 1
    assert failures["failures"][0]["migration_key"].endswith("flashcards.v1")

def test_successful_migration_status_is_queryable(client):
    http, db = client
    store = LearningStore(db_path=db)
    try:
        ctx = LearningExecutionContext(store, OWNER)
        ctx.mark_migration("legacy:done", detail={"count": 2})
    finally:
        store.close()
    status = http.get("/api/desk/study/migrations/status", headers=headers()).json()
    assert status["count"] == 1
    assert status["migrations"][0]["migration_key"] == "legacy:done"
    assert status["migrations"][0]["status"] == "done"
    assert status["migrations"][0]["detail"] == {"count": 2}
