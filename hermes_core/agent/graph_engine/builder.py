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
from langgraph.runtime import Runtime

from agent.graph_engine import nodes
from agent.graph_engine.contracts import TurnState
from agent.graph_engine.ports import GraphRuntimeContext


def _route(state: dict[str, Any]) -> str:
    """Shared routing function: follows ``state["route"]``."""
    return state["route"]


def _with_runtime(node):
    """Adapt an engine-neutral node to LangGraph's Runtime signature."""
    def wrapped(
        state: TurnState, runtime: Runtime[GraphRuntimeContext]
    ) -> dict[str, Any]:
        if runtime.context is None:
            raise RuntimeError("Graph runtime context is required")
        return node(state, context=runtime.context)

    return wrapped


def build_agent_graph() -> StateGraph:
    """Construct and compile the agent turn graph without a checkpointer.

    Returns a compiled graph ready for ``.ainvoke()`` / ``.invoke()``.
    The caller supplies ``GraphRuntimeContext`` through ``invoke(context=...)``.
    """
    graph = StateGraph(TurnState, context_schema=GraphRuntimeContext)

    # -- nodes -----------------------------------------------------------
    graph.add_node("initialize_turn", _with_runtime(nodes.initialize_turn))
    graph.add_node("prepare_request", _with_runtime(nodes.prepare_request))
    graph.add_node("call_transport", _with_runtime(nodes.call_transport))
    graph.add_node("process_response", _with_runtime(nodes.process_response))
    graph.add_node(
        "handle_transport_error", _with_runtime(nodes.handle_transport_error)
    )
    graph.add_node("dispatch_tools", _with_runtime(nodes.dispatch_tools))
    graph.add_node("apply_steer", _with_runtime(nodes.apply_steer))
    graph.add_node(
        "summarize_on_budget", _with_runtime(nodes.summarize_on_budget)
    )
    graph.add_node("finish", _with_runtime(nodes.finish))

    # -- edges -----------------------------------------------------------
    graph.add_edge(START, "initialize_turn")
    graph.add_edge("initialize_turn", "prepare_request")

    # prepare → call, budget summary, error, or finish (route set by prepare_request)
    graph.add_conditional_edges(
        "prepare_request", _route,
        {"call_transport": "call_transport",
         "summarize_on_budget": "summarize_on_budget",
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
