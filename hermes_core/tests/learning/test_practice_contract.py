# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest

from learning.practice_contract import (
    MAX_EXPLANATION_CODEPOINTS,
    MAX_HINT_CODEPOINTS,
    PracticeContractError,
    PracticeExplanationRequestV1,
    PracticeHintRequestV1,
    PracticeSemanticResultV1,
    build_grader_provenance,
    explanation_rubric_hash,
    validate_explanation_rubric,
    validate_grader_provenance,
    validate_hint_ladder,
)


def _rubric():
    return {
        "schema_version": 1,
        "criteria": [
            {
                "criterion_id": "cause",
                "description": "Explain the causal step.",
                "tags": ["reasoning"],
            }
        ],
    }


def _semantic_result(rubric_sha256: str):
    return {
        "schema_version": 1,
        "rubric_sha256": rubric_sha256,
        "criteria": [
            {
                "criterion_id": "cause",
                "status": "gap",
                "note": "The causal step is missing.",
                "tags": ["reasoning"],
            }
        ],
        "observations": ["The definition is stated."],
        "suggestions": ["Connect the definition to the next step."],
        "tags": ["reasoning"],
        "usage_summary": {
            "provider_attempts": 1,
            "input_tokens": 100,
            "output_tokens": 50,
            "wall_ms": 500,
        },
    }


def test_hint_ladder_is_exact_bounded_and_needs_one_level():
    assert validate_hint_ladder(
        {"schema_version": 1, "direction": "Use the definition."}
    ) == {"schema_version": 1, "direction": "Use the definition."}

    for invalid in (
        {"schema_version": 1},
        {"schema_version": 2, "direction": "x"},
        {"schema_version": 1, "direction": "x", "answer": "secret"},
        {"schema_version": 1, "direction": "x" * (MAX_HINT_CODEPOINTS + 1)},
    ):
        with pytest.raises(PracticeContractError):
            validate_hint_ladder(invalid)


def test_explanation_rubric_is_exact_unique_and_hash_stable():
    normalized = validate_explanation_rubric(_rubric())
    assert normalized["criteria"][0]["criterion_id"] == "cause"
    assert explanation_rubric_hash(_rubric()) == explanation_rubric_hash(normalized)

    duplicate = _rubric()
    duplicate["criteria"].append(dict(duplicate["criteria"][0]))
    with pytest.raises(PracticeContractError, match="unique"):
        validate_explanation_rubric(duplicate)

    unknown = _rubric()
    unknown["criteria"][0]["passed"] = True
    with pytest.raises(PracticeContractError):
        validate_explanation_rubric(unknown)


@pytest.mark.parametrize(
    ("question", "grader_kind"),
    [
        ({"type": "choice", "options": ["a", "b"], "answer": 1}, "choice_exact"),
        ({"type": "true_false", "answer": True}, "boolean_exact"),
        ({"type": "short_answer", "answer": "x", "accepted": ["X"]}, "short_answer_exact"),
        (
            {
                "type": "code",
                "language": "python",
                "mode": "solve",
                "starter": "def f(): pass",
                "test_code": "assert f() == 1",
            },
            "code_sandbox",
        ),
        (
            {
                "type": "derivation",
                "mode": "solve",
                "check": "normalized-match",
                "cloze": [0],
                "steps": [{"expr": "x"}],
            },
            "derivation",
        ),
    ],
)
def test_grader_provenance_pins_each_deterministic_truth(question, grader_kind):
    provenance = build_grader_provenance(
        question,
        artifact_id="quiz-1",
        artifact_version=1,
        item_id="quiz-1-0000",
    )
    assert provenance["grader_kind"] == grader_kind
    assert len(provenance["rubric_sha256"]) == 64
    assert validate_grader_provenance(provenance) == provenance


def test_grader_hash_changes_with_hidden_truth_not_hint_content():
    base = {"type": "short_answer", "answer": "alpha", "accepted": []}
    changed = {**base, "answer": "beta"}
    hint_changed = {**base, "hint_ladder": {"schema_version": 1, "direction": "look"}}

    def digest(question):
        return build_grader_provenance(
            question,
            artifact_id="quiz-1",
            artifact_version=1,
            item_id="quiz-1-0000",
        )["rubric_sha256"]

    assert digest(base) != digest(changed)
    assert digest(base) == digest(hint_changed)


def test_hint_request_has_global_idempotency_identity_and_payload_fingerprint():
    request = PracticeHintRequestV1.from_mapping(
        {
            "schema_version": 1,
            "artifact_id": "quiz-1",
            "item_id": "quiz-1-0000",
            "idempotency_key": "request-1",
            "level": "full_solution",
        }
    )
    replay = PracticeHintRequestV1.from_mapping(request.to_dict())
    changed = PracticeHintRequestV1(
        artifact_id=request.artifact_id,
        item_id=request.item_id,
        idempotency_key=request.idempotency_key,
        level="direction",
    )

    assert request.activity_id == replay.activity_id == changed.activity_id
    assert request.request_fingerprint == replay.request_fingerprint
    assert request.request_fingerprint != changed.request_fingerprint
    assert request.activity_id.startswith("phint_")


def test_explanation_request_is_bounded_and_pins_rubric():
    rubric_sha256 = explanation_rubric_hash(_rubric())
    request = PracticeExplanationRequestV1(
        artifact_id="quiz-1",
        item_id="quiz-1-0000",
        idempotency_key="explain-1",
        learner_explanation="Because the definition implies the next step.",
        rubric_sha256=rubric_sha256,
    )
    assert request.to_dict()["rubric_sha256"] == rubric_sha256

    with pytest.raises(PracticeContractError):
        PracticeExplanationRequestV1(
            artifact_id="quiz-1",
            item_id="quiz-1-0000",
            idempotency_key="explain-2",
            learner_explanation="x" * (MAX_EXPLANATION_CODEPOINTS + 1),
            rubric_sha256=rubric_sha256,
        )


def test_semantic_result_has_no_branchable_pass_fail_fields():
    rubric_sha256 = explanation_rubric_hash(_rubric())
    result = PracticeSemanticResultV1.from_mapping(_semantic_result(rubric_sha256))
    assert result.criteria[0]["status"] == "gap"
    assert "passed" not in result.to_dict()

    for forbidden in ("passed", "correct", "score", "mastery", "branch"):
        invalid = _semantic_result(rubric_sha256)
        invalid[forbidden] = True
        with pytest.raises(PracticeContractError):
            PracticeSemanticResultV1.from_mapping(invalid)


def test_semantic_result_rejects_retry_budget_and_unknown_criterion_status():
    rubric_sha256 = explanation_rubric_hash(_rubric())
    retry = _semantic_result(rubric_sha256)
    retry["usage_summary"]["provider_attempts"] = 2
    with pytest.raises(PracticeContractError):
        PracticeSemanticResultV1.from_mapping(retry)

    unknown = _semantic_result(rubric_sha256)
    unknown["criteria"][0]["status"] = "passed"
    with pytest.raises(PracticeContractError):
        PracticeSemanticResultV1.from_mapping(unknown)
