# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Golden-transcript characterization tests for ``AIAgent.run_conversation``.

Each ``golden/*.json`` fixture scripts a full conversation (see
``golden_harness`` for the schema and rationale) and stores the expected
observable snapshot under ``"expected"``. The test replays the transcript and
asserts the snapshot is unchanged — so any behavior drift in the loop during the
phase-3 consolidate or phase-3.5 LangGraph re-platform shows up as a diff here.

Recording / updating goldens (review the diff before committing!)::

    GOLDEN_RECORD=1 python -m pytest tests/run_agent/test_golden_transcripts.py \
        -o "addopts=" -p no:cacheprovider

Run normally (hermetic — no network, no disk, no DB)::

    python -m pytest tests/run_agent/test_golden_transcripts.py \
        -o "addopts=" -p no:cacheprovider
"""

from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path

import pytest

# Optional heavy deps that run_agent imports transitively (mirror the stubs used
# by the sibling run_agent tests so collection never needs the real packages).
sys.modules.setdefault("fire", types.SimpleNamespace(Fire=lambda *a, **k: None))
sys.modules.setdefault("firecrawl", types.SimpleNamespace(Firecrawl=object))
sys.modules.setdefault("fal_client", types.SimpleNamespace())

try:
    from tests.run_agent.golden_harness import replay_transcript
except ImportError:  # pytest prepend-import mode puts this dir on sys.path
    from golden_harness import replay_transcript

GOLDEN_DIR = Path(__file__).parent / "golden"
RECORD = os.environ.get("GOLDEN_RECORD") == "1"


def _fixtures():
    return sorted(GOLDEN_DIR.glob("*.json"))


@pytest.mark.parametrize("engine", ["loop", "graph"])
@pytest.mark.parametrize(
    "fixture_path", _fixtures(), ids=lambda p: p.stem
)
def test_golden_transcript(fixture_path: Path, engine: str):
    """Replay each fixture under both engines and pin it to the frozen golden.

    The ``loop`` parameterization is the legacy characterization gate; the
    ``graph`` parameterization is the Phase 3.5 equivalence gate.  Both engines
    are compared to the **same** committed ``expected`` snapshot (recorded from
    the loop), so a graph divergence in result keys, messages, hooks, cleanup,
    interrupt clearing, persistence, streaming, or usage shows up here.  Each
    parameterization constructs its own fresh agent and scripted transport.
    """
    spec = json.loads(fixture_path.read_text(encoding="utf-8"))

    if RECORD:
        if engine != "loop":
            pytest.skip("goldens are recorded from the loop only")
        snapshot = replay_transcript(spec, engine="loop")
        spec["expected"] = snapshot
        fixture_path.write_text(
            json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        pytest.skip(f"recorded golden snapshot for {fixture_path.name}")

    snapshot = replay_transcript(spec, engine=engine)

    expected = spec.get("expected")
    assert expected is not None, (
        f"{fixture_path.name} has no 'expected' snapshot — record it first with "
        f"GOLDEN_RECORD=1"
    )
    assert snapshot == expected


def test_at_least_one_fixture_present():
    """Guard against the suite silently degrading to zero cases."""
    assert _fixtures(), "no golden transcripts found under tests/run_agent/golden/"
