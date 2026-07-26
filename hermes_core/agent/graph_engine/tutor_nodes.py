# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Deterministic L-2 Tutor graph nodes."""

from __future__ import annotations

import copy
from typing import Any

from agent.graph_engine.tutor_contracts import (
    TutorGraphStateV1,
    classify_learner_control,
    validate_tutor_state,
)
from agent.graph_engine.tutor_ports import TutorGraphServices
from learning.tutor_contract import TutorContractError


def _advance_node(state: TutorGraphStateV1) -> TutorGraphStateV1:
    updated = copy.deepcopy(state)
    budget = dict(updated["budget"])
    budget["nodes_used"] += 1
    updated["budget"] = budget
    updated.pop("pending_interrupt", None)
    return updated


def validate_context(
    state: TutorGraphStateV1, *, services: TutorGraphServices
) -> TutorGraphStateV1:
    del services
    updated = _advance_node(validate_tutor_state(state))
    if updated["identity"]["activity_kind"] != "tutor":
        raise TutorContractError("L-2 requires activity_kind=tutor")
    updated["phase"] = "explain"
    return updated


def explain_bounded_unit(
    state: TutorGraphStateV1, *, services: TutorGraphServices
) -> TutorGraphStateV1:
    updated = _advance_node(validate_tutor_state(state))
    markdown = services.generate(updated, purpose="explain")
    updated["latest_output"] = {"kind": "explanation", "markdown": markdown}
    updated["turns"] = [
        *updated["turns"],
        {"kind": "explanation", "markdown": markdown},
    ]
    updated["phase"] = "handoff"
    return validate_tutor_state(updated)


def handoff_to_learner(
    state: TutorGraphStateV1, *, services: TutorGraphServices
) -> TutorGraphStateV1:
    del services
    updated = _advance_node(validate_tutor_state(state))
    updated["phase"] = "acknowledge"
    return updated


def learner_control_check(
    state: TutorGraphStateV1, *, services: TutorGraphServices
) -> TutorGraphStateV1:
    del services
    updated = _advance_node(validate_tutor_state(state))
    updated["phase"] = "acknowledge"
    updated.pop("learner_answer", None)
    return updated


def acknowledge(
    state: TutorGraphStateV1, *, services: TutorGraphServices
) -> TutorGraphStateV1:
    del services
    updated = _advance_node(validate_tutor_state(state))
    answer = updated.pop("learner_answer", None)
    action = classify_learner_control(updated["branch"], answer)
    updated["learner_evidence"] = [
        *updated["learner_evidence"],
        {"kind": "control", "action": action},
    ][-2:]
    if action == "continue":
        updated["phase"] = "terminal"
    elif action == "explain_again":
        updated["phase"] = "remediate"
        updated["branch"] = "check_2"
        updated["remediation_count"] = 1
    else:
        updated["phase"] = "acknowledge"
    return validate_tutor_state(updated)


def remediate_once(
    state: TutorGraphStateV1, *, services: TutorGraphServices
) -> TutorGraphStateV1:
    updated = _advance_node(validate_tutor_state(state))
    if updated["remediation_count"] != 1 or updated["branch"] != "check_2":
        raise TutorContractError("remediation is not available")
    markdown = services.generate(updated, purpose="remediate")
    updated["latest_output"] = {"kind": "feedback", "markdown": markdown}
    updated["turns"] = [
        *updated["turns"],
        {"kind": "feedback", "markdown": markdown},
    ][-2:]
    updated["phase"] = "handoff"
    return validate_tutor_state(updated)


def complete(
    state: TutorGraphStateV1, *, services: TutorGraphServices
) -> TutorGraphStateV1:
    del services
    updated = _advance_node(validate_tutor_state(state))
    updated["phase"] = "terminal"
    updated["terminal"] = {
        "outcome": "completed",
        "completion_basis": "participation_only",
    }
    return validate_tutor_state(updated)


def route_entry(state: TutorGraphStateV1) -> str:
    phase = validate_tutor_state(state)["phase"]
    return {
        "start": "validate_context",
        "explain": "explain_bounded_unit",
        "handoff": "handoff_to_learner",
        "acknowledge": "acknowledge",
        "remediate": "remediate_once",
        "terminal": "complete",
    }[phase]


def route_after_acknowledge(state: TutorGraphStateV1) -> str:
    phase = validate_tutor_state(state)["phase"]
    if phase == "terminal":
        return "complete"
    if phase == "remediate":
        return "remediate_once"
    return "learner_control_check"


__all__ = [
    "acknowledge",
    "complete",
    "explain_bounded_unit",
    "handoff_to_learner",
    "learner_control_check",
    "remediate_once",
    "route_after_acknowledge",
    "route_entry",
    "validate_context",
]
