# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Deterministic Tutor learner-evidence retention for L-5.

Only the current remediation may retain a bounded learner excerpt. Historical
records retain typed evaluator provenance, answer fingerprints and branch
reasons, never raw source documents, provider responses or secrets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from agent.graph_engine.tutor_branch_policy import (
    DeterministicEvaluationResultV1,
    TutorBranchResolutionV1,
)
from learning.tutor_contract import TutorContractError, canonical_json_bytes


TUTOR_RETENTION_POLICY_VERSION = "tutor-retention-v1"
MAX_REMEDIATION_EXCERPT_BYTES = 2_048
MAX_RETAINED_EVALUATIONS = 2
MAX_RETAINED_EVIDENCE_BYTES = 20 * 1024


def _utf8_prefix(value: str, maximum: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= maximum:
        return value
    return encoded[:maximum].decode("utf-8", errors="ignore")


def learner_answer_excerpt(answer: Mapping[str, Any]) -> str:
    """Return a canonical, bounded excerpt suitable only for current repair."""
    if not isinstance(answer, Mapping):
        raise TutorContractError("learner answer excerpt requires an object")
    answer_type = answer.get("type")
    if answer_type in {"free_text", "step"} and isinstance(answer.get("text"), str):
        value = answer["text"]
    elif answer_type == "choice" and isinstance(answer.get("selected"), list):
        value = canonical_json_bytes(
            {"type": "choice", "selected": answer["selected"]}
        ).decode("utf-8")
    else:
        raise TutorContractError("learner answer shape cannot be retained")
    return _utf8_prefix(value, MAX_REMEDIATION_EXCERPT_BYTES)


@dataclass(frozen=True)
class TutorRemediationContextV1:
    check_id: str
    answer_fingerprint: str
    outcome: str
    branch_reason: str
    learner_excerpt: str
    schema_version: int = 1
    policy_version: str = TUTOR_RETENTION_POLICY_VERSION

    def __post_init__(self) -> None:
        if (
            self.schema_version != 1
            or self.policy_version != TUTOR_RETENTION_POLICY_VERSION
        ):
            raise TutorContractError("Tutor remediation context version is invalid")
        if (
            self.outcome != "incorrect"
            or self.branch_reason != "deterministic_incorrect"
        ):
            raise TutorContractError("Tutor remediation context reason is invalid")
        for field in ("check_id", "branch_reason"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value or len(value) > 256:
                raise TutorContractError(f"Tutor remediation {field} is invalid")
        if (
            not isinstance(self.answer_fingerprint, str)
            or len(self.answer_fingerprint) != 64
            or any(char not in "0123456789abcdef" for char in self.answer_fingerprint)
        ):
            raise TutorContractError("Tutor remediation fingerprint is invalid")
        if (
            not isinstance(self.learner_excerpt, str)
            or len(self.learner_excerpt.encode("utf-8")) > MAX_REMEDIATION_EXCERPT_BYTES
        ):
            raise TutorContractError("Tutor remediation excerpt is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "policy_version": self.policy_version,
            "check_id": self.check_id,
            "answer_fingerprint": self.answer_fingerprint,
            "outcome": self.outcome,
            "branch_reason": self.branch_reason,
            "learner_excerpt": self.learner_excerpt,
        }

    @classmethod
    def from_mapping(cls, value: Any) -> "TutorRemediationContextV1":
        if not isinstance(value, Mapping) or set(value) != {
            "schema_version",
            "policy_version",
            "check_id",
            "answer_fingerprint",
            "outcome",
            "branch_reason",
            "learner_excerpt",
        }:
            raise TutorContractError("Tutor remediation context fields are invalid")
        return cls(
            schema_version=value.get("schema_version"),
            policy_version=value.get("policy_version"),
            check_id=value.get("check_id"),
            answer_fingerprint=value.get("answer_fingerprint"),
            outcome=value.get("outcome"),
            branch_reason=value.get("branch_reason"),
            learner_excerpt=value.get("learner_excerpt"),
        )


def build_remediation_context(
    evaluation: DeterministicEvaluationResultV1,
    resolution: TutorBranchResolutionV1,
    answer: Mapping[str, Any],
) -> TutorRemediationContextV1:
    if evaluation.outcome != "incorrect" or resolution.branch_action != "remediate":
        raise TutorContractError(
            "only an incorrect remediate branch retains an excerpt"
        )
    return TutorRemediationContextV1(
        check_id=evaluation.check_id,
        answer_fingerprint=evaluation.answer_fingerprint,
        outcome=evaluation.outcome,
        branch_reason=resolution.reason_code,
        learner_excerpt=learner_answer_excerpt(answer),
    )


def retain_evaluation_evidence(
    existing: list[dict[str, Any]],
    evaluation: DeterministicEvaluationResultV1,
    resolution: TutorBranchResolutionV1,
) -> list[dict[str, Any]]:
    if not isinstance(existing, list):
        raise TutorContractError("Tutor learner evidence must be a list")
    record = {
        "kind": "deterministic_evaluation",
        "evaluation": evaluation.to_dict(),
        "resolution": resolution.to_dict(),
    }
    retained = [*existing, record][-MAX_RETAINED_EVALUATIONS:]
    if len(canonical_json_bytes(retained)) > MAX_RETAINED_EVIDENCE_BYTES:
        retained = [record]
    if len(canonical_json_bytes(retained)) > MAX_RETAINED_EVIDENCE_BYTES:
        raise TutorContractError("Tutor learner evidence exceeds retention budget")
    return retained


__all__ = [
    "MAX_REMEDIATION_EXCERPT_BYTES",
    "TUTOR_RETENTION_POLICY_VERSION",
    "TutorRemediationContextV1",
    "build_remediation_context",
    "learner_answer_excerpt",
    "retain_evaluation_evidence",
]
