# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Trusted Desktop route coverage for S-2 whiteboard runtime."""

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

from learning.learning_store import LearningStore  # noqa: E402


OWNER = "desktop:whiteboard-owner"
SECRET = "whiteboard-route-secret"


def _headers():
    return {"X-HermesDesk-Auth": SECRET}


def _scene(label="one"):
    return {
        "schema_version": 1,
        "elements": [
            {
                "element_id": "e1",
                "type": "math",
                "x": 0,
                "y": 0,
                "tone": "accent",
                "stroke_width": 2,
                "width": 200,
                "height": 60,
                "content": f"x + y = {label}",
            }
        ],
    }


@pytest.fixture()
def study_client(tmp_path):
    from fastapi.testclient import TestClient
    from desk_server.app import create_app

    db_path = tmp_path / "learning.db"
    store = LearningStore(db_path)
    try:
        store.create_space(OWNER, title="Algebra", space_id="s1")
    finally:
        store.close()
    with patch.dict(os.environ, {"HERMESDESK_BRIDGE_SECRET": SECRET}, clear=False):
        with patch(
            "learning.learning_store.default_learning_db_path", return_value=db_path
        ):
            with patch("learning_owner.desktop_owner_id", return_value=OWNER):
                yield TestClient(create_app()), db_path


def _save_body(key="save-1", expected=0, label="one"):
    return {
        "schema_version": 1,
        "space_id": "s1",
        "lineage_id": "lineage-1",
        "expected_revision": expected,
        "idempotency_key": key,
        "scene": _scene(label),
    }


def test_whiteboard_route_save_list_load_snapshot_restore_export(study_client):
    client, _ = study_client
    working_path = "/api/desk/study/whiteboards/working/activity-1"

    first = client.put(working_path, json=_save_body(), headers=_headers())
    replay = client.put(working_path, json=_save_body(), headers=_headers())
    assert first.status_code == 200
    assert first.json()["revision"] == 1
    assert replay.json()["replayed"] is True

    listed = client.get(
        "/api/desk/study/whiteboards?space_id=s1", headers=_headers()
    )
    loaded = client.get(f"{working_path}?space_id=s1", headers=_headers())
    assert listed.status_code == 200
    assert listed.json()["items"][0]["activity_id"] == "activity-1"
    assert "scene" not in listed.json()["items"][0]
    assert loaded.json()["state"]["scene"] == _scene()

    created = client.post(
        f"{working_path}/snapshots",
        json={
            "schema_version": 1,
            "space_id": "s1",
            "expected_working_revision": 1,
            "idempotency_key": "snapshot-1",
        },
        headers=_headers(),
    )
    assert created.status_code == 200
    artifact_id = created.json()["artifact_id"]
    exported = client.get(
        f"/api/desk/study/whiteboards/snapshots/{artifact_id}/export?space_id=s1",
        headers=_headers(),
    )
    assert exported.status_code == 200
    assert exported.json()["envelope"]["payload"]["scene"] == _scene()

    client.put(
        working_path,
        json=_save_body("save-2", expected=1, label="two"),
        headers=_headers(),
    )
    restored = client.post(
        f"/api/desk/study/whiteboards/snapshots/{artifact_id}/restore",
        json={
            "schema_version": 1,
            "space_id": "s1",
            "expected_working_revision": 2,
            "idempotency_key": "restore-1",
        },
        headers=_headers(),
    )
    assert restored.status_code == 200
    assert restored.json()["revision"] == 3
    assert client.get(f"{working_path}?space_id=s1", headers=_headers()).json()[
        "state"
    ]["scene"] == _scene()


def test_whiteboard_routes_reject_owner_injection_conflict_and_cross_space(study_client):
    client, db_path = study_client
    path = "/api/desk/study/whiteboards/working/activity-1"

    injected = client.put(
        path,
        json={**_save_body(), "owner_id": "attacker"},
        headers=_headers(),
    )
    assert injected.status_code == 400
    assert injected.json()["detail"]["code"] == "study_invalid_request"

    assert client.put(path, json=_save_body(), headers=_headers()).status_code == 200
    drift = client.put(
        path,
        json=_save_body(label="different"),
        headers=_headers(),
    )
    assert drift.status_code == 409
    assert drift.json()["detail"]["code"] == "study_conflict"

    store = LearningStore(db_path)
    try:
        store.create_space(OWNER, title="Other", space_id="s2", make_current=False)
    finally:
        store.close()
    absent = client.get(f"{path}?space_id=s2", headers=_headers())
    assert absent.status_code == 404


def test_whiteboard_attach_and_exact_delete_preview_routes(study_client):
    client, _ = study_client
    working_path = "/api/desk/study/whiteboards/working/activity-1"
    client.put(working_path, json=_save_body(), headers=_headers())
    created = client.post(
        f"{working_path}/snapshots",
        json={
            "schema_version": 1,
            "space_id": "s1",
            "expected_working_revision": 1,
            "idempotency_key": "snapshot-1",
        },
        headers=_headers(),
    ).json()
    artifact_id = created["artifact_id"]

    attached = client.post(
        f"/api/desk/study/whiteboards/snapshots/{artifact_id}/attach",
        json={
            "schema_version": 1,
            "space_id": "s1",
            "idempotency_key": "attach-1",
        },
        headers=_headers(),
    )
    assert attached.status_code == 200
    preview = client.get(
        f"/api/desk/study/whiteboards/snapshots/{artifact_id}/delete-preview?space_id=s1",
        headers=_headers(),
    ).json()
    assert preview["requires_cascade"] is True
    deleted = client.request(
        "DELETE",
        f"/api/desk/study/whiteboards/snapshots/{artifact_id}",
        json={
            "schema_version": 1,
            "space_id": "s1",
            "target_artifact_ids": preview["target_artifact_ids"],
            "idempotency_key": "delete-1",
        },
        headers=_headers(),
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted_artifact_ids"] == [artifact_id]


def test_whiteboard_route_requires_loopback_auth(study_client):
    client, _ = study_client
    response = client.get("/api/desk/study/whiteboards?space_id=s1")
    assert response.status_code in {401, 403}
