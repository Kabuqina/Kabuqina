"""``PlannerSpec`` — a declarative planner strategy (design §5, §15).

A PlannerSpec *declares* how a planner participates in the pipeline. It does
**not** execute tools, own a retry loop, or replace ``AIAgent`` — if a field
does not drive activation, prompt, accepted contract, allowed output kinds, or
review policy, it does not belong here.

Two planners exist in M1: the Deliverable Planner (delegates to the existing
file-generation prompt) and the Learning Planner (stub). Both are registered in
``planner_registry``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class PlannerSpec:
    """Immutable declaration of a planner strategy."""

    planner_id: str
    domain: str
    activation: Callable[[Any], bool]
    prompt_builder: Callable[..., str]
    accepted_context: str
    allowed_kinds: frozenset = field(default_factory=frozenset)
    review_policy: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )

    # ── declarative helpers (no execution) ─────────────────────────────── #

    def is_active(self, context: Any) -> bool:
        """Whether this planner applies for the given activation context."""
        return bool(self.activation(context))

    def build_prompt(self, *args: Any, **kwargs: Any) -> str:
        """Delegate to the declared prompt builder — byte-for-byte."""
        return self.prompt_builder(*args, **kwargs)

    def allows_kind(self, kind: str) -> bool:
        """Whether this planner may produce the given artifact kind."""
        return kind in self.allowed_kinds

    def review_mode_for(self, kind: str) -> str:
        """Declared review mode for a produced kind (``deterministic`` /
        ``semantic``). Raises :class:`KeyError` for a kind this planner does not
        produce."""
        return self.review_policy[kind]
