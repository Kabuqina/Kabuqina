# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Build the independent L-2 Tutor graph without a checkpointer.

This is the only Tutor production module that imports LangGraph.  Durable
checkpointing remains explicit through ``TutorGraphServices.after_node`` and
the B02 runtime store.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from agent.graph_engine import tutor_nodes as nodes
from agent.graph_engine.tutor_contracts import TutorGraphStateV1
from agent.graph_engine.tutor_ports import TutorGraphRuntimeContext


def _with_runtime(name: str, node):
    def wrapped(
        state: TutorGraphStateV1, runtime: Runtime[TutorGraphRuntimeContext]
    ) -> dict[str, Any]:
        if runtime.context is None:
            raise RuntimeError("Tutor graph runtime context is required")
        services = runtime.context["services"]
        updated = node(state, services=services)
        return services.after_node(name, updated)

    return wrapped


def build_tutor_graph() -> StateGraph:
    graph = StateGraph(TutorGraphStateV1, context_schema=TutorGraphRuntimeContext)
    graph.add_node(
        "validate_context", _with_runtime("validate_context", nodes.validate_context)
    )
    graph.add_node(
        "explain_bounded_unit",
        _with_runtime("explain_bounded_unit", nodes.explain_bounded_unit),
    )
    graph.add_node(
        "handoff_to_learner",
        _with_runtime("handoff_to_learner", nodes.handoff_to_learner),
    )
    graph.add_node(
        "learner_control_check",
        _with_runtime("learner_control_check", nodes.learner_control_check),
    )
    graph.add_node("acknowledge", _with_runtime("acknowledge", nodes.acknowledge))
    graph.add_node(
        "remediate_once", _with_runtime("remediate_once", nodes.remediate_once)
    )
    graph.add_node("complete", _with_runtime("complete", nodes.complete))

    graph.add_conditional_edges(
        START,
        nodes.route_entry,
        {
            "validate_context": "validate_context",
            "explain_bounded_unit": "explain_bounded_unit",
            "handoff_to_learner": "handoff_to_learner",
            "acknowledge": "acknowledge",
            "remediate_once": "remediate_once",
            "complete": "complete",
        },
    )
    graph.add_edge("validate_context", "explain_bounded_unit")
    graph.add_edge("explain_bounded_unit", "handoff_to_learner")
    graph.add_edge("handoff_to_learner", "learner_control_check")
    graph.add_edge("learner_control_check", END)
    graph.add_conditional_edges(
        "acknowledge",
        nodes.route_after_acknowledge,
        {
            "complete": "complete",
            "remediate_once": "remediate_once",
            "learner_control_check": "learner_control_check",
        },
    )
    graph.add_edge("remediate_once", "handoff_to_learner")
    graph.add_edge("complete", END)
    return graph.compile()


__all__ = ["build_tutor_graph"]

