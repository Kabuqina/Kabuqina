# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Pure L-3 Tutor branch contracts and ``tutor-branch-v1`` policy.

The policy consumes only a host-pinned check spec, a typed deterministic
evaluation result, bounded weak-point codes and an explicit hint request.  It
does not load storage, call a model, inspect learner prose or mutate a graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
from typing import Any, Literal, Mapping

from learning.tutor_contract import TutorContractError, canonical_json_bytes


TUTOR_BRANCH_POLICY_VERSION = "tutor-branch-v1"
MAX_BRANCH_EVIDENCE_CODES = 8
MAX_BRANCH_WEAK_POINT_CODES = 8

SourceStatus = Literal["not_applicable", "verified", "missing", "stale", "hash_mismatch"]
EvaluationOutcome = Literal["submitted", "correct", "incorrect", "invalid"]
BranchAction = Literal["advance", "remediate", "hint", "complete", "blocked"]

_RUBRIC_SOURCE_KINDS = frozenset(
    {"activated_quiz_item", "trusted_builtin_rubric"}
)
_UNIT_SOURCE_KINDS = frozenset({"activated_plan_item", "trusted_builtin_unit"})
_SOURCE_KINDS = _RUBRIC_SOURCE_KINDS | _UNIT_SOURCE_KINDS
_EXPECTED_INPUTS = frozenset({"free_text", "choice", "step"})
_EVALUATION_MODES = frozenset({"acknowledgement", "deterministic"})
_NORMALIZATION_POLICIES = frozenset(
    {
        "acknowledgement-v1",
        "choice-v1",
        "boolean-v1",
        "short-answer-v1",
        "code-v1",
        "derivation-v1",
    }
)
_NORMALIZATION_INPUT = {
    "acknowledgement-v1": "choice",
    "choice-v1": "choice",
    "boolean-v1": "choice",
    "short-answer-v1": "free_text",
    "code-v1": "free_text",
    "derivation-v1": "step",
}
_CONTROL_POLICIES = frozenset({"continue_or_explain_once", "continue_only"})
_CORRECT_ACTIONS = frozenset({"complete", "advance"})
_OUTCOMES = frozenset({"submitted", "correct", "incorrect", "invalid"})
_SOURCE_STATUSES = frozenset(
    {"not_applicable", "verified", "missing", "stale", "hash_mismatch"}
)
_EVIDENCE_CODES = frozenset(
    {
        "answer_submitted",
        "answer_invalid",
        "deterministic_correct",
        "deterministic_incorrect",
        "rubric_verified",
    }
)
_WEAK_POINT_CODES = frozenset(
    {
        "concept_gap",
        "procedure_gap",
        "calculation_gap",
        "representation_gap",
        "explanation_gap",
        "uncertain",
    }
)


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TutorContractError(f"{label} must be an object")
    return value


def _exact(value: Mapping[str, Any], fields: set[str], label: str) -> None:
    if set(value) != fields:
        raise TutorContractError(f"{label} fields are invalid")


def _opaque_id(value: Any, label: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise TutorContractError(f"{label} is invalid")
    if any(ord(char) < 0x21 or ord(char) > 0x7E for char in value):
        raise TutorContractError(f"{label} must be printable ASCII")
    return value


def _sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise TutorContractError(f"{label} is invalid")
    return value


def _iso8601(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z") or len(value) > 40:
        raise TutorContractError(f"{label} is invalid")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise TutorContractError(f"{label} is invalid") from exc
    return value


def _bounded_codes(
    value: Any,
    *,
    label: str,
    allowed: frozenset[str],
    maximum: int,
) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise TutorContractError(f"{label} is invalid")
    result: list[str] = []
    for item in value:
        if item not in allowed or item in result:
            raise TutorContractError(f"{label} is invalid")
        result.append(item)
    return tuple(result)


@dataclass(frozen=True)
class PinnedTutorSourceRefV1:
    source_kind: Literal[
        "activated_quiz_item",
        "trusted_builtin_rubric",
        "activated_plan_item",
        "trusted_builtin_unit",
    ]
    source_id: str
    source_version: int
    source_sha256: str
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1 or self.source_kind not in _SOURCE_KINDS:
            raise TutorContractError("pinned Tutor source is invalid")
        object.__setattr__(self, "source_id", _opaque_id(self.source_id, "source_id"))
        if type(self.source_version) is not int or self.source_version < 1:
            raise TutorContractError("source_version is invalid")
        object.__setattr__(
            self, "source_sha256", _sha256(self.source_sha256, "source_sha256")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "source_kind": self.source_kind,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "source_sha256": self.source_sha256,
        }

    @classmethod
    def from_mapping(cls, value: Any) -> "PinnedTutorSourceRefV1":
        raw = _mapping(value, "pinned Tutor source")
        _exact(
            raw,
            {
                "schema_version",
                "source_kind",
                "source_id",
                "source_version",
                "source_sha256",
            },
            "pinned Tutor source",
        )
        return cls(
            schema_version=raw.get("schema_version"),
            source_kind=raw.get("source_kind"),
            source_id=raw.get("source_id"),
            source_version=raw.get("source_version"),
            source_sha256=raw.get("source_sha256"),
        )


@dataclass(frozen=True)
class TutorCheckSpecV1:
    check_id: str
    expected_input: Literal["free_text", "choice", "step"]
    evaluation_mode: Literal["acknowledgement", "deterministic"]
    normalization_policy: str
    rubric_ref: PinnedTutorSourceRefV1 | None = None
    control_policy: Literal["continue_or_explain_once", "continue_only"] | None = None
    correct_action: Literal["complete", "advance"] | None = None
    next_unit_ref: PinnedTutorSourceRefV1 | None = None
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise TutorContractError("unsupported Tutor check schema_version")
        object.__setattr__(self, "check_id", _opaque_id(self.check_id, "check_id"))
        if self.expected_input not in _EXPECTED_INPUTS:
            raise TutorContractError("expected_input is invalid")
        if self.evaluation_mode not in _EVALUATION_MODES:
            raise TutorContractError("evaluation_mode is invalid")
        if self.normalization_policy not in _NORMALIZATION_POLICIES:
            raise TutorContractError("normalization_policy is invalid")
        if _NORMALIZATION_INPUT[self.normalization_policy] != self.expected_input:
            raise TutorContractError("normalization_policy does not match expected_input")
        if self.rubric_ref is not None and not isinstance(
            self.rubric_ref, PinnedTutorSourceRefV1
        ):
            raise TutorContractError("rubric_ref is invalid")
        if (
            self.rubric_ref is not None
            and self.rubric_ref.source_kind not in _RUBRIC_SOURCE_KINDS
        ):
            raise TutorContractError("rubric_ref source_kind is invalid")
        if self.next_unit_ref is not None and not isinstance(
            self.next_unit_ref, PinnedTutorSourceRefV1
        ):
            raise TutorContractError("next_unit_ref is invalid")
        if (
            self.next_unit_ref is not None
            and self.next_unit_ref.source_kind not in _UNIT_SOURCE_KINDS
        ):
            raise TutorContractError("next_unit_ref source_kind is invalid")
        if self.control_policy is not None and self.control_policy not in _CONTROL_POLICIES:
            raise TutorContractError("control_policy is invalid")
        if self.correct_action is not None and self.correct_action not in _CORRECT_ACTIONS:
            raise TutorContractError("correct_action is invalid")
        if self.evaluation_mode == "acknowledgement":
            if (
                self.rubric_ref is not None
                or self.correct_action is not None
                or self.next_unit_ref is not None
                or self.control_policy is None
                or self.normalization_policy != "acknowledgement-v1"
            ):
                raise TutorContractError("acknowledgement check fields are invalid")
        else:
            if self.rubric_ref is None or self.correct_action is None or self.control_policy is not None:
                raise TutorContractError("deterministic check fields are invalid")
            if self.normalization_policy == "acknowledgement-v1":
                raise TutorContractError("deterministic check normalization is invalid")
            if (self.correct_action == "advance") != (self.next_unit_ref is not None):
                raise TutorContractError("advance requires exactly one next_unit_ref")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "check_id": self.check_id,
            "expected_input": self.expected_input,
            "evaluation_mode": self.evaluation_mode,
            "normalization_policy": self.normalization_policy,
            "rubric_ref": self.rubric_ref.to_dict() if self.rubric_ref else None,
            "control_policy": self.control_policy,
            "correct_action": self.correct_action,
            "next_unit_ref": self.next_unit_ref.to_dict() if self.next_unit_ref else None,
        }

    @classmethod
    def from_mapping(cls, value: Any) -> "TutorCheckSpecV1":
        raw = _mapping(value, "Tutor check spec")
        _exact(
            raw,
            {
                "schema_version",
                "check_id",
                "expected_input",
                "evaluation_mode",
                "normalization_policy",
                "rubric_ref",
                "control_policy",
                "correct_action",
                "next_unit_ref",
            },
            "Tutor check spec",
        )
        return cls(
            schema_version=raw.get("schema_version"),
            check_id=raw.get("check_id"),
            expected_input=raw.get("expected_input"),
            evaluation_mode=raw.get("evaluation_mode"),
            normalization_policy=raw.get("normalization_policy"),
            rubric_ref=(
                PinnedTutorSourceRefV1.from_mapping(raw["rubric_ref"])
                if raw.get("rubric_ref") is not None
                else None
            ),
            control_policy=raw.get("control_policy"),
            correct_action=raw.get("correct_action"),
            next_unit_ref=(
                PinnedTutorSourceRefV1.from_mapping(raw["next_unit_ref"])
                if raw.get("next_unit_ref") is not None
                else None
            ),
        )


@dataclass(frozen=True)
class DeterministicEvaluationResultV1:
    evaluation_id: str
    activity_id: str
    activity_kind: str
    check_id: str
    checkpoint_revision: int
    mode: Literal["acknowledgement", "deterministic"]
    outcome: EvaluationOutcome
    grader_id: str
    grader_version: str
    rubric_ref: PinnedTutorSourceRefV1 | None
    answer_fingerprint: str
    evidence_codes: tuple[str, ...]
    evaluated_at: str
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1 or self.mode not in _EVALUATION_MODES:
            raise TutorContractError("evaluation result mode/version is invalid")
        for field in ("evaluation_id", "activity_id", "activity_kind", "check_id"):
            object.__setattr__(self, field, _opaque_id(getattr(self, field), field))
        if type(self.checkpoint_revision) is not int or self.checkpoint_revision < 0:
            raise TutorContractError("checkpoint_revision is invalid")
        if self.outcome not in _OUTCOMES:
            raise TutorContractError("evaluation outcome is invalid")
        if self.rubric_ref is not None and not isinstance(
            self.rubric_ref, PinnedTutorSourceRefV1
        ):
            raise TutorContractError("evaluation rubric_ref is invalid")
        if (
            self.rubric_ref is not None
            and self.rubric_ref.source_kind not in _RUBRIC_SOURCE_KINDS
        ):
            raise TutorContractError("evaluation rubric_ref source_kind is invalid")
        object.__setattr__(self, "grader_id", _opaque_id(self.grader_id, "grader_id"))
        object.__setattr__(
            self, "grader_version", _opaque_id(self.grader_version, "grader_version")
        )
        object.__setattr__(
            self,
            "answer_fingerprint",
            _sha256(self.answer_fingerprint, "answer_fingerprint"),
        )
        object.__setattr__(
            self,
            "evidence_codes",
            _bounded_codes(
                self.evidence_codes,
                label="evidence_codes",
                allowed=_EVIDENCE_CODES,
                maximum=MAX_BRANCH_EVIDENCE_CODES,
            ),
        )
        object.__setattr__(self, "evaluated_at", _iso8601(self.evaluated_at, "evaluated_at"))
        if self.activity_kind != "tutor":
            raise TutorContractError("branch evaluation requires activity_kind=tutor")
        if self.mode == "acknowledgement":
            if self.rubric_ref is not None or self.outcome not in {"submitted", "invalid"}:
                raise TutorContractError("acknowledgement evaluation is invalid")
        elif self.rubric_ref is None or self.outcome == "submitted":
            raise TutorContractError("deterministic evaluation is invalid")
        required_code = {
            "submitted": "answer_submitted",
            "invalid": "answer_invalid",
            "correct": "deterministic_correct",
            "incorrect": "deterministic_incorrect",
        }[self.outcome]
        if required_code not in self.evidence_codes:
            raise TutorContractError("evaluation evidence does not support its outcome")
        if self.outcome in {"correct", "incorrect"} and "rubric_verified" not in self.evidence_codes:
            raise TutorContractError("deterministic outcome requires verified rubric evidence")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "evaluation_id": self.evaluation_id,
            "activity_id": self.activity_id,
            "activity_kind": self.activity_kind,
            "check_id": self.check_id,
            "checkpoint_revision": self.checkpoint_revision,
            "mode": self.mode,
            "outcome": self.outcome,
            "grader_id": self.grader_id,
            "grader_version": self.grader_version,
            "rubric_ref": self.rubric_ref.to_dict() if self.rubric_ref else None,
            "answer_fingerprint": self.answer_fingerprint,
            "evidence_codes": list(self.evidence_codes),
            "evaluated_at": self.evaluated_at,
        }

    @classmethod
    def from_mapping(cls, value: Any) -> "DeterministicEvaluationResultV1":
        raw = _mapping(value, "deterministic evaluation result")
        _exact(
            raw,
            {
                "schema_version",
                "evaluation_id",
                "activity_id",
                "activity_kind",
                "check_id",
                "checkpoint_revision",
                "mode",
                "outcome",
                "grader_id",
                "grader_version",
                "rubric_ref",
                "answer_fingerprint",
                "evidence_codes",
                "evaluated_at",
            },
            "deterministic evaluation result",
        )
        return cls(
            schema_version=raw.get("schema_version"),
            evaluation_id=raw.get("evaluation_id"),
            activity_id=raw.get("activity_id"),
            activity_kind=raw.get("activity_kind"),
            check_id=raw.get("check_id"),
            checkpoint_revision=raw.get("checkpoint_revision"),
            mode=raw.get("mode"),
            outcome=raw.get("outcome"),
            grader_id=raw.get("grader_id"),
            grader_version=raw.get("grader_version"),
            rubric_ref=(
                PinnedTutorSourceRefV1.from_mapping(raw["rubric_ref"])
                if raw.get("rubric_ref") is not None
                else None
            ),
            answer_fingerprint=raw.get("answer_fingerprint"),
            evidence_codes=tuple(raw.get("evidence_codes") or ()),
            evaluated_at=raw.get("evaluated_at"),
        )


@dataclass(frozen=True)
class TutorBranchPolicyInputV1:
    check_spec: TutorCheckSpecV1
    evaluation: DeterministicEvaluationResultV1
    remediation_count: int
    source_status: SourceStatus
    hint_requested: bool = False
    weak_point_codes: tuple[str, ...] = ()
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise TutorContractError("unsupported branch input schema_version")
        if not isinstance(self.check_spec, TutorCheckSpecV1) or not isinstance(
            self.evaluation, DeterministicEvaluationResultV1
        ):
            raise TutorContractError("branch check/evaluation is invalid")
        if type(self.remediation_count) is not int or self.remediation_count not in {0, 1}:
            raise TutorContractError("remediation_count is invalid")
        if self.source_status not in _SOURCE_STATUSES or type(self.hint_requested) is not bool:
            raise TutorContractError("branch source/hint status is invalid")
        object.__setattr__(
            self,
            "weak_point_codes",
            _bounded_codes(
                self.weak_point_codes,
                label="weak_point_codes",
                allowed=_WEAK_POINT_CODES,
                maximum=MAX_BRANCH_WEAK_POINT_CODES,
            ),
        )
        if (
            self.evaluation.activity_id == ""
            or self.evaluation.check_id != self.check_spec.check_id
            or self.evaluation.mode != self.check_spec.evaluation_mode
        ):
            raise TutorContractError("branch evaluation/check identity is invalid")
        if self.check_spec.evaluation_mode == "acknowledgement":
            if self.source_status != "not_applicable" or self.hint_requested:
                raise TutorContractError("acknowledgement source_status is invalid")
        elif self.evaluation.rubric_ref != self.check_spec.rubric_ref:
            raise TutorContractError("branch rubric provenance mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "check_spec": self.check_spec.to_dict(),
            "evaluation": self.evaluation.to_dict(),
            "remediation_count": self.remediation_count,
            "source_status": self.source_status,
            "hint_requested": self.hint_requested,
            "weak_point_codes": list(self.weak_point_codes),
        }

    @classmethod
    def from_mapping(cls, value: Any) -> "TutorBranchPolicyInputV1":
        raw = _mapping(value, "Tutor branch input")
        _exact(
            raw,
            {
                "schema_version",
                "check_spec",
                "evaluation",
                "remediation_count",
                "source_status",
                "hint_requested",
                "weak_point_codes",
            },
            "Tutor branch input",
        )
        return cls(
            schema_version=raw.get("schema_version"),
            check_spec=TutorCheckSpecV1.from_mapping(raw.get("check_spec")),
            evaluation=DeterministicEvaluationResultV1.from_mapping(
                raw.get("evaluation")
            ),
            remediation_count=raw.get("remediation_count"),
            source_status=raw.get("source_status"),
            hint_requested=raw.get("hint_requested"),
            weak_point_codes=tuple(raw.get("weak_point_codes") or ()),
        )


@dataclass(frozen=True)
class TutorBranchResolutionV1:
    branch_action: BranchAction | None
    control_action: Literal["reissue"] | None
    reason_code: str
    completion_basis: Literal["participation_only", "deterministic_correct"] | None
    next_unit_ref: PinnedTutorSourceRefV1 | None
    input_fingerprint: str
    policy_version: str = TUTOR_BRANCH_POLICY_VERSION
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1 or self.policy_version != TUTOR_BRANCH_POLICY_VERSION:
            raise TutorContractError("branch resolution version is invalid")
        if (self.branch_action is None) == (self.control_action is None):
            raise TutorContractError("branch resolution requires exactly one action")
        if self.branch_action is not None and self.branch_action not in {
            "advance", "remediate", "hint", "complete", "blocked"
        }:
            raise TutorContractError("branch action is invalid")
        if self.control_action not in {None, "reissue"}:
            raise TutorContractError("branch control action is invalid")
        if self.next_unit_ref is not None and not isinstance(
            self.next_unit_ref, PinnedTutorSourceRefV1
        ):
            raise TutorContractError("resolution next_unit_ref is invalid")
        object.__setattr__(self, "reason_code", _opaque_id(self.reason_code, "reason_code"))
        object.__setattr__(
            self, "input_fingerprint", _sha256(self.input_fingerprint, "input_fingerprint")
        )
        if self.branch_action == "advance" and self.next_unit_ref is None:
            raise TutorContractError("advance resolution requires next_unit_ref")
        if self.branch_action != "advance" and self.next_unit_ref is not None:
            raise TutorContractError("only advance resolution accepts next_unit_ref")
        if self.branch_action == "complete":
            if self.completion_basis not in {"participation_only", "deterministic_correct"}:
                raise TutorContractError("complete resolution basis is invalid")
        elif self.completion_basis is not None:
            raise TutorContractError("non-complete resolution cannot have completion_basis")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "policy_version": self.policy_version,
            "branch_action": self.branch_action,
            "control_action": self.control_action,
            "reason_code": self.reason_code,
            "completion_basis": self.completion_basis,
            "next_unit_ref": self.next_unit_ref.to_dict() if self.next_unit_ref else None,
            "input_fingerprint": self.input_fingerprint,
        }

    @classmethod
    def from_mapping(cls, value: Any) -> "TutorBranchResolutionV1":
        raw = _mapping(value, "Tutor branch resolution")
        _exact(
            raw,
            {
                "schema_version",
                "policy_version",
                "branch_action",
                "control_action",
                "reason_code",
                "completion_basis",
                "next_unit_ref",
                "input_fingerprint",
            },
            "Tutor branch resolution",
        )
        return cls(
            schema_version=raw.get("schema_version"),
            policy_version=raw.get("policy_version"),
            branch_action=raw.get("branch_action"),
            control_action=raw.get("control_action"),
            reason_code=raw.get("reason_code"),
            completion_basis=raw.get("completion_basis"),
            next_unit_ref=(
                PinnedTutorSourceRefV1.from_mapping(raw["next_unit_ref"])
                if raw.get("next_unit_ref") is not None
                else None
            ),
            input_fingerprint=raw.get("input_fingerprint"),
        )


def apply_tutor_branch_policy(value: TutorBranchPolicyInputV1) -> TutorBranchResolutionV1:
    """Apply the pure, total ``tutor-branch-v1`` decision table."""

    if not isinstance(value, TutorBranchPolicyInputV1):
        raise TutorContractError("branch policy input is invalid")
    fingerprint = hashlib.sha256(canonical_json_bytes(value.to_dict())).hexdigest()
    check = value.check_spec
    outcome = value.evaluation.outcome

    def resolution(
        *,
        branch_action: BranchAction | None = None,
        control_action: Literal["reissue"] | None = None,
        reason_code: str,
        completion_basis: Literal["participation_only", "deterministic_correct"] | None = None,
        next_unit_ref: PinnedTutorSourceRefV1 | None = None,
    ) -> TutorBranchResolutionV1:
        return TutorBranchResolutionV1(
            branch_action=branch_action,
            control_action=control_action,
            reason_code=reason_code,
            completion_basis=completion_basis,
            next_unit_ref=next_unit_ref,
            input_fingerprint=fingerprint,
        )

    if check.evaluation_mode == "deterministic" and value.source_status != "verified":
        return resolution(branch_action="blocked", reason_code="source_missing")
    if outcome == "invalid":
        return resolution(control_action="reissue", reason_code="invalid_answer")
    if outcome == "correct":
        if check.correct_action == "advance":
            return resolution(
                branch_action="advance",
                reason_code="deterministic_correct",
                next_unit_ref=check.next_unit_ref,
            )
        return resolution(
            branch_action="complete",
            reason_code="deterministic_correct",
            completion_basis="deterministic_correct",
        )
    if value.hint_requested:
        return resolution(branch_action="hint", reason_code="explicit_hint_requested")
    if outcome == "incorrect":
        if value.remediation_count == 0:
            return resolution(branch_action="remediate", reason_code="deterministic_incorrect")
        return resolution(branch_action="blocked", reason_code="remediation_exhausted")
    if outcome == "submitted":
        return resolution(
            branch_action="complete",
            reason_code="acknowledged",
            completion_basis="participation_only",
        )
    raise TutorContractError("branch policy outcome is unreachable")


__all__ = [
    "DeterministicEvaluationResultV1",
    "PinnedTutorSourceRefV1",
    "TUTOR_BRANCH_POLICY_VERSION",
    "TutorBranchPolicyInputV1",
    "TutorBranchResolutionV1",
    "TutorCheckSpecV1",
    "apply_tutor_branch_policy",
]
