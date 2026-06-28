# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Phase 3.5 graph engine: serializable state, result, route, and exit-policy types.

No LangGraph imports. These types are engine-neutral and represent the exact
legacy ``AIAgent.run_conversation`` return contract frozen in Task 2.

NOTE: Do NOT add ``from __future__ import annotations`` here.
TypedDict needs live (non-string) annotations so that ``NotRequired``
fields are correctly placed in ``__optional_keys__`` on Python 3.11.
"""

from typing import Any, Literal, NotRequired, TypedDict

# ── Public result dictionary (exact legacy shape) ────────────────────────

class LegacyRunResult(TypedDict, total=False):
    """Exact shape of the dictionary returned by ``AIAgent.run_conversation``.

    Keys with ``total=False`` are optional and their **absence** is part of the
    frozen contract.  Adding a missing key with ``None`` is an observable
    behaviour change.
    """
    final_response: str | None
    messages: list[dict[str, Any]]
    api_calls: int
    completed: bool
    partial: bool
    interrupted: bool
    failed: bool
    error: str
    compression_exhausted: bool


# ── Graph routing ────────────────────────────────────────────────────────

Route = Literal[
    "prepare_request",
    "call_transport",
    "process_response",
    "handle_transport_error",
    "dispatch_tools",
    "apply_steer",
    "summarize_on_budget",
    "finish",
]


# ── Side-effect policy per exit ──────────────────────────────────────────

class ExitPolicy(TypedDict):
    """Which side effects to perform when a turn finishes.

    Each exit path produces exactly one policy; the graph engine applies it
    without adding or suppressing individual effects.
    """
    cleanup_task_resources: bool
    persist_session: bool
    save_trajectory: bool
    fire_post_llm_call: bool
    fire_on_session_end: bool
    clear_interrupt: bool


# ── Per-turn state that flows through graph nodes ────────────────────────

class TurnState(TypedDict):
    """Serializable state carried through every graph node.

    Callbacks, clients, plugin managers, DB handles, and the ``AIAgent``
    instance itself must **not** be fields of ``TurnState``.  They travel
    through the LangGraph ``Runtime`` context instead.
    """
    user_message: Any
    system_message: str | None
    conversation_history: list[dict[str, Any]] | None
    messages: list[dict[str, Any]]
    effective_task_id: str
    api_call_count: int
    retry_count: int
    compression_attempts: int
    iteration_budget_remaining: int
    fallback_index: int
    route: Route
    result: NotRequired[LegacyRunResult]
    exit_policy: NotRequired[ExitPolicy]
