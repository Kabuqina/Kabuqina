"""Engine-neutral persisted view of the per-iteration usage-event stream.

This module is part of the Bounded Goal Runner G0 foundation. It does not import
LangGraph, the inner agent, or any provider SDK. It defines the durable shape of
the usage events that Phase 3.5's usage sink records, and the rule that turns a
sequence of those events into an aggregate cost for one goal iteration.

The cost rule is deliberately conservative:

* No events at all means a *complete* zero-cost iteration — no transport attempt
  was made, so there is nothing to charge.
* Every attempted request must carry a numeric ``actual``/``estimated`` amount or
  be explicitly ``included`` (bundled, no marginal charge). If any event is
  ``unknown`` (missing pricing) or lacks an amount despite a numeric status, the
  aggregate amount is ``None`` and the snapshot is incomplete.
* Known events are never summed while an unknown one is silently discarded — an
  incomplete ledger pauses the goal before verification or completion rather than
  charging unknown cost as zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Sequence

__all__ = [
    "GoalUsageEvent",
    "GoalUsageSnapshot",
    "summarize_usage_events",
    "usage_event_to_json",
    "usage_event_from_json",
    "usage_snapshot_to_json",
    "usage_snapshot_from_json",
]

UsageOutcome = Literal["response", "invalid_response", "transport_error"]
CostStatus = Literal["actual", "estimated", "included", "unknown"]


@dataclass(frozen=True)
class GoalUsageEvent:
    """One transport attempt's usage and cost, as recorded by the usage sink."""

    attempt_index: int
    outcome: UsageOutcome
    provider: str
    model: str
    api_mode: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    reasoning_tokens: int
    amount_usd: Decimal | None
    cost_status: CostStatus
    cost_source: str
    pricing_version: str | None


@dataclass(frozen=True)
class GoalUsageSnapshot:
    """Aggregate cost for one iteration, or an explicit incomplete ledger."""

    events: tuple[GoalUsageEvent, ...]
    amount_usd: Decimal | None
    complete: bool
    incomplete_reason: str | None


def summarize_usage_events(
    events: Sequence[GoalUsageEvent],
) -> GoalUsageSnapshot:
    """Aggregate per-attempt usage events into a single iteration snapshot.

    Returns a complete zero-cost snapshot when there were no attempts. Returns
    an incomplete snapshot (``amount_usd=None``) the moment any event cannot be
    priced, without summing the events that could be.
    """
    events = tuple(events)
    if not events:
        return GoalUsageSnapshot(
            events=(), amount_usd=Decimal("0"), complete=True, incomplete_reason=None
        )

    if any(type(event.attempt_index) is not int for event in events) or tuple(
        event.attempt_index for event in events
    ) != tuple(range(len(events))):
        return GoalUsageSnapshot(
            events=events,
            amount_usd=None,
            complete=False,
            incomplete_reason="invalid_attempt_sequence",
        )

    if any(
        event.amount_usd is not None
        and (
            not isinstance(event.amount_usd, Decimal)
            or not event.amount_usd.is_finite()
            or event.amount_usd < 0
        )
        for event in events
    ):
        return GoalUsageSnapshot(
            events=events,
            amount_usd=None,
            complete=False,
            incomplete_reason="invalid_amount",
        )

    total = Decimal("0")
    complete = True
    incomplete_reason: str | None = None

    for event in events:
        if event.cost_status == "included":
            # Bundled route — no marginal charge. Honour any explicit amount.
            total += event.amount_usd if event.amount_usd is not None else Decimal("0")
            continue
        if event.cost_status in ("actual", "estimated"):
            if event.amount_usd is None:
                complete = False
                if incomplete_reason is None:
                    incomplete_reason = "missing_amount"
                continue
            total += event.amount_usd
            continue
        # cost_status == "unknown": pricing could not be resolved.
        complete = False
        if incomplete_reason is None:
            incomplete_reason = "unknown_cost"

    if not complete:
        return GoalUsageSnapshot(
            events=events,
            amount_usd=None,
            complete=False,
            incomplete_reason=incomplete_reason,
        )
    return GoalUsageSnapshot(
        events=events, amount_usd=total, complete=True, incomplete_reason=None
    )


# ---------------------------------------------------------------------------
# JSON (de)serialization — decimals are persisted as strings.
# ---------------------------------------------------------------------------

def _decimal_to_json(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _decimal_from_json(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def usage_event_to_json(event: GoalUsageEvent) -> dict:
    return {
        "attempt_index": event.attempt_index,
        "outcome": event.outcome,
        "provider": event.provider,
        "model": event.model,
        "api_mode": event.api_mode,
        "input_tokens": event.input_tokens,
        "output_tokens": event.output_tokens,
        "cache_read_tokens": event.cache_read_tokens,
        "cache_write_tokens": event.cache_write_tokens,
        "reasoning_tokens": event.reasoning_tokens,
        "amount_usd": _decimal_to_json(event.amount_usd),
        "cost_status": event.cost_status,
        "cost_source": event.cost_source,
        "pricing_version": event.pricing_version,
    }


def usage_event_from_json(data: dict) -> GoalUsageEvent:
    return GoalUsageEvent(
        attempt_index=int(data["attempt_index"]),
        outcome=data["outcome"],
        provider=data["provider"],
        model=data["model"],
        api_mode=data["api_mode"],
        input_tokens=int(data["input_tokens"]),
        output_tokens=int(data["output_tokens"]),
        cache_read_tokens=int(data["cache_read_tokens"]),
        cache_write_tokens=int(data["cache_write_tokens"]),
        reasoning_tokens=int(data["reasoning_tokens"]),
        amount_usd=_decimal_from_json(data.get("amount_usd")),
        cost_status=data["cost_status"],
        cost_source=data["cost_source"],
        pricing_version=data.get("pricing_version"),
    )


def usage_snapshot_to_json(snapshot: GoalUsageSnapshot) -> dict:
    return {
        "events": [usage_event_to_json(e) for e in snapshot.events],
        "amount_usd": _decimal_to_json(snapshot.amount_usd),
        "complete": snapshot.complete,
        "incomplete_reason": snapshot.incomplete_reason,
    }


def usage_snapshot_from_json(data: dict) -> GoalUsageSnapshot:
    return GoalUsageSnapshot(
        events=tuple(usage_event_from_json(e) for e in data.get("events", [])),
        amount_usd=_decimal_from_json(data.get("amount_usd")),
        complete=bool(data["complete"]),
        incomplete_reason=data.get("incomplete_reason"),
    )
