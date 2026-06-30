# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Freeze hook/cleanup/interrupt-clear policy for every reachable exit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.run_agent.golden_harness import replay_transcript
from tests.run_agent.test_exit_contract import EXIT_INVENTORY

GOLDEN_DIR = Path(__file__).parent / "golden"
RUNTIME_FIXTURES = [
    (scenario, fixture)
    for scenario, fixture in EXIT_INVENTORY
    if fixture is not None
]


@pytest.mark.parametrize("engine", ["loop", "graph"])
@pytest.mark.parametrize(
    ("scenario_id", "fixture_name"),
    RUNTIME_FIXTURES,
    ids=[scenario for scenario, _fixture in RUNTIME_FIXTURES],
)
def test_exit_hook_cleanup_and_interrupt_policy_matches_frozen_snapshot(
    scenario_id: str, fixture_name: str, engine: str
) -> None:
    """Every reachable exit fires the same hooks, cleanup, and interrupt-clear
    side effects under both the legacy loop and the Phase 3.5 graph engine."""
    spec = json.loads((GOLDEN_DIR / fixture_name).read_text(encoding="utf-8"))
    expected = spec.get("expected")
    assert expected is not None, f"{scenario_id} has not been recorded"

    actual = replay_transcript(spec, engine=engine)

    assert actual["hook_calls"] == expected["hook_calls"], (scenario_id, engine)
    assert actual["cleanup_task_ids"] == expected["cleanup_task_ids"], (scenario_id, engine)
    assert actual["clear_interrupt_calls"] == expected["clear_interrupt_calls"], (scenario_id, engine)
