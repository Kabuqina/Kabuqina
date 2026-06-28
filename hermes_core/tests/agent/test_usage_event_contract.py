# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Phase 3.5 Task 3: usage event ledger contract invariants."""

from __future__ import annotations

from decimal import Decimal

import pytest


# ── Zero-attempts → complete zero cost ───────────────────────────────────

def test_zero_attempts_is_complete_zero_cost():
    """A ledger with zero attempts must report complete with zero total cost."""
    from agent.usage_events import UsageLedger

    ledger = UsageLedger()
    snapshot = ledger.snapshot()
    assert snapshot.complete is True
    assert snapshot.total_cost == Decimal("0.00")
    assert len(snapshot.events) == 0


# ── Numeric cost aggregation ─────────────────────────────────────────────

def test_numeric_amounts_sum_exactly():
    """Numeric amount aggregation must use Decimal for exact sums."""
    from agent.usage_events import UsageEvent, UsageLedger

    ledger = UsageLedger()
    ledger.record(
        UsageEvent(
            attempt_index=0,
            outcome="success",
            route="call_transport",
            provider="openai",
            model="gpt-4o",
            input_tokens=100,
            output_tokens=50,
            pricing_version="v1",
            cost_amount=Decimal("0.015"),
            cost_currency="USD",
        )
    )
    ledger.record(
        UsageEvent(
            attempt_index=1,
            outcome="success",
            route="call_transport",
            provider="openai",
            model="gpt-4o",
            input_tokens=200,
            output_tokens=100,
            pricing_version="v1",
            cost_amount=Decimal("0.030"),
            cost_currency="USD",
        )
    )
    snapshot = ledger.snapshot()
    assert snapshot.complete is True
    assert snapshot.total_cost == Decimal("0.045")


# ── Missing usage → incomplete ───────────────────────────────────────────

def test_missing_usage_makes_snapshot_incomplete():
    """A single unknown-cost attempt makes the entire snapshot incomplete."""
    from agent.usage_events import UsageEvent, UsageLedger

    ledger = UsageLedger()
    # First event with known cost
    ledger.record(
        UsageEvent(
            attempt_index=0,
            outcome="success",
            route="call_transport",
            provider="openai",
            model="gpt-4o",
            input_tokens=100,
            output_tokens=50,
            pricing_version="v1",
            cost_amount=Decimal("0.015"),
            cost_currency="USD",
        )
    )
    # Second event with unknown cost
    ledger.record(
        UsageEvent(
            attempt_index=1,
            outcome="transport_error",
            route="call_transport",
            provider=None,
            model=None,
            input_tokens=None,
            output_tokens=None,
            pricing_version=None,
            cost_amount=None,
            cost_currency=None,
        )
    )
    snapshot = ledger.snapshot()
    assert snapshot.complete is False
    assert snapshot.total_cost is None  # incomplete → no aggregate
    assert len(snapshot.events) == 2


# ── Unknown pricing → incomplete ─────────────────────────────────────────

def test_unknown_pricing_makes_snapshot_incomplete():
    """A successful attempt with unknown pricing makes the snapshot incomplete."""
    from agent.usage_events import UsageEvent, UsageLedger

    ledger = UsageLedger()
    ledger.record(
        UsageEvent(
            attempt_index=0,
            outcome="success",
            route="call_transport",
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            input_tokens=500,
            output_tokens=200,
            pricing_version=None,  # unknown pricing
            cost_amount=None,
            cost_currency=None,
        )
    )
    snapshot = ledger.snapshot()
    assert snapshot.complete is False
    assert snapshot.total_cost is None


# ── Event sequence preserved ─────────────────────────────────────────────

def test_event_sequence_is_preserved():
    """Events must be returned in insertion order."""
    from agent.usage_events import UsageEvent, UsageLedger

    ledger = UsageLedger()
    for i in range(5):
        ledger.record(
            UsageEvent(
                attempt_index=i,
                outcome="success",
                route="call_transport",
                provider="test",
                model="test",
                input_tokens=10,
                output_tokens=5,
                pricing_version="v1",
                cost_amount=Decimal("0.001") * i,
                cost_currency="USD",
            )
        )
    snapshot = ledger.snapshot()
    assert [e.attempt_index for e in snapshot.events] == [0, 1, 2, 3, 4]
