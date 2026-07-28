# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Desktop HTTP contracts for the B-12 scratch notebook."""

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

from learning.learning_context import LearningExecutionContext  # noqa: E402
from learning.learning_store import LearningStore  # noqa: E402

OWNER = "desktop:scratch-routes"
SECRET = "scratch-route-secret"


@pytest.fixture()
def scratch_client(tmp_path):
    from fastapi.testclient import TestClient
    from desk_server.app import create_app

    db_path = tmp_path / "learning.db"
    with patch.dict(os.environ, {"HERMESDESK_BRIDGE_SECRET": SECRET}, clear=False):
        with patch("learning.learning_store.default_learning_db_path", return_value=db_path):
            with patch("learning_owner.desktop_owner_id", return_value=OWNER):
                yield TestClient(create_app()), db_path


def _headers():
    return {"X-HermesDesk-Auth": SECRET}


def test_spaces_seed_one_non_current_scratch_notebook(scratch_client):
    client, _ = scratch_client

    first = client.get("/api/desk/study/spaces", headers=_headers())
    second = client.get("/api/desk/study/spaces", headers=_headers())

    assert first.status_code == 200
    assert first.json()["currentSpaceId"] is None
    assert first.json() == second.json()
    scratch = [space for space in first.json()["spaces"] if space["kind"] == "scratch"]
    assert len(scratch) == 1
    assert scratch[0]["title"] == "杂记本"
    assert scratch[0]["is_current"] is False


def test_scratch_pad_round_trip_has_no_counts(scratch_client):
    client, _ = scratch_client
    spaces = client.get("/api/desk/study/spaces", headers=_headers()).json()["spaces"]
    scratch_id = next(space["space_id"] for space in spaces if space["kind"] == "scratch")

    saved = client.put(
        f"/api/desk/study/spaces/{scratch_id}/scratch/pad",
        json={"pad": "想到什么，就写什么。"},
        headers=_headers(),
    )
    page = client.get(
        f"/api/desk/study/spaces/{scratch_id}/scratch", headers=_headers()
    )

    assert saved.status_code == 200
    assert page.json() == {"pad": "想到什么，就写什么。", "notes": []}
    assert not ({"count", "pending", "unfiled"} & set(page.json()))


def test_scratch_notebook_cannot_be_selected_as_the_current_course(scratch_client):
    client, _ = scratch_client
    scratch_id = next(
        space["space_id"]
        for space in client.get("/api/desk/study/spaces", headers=_headers()).json()["spaces"]
        if space["kind"] == "scratch"
    )

    selected = client.post(
        f"/api/desk/study/spaces/{scratch_id}/select", headers=_headers()
    )

    assert selected.status_code == 400
    assert selected.json()["detail"]["code"] == "study_invalid_request"


def test_file_note_moves_it_to_a_course_draft(scratch_client):
    client, db_path = scratch_client
    scratch_id = next(
        space["space_id"]
        for space in client.get("/api/desk/study/spaces", headers=_headers()).json()["spaces"]
        if space["kind"] == "scratch"
    )
    store = LearningStore(db_path=db_path)
    try:
        ctx = LearningExecutionContext(store, OWNER)
        ctx.create_space(title="高等数学", space_id="course-1")
        ctx.add_scratch_note(
            scratch_id, text="极限描述趋近过程。", origin="来自对话", note_id="note-1"
        )
    finally:
        store.close()

    filed = client.post(
        f"/api/desk/study/spaces/{scratch_id}/scratch/notes/note-1/file",
        json={"target_space_id": "course-1"},
        headers=_headers(),
    )

    assert filed.status_code == 200
    assert filed.json()["status"] == "draft"
    page = client.get(
        f"/api/desk/study/spaces/{scratch_id}/scratch", headers=_headers()
    ).json()
    assert page["notes"] == []
    store = LearningStore(db_path=db_path)
    try:
        artifact = store.get_artifact(OWNER, "course-1", filed.json()["artifact_id"])
        assert artifact is not None
        assert artifact["status"] == "draft"
    finally:
        store.close()
