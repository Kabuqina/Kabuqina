# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Tests for trusted desktop STUDY M2 routes."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "python" / "src"
CORE_DIR = ROOT / "hermes_core"
for p in (SRC_DIR, CORE_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from learning.learning_context import LearningExecutionContext  # noqa: E402
from learning.learning_store import LearningStore  # noqa: E402
from learning.output_writer import OutputWriter  # noqa: E402


OWNER = "desktop:test-owner"
SECRET = "study-route-secret"


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


def _seed_draft(db_path: Path, *, status: str = "draft") -> str:
    store = LearningStore(db_path=db_path)
    try:
        ctx = LearningExecutionContext(store, owner_id=OWNER)
        ctx.create_space(title="Algebra", space_id="s1")
        artifact_id = OutputWriter(ctx).write_artifact(
            kind="flashcard_deck",
            title="Deck",
            payload={"cards": [{"front": "2+2", "back": "4"}]},
        )["artifact_id"]
        if status == "active":
            ctx.set_artifact_status(artifact_id, "active")
        return artifact_id
    finally:
        store.close()


def _seed_quiz_draft(db_path: Path) -> str:
    store = LearningStore(db_path=db_path)
    try:
        ctx = LearningExecutionContext(store, owner_id=OWNER)
        ctx.create_space(title="Algebra", space_id="s1")
        return OutputWriter(ctx).write_artifact(
            kind="quiz",
            title="Diagnostic quiz",
            payload={
                "questions": [
                    {
                        "type": "choice",
                        "prompt": "2+2?",
                        "options": ["3", "4"],
                        "answer": 1,
                        "tags": ["arithmetic"],
                        "points": 2,
                    },
                    {
                        "type": "short_answer",
                        "prompt": "Optimizer abbreviated GD?",
                        "answer": "gradient descent",
                        "accepted": ["GD"],
                        "tags": ["optimization"],
                    },
                ]
            },
        )["artifact_id"]
    finally:
        store.close()


def test_space_routes_create_list_and_select(study_client):
    client, _db_path = study_client

    created = client.post(
        "/api/desk/study/spaces",
        json={"title": "Algebra"},
        headers=_headers(),
    )
    assert created.status_code == 200
    sid = created.json()["space_id"]
    assert sid

    listed = client.get("/api/desk/study/spaces", headers=_headers())
    assert listed.status_code == 200
    assert listed.json()["currentSpaceId"] == sid
    assert [space["title"] for space in listed.json()["spaces"]] == ["Algebra"]

    selected = client.post(f"/api/desk/study/spaces/{sid}/select", headers=_headers())
    assert selected.status_code == 200
    assert selected.json()["space_id"] == sid


def test_flashcard_draft_activate_and_review_routes(study_client):
    client, db_path = study_client
    artifact_id = _seed_draft(db_path)

    drafts = client.get(
        "/api/desk/study/drafts?kind=flashcard_deck",
        headers=_headers(),
    )
    assert drafts.status_code == 200
    assert [item["artifact_id"] for item in drafts.json()["drafts"]] == [artifact_id]

    activated = client.post(
        f"/api/desk/study/artifacts/{artifact_id}/activate",
        headers=_headers(),
    )
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"
    assert activated.json()["materialized"] == 1

    cards = client.get("/api/desk/study/flashcards?due_only=true", headers=_headers())
    assert cards.status_code == 200
    assert len(cards.json()["cards"]) == 1
    item_id = cards.json()["cards"][0]["item_id"]

    reviewed = client.post(
        "/api/desk/study/flashcards/review",
        json={"item_id": item_id, "grade": "good"},
        headers=_headers(),
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["grade"] == "good"
    assert reviewed.json()["repetitions"] == 1


def test_reject_route_keeps_draft_out_of_practice(study_client):
    client, db_path = study_client
    artifact_id = _seed_draft(db_path)

    rejected = client.post(
        f"/api/desk/study/artifacts/{artifact_id}/reject",
        headers=_headers(),
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    cards = client.get("/api/desk/study/flashcards", headers=_headers())
    assert cards.status_code == 200
    assert cards.json()["cards"] == []


def test_legacy_flashcard_migration_is_idempotent(study_client):
    client, _db_path = study_client
    payload = {
        "deck": {
            "cards": [
                {"front": "legacy q", "back": "legacy a", "hint": "h", "tags": ["old"]}
            ]
        }
    }

    first = client.post(
        "/api/desk/study/migrations/flashcards",
        json=payload,
        headers=_headers(),
    )
    assert first.status_code == 200
    assert first.json()["migrated"] is True
    assert first.json()["cards"] == 1
    assert first.json()["status"] == "active"

    second = client.post(
        "/api/desk/study/migrations/flashcards",
        json=payload,
        headers=_headers(),
    )
    assert second.status_code == 200
    assert second.json()["migrated"] is False

    cards = client.get("/api/desk/study/flashcards", headers=_headers())
    assert [card["front"] for card in cards.json()["cards"]] == ["legacy q"]


def test_quiz_draft_activate_questions_and_submit_routes(study_client):
    client, db_path = study_client
    artifact_id = _seed_quiz_draft(db_path)

    activated = client.post(
        f"/api/desk/study/artifacts/{artifact_id}/activate",
        headers=_headers(),
    )
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"
    assert activated.json()["materialized"] == 2

    quizzes = client.get("/api/desk/study/quizzes", headers=_headers())
    assert quizzes.status_code == 200
    assert [item["artifact_id"] for item in quizzes.json()["quizzes"]] == [artifact_id]

    questions = client.get(
        f"/api/desk/study/quizzes/{artifact_id}/questions",
        headers=_headers(),
    )
    assert questions.status_code == 200
    rows = questions.json()["questions"]
    assert [row["prompt"] for row in rows] == ["2+2?", "Optimizer abbreviated GD?"]
    assert all("answer" not in row for row in rows)

    submitted = client.post(
        f"/api/desk/study/quizzes/{artifact_id}/submit",
        json={
            "responses": {
                rows[0]["item_id"]: {"selected": [1]},
                rows[1]["item_id"]: {"text": " gd! "},
            }
        },
        headers=_headers(),
    )
    assert submitted.status_code == 200
    assert submitted.json()["score"] == 3
    assert submitted.json()["maxScore"] == 3
    assert submitted.json()["correctCount"] == 2


def test_legacy_quiz_migration_is_idempotent(study_client):
    client, _db_path = study_client
    payload = {
        "quiz": {
            "title": "Legacy quiz",
            "questions": [
                {
                    "type": "choice",
                    "prompt": "legacy q",
                    "options": ["a", "b"],
                    "answer": 0,
                }
            ],
        }
    }

    first = client.post(
        "/api/desk/study/migrations/quizzes",
        json=payload,
        headers=_headers(),
    )
    assert first.status_code == 200
    assert first.json()["migrated"] is True
    assert first.json()["questions"] == 1
    assert first.json()["status"] == "active"

    second = client.post(
        "/api/desk/study/migrations/quizzes",
        json=payload,
        headers=_headers(),
    )
    assert second.status_code == 200
    assert second.json()["migrated"] is False

    quizzes = client.get("/api/desk/study/quizzes", headers=_headers())
    assert [item["title"] for item in quizzes.json()["quizzes"]] == ["Legacy quiz"]


def test_empty_context_migration_does_not_seed_learning_data(study_client):
    client, db_path = study_client

    migrated = client.post(
        "/api/desk/study/migrations/context",
        json={"context": {}},
        headers=_headers(),
    )

    assert migrated.status_code == 200
    assert migrated.json() == {
        "migrated": True,
        "student_state": None,
        "evaluation": None,
    }
    store = LearningStore(db_path=db_path)
    try:
        assert store.list_spaces(OWNER) == []
    finally:
        store.close()


def test_student_state_save_persists_canonical_context_and_archives_old(study_client):
    client, db_path = study_client
    first = client.put(
        "/api/desk/study/student-state",
        json={"state": {"course": "Algebra", "goals": ["Pass"]}},
        headers=_headers(),
    )
    assert first.status_code == 200

    state = {
        "course": "Calculus",
        "goals": ["Master limits"],
        "preferences": {
            "profile_summary": "Visual learner",
            "study_preferences": "Daily examples",
        },
        "progress_notes": ["Chapter 1 complete", "Limits guide"],
        "current_stage": "Practice",
        "next_adjustment": "Add mixed exercises",
    }
    evaluation = {
        "observations": [
            "Concepts improving",
            "Quiz 7/10",
            "Review epsilon-delta",
        ],
        "weak_points": ["one-sided limits"],
        "suggestions": ["Add mixed exercises"],
        "evidence_refs": [{"origin": "study_profile_editor"}],
    }
    second = client.put(
        "/api/desk/study/student-state",
        json={"state": state, "evaluation": evaluation},
        headers=_headers(),
    )
    assert second.status_code == 200
    assert second.json()["state"]["payload"] == {**state, "constraints": []}
    assert second.json()["evaluation"]["status"] == "active"

    loaded = client.get("/api/desk/study/student-state", headers=_headers())
    assert loaded.status_code == 200
    assert loaded.json()["state"]["payload"]["progress_notes"] == [
        "Chapter 1 complete",
        "Limits guide",
    ]

    store = LearningStore(db_path=db_path)
    try:
        sid = store.get_current_space(OWNER)
        active = store.list_artifacts(OWNER, sid, kind="student_state", status="active")
        archived = store.list_artifacts(OWNER, sid, kind="student_state", status="archived")
        assert len(active) == 1
        assert len(archived) == 1
        assert active[0]["review"]["status"] == "passed"
    finally:
        store.close()


def test_learning_plan_activation_archives_previous_and_materializes_items(study_client):
    client, db_path = study_client
    store = LearningStore(db_path=db_path)
    try:
        ctx = LearningExecutionContext(store, owner_id=OWNER)
        ctx.create_space(title="Algebra", space_id="s1")
        ids = [
            OutputWriter(ctx).write_artifact(
                kind="learning_plan",
                title=title,
                payload={
                    "phases": [
                        {"title": "Phase", "tasks": [{"title": "Practice", "order": 1}]}
                    ]
                },
            )["artifact_id"]
            for title in ("First", "Second")
        ]
    finally:
        store.close()

    first = client.post(f"/api/desk/study/artifacts/{ids[0]}/activate", headers=_headers())
    second = client.post(f"/api/desk/study/artifacts/{ids[1]}/activate", headers=_headers())
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["materialized"] == 1

    store = LearningStore(db_path=db_path)
    try:
        assert [
            row["artifact_id"]
            for row in store.list_artifacts(OWNER, "s1", kind="learning_plan", status="active")
        ] == [ids[1]]
        assert [
            row["artifact_id"]
            for row in store.list_artifacts(OWNER, "s1", kind="learning_plan", status="archived")
        ] == [ids[0]]
        assert store.get_artifact(OWNER, "s1", ids[1])["review"]["status"] == "passed"
    finally:
        store.close()


def test_cache_clear_removes_only_desktop_owner_learning_data(study_client):
    client, db_path = study_client
    _seed_draft(db_path, status="active")
    other_owner = "gateway:discord:other"
    store = LearningStore(db_path=db_path)
    try:
        other_ctx = LearningExecutionContext(store, owner_id=other_owner)
        other_ctx.create_space(title="Other", space_id="other-space")
        OutputWriter(other_ctx).write_artifact(
            kind="flashcard_deck",
            title="Other deck",
            payload={"cards": [{"front": "safe", "back": "kept"}]},
        )
    finally:
        store.close()

    response = client.post("/api/desk/study/cache/clear", headers=_headers())

    assert response.status_code == 200
    assert response.json()["cleared"] is True
    assert response.json()["counts"]["learning_artifacts"] == 1
    store = LearningStore(db_path=db_path)
    try:
        assert store.list_spaces(OWNER) == []
        assert len(store.list_spaces(other_owner)) == 1
        assert len(store.list_artifacts(other_owner, "other-space")) == 1
    finally:
        store.close()
