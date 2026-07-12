# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Phase 3.5 Task 11: deterministic graph replay fuzzing.

The committed ``golden/*.json`` fixtures pin specific, hand-chosen exit paths.
This module *supplements* them with a fixed-seed generator (stdlib ``random``
only — no property-testing dependency) that builds many valid, bounded
transport/tool/steer sequences and asserts the graph engine produces identical
observable snapshots across fresh replays. (Interrupt sequences are deliberately
excluded — see ``_generate_spec`` — because their mid-turn timing is not
deterministically reproducible.)

Each generated case is replayed twice on fresh agents and scripted transports,
so the determinism check cannot leak state. On a mismatch the test prints the
seed and the failing spec so it can be promoted to a named regression fixture.
"""

from __future__ import annotations

import json
import random
import sys
import types
from typing import Any, Dict, List

import pytest

sys.modules.setdefault("fire", types.SimpleNamespace(Fire=lambda *a, **k: None))
sys.modules.setdefault("firecrawl", types.SimpleNamespace(Firecrawl=object))
sys.modules.setdefault("fal_client", types.SimpleNamespace())

try:
    from tests.run_agent.golden_harness import replay_transcript
except ImportError:  # pytest prepend-import mode
    from golden_harness import replay_transcript


# Known tools the generator may call.  ``unknown_tool_X`` names are emitted
# verbatim to exercise the invalid-tool self-correction path under both engines.
_KNOWN_TOOLS = ["web_search", "calculator", "read_file"]
_SEED = 0xC0FFEE
_NUM_SEQUENCES = 120


def _usage(rng: random.Random) -> Dict[str, int]:
    p = rng.randint(10, 200)
    c = rng.randint(1, 60)
    return {"prompt_tokens": p, "completion_tokens": c, "total_tokens": p + c}


def _tool_turn(rng: random.Random, name: str) -> Dict[str, Any]:
    return {
        "content": None,
        "finish_reason": "tool_calls",
        "tool_calls": [
            {
                "id": f"call_{rng.randint(1, 1_000_000):06d}",
                "name": name,
                "arguments": json.dumps({"q": rng.randint(0, 99)}),
            }
        ],
        "usage": _usage(rng),
    }


def _text_turn(rng: random.Random) -> Dict[str, Any]:
    return {
        "content": f"Final answer #{rng.randint(0, 9999)}.",
        "finish_reason": "stop",
        "usage": _usage(rng),
    }


def _unknown_tool_turn(rng: random.Random) -> Dict[str, Any]:
    """A call to a tool the agent does not have → invalid-tool self-correction."""
    return {
        "content": None,
        "finish_reason": "tool_calls",
        "tool_calls": [
            {
                "id": f"call_{rng.randint(1, 1_000_000):06d}",
                "name": f"unknown_tool_{rng.randint(0, 99)}",
                "arguments": "{}",
            }
        ],
        "usage": _usage(rng),
    }


def _length_turn(rng: random.Random) -> Dict[str, Any]:
    """A length-truncated turn → drives one text-continuation before the end."""
    return {
        "content": f"partial {rng.randint(0, 99)} ",
        "finish_reason": "length",
        "usage": _usage(rng),
    }


def _generate_spec(rng: random.Random) -> Dict[str, Any]:
    """Build one valid, bounded transcript spec.

    Structure: an optional single-shot *prefix* event (recoverable unknown-tool,
    retryable transport error, length-truncation, or empty/malformed response),
    then zero or more known-tool turns, then a terminating text turn.  All
    variants recover and end on the same text turn, so the conversation is
    bounded and deterministic on both engines (review P1-5 — the fuzzer now
    covers the unknown-tool / truncation / retryable-error / empty-response
    families the spec requires, not just known tools + steer).

    NOTE: the ``interrupt`` action is intentionally NOT generated here.  An
    interrupt fired mid-turn is observed at a *timing-dependent* point relative
    to the API-call/tool boundary, and the graph runs the turn asynchronously
    (LangGraph) so under a real event loop the observation point — and therefore
    the early-exit vs tool-cancel path — is not deterministically reproducible
    in a fixed-seed fuzzer.  Interrupt equivalence is instead pinned
    deterministically by the committed ``interrupt.json`` golden
    (``test_golden_transcripts``, loop+graph) and ``test_graph_error_parity``.
    The differential fuzzer surfaced a genuine timing-dependent divergence on
    interrupt-during-API-call (graph early-exits with a minimal result, skipping
    `_finalize_turn`/`on_session_end`/cleanup/trajectory) — tracked as
    PH35-FU-008 in DECISIONS.md for the equivalence track to pin and fix.
    """
    api_mode = rng.choice(["chat_completions", "anthropic_messages"])
    n_tool_turns = rng.randint(0, 3)
    used_tools = [rng.choice(_KNOWN_TOOLS) for _ in range(n_tool_turns)]

    turns: List[Dict[str, Any]] = [_tool_turn(rng, t) for t in used_tools]
    turns.append(_text_turn(rng))

    # Optional single-shot variant (kept bounded + deterministic so the
    # conversation still recovers and ends the same way on both engines).
    variant = rng.choice(
        [
            "plain",
            "plain",
            "steer",
            "unknown_tool",
            "retryable_error",
            "truncation",
            "empty_response",
        ]
    )
    if variant == "steer" and turns:
        idx = rng.randrange(len(turns))
        turns[idx]["action"] = "steer"
        turns[idx]["action_text"] = "please be concise"
    elif variant == "unknown_tool":
        # Reject one unknown tool call, then proceed through the planned turns.
        turns.insert(0, _unknown_tool_turn(rng))
    elif variant == "retryable_error":
        # One retryable 5xx, recovered on the next transport attempt.
        turns.insert(
            0,
            {
                "raise": {
                    "type": "api_error",
                    "status_code": 500,
                    "message": "upstream server error",
                }
            },
        )
    elif variant == "truncation":
        # A length-truncated turn → exactly one text continuation, then end.
        # Kept free of intervening tool turns so this exercises the legitimate
        # text-continuation path (Task 8c parity), not a malformed length→tool
        # sequence whose continuation semantics aren't a defined contract.
        turns = [_length_turn(rng), _text_turn(rng)]
    elif variant == "empty_response":
        # One empty/malformed response → retry/fallback, then recover.
        turns.insert(0, {"invalid": True})

    spec: Dict[str, Any] = {
        "name": "generated",
        "agent": {
            "api_mode": api_mode,
            "provider": "openrouter",
            "model": "golden/test-model",
            "base_url": "https://api.openai.com/v1",
        },
        "user_message": f"Question {rng.randint(0, 9999)}?",
        "tools": sorted(set(used_tools)),
        "tool_results": {t: json.dumps({"ok": True, "tool": t}) for t in set(used_tools)},
        "model_turns": turns,
    }
    return spec


def _generated_specs() -> List[Dict[str, Any]]:
    rng = random.Random(_SEED)
    return [_generate_spec(rng) for _ in range(_NUM_SEQUENCES)]


def _reset_interrupt_global() -> None:
    """Clear the process-wide per-thread interrupt registry.

    ``tools.interrupt`` tracks interrupted threads in a module-global set keyed
    by thread id.  Production runs one agent per thread, but this test replays
    hundreds of agents on the *same* pytest worker thread; an interrupt-variant
    case can leave a residual thread bit that the next replay would observe.
    Resetting before each replay restores the one-agent-per-thread invariant so
    the comparison stays hermetic and order-independent.
    """
    import tools.interrupt as _interrupt_mod

    with _interrupt_mod._lock:
        _interrupt_mod._interrupted_threads.clear()


@pytest.mark.parametrize(
    "index", range(_NUM_SEQUENCES), ids=lambda i: f"seq{i:03d}"
)
def test_graph_replay_is_deterministic(index: int) -> None:
    """Fresh graph replays produce identical snapshots on a generated sequence."""
    spec = _generated_specs()[index]

    _reset_interrupt_global()
    first_snap = replay_transcript(spec)
    _reset_interrupt_global()
    second_snap = replay_transcript(spec)

    if first_snap != second_snap:
        # Surface the seed + spec so this becomes a named fixture.
        diff_keys = sorted(
            k
            for k in set(first_snap) | set(second_snap)
            if first_snap.get(k) != second_snap.get(k)
        )
        diff = {
            k: {"first": first_snap.get(k), "second": second_snap.get(k)}
            for k in diff_keys
        }
        msg = (
            f"non-deterministic graph replay on generated seq{index:03d}\n"
            f"seed={_SEED:#x} index={index}\n"
            f"diff_keys={diff_keys}\n"
            f"diff={json.dumps(diff, ensure_ascii=False, default=str)}\n"
            f"spec={json.dumps(spec, ensure_ascii=False)}"
        )
        raise AssertionError(msg)


def test_generator_is_deterministic() -> None:
    """The fixed seed yields the same corpus on every run (regression-stable)."""
    first = _generated_specs()
    second = _generated_specs()
    assert first == second
    assert len(first) >= 100
