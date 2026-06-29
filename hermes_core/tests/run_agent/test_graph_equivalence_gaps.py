# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Measure graph-vs-loop equivalence and pin the KNOWN Task-9 gaps.

The graph-specific parity suites (``test_graph_plain_text``,
``test_graph_protocol_parity``, ``test_graph_tool_parity``,
``test_graph_error_parity``) only assert *core* result fields.  The plan's
file-map called for ``test_golden_transcripts`` to be parameterised over
loop/graph so the *full* snapshot is compared; that was never done, which left
two real divergences unmeasured:

* the graph fires **none** of the six load-bearing plugin hooks the loop fires
  (``on_session_start`` … ``on_session_end``);
* the graph never updates the session token/cost counters, so a successful
  turn reports zero usage / zero cost.

Task 9 **closed** all three gaps: the graph now fires the six load-bearing
plugin hooks, updates the session token/cost counters, and writes the
trajectory exactly like the loop.  The former ``xfail(strict=True)`` measurement
cases are now plain parity assertions; the authoritative end-to-end gate is the
loop/graph-parameterized ``test_golden_transcripts``.

See ``DECISIONS.md`` (PH35-FU-001 / PH35-FU-002 / PH35-FU-003 — closed).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from tests.run_agent.test_graph_protocol_parity import _replay_graph


GOLDEN_DIR = Path(__file__).parent / "golden"

# Fixtures whose *core* result the graph already reproduces (successful turns).
CORE_PARITY_FIXTURES = ["plain_text", "anthropic_text"]

# Canonical successful turn used to measure the side-effect gaps.
GAP_FIXTURE = "plain_text"


def _load(name: str) -> Dict[str, Any]:
    return json.loads((GOLDEN_DIR / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", CORE_PARITY_FIXTURES)
def test_graph_core_parity(name: str) -> None:
    """The graph reproduces the loop's core result on a successful turn."""
    spec = _load(name)
    snap = _replay_graph(spec)
    exp = spec["expected"]

    assert snap["result"]["final_response"] == exp["result"]["final_response"]
    assert snap["result"]["completed"] == exp["result"]["completed"]
    assert snap["result"]["api_calls"] == exp["result"]["api_calls"]
    assert snap["result"]["partial"] == exp["result"]["partial"]
    assert snap["result"]["interrupted"] == exp["result"]["interrupted"]
    assert snap["model_turns_consumed"] == exp["model_turns_consumed"]
    assert snap["tool_invocations"] == exp["tool_invocations"]


def test_graph_plugin_hooks_closed() -> None:
    """CLOSED (PH35-FU-001): the graph fires the same plugin hooks as the loop."""
    spec = _load(GAP_FIXTURE)
    snap = _replay_graph(spec)
    exp = spec["expected"]
    assert snap["hook_calls"] == exp["hook_calls"]


def test_graph_usage_accounting_closed() -> None:
    """CLOSED (PH35-FU-002): the graph records the same usage/cost as the loop."""
    spec = _load(GAP_FIXTURE)
    snap = _replay_graph(spec)
    exp = spec["expected"]
    assert snap["usage"] == exp["usage"]


def test_graph_trajectory_write_closed() -> None:
    """CLOSED (PH35-FU-003): the graph writes the trajectory like the loop."""
    spec = _load(GAP_FIXTURE)
    snap = _replay_graph(spec)
    exp = spec["expected"]
    assert snap["trajectory_writes"] == exp["trajectory_writes"]
