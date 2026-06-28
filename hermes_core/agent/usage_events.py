# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Phase 3.5: engine-neutral per-transport-attempt usage and cost events.

No LangGraph imports.  The optional sink is additive and cannot alter the
frozen ``LegacyRunResult`` dictionary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol


# ── Event ────────────────────────────────────────────────────────────────

@dataclass(slots=True)
class UsageEvent:
    """One transport attempt with its canonical usage and optional cost.

    *attempt_index* is zero-based within a single turn.
    """
    attempt_index: int
    outcome: str                     # "success" | "transport_error" | "invalid_response" | ...
    route: str                       # e.g. "call_transport", "summarize_on_budget"
    provider: str | None
    model: str | None
    input_tokens: int | None
    output_tokens: int | None
    pricing_version: str | None      # None → unknown pricing
    cost_amount: Decimal | None      # None → unknown cost
    cost_currency: str | None


# ── Sink protocol ────────────────────────────────────────────────────────

class UsageEventSink(Protocol):
    """Optional side-channel that receives every transport-attempt event.

    Exceptions raised by the sink are logged and must not change the agent
    result or retry path.
    """
    def on_attempt(self, event: UsageEvent) -> None: ...


# ── Ledger ───────────────────────────────────────────────────────────────

@dataclass
class UsageSnapshot:
    """Immutable view of a completed (or abandoned) turn's usage ledger."""
    complete: bool
    total_cost: Decimal | None       # None when any event has unknown cost
    events: list[UsageEvent] = field(default_factory=list)


class UsageLedger:
    """In-memory collector and optional sink for per-attempt usage events.

    Thread-safe for a single turn; not designed for cross-turn reuse.
    """

    def __init__(self, sink: UsageEventSink | None = None) -> None:
        self._events: list[UsageEvent] = []
        self._sink = sink
        self._has_unknown: bool = False

    def record(self, event: UsageEvent) -> None:
        """Append an event and forward it to the optional sink."""
        self._events.append(event)
        if event.cost_amount is None or event.pricing_version is None:
            self._has_unknown = True
        if self._sink is not None:
            self._sink.on_attempt(event)

    def snapshot(self) -> UsageSnapshot:
        """Return a stable view of the current ledger.

        *complete* is ``True`` when every recorded attempt has a known
        numeric cost.  *total_cost* is ``None`` when the ledger is
        incomplete.
        """
        if self._has_unknown:
            return UsageSnapshot(complete=False, total_cost=None, events=list(self._events))
        total = sum(
            (e.cost_amount for e in self._events if e.cost_amount is not None),
            Decimal("0.00"),
        )
        return UsageSnapshot(complete=True, total_cost=total, events=list(self._events))
