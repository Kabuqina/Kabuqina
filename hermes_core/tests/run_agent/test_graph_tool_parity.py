# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Phase 3.5 Task 6: tool dispatch parity — loop ≡ graph for tool scenarios.

Verifies that the graph engine produces the same essential output as the
legacy loop for tool-call branches: single tool, parallel tools, unknown
tool rejection, truncated-JSON-args exit, and steer placement.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from tests.run_agent.test_graph_protocol_parity import _replay_graph


GOLDEN_DIR = Path(__file__).parent / "golden"


def _load_fixture(name: str) -> Dict[str, Any]:
    path = GOLDEN_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ── Text / single-tool / parallel-tools — must complete ─────────────────


def test_graph_single_tool():
    """Graph engine: one tool call (sequential), result fed back, final answer."""
    spec = _load_fixture("single_tool")
    snapshot = _replay_graph(spec)
    expected = spec.get("expected", {})

    assert snapshot["result"]["completed"] is True
    assert snapshot["result"]["final_response"] == expected["result"]["final_response"]
    assert snapshot["result"]["api_calls"] == expected["result"]["api_calls"]
    assert snapshot["result"]["model"] == expected["result"]["model"]
    assert snapshot["result"]["provider"] == expected["result"]["provider"]

    # 4 messages: user → assistant(tool_calls) → tool → assistant(stop)
    assert len(snapshot["messages"]) == 4, (
        f"expected 4 messages, got {len(snapshot['messages'])}"
    )
    assert snapshot["messages"][1]["role"] == "assistant"
    assert snapshot["messages"][1].get("tool_calls")
    assert snapshot["messages"][2]["role"] == "tool"
    assert snapshot["messages"][3]["role"] == "assistant"
    assert "final_response" not in snapshot["messages"][3].get("content", "")

    # One tool invocation recorded
    assert len(snapshot["tool_invocations"]) == 1
    assert snapshot["tool_invocations"][0]["name"] == "web_search"

    # Two model turns consumed
    assert snapshot["model_turns_consumed"] == 2


def test_graph_parallel_tools():
    """Graph engine: two concurrent tool calls, results fed back, final answer."""
    spec = _load_fixture("parallel_tools")
    snapshot = _replay_graph(spec)
    expected = spec.get("expected", {})

    assert snapshot["result"]["completed"] is True
    assert snapshot["result"]["final_response"] == expected["result"]["final_response"]
    assert snapshot["result"]["api_calls"] == expected["result"]["api_calls"]

    # 5 messages: user → assistant(2 tool_calls) → tool(ws) → tool(we) → assistant(stop)
    assert len(snapshot["messages"]) == 5, (
        f"expected 5 messages, got {len(snapshot['messages'])}"
    )
    assert snapshot["messages"][1]["role"] == "assistant"
    tcs = snapshot["messages"][1].get("tool_calls", [])
    assert len(tcs) == 2, f"expected 2 tool_calls, got {len(tcs)}"

    # Both tools recorded in invocations
    names = {inv["name"] for inv in snapshot["tool_invocations"]}
    assert names == {"web_search", "web_extract"}, f"got {names}"

    assert snapshot["model_turns_consumed"] == 2


# ── Unknown tool — partial exit ─────────────────────────────────────────


def test_graph_unknown_tool():
    """Graph engine: a hallucinated tool name is rejected, not dispatched.

    Task 9 wired the loop's invalid-tool-name validation into the graph
    (``_validate_tool_names``): an unknown tool name is never sent to
    ``handle_function_call``; instead an error tool result is appended and the
    model is asked to self-correct, ending ``partial`` after three straight
    invalid turns — matching the ``unknown_tool.json`` golden exactly.
    """
    spec = _load_fixture("unknown_tool")
    snapshot = _replay_graph(spec)
    expected = spec["expected"]

    # Unknown names short-circuit before dispatch, so nothing reaches the tool
    # primitive (parity with the loop's empty ``tool_invocations``).
    assert snapshot["tool_invocations"] == expected["tool_invocations"] == []
    assert snapshot["result"]["partial"] is True
    assert snapshot["result"]["api_calls"] == expected["result"]["api_calls"]
    assert snapshot["result"]["final_response"] == expected["result"]["final_response"]


# ── Truncated JSON args — immediate partial ─────────────────────────────


def test_graph_exit_truncated_json_args():
    """Graph engine: truncated tool-call arguments → partial exit, no execution.

    Task 8c routes cut-off JSON arguments to the truncated exit (loop
    :11969) instead of forwarding broken args to ``_execute_tool_calls``.
    """
    spec = _load_fixture("exit_truncated_json_args")
    snapshot = _replay_graph(spec)

    assert snapshot["result"]["completed"] is False
    assert snapshot["result"]["partial"] is True
    assert snapshot["result"]["final_response"] is None
    # The broken tool call must NOT have executed.
    assert snapshot["tool_invocations"] == []


# ── Steer — appended to tool result ──────────────────────────────────────


def test_graph_steer():
    """Graph engine: /steer during tool round appended to last tool result."""
    spec = _load_fixture("steer")
    snapshot = _replay_graph(spec)
    expected = spec.get("expected", {})

    assert snapshot["result"]["completed"] is True
    assert snapshot["result"]["api_calls"] == expected["result"]["api_calls"]

    # final_response should include humidity info from steer
    assert snapshot["result"]["final_response"] is not None
    assert "humidity" in snapshot["result"]["final_response"].lower(), (
        f"steer effect missing in final_response: {snapshot['result']['final_response']}"
    )

    # 4 messages: user → assistant(tool_calls) → tool(steer) → assistant(stop)
    assert len(snapshot["messages"]) == 4

    # Tool message should contain the User guidance marker
    tool_msgs = [m for m in snapshot["messages"] if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    steer_content = str(tool_msgs[0].get("content", ""))
    assert "User guidance" in steer_content, (
        f"steer marker not found in tool content: {steer_content[:200]}"
    )

    assert snapshot["model_turns_consumed"] == 2
