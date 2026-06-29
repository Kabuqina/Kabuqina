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


# ── Payload-too-large (413) compression family (Task 8b) ─────────────────


def test_graph_payload_compression_exhausted():
    """413 compressed ``max_compression_attempts`` times → compression_exhausted.

    Four 413 transport turns (1 initial + 3 compression retries) with the
    compressor shrinking history each time; the fourth exhausts the budget.
    Parity with the loop's payload exit (run_agent.py:11292).
    """
    spec = _load("exit_payload_compression")
    snapshot = _replay_graph(spec)
    expected = spec["expected"]

    assert snapshot["result_keys"] == expected["result_keys"]
    assert "compression_exhausted" in snapshot["result_keys"]
    assert "final_response" not in snapshot["result_keys"]
    assert snapshot["result"]["completed"] is False
    assert snapshot["result"]["partial"] is True
    assert snapshot["result"]["api_calls"] == expected["result"]["api_calls"] == 1
    assert snapshot["model_turns_consumed"] == expected["model_turns_consumed"] == 4


def test_graph_payload_cannot_compress():
    """413 where compression cannot shrink history → immediate exhaustion.

    Parity with the loop's "cannot compress further" exit (run_agent.py:11323):
    one transport turn, no retries.
    """
    spec = _load("exit_payload_no_compression")
    snapshot = _replay_graph(spec)
    expected = spec["expected"]

    assert snapshot["result_keys"] == expected["result_keys"]
    assert "compression_exhausted" in snapshot["result_keys"]
    assert snapshot["result"]["completed"] is False
    assert snapshot["result"]["partial"] is True
    assert snapshot["result"]["api_calls"] == expected["result"]["api_calls"] == 1
    assert snapshot["model_turns_consumed"] == expected["model_turns_consumed"] == 1


# ── Context-overflow compression family (Task 8b) ────────────────────────


def _assert_compression_exhausted(fixture: str, *, turns: int):
    spec = _load(fixture)
    snapshot = _replay_graph(spec)
    expected = spec["expected"]

    assert snapshot["result_keys"] == expected["result_keys"]
    assert "compression_exhausted" in snapshot["result_keys"]
    assert "final_response" not in snapshot["result_keys"]
    assert snapshot["result"]["completed"] is False
    assert snapshot["result"]["partial"] is True
    assert snapshot["result"]["api_calls"] == expected["result"]["api_calls"] == 1
    assert snapshot["model_turns_consumed"] == expected["model_turns_consumed"] == turns


def test_graph_context_stepdown_exhausted():
    """400 context-length → step the window down + compress × 3 → exhausted.

    Parity with the loop's context step-down exit (run_agent.py:11449).
    """
    _assert_compression_exhausted("exit_context_stepdown", turns=4)


def test_graph_safe_output_context_exhausted():
    """400 max_tokens-too-large → cap output + retry × 3 → exhausted.

    Parity with the loop's safe-output exit (run_agent.py:11376).
    """
    _assert_compression_exhausted("exit_safe_output_context", turns=4)


def test_graph_context_cannot_compress():
    """400 at the minimum tier with nothing left to compress → exhaustion.

    Parity with the loop's "cannot compress further" exit (run_agent.py:11482).
    """
    _assert_compression_exhausted("exit_context_no_compression", turns=1)


# ── Preflight compression (success path, Task 8b) ────────────────────────


def test_graph_preflight_compression():
    """An over-threshold request is compressed up front, then succeeds.

    Parity with the loop's preflight compression (run_agent.py:9614): the
    middle turns are summarised before the first call, so the surviving
    history starts with the summary marker and the single model turn returns
    the answer.
    """
    spec = _load("compression")
    snapshot = _replay_graph(spec)
    expected = spec["expected"]

    assert snapshot["result"]["completed"] is True
    assert snapshot["result"]["api_calls"] == expected["result"]["api_calls"] == 1
    assert snapshot["model_turns_consumed"] == expected["model_turns_consumed"] == 1
    assert snapshot["result"]["final_response"] == expected["result"]["final_response"]
    # Compression actually ran: the surviving history opens with the summary.
    assert len(snapshot["messages"]) == len(expected["messages"])
    assert "summarized" in str(snapshot["messages"][0].get("content", ""))


# ── Truncation / continuation families (Task 8c) ─────────────────────────


def test_graph_thinking_budget_exhausted():
    """finish_reason=length with reasoning but no answer → thinking-budget exit.

    Parity with the loop (run_agent.py:10470): one turn, no continuation.
    """
    spec = _load("exit_thinking_budget")
    snapshot = _replay_graph(spec)
    expected = spec["expected"]

    assert snapshot["result_keys"] == expected["result_keys"]
    assert snapshot["result"]["completed"] is False
    assert snapshot["result"]["partial"] is True
    assert snapshot["result"]["api_calls"] == expected["result"]["api_calls"] == 1
    assert snapshot["model_turns_consumed"] == 1
    assert "Thinking Budget" in (snapshot["result"]["final_response"] or "")


def test_graph_text_continuation_exhausted():
    """finish_reason=length text → 3 continuation turns → concatenated partial.

    Parity with the loop (run_agent.py:10510): each continuation is a fresh
    model turn (api_calls=3), and the accumulated prefix is returned.
    """
    spec = _load("exit_text_continuation")
    snapshot = _replay_graph(spec)
    expected = spec["expected"]

    assert snapshot["result_keys"] == expected["result_keys"]
    assert snapshot["result"]["completed"] is False
    assert snapshot["result"]["partial"] is True
    assert snapshot["result"]["api_calls"] == expected["result"]["api_calls"] == 3
    assert snapshot["model_turns_consumed"] == 3
    assert snapshot["result"]["final_response"] == expected["result"]["final_response"]


def test_graph_truncated_tool_call_repeated():
    """finish_reason=length tool call → 1 inner retry → truncated exit.

    Parity with the loop (run_agent.py:10538): the retry does not bump
    api_calls (1) but consumes a second model turn (2).
    """
    spec = _load("exit_truncated_tool_call")
    snapshot = _replay_graph(spec)
    expected = spec["expected"]

    assert snapshot["result_keys"] == expected["result_keys"]
    assert snapshot["result"]["completed"] is False
    assert snapshot["result"]["partial"] is True
    assert snapshot["result"]["api_calls"] == expected["result"]["api_calls"] == 1
    assert snapshot["model_turns_consumed"] == 2
    assert snapshot["result"]["final_response"] is None


def test_graph_incomplete_scratchpad_exhausted():
    """Unclosed <REASONING_SCRATCHPAD> → 2 fresh-turn retries → partial exit.

    Parity with the loop (run_agent.py:11856): each retry is a fresh model
    turn (api_calls=3) and the broken turns are rolled back.
    """
    spec = _load("exit_incomplete_scratchpad")
    snapshot = _replay_graph(spec)
    expected = spec["expected"]

    assert snapshot["result_keys"] == expected["result_keys"]
    assert snapshot["result"]["completed"] is False
    assert snapshot["result"]["partial"] is True
    assert snapshot["result"]["api_calls"] == expected["result"]["api_calls"] == 3
    assert snapshot["model_turns_consumed"] == 3
    assert snapshot["result"]["final_response"] is None


def test_graph_truncated_json_tool_arguments():
    """tool_calls with cut-off JSON arguments → immediate truncated exit.

    Parity with the loop (run_agent.py:11969): one turn, no tool execution.
    """
    spec = _load("exit_truncated_json_args")
    snapshot = _replay_graph(spec)
    expected = spec["expected"]

    assert snapshot["result_keys"] == expected["result_keys"]
    assert snapshot["result"]["completed"] is False
    assert snapshot["result"]["partial"] is True
    assert snapshot["result"]["api_calls"] == expected["result"]["api_calls"] == 1
    assert snapshot["model_turns_consumed"] == 1
    assert snapshot["result"]["final_response"] is None
    # The truncated tool was never executed.
    assert snapshot["tool_invocations"] == []
