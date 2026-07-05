"""Tests for the Planner strategy framework (learning/planner_spec.py) and
registry (learning/planner_registry.py).

The linchpin invariant: the Deliverable Planner prompt produced *through the new
PlannerSpec* is byte-identical to today's ``build_deliverable_planner_prompt``.
That is the guarantee that existing PPT/PDF/HTML/DOCX planning behaviour is
unchanged. The rest pins the declarative surface: activation, allowed kinds, and
review policy — a PlannerSpec declares, it does not execute.
"""

import pytest

from agent.prompt_builder import (
    build_deliverable_planner_prompt,
    deliverable_planner_is_active,
)
from tools.deliverable_contract import DELIVERABLE_WRITER_TOOLS
from learning.learning_contract import KINDS, DEFAULT_REVIEW_MODE
from learning.planner_spec import PlannerSpec
from learning.planner_registry import (
    DELIVERABLE_PLANNER_ID,
    LEARNING_PLANNER_ID,
    build_learning_planner_prompt,
    get_planner,
    list_planners,
    planner_ids,
)


# --------------------------------------------------------------------------- #
# CRITICAL: byte-identical Deliverable Planner prompt through the PlannerSpec
# --------------------------------------------------------------------------- #

_WRITERS = sorted(DELIVERABLE_WRITER_TOOLS)

EQUIVALENCE_INPUTS = [
    None,                                   # None
    set(),                                  # empty
    {"read_file"},                          # non-writer only → still empty prompt
    {_WRITERS[0], "read_file"},             # typical: one writer present
    set(DELIVERABLE_WRITER_TOOLS) | {"read_file"},  # full
]


@pytest.mark.parametrize("names", EQUIVALENCE_INPUTS)
def test_deliverable_prompt_is_byte_identical_through_spec(names):
    spec = get_planner(DELIVERABLE_PLANNER_ID)
    assert spec.build_prompt(names) == build_deliverable_planner_prompt(names)


# --------------------------------------------------------------------------- #
# Registry surface
# --------------------------------------------------------------------------- #

def test_registry_has_both_planners():
    assert planner_ids() == frozenset({DELIVERABLE_PLANNER_ID, LEARNING_PLANNER_ID})
    assert {s.planner_id for s in list_planners()} == planner_ids()


def test_get_unknown_planner_raises():
    with pytest.raises(KeyError):
        get_planner("no-such-planner")


def test_specs_are_frozen_declarations_not_executors():
    for spec in list_planners():
        # Declarative only — a PlannerSpec must not become a second executor.
        assert not hasattr(spec, "run")
        assert not hasattr(spec, "execute")
        with pytest.raises(Exception):
            spec.planner_id = "mutated"  # frozen


# --------------------------------------------------------------------------- #
# Deliverable spec — activation + allowed kinds
# --------------------------------------------------------------------------- #

def test_deliverable_activation_tracks_writer_presence():
    spec = get_planner(DELIVERABLE_PLANNER_ID)
    assert spec.is_active(set()) is False
    assert spec.is_active({"read_file"}) is False
    assert spec.is_active({_WRITERS[0]}) is True
    # activation delegates to the shared helper (single source, no drift)
    assert deliverable_planner_is_active({_WRITERS[0]}) is True


def test_deliverable_produces_no_learning_kinds():
    spec = get_planner(DELIVERABLE_PLANNER_ID)
    assert spec.allowed_kinds == frozenset()
    assert spec.allows_kind("flashcard_deck") is False


# --------------------------------------------------------------------------- #
# Learning spec — activation, allowed kinds, review policy, stub prompt
# --------------------------------------------------------------------------- #

def _fake_index():
    return {"index_version": 1, "space_id": "s1", "artifacts": [], "activities": []}


def test_learning_activation_requires_an_index():
    spec = get_planner(LEARNING_PLANNER_ID)
    assert spec.is_active(_fake_index()) is True
    assert spec.is_active(None) is False
    assert spec.is_active({}) is False


def test_learning_allows_every_contract_kind():
    spec = get_planner(LEARNING_PLANNER_ID)
    assert spec.allowed_kinds == KINDS
    for kind in KINDS:
        assert spec.allows_kind(kind) is True


def test_learning_review_policy_matches_contract():
    spec = get_planner(LEARNING_PLANNER_ID)
    assert dict(spec.review_policy) == DEFAULT_REVIEW_MODE
    assert spec.review_mode_for("knowledge_base") == "semantic"
    assert spec.review_mode_for("student_state") == "deterministic"


def test_learning_prompt_stub_gated_on_activation():
    spec = get_planner(LEARNING_PLANNER_ID)
    # Minimal M1 stub: non-empty guidance for an active index, empty otherwise.
    assert spec.build_prompt(_fake_index()).strip() != ""
    assert build_learning_planner_prompt(None) == ""
    assert build_learning_planner_prompt({}) == ""


def test_planner_ids_and_domains():
    d = get_planner(DELIVERABLE_PLANNER_ID)
    ell = get_planner(LEARNING_PLANNER_ID)
    assert d.planner_id == "deliverable" and d.domain == "deliverable"
    assert ell.planner_id == "learning" and ell.domain == "learning"
    assert d.accepted_context == "valid_tool_names"
    assert ell.accepted_context == "LearningIndex"
