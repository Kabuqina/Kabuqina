from __future__ import annotations

import pytest

from learning.learning_contract import ContractError
from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningStore
from learning.output_writer import OutputWriter
from learning.student_state import StudentStateService


@pytest.fixture()
def ctx(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    context = LearningExecutionContext(store, owner_id="owner-A")
    context.create_space(title="Algebra", space_id="s1")
    try:
        yield context
    finally:
        store.close()


def test_save_state_archives_previous_active_state(ctx):
    service = StudentStateService(ctx)
    first = service.save_state(
        {
            "course": "Algebra",
            "goals": ["Pass the midterm"],
            "preferences": {"study_time": "30 minutes"},
        }
    )
    second = service.save_state(
        {
            "course": "Algebra II",
            "goals": ["Prepare for finals"],
            "preferences": {"study_time": "45 minutes"},
        }
    )

    assert first["status"] == "active"
    assert second["status"] == "active"
    active = ctx.list_artifacts(kind="student_state", status="active")
    archived = ctx.list_artifacts(kind="student_state", status="archived")
    assert [row["artifact_id"] for row in active] == [second["artifact_id"]]
    assert [row["artifact_id"] for row in archived] == [first["artifact_id"]]
    assert active[0]["review"]["status"] == "passed"
    assert archived[0]["review"]["status"] == "passed"
    assert service.get_current_state()["payload"]["course"] == "Algebra II"


def test_activate_state_uses_existing_draft_and_preserves_dimensions(ctx):
    draft_id = OutputWriter(ctx).write_artifact(
        kind="student_state",
        title="AI profile",
        payload={
            "course": "Geometry",
            "goals": ["Proof practice"],
            "dimensions": [
                {
                    "key": "foundation",
                    "label": "Knowledge foundation",
                    "level": 3,
                    "summary": "Understands definitions",
                }
            ],
        },
    )["artifact_id"]

    activated = StudentStateService(ctx).activate_state(draft_id)

    assert activated["artifact_id"] == draft_id
    assert activated["status"] == "active"
    assert activated["payload"]["dimensions"][0]["level"] == 3
    assert ctx.get_artifact(draft_id)["review"]["status"] == "passed"


def test_reject_state_marks_review_failed(ctx):
    draft_id = OutputWriter(ctx).write_artifact(
        kind="student_state",
        title="Unwanted profile",
        payload={"course": "Geometry"},
    )["artifact_id"]

    assert StudentStateService(ctx).reject_state(draft_id) == {
        "artifact_id": draft_id,
        "status": "rejected",
    }
    assert ctx.get_artifact(draft_id)["review"]["status"] == "failed"


def test_failed_activation_does_not_archive_current_state(ctx):
    service = StudentStateService(ctx)
    current = service.save_state({"course": "Algebra"})
    rejected_id = OutputWriter(ctx).write_artifact(
        kind="student_state",
        title="Rejected profile",
        payload={"course": "Geometry"},
    )["artifact_id"]
    service.reject_state(rejected_id)

    with pytest.raises(ContractError):
        service.activate_state(rejected_id)

    assert [
        row["artifact_id"]
        for row in ctx.list_artifacts(kind="student_state", status="active")
    ] == [current["artifact_id"]]


def test_save_state_rejects_fixed_labels(ctx):
    with pytest.raises(ValueError, match="fixed learner labels"):
        StudentStateService(ctx).save_state(
            {"course": "Geometry", "capability_labels": ["weak"]}
        )


def test_legacy_context_maps_all_twelve_fields_without_loss():
    state, evaluation = StudentStateService.legacy_context_to_payloads(
        {
            "course": "Calculus",
            "goal": "Pass",
            "profileSummary": "Likes examples",
            "weakPoints": "limits\nchain rule",
            "preferences": "20 minutes daily",
            "progressNotes": "Finished derivatives",
            "assessmentEvidence": "Quiz 1: 60%",
            "currentStage": "Review",
            "generatedResources": "Derivative worksheet",
            "tutoringNotes": "Still asks when to use the chain rule",
            "evaluationSummary": "Application is inconsistent",
            "nextAdjustment": "More mixed practice",
        }
    )

    assert state == {
        "course": "Calculus",
        "goals": ["Pass"],
        "preferences": {
            "profile_summary": "Likes examples",
            "study_preferences": "20 minutes daily",
        },
        "constraints": [],
        "progress_notes": ["Finished derivatives", "Derivative worksheet"],
        "current_stage": "Review",
        "next_adjustment": "More mixed practice",
    }
    assert evaluation == {
        "observations": [
            "Application is inconsistent",
            "Quiz 1: 60%",
            "Still asks when to use the chain rule",
        ],
        "weak_points": ["limits", "chain rule"],
        "suggestions": ["More mixed practice"],
        "evidence_refs": [
            {
                "origin": "legacy_local_storage",
                "key": "kabuqina.study.context.v1",
            }
        ],
    }
    assert not {
        "weakPoints",
        "assessmentEvidence",
        "evaluationSummary",
        "tutoringNotes",
    } & set(state)


def test_legacy_generated_resources_and_tutoring_notes_keep_order_and_dedupe():
    state, evaluation = StudentStateService.legacy_context_to_payloads(
        {
            "progressNotes": "Chapter 1\nshared",
            "generatedResources": "Shared; Worksheet",
            "tutoringNotes": "Question A; Question B",
        }
    )

    assert state["progress_notes"] == ["Chapter 1", "shared", "Worksheet"]
    assert evaluation["observations"] == ["Question A", "Question B"]


def test_legacy_pure_state_has_no_evaluation_and_tutoring_note_is_preserved():
    state, evaluation = StudentStateService.legacy_context_to_payloads(
        {"course": "Calculus", "goal": "Pass"}
    )
    assert state["course"] == "Calculus"
    assert evaluation is None

    _, tutoring_evaluation = StudentStateService.legacy_context_to_payloads(
        {"tutoringNotes": "Review the chain rule"}
    )
    assert tutoring_evaluation["observations"] == ["Review the chain rule"]


def test_state_is_owner_and_space_scoped(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    try:
        owner_a = LearningExecutionContext(store, owner_id="owner-A")
        owner_a.create_space(title="Algebra", space_id="s1")
        StudentStateService(owner_a).save_state({"course": "Algebra"})

        owner_b = LearningExecutionContext(store, owner_id="owner-B", space_id="s1")
        assert StudentStateService(owner_b).get_current_state() is None
    finally:
        store.close()
