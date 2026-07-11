# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""End-to-end desk route coverage for active Python code quiz grading."""

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
from learning.output_writer import OutputWriter  # noqa: E402


OWNER = "desktop:code-grading-owner"
SECRET = "study-code-grading-secret"


@pytest.fixture()
def study_client(tmp_path):
    from fastapi.testclient import TestClient
    from desk_server.app import create_app

    db_path = tmp_path / "learning.db"
    with patch.dict(os.environ, {"HERMESDESK_BRIDGE_SECRET": SECRET}, clear=False):
        with patch("learning.learning_store.default_learning_db_path", return_value=db_path):
            with patch("learning_owner.desktop_owner_id", return_value=OWNER):
                yield TestClient(create_app()), db_path


def _headers():
    return {"X-HermesDesk-Auth": SECRET}


def _seed_code_quiz(db_path: Path) -> str:
    store = LearningStore(db_path=db_path)
    try:
        ctx = LearningExecutionContext(store, owner_id=OWNER)
        ctx.create_space(title="Python", space_id="python")
        return OutputWriter(ctx).write_artifact(
            kind="quiz",
            title="Add",
            payload={
                "questions": [
                    {
                        "type": "code",
                        "prompt": "Implement add",
                        "language": "python",
                        "mode": "solve",
                        "starter": "# implement below",
                        "test_code": "assert add(2, 3) == 5",
                        "reference": "def add(a, b): return a + b",
                        "points": 2,
                    }
                ]
            },
        )["artifact_id"]
    finally:
        store.close()


def test_code_question_route_hides_secrets_and_runs_active_sandbox(study_client):
    client, db_path = study_client
    artifact_id = _seed_code_quiz(db_path)

    activated = client.post(
        f"/api/desk/study/artifacts/{artifact_id}/activate", headers=_headers()
    )
    assert activated.status_code == 200

    questions = client.get(
        f"/api/desk/study/quizzes/{artifact_id}/questions", headers=_headers()
    )
    assert questions.status_code == 200
    question = questions.json()["questions"][0]
    assert question["starter"] == "# implement below"
    assert "test_code" not in question
    assert "reference" not in question

    submitted = client.post(
        f"/api/desk/study/quizzes/{artifact_id}/submit",
        json={
            "responses": {
                question["item_id"]: {"code": "def add(a, b):\n    return a + b"}
            }
        },
        headers=_headers(),
    )
    assert submitted.status_code == 200
    result = submitted.json()
    assert result["score"] == 2
    assert result["maxScore"] == 2
    assert result["perQuestion"][0]["mode"] == "solve"
    assert result["perQuestion"][0]["timed_out"] is False


def test_practice_route_creates_a_reviewable_self_checked_variant_draft(study_client):
    client, db_path = study_client
    artifact_id = _seed_code_quiz(db_path)
    client.post(f"/api/desk/study/artifacts/{artifact_id}/activate", headers=_headers())
    question = client.get(
        f"/api/desk/study/quizzes/{artifact_id}/questions", headers=_headers()
    ).json()["questions"][0]

    generated = client.post(
        f"/api/desk/study/quizzes/{artifact_id}/practice",
        json={"item_id": question["item_id"], "practice_kind": "variant"},
        headers=_headers(),
    )

    assert generated.status_code == 200
    result = generated.json()
    assert result["generated"] is True
    assert result["status"] == "draft"
    assert result["self_checked"] is True

    drafts = client.get("/api/desk/study/drafts?kind=quiz", headers=_headers())
    assert [draft["artifact_id"] for draft in drafts.json()["drafts"]] == [
        result["artifact_id"]
    ]
