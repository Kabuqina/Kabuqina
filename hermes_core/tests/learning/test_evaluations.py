from __future__ import annotations

import pytest

from learning.evaluations import EvaluationService
from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningStore
from learning.output_writer import OutputWriter


@pytest.fixture()
def ctx(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    context = LearningExecutionContext(store, owner_id="owner-A")
    context.create_space(title="Algebra", space_id="s1")
    try:
        yield context
    finally:
        store.close()


def _draft(ctx):
    return OutputWriter(ctx).write_artifact(
        kind="evaluation",
        title="Weekly evaluation",
        payload={
            "observations": ["Missed prime questions."],
            "weak_points": ["prime numbers"],
            "suggestions": ["Add mixed drills"],
            "evidence_refs": [
                {"activity_id": "a1", "activity_type": "quiz.attempt"}
            ],
        },
    )["artifact_id"]


def test_activate_and_reject_evaluations_synchronize_review(ctx):
    service = EvaluationService(ctx)
    active_id = _draft(ctx)
    rejected_id = _draft(ctx)

    assert service.activate_evaluation(active_id)["status"] == "active"
    assert service.reject_evaluation(rejected_id)["status"] == "rejected"
    assert ctx.get_artifact(active_id)["review"]["status"] == "passed"
    assert ctx.get_artifact(rejected_id)["review"]["status"] == "failed"
    assert [
        row["artifact_id"] for row in service.list_evaluations(status="active")
    ] == [active_id]


def test_projection_is_bounded_and_contains_only_safe_fields(ctx):
    service = EvaluationService(ctx)
    artifact_id = _draft(ctx)
    service.activate_evaluation(artifact_id)

    assert service.active_evaluation_projections() == [
        {
            "artifact_id": artifact_id,
            "title": "Weekly evaluation",
            "observations": ["Missed prime questions."],
            "weak_points": ["prime numbers"],
            "suggestions": ["Add mixed drills"],
            "evidence_refs": [
                {"activity_id": "a1", "activity_type": "quiz.attempt"}
            ],
        }
    ]


def test_evaluation_is_owner_scoped(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    try:
        owner_a = LearningExecutionContext(store, owner_id="owner-A")
        owner_a.create_space(title="Algebra", space_id="s1")
        artifact_id = _draft(owner_a)

        owner_b = LearningExecutionContext(store, owner_id="owner-B", space_id="s1")
        with pytest.raises(KeyError):
            EvaluationService(owner_b).activate_evaluation(artifact_id)
    finally:
        store.close()
