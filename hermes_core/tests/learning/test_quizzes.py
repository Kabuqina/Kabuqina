"""Tests for the STUDY M3 quiz service.

M3 turns ``quiz`` artifacts into durable practice state: trusted UI/API
activation materializes questions into learning items, and each submission is
graded deterministically while recording a genuine user activity.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningStore
from learning.output_writer import OutputWriter
from learning.quizzes import QUIZ_ATTEMPT_ACTIVITY, QuizService


T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture()
def ctx(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    context = LearningExecutionContext(store, owner_id="owner-A")
    context.create_space(title="Algebra", space_id="s1")
    try:
        yield context
    finally:
        store.close()


def _quiz_payload():
    return {
        "questions": [
            {
                "type": "choice",
                "prompt": "2 + 2 = ?",
                "options": ["3", "4"],
                "answer": 1,
                "explanation": "Basic addition.",
                "tags": ["arithmetic"],
                "points": 2,
            },
            {
                "type": "choice",
                "prompt": "Pick primes.",
                "options": ["2", "3", "4"],
                "answer": [0, 1],
                "tags": ["prime"],
                "points": 3,
            },
            {
                "type": "true_false",
                "prompt": "Every square is non-negative over real numbers.",
                "answer": True,
                "tags": ["algebra"],
            },
            {
                "type": "short_answer",
                "prompt": "Name the first-order optimizer often abbreviated GD.",
                "answer": "gradient descent",
                "accepted": ["GD"],
                "tags": ["optimization"],
                "points": 4,
            },
        ]
    }


def _draft_quiz(ctx, title="Diagnostic quiz"):
    return OutputWriter(ctx).write_artifact(
        kind="quiz",
        title=title,
        payload=_quiz_payload(),
    )["artifact_id"]


def test_activate_quiz_materializes_questions_as_items(ctx):
    artifact_id = _draft_quiz(ctx)
    service = QuizService(ctx, now=lambda: T0)

    result = service.activate_quiz(artifact_id)

    assert result["artifact_id"] == artifact_id
    assert result["status"] == "active"
    assert result["materialized"] == 4

    questions = service.list_questions()
    assert [question["prompt"] for question in questions] == [
        "2 + 2 = ?",
        "Pick primes.",
        "Every square is non-negative over real numbers.",
        "Name the first-order optimizer often abbreviated GD.",
    ]
    assert all(question["artifact_id"] == artifact_id for question in questions)
    assert all("answer" not in question for question in questions)
    assert all("accepted" not in question for question in questions)


def test_reject_quiz_does_not_materialize_questions(ctx):
    artifact_id = _draft_quiz(ctx)
    service = QuizService(ctx, now=lambda: T0)

    result = service.reject_quiz(artifact_id)

    assert result["status"] == "rejected"
    assert service.list_questions() == []


def test_submit_attempt_scores_deterministically_and_records_activity(ctx):
    artifact_id = _draft_quiz(ctx)
    service = QuizService(ctx, now=lambda: T0)
    service.activate_quiz(artifact_id)
    questions = service.list_questions()
    by_prompt = {question["prompt"]: question["item_id"] for question in questions}

    result = service.submit_attempt(
        artifact_id,
        {
            by_prompt["2 + 2 = ?"]: {"selected": [1]},
            by_prompt["Pick primes."]: {"selected": [0]},
            by_prompt["Every square is non-negative over real numbers."]: {"value": True},
            by_prompt["Name the first-order optimizer often abbreviated GD."]: {
                "text": " gd! "
            },
        },
    )

    assert result["score"] == 7
    assert result["maxScore"] == 10
    assert result["percent"] == 70
    assert result["correctCount"] == 3
    assert result["total"] == 4
    assert result["weakTags"] == ["prime"]
    assert len(result["perQuestion"]) == 4
    assert [item["correct"] for item in result["perQuestion"]] == [
        True,
        False,
        True,
        True,
    ]
    assert result["perQuestion"][1]["answer"] == [0, 1]
    assert result["perQuestion"][3]["answer"] == "gradient descent"

    activities = ctx.list_activities()
    assert len(activities) == 1
    assert activities[0]["activity_type"] == QUIZ_ATTEMPT_ACTIVITY
    assert activities[0]["artifact_id"] == artifact_id
    assert activities[0]["detail"]["score"] == 7
    assert activities[0]["detail"]["weakTags"] == ["prime"]


def test_list_questions_can_include_answers_for_result_views(ctx):
    artifact_id = _draft_quiz(ctx)
    service = QuizService(ctx, now=lambda: T0)
    service.activate_quiz(artifact_id)

    questions = service.list_questions(artifact_id=artifact_id, include_answers=True)

    assert questions[0]["answer"] == 1
    assert questions[3]["accepted"] == ["GD"]
