# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

from dataclasses import replace

import pytest

from agent.graph_engine.tutor_branch_policy import (
    DeterministicEvaluationResultV1,
    PinnedTutorSourceRefV1,
    TutorBranchPolicyInputV1,
    TutorCheckSpecV1,
    apply_tutor_branch_policy,
)
from learning.tutor_contract import TutorContractError


SHA_A = "a" * 64
SHA_B = "b" * 64


def source(
    *,
    source_id: str = "quiz:item-1",
    digest: str = SHA_A,
    source_kind: str = "activated_quiz_item",
):
    return PinnedTutorSourceRefV1(
        source_kind=source_kind,
        source_id=source_id,
        source_version=3,
        source_sha256=digest,
    )


def deterministic_check(*, action: str = "complete") -> TutorCheckSpecV1:
    return TutorCheckSpecV1(
        check_id="check-1",
        expected_input="choice",
        evaluation_mode="deterministic",
        normalization_policy="choice-v1",
        rubric_ref=source(),
        correct_action=action,
        next_unit_ref=(
            source(
                source_id="unit-2",
                digest=SHA_B,
                source_kind="activated_plan_item",
            )
            if action == "advance"
            else None
        ),
    )


def acknowledgement_check() -> TutorCheckSpecV1:
    return TutorCheckSpecV1(
        check_id="check-1",
        expected_input="choice",
        evaluation_mode="acknowledgement",
        normalization_policy="acknowledgement-v1",
        control_policy="continue_or_explain_once",
    )


def evaluation(
    outcome: str,
    *,
    mode: str = "deterministic",
    rubric_ref=None,
) -> DeterministicEvaluationResultV1:
    codes = {
        "submitted": ("answer_submitted",),
        "invalid": ("answer_invalid",),
        "correct": ("deterministic_correct", "rubric_verified"),
        "incorrect": ("deterministic_incorrect", "rubric_verified"),
    }[outcome]
    return DeterministicEvaluationResultV1(
        evaluation_id=f"eval-{outcome}",
        activity_id="activity-1",
        activity_kind="tutor",
        check_id="check-1",
        checkpoint_revision=4,
        mode=mode,
        outcome=outcome,
        grader_id="quiz-service",
        grader_version="practice-grader-v1",
        rubric_ref=rubric_ref,
        answer_fingerprint="c" * 64,
        evidence_codes=codes,
        evaluated_at="2026-07-26T12:00:00Z",
    )


def branch_input(
    outcome: str,
    *,
    remediation_count: int = 0,
    hint_requested: bool = False,
    source_status: str = "verified",
    action: str = "complete",
) -> TutorBranchPolicyInputV1:
    check = deterministic_check(action=action)
    return TutorBranchPolicyInputV1(
        check_spec=check,
        evaluation=evaluation(outcome, rubric_ref=check.rubric_ref),
        remediation_count=remediation_count,
        source_status=source_status,
        hint_requested=hint_requested,
        weak_point_codes=("concept_gap",) if outcome == "incorrect" else (),
    )


def test_check_specs_are_exact_and_mode_conditional():
    ack = acknowledgement_check()
    assert TutorCheckSpecV1.from_mapping(ack.to_dict()) == ack
    assert TutorCheckSpecV1.from_mapping(deterministic_check().to_dict()) == deterministic_check()

    with pytest.raises(TutorContractError):
        replace(ack, rubric_ref=source())
    with pytest.raises(TutorContractError):
        deterministic_check(action="advance").__class__(
            **{**deterministic_check(action="advance").__dict__, "next_unit_ref": None}
        )
    with pytest.raises(TutorContractError):
        TutorCheckSpecV1.from_mapping({**ack.to_dict(), "model_decides": True})


def test_evaluation_schema_has_provenance_but_no_learner_text_or_score():
    result = evaluation("correct", rubric_ref=source())
    payload = result.to_dict()
    assert DeterministicEvaluationResultV1.from_mapping(payload) == result
    assert not ({"answer", "score", "passed", "mastery", "branch"} & set(payload))

    with pytest.raises(TutorContractError):
        DeterministicEvaluationResultV1.from_mapping({**payload, "answer": "secret"})
    with pytest.raises(TutorContractError):
        replace(result, evidence_codes=("answer_submitted",))
    with pytest.raises(TutorContractError):
        replace(result, activity_kind="gateway")


def test_submitted_acknowledgement_completes_participation_only():
    check = acknowledgement_check()
    value = TutorBranchPolicyInputV1(
        check_spec=check,
        evaluation=evaluation("submitted", mode="acknowledgement", rubric_ref=None),
        remediation_count=0,
        source_status="not_applicable",
    )
    decision = apply_tutor_branch_policy(value)
    assert decision.branch_action == "complete"
    assert decision.completion_basis == "participation_only"
    assert decision.reason_code == "acknowledged"


def test_correct_completes_or_advances_only_from_host_action():
    complete = apply_tutor_branch_policy(branch_input("correct"))
    assert complete.branch_action == "complete"
    assert complete.completion_basis == "deterministic_correct"

    advance = apply_tutor_branch_policy(branch_input("correct", action="advance"))
    assert advance.branch_action == "advance"
    assert advance.next_unit_ref == deterministic_check(action="advance").next_unit_ref
    assert advance.completion_basis is None


def test_incorrect_remediates_once_then_blocks():
    first = apply_tutor_branch_policy(branch_input("incorrect", remediation_count=0))
    assert first.branch_action == "remediate"
    assert first.reason_code == "deterministic_incorrect"

    exhausted = apply_tutor_branch_policy(branch_input("incorrect", remediation_count=1))
    assert exhausted.branch_action == "blocked"
    assert exhausted.reason_code == "remediation_exhausted"


def test_explicit_hint_precedes_incorrect_remediation_but_not_correct_action():
    hint = apply_tutor_branch_policy(
        branch_input("incorrect", hint_requested=True, remediation_count=0)
    )
    assert hint.branch_action == "hint"
    assert hint.reason_code == "explicit_hint_requested"

    correct = apply_tutor_branch_policy(branch_input("correct", hint_requested=True))
    assert correct.branch_action == "complete"


def test_invalid_reissues_without_a_branch_action_or_model_authority():
    decision = apply_tutor_branch_policy(branch_input("invalid"))
    assert decision.branch_action is None
    assert decision.control_action == "reissue"
    assert decision.reason_code == "invalid_answer"


@pytest.mark.parametrize("status", ["missing", "stale", "hash_mismatch"])
def test_untrusted_deterministic_source_blocks_before_other_actions(status):
    decision = apply_tutor_branch_policy(
        branch_input("invalid", source_status=status, hint_requested=True)
    )
    assert decision.branch_action == "blocked"
    assert decision.control_action is None
    assert decision.reason_code == "source_missing"


def test_rubric_provenance_and_check_identity_must_match():
    check = deterministic_check()
    with pytest.raises(TutorContractError):
        TutorBranchPolicyInputV1(
            check_spec=check,
            evaluation=evaluation("correct", rubric_ref=source(digest=SHA_B)),
            remediation_count=0,
            source_status="verified",
        )
    with pytest.raises(TutorContractError):
        TutorBranchPolicyInputV1(
            check_spec=check,
            evaluation=replace(
                evaluation("correct", rubric_ref=check.rubric_ref), check_id="other-check"
            ),
            remediation_count=0,
            source_status="verified",
        )


def test_branch_input_rejects_freeform_weak_points_and_is_fingerprint_stable():
    value = branch_input("incorrect")
    assert TutorBranchPolicyInputV1.from_mapping(value.to_dict()) == value
    decision = apply_tutor_branch_policy(value)
    assert decision.input_fingerprint == apply_tutor_branch_policy(value).input_fingerprint
    assert decision.from_mapping(decision.to_dict()) == decision
    with pytest.raises(TutorContractError):
        replace(value, weak_point_codes=("the learner seems weak",))


def test_normalization_and_hint_mode_cannot_drift():
    with pytest.raises(TutorContractError):
        replace(deterministic_check(), expected_input="free_text")
    with pytest.raises(TutorContractError):
        TutorBranchPolicyInputV1(
            check_spec=acknowledgement_check(),
            evaluation=evaluation("submitted", mode="acknowledgement", rubric_ref=None),
            remediation_count=0,
            source_status="not_applicable",
            hint_requested=True,
        )
    with pytest.raises(TutorContractError):
        replace(deterministic_check(), rubric_ref=source(source_kind="activated_plan_item"))
    with pytest.raises(TutorContractError):
        replace(
            deterministic_check(action="advance"),
            next_unit_ref=source(source_kind="activated_quiz_item"),
        )


def test_resolution_serialization_contains_auditable_policy_metadata():
    payload = apply_tutor_branch_policy(branch_input("correct")).to_dict()
    assert payload["policy_version"] == "tutor-branch-v1"
    assert payload["input_fingerprint"]
    assert payload["branch_action"] == "complete"
    assert payload["control_action"] is None
    assert not ({"answer", "learner_text", "model_reasoning"} & set(payload))
