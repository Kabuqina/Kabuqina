"""Planner registry — the two M1 PlannerSpecs and lookup helpers.

- **Deliverable Planner**: delegates its prompt to the existing
  ``build_deliverable_planner_prompt`` (byte-identical) and its activation to
  ``deliverable_planner_is_active``. It produces files, not learning artifacts,
  so it declares no learning kinds.
- **Learning Planner** (M1 stub): activates on a Learning Index snapshot,
  accepts the ``LearningIndex`` contract, may produce every learning ``kind``,
  and carries the per-kind review policy from the contract. Its prompt builder
  is intentionally minimal in M1.

All ids/kinds/review modes are referenced from their single sources
(``prompt_builder``, ``learning_contract``) — nothing is duplicated here.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Dict, Optional, Tuple

from agent.prompt_builder import (
    build_deliverable_planner_prompt,
    deliverable_planner_is_active,
)
from learning.learning_contract import DEFAULT_REVIEW_MODE, KINDS
from learning.planner_spec import PlannerSpec

DELIVERABLE_PLANNER_ID = "deliverable"
LEARNING_PLANNER_ID = "learning"


def learning_planner_is_active(learning_index: Any) -> bool:
    """Active once a Learning Index snapshot exists for the current space."""
    return isinstance(learning_index, dict) and learning_index.get("index_version") is not None


def build_learning_planner_prompt(learning_index: Optional[Dict[str, Any]] = None) -> str:
    """Minimal M1 Learning Planner guidance, self-gated on an active index.

    Returns ``""`` when no index is present (mirrors the Deliverable Planner's
    self-gating). The full learning planning prompt lands in a later milestone.
    """
    if not learning_planner_is_active(learning_index):
        return ""
    return (
        "# Learning planning\n"
        "Plan learning artifacts from the Learning Index for the current course "
        "space. Read the index (active artifacts + activities) before planning; "
        "propose typed learning outputs (see allowed kinds) as drafts for review "
        "— never treat unreviewed content as course fact, and never invent "
        "results the index did not contain.\n"
        "For learning_plan tasks, set mode to learn, practice, or review so the "
        "desk opens the intended Study page. When a task belongs to a real source "
        "outline node, preserve that node's id in outline_node_id; do not invent an "
        "id or expand knowledge cores into a fourth directory level.\n"
        "When the learner imports two or more materials together, use "
        "learning_material_alignment_propose after reading their real extracted "
        "structures. First decide whether they belong to one course or several; "
        "for each proposed course nominate one real material as the directory "
        "skeleton and explain why, map other section/page ranges only onto section "
        "ids that actually exist in that skeleton, assign each material an "
        "explanation/practice/assessment/reference role with a reason, and list "
        "anything that does not align. Never synthesize a topic tree, hide an "
        "unaligned material, calculate coverage, or activate the draft yourself. "
        "For a single imported material, keep the existing single-material flow."
    )


DELIVERABLE_PLANNER_SPEC = PlannerSpec(
    planner_id=DELIVERABLE_PLANNER_ID,
    domain="deliverable",
    activation=deliverable_planner_is_active,
    prompt_builder=build_deliverable_planner_prompt,
    accepted_context="valid_tool_names",
    allowed_kinds=frozenset(),  # produces files, not learning artifacts
    review_policy=MappingProxyType({}),
)

LEARNING_PLANNER_SPEC = PlannerSpec(
    planner_id=LEARNING_PLANNER_ID,
    domain="learning",
    activation=learning_planner_is_active,
    prompt_builder=build_learning_planner_prompt,
    accepted_context="LearningIndex",
    allowed_kinds=KINDS,
    review_policy=MappingProxyType(dict(DEFAULT_REVIEW_MODE)),
)


_REGISTRY: Dict[str, PlannerSpec] = {
    spec.planner_id: spec
    for spec in (DELIVERABLE_PLANNER_SPEC, LEARNING_PLANNER_SPEC)
}


def get_planner(planner_id: str) -> PlannerSpec:
    """Return the PlannerSpec for ``planner_id`` or raise ``KeyError``."""
    return _REGISTRY[planner_id]


def list_planners() -> Tuple[PlannerSpec, ...]:
    return tuple(_REGISTRY.values())


def planner_ids() -> frozenset:
    return frozenset(_REGISTRY)
