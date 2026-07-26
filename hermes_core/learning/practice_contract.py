# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Versioned contracts for trusted Practice grading and assistance.

The module is dependency-light and contains no provider, store, HTTP, or UI
code.  In particular, semantic evaluation values deliberately have no
``passed``, ``correct``, ``score``, ``mastery``, or branch field: they are
reviewable draft material, never deterministic grader truth.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
import unicodedata
from typing import Any, Mapping

from learning.tutor_contract import canonical_json_bytes


PRACTICE_CONTRACT_VERSION = 1
PRACTICE_GRADER_POLICY_VERSION = "practice-grader-v1"
MAX_PRACTICE_REQUEST_BYTES = 32 * 1024
MAX_HINT_CODEPOINTS = 4_000
MAX_HINT_TOTAL_BYTES = 12 * 1024
MAX_EXPLANATION_CODEPOINTS = 8_000
MAX_RUBRIC_CRITERIA = 8
MAX_CRITERION_TEXT = 1_200
MAX_RESULT_ITEMS = 12
MAX_RESULT_TEXT = 800

HINT_LEVELS = (
    "direction",
    "next_step",
    "scaffold",
    "full_solution",
)
GRADER_OUTCOMES = frozenset(
    {"correct", "incorrect", "timeout", "sandbox_failure", "ungradable"}
)
CRITERION_STATUSES = frozenset({"addressed", "gap", "uncertain"})

_OPAQUE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class PracticeContractError(ValueError):
    """A Practice request, rubric, or typed result is invalid."""


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) for key in value
    ):
        raise PracticeContractError(f"{field} must be an object")
    return value


def _exact(value: Mapping[str, Any], fields: set[str], field: str) -> None:
    if set(value) != fields:
        raise PracticeContractError(f"{field} fields are invalid")


def _opaque_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _OPAQUE_ID_RE.fullmatch(value):
        raise PracticeContractError(f"{field} is invalid")
    return unicodedata.normalize("NFC", value)


def _sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise PracticeContractError(f"{field} is invalid")
    return value


def _bounded_text(
    value: Any,
    field: str,
    *,
    maximum: int,
    required: bool = True,
) -> str:
    if not isinstance(value, str):
        raise PracticeContractError(f"{field} must be a string")
    normalized = unicodedata.normalize("NFC", value).strip()
    if (required and not normalized) or len(normalized) > maximum:
        raise PracticeContractError(f"{field} is invalid")
    return normalized


def _bounded_strings(
    value: Any,
    field: str,
    *,
    maximum_items: int = MAX_RESULT_ITEMS,
    maximum_text: int = MAX_RESULT_TEXT,
) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > maximum_items:
        raise PracticeContractError(f"{field} must be a bounded list")
    return tuple(
        _bounded_text(item, f"{field}[{index}]", maximum=maximum_text)
        for index, item in enumerate(value)
    )


def validate_hint_ladder(value: Any) -> dict[str, Any]:
    """Validate and own one explicit activated-question hint ladder."""

    raw = _mapping(value, "hint_ladder")
    allowed = {"schema_version", *HINT_LEVELS}
    if not set(raw).issubset(allowed) or raw.get("schema_version") != 1:
        raise PracticeContractError("hint_ladder fields are invalid")
    ladder: dict[str, Any] = {"schema_version": 1}
    for level in HINT_LEVELS:
        if level in raw:
            ladder[level] = _bounded_text(
                raw[level], f"hint_ladder.{level}", maximum=MAX_HINT_CODEPOINTS
            )
    if len(ladder) == 1:
        raise PracticeContractError("hint_ladder needs at least one level")
    if len(canonical_json_bytes(ladder)) > MAX_HINT_TOTAL_BYTES:
        raise PracticeContractError("hint_ladder exceeds its byte cap")
    return ladder


def validate_explanation_rubric(value: Any) -> dict[str, Any]:
    """Validate the exact semantic rubric pinned when a quiz is activated."""

    raw = _mapping(value, "explanation_rubric")
    _exact(raw, {"schema_version", "criteria"}, "explanation_rubric")
    if raw.get("schema_version") != 1:
        raise PracticeContractError("unsupported explanation_rubric version")
    criteria = raw.get("criteria")
    if not isinstance(criteria, list) or not 1 <= len(criteria) <= MAX_RUBRIC_CRITERIA:
        raise PracticeContractError("explanation_rubric criteria are invalid")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(criteria):
        criterion = _mapping(item, f"criteria[{index}]")
        if not set(criterion).issubset({"criterion_id", "description", "tags"}):
            raise PracticeContractError(f"criteria[{index}] fields are invalid")
        criterion_id = _opaque_id(
            criterion.get("criterion_id"), f"criteria[{index}].criterion_id"
        )
        if criterion_id in seen:
            raise PracticeContractError("criterion_id must be unique")
        seen.add(criterion_id)
        normalized_item = {
            "criterion_id": criterion_id,
            "description": _bounded_text(
                criterion.get("description"),
                f"criteria[{index}].description",
                maximum=MAX_CRITERION_TEXT,
            ),
            "tags": list(
                _bounded_strings(
                    criterion.get("tags", []),
                    f"criteria[{index}].tags",
                    maximum_items=8,
                    maximum_text=80,
                )
            ),
        }
        normalized.append(normalized_item)
    return {"schema_version": 1, "criteria": normalized}


def explanation_rubric_hash(value: Any) -> str:
    return hashlib.sha256(
        canonical_json_bytes(validate_explanation_rubric(value))
    ).hexdigest()


def _grader_kind(question: Mapping[str, Any]) -> str:
    qtype = question.get("type")
    if qtype == "choice":
        return "choice_exact"
    if qtype == "true_false":
        return "boolean_exact"
    if qtype == "short_answer":
        return "short_answer_exact"
    if qtype == "code":
        return (
            "code_transcribe"
            if question.get("mode") == "transcribe"
            else "code_sandbox"
        )
    if qtype == "derivation":
        return "derivation"
    raise PracticeContractError("question type has no deterministic grader")


def _grader_truth(question: Mapping[str, Any]) -> dict[str, Any]:
    qtype = question.get("type")
    if qtype == "choice":
        return {
            "type": qtype,
            "options": question.get("options") or [],
            "answer": question.get("answer"),
        }
    if qtype == "true_false":
        return {"type": qtype, "answer": question.get("answer")}
    if qtype == "short_answer":
        return {
            "type": qtype,
            "answer": question.get("answer"),
            "accepted": question.get("accepted") or [],
        }
    if qtype == "code":
        return {
            "type": qtype,
            "language": question.get("language"),
            "mode": question.get("mode"),
            "starter": question.get("starter") or "",
            "target_code": question.get("target_code") or "",
            "test_code": question.get("test_code") or "",
        }
    if qtype == "derivation":
        return {
            "type": qtype,
            "mode": question.get("mode") or "solve",
            "check": question.get("check"),
            "cloze": question.get("cloze") or [],
            "steps": question.get("steps") or [],
            "target_steps": question.get("target_steps") or [],
        }
    raise PracticeContractError("question type has no deterministic grader")


def build_grader_provenance(
    question: Mapping[str, Any],
    *,
    artifact_id: str,
    artifact_version: int,
    item_id: str,
) -> dict[str, Any]:
    if type(artifact_version) is not int or artifact_version < 1:
        raise PracticeContractError("artifact_version is invalid")
    truth = _grader_truth(_mapping(question, "question"))
    return {
        "schema_version": 1,
        "source_kind": "activated_quiz_item",
        "artifact_id": _opaque_id(artifact_id, "artifact_id"),
        "artifact_version": artifact_version,
        "item_id": _opaque_id(item_id, "item_id"),
        "grader_kind": _grader_kind(question),
        "rubric_sha256": hashlib.sha256(canonical_json_bytes(truth)).hexdigest(),
        "policy_version": PRACTICE_GRADER_POLICY_VERSION,
    }


def validate_grader_provenance(value: Any) -> dict[str, Any]:
    raw = _mapping(value, "grader_provenance")
    _exact(
        raw,
        {
            "schema_version",
            "source_kind",
            "artifact_id",
            "artifact_version",
            "item_id",
            "grader_kind",
            "rubric_sha256",
            "policy_version",
        },
        "grader_provenance",
    )
    if raw.get("schema_version") != 1 or raw.get("source_kind") != "activated_quiz_item":
        raise PracticeContractError("grader provenance source is invalid")
    if raw.get("policy_version") != PRACTICE_GRADER_POLICY_VERSION:
        raise PracticeContractError("grader provenance policy is invalid")
    version = raw.get("artifact_version")
    if type(version) is not int or version < 1:
        raise PracticeContractError("artifact_version is invalid")
    grader_kind = raw.get("grader_kind")
    if grader_kind not in {
        "choice_exact",
        "boolean_exact",
        "short_answer_exact",
        "code_sandbox",
        "code_transcribe",
        "derivation",
    }:
        raise PracticeContractError("grader_kind is invalid")
    return {
        **dict(raw),
        "artifact_id": _opaque_id(raw.get("artifact_id"), "artifact_id"),
        "item_id": _opaque_id(raw.get("item_id"), "item_id"),
        "rubric_sha256": _sha256(raw.get("rubric_sha256"), "rubric_sha256"),
    }


@dataclass(frozen=True)
class PracticeHintRequestV1:
    artifact_id: str
    item_id: str
    idempotency_key: str
    level: str
    schema_version: int = PRACTICE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise PracticeContractError("unsupported hint request version")
        object.__setattr__(self, "artifact_id", _opaque_id(self.artifact_id, "artifact_id"))
        object.__setattr__(self, "item_id", _opaque_id(self.item_id, "item_id"))
        object.__setattr__(
            self, "idempotency_key", _opaque_id(self.idempotency_key, "idempotency_key")
        )
        if self.level not in HINT_LEVELS:
            raise PracticeContractError("hint level is invalid")
        if len(canonical_json_bytes(self.to_dict())) > MAX_PRACTICE_REQUEST_BYTES:
            raise PracticeContractError("hint request exceeds its byte cap")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_id": self.artifact_id,
            "item_id": self.item_id,
            "idempotency_key": self.idempotency_key,
            "level": self.level,
        }

    @property
    def request_fingerprint(self) -> str:
        value = self.to_dict()
        value.pop("idempotency_key")
        return hashlib.sha256(canonical_json_bytes(value)).hexdigest()

    @property
    def activity_id(self) -> str:
        digest = hashlib.sha256(self.idempotency_key.encode("utf-8")).hexdigest()
        return f"phint_{digest[:48]}"

    @classmethod
    def from_mapping(cls, value: Any) -> "PracticeHintRequestV1":
        raw = _mapping(value, "hint request")
        _exact(
            raw,
            {"schema_version", "artifact_id", "item_id", "idempotency_key", "level"},
            "hint request",
        )
        return cls(
            schema_version=raw.get("schema_version"),
            artifact_id=raw.get("artifact_id"),
            item_id=raw.get("item_id"),
            idempotency_key=raw.get("idempotency_key"),
            level=raw.get("level"),
        )


@dataclass(frozen=True)
class PracticeExplanationRequestV1:
    artifact_id: str
    item_id: str
    idempotency_key: str
    learner_explanation: str
    rubric_sha256: str
    schema_version: int = PRACTICE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise PracticeContractError("unsupported explanation request version")
        object.__setattr__(self, "artifact_id", _opaque_id(self.artifact_id, "artifact_id"))
        object.__setattr__(self, "item_id", _opaque_id(self.item_id, "item_id"))
        object.__setattr__(
            self, "idempotency_key", _opaque_id(self.idempotency_key, "idempotency_key")
        )
        object.__setattr__(
            self,
            "learner_explanation",
            _bounded_text(
                self.learner_explanation,
                "learner_explanation",
                maximum=MAX_EXPLANATION_CODEPOINTS,
            ),
        )
        object.__setattr__(
            self, "rubric_sha256", _sha256(self.rubric_sha256, "rubric_sha256")
        )
        if len(canonical_json_bytes(self.to_dict())) > MAX_PRACTICE_REQUEST_BYTES:
            raise PracticeContractError("explanation request exceeds its byte cap")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_id": self.artifact_id,
            "item_id": self.item_id,
            "idempotency_key": self.idempotency_key,
            "learner_explanation": self.learner_explanation,
            "rubric_sha256": self.rubric_sha256,
        }

    @property
    def request_fingerprint(self) -> str:
        value = self.to_dict()
        value.pop("idempotency_key")
        return hashlib.sha256(canonical_json_bytes(value)).hexdigest()

    @property
    def activity_id(self) -> str:
        digest = hashlib.sha256(self.idempotency_key.encode("utf-8")).hexdigest()
        return f"pexpl_{digest[:48]}"

    @classmethod
    def from_mapping(cls, value: Any) -> "PracticeExplanationRequestV1":
        raw = _mapping(value, "explanation request")
        _exact(
            raw,
            {
                "schema_version",
                "artifact_id",
                "item_id",
                "idempotency_key",
                "learner_explanation",
                "rubric_sha256",
            },
            "explanation request",
        )
        return cls(
            schema_version=raw.get("schema_version"),
            artifact_id=raw.get("artifact_id"),
            item_id=raw.get("item_id"),
            idempotency_key=raw.get("idempotency_key"),
            learner_explanation=raw.get("learner_explanation"),
            rubric_sha256=raw.get("rubric_sha256"),
        )


@dataclass(frozen=True)
class PracticeSemanticResultV1:
    rubric_sha256: str
    criteria: tuple[dict[str, Any], ...]
    observations: tuple[str, ...]
    suggestions: tuple[str, ...]
    tags: tuple[str, ...]
    usage_summary: dict[str, int]
    schema_version: int = PRACTICE_CONTRACT_VERSION

    @classmethod
    def from_mapping(cls, value: Any) -> "PracticeSemanticResultV1":
        raw = _mapping(value, "semantic result")
        _exact(
            raw,
            {
                "schema_version",
                "rubric_sha256",
                "criteria",
                "observations",
                "suggestions",
                "tags",
                "usage_summary",
            },
            "semantic result",
        )
        if raw.get("schema_version") != 1:
            raise PracticeContractError("unsupported semantic result version")
        criteria = raw.get("criteria")
        if not isinstance(criteria, list) or not 1 <= len(criteria) <= MAX_RUBRIC_CRITERIA:
            raise PracticeContractError("semantic result criteria are invalid")
        normalized_criteria: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, item in enumerate(criteria):
            criterion = _mapping(item, f"criteria[{index}]")
            _exact(
                criterion,
                {"criterion_id", "status", "note", "tags"},
                f"criteria[{index}]",
            )
            criterion_id = _opaque_id(
                criterion.get("criterion_id"), f"criteria[{index}].criterion_id"
            )
            if criterion_id in seen:
                raise PracticeContractError("semantic criterion_id must be unique")
            seen.add(criterion_id)
            status = criterion.get("status")
            if status not in CRITERION_STATUSES:
                raise PracticeContractError("semantic criterion status is invalid")
            normalized_criteria.append(
                {
                    "criterion_id": criterion_id,
                    "status": status,
                    "note": _bounded_text(
                        criterion.get("note"),
                        f"criteria[{index}].note",
                        maximum=MAX_RESULT_TEXT,
                        required=False,
                    ),
                    "tags": list(
                        _bounded_strings(
                            criterion.get("tags"),
                            f"criteria[{index}].tags",
                            maximum_items=8,
                            maximum_text=80,
                        )
                    ),
                }
            )
        usage = _mapping(raw.get("usage_summary"), "usage_summary")
        _exact(
            usage,
            {"provider_attempts", "input_tokens", "output_tokens", "wall_ms"},
            "usage_summary",
        )
        normalized_usage: dict[str, int] = {}
        caps = {
            "provider_attempts": 1,
            "input_tokens": 1_000_000,
            "output_tokens": 1_000_000,
            "wall_ms": 120_000,
        }
        for field, cap in caps.items():
            number = usage.get(field)
            if type(number) is not int or not 0 <= number <= cap:
                raise PracticeContractError(f"usage_summary.{field} is invalid")
            normalized_usage[field] = number
        observations = _bounded_strings(raw.get("observations"), "observations")
        if not observations:
            raise PracticeContractError("semantic observations must not be empty")
        return cls(
            schema_version=1,
            rubric_sha256=_sha256(raw.get("rubric_sha256"), "rubric_sha256"),
            criteria=tuple(normalized_criteria),
            observations=observations,
            suggestions=_bounded_strings(raw.get("suggestions"), "suggestions"),
            tags=_bounded_strings(raw.get("tags"), "tags", maximum_items=12, maximum_text=80),
            usage_summary=normalized_usage,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "rubric_sha256": self.rubric_sha256,
            "criteria": [dict(item) for item in self.criteria],
            "observations": list(self.observations),
            "suggestions": list(self.suggestions),
            "tags": list(self.tags),
            "usage_summary": dict(self.usage_summary),
        }


def validate_practice_evaluation_record(value: Any) -> dict[str, Any]:
    """Validate the exact semantic provenance embedded in an evaluation draft."""

    raw = _mapping(value, "practice_evaluation")
    _exact(
        raw,
        {
            "schema_version",
            "rubric_sha256",
            "evidence_activity_id",
            "criteria",
            "usage_summary",
        },
        "practice_evaluation",
    )
    result = PracticeSemanticResultV1.from_mapping(
        {
            "schema_version": raw.get("schema_version"),
            "rubric_sha256": raw.get("rubric_sha256"),
            "criteria": raw.get("criteria"),
            "observations": ["provenance"],
            "suggestions": [],
            "tags": [],
            "usage_summary": raw.get("usage_summary"),
        }
    )
    return {
        "schema_version": 1,
        "rubric_sha256": result.rubric_sha256,
        "evidence_activity_id": _opaque_id(
            raw.get("evidence_activity_id"), "evidence_activity_id"
        ),
        "criteria": [dict(item) for item in result.criteria],
        "usage_summary": dict(result.usage_summary),
    }


__all__ = [
    "CRITERION_STATUSES",
    "GRADER_OUTCOMES",
    "HINT_LEVELS",
    "MAX_EXPLANATION_CODEPOINTS",
    "MAX_HINT_CODEPOINTS",
    "PRACTICE_CONTRACT_VERSION",
    "PRACTICE_GRADER_POLICY_VERSION",
    "PracticeContractError",
    "PracticeExplanationRequestV1",
    "PracticeHintRequestV1",
    "PracticeSemanticResultV1",
    "build_grader_provenance",
    "explanation_rubric_hash",
    "validate_explanation_rubric",
    "validate_grader_provenance",
    "validate_hint_ladder",
    "validate_practice_evaluation_record",
]
