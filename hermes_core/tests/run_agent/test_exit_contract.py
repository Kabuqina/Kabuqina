# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Graph-only exit fixture inventory.

The graph runtime owns the exit implementation, so this contract tracks the
observable exit corpus rather than private source line numbers. Each runtime
scenario must have a frozen golden fixture; the two truncation fallthroughs
remain structural cases with no fixture.
"""

from __future__ import annotations

import json
from pathlib import Path


GOLDEN_DIR = Path(__file__).parent / "golden"

EXIT_INVENTORY: tuple[tuple[str, str | None], ...] = (
    ("nous_rate_guard_without_fallback", "exit_nous_rate_guard.json"),
    ("invalid_response_retries_exhausted", "exit_invalid_response.json"),
    ("interrupt_during_invalid_response_wait", "exit_interrupt_invalid_wait.json"),
    ("thinking_budget_exhausted", "exit_thinking_budget.json"),
    ("text_continuation_exhausted", "exit_text_continuation.json"),
    ("truncated_tool_call_repeated", "exit_truncated_tool_call.json"),
    ("truncation_rolls_back_history", None),
    ("first_response_truncated", None),
    ("interrupt_during_api_error_handling", "exit_interrupt_api_error.json"),
    ("payload_compression_attempts_exhausted", "exit_payload_compression.json"),
    ("payload_cannot_compress", "exit_payload_no_compression.json"),
    ("safe_output_context_attempts_exhausted", "exit_safe_output_context.json"),
    ("context_stepdown_attempts_exhausted", "exit_context_stepdown.json"),
    ("context_cannot_compress", "exit_context_no_compression.json"),
    ("nonretryable_client_error", "exit_nonretryable_client.json"),
    ("api_retries_exhausted", "exit_api_retries.json"),
    ("interrupt_during_generic_retry_wait", "exit_interrupt_retry_wait.json"),
    ("incomplete_scratchpad_exhausted", "exit_incomplete_scratchpad.json"),
    ("unknown_tool_retries_exhausted", "unknown_tool.json"),
    ("truncated_json_tool_arguments", "exit_truncated_json_args.json"),
    ("normal_final_result", "plain_text.json"),
)


def test_inventory_has_the_full_graph_exit_corpus() -> None:
    assert len(EXIT_INVENTORY) == 21
    assert len({scenario for scenario, _fixture in EXIT_INVENTORY}) == 21


def test_runtime_exits_have_fixtures_and_structural_cases_do_not() -> None:
    runtime = [row for row in EXIT_INVENTORY if row[1] is not None]
    structural = [row for row in EXIT_INVENTORY if row[1] is None]

    assert len(runtime) == 19
    assert {scenario for scenario, _fixture in structural} == {
        "truncation_rolls_back_history",
        "first_response_truncated",
    }
    missing = [fixture for _scenario, fixture in runtime if not (GOLDEN_DIR / fixture).is_file()]
    assert not missing, f"missing graph exit fixtures: {missing}"


def test_runtime_exit_fixtures_have_frozen_observable_snapshots() -> None:
    usage_keys = {
        "input_tokens", "output_tokens", "prompt_tokens", "completion_tokens",
        "total_tokens", "cache_read_tokens", "cache_write_tokens",
        "reasoning_tokens", "last_prompt_tokens", "estimated_cost_usd",
        "cost_status", "cost_source",
    }
    for scenario, fixture in EXIT_INVENTORY:
        if fixture is None:
            continue
        spec = json.loads((GOLDEN_DIR / fixture).read_text(encoding="utf-8"))
        expected = spec.get("expected")
        assert expected is not None, f"{scenario} has no frozen snapshot"
        assert expected["result_keys"] == sorted(expected["result_keys"]), scenario
        assert set(expected["usage"]) == usage_keys, scenario
        assert "callback_events" in expected, scenario
        assert "trajectory_writes" in expected, scenario
