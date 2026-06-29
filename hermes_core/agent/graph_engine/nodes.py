# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Phase 3.5 graph engine: pure node functions.

Each function corresponds to exactly one ``GraphServices`` method and
delegates through an engine-neutral runtime context dictionary.

No LangGraph imports.
"""

from typing import Any

from agent.graph_engine.contracts import TurnState
from agent.graph_engine.ports import GraphRuntimeContext, GraphServices


def _services(context: GraphRuntimeContext) -> GraphServices:
    """Extract the service adapter from the explicit runtime context."""
    if context is None:
        raise RuntimeError("GraphServices not available in runtime context")
    return context["services"]


# ── Initialisation ───────────────────────────────────────────────────────

def initialize_turn(
    state: TurnState, *, context: GraphRuntimeContext
) -> dict[str, Any]:
    """Bootstrap a fresh agent turn."""
    svc = _services(context)
    return svc.initialize_turn(
        state,
        user_message=state.get("user_message"),
        system_message=state.get("system_message"),
        conversation_history=state.get("conversation_history"),
        task_id=state.get("effective_task_id"),
        stream_callback=context["stream_callback"],
        persist_user_message=context["persist_user_message"],
    )


# ── Request / response ───────────────────────────────────────────────────

def prepare_request(
    state: TurnState, *, context: GraphRuntimeContext
) -> dict[str, Any]:
    return _services(context).prepare_request(state)


def call_transport(
    state: TurnState, *, context: GraphRuntimeContext
) -> dict[str, Any]:
    return _services(context).call_transport(state)


def process_response(
    state: TurnState, *, context: GraphRuntimeContext
) -> dict[str, Any]:
    return _services(context).process_response(state)


def handle_transport_error(
    state: TurnState, *, context: GraphRuntimeContext
) -> dict[str, Any]:
    return _services(context).handle_transport_error(state)


# ── Tool / steer ─────────────────────────────────────────────────────────

def dispatch_tools(
    state: TurnState, *, context: GraphRuntimeContext
) -> dict[str, Any]:
    return _services(context).dispatch_tools(state)


def apply_steer(
    state: TurnState, *, context: GraphRuntimeContext
) -> dict[str, Any]:
    return _services(context).apply_steer(state)


# ── Budget ───────────────────────────────────────────────────────────────

def summarize_on_budget(
    state: TurnState, *, context: GraphRuntimeContext
) -> dict[str, Any]:
    return _services(context).summarize_on_budget(state)


# ── Finalisation ─────────────────────────────────────────────────────────

def finish(
    state: TurnState, *, context: GraphRuntimeContext
) -> dict[str, Any]:
    return _services(context).apply_exit_policy(state)
