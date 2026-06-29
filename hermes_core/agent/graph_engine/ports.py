# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Phase 3.5 graph engine: service port protocol.

Every node function delegates through this protocol so the graph builder
never touches ``AIAgent`` internals directly.  The adapter that implements
this protocol lives in ``run_agent.py`` (Task 4).

No LangGraph imports.
"""

from __future__ import annotations

from typing import Any, Protocol, TypedDict

from agent.graph_engine.contracts import TurnState


class GraphServices(Protocol):
    """Named service methods called by pure graph nodes.

    Each method accepts the current ``TurnState`` and returns a **partial**
    state update dictionary.  Mutable per-turn state on ``AIAgent`` (e.g.
    provider, base URL) is copied into the returned update by the adapter
    before the next node consumes it.
    """

    def initialize_turn(
        self, state: TurnState, user_message: Any,
        system_message: str | None, conversation_history: list[dict[str, Any]] | None,
        task_id: str | None, stream_callback: Any, persist_user_message: str | None,
    ) -> dict[str, Any]:
        """Set up a fresh turn: assign task id, fire ``on_session_start``,
        apply system prompt, and return initial ``TurnState`` fields."""
        ...

    def prepare_request(self, state: TurnState) -> dict[str, Any]:
        """Build the API request payload, fire ``pre_llm_call``, and return
        route + any updated counters."""
        ...

    def call_transport(self, state: TurnState) -> dict[str, Any]:
        """Invoke the provider transport (chat-completions or anthropic-messages)
        and return serializable routing/counter updates. Live responses remain
        on the runtime adapter for ``process_response`` to consume."""
        ...

    def process_response(self, state: TurnState) -> dict[str, Any]:
        """Validate, truncate, and finish a successful transport response."""
        ...

    def handle_transport_error(self, state: TurnState) -> dict[str, Any]:
        """Classify, retry, fallback, or abort after a transport failure."""
        ...

    def dispatch_tools(self, state: TurnState) -> dict[str, Any]:
        """Execute tool calls and append tool-result messages."""
        ...

    def apply_steer(self, state: TurnState) -> dict[str, Any]:
        """Drain pending user steer and append to messages."""
        ...

    def summarize_on_budget(self, state: TurnState) -> dict[str, Any]:
        """Produce a budget-exhaustion summary via a toolless model call."""
        ...

    def apply_exit_policy(self, state: TurnState) -> dict[str, Any]:
        """Execute side effects (persistence, hooks, cleanup) according to
        the frozen ``ExitPolicy``, then return the final ``LegacyRunResult``."""
        ...


class GraphRuntimeContext(TypedDict):
    """Non-serializable collaborators supplied through LangGraph Runtime."""

    services: GraphServices
    stream_callback: Any
    persist_user_message: str | None
