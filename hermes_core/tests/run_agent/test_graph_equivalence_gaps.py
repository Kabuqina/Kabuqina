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

This module makes both visible:

* ``test_graph_core_parity`` enforces the parity the graph *does* achieve today
  (regression protection).
* the ``test_graph_*_gap`` cases are ``xfail(strict=True)``: they assert the
  *desired* full parity and are expected to fail now.  When Task 9 closes a gap
  the case XPASSes, which strict mode reports as a failure — forcing whoever
  fixes it to delete the marker and promote the assertion.  This is the
  measurement, not a blessing of the divergence.

See ``DECISIONS.md`` (PH35-FU-001 / PH35-FU-002 / PH35-FU-003).
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


@pytest.mark.xfail(
    strict=True,
    reason="Graph fires no plugin hooks (Task 9 / DECISIONS.md PH35-FU-001)",
)
def test_graph_plugin_hooks_gap() -> None:
    """KNOWN GAP: the graph should fire the same plugin hooks as the loop."""
    spec = _load(GAP_FIXTURE)
    snap = _replay_graph(spec)
    exp = spec["expected"]
    assert snap["hook_calls"] == exp["hook_calls"]


@pytest.mark.xfail(
    strict=True,
    reason="Graph does not update session usage/cost (Task 9 / DECISIONS.md PH35-FU-002)",
)
def test_graph_usage_accounting_gap() -> None:
    """KNOWN GAP: the graph should record the same usage/cost as the loop."""
    spec = _load(GAP_FIXTURE)
    snap = _replay_graph(spec)
    exp = spec["expected"]
    assert snap["usage"] == exp["usage"]


@pytest.mark.xfail(
    strict=True,
    reason="Graph does not write trajectories (Task 9 / DECISIONS.md PH35-FU-003)",
)
def test_graph_trajectory_write_gap() -> None:
    """KNOWN GAP: the graph should write trajectories like the loop."""
    spec = _load(GAP_FIXTURE)
    snap = _replay_graph(spec)
    exp = spec["expected"]
    assert len(snap["trajectory_writes"]) == len(exp["trajectory_writes"])
