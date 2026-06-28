# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Pin the agent loop's retry / attempt limits (Phase 3.5 Task 2).

These hard-coded branch limits (plus the ``api_max_retries`` config default) are
*preconditions* for the exit-contract goldens: every retry-exhaustion fixture
scripts exactly ``limit + 1`` transport turns to drive its branch to exhaustion.
If a limit changes silently, an exhaustion transcript would run out of scripted
turns and fail deep inside the harness with a confusing AssertionError instead of
a clear contract failure. This test fails first, loudly, naming the broken
contract — exactly the guard the reachability spike
(``docs/superpowers/specs/2026-06-28-phase-3.5-exit-reachability-spike.md``) asks
for.

It is implemented as source introspection because most of these limits are local
literals inside the ~3k-line ``run_conversation`` and are not reachable as
attributes. ``EXPECTED_RETRY_COUNTS`` is exported so exit fixtures and the
harness can declare ``assumed_retry_counts`` against a single source of truth.
"""

from __future__ import annotations

import re
from pathlib import Path

RUN_AGENT_SRC = Path(__file__).resolve().parents[2] / "run_agent.py"

# name -> (expected count, regex pinning the production source expression that
# encodes that count). The number is embedded in the pattern so changing the
# limit in run_agent.py breaks the match and fails this test by name.
RETRY_CONTRACT: dict[str, tuple[int, str]] = {
    "api_max_retries": (3, r'_agent_section\.get\(\s*"api_max_retries",\s*3\s*\)'),
    "max_compression_attempts": (3, r"\bmax_compression_attempts\s*=\s*3\b"),
    "text_continuation_attempts": (3, r"\blength_continue_retries\s*<\s*3\b"),
    "truncated_tool_call_retries": (1, r"\btruncated_tool_call_retries\s*<\s*1\b"),
    "incomplete_scratchpad_retries": (2, r"self\._incomplete_scratchpad_retries\s*<=\s*2\b"),
    "unknown_tool_retries": (3, r"self\._invalid_tool_retries\s*>=\s*3\b"),
}

# Single source of truth for fixtures' ``assumed_retry_counts``.
EXPECTED_RETRY_COUNTS: dict[str, int] = {
    name: count for name, (count, _pat) in RETRY_CONTRACT.items()
}


def test_retry_limits_match_production_source() -> None:
    src = RUN_AGENT_SRC.read_text(encoding="utf-8")
    broken: list[str] = []
    for name, (count, pattern) in RETRY_CONTRACT.items():
        if re.search(pattern, src) is None:
            broken.append(f"{name} (expected {count}): pattern /{pattern}/ not found")
    assert not broken, (
        "agent retry/attempt contract drifted from run_agent.py. The exit-contract "
        "goldens script (limit + 1) transport turns per exhaustion path, so a changed "
        "limit must be reviewed and re-pinned here first:\n  " + "\n  ".join(broken)
    )


def test_expected_counts_are_the_documented_contract() -> None:
    # Locks the exported contract to the values declared by the Phase 3.5 plan /
    # reachability spike, so the export can't silently drift from the goldens.
    assert EXPECTED_RETRY_COUNTS == {
        "api_max_retries": 3,
        "max_compression_attempts": 3,
        "text_continuation_attempts": 3,
        "truncated_tool_call_retries": 1,
        "incomplete_scratchpad_retries": 2,
        "unknown_tool_retries": 3,
    }
