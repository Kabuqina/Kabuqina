# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Static inventory for all source exits in legacy ``run_conversation``."""

from __future__ import annotations

import ast
import json
from pathlib import Path

RUN_AGENT_SRC = Path(__file__).resolve().parents[2] / "run_agent.py"
GOLDEN_DIR = Path(__file__).parent / "golden"

# Stable scenario ids are the review contract. Source lines document the audited
# legacy body and intentionally require review when that body moves.
#
# Line numbers rebased 2026-06-29 (Task 9): the legacy ``run_conversation`` body
# shifted uniformly when Task 8 landed loop-side compression code above the
# returns.  Task 9 added only graph-engine/adapter code *below* the loop, so the
# 21 returns themselves are unchanged — only their absolute positions moved.
# Scenario ids and ordering are the stable review contract.
EXIT_INVENTORY = (
    (10116, "nous_rate_guard_without_fallback", "exit_nous_rate_guard.json"),
    (10341, "invalid_response_retries_exhausted", "exit_invalid_response.json"),
    (10362, "interrupt_during_invalid_response_wait", "exit_interrupt_invalid_wait.json"),
    (10475, "thinking_budget_exhausted", "exit_thinking_budget.json"),
    (10515, "text_continuation_exhausted", "exit_text_continuation.json"),
    (10543, "truncated_tool_call_repeated", "exit_truncated_tool_call.json"),
    (10560, "truncation_rolls_back_history", None),
    (10572, "first_response_truncated", None),
    (11127, "interrupt_during_api_error_handling", "exit_interrupt_api_error.json"),
    (11297, "payload_compression_attempts_exhausted", "exit_payload_compression.json"),
    (11328, "payload_cannot_compress", "exit_payload_no_compression.json"),
    (11381, "safe_output_context_attempts_exhausted", "exit_safe_output_context.json"),
    (11454, "context_stepdown_attempts_exhausted", "exit_context_stepdown.json"),
    (11487, "context_cannot_compress", "exit_context_no_compression.json"),
    (11582, "nonretryable_client_error", "exit_nonretryable_client.json"),
    (11665, "api_retries_exhausted", "exit_api_retries.json"),
    (11707, "interrupt_during_generic_retry_wait", "exit_interrupt_retry_wait.json"),
    (11861, "incomplete_scratchpad_exhausted", "exit_incomplete_scratchpad.json"),
    (11908, "unknown_tool_retries_exhausted", "unknown_tool.json"),
    (11974, "truncated_json_tool_arguments", "exit_truncated_json_args.json"),
    (12694, "normal_final_result", "plain_text.json"),
)


def _run_conversation_return_lines() -> list[int]:
    source = RUN_AGENT_SRC.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run_conversation":
            return sorted(
                child.lineno for child in ast.walk(node) if isinstance(child, ast.Return)
            )
    raise AssertionError("AIAgent.run_conversation not found")


def test_inventory_covers_all_21_source_returns() -> None:
    expected_lines = [line for line, _scenario, _fixture in EXIT_INVENTORY]
    assert len(EXIT_INVENTORY) == 21
    assert len({scenario for _line, scenario, _fixture in EXIT_INVENTORY}) == 21
    assert _run_conversation_return_lines() == expected_lines


def test_nineteen_runtime_exits_have_fixtures_and_two_dead_exits_do_not() -> None:
    runtime = [row for row in EXIT_INVENTORY if row[2] is not None]
    structural = [row for row in EXIT_INVENTORY if row[2] is None]

    assert len(runtime) == 19
    assert {scenario for _line, scenario, _fixture in structural} == {
        "truncation_rolls_back_history",
        "first_response_truncated",
    }
    missing = [fixture for _line, _scenario, fixture in runtime if not (GOLDEN_DIR / fixture).is_file()]
    assert not missing, f"missing runtime exit fixtures: {missing}"


def test_nineteen_runtime_exits_have_frozen_observable_snapshots() -> None:
    usage_keys = {
        "input_tokens",
        "output_tokens",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
        "last_prompt_tokens",
        "estimated_cost_usd",
        "cost_status",
        "cost_source",
    }
    for _line, scenario, fixture in EXIT_INVENTORY:
        if fixture is None:
            continue
        spec = json.loads((GOLDEN_DIR / fixture).read_text(encoding="utf-8"))
        expected = spec.get("expected")
        assert expected is not None, f"{scenario} has no frozen snapshot"
        assert expected["result_keys"] == sorted(expected["result_keys"]), scenario
        assert set(expected["usage"]) == usage_keys, scenario
        assert "callback_events" in expected, scenario
        assert "trajectory_writes" in expected, scenario
