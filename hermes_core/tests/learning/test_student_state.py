from __future__ import annotations

import pytest

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
        {"course": "Algebra", "goals": ["Pass the midterm"], "preferences": {"study_time": "30 minutes"}}
    )
    second = service.save_state(
        {"course": "Algebra II", "goals": ["Prepare for finals"], "preferences": {"study_time": "45 minutes"}}
    )

    assert first["status"] == "active"
    assert second["status"] == "active"
    assert [row["artifact_id"] for row in ctx.list_artifacts(kind="student_state", status="active")] == [second["artifact_id"]]
    assert [row["artifact_id"] for row in ctx.list_artifacts(kind="student_state", status="archived")] == [first["artifact_id"]]
    assert service.get_current_state()["payload"]["course"] == "Algebra II"


def test_activate_state_uses_existing_draft_and_rejects_fixed_labels(ctx):
    draft_id = OutputWriter(ctx).write_artifact(
        kind="student_state",
        title="AI profile",
        payload={"course": "Geometry", "goals": ["Proof practice"]},
    )["artifact_id"]

    activated = StudentStateService(ctx).activate_state(draft_id)

    assert activated["artifact_id"] == draft_id
    assert activated["status"] == "active"
    with pytest.raises(ValueError, match="fixed learner labels"):
        StudentStateService(ctx).save_state({"course": "Geometry", "capability_labels": ["weak"]})


def test_legacy_context_maps_all_twelve_fields_without_labels():
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
        "preferences": {"profile_summary": "Likes examples", "study_preferences": "20 minutes daily"},
        "constraints": [],
        "progress_notes": ["Finished derivatives", "Derivative worksheet"],
        "current_stage": "Review",
        "next_adjustment": "More mixed practice",
    }
    assert evaluation == {
        "observations": ["Application is inconsistent", "Quiz 1: 60%", "Still asks when to use the chain rule"],
        "weak_points": ["limits", "chain rule"],
        "suggestions": ["More mixed practice"],
        "evidence_refs": [{"origin": "legacy_local_storage", "key": "kabuqina.study.context.v1"}],
    }
    assert not {"capability_labels", "ability_labels", "personality"} & set(state)


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
