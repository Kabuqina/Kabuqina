# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Phase 3.5 Task 3: usage event ledger contract invariants."""

from __future__ import annotations

from decimal import Decimal

def _rich_event(
    *,
    attempt_index: int = 0,
    amount: Decimal | None = Decimal("0.015"),
    status: str = "estimated",
    include_usage: bool = True,
):
    from agent.usage_events import UsageEvent
    from agent.usage_pricing import BillingRoute, CanonicalUsage, CostResult

    billing_route = BillingRoute(
        provider="openai",
        model="gpt-4o",
        base_url="https://api.openai.com/v1",
        billing_mode="official_docs_snapshot",
    )
    usage = (
        CanonicalUsage(
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=20,
            cache_write_tokens=10,
            reasoning_tokens=5,
        )
        if include_usage
        else None
    )
    cost = CostResult(
        amount_usd=amount,
        status=status,
        source="official_docs_snapshot" if status != "included" else "none",
        label="included" if status == "included" else "~$0.02",
        pricing_version="v1" if status != "included" else "included-route",
    )
    event = UsageEvent(
        attempt_index=attempt_index,
        outcome="success",
        route="call_transport",
        billing_route=billing_route,
        usage=usage,
        cost=cost,
    )
    return event, billing_route, usage, cost


def test_usage_event_preserves_rich_billing_contract():
    event, billing_route, usage, cost = _rich_event()

    assert event.billing_route is billing_route
    assert event.usage is usage
    assert event.cost is cost
    assert event.provider == "openai"
    assert event.model == "gpt-4o"
    assert event.input_tokens == 100
    assert event.output_tokens == 50
    assert event.pricing_version == "v1"
    assert event.cost_amount == Decimal("0.015")
    assert event.cost_currency == "USD"
    assert event.usage.cache_read_tokens == 20
    assert event.usage.cache_write_tokens == 10
    assert event.usage.reasoning_tokens == 5
    assert event.conduct is None


def test_learning_conduct_metrics_capture_text_shape_and_protocol():
    from agent.usage_events import analyze_learning_conduct_text

    text = (
        "答案是 42。\n\n"
        "你可以先想想为什么单位会抵消？\n\n"
        "```kq-kp\n"
        "[{\"name\":\"单位分析\",\"gist\":\"检查单位能暴露公式错配。\",\"confidence\":\"confirmed\"}]\n"
        "```"
    )

    metrics = analyze_learning_conduct_text(text)

    assert metrics is not None
    assert metrics.assistant_chars == len("答案是 42。\n\n你可以先想想为什么单位会抵消？")
    assert metrics.assistant_words == 3
    assert metrics.ends_with_check_question is True
    assert metrics.kq_kp_emitted is True
    assert metrics.answer_then_teach_covered is True


def test_usage_event_can_carry_learning_conduct_metrics():
    from agent.usage_events import analyze_learning_conduct_text

    metrics = analyze_learning_conduct_text("Short answer?")
    event, *_ = _rich_event()
    enriched = type(event)(
        attempt_index=event.attempt_index,
        outcome=event.outcome,
        route=event.route,
        billing_route=event.billing_route,
        usage=event.usage,
        cost=event.cost,
        conduct=metrics,
    )

    assert enriched.conduct is metrics


def test_ledger_is_a_sink_and_downstream_errors_do_not_escape():
    from agent.usage_events import UsageLedger

    class RaisingSink:
        def on_attempt(self, event):
            raise RuntimeError("observer failed")

    event, *_ = _rich_event()
    ledger = UsageLedger(sink=RaisingSink())

    ledger.on_attempt(event)

    snapshot = ledger.snapshot()
    assert snapshot.events == (event,)
    assert snapshot.complete is True
    assert snapshot.total_cost == Decimal("0.015")


def test_actual_estimated_and_included_costs_sum_exactly():
    from agent.usage_events import UsageLedger

    ledger = UsageLedger()
    for event in (
        _rich_event(attempt_index=0, amount=Decimal("0.10"), status="actual")[0],
        _rich_event(attempt_index=1, amount=Decimal("0.20"), status="estimated")[0],
        _rich_event(attempt_index=2, amount=Decimal("0"), status="included")[0],
    ):
        ledger.on_attempt(event)

    snapshot = ledger.snapshot()
    assert snapshot.complete is True
    assert snapshot.total_cost == Decimal("0.30")


def test_missing_usage_is_incomplete_even_with_known_zero_amount():
    from agent.usage_events import UsageLedger

    event, *_ = _rich_event(
        amount=Decimal("0"), status="included", include_usage=False
    )
    ledger = UsageLedger()
    ledger.on_attempt(event)

    snapshot = ledger.snapshot()
    assert snapshot.complete is False
    assert snapshot.total_cost is None


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
    from agent.usage_events import UsageLedger

    ledger = UsageLedger()
    ledger.record(_rich_event(attempt_index=0, amount=Decimal("0.015"))[0])
    ledger.record(_rich_event(attempt_index=1, amount=Decimal("0.030"))[0])
    snapshot = ledger.snapshot()
    assert snapshot.complete is True
    assert snapshot.total_cost == Decimal("0.045")


# ── Missing usage → incomplete ───────────────────────────────────────────

def test_missing_usage_makes_snapshot_incomplete():
    """A single unknown-cost attempt makes the entire snapshot incomplete."""
    from agent.usage_events import UsageLedger

    ledger = UsageLedger()
    # First event with known cost
    ledger.record(_rich_event(attempt_index=0)[0])
    # Second event with unknown cost
    ledger.record(
        _rich_event(
            attempt_index=1,
            amount=None,
            status="unknown",
            include_usage=False,
        )[0]
    )
    snapshot = ledger.snapshot()
    assert snapshot.complete is False
    assert snapshot.total_cost is None  # incomplete → no aggregate
    assert len(snapshot.events) == 2


# ── Unknown pricing → incomplete ─────────────────────────────────────────

def test_unknown_pricing_makes_snapshot_incomplete():
    """A successful attempt with unknown pricing makes the snapshot incomplete."""
    from agent.usage_events import UsageLedger

    ledger = UsageLedger()
    ledger.record(_rich_event(amount=None, status="unknown")[0])
    snapshot = ledger.snapshot()
    assert snapshot.complete is False
    assert snapshot.total_cost is None


# ── Event sequence preserved ─────────────────────────────────────────────

def test_event_sequence_is_preserved():
    """Events must be returned in insertion order."""
    from agent.usage_events import UsageLedger

    ledger = UsageLedger()
    for i in range(5):
        ledger.record(
            _rich_event(attempt_index=i, amount=Decimal("0.001") * i)[0]
        )
    snapshot = ledger.snapshot()
    assert [e.attempt_index for e in snapshot.events] == [0, 1, 2, 3, 4]
