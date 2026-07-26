# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Ports used by the independent Tutor graph.

Provider clients, stores, clocks, and persistence callbacks travel through the
LangGraph runtime context and never enter durable ``TutorGraphStateV1``.
"""

from __future__ import annotations

from typing import Any, Protocol, TypedDict, runtime_checkable

from agent.graph_engine.tutor_contracts import (
    TutorGraphStateV1,
    TutorProviderRequestV1,
    TutorProviderResult,
)
from learning.tutor_runtime_store import ProviderAttemptReservationV1


@runtime_checkable
class TutorProviderPort(Protocol):
    def execute_once(
        self,
        reservation: ProviderAttemptReservationV1,
        request: TutorProviderRequestV1,
        *,
        timeout_s: float,
    ) -> TutorProviderResult: ...


@runtime_checkable
class TutorGraphServices(Protocol):
    def generate(self, state: TutorGraphStateV1, *, purpose: str) -> str: ...

    def after_node(
        self, node_name: str, state: TutorGraphStateV1
    ) -> TutorGraphStateV1: ...


class TutorGraphRuntimeContext(TypedDict):
    services: TutorGraphServices


__all__ = [
    "TutorGraphRuntimeContext",
    "TutorGraphServices",
    "TutorProviderPort",
]

