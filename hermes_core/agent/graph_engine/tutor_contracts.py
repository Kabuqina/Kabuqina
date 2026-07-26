# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Serializable contracts for the independent L-2 Tutor graph.

The ordinary Agent graph does not import this module.  Tutor state is durable
checkpoint data, so every accepted value is JSON-safe and contains no client,
credential, callback, exception, or raw provider response.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
from typing import Any, Literal, Mapping, TypedDict

from learning.tutor_contract import (
    LearningActivityKeyV1,
    TutorContractError,
    canonical_json_bytes,
)


TUTOR_GRAPH_SCHEMA_VERSION = 1
TUTOR_POLICY_VERSION = "tutor-v1"
MAX_TUTOR_GRAPH_NODES = 14
MAX_TUTOR_PROVIDER_ATTEMPTS = 2
MAX_TUTOR_INPUT_TOKENS = 32_768
MAX_TUTOR_OUTPUT_TOKENS = 4_096
MAX_TUTOR_PROVIDER_WALL_MS = 70_000
MAX_TUTOR_ACTIVE_ELAPSED_MS = 120_000
MAX_TUTOR_OUTPUT_CODEPOINTS = 24_000

TutorPhase = Literal[
    "start",
    "explain",
    "handoff",
    "acknowledge",
    "remediate",
    "terminal",
]
TutorBranch = Literal["check_1", "check_2"]
TutorControlAction = Literal["continue", "explain_again", "invalid"]

_PHASES = frozenset(
    {"start", "explain", "handoff", "acknowledge", "remediate", "terminal"}
)
_BRANCHES = frozenset({"check_1", "check_2"})
_ALLOWED_STATE_FIELDS = frozenset(
    {
        "schema_version",
        "graph_schema_version",
        "policy_version",
        "identity",
        "phase",
        "goal",
        "input_refs",
        "turns",
        "learner_evidence",
        "pending_interrupt",
        "learner_answer",
        "branch",
        "remediation_count",
        "budget",
        "provider_plan",
        "latest_output",
        "terminal",
    }
)


class TutorGraphStateV1(TypedDict, total=False):
    schema_version: int
    graph_schema_version: int
    policy_version: str
    identity: dict[str, str]
    phase: TutorPhase
    goal: str
    input_refs: list[dict[str, Any]]
    turns: list[dict[str, Any]]
    learner_evidence: list[dict[str, Any]]
    pending_interrupt: dict[str, Any]
    learner_answer: dict[str, Any]
    branch: TutorBranch
    remediation_count: int
    budget: dict[str, int]
    provider_plan: dict[str, Any]
    latest_output: dict[str, str]
    terminal: dict[str, Any]


def _bounded_text(value: Any, field: str, *, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise TutorContractError(f"{field} is invalid")
    return value


@dataclass(frozen=True)
class TutorProviderPlanV1:
    """Secret-free provider identity fixed for one Tutor activity."""

    provider_id: str
    model_id: str
    api_mode: str
    endpoint_identity: str
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise TutorContractError("unsupported provider plan schema_version")
        object.__setattr__(
            self, "provider_id", _bounded_text(self.provider_id, "provider_id", maximum=128)
        )
        object.__setattr__(
            self, "model_id", _bounded_text(self.model_id, "model_id", maximum=300)
        )
        if self.api_mode not in {"chat_completions", "anthropic_messages"}:
            raise TutorContractError("provider api_mode is unsupported")
        endpoint = _bounded_text(
            self.endpoint_identity, "endpoint_identity", maximum=2_048
        ).rstrip("/")
        if "@" in endpoint or "api_key=" in endpoint.lower():
            raise TutorContractError("endpoint_identity must not contain credentials")
        object.__setattr__(self, "endpoint_identity", endpoint)

    def to_checkpoint_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "api_mode": self.api_mode,
            "endpoint_identity": self.endpoint_identity,
        }

    @property
    def plan_hash(self) -> str:
        return hashlib.sha256(
            canonical_json_bytes(self.to_checkpoint_dict())
        ).hexdigest()

    @classmethod
    def from_checkpoint_dict(cls, value: Mapping[str, Any]) -> "TutorProviderPlanV1":
        if not isinstance(value, Mapping):
            raise TutorContractError("provider_plan must be an object")
        if set(value) != {
            "schema_version",
            "provider_id",
            "model_id",
            "api_mode",
            "endpoint_identity",
        }:
            raise TutorContractError("provider_plan fields are invalid")
        return cls(
            schema_version=value.get("schema_version"),
            provider_id=value.get("provider_id"),
            model_id=value.get("model_id"),
            api_mode=value.get("api_mode"),
            endpoint_identity=value.get("endpoint_identity"),
        )


@dataclass(frozen=True)
class TutorProviderRequestV1:
    purpose: Literal["explain", "remediate"]
    goal: str
    input_refs: tuple[dict[str, Any], ...]
    previous_output: str | None = None
    max_output_tokens: int = 2_048
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1 or self.purpose not in {"explain", "remediate"}:
            raise TutorContractError("provider request is invalid")
        _bounded_text(self.goal, "provider request goal", maximum=4_000)
        if not isinstance(self.input_refs, tuple) or len(self.input_refs) > 16:
            raise TutorContractError("provider request input_refs are invalid")
        if self.previous_output is not None and (
            not isinstance(self.previous_output, str)
            or len(self.previous_output) > MAX_TUTOR_OUTPUT_CODEPOINTS
        ):
            raise TutorContractError("provider request previous_output is invalid")
        if type(self.max_output_tokens) is not int or not 1 <= self.max_output_tokens <= 2_048:
            raise TutorContractError("provider request max_output_tokens is invalid")


@dataclass(frozen=True)
class TutorProviderResult:
    markdown: str
    actual_input_tokens: int | None = None
    actual_output_tokens: int | None = None
    actual_latency_ms: int | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.markdown, str)
            or not self.markdown.strip()
            or len(self.markdown) > MAX_TUTOR_OUTPUT_CODEPOINTS
        ):
            raise TutorContractError(
                "Tutor provider output is invalid", reason_code="invalid_model_output"
            )
        for field in (
            "actual_input_tokens",
            "actual_output_tokens",
            "actual_latency_ms",
        ):
            value = getattr(self, field)
            if value is not None and (type(value) is not int or value < 0):
                raise TutorContractError(f"{field} is invalid")


def _validate_identity(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != {
        "owner_id",
        "space_id",
        "activity_kind",
        "activity_id",
    }:
        raise TutorContractError("Tutor identity is invalid")
    key = LearningActivityKeyV1(
        value.get("owner_id"),
        value.get("space_id"),
        value.get("activity_kind"),
        value.get("activity_id"),
    )
    if key.activity_kind != "tutor":
        raise TutorContractError("L-2 requires activity_kind=tutor")
    return {
        "owner_id": key.owner_id,
        "space_id": key.space_id,
        "activity_kind": key.activity_kind,
        "activity_id": key.activity_id,
    }


def _validate_budget(value: Any) -> dict[str, int]:
    caps = {
        "nodes_used": MAX_TUTOR_GRAPH_NODES,
        "attempts_used": MAX_TUTOR_PROVIDER_ATTEMPTS,
        "reserved_input_tokens": MAX_TUTOR_INPUT_TOKENS,
        "reserved_output_tokens": MAX_TUTOR_OUTPUT_TOKENS,
        "reserved_wall_ms": MAX_TUTOR_PROVIDER_WALL_MS,
        "active_elapsed_ms": MAX_TUTOR_ACTIVE_ELAPSED_MS,
    }
    if not isinstance(value, Mapping) or set(value) != set(caps):
        raise TutorContractError("Tutor budget is invalid")
    result: dict[str, int] = {}
    for field, cap in caps.items():
        item = value.get(field)
        if type(item) is not int or not 0 <= item <= cap:
            raise TutorContractError(f"Tutor budget {field} is invalid")
        result[field] = item
    return result


def validate_tutor_state(value: Any) -> TutorGraphStateV1:
    if not isinstance(value, Mapping):
        raise TutorContractError("Tutor graph state must be an object")
    unknown = set(value) - set(_ALLOWED_STATE_FIELDS)
    if unknown:
        raise TutorContractError(f"Tutor graph state contains unknown field: {sorted(unknown)[0]}")
    if value.get("schema_version") != 1:
        raise TutorContractError("unsupported Tutor state schema_version")
    if value.get("graph_schema_version") != TUTOR_GRAPH_SCHEMA_VERSION:
        raise TutorContractError("unsupported Tutor graph_schema_version")
    if value.get("policy_version") != TUTOR_POLICY_VERSION:
        raise TutorContractError("unsupported Tutor policy_version")
    identity = _validate_identity(value.get("identity"))
    phase = value.get("phase")
    if phase not in _PHASES:
        raise TutorContractError("Tutor phase is invalid")
    goal = _bounded_text(value.get("goal"), "Tutor goal", maximum=4_000)
    input_refs = value.get("input_refs")
    if not isinstance(input_refs, list) or len(input_refs) > 16 or not all(
        isinstance(item, dict) for item in input_refs
    ):
        raise TutorContractError("Tutor input_refs are invalid")
    turns = value.get("turns")
    evidence = value.get("learner_evidence")
    if not isinstance(turns, list) or len(turns) > 2:
        raise TutorContractError("Tutor turns are invalid")
    if not isinstance(evidence, list) or len(evidence) > 2:
        raise TutorContractError("Tutor learner_evidence is invalid")
    branch = value.get("branch")
    if branch not in _BRANCHES:
        raise TutorContractError("Tutor branch is invalid")
    remediation_count = value.get("remediation_count")
    if type(remediation_count) is not int or remediation_count not in {0, 1}:
        raise TutorContractError("Tutor remediation_count is invalid")
    if (branch == "check_1" and remediation_count != 0) or (
        branch == "check_2" and remediation_count != 1
    ):
        raise TutorContractError("Tutor branch/remediation_count mismatch")
    budget = _validate_budget(value.get("budget"))
    provider_plan = TutorProviderPlanV1.from_checkpoint_dict(
        value.get("provider_plan")
    ).to_checkpoint_dict()

    result: TutorGraphStateV1 = {
        "schema_version": 1,
        "graph_schema_version": TUTOR_GRAPH_SCHEMA_VERSION,
        "policy_version": TUTOR_POLICY_VERSION,
        "identity": identity,
        "phase": phase,
        "goal": goal,
        "input_refs": copy.deepcopy(input_refs),
        "turns": copy.deepcopy(turns),
        "learner_evidence": copy.deepcopy(evidence),
        "branch": branch,
        "remediation_count": remediation_count,
        "budget": budget,
        "provider_plan": provider_plan,
    }
    for optional in (
        "pending_interrupt",
        "learner_answer",
        "latest_output",
        "terminal",
    ):
        if optional in value:
            candidate = value[optional]
            if not isinstance(candidate, Mapping):
                raise TutorContractError(f"Tutor {optional} is invalid")
            result[optional] = copy.deepcopy(dict(candidate))

    latest = result.get("latest_output")
    if latest is not None:
        if set(latest) != {"kind", "markdown"} or latest.get("kind") not in {
            "explanation",
            "feedback",
        }:
            raise TutorContractError("Tutor latest_output is invalid")
        markdown = latest.get("markdown")
        if not isinstance(markdown, str) or not markdown or len(markdown) > MAX_TUTOR_OUTPUT_CODEPOINTS:
            raise TutorContractError("Tutor latest_output markdown is invalid")
    terminal = result.get("terminal")
    if terminal is not None:
        if terminal != {
            "outcome": "completed",
            "completion_basis": "participation_only",
        }:
            raise TutorContractError("L-2 terminal is invalid")
        if phase != "terminal":
            raise TutorContractError("Tutor terminal requires terminal phase")
    return copy.deepcopy(result)


def new_tutor_state(
    key: LearningActivityKeyV1,
    *,
    goal: str,
    input_refs: tuple[dict[str, Any], ...],
    provider_plan: TutorProviderPlanV1,
) -> TutorGraphStateV1:
    return validate_tutor_state(
        {
            "schema_version": 1,
            "graph_schema_version": TUTOR_GRAPH_SCHEMA_VERSION,
            "policy_version": TUTOR_POLICY_VERSION,
            "identity": {
                "owner_id": key.owner_id,
                "space_id": key.space_id,
                "activity_kind": key.activity_kind,
                "activity_id": key.activity_id,
            },
            "phase": "start",
            "goal": goal,
            "input_refs": copy.deepcopy(list(input_refs)),
            "turns": [],
            "learner_evidence": [],
            "branch": "check_1",
            "remediation_count": 0,
            "budget": {
                "nodes_used": 0,
                "attempts_used": 0,
                "reserved_input_tokens": 0,
                "reserved_output_tokens": 0,
                "reserved_wall_ms": 0,
                "active_elapsed_ms": 0,
            },
            "provider_plan": provider_plan.to_checkpoint_dict(),
        }
    )


def classify_learner_control(
    branch: str, answer: Mapping[str, Any] | None
) -> TutorControlAction:
    if branch not in _BRANCHES or not isinstance(answer, Mapping):
        return "invalid"
    if answer.get("type") != "choice" or set(answer) != {"type", "selected"}:
        return "invalid"
    selected = answer.get("selected")
    if not isinstance(selected, list) or len(selected) != 1:
        return "invalid"
    option = selected[0]
    if option == "continue":
        return "continue"
    if option == "explain_again" and branch == "check_1":
        return "explain_again"
    return "invalid"


__all__ = [
    "TutorBranch",
    "TutorControlAction",
    "TutorGraphStateV1",
    "TutorPhase",
    "TutorProviderPlanV1",
    "TutorProviderRequestV1",
    "TutorProviderResult",
    "classify_learner_control",
    "new_tutor_state",
    "validate_tutor_state",
]

