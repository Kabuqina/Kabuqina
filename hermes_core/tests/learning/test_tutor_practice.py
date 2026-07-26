# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import replace

import pytest

from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningStore
from learning.output_writer import OutputWriter
from learning.practice_contract import build_grader_provenance
from learning.quizzes import QuizService
from learning.tutor_contract import LearningActivityKeyV1, TutorContractError
from learning.tutor_practice import TutorPracticeAdapter


@pytest.fixture()
def practice(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    ctx = LearningExecutionContext(store, owner_id="owner-A")
    ctx.create_space(title="Practice", space_id="space-A")
    artifact_id = OutputWriter(ctx).write_artifact(
        kind="quiz",
        title="Trusted quiz",
        payload={
            "questions": [
                {
                    "type": "choice",
                    "prompt": "Pick the primes.",
                    "options": ["2", "4", "5"],
                    "answer": [0, 2],
                },
                {
                    "type": "short_answer",
                    "prompt": "Name GD.",
                    "answer": "gradient descent",
                    "accepted": ["GD"],
                },
                {
                    "type": "code",
                    "mode": "solve",
                    "language": "python",
                    "prompt": "Implement add.",
                    "test_code": "assert add(1, 2) == 3",
                },
            ]
        },
    )["artifact_id"]
    quiz = QuizService(ctx)
    quiz.activate_quiz(artifact_id)
    items = quiz.list_questions(artifact_id=artifact_id)
    try:
        yield ctx, artifact_id, items
    finally:
        store.close()


def _key() -> LearningActivityKeyV1:
    return LearningActivityKeyV1("owner-A", "space-A", "tutor", "activity-A")


def test_resolve_pins_active_truth_and_exposes_no_answer(practice):
    ctx, artifact_id, items = practice
    resolved = TutorPracticeAdapter(ctx).resolve_check(
        artifact_id=artifact_id,
        item_id=items[0]["item_id"],
    )

    assert resolved.check_spec.evaluation_mode == "deterministic"
    assert resolved.check_spec.normalization_policy == "choice-v1"
    assert resolved.check_spec.correct_action == "complete"
    assert resolved.prompt["options"] == [
        {"id": "0", "label": "2"},
        {"id": "1", "label": "4"},
        {"id": "2", "label": "5"},
    ]
    assert "answer" not in resolved.prompt
    assert "accepted" not in resolved.prompt


def test_evaluate_choice_is_pure_and_returns_only_typed_evidence(practice):
    ctx, artifact_id, items = practice
    adapter = TutorPracticeAdapter(ctx, now=lambda: "2026-07-26T12:00:00Z")
    check = adapter.resolve_check(
        artifact_id=artifact_id,
        item_id=items[0]["item_id"],
    ).check_spec

    result, status = adapter.evaluate(
        key=_key(),
        checkpoint_revision=3,
        check_spec=check,
        answer={"type": "choice", "selected": ["0", "2"]},
    )

    assert status == "verified"
    assert result.outcome == "correct"
    assert result.evidence_codes == ("deterministic_correct", "rubric_verified")
    assert result.grader_id == "practice.choice_exact"
    assert not ({"answer", "score", "passed", "branch"} & set(result.to_dict()))
    assert ctx.list_activities() == []


def test_evaluate_short_answer_incorrect_uses_pinned_provenance(practice):
    ctx, artifact_id, items = practice
    adapter = TutorPracticeAdapter(ctx, now=lambda: "2026-07-26T12:00:00Z")
    check = adapter.resolve_check(
        artifact_id=artifact_id,
        item_id=items[1]["item_id"],
    ).check_spec

    result, status = adapter.evaluate(
        key=_key(),
        checkpoint_revision=4,
        check_spec=check,
        answer={"type": "free_text", "text": "momentum"},
    )

    assert status == "verified"
    assert result.outcome == "incorrect"
    assert result.rubric_ref == check.rubric_ref
    assert result.answer_fingerprint != check.rubric_ref.source_sha256


@pytest.mark.parametrize(
    "answer",
    [
        {"type": "choice", "selected": ["00"]},
        {"type": "choice", "selected": ["7"]},
        {"type": "choice", "selected": ["0", "0"]},
        {"type": "free_text", "text": "2 and 5"},
    ],
)
def test_invalid_answer_shape_never_calls_it_correct(practice, answer):
    ctx, artifact_id, items = practice
    adapter = TutorPracticeAdapter(ctx, now=lambda: "2026-07-26T12:00:00Z")
    check = adapter.resolve_check(
        artifact_id=artifact_id,
        item_id=items[0]["item_id"],
    ).check_spec

    result, status = adapter.evaluate(
        key=_key(),
        checkpoint_revision=3,
        check_spec=check,
        answer=answer,
    )

    assert status == "verified"
    assert result.outcome == "invalid"
    assert result.evidence_codes == ("answer_invalid",)


def test_hash_drift_blocks_truth_before_grading(practice):
    ctx, artifact_id, items = practice
    adapter = TutorPracticeAdapter(ctx, now=lambda: "2026-07-26T12:00:00Z")
    check = adapter.resolve_check(
        artifact_id=artifact_id,
        item_id=items[0]["item_id"],
    ).check_spec
    row = next(row for row in ctx.list_items() if row["item_id"] == items[0]["item_id"])
    state = dict(row["state"])
    state["answer"] = [1]
    ctx.update_item_state(items[0]["item_id"], state)

    result, status = adapter.evaluate(
        key=_key(),
        checkpoint_revision=3,
        check_spec=check,
        answer={"type": "choice", "selected": ["1"]},
    )

    assert status == "hash_mismatch"
    assert result.outcome == "invalid"
    assert "rubric_verified" not in result.evidence_codes


def test_new_valid_provenance_version_is_stale_against_pin(practice):
    ctx, artifact_id, items = practice
    adapter = TutorPracticeAdapter(ctx)
    check = adapter.resolve_check(
        artifact_id=artifact_id,
        item_id=items[0]["item_id"],
    ).check_spec
    row = next(row for row in ctx.list_items() if row["item_id"] == items[0]["item_id"])
    state = dict(row["state"])
    state["artifact_version"] = check.rubric_ref.source_version + 1
    state["grader_provenance"] = build_grader_provenance(
        state,
        artifact_id=artifact_id,
        artifact_version=state["artifact_version"],
        item_id=items[0]["item_id"],
    )
    ctx.update_item_state(items[0]["item_id"], state)

    assert adapter.source_status(check.rubric_ref) == "stale"


def test_missing_item_and_unsupported_non_total_grader_fail_closed(practice):
    ctx, artifact_id, items = practice
    adapter = TutorPracticeAdapter(ctx)

    with pytest.raises(TutorContractError) as missing:
        adapter.resolve_check(artifact_id=artifact_id, item_id="missing")
    assert missing.value.reason_code == "source_missing"

    with pytest.raises(TutorContractError) as unsupported:
        adapter.resolve_check(
            artifact_id=artifact_id,
            item_id=items[2]["item_id"],
        )
    assert unsupported.value.reason_code == "grader_not_supported"


def test_pinned_hash_or_version_cannot_be_claimed_as_verified(practice):
    ctx, artifact_id, items = practice
    adapter = TutorPracticeAdapter(ctx)
    ref = adapter.resolve_check(
        artifact_id=artifact_id,
        item_id=items[0]["item_id"],
    ).check_spec.rubric_ref

    assert adapter.source_status(replace(ref, source_sha256="0" * 64)) == "hash_mismatch"
    assert adapter.source_status(replace(ref, source_version=ref.source_version + 1)) == "stale"
