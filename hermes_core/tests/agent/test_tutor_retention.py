# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

import pytest

from agent.graph_engine.tutor_branch_policy import (
    DeterministicEvaluationResultV1,
    PinnedTutorSourceRefV1,
    TutorBranchResolutionV1,
)
from agent.graph_engine.tutor_retention import (
    MAX_REMEDIATION_EXCERPT_BYTES,
    TutorRemediationContextV1,
    build_remediation_context,
    learner_answer_excerpt,
    retain_evaluation_evidence,
)
from learning.tutor_contract import TutorContractError


def _source():
    return PinnedTutorSourceRefV1(
        source_kind="activated_quiz_item",
        source_id="item-1",
        source_version=1,
        source_sha256="a" * 64,
    )


def _evaluation(outcome="incorrect", revision=4):
    return DeterministicEvaluationResultV1(
        evaluation_id=f"evaluation-{revision}",
        activity_id="activity-1",
        activity_kind="tutor",
        check_id="check-1",
        checkpoint_revision=revision,
        mode="deterministic",
        outcome=outcome,
        grader_id="practice.choice_exact",
        grader_version="practice-grader-v1",
        rubric_ref=_source(),
        answer_fingerprint="b" * 64,
        evidence_codes=(
            ("deterministic_incorrect", "rubric_verified")
            if outcome == "incorrect"
            else ("deterministic_correct", "rubric_verified")
        ),
        evaluated_at="2026-07-26T12:00:00Z",
    )


def _resolution(action="remediate", revision=4):
    return TutorBranchResolutionV1(
        branch_action=action,
        control_action=None,
        reason_code=(
            "deterministic_incorrect"
            if action == "remediate"
            else "deterministic_correct"
        ),
        completion_basis="deterministic_correct" if action == "complete" else None,
        next_unit_ref=None,
        input_fingerprint=(f"{revision:064x}"[-64:]),
    )


def test_current_remediation_keeps_bounded_excerpt_and_fingerprint():
    context = build_remediation_context(
        _evaluation(),
        _resolution(),
        {"type": "free_text", "text": "错" * 2_000},
    )

    assert context.answer_fingerprint == "b" * 64
    assert context.branch_reason == "deterministic_incorrect"
    assert len(context.learner_excerpt.encode("utf-8")) <= MAX_REMEDIATION_EXCERPT_BYTES
    assert TutorRemediationContextV1.from_mapping(context.to_dict()) == context


def test_choice_excerpt_is_canonical_and_contains_no_rubric_truth():
    excerpt = learner_answer_excerpt({"type": "choice", "selected": ["2", "0"]})

    assert excerpt == '{"selected":["2","0"],"type":"choice"}'
    assert "answer" not in excerpt
    assert "rubric" not in excerpt


def test_only_incorrect_remediate_may_retain_raw_excerpt():
    with pytest.raises(TutorContractError):
        build_remediation_context(
            _evaluation(outcome="correct"),
            _resolution(action="complete"),
            {"type": "choice", "selected": ["1"]},
        )


def test_evaluation_history_keeps_only_two_typed_records():
    retained = []
    for revision in (1, 2, 3):
        retained = retain_evaluation_evidence(
            retained,
            _evaluation(revision=revision),
            _resolution(revision=revision),
        )

    assert len(retained) == 2
    assert [item["evaluation"]["checkpoint_revision"] for item in retained] == [2, 3]
    assert all("learner_excerpt" not in item for item in retained)
