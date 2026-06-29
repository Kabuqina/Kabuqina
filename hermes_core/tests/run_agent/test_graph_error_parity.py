# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Phase 3.5 Task 7: error parity — the graph engine reproduces the legacy
loop's retry, fallback, interrupt, and error-classification behaviour.

The graph mirrors the loop's inner retry block: invalid/empty responses and
retryable transport errors are retried up to ``api_max_retries`` with the same
interrupt-aware backoff, non-retryable client errors abort, and an interrupt
observed while handling an error (or during a retry wait) terminates the turn.
``api_calls`` counts once per model turn regardless of how many retries occur.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List

from agent.usage_events import UsageEvent
from tests.run_agent.test_graph_protocol_parity import _replay_graph


GOLDEN_DIR = Path(__file__).parent / "golden"


def _load_fixture(name: str) -> Dict[str, Any]:
    path = GOLDEN_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ── Fallback ─────────────────────────────────────────────────────────────


def test_graph_fallback():
    """Primary returns None → fallback activates → success on the new provider."""
    spec = _load_fixture("fallback")
    snapshot = _replay_graph(spec)
    expected = spec.get("expected", {})

    assert snapshot["result"]["completed"] is True
    assert snapshot["result"]["api_calls"] == expected["result"]["api_calls"]
    assert snapshot["result"]["provider"] == expected["result"]["provider"]
    assert snapshot["result"]["model"] == expected["result"]["model"]
    assert snapshot["result"]["final_response"] == expected["result"]["final_response"]

    # Two messages: user + fallback assistant
    assert len(snapshot["messages"]) == 2
    assert snapshot["messages"][1]["role"] == "assistant"
    assert snapshot["messages"][1]["content"] == "Hello from the fallback provider."


# ── Retryable errors exhaust retries ─────────────────────────────────────


def test_graph_api_retries_exhausted():
    """Three retryable server errors exhaust retries → fail.

    The frozen loop contract counts ``api_calls == 1`` (one model turn, three
    transport attempts) and surfaces the summarised error.
    """
    spec = _load_fixture("exit_api_retries")
    snapshot = _replay_graph(spec)
    expected = spec.get("expected", {})

    assert snapshot["result"]["completed"] is False
    assert snapshot["result"]["api_calls"] == expected["result"]["api_calls"] == 1
    assert (
        snapshot["result"]["final_response"]
        == expected["result"]["final_response"]
    )
    assert "API call failed after 3 retries" in snapshot["result"]["final_response"]


# ── Interrupt while handling an API error ────────────────────────────────


def test_graph_interrupt_api_error():
    """Interrupt is pending when API error handling begins → interrupted."""
    spec = _load_fixture("exit_interrupt_api_error")
    snapshot = _replay_graph(spec)
    expected = spec.get("expected", {})

    assert snapshot["result"]["completed"] is False
    assert snapshot["result"]["interrupted"] is True
    assert snapshot["result"]["api_calls"] == expected["result"]["api_calls"]
    assert (
        snapshot["result"]["final_response"]
        == expected["result"]["final_response"]
    )


# ── Interrupt during a generic retry wait ────────────────────────────────


def test_graph_interrupt_during_retry_wait():
    """Interrupt fires during the post-error backoff sleep → interrupted.

    Reproduces the loop's interrupt-aware backoff (run_agent.py:11671-11695):
    the scripted clock raises the interrupt on the first 200 ms sleep tick.
    """
    spec = _load_fixture("exit_interrupt_retry_wait")
    snapshot = _replay_graph(spec)
    expected = spec.get("expected", {})

    assert snapshot["result"]["interrupted"] is True
    assert snapshot["result"]["completed"] is False
    assert snapshot["result"]["api_calls"] == expected["result"]["api_calls"]
    assert (
        snapshot["result"]["final_response"]
        == expected["result"]["final_response"]
    )


# ── Interrupt during an invalid-response retry wait ──────────────────────


def test_graph_interrupt_during_invalid_wait():
    """Interrupt fires during the invalid-response backoff sleep → interrupted.

    Mirrors the loop's invalid-response backoff (run_agent.py:10327-10351),
    including the duration-based failure-hint text.
    """
    spec = _load_fixture("exit_interrupt_invalid_wait")
    snapshot = _replay_graph(spec)
    expected = spec.get("expected", {})

    assert snapshot["result"]["interrupted"] is True
    assert snapshot["result"]["completed"] is False
    assert snapshot["result"]["api_calls"] == expected["result"]["api_calls"]
    assert (
        snapshot["result"]["final_response"]
        == expected["result"]["final_response"]
    )


# ── Non-retryable client error ───────────────────────────────────────────


def test_graph_nonretryable_client_error():
    """Local ValueError aborts without retry → fail with a null final_response."""
    spec = _load_fixture("exit_nonretryable_client")
    snapshot = _replay_graph(spec)
    expected = spec["expected"]

    assert snapshot["result"]["completed"] is False
    assert snapshot["result_keys"] == expected["result_keys"]
    assert "failed" in snapshot["result_keys"]
    assert snapshot["result"]["api_calls"] == expected["result"]["api_calls"]
    # A client error aborts on the first and only transport attempt.
    assert snapshot["result"]["api_calls"] == 1
    assert snapshot["model_turns_consumed"] == 1
    assert snapshot["result"]["final_response"] is None


# ── Nous rate guard ──────────────────────────────────────────────────────


def test_graph_nous_rate_guard():
    """Nous rate guard active → fail before any API call."""
    spec = _load_fixture("exit_nous_rate_guard")
    snapshot = _replay_graph(spec)
    expected = spec.get("expected", {})

    assert snapshot["result"]["completed"] is False
    assert snapshot["result"]["api_calls"] == expected["result"]["api_calls"]
    assert "rate limit" in (snapshot["result"].get("final_response") or "").lower()


# ── Invalid responses retried up to the limit ────────────────────────────


def test_graph_invalid_response_retries_exhausted():
    """Three malformed responses exhaust the retry budget → fail.

    Parity with the loop: invalid responses are retryable, so all three turns
    are consumed before the turn fails, and ``api_calls`` stays 1.
    """
    spec = _load_fixture("exit_invalid_response")
    snapshot = _replay_graph(spec)
    expected = spec["expected"]

    assert snapshot["result"]["completed"] is False
    # Exact key presence matches the frozen loop contract: error + failed
    # present, final_response absent (exit_invalid_response.json).
    assert snapshot["result_keys"] == expected["result_keys"]
    assert "final_response" not in snapshot["result_keys"]
    assert "failed" in snapshot["result_keys"]
    # One model turn attempted, three transport attempts consumed.
    assert snapshot["result"]["api_calls"] == 1
    assert snapshot["model_turns_consumed"] == 3


# ── Usage events: one per attempted transport route ──────────────────────


def _replay_graph_with_sink(spec: Dict[str, Any]) -> List[UsageEvent]:
    """Replay a fixture through the graph, collecting per-attempt usage events."""
    events: List[UsageEvent] = []

    class _Sink:
        def on_attempt(self, event: UsageEvent) -> None:
            events.append(event)

    _replay_graph(spec, usage_sink=_Sink())
    return events


def test_graph_usage_event_per_attempt_on_exhaustion():
    """Each retryable transport attempt emits exactly one usage event."""
    spec = _load_fixture("exit_api_retries")
    events = _replay_graph_with_sink(spec)

    # Three transport attempts → three events, all transport_error, unknown cost.
    assert len(events) == 3
    assert all(e.outcome == "transport_error" for e in events)
    assert all(e.route == "call_transport" for e in events)
    # Transport errors have no priced usage → unknown cost (incomplete ledger).
    assert all(e.cost_amount is None for e in events)


def test_graph_usage_event_fallback_retains_provider():
    """Fallback attempts retain the provider/model active for each attempt."""
    spec = _load_fixture("fallback")
    events = _replay_graph_with_sink(spec)

    # Attempt 1: primary, invalid. Attempt 2: fallback, success.
    assert len(events) == 2
    assert events[0].outcome == "invalid_response"
    assert events[0].provider == "openrouter"
    assert events[1].outcome == "success"
    assert events[1].provider == "fallbackprov"
    assert events[1].model == "fallback-model"


# ── A graph error must never live-fall-back to the legacy loop ───────────


def test_graph_error_never_invokes_legacy_loop():
    """A graph turn that fails must not silently rerun through the loop.

    Records a side effect on the single transport attempt, then forces the
    attempt to fail. The legacy ``run_conversation`` must never be called and
    the side effect must be observed exactly once — never replayed by a second
    engine on the same real turn (plan decision 5).
    """
    import run_agent
    from unittest.mock import MagicMock, patch
    from tests.run_agent.golden_harness import (
        GOLDEN_SESSION_ID,
        GOLDEN_TASK_ID,
        _ToolStub,
        _patches,
        _ScriptedClock,
    )

    side_effects: List[str] = []

    spec = _load_fixture("exit_nonretryable_client")
    cfg = spec.get("agent", {})
    api_mode = cfg.get("api_mode", "chat_completions")
    model = cfg.get("model", "golden/test-model")

    with _patches(spec.get("tools", []), _ToolStub({}), api_mode) as _hooks:
        agent = run_agent.AIAgent(
            api_key="golden-key",
            base_url=cfg.get("base_url", "https://api.openai.com/v1"),
            provider=cfg.get("provider", "openrouter"),
            api_mode=api_mode,
            model=model,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
        agent.session_id = GOLDEN_SESSION_ID
        agent._disable_streaming = True
        agent._session_db = MagicMock()
        agent._save_session_log = lambda *a, **k: None
        agent._save_trajectory = lambda *a, **k: None

        def _failing_transport(api_kwargs):
            side_effects.append("transport")
            raise ValueError("invalid local request")

        agent._interruptible_api_call = _failing_transport

        loop_spy = MagicMock(side_effect=AssertionError(
            "legacy run_conversation must not run after a graph turn"
        ))
        clock = _ScriptedClock()
        with (
            patch.object(run_agent.AIAgent, "run_conversation", loop_spy),
            patch.object(run_agent.time, "time", clock.time),
            patch.object(run_agent.time, "sleep", clock.sleep),
            patch.object(run_agent, "jittered_backoff", lambda *a, **k: 0.1),
        ):
            result = agent._run_conversation_graph(
                spec["user_message"], task_id=GOLDEN_TASK_ID
            )

    assert loop_spy.call_count == 0
    assert side_effects == ["transport"]
    assert result.get("completed") is False
    assert result.get("failed") is True
