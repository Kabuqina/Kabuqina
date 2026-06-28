"""Tests for the engine-neutral goal usage summary (Bounded Goal Runner Task 1).

``summarize_usage_events`` is the persisted view of Phase 3.5's usage-event
stream. The hard rule under test: an aggregate cost is only available when
*every* attempted request carries a numeric ``actual``/``estimated``/``included``
event. Any unknown event makes the aggregate ``None`` and ``complete=False`` —
known events are never summed while an unknown one is silently discarded.

No events at all is a complete zero-cost iteration (no transport attempt made).
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest


def _ev(
    amount,
    cost_status,
    *,
    attempt=0,
    outcome="response",
):
    from cron.goal_usage import GoalUsageEvent

    return GoalUsageEvent(
        attempt_index=attempt,
        outcome=outcome,
        provider="anthropic",
        model="claude-opus-4-8",
        api_mode="messages",
        input_tokens=10,
        output_tokens=5,
        cache_read_tokens=0,
        cache_write_tokens=0,
        reasoning_tokens=0,
        amount_usd=amount,
        cost_status=cost_status,
        cost_source="ledger",
        pricing_version="2026-06-01",
    )


class TestSummarize:
    def test_no_events_is_complete_zero(self):
        from cron.goal_usage import summarize_usage_events

        snap = summarize_usage_events([])
        assert snap.events == ()
        assert snap.amount_usd == Decimal("0")
        assert snap.complete is True
        assert snap.incomplete_reason is None

    def test_multiple_known_events_sum(self):
        from cron.goal_usage import summarize_usage_events

        snap = summarize_usage_events(
            [_ev(Decimal("0.10"), "actual", attempt=0),
             _ev(Decimal("0.20"), "estimated", attempt=1)]
        )
        assert snap.amount_usd == Decimal("0.30")
        assert snap.complete is True
        assert snap.incomplete_reason is None

    def test_included_route_contributes_zero_and_stays_complete(self):
        from cron.goal_usage import summarize_usage_events

        snap = summarize_usage_events(
            [_ev(Decimal("0.05"), "actual", attempt=0),
             _ev(None, "included", attempt=1)]
        )
        assert snap.amount_usd == Decimal("0.05")
        assert snap.complete is True

    def test_exact_decimal_addition(self):
        from cron.goal_usage import summarize_usage_events

        snap = summarize_usage_events(
            [_ev(Decimal("0.1"), "actual", attempt=0),
             _ev(Decimal("0.2"), "actual", attempt=1)]
        )
        assert snap.amount_usd == Decimal("0.3")

    def test_mixed_known_and_unknown_is_unavailable(self):
        from cron.goal_usage import summarize_usage_events

        snap = summarize_usage_events(
            [_ev(Decimal("0.10"), "actual", attempt=0),
             _ev(None, "unknown", attempt=1)]
        )
        # Never sum the known event and silently drop the unknown one.
        assert snap.amount_usd is None
        assert snap.complete is False
        assert snap.incomplete_reason is not None

    def test_missing_usage_is_unavailable(self):
        from cron.goal_usage import summarize_usage_events

        # An attempted request whose amount is missing despite a numeric status.
        snap = summarize_usage_events([_ev(None, "actual", attempt=0)])
        assert snap.amount_usd is None
        assert snap.complete is False
        assert snap.incomplete_reason is not None

    def test_unknown_pricing_is_unavailable(self):
        from cron.goal_usage import summarize_usage_events

        snap = summarize_usage_events([_ev(None, "unknown", attempt=0)])
        assert snap.amount_usd is None
        assert snap.complete is False
        assert snap.incomplete_reason is not None


class TestJsonRoundTrip:
    def test_snapshot_round_trip(self):
        from cron.goal_usage import (
            summarize_usage_events,
            usage_snapshot_from_json,
            usage_snapshot_to_json,
        )

        snap = summarize_usage_events(
            [_ev(Decimal("0.10"), "actual", attempt=0),
             _ev(None, "included", attempt=1)]
        )
        payload = usage_snapshot_to_json(snap)
        # Must be plain-JSON serializable (decimals already stringified).
        text = json.dumps(payload)
        restored = usage_snapshot_from_json(json.loads(text))
        assert restored == snap

    def test_incomplete_snapshot_round_trip(self):
        from cron.goal_usage import (
            summarize_usage_events,
            usage_snapshot_from_json,
            usage_snapshot_to_json,
        )

        snap = summarize_usage_events([_ev(None, "unknown", attempt=0)])
        restored = usage_snapshot_from_json(
            json.loads(json.dumps(usage_snapshot_to_json(snap)))
        )
        assert restored == snap
        assert restored.amount_usd is None
        assert restored.complete is False
