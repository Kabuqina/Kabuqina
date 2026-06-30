# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Static inventory for all source exits in the legacy ``_run_conversation_loop``.

The loop body has exactly 21 ``return`` statements.  Their **absolute line
positions** drift whenever ``run_agent.py`` is edited above or inside the loop
(this previously caused a red-committed gate and two manual rebases), so this
module does **not** hardcode them.  Instead:

* ``loop_return_lines()`` derives the 21 return lines from the source via AST at
  test time (always current, never drifts);
* ``EXIT_INVENTORY`` is the stable, review-enforced contract — every return, in
  **source order**, mapped to a named scenario and (for the 19 reachable ones) a
  golden fixture.  ``None`` marks a structurally-dead truncation fallthrough.
* ``scenario_return_lines()`` joins the two by position: the i-th scenario owns
  the i-th return line.

Adding, removing, or reordering a return changes ``EXIT_INVENTORY`` (or trips the
count assertion), forcing review.  Editing unrelated code does not.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

RUN_AGENT_SRC = Path(__file__).resolve().parents[2] / "run_agent.py"
GOLDEN_DIR = Path(__file__).parent / "golden"

LOOP_METHOD = "_run_conversation_loop"

# Scenario ids are the stable review contract; ORDER is source order (top to
# bottom of the loop body).  No absolute line numbers — see module docstring.
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


def loop_return_lines() -> list[int]:
    """AST-derived line numbers of every ``return`` in the loop body, ascending
    (source order).  Source of truth — never hardcoded, so it cannot drift."""
    source = RUN_AGENT_SRC.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == LOOP_METHOD:
            return sorted(
                child.lineno for child in ast.walk(node) if isinstance(child, ast.Return)
            )
    raise AssertionError(f"AIAgent.{LOOP_METHOD} not found")


def scenario_return_lines() -> dict[str, int]:
    """Map each inventory scenario to its return line by source-order position:
    the i-th scenario (top to bottom) owns the i-th AST-derived return."""
    lines = loop_return_lines()
    assert len(lines) == len(EXIT_INVENTORY), (
        f"{LOOP_METHOD} has {len(lines)} return statements but EXIT_INVENTORY "
        f"lists {len(EXIT_INVENTORY)} scenarios; a return was added/removed/"
        "reordered — review and update the scenario inventory before re-pinning."
    )
    return {
        scenario: line for (scenario, _fixture), line in zip(EXIT_INVENTORY, lines)
    }


def test_inventory_covers_all_source_returns() -> None:
    lines = loop_return_lines()
    assert len(EXIT_INVENTORY) == 21
    assert len(lines) == 21, f"expected 21 source returns in {LOOP_METHOD}, found {len(lines)}"
    assert len({scenario for scenario, _fixture in EXIT_INVENTORY}) == 21  # ids unique
    # scenario_return_lines() asserts the count join is 1:1.
    assert len(scenario_return_lines()) == 21


def test_nineteen_runtime_exits_have_fixtures_and_two_dead_exits_do_not() -> None:
    runtime = [row for row in EXIT_INVENTORY if row[1] is not None]
    structural = [row for row in EXIT_INVENTORY if row[1] is None]

    assert len(runtime) == 19
    assert {scenario for scenario, _fixture in structural} == {
        "truncation_rolls_back_history",
        "first_response_truncated",
    }
    missing = [fixture for _scenario, fixture in runtime if not (GOLDEN_DIR / fixture).is_file()]
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
