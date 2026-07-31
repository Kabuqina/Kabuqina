# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Tests for trusted desktop STUDY M2 routes."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "python" / "src"
CORE_DIR = ROOT / "hermes_core"
for p in (SRC_DIR, CORE_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from learning.learning_context import LearningExecutionContext  # noqa: E402
from learning.learning_store import LearningStore  # noqa: E402
from learning.learning_plans import (  # noqa: E402
    LEARNING_PLAN_ITEM_TYPE,
    LearningPlanService,
)
from learning.output_writer import OutputWriter  # noqa: E402
from learning.flashcards import FlashcardService  # noqa: E402
from learning.quizzes import QuizService  # noqa: E402


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
                        "knowledge_core_id": "core-arithmetic",
                        "origin": "source",
                        "source_refs": [
                            {"material_id": "book-1", "title": "Algebra", "locator": "p. 12"}
                        ],
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


def _seed_course_core_draft(db_path: Path) -> str:
    store = LearningStore(db_path=db_path)
    try:
        ctx = LearningExecutionContext(store, owner_id=OWNER)
        ctx.create_space(title="Algebra", space_id="s1")
        resource = ctx.put_artifact(
            kind="resource_pack",
            title="Algebra material",
            payload={
                "resources": [{"title": "Algebra.pdf", "purpose": "Primary"}],
                "outline": [
                    {
                        "id": "section-equations",
                        "title": "Linear equations",
                        "locator": "p. 12",
                    }
                ],
            },
            source_refs=[
                {
                    "origin": "imported",
                    "structure_status": "reliable",
                    "structure_origin": "embedded_pdf_outline",
                    "source_label": "Algebra.pdf",
                }
            ],
            review={"mode": "semantic", "status": "passed"},
        )
        ctx.set_artifact_status(resource["artifact_id"], "active")
        return OutputWriter(ctx).write_artifact(
            kind="flashcard_deck",
            title="Linear equation cores",
            payload={
                "cards": [
                    {
                        "front": "Linear equation",
                        "back": "An equation whose unknown has degree one.",
                        "knowledge_core_id": "core-linear-equation",
                        "outline_node_id": "section-equations",
                        "order": 0,
                        "source_refs": [
                            {
                                "origin": "kq-kp",
                                "material_id": "material-algebra",
                                "locator": "p. 12",
                                "knowledge_core_id": "core-linear-equation",
                                "outline_node_id": "section-equations",
                            }
                        ],
                    }
                ]
            },
        )["artifact_id"]
    finally:
        store.close()


def _material_alignment_payload() -> dict:
    return {
        "schema_version": 1,
        "batch_id": "batch-route",
        "materials": [
            {
                "material_id": "book",
                "title": "Book",
                "source_ref": "read:book",
                "structure": [
                    {"section_id": "s1", "title": "Limits", "locator": "§1"}
                ],
            },
            {
                "material_id": "exercises",
                "title": "Exercises",
                "source_ref": "read:exercises",
                "structure": [],
            },
        ],
        "course_groups": [
            {
                "group_id": "group-1",
                "proposed_title": "Calculus",
                "rationale": "Both materials concern calculus.",
                "material_ids": ["book", "exercises"],
                "skeleton": {
                    "material_id": "book",
                    "reason": "It has a real chapter structure.",
                    "role": "explanation",
                    "role_reason": "It explains the course.",
                },
                "attachments": [
                    {
                        "material_id": "exercises",
                        "role": "practice",
                        "role_reason": "It contains exercises.",
                        "mappings": [
                            {
                                "source_locator": "p.41",
                                "target_section_id": "s1",
                                "reason": "The page practices the skeleton section.",
                            }
                        ],
                        "unaligned": [],
                    }
                ],
            }
        ],
        "ungrouped": [],
    }


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
    assert [space["title"] for space in listed.json()["spaces"]] == ["Algebra", "杂记本"]
    assert [space["kind"] for space in listed.json()["spaces"]] == ["course", "scratch"]

    selected = client.post(f"/api/desk/study/spaces/{sid}/select", headers=_headers())
    assert selected.status_code == 200
    assert selected.json()["space_id"] == sid


def test_study_preferences_have_safe_defaults_and_persist_updates(study_client):
    client, _db_path = study_client
    defaults = client.get("/api/desk/study/preferences", headers=_headers())
    assert defaults.status_code == 200
    assert defaults.json() == {
        "importReadMode": "auto",
        "dailyNewCardLimit": 20,
        "dailyReviewCardLimit": 100,
        "defaults": {
            "importReadMode": "auto",
            "dailyNewCardLimit": 20,
            "dailyReviewCardLimit": 100,
        },
    }

    updated = client.put(
        "/api/desk/study/preferences",
        json={
            "importReadMode": "precise",
            "dailyNewCardLimit": 12,
            "dailyReviewCardLimit": 80,
        },
        headers=_headers(),
    )
    assert updated.status_code == 200
    assert updated.json()["importReadMode"] == "precise"
    assert updated.json()["dailyNewCardLimit"] == 12
    assert client.get(
        "/api/desk/study/preferences", headers=_headers()
    ).json()["dailyReviewCardLimit"] == 80

    invalid = client.put(
        "/api/desk/study/preferences",
        json={"dailyNewCardLimit": 101},
        headers=_headers(),
    )
    assert invalid.status_code == 400


def test_study_material_read_applies_import_only_cap_and_explicit_override(study_client):
    client, _db_path = study_client
    client.put(
        "/api/desk/study/preferences",
        json={"importReadMode": "auto"},
        headers=_headers(),
    )
    fake_result = json.dumps({"ok": True, "engine": "fake"})
    with patch(
        "desk_server.routes.study_routes.pdf_read_precise",
        return_value=fake_result,
    ) as reader:
        limited = client.post(
            "/api/desk/study/materials/read",
            json={"path": "course.pdf", "requestedMode": "math"},
            headers=_headers(),
        )
        assert limited.status_code == 200
        assert limited.json() | {"result": {}} == {
            "preferredMode": "auto",
            "requestedMode": "math",
            "effectiveMode": "auto",
            "limited": True,
            "override": False,
            "result": {},
        }
        assert limited.json()["result"] == {"ok": True, "engine": "fake"}
        assert reader.call_args.kwargs["mode"] == "auto"

        overridden = client.post(
            "/api/desk/study/materials/read",
            json={
                "path": "course.pdf",
                "requestedMode": "math",
                "override": True,
            },
            headers=_headers(),
        )
        assert overridden.status_code == 200
        assert overridden.json()["effectiveMode"] == "math"
        assert overridden.json()["limited"] is False
        assert reader.call_args.kwargs["mode"] == "math"


def test_study_material_read_rejects_tool_level_failure(study_client):
    client, _db_path = study_client
    with patch(
        "desk_server.routes.study_routes.pdf_read_precise",
        return_value=json.dumps({"ok": False, "error": "broken character map"}),
    ):
        response = client.post(
            "/api/desk/study/materials/read",
            json={"path": "course.pdf"},
            headers=_headers(),
        )

    assert response.status_code == 400
    assert "broken character map" in response.json()["detail"]["message"]


def test_study_material_read_registers_and_deduplicates_course_source(study_client):
    client, _db_path = study_client
    created = client.post(
        "/api/desk/study/spaces",
        json={"title": "Python 程序设计", "space_id": "python-course"},
        headers=_headers(),
    )
    assert created.status_code == 200
    fake_result = json.dumps({
        "ok": True,
        "engine": "docling",
        "read_id": "read-python-book",
        "pages": 12,
        "total_pages": 342,
        "structure_status": "reliable",
        "structure_origin": "embedded_pdf_outline",
        "outline": [{
            "id": "pdf-outline-1",
            "title": "第1章 计算机和程序",
            "level": 1,
            "page": 9,
            "children": [],
        }],
        "content": "",
    })
    request = {
        "spaceId": "python-course",
        "path": r"D:\books\Python程序设计.pdf",
        "includeContent": False,
        "pageStart": 1,
        "pageEnd": 12,
    }
    with patch(
        "desk_server.routes.study_routes.pdf_read_precise",
        return_value=fake_result,
    ):
        first = client.post(
            "/api/desk/study/materials/read", json=request, headers=_headers()
        )
        second = client.post(
            "/api/desk/study/materials/read", json=request, headers=_headers()
        )

    assert first.status_code == 200
    assert first.json()["material"] | {"artifact_id": "ignored"} == {
        "artifact_id": "ignored",
        "title": "Python程序设计",
        "status": "active",
        "deduplicated": False,
    }
    assert second.status_code == 200
    assert second.json()["material"]["artifact_id"] == first.json()["material"]["artifact_id"]
    assert second.json()["material"]["deduplicated"] is True

    materials = client.get(
        "/api/desk/study/artifacts"
        "?space_id=python-course&kind=resource_pack&status=active",
        headers=_headers(),
    )
    assert materials.status_code == 200
    assert materials.json()["count"] == 1
    artifact_id = materials.json()["items"][0]["artifact_id"]
    detail = client.get(
        f"/api/desk/study/artifacts/{artifact_id}?space_id=python-course",
        headers=_headers(),
    )
    source = detail.json()["artifact"]["envelope"]["source_refs"][0]
    assert source["origin"] == "imported"
    assert source["structure_status"] == "reliable"
    assert source["structure_origin"] == "embedded_pdf_outline"
    assert source["pages"] == 342
    assert source["read_id"] == "read-python-book"
    assert detail.json()["artifact"]["envelope"]["payload"]["outline"][0]["title"] == "第1章 计算机和程序"


def test_study_material_reader_resolves_trusted_artifact_and_reads_bounded_pages(study_client, tmp_path):
    client, db_path = study_client
    assert client.post(
        "/api/desk/study/spaces",
        json={"title": "Reader course", "space_id": "reader-course"},
        headers=_headers(),
    ).status_code == 200
    source = tmp_path / "reader.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    imported = json.dumps({
        "ok": True,
        "engine": "pypdf",
        "read_id": "reader-source",
        "total_pages": 42,
        "outline": [{"id": "chapter-1", "title": "第一章", "level": 1, "page": 7}],
    })
    with patch("desk_server.routes.study_routes.pdf_read_precise", return_value=imported):
        response = client.post(
            "/api/desk/study/materials/read",
            json={"spaceId": "reader-course", "path": str(source), "requestedMode": "auto"},
            headers=_headers(),
        )
    artifact_id = response.json()["material"]["artifact_id"]

    page_result = json.dumps({
        "ok": True,
        "engine": "pypdf",
        "total_pages": 42,
        "page_start": 7,
        "page_end": 12,
        "content": "<!-- page:7 -->\n第一章正文",
        "text_quality": "sufficient",
    })
    with patch("desk_server.routes.study_routes.pdf_read_precise", return_value=page_result) as reader:
        opened = client.post(
            f"/api/desk/study/materials/{artifact_id}/reader",
            json={"spaceId": "reader-course", "pageStart": 7, "pageEnd": 12},
            headers=_headers(),
        )

    assert opened.status_code == 200, opened.text
    assert opened.json()["filename"] == "reader.pdf"
    assert opened.json()["pageStart"] == 7
    assert opened.json()["totalPages"] == 42
    assert opened.json()["outline"][0]["title"] == "第一章"
    assert "第一章正文" in opened.json()["content"]
    assert reader.call_args.kwargs["path"] == str(source)
    assert reader.call_args.kwargs["page_start"] == 7
    assert reader.call_args.kwargs["page_end"] == 12

    too_large = client.post(
        f"/api/desk/study/materials/{artifact_id}/reader",
        json={"spaceId": "reader-course", "pageStart": 1, "pageEnd": 20},
        headers=_headers(),
    )
    assert too_large.status_code == 400

    store = LearningStore(db_path=db_path)
    try:
        ctx = LearningExecutionContext(
            store, owner_id=OWNER, space_id="reader-course"
        )
        plan_id = OutputWriter(ctx).write_artifact(
            kind="learning_plan",
            title="Python学习计划",
            source_refs=[
                {
                    "origin": "imported",
                    "artifact_id": artifact_id,
                    "source_label": "reader.pdf",
                }
            ],
            payload={
                "phases": [
                    {
                        "title": "第一阶段",
                        "tasks": [{"title": "阅读第一章", "order": 0}],
                    }
                ]
            },
        )["artifact_id"]
        ctx.set_artifact_status(plan_id, "active")
        activity_id = ctx.record_activity(
            activity_type="plan.started",
            artifact_id=plan_id,
            detail={"source_artifact_id": artifact_id},
        )
    finally:
        store.close()

    deleted = client.delete(
        f"/api/desk/study/materials/{artifact_id}?space_id=reader-course",
        headers=_headers(),
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"artifact_id": artifact_id, "status": "deleted"}

    store = LearningStore(db_path=db_path)
    try:
        ctx = LearningExecutionContext(
            store, owner_id=OWNER, space_id="reader-course"
        )
        tombstone = ctx.get_artifact(artifact_id)
        assert tombstone is not None
        assert tombstone["status"] == "deleted"
        assert tombstone["envelope"]["source_refs"][0]["path"] == str(source)

        retained_plan = ctx.get_artifact(plan_id)
        assert retained_plan is not None
        assert retained_plan["status"] == "active"
        assert retained_plan["envelope"]["source_refs"][0]["artifact_id"] == artifact_id
        assert any(
            row["activity_id"] == activity_id
            for row in ctx.list_activities()
        )
    finally:
        store.close()

    assert source.is_file(), "knowledge-source deletion must not delete the original file"
    active_sources = client.get(
        "/api/desk/study/artifacts?space_id=reader-course&kind=resource_pack&status=active",
        headers=_headers(),
    )
    assert active_sources.status_code == 200
    assert active_sources.json()["items"] == []

    source_audit = client.get(
        f"/api/desk/study/artifacts/{plan_id}/source-audit?space_id=reader-course",
        headers=_headers(),
    )
    assert source_audit.status_code == 200
    assert source_audit.json()["source_refs"][0]["source_status"] == "deleted"


def test_study_material_reread_replaces_pending_structure_with_real_outline(study_client):
    client, _db_path = study_client
    assert client.post(
        "/api/desk/study/spaces",
        json={"title": "Outline upgrade", "space_id": "outline-upgrade"},
        headers=_headers(),
    ).status_code == 200
    request = {
        "spaceId": "outline-upgrade",
        "path": r"D:\books\course.pdf",
        "includeContent": False,
        "pageStart": 1,
        "pageEnd": 12,
    }
    without_outline = json.dumps({
        "ok": True, "engine": "pypdf", "read_id": "read-weak",
        "pages": 12, "total_pages": 100, "outline": [],
    })
    with_outline = json.dumps({
        "ok": True, "engine": "pypdf", "read_id": "read-strong",
        "pages": 12, "total_pages": 100,
        "outline": [{"id": "chapter-1", "title": "Chapter 1", "level": 1, "page": 8}],
    })
    with patch("desk_server.routes.study_routes.pdf_read_precise", return_value=without_outline):
        first = client.post("/api/desk/study/materials/read", json=request, headers=_headers())
    with patch("desk_server.routes.study_routes.pdf_read_precise", return_value=with_outline):
        upgraded = client.post("/api/desk/study/materials/read", json=request, headers=_headers())

    assert first.status_code == 200
    assert upgraded.status_code == 200
    assert upgraded.json()["material"]["artifact_id"] != first.json()["material"]["artifact_id"]
    assert upgraded.json()["material"]["deduplicated"] is False
    active = client.get(
        "/api/desk/study/artifacts?space_id=outline-upgrade&kind=resource_pack&status=active",
        headers=_headers(),
    ).json()["items"]
    assert len(active) == 1
    detail = client.get(
        f"/api/desk/study/artifacts/{active[0]['artifact_id']}?space_id=outline-upgrade",
        headers=_headers(),
    ).json()["artifact"]
    assert detail["envelope"]["source_refs"][0]["structure_status"] == "reliable"
    assert detail["envelope"]["payload"]["outline"][0]["title"] == "Chapter 1"


def test_flashcard_draft_activate_and_review_routes(study_client):
    client, db_path = study_client
    artifact_id = _seed_draft(db_path)

    drafts = client.get(
        "/api/desk/study/drafts?kind=flashcard_deck",
        headers=_headers(),
    )
    assert drafts.status_code == 200
    assert [item["artifact_id"] for item in drafts.json()["items"]] == [artifact_id]
    assert drafts.json()["count"] == 1
    assert all("envelope" not in item for item in drafts.json()["items"])

    activated = client.post(
        f"/api/desk/study/artifacts/{artifact_id}/activate",
        headers=_headers(),
    )
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"
    assert activated.json()["materialized"] == 1

    cards = client.get("/api/desk/study/flashcards?space_id=s1&due_only=true", headers=_headers())
    assert cards.status_code == 200
    assert len(cards.json()["cards"]) == 1
    item_id = cards.json()["cards"][0]["item_id"]

    reviewed = client.post(
        "/api/desk/study/flashcards/review",
        json={"space_id": "s1", "item_id": item_id, "grade": "good"},
        headers=_headers(),
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["grade"] == "good"
    assert reviewed.json()["repetitions"] == 1


def test_course_core_deck_requires_review_before_activation(study_client):
    client, db_path = study_client
    artifact_id = _seed_course_core_draft(db_path)

    blocked = client.post(
        f"/api/desk/study/artifacts/{artifact_id}/activate",
        headers=_headers(),
    )
    assert blocked.status_code == 400
    assert "semantic review" in blocked.json()["detail"]["message"]

    store = LearningStore(db_path=db_path)
    try:
        ctx = LearningExecutionContext(store, owner_id=OWNER, space_id="s1")
        ctx.set_artifact_review(artifact_id, "passed")
    finally:
        store.close()

    activated = client.post(
        f"/api/desk/study/artifacts/{artifact_id}/activate",
        headers=_headers(),
    )
    assert activated.status_code == 200
    assert activated.json()["materialized"] == 1
    learning_map = client.get(
        "/api/desk/study/learning-map?space_id=s1", headers=_headers()
    ).json()
    assert learning_map["knowledgeCores"][0]["id"] == "core-linear-equation"
    location = client.get(
        "/api/desk/study/location?space_id=s1", headers=_headers()
    ).json()
    assert location["page"] == "learn"
    assert location["knowledgeCoreId"] == "core-linear-equation"


def test_reject_route_keeps_draft_out_of_practice(study_client):
    client, db_path = study_client
    artifact_id = _seed_draft(db_path)

    rejected = client.post(
        f"/api/desk/study/artifacts/{artifact_id}/reject",
        headers=_headers(),
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    space_id = client.get("/api/desk/study/spaces", headers=_headers()).json()["currentSpaceId"]
    cards = client.get(f"/api/desk/study/flashcards?space_id={space_id}", headers=_headers())
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

    space_id = client.get("/api/desk/study/spaces", headers=_headers()).json()["currentSpaceId"]
    cards = client.get(f"/api/desk/study/flashcards?space_id={space_id}", headers=_headers())
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

    quizzes = client.get("/api/desk/study/quizzes?space_id=s1", headers=_headers())
    assert quizzes.status_code == 200
    assert [item["artifact_id"] for item in quizzes.json()["quizzes"]] == [artifact_id]

    questions = client.get(
        f"/api/desk/study/quizzes/{artifact_id}/questions?space_id=s1",
        headers=_headers(),
    )
    assert questions.status_code == 200
    rows = questions.json()["questions"]
    assert [row["prompt"] for row in rows] == ["2+2?", "Optimizer abbreviated GD?"]
    assert all("answer" not in row for row in rows)
    assert rows[0]["knowledge_core_id"] == "core-arithmetic"
    assert rows[0]["origin"] == "source"
    assert rows[0]["source_refs"] == [
        {"material_id": "book-1", "title": "Algebra", "locator": "p. 12"}
    ]

    submitted = client.post(
        f"/api/desk/study/quizzes/{artifact_id}/submit",
        json={
            "space_id": "s1",
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
    public_attempt = submitted.json()["perQuestion"]
    assert all("answer" not in row and "accepted" not in row and "response" not in row for row in public_attempt)


def test_quiz_submit_can_grade_one_step_without_marking_future_questions_wrong(study_client):
    client, db_path = study_client
    artifact_id = _seed_quiz_draft(db_path)
    client.post(f"/api/desk/study/artifacts/{artifact_id}/activate", headers=_headers())
    rows = client.get(
        f"/api/desk/study/quizzes/{artifact_id}/questions?space_id=s1",
        headers=_headers(),
    ).json()["questions"]

    submitted = client.post(
        f"/api/desk/study/quizzes/{artifact_id}/submit",
        json={
            "space_id": "s1",
            "responses": {rows[0]["item_id"]: {"selected": [1]}},
            "item_ids": [rows[0]["item_id"]],
        },
        headers=_headers(),
    )

    assert submitted.status_code == 200
    assert submitted.json()["total"] == 1
    assert submitted.json()["correctCount"] == 1
    assert [item["item_id"] for item in submitted.json()["perQuestion"]] == [
        rows[0]["item_id"]
    ]


def test_quiz_submit_rejects_duplicate_step_ids_without_recording_activity(study_client):
    client, db_path = study_client
    artifact_id = _seed_quiz_draft(db_path)
    client.post(f"/api/desk/study/artifacts/{artifact_id}/activate", headers=_headers())
    question = client.get(
        f"/api/desk/study/quizzes/{artifact_id}/questions?space_id=s1",
        headers=_headers(),
    ).json()["questions"][0]

    submitted = client.post(
        f"/api/desk/study/quizzes/{artifact_id}/submit",
        json={
            "space_id": "s1",
            "responses": {question["item_id"]: {"selected": [1]}},
            "item_ids": [question["item_id"], question["item_id"]],
        },
        headers=_headers(),
    )

    assert submitted.status_code == 400
    assert submitted.json()["detail"]["code"] == "study_invalid_request"
    activities = client.get(
        "/api/desk/study/activities?space_id=s1",
        headers=_headers(),
    )
    assert activities.status_code == 200
    assert activities.json()["count"] == 0


def test_practice_source_resolves_wrongbook_attempt_without_content(study_client):
    client, db_path = study_client
    artifact_id = _seed_quiz_draft(db_path)
    client.post(f"/api/desk/study/artifacts/{artifact_id}/activate", headers=_headers())
    question = client.get(
        f"/api/desk/study/quizzes/{artifact_id}/questions?space_id=s1",
        headers=_headers(),
    ).json()["questions"][0]

    submitted = client.post(
        f"/api/desk/study/quizzes/{artifact_id}/submit",
        json={"space_id": "s1", "responses": {question["item_id"]: {"selected": [0]}}},
        headers=_headers(),
    )
    activity_id = submitted.json()["activity_id"]
    source = client.get(
        f"/api/desk/study/practice-source?space_id=s1&activity_id={activity_id}",
        headers=_headers(),
    )
    assert source.json() == {
        "source": {
            "artifact_id": artifact_id,
            "item_ids": [question["item_id"], f"{artifact_id}-0001"],
        }
    }
    assert "2+2" not in str(source.json())

    missing = client.get(
        "/api/desk/study/practice-source?space_id=s1&activity_id=missing",
        headers=_headers(),
    )
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "study_not_found"


def test_m5_artifact_requires_semantic_approval_before_activation(study_client):
    client, db_path = study_client
    store = LearningStore(db_path=db_path)
    try:
        ctx = LearningExecutionContext(store, owner_id=OWNER)
        ctx.create_space(title="Algebra", space_id="s1")
        artifact_id = OutputWriter(ctx).write_artifact(
            kind="knowledge_base",
            title="Concepts",
            payload={"concepts": [{"term": "limit", "explanation": "approach"}]},
        )["artifact_id"]
    finally:
        store.close()

    blocked = client.post(
        f"/api/desk/study/artifacts/{artifact_id}/activate", headers=_headers()
    )
    assert blocked.status_code == 400
    assert blocked.json()["detail"]["code"] == "study_invalid_request"
    assert "semantic review" in blocked.json()["detail"]["message"]

    with patch("study_semantic_reviewer.review_artifact_with_model", return_value=True):
        reviewed = client.post(
            f"/api/desk/study/artifacts/{artifact_id}/semantic-review",
            json={"space_id": "s1"},
            headers=_headers(),
        )
    assert reviewed.json()["status"] == "passed"
    activated = client.post(
        f"/api/desk/study/artifacts/{artifact_id}/activate", headers=_headers()
    )
    assert activated.json()["status"] == "active"

    audit = client.get(
        f"/api/desk/study/artifacts/{artifact_id}/source-audit?space_id=s1", headers=_headers()
    )
    assert audit.json() == {"artifact_id": artifact_id, "source_refs": []}


def test_material_alignment_uses_semantic_review_and_trusted_activation(study_client):
    client, db_path = study_client
    store = LearningStore(db_path=db_path)
    try:
        ctx = LearningExecutionContext(store, owner_id=OWNER)
        ctx.create_space(title="Calculus", space_id="s1")
        artifact_id = OutputWriter(ctx).write_artifact(
            kind="material_alignment",
            title="Material alignment",
            payload=_material_alignment_payload(),
        )["artifact_id"]
    finally:
        store.close()

    blocked = client.post(
        f"/api/desk/study/artifacts/{artifact_id}/activate", headers=_headers()
    )
    assert blocked.status_code == 400
    assert "semantic review" in blocked.json()["detail"]["message"]

    with patch("study_semantic_reviewer.review_artifact_with_model", return_value=True):
        reviewed = client.post(
            f"/api/desk/study/artifacts/{artifact_id}/semantic-review",
            json={"space_id": "s1"},
            headers=_headers(),
        )
    assert reviewed.json()["status"] == "passed"
    activated = client.post(
        f"/api/desk/study/artifacts/{artifact_id}/activate", headers=_headers()
    )
    assert activated.status_code == 200
    assert activated.json() == {"artifact_id": artifact_id, "status": "active"}


def test_m5_audit_and_review_are_scoped_to_url_space(study_client):
    client, db_path = study_client
    store = LearningStore(db_path=db_path)
    try:
        ctx = LearningExecutionContext(store, owner_id=OWNER)
        ctx.create_space(title="Algebra", space_id="s1")
        artifact_id = OutputWriter(ctx).write_artifact(
            kind="knowledge_base",
            title="Concepts",
            payload={"concepts": [{"term": "limit", "explanation": "approach"}]},
        )["artifact_id"]
        ctx.create_space(title="Other", space_id="s2")
    finally:
        store.close()

    wrong_audit = client.get(
        f"/api/desk/study/artifacts/{artifact_id}/source-audit?space_id=s2", headers=_headers(),
    )
    assert wrong_audit.status_code == 404
    assert wrong_audit.json()["detail"]["code"] == "study_not_found"
    with patch("study_semantic_reviewer.review_artifact_with_model", return_value=True):
        wrong_review = client.post(
            f"/api/desk/study/artifacts/{artifact_id}/semantic-review",
            json={"space_id": "s2"},
            headers=_headers(),
        )
    assert wrong_review.status_code == 404
    assert wrong_review.json()["detail"]["code"] == "study_not_found"


def test_knowledge_points_projection_uses_trusted_source_ref(study_client):
    client, db_path = study_client
    store = LearningStore(db_path=db_path)
    try:
        ctx = LearningExecutionContext(store, owner_id=OWNER)
        ctx.create_space(title="Algebra", space_id="s1")
        FlashcardService(ctx).capture_card(
            front="Limits",
            back="Approach without reaching.",
            tags=["not-a-provenance-contract"],
            source_refs=[{"origin": "kq-kp", "confidence": "confirmed", "session_id": "private"}],
        )
        FlashcardService(ctx).capture_card(
            front="Other",
            back="Do not return this.",
            tags=["知识点"],
            source_refs=[{"origin": "manual"}],
        )
    finally:
        store.close()

    response = client.get(
        "/api/desk/study/knowledge-points?space_id=s1", headers=_headers(),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == payload["returned"] == 1
    assert payload["limit"] == 50 and payload["truncated"] is False
    assert payload["items"][0] | {"item_id": "", "artifact_id": ""} == {
        "item_id": "",
        "artifact_id": "",
        "front": "Limits",
        "gist": "Approach without reaching.",
        "captured": True,
        "confidence": "confirmed",
    }
    assert payload["items"][0]["item_id"] and payload["items"][0]["artifact_id"]
    assert "private" not in str(payload)


def test_learning_map_and_shared_location_routes_use_revision_cas(study_client):
    client, db_path = study_client
    store = LearningStore(db_path=db_path)
    try:
        ctx = LearningExecutionContext(store, owner_id=OWNER)
        ctx.create_space(title="Calculus", space_id="map-course")
        resource = ctx.put_artifact(
            kind="resource_pack",
            title="Calculus",
            payload={
                "resources": [{"title": "Book", "purpose": "Primary"}],
                "outline": [
                    {"id": "limits", "title": "Limits", "locator": "§1"}
                ],
            },
            source_refs=[
                {
                    "origin": "imported",
                    "structure_status": "reliable",
                    "structure_origin": "embedded_pdf_outline",
                    "source_label": "Book",
                }
            ],
            review={"mode": "semantic", "status": "passed"},
        )
        ctx.set_artifact_status(resource["artifact_id"], "active")
        FlashcardService(ctx).capture_card(
            front="Limit uniqueness",
            back="A limit is unique.",
            source_refs=[
                {
                    "origin": "kq-kp",
                    "knowledge_core_id": "core-limit",
                    "outline_node_id": "limits",
                }
            ],
        )
        quiz_id = OutputWriter(ctx).write_artifact(
            kind="quiz",
            title="Limit exercise",
            payload={
                "questions": [
                    {
                        "type": "short_answer",
                        "prompt": "State uniqueness.",
                        "answer": "A limit is unique.",
                        "knowledge_core_id": "core-limit",
                        "origin": "source",
                        "source_refs": [{"material_id": "book", "locator": "§1"}],
                    }
                ]
            },
        )["artifact_id"]
        QuizService(ctx).activate_quiz(quiz_id)
        exercise_id = QuizService(ctx).list_questions(artifact_id=quiz_id)[0]["item_id"]
    finally:
        store.close()

    learning_map = client.get(
        "/api/desk/study/learning-map?space_id=map-course", headers=_headers()
    )
    assert learning_map.status_code == 200
    assert learning_map.json()["revision"] == 1
    assert learning_map.json()["knowledgeCores"][0]["id"] == "core-limit"
    assert learning_map.json()["exerciseLinks"][0]["exerciseId"] == exercise_id

    empty = client.get(
        "/api/desk/study/location?space_id=map-course", headers=_headers()
    )
    assert empty.status_code == 200 and empty.json() is None
    saved = client.put(
        "/api/desk/study/location",
        json={
            "spaceId": "map-course",
            "expectedRevision": 0,
            "expectedMapRevision": 1,
            "page": "practice",
            "knowledgeCoreId": "core-limit",
            "exerciseId": exercise_id,
        },
        headers=_headers(),
    )
    assert saved.status_code == 200
    assert saved.json()["revision"] == 1
    assert saved.json()["exerciseByCore"] == {
        "core-limit": exercise_id
    }

    conflict = client.put(
        "/api/desk/study/location",
        json={
            "spaceId": "map-course",
            "expectedRevision": 0,
            "page": "learn",
            "knowledgeCoreId": "core-limit",
        },
        headers=_headers(),
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "study_conflict"


def test_plan_items_route_repairs_legacy_binding_and_enqueues_once(study_client):
    client, db_path = study_client
    store = LearningStore(db_path=db_path)
    try:
        ctx = LearningExecutionContext(store, owner_id=OWNER)
        ctx.create_space(title="Algebra", space_id="s1")
        resource = ctx.put_artifact(
            kind="resource_pack",
            title="Algebra material",
            payload={
                "resources": [{"title": "Algebra.pdf", "purpose": "Primary"}],
                "outline": [
                    {
                        "id": "section-equations",
                        "title": "Linear equations",
                        "locator": "p. 12",
                    }
                ],
            },
            source_refs=[
                {
                    "origin": "imported",
                    "structure_status": "reliable",
                    "structure_origin": "embedded_pdf_outline",
                    "source_label": "Algebra.pdf",
                }
            ],
            review={"mode": "semantic", "status": "passed"},
        )
        ctx.set_artifact_status(resource["artifact_id"], "active")
        artifact_id = OutputWriter(ctx).write_artifact(
            kind="learning_plan",
            title="Legacy Web plan",
            payload={
                "phases": [
                    {
                        "title": "Foundations",
                        "tasks": [
                            {
                                "title": "Read equations",
                                "mode": "learn",
                                "outlineNodeId": "section-equations",
                            }
                        ],
                    }
                ]
            },
        )["artifact_id"]
        service = LearningPlanService(ctx)
        service.activate_plan(artifact_id)
        row = ctx.list_items(
            item_type=LEARNING_PLAN_ITEM_TYPE, artifact_id=artifact_id
        )[0]
        state = dict(row["state"])
        state["outlineNodeId"] = ""
        ctx.update_item_state(row["item_id"], state)
    finally:
        store.close()

    runner = MagicMock()
    runner.enqueue.return_value = {
        "run_id": "run-repaired",
        "outline_node_id": "section-equations",
        "status": "queued",
    }
    with patch(
        "desk_server.knowledge_core_compile_runner.get_knowledge_core_compile_runner",
        return_value=runner,
    ):
        repaired = client.get(
            f"/api/desk/study/learning-plans/{artifact_id}/items?space_id=s1",
            headers=_headers(),
        )
        unchanged = client.get(
            f"/api/desk/study/learning-plans/{artifact_id}/items?space_id=s1",
            headers=_headers(),
        )

    assert repaired.status_code == 200
    assert repaired.json()["items"][0]["outlineNodeId"] == "section-equations"
    assert repaired.json()["compilationRuns"] == [
        {
            "runId": "run-repaired",
            "outlineNodeId": "section-equations",
            "status": "queued",
        }
    ]
    assert unchanged.status_code == 200
    assert "compilationRuns" not in unchanged.json()
    runner.enqueue.assert_called_once()


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

    space_id = client.get("/api/desk/study/spaces", headers=_headers()).json()["currentSpaceId"]
    quizzes = client.get(f"/api/desk/study/quizzes?space_id={space_id}", headers=_headers())
    assert [item["title"] for item in quizzes.json()["quizzes"]] == ["Legacy quiz"]
