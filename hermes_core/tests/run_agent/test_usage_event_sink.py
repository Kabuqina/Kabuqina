# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Phase 3.5 Task 4: usage-event sink wired through graph-engine path.

Verifies that the optional ``UsageEventSink`` (from ``agent.usage_events``)
receives exactly one ``UsageEvent`` per transport attempt — success or error
— and that the ledger snapshot reflects the outcome.
"""

from __future__ import annotations

import json
import sys
import types
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

sys.modules.setdefault("fire", types.SimpleNamespace(Fire=lambda *a, **k: None))
sys.modules.setdefault("firecrawl", types.SimpleNamespace(Firecrawl=object))
sys.modules.setdefault("fal_client", types.SimpleNamespace())

try:
    from tests.run_agent.golden_harness import (
        GOLDEN_SESSION_ID,
        GOLDEN_TASK_ID,
        _ScriptedTransport,
        _ToolStub,
        _chat_response,
        _patches,
        _ScriptedClock,
        replay_transcript,
    )
except ImportError:
    from golden_harness import (
        GOLDEN_SESSION_ID,
        GOLDEN_TASK_ID,
        _ScriptedTransport,
        _ToolStub,
        _chat_response,
        _patches,
        _ScriptedClock,
        replay_transcript,
    )

from agent.usage_events import (
    UsageEvent,
    UsageLedger,
)
from agent.usage_pricing import BillingRoute, CanonicalUsage, CostResult


GOLDEN_DIR = Path(__file__).parent / "golden"


class _RecordingSink:
    """Collects UsageEvents for assertion; also acts as a UsageEventSink."""

    def __init__(self) -> None:
        self.events: List[UsageEvent] = []

    def on_attempt(self, event: UsageEvent) -> None:
        self.events.append(event)


# ── Tests ────────────────────────────────────────────────────────────────────


def test_usage_event_sink_plain_text():
    """A plain-text graph turn fires exactly one usage event via the sink."""
    import run_agent

    fixture_path = GOLDEN_DIR / "plain_text.json"
    spec = json.loads(fixture_path.read_text(encoding="utf-8"))

    cfg = spec.get("agent", {})
    api_mode = cfg.get("api_mode", "chat_completions")
    # Use a deterministic official-pricing route so this integration test
    # proves the emitter produces a numeric CostResult, not only rich fields.
    model = "gpt-4o"
    provider = "openai"
    base_url = cfg.get("base_url", "https://api.openai.com/v1")

    transport = _ScriptedTransport(
        spec.get("model_turns", []), _chat_response, model
    )
    sink = _RecordingSink()
    tool_stub = _ToolStub({})

    with _patches(
        spec.get("tools", []), tool_stub, api_mode
    ) as _hook_recorder:
        agent = run_agent.AIAgent(
            api_key="golden-key",
            base_url=base_url,
            provider=provider,
            api_mode=api_mode,
            model=model,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            usage_sink=sink,
        )
        agent.session_id = GOLDEN_SESSION_ID
        agent._disable_streaming = True
        agent._session_db = MagicMock()
        agent._save_session_log = lambda *a, **k: None
        agent._save_trajectory = lambda *a, **k: None

        transport.agent = agent
        agent._interruptible_api_call = transport

        clock = _ScriptedClock()
        with (
            patch.object(run_agent.time, "time", clock.time),
            patch.object(run_agent.time, "sleep", clock.sleep),
            patch.object(
                run_agent,
                "jittered_backoff",
                lambda *a, **k: 0.1,
            ),
        ):
            result = agent._run_conversation_graph(
                spec["user_message"],
                task_id=GOLDEN_TASK_ID,
            )

    # Assert the result looks like a plain-text reply
    assert result.get("final_response") == "Hello! How can I help you today?"
    assert result.get("completed") is True

    # Assert exactly one transport attempt was made
    assert transport.calls == 1

    # Assert exactly one usage event was recorded
    assert len(sink.events) == 1, f"Expected 1 usage event, got {len(sink.events)}"
    event = sink.events[0]

    # Event fields
    assert event.attempt_index == 0
    assert event.outcome == "success"
    assert event.route == "call_transport"
    assert event.provider == "openai"
    assert event.model == "gpt-4o"
    assert event.input_tokens == 50
    assert event.output_tokens == 8
    assert event.billing_route.billing_mode == "official_docs_snapshot"
    assert event.usage == CanonicalUsage(input_tokens=50, output_tokens=8)
    assert event.cost.status == "estimated"
    assert event.cost.source == "official_docs_snapshot"
    assert event.cost.amount_usd is not None
    assert event.cost.amount_usd > Decimal("0")


def test_usage_ledger_snapshot():
    """UsageLedger.snapshot() with all-known-cost events is complete."""
    ledger = UsageLedger()
    ledger.record(
        UsageEvent(
            attempt_index=0,
            outcome="success",
            route="call_transport",
            billing_route=BillingRoute(provider="test", model="test-model"),
            usage=CanonicalUsage(input_tokens=100, output_tokens=50),
            cost=CostResult(
                amount_usd=Decimal("0.005"),
                status="estimated",
                source="official_docs_snapshot",
                label="~$0.01",
                pricing_version="v1",
            ),
        )
    )
    snap = ledger.snapshot()
    assert snap.complete is True
    assert snap.total_cost == Decimal("0.005")
    assert len(snap.events) == 1


def test_usage_ledger_unknown_cost_incomplete():
    """UsageLedger with any unknown-cost event makes snapshot incomplete."""
    ledger = UsageLedger()
    ledger.record(
        UsageEvent(
            attempt_index=0,
            outcome="transport_error",
            route="call_transport",
            billing_route=BillingRoute(provider="test", model="test-model"),
            usage=None,
            cost=CostResult(
                amount_usd=None,
                status="unknown",
                source="none",
                label="n/a",
            ),
        )
    )
    snap = ledger.snapshot()
    assert snap.complete is False
    assert snap.total_cost is None


# ── Review remediation: per-attempt index (P1-4), aux usage (P1-3), and
#    engine-neutral loop emission (PH35-FU-007). ──────────────────────────────


def _events_for(fixture: str) -> List[UsageEvent]:
    spec = json.loads((GOLDEN_DIR / fixture).read_text(encoding="utf-8"))
    sink = _RecordingSink()
    replay_transcript(spec, usage_sink=sink)
    return sink.events


def test_attempt_index_is_unique_and_monotonic_across_retries():
    """Review P1-4: each transport attempt gets a distinct, monotonic index.

    The graph previously set ``attempt_index = state["api_call_count"]`` — a
    per-model-turn counter — so consecutive retries within one model turn
    collided (observed ``[0, 1, 1]``).  ``exit_api_retries`` drives the retry
    ladder to exhaustion, so it emits several attempts in one turn.
    """
    events = _events_for("exit_api_retries.json")
    indices = [e.attempt_index for e in events]
    assert len(indices) >= 2, f"expected multiple transport attempts, got {indices}"
    assert indices == list(range(len(indices))), (
        f"attempt_index must be unique + monotonic 0..n-1, got {indices}"
    )


def test_aux_summary_event_records_real_usage():
    """Review P1-3: the max-iteration summary event carries the real aux-call
    usage, not a ``response=None`` placeholder (which lost the tokens)."""
    events = _events_for("max_iterations.json")
    summary = [e for e in events if e.route == "summarize_on_budget"]
    assert len(summary) >= 1, f"no summary usage event; routes={[e.route for e in events]}"
    ev = summary[0]
    assert ev.usage is not None, "summary event lost the real aux-call usage"
    # max_iterations.json's summary_response declares prompt=150, completion=14.
    assert ev.input_tokens == 150, ev.input_tokens
    assert ev.output_tokens == 14, ev.output_tokens


def test_graph_emits_a_complete_success_event():
    events = _events_for("plain_text.json")

    assert len(events) == 1, [e.outcome for e in events]
    event = events[0]
    assert event.attempt_index == 0
    assert event.outcome == "success"
    assert event.route == "call_transport"
    assert event.usage is not None
    assert event.cost.status in {"actual", "estimated", "included", "unknown"}


@pytest.mark.parametrize(
    "fixture",
    [
        "exit_api_retries.json",         # transport_error ladder to exhaustion
        "exit_invalid_response.json",    # invalid_response (None) retries
        "exit_nonretryable_client.json", # single transport_error
        "exit_payload_compression.json", # 413 payload-too-large compression events
        "exit_context_stepdown.json",    # context-overflow step-down compression
    ],
)
def test_graph_emits_error_path_events(fixture):
    sequence = [(e.outcome, e.route) for e in _events_for(fixture)]
    # Guard: the fixture must actually exercise an error path, else it is not
    # testing FU-007 (a success-only sequence would pass vacuously).
    assert any(outcome != "success" for outcome, _ in sequence), (
        f"{fixture} emitted no error-path usage event: {sequence}"
    )


def test_recorder_is_noop_without_sink():
    """The engine-neutral recorder must not touch the counter or result when no
    sink is configured (so sink-less production callers pay nothing)."""
    import run_agent

    with _patches([], _ToolStub({}), "chat_completions"):
        agent = run_agent.AIAgent(
            api_key="k", base_url="https://api.openai.com/v1", provider="openai",
            api_mode="chat_completions", model="gpt-4o", quiet_mode=True,
            skip_context_files=True, skip_memory=True,  # no usage_sink
        )
    assert agent._usage_sink is None
    agent._record_usage_attempt(outcome="success", response=None)
    assert agent._usage_attempt_index == 0  # counter did not advance
