# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Phase 3.5 graph engine — LangGraph-based agent turn runner.

Export only ``GraphEngine`` and stable contracts.  No LangChain or
LangSmith imports.
"""

from agent.graph_engine.engine import GraphEngine

__all__ = ["GraphEngine"]
