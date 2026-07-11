"""Tests for deterministic B-3 transcription and variant draft generation."""

from __future__ import annotations

import pytest

from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningStore
from learning.output_writer import OutputWriter
from learning.practice_generator import MODEL_DRAFT_REQUIRED, PracticeGenerator
from learning.quizzes import QuizService


@pytest.fixture()
def ctx(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    context = LearningExecutionContext(store, owner_id="owner-A")
    context.create_space(title="Python", space_id="s1")
    try:
        yield context
    finally:
        store.close()


def _active_code_quiz(ctx, *, reference="def add(a, b):\n    return a + b"):
    question = {
        "type": "code",
        "prompt": "Implement add",
        "language": "python",
        "mode": "solve",
        "starter": "def add(a, b):\n    pass",
        "test_code": "assert add(2, 3) == 5",
        "tags": ["functions"],
        "points": 2,
    }
    if reference is not None:
        question["reference"] = reference
    artifact_id = OutputWriter(ctx).write_artifact(
        kind="quiz",
        title="Add",
        payload={"questions": [question]},
    )["artifact_id"]
    QuizService(ctx).activate_quiz(artifact_id)
    question = QuizService(ctx).list_questions(artifact_id=artifact_id)[0]
    return artifact_id, question["item_id"]


def test_code_transcription_draft_keeps_source_lineage_and_is_graded(ctx):
    source_id, item_id = _active_code_quiz(ctx)

    generated = PracticeGenerator(ctx).generate(
        artifact_id=source_id, item_id=item_id, practice_kind="transcribe"
    )

    assert generated["generated"] is True
    assert generated["status"] == "draft"
    draft = ctx.get_artifact(generated["artifact_id"])
    question = draft["envelope"]["payload"]["questions"][0]
    assert question["mode"] == "transcribe"
    assert question["variant_of"] == item_id
    assert question["target_code"] == "def add(a, b):\n    return a + b"

    QuizService(ctx).activate_quiz(generated["artifact_id"])
    generated_item = QuizService(ctx).list_questions(artifact_id=generated["artifact_id"])[0]
    result = QuizService(ctx).submit_attempt(
        generated["artifact_id"],
        {generated_item["item_id"]: {"code": "def add(a, b):\n    return a + b\n\n"}},
    )
    assert result["score"] == 2


def test_python_variant_alpha_renames_and_self_checks_before_draft_write(ctx):
    source_id, item_id = _active_code_quiz(ctx)

    generated = PracticeGenerator(ctx).generate(
        artifact_id=source_id, item_id=item_id, practice_kind="variant"
    )

    assert generated["generated"] is True
    assert generated["self_checked"] is True
    question = ctx.get_artifact(generated["artifact_id"])["envelope"]["payload"]["questions"][0]
    assert question["mode"] == "variant"
    assert question["variant_of"] == item_id
    assert "def add_variant(" in question["reference"]
    assert "add_variant(2, 3)" in question["test_code"]

    QuizService(ctx).activate_quiz(generated["artifact_id"])
    generated_item = QuizService(ctx).list_questions(artifact_id=generated["artifact_id"])[0]
    result = QuizService(ctx).submit_attempt(
        generated["artifact_id"],
        {generated_item["item_id"]: {"code": "def add_variant(a, b):\n    return a + b"}},
    )
    assert result["score"] == 2


def test_template_gap_returns_model_fallback_without_creating_draft(ctx):
    source_id, item_id = _active_code_quiz(ctx, reference=None)
    before = ctx.list_artifacts(kind="quiz")

    generated = PracticeGenerator(ctx).generate(
        artifact_id=source_id, item_id=item_id, practice_kind="variant"
    )

    assert generated == {
        "generated": False,
        "fallback": MODEL_DRAFT_REQUIRED,
        "reason": "no_safe_template",
        "source_item_id": item_id,
    }
    assert ctx.list_artifacts(kind="quiz") == before


def test_draft_source_cannot_generate_practice(ctx):
    artifact_id = OutputWriter(ctx).write_artifact(
        kind="quiz",
        title="Draft",
        payload={
            "questions": [
                {
                    "type": "code",
                    "prompt": "Implement add",
                    "language": "python",
                    "mode": "solve",
                    "test_code": "assert True",
                }
            ]
        },
    )["artifact_id"]

    with pytest.raises(ValueError, match="not active"):
        PracticeGenerator(ctx).generate(
            artifact_id=artifact_id,
            item_id=f"{artifact_id}-0000",
            practice_kind="transcribe",
        )


def test_derivation_transcription_turns_every_step_into_a_reason_cloze(ctx):
    artifact_id = OutputWriter(ctx).write_artifact(
        kind="quiz",
        title="Simplify",
        payload={
            "questions": [
                {
                    "type": "derivation",
                    "prompt": "Simplify x + x",
                    "steps": [
                        {
                            "expr": "x + x",
                            "justification": "start",
                        },
                        {
                            "expr": "2 * x",
                            "justification": "combine like terms",
                        },
                    ],
                    "check": "normalized-match",
                    "cloze": [1],
                    "points": 3,
                }
            ]
        },
    )["artifact_id"]
    QuizService(ctx).activate_quiz(artifact_id)
    item_id = QuizService(ctx).list_questions(artifact_id=artifact_id)[0]["item_id"]

    generated = PracticeGenerator(ctx).generate(
        artifact_id=artifact_id, item_id=item_id, practice_kind="transcribe"
    )

    question = ctx.get_artifact(generated["artifact_id"])["envelope"]["payload"]["questions"][0]
    assert question["cloze"] == [0, 1]
    assert question["steps"][1]["accepted"] == ["combine like terms"]
    QuizService(ctx).activate_quiz(generated["artifact_id"])
    public = QuizService(ctx).list_questions(artifact_id=generated["artifact_id"])[0]
    assert [step["expr"] for step in public["steps"]] == ["", ""]
    assert public["target_steps"] == [
        {"expr": "x + x", "justification": "start"},
        {"expr": "2 * x", "justification": "combine like terms"},
    ]


def test_identifier_renaming_does_not_change_strings_comments_or_docstrings(ctx):
    source_id, item_id = _active_code_quiz(
        ctx,
        reference='def add(a, b):\n    "add docs"\n    # add comment\n    return "add" if False else a + b',
    )

    generated = PracticeGenerator(ctx).generate(
        artifact_id=source_id, item_id=item_id, practice_kind="variant"
    )

    question = ctx.get_artifact(generated["artifact_id"])["envelope"]["payload"]["questions"][0]
    assert "def add_variant(" in question["reference"]
    assert '"add docs"' in question["reference"]
    assert "# add comment" in question["reference"]
    assert 'return "add"' in question["reference"]
