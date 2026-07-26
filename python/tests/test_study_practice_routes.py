# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

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
from learning.quizzes import QuizService  # noqa: E402


OWNER = "desktop:practice-owner"
SECRET = "study-practice-secret"


@pytest.fixture()
def study_client(tmp_path):
    from fastapi.testclient import TestClient
    from desk_server.app import create_app

    db_path = tmp_path / "learning.db"
    with patch.dict(os.environ, {"HERMESDESK_BRIDGE_SECRET": SECRET}, clear=False):
        with patch(
            "learning.learning_store.default_learning_db_path", return_value=db_path
        ):
            with patch("learning_owner.desktop_owner_id", return_value=OWNER):
                yield TestClient(create_app()), db_path


def _headers():
    return {"X-HermesDesk-Auth": SECRET}


def _seed(db_path, *, active=True):
    store = LearningStore(db_path=db_path)
    try:
        ctx = LearningExecutionContext(store, owner_id=OWNER)
        ctx.create_space(title="Algebra", space_id="s1")
        artifact_id = OutputWriter(ctx).write_artifact(
            kind="quiz",
            title="Assisted quiz",
            payload={
                "questions": [
                    {
                        "type": "short_answer",
                        "prompt": "Why?",
                        "answer": "definition",
                        "hint_ladder": {
                            "schema_version": 1,
                            "direction": "Start from the definition.",
                            "full_solution": "Use the definition directly.",
                        },
                    }
                ]
            },
        )["artifact_id"]
        if active:
            QuizService(ctx).activate_quiz(artifact_id)
            item_id = QuizService(ctx).list_questions(
                artifact_id=artifact_id
            )[0]["item_id"]
        else:
            item_id = f"{artifact_id}-0000"
        return artifact_id, item_id
    finally:
        store.close()


def _hint_body(key="hint-1", level="direction"):
    return {
        "schema_version": 1,
        "space_id": "s1",
        "idempotency_key": key,
        "level": level,
    }


def test_hint_route_returns_one_explicit_level_and_replays(study_client):
    client, db_path = study_client
    artifact_id, item_id = _seed(db_path)
    path = f"/api/desk/study/quizzes/{artifact_id}/questions/{item_id}/hints"

    first = client.post(path, json=_hint_body(level="full_solution"), headers=_headers())
    replay = client.post(path, json=_hint_body(level="full_solution"), headers=_headers())

    assert first.status_code == 200
    assert first.json()["content"] == "Use the definition directly."
    assert first.json()["budget_summary"]["provider_attempts"] == 0
    assert first.json()["replayed"] is False
    assert replay.status_code == 200
    assert replay.json()["activity_id"] == first.json()["activity_id"]
    assert replay.json()["replayed"] is True


def test_hint_route_conflict_invalid_fields_and_missing_item_are_structured(study_client):
    client, db_path = study_client
    artifact_id, item_id = _seed(db_path)
    path = f"/api/desk/study/quizzes/{artifact_id}/questions/{item_id}/hints"
    assert client.post(path, json=_hint_body(level="direction"), headers=_headers()).status_code == 200

    conflict = client.post(
        path, json=_hint_body(level="full_solution"), headers=_headers()
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "study_conflict"

    unknown = client.post(
        path,
        json={**_hint_body("hint-2"), "owner_id": "attacker"},
        headers=_headers(),
    )
    assert unknown.status_code == 400
    assert unknown.json()["detail"]["code"] == "study_invalid_request"

    missing = client.post(
        f"/api/desk/study/quizzes/{artifact_id}/questions/missing/hints",
        json=_hint_body("hint-3"),
        headers=_headers(),
    )
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "study_not_found"


def test_hint_route_rejects_draft_and_question_route_never_leaks_ladder(study_client):
    client, db_path = study_client
    draft_id, draft_item = _seed(db_path, active=False)
    blocked = client.post(
        f"/api/desk/study/quizzes/{draft_id}/questions/{draft_item}/hints",
        json=_hint_body(),
        headers=_headers(),
    )
    assert blocked.status_code == 400

    active_id, _item_id = _seed(db_path)
    questions = client.get(
        f"/api/desk/study/quizzes/{active_id}/questions?space_id=s1",
        headers=_headers(),
    )
    assert questions.status_code == 200
    assert "hint_ladder" not in str(questions.json())
    assert "Use the definition" not in str(questions.json())


def test_submit_route_exposes_outcome_and_hash_only_provenance(study_client):
    client, db_path = study_client
    artifact_id, item_id = _seed(db_path)

    result = client.post(
        f"/api/desk/study/quizzes/{artifact_id}/submit",
        json={
            "space_id": "s1",
            "responses": {item_id: {"text": "definition"}},
            "item_ids": [item_id],
        },
        headers=_headers(),
    )

    assert result.status_code == 200
    grade = result.json()["perQuestion"][0]
    assert grade["outcome"] == "correct"
    assert grade["grader_provenance"]["source_kind"] == "activated_quiz_item"
    assert len(grade["grader_provenance"]["rubric_sha256"]) == 64
    assert "answer" not in grade
