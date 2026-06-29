# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Phase 3.5 Task 8a: budget parity — iteration-budget consumption, the
max-iteration toolless summary, and the LangGraph recursion ceiling.

The compression and truncation/continuation exit families (Task 8b / 8c) are
not yet routed through the graph; this module covers the budget third of
"compression, truncation, and budget parity" and closes DECISIONS.md
PH35-FU-006 (the previously dead ``apply_steer`` budget gate).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

from tests.run_agent.test_graph_protocol_parity import _replay_graph


GOLDEN_DIR = Path(__file__).parent / "golden"

NODE_METHODS = (
    "initialize_turn",
    "prepare_request",
    "call_transport",
    "process_response",
    "handle_transport_error",
    "dispatch_tools",
    "apply_steer",
    "summarize_on_budget",
    "apply_exit_policy",
)


def _load(name: str) -> Dict[str, Any]:
    return json.loads((GOLDEN_DIR / f"{name}.json").read_text(encoding="utf-8"))


# ── Max-iteration toolless summary ───────────────────────────────────────


def test_graph_max_iterations_summary():
    """Hitting ``max_iterations`` produces a toolless summary, no extra call.

    ``max_iterations.json`` scripts a single tool-call turn with
    ``max_iterations=1`` and a ``summary_response``.  The fixture only succeeds
    if the budget gate fires: without it the graph would request a second model
    turn and the scripted transport (1 turn) would raise.  Parity with the
    loop's post-loop ``_handle_max_iterations`` (run_agent.py:12493).
    """
    spec = _load("max_iterations")
    snapshot = _replay_graph(spec)
    expected = spec["expected"]

    assert snapshot["result"]["completed"] is False
    assert snapshot["result"]["api_calls"] == expected["result"]["api_calls"] == 1
    assert snapshot["model_turns_consumed"] == expected["model_turns_consumed"] == 1
    assert snapshot["result"]["final_response"] == expected["result"]["final_response"]


# ── Iteration budget is actually consumed (closes PH35-FU-006) ───────────


def test_graph_consumes_iteration_budget():
    """Each fresh model turn consumes one iteration-budget unit.

    Proves the budget is no longer a dead gate: a two-turn tool conversation
    (single_tool) leaves ``iteration_budget.used == 2``.
    """
    import run_agent
    from tests.run_agent.golden_harness import (
        GOLDEN_SESSION_ID,
        GOLDEN_TASK_ID,
        _ScriptedTransport,
        _ToolStub,
        _chat_response,
        _patches,
        _ScriptedClock,
    )

    spec = _load("single_tool")
    cfg = spec.get("agent", {})
    api_mode = cfg.get("api_mode", "chat_completions")
    model = cfg.get("model", "golden/test-model")
    transport = _ScriptedTransport(spec.get("model_turns", []), _chat_response, model)

    with _patches(spec.get("tools", []), _ToolStub(spec.get("tool_results", {})), api_mode):
        agent = run_agent.AIAgent(
            api_key="golden-key",
            base_url=cfg.get("base_url", "https://api.openai.com/v1"),
            provider=cfg.get("provider", "openrouter"),
            api_mode=api_mode,
            model=model,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
        agent.session_id = GOLDEN_SESSION_ID
        agent._disable_streaming = True
        agent._session_db = MagicMock()
        agent._save_session_log = lambda *a, **k: None
        agent._save_trajectory = lambda *a, **k: None
        transport.agent = agent
        agent._interruptible_api_call = transport
        agent._interruptible_streaming_api_call = transport

        clock = _ScriptedClock()
        with (
            patch.object(run_agent.time, "time", clock.time),
            patch.object(run_agent.time, "sleep", clock.sleep),
            patch.object(run_agent, "jittered_backoff", lambda *a, **k: 0.1),
        ):
            result = agent._run_conversation_graph(
                spec["user_message"], task_id=GOLDEN_TASK_ID
            )

    assert result["completed"] is True
    assert result["api_calls"] == 2
    # Two model turns ⇒ two budget units consumed (was 0 before the fix).
    assert agent.iteration_budget.used == 2


# ── Recursion ceiling ────────────────────────────────────────────────────


def _count_supersteps(spec: Dict[str, Any]) -> int:
    """Replay a fixture through the graph, counting node invocations.

    Each node execution is ~one LangGraph super-step in this linear graph.
    """
    import run_agent

    counter = {"n": 0}
    originals = {name: getattr(run_agent._GraphServicesAdapter, name) for name in NODE_METHODS}

    def _make(orig):
        def _wrapper(self, *a, **k):
            counter["n"] += 1
            return orig(self, *a, **k)
        return _wrapper

    for name, orig in originals.items():
        setattr(run_agent._GraphServicesAdapter, name, _make(orig))
    try:
        _replay_graph(spec)
    finally:
        for name, orig in originals.items():
            setattr(run_agent._GraphServicesAdapter, name, orig)
    return counter["n"]


def test_recursion_limit_has_headroom_for_routed_fixtures():
    """The configured recursion limit clears the routed worst cases with margin.

    NOTE: the *full* worst case (compression × continuation × retry) cannot be
    measured until Task 8b/8c route those families; this asserts headroom for
    the fixtures that route today (budget summary + a 3-retry transport loop)
    and pins the formula value.  Revisit the 20%-headroom requirement and the
    formula in Task 8c once the multiplying paths exist (see PH35-FU-006).
    """
    # Formula mirrored from engine.run_turn.
    def _limit(max_iters: int) -> int:
        return max(1000, (max_iters * 12) + 100)

    assert _limit(1) == 1000
    assert _limit(90) == 1180

    for fixture in ("max_iterations", "exit_api_retries"):
        spec = _load(fixture)
        steps = _count_supersteps(spec)
        max_iters = spec.get("agent", {}).get("max_iterations", 90)
        limit = _limit(max_iters)
        assert steps <= 0.8 * limit, (
            f"{fixture}: {steps} super-steps exceeds 80% of recursion_limit {limit}"
        )
