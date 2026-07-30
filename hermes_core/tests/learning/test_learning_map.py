"""Contracts for the versioned Course map and shared location truth."""

from __future__ import annotations

import pytest

from learning.flashcards import FlashcardService
from learning.learning_context import LearningExecutionContext
from learning.learning_map import LearningMapService
from learning.learning_store import LearningConflictError, LearningStore
from learning.output_writer import OutputWriter
from learning.quizzes import QuizService


@pytest.fixture()
def ctx(tmp_path):
    store = LearningStore(tmp_path / "learning.db")
    context = LearningExecutionContext(store, "owner-map")
    context.create_space(title="Calculus", space_id="course-1")
    yield context
    store.close()


def _active_resource(ctx, *, outline, inferred=False):
    source_ref = {
        "origin": "imported",
        "structure_status": "confirmed" if inferred else "reliable",
        "structure_origin": "inferred_confirmed" if inferred else "embedded_pdf_outline",
        "source_label": "Calculus.pdf",
    }
    artifact = ctx.put_artifact(
        kind="resource_pack",
        title="Calculus",
        payload={
            "resources": [
                {
                    "title": "Calculus.pdf",
                    "purpose": "Primary material",
                    "credibility": "Learner-owned source",
                }
            ],
            "outline": outline,
        },
        source_refs=[source_ref],
        review={"mode": "semantic", "status": "passed"},
    )
    ctx.set_artifact_status(artifact["artifact_id"], "active")
    return artifact["artifact_id"]


def _seed_vertical_slice(ctx):
    resource_id = _active_resource(
        ctx,
        outline=[
            {
                "id": "chapter-1",
                "title": "Limits",
                "locator": "§1",
                "children": [
                    {
                        "id": "section-1-1",
                        "title": "Limit laws",
                        "locator": "§1.1",
                        "children": [
                            {
                                "id": "section-1-1-a",
                                "title": "Uniqueness",
                                "locator": "p. 18",
                                "children": [
                                    {
                                        "id": "too-deep",
                                        "title": "Reader-only detail",
                                        "locator": "p. 19",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    )
    captured = FlashcardService(ctx).capture_card(
        front="Limit uniqueness",
        back="A limit, when it exists, is unique.",
        source_refs=[
            {
                "origin": "kq-kp",
                "confidence": "confirmed",
                "knowledge_core_id": "core-limit",
                "outline_node_id": "section-1-1-a",
                "order": 4,
            }
        ],
    )
    quiz_id = OutputWriter(ctx).write_artifact(
        kind="quiz",
        title="Limit source exercise",
        payload={
            "questions": [
                {
                    "type": "short_answer",
                    "prompt": "Why can a function not have two limits at one point?",
                    "answer": "Limits are unique.",
                    "knowledge_core_id": "core-limit",
                    "origin": "source",
                    "source_refs": [
                        {
                            "material_id": "calculus",
                            "title": "Calculus.pdf",
                            "locator": "p. 18",
                        }
                    ],
                },
                {
                    "type": "short_answer",
                    "prompt": "An unrelated legacy question",
                    "answer": "No relation",
                },
            ]
        },
    )["artifact_id"]
    QuizService(ctx).activate_quiz(quiz_id)
    question_id = QuizService(ctx).list_questions(artifact_id=quiz_id)[0]["item_id"]
    return resource_id, captured["artifact_id"], quiz_id, question_id


def test_map_uses_confirmed_outline_and_only_explicit_exercise_links(ctx):
    _resource, _card, quiz_id, question_id = _seed_vertical_slice(ctx)

    learning_map = LearningMapService(ctx).get_map()

    assert learning_map["revision"] == 1
    assert learning_map["outlineStatus"] == "ready"
    assert [node["id"] for node in learning_map["outlineNodes"]] == [
        "chapter-1",
        "section-1-1",
        "section-1-1-a",
    ]
    assert max(node["depth"] for node in learning_map["outlineNodes"]) == 3
    assert all(node["locator"] for node in learning_map["outlineNodes"])
    assert learning_map["knowledgeCores"] == [
        {
            "id": "core-limit",
            "itemId": learning_map["knowledgeCores"][0]["itemId"],
            "artifactId": learning_map["knowledgeCores"][0]["artifactId"],
            "front": "Limit uniqueness",
            "gist": "A limit, when it exists, is unique.",
            "captured": True,
            "outlineNodeId": "section-1-1-a",
            "order": 0,
        }
    ]
    assert learning_map["exerciseLinks"] == [
        {
            "knowledgeCoreId": "core-limit",
            "quizArtifactId": quiz_id,
            "exerciseId": question_id,
            "origin": "source",
            "sourceRefs": [
                {
                    "material_id": "calculus",
                    "title": "Calculus.pdf",
                    "locator": "p. 18",
                }
            ],
            "order": 0,
        }
    ]


def test_missing_and_unconfirmed_inferred_outlines_do_not_become_the_map(ctx):
    draft = ctx.put_artifact(
        kind="resource_pack",
        title="Unconfirmed proposal",
        payload={
            "resources": [{"title": "Book", "purpose": "Source"}],
            "outline": [
                {"id": "proposed", "title": "Proposed chapter", "locator": "pp. 1-20"}
            ],
        },
        source_refs=[
            {
                "structure_status": "proposed",
                "structure_origin": "inferred_confirmed",
                "source_label": "Book",
            }
        ],
    )
    service = LearningMapService(ctx)
    assert service.get_map()["outlineStatus"] == "missing"
    assert service.get_map()["outlineNodes"] == []

    ctx.set_artifact_review(draft["artifact_id"], "passed")
    ctx.set_artifact_status(draft["artifact_id"], "active")
    assert service.get_map()["outlineStatus"] == "weak"
    assert service.get_map()["outlineNodes"] == []


def test_confirmed_inferred_outline_requires_bounded_node_evidence(ctx):
    _active_resource(
        ctx,
        inferred=True,
        outline=[
            {
                "id": "sampled-limits",
                "title": "Limits",
                "evidence": {
                    "source_ref": "Calculus.pdf",
                    "locator": "pp. 11-28",
                },
            }
        ],
    )
    learning_map = LearningMapService(ctx).get_map()
    assert learning_map["outlineStatus"] == "ready"
    assert learning_map["outlineNodes"][0]["origin"] == "inferred_confirmed"
    assert learning_map["outlineNodes"][0]["locator"] == "pp. 11-28"


def test_location_is_revisioned_exported_and_stales_when_link_disappears(ctx):
    _resource, _card, quiz_id, question_id = _seed_vertical_slice(ctx)
    service = LearningMapService(ctx)
    learning_map = service.get_map()
    location = service.put_location(
        expected_revision=0,
        expected_map_revision=learning_map["revision"],
        page="practice",
        knowledge_core_id="core-limit",
        exercise_id=question_id,
    )
    assert location | {"updatedAt": ""} == {
        "revision": 1,
        "mapRevision": 1,
        "page": "practice",
        "knowledgeCoreId": "core-limit",
        "outlineNodeId": "section-1-1-a",
        "exerciseId": question_id,
        "exerciseByCore": {"core-limit": question_id},
        "stale": False,
        "updatedAt": "",
    }
    with pytest.raises(LearningConflictError, match="stale_revision"):
        service.put_location(
            expected_revision=0,
            page="learn",
            knowledge_core_id="core-limit",
        )

    ctx.set_artifact_status(quiz_id, "archived")
    changed = service.get_map()
    assert changed["revision"] == 2
    stale = service.get_location()
    assert stale["revision"] == 2
    assert stale["mapRevision"] == 2
    assert stale["stale"] is True
    assert stale["staleReason"] == "exercise_removed"

    exported = ctx.export_owner_bundle()
    reserved_types = {
        row["item_type"]
        for row in exported["items"]
        if row["item_id"].startswith("__course_")
    }
    assert reserved_types == {"course_learning_map_meta", "course_location"}
