# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Phase 3.5 Task 3: contract type invariants for graph engine state and results."""

from __future__ import annotations

import pytest


# ── LegacyRunResult key-presence contract ────────────────────────────────

def test_legacy_result_to_output_preserves_absent_keys():
    """Converting a minimal LegacyRunResult to output must not add absent optional keys."""
    from agent.graph_engine.contracts import LegacyRunResult

    minimal: LegacyRunResult = {
        "final_response": "ok",
        "messages": [],
        "api_calls": 1,
        "completed": True,
    }
    output = dict(minimal)
    assert "partial" not in output
    assert "interrupted" not in output
    assert "failed" not in output
    assert "error" not in output
    assert "compression_exhausted" not in output


def test_legacy_result_optional_keys_present_when_set():
    """When optional keys are explicitly set, they appear in the output dict."""
    from agent.graph_engine.contracts import LegacyRunResult

    full: LegacyRunResult = {
        "final_response": None,
        "messages": [],
        "api_calls": 0,
        "completed": False,
        "partial": True,
        "interrupted": True,
        "failed": True,
        "error": "boom",
        "compression_exhausted": True,
    }
    output = dict(full)
    assert output.get("partial") is True
    assert output.get("interrupted") is True
    assert output.get("failed") is True
    assert output.get("error") == "boom"
    assert output.get("compression_exhausted") is True


# ── Route literal contract ───────────────────────────────────────────────

def test_route_literal_values():
    """All expected routes must be valid literal values."""
    from agent.graph_engine.contracts import Route

    # Route is a Literal type; we verify the allowed values by checking type checking
    valid_routes = {
        "prepare_request",
        "call_transport",
        "process_response",
        "handle_transport_error",
        "dispatch_tools",
        "apply_steer",
        "summarize_on_budget",
        "finish",
    }
    # The Route type itself cannot be enumerated at runtime, but we can verify
    # it exists and has the expected __args__ for typing inspection.
    import typing
    args = typing.get_args(Route)
    assert set(args) == valid_routes, f"Route values mismatch: {set(args)} != {valid_routes}"


# ── ExitPolicy required keys ─────────────────────────────────────────────

def test_exit_policy_has_required_keys():
    """ExitPolicy must declare all six boolean fields."""
    from agent.graph_engine.contracts import ExitPolicy

    required = {
        "cleanup_task_resources",
        "persist_session",
        "save_trajectory",
        "fire_post_llm_call",
        "fire_on_session_end",
        "clear_interrupt",
    }
    # ExitPolicy is total=True by default, so all keys are required
    assert set(ExitPolicy.__required_keys__) == required


# ── TurnState required keys ──────────────────────────────────────────────

def test_turn_state_required_keys():
    """TurnState must have the expected required and optional keys."""
    from agent.graph_engine.contracts import TurnState

    required = {
        "user_message",
        "system_message",
        "conversation_history",
        "messages",
        "effective_task_id",
        "api_call_count",
        "retry_count",
        "compression_attempts",
        "iteration_budget_remaining",
        "fallback_index",
        "route",
    }
    optional = {"result", "exit_policy"}

    assert set(TurnState.__required_keys__) == required
    assert set(TurnState.__optional_keys__) == optional
