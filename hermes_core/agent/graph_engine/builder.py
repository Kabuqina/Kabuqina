# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Phase 3.5 graph engine: **the only production file that imports langgraph**.

Wraps the pure node functions from ``nodes.py``, adds conditional edges
based on ``state["route"]``, and compiles without a checkpointer.

No LangChain, langgraph-prebuilt, LangSmith, or checkpoint imports.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from agent.graph_engine import nodes


def _route(state: dict[str, Any]) -> str:
    """Shared routing function: follows ``state["route"]``."""
    return state["route"]


def build_agent_graph() -> StateGraph:
    """Construct and compile the agent turn graph without a checkpointer.

    Returns a compiled graph ready for ``.ainvoke()`` / ``.invoke()``.
    The caller must supply a ``config`` dict with ``configurable.services``
    containing the ``GraphServices`` adapter.
    """
    graph = StateGraph(dict)

    # -- nodes -----------------------------------------------------------
    graph.add_node("initialize_turn", nodes.initialize_turn)
    graph.add_node("prepare_request", nodes.prepare_request)
    graph.add_node("call_transport", nodes.call_transport)
    graph.add_node("process_response", nodes.process_response)
    graph.add_node("handle_transport_error", nodes.handle_transport_error)
    graph.add_node("dispatch_tools", nodes.dispatch_tools)
    graph.add_node("apply_steer", nodes.apply_steer)
    graph.add_node("summarize_on_budget", nodes.summarize_on_budget)
    graph.add_node("finish", nodes.finish)

    # -- edges -----------------------------------------------------------
    graph.add_edge(START, "initialize_turn")
    graph.add_edge("initialize_turn", "prepare_request")

    # prepare → call or error or finish (route set by prepare_request)
    graph.add_conditional_edges(
        "prepare_request", _route,
        {"call_transport": "call_transport",
         "handle_transport_error": "handle_transport_error",
         "finish": "finish"},
    )

    # transport → process or error or finish
    graph.add_conditional_edges(
        "call_transport", _route,
        {"process_response": "process_response",
         "handle_transport_error": "handle_transport_error",
         "finish": "finish"},
    )

    # process → tools, steer, budget, finish, or loop back to prepare
    graph.add_conditional_edges(
        "process_response", _route,
        {"prepare_request": "prepare_request",
         "dispatch_tools": "dispatch_tools",
         "apply_steer": "apply_steer",
         "summarize_on_budget": "summarize_on_budget",
         "finish": "finish"},
    )

    # tools → steer or prepare or budget or finish
    graph.add_conditional_edges(
        "dispatch_tools", _route,
        {"apply_steer": "apply_steer",
         "prepare_request": "prepare_request",
         "summarize_on_budget": "summarize_on_budget",
         "finish": "finish"},
    )

    # steer → prepare or budget or finish
    graph.add_conditional_edges(
        "apply_steer", _route,
        {"prepare_request": "prepare_request",
         "summarize_on_budget": "summarize_on_budget",
         "finish": "finish"},
    )

    # budget → finish
    graph.add_edge("summarize_on_budget", "finish")

    # error → prepare (retry) or finish (abort)
    graph.add_conditional_edges(
        "handle_transport_error", _route,
        {"prepare_request": "prepare_request",
         "finish": "finish"},
    )

    # finish → END
    graph.add_edge("finish", END)

    # Compile without a checkpointer (decision 3 in the plan).
    return graph.compile()
