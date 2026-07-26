# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Stable adapter for running one Tutor start/resume segment.

Lifecycle persistence and provider budgeting are wired in the next B03 task;
this adapter already keeps the compiled graph stateless and independent from
the ordinary Agent ``GraphEngine``.
"""

from __future__ import annotations

from agent.graph_engine.tutor_contracts import (
    TutorGraphStateV1,
    validate_tutor_state,
)
from agent.graph_engine.tutor_ports import TutorGraphRuntimeContext, TutorGraphServices


class TutorGraphEngine:
    def __init__(self) -> None:
        from agent.graph_engine.tutor_builder import build_tutor_graph

        self._graph = build_tutor_graph()

    def run_segment(
        self, state: TutorGraphStateV1, services: TutorGraphServices
    ) -> TutorGraphStateV1:
        context: TutorGraphRuntimeContext = {"services": services}
        result = self._graph.invoke(
            validate_tutor_state(state),
            {"recursion_limit": 32},
            context=context,
        )
        return validate_tutor_state(result)


__all__ = ["TutorGraphEngine"]

