# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Phase 3.5 graph engine: stable ``GraphEngine.run_turn()`` adapter.

Converts graph output back to the exact legacy ``LegacyRunResult``
dictionary shape.
"""

from __future__ import annotations

from typing import Any

from agent.graph_engine.contracts import LegacyRunResult
from agent.graph_engine.ports import GraphServices


class GraphEngine:
    """Compiled LangGraph agent turn runner.

    One instance per process; ``run_turn()`` is called once per user message.
    The compiled graph is stateless (no checkpointer).

    LangGraph is imported lazily so that contracts, ports, and nodes can be
    imported and tested without a langgraph installation.
    """

    def __init__(self) -> None:
        # Lazy import: builder is the only file that imports langgraph.
        from agent.graph_engine.builder import build_agent_graph
        self._graph = build_agent_graph()

    def run_turn(
        self,
        services: GraphServices,
        user_message: Any,
        system_message: str | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
        task_id: str | None = None,
        stream_callback: Any = None,
        persist_user_message: str | None = None,
    ) -> LegacyRunResult:
        """Execute one complete agent turn through the compiled graph.

        Args:
            services: Adapter implementing ``GraphServices`` for this turn.
            user_message: The user's message.
            system_message: Optional custom system prompt.
            conversation_history: Previous conversation messages.
            task_id: Unique task identifier.
            stream_callback: Optional streaming delta callback.
            persist_user_message: Optional clean message for transcripts.

        Returns:
            The exact ``LegacyRunResult`` dictionary frozen by Task 2.
        """
        # LangGraph's recursion limit is only a safety ceiling — Hermes
        # ``iteration_budget`` is the user-visible authority (enforced in the
        # prepare_request node).  Size it from ``max_iterations`` with generous
        # headroom for retry/compression sub-steps within each iteration.
        # NOTE: treat this formula as an initial ceiling validated by the
        # super-step measurement in test_graph_budget_parity.py, not a proved
        # constant; revise from evidence if that test loses its 20% headroom.
        max_iterations = getattr(
            getattr(services, "_agent", None), "max_iterations", 90
        ) or 90
        recursion_limit = max(1000, (max_iterations * 12) + 100)

        config: dict[str, Any] = {
            "recursion_limit": recursion_limit,
            "configurable": {
                "services": services,
                "stream_callback": stream_callback,
                "persist_user_message": persist_user_message,
            },
        }

        initial_state: dict[str, Any] = {
            "user_message": user_message,
            "system_message": system_message,
            "conversation_history": conversation_history,
            "messages": [],
            "effective_task_id": task_id or "",
            "api_call_count": 0,
            "retry_count": 0,
            "compression_attempts": 0,
            "iteration_budget_remaining": 0,
            "fallback_index": 0,
            "route": "prepare_request",
        }

        final_state = self._graph.invoke(initial_state, config)

        # Extract the exact legacy result from final state
        result: LegacyRunResult = final_state.get("result", {})
        return result
