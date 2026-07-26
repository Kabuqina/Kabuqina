# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Phase 3.5: engine-neutral per-transport-attempt usage and cost events.

No LangGraph imports.  The optional sink is additive and cannot alter the
frozen ``LegacyRunResult`` dictionary.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import logging
import re
from typing import Protocol

from agent.knowledge_post_node import strip_legacy_kq_kp_blocks
from agent.usage_pricing import BillingRoute, CanonicalUsage, CostResult


logger = logging.getLogger(__name__)
_COMPLETE_COST_STATUSES = {"actual", "estimated", "included"}
_CHECK_QUESTION_ENDINGS = ("?", "？")


# ── Event ────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class LearningConductMetrics:
    """Cheap per-assistant-turn signals for the learning conduct contract."""
    assistant_chars: int
    assistant_words: int
    ends_with_check_question: bool
    kq_kp_emitted: bool
    answer_then_teach_covered: bool


def analyze_learning_conduct_text(text: str | None) -> LearningConductMetrics | None:
    """Extract low-cost learning-conduct telemetry from assistant text."""
    if not isinstance(text, str):
        return None

    visible_text, kq_kp_emitted = strip_legacy_kq_kp_blocks(text)
    if not visible_text and not kq_kp_emitted:
        return None

    return LearningConductMetrics(
        assistant_chars=len(visible_text),
        assistant_words=len(re.findall(r"\S+", visible_text)),
        ends_with_check_question=visible_text.rstrip().endswith(_CHECK_QUESTION_ENDINGS),
        kq_kp_emitted=kq_kp_emitted,
        answer_then_teach_covered=bool(kq_kp_emitted and visible_text),
    )


@dataclass(frozen=True, slots=True)
class UsageEvent:
    """One transport attempt with canonical usage and its billing result.

    *attempt_index* is zero-based within a single turn.
    """
    attempt_index: int
    outcome: str                     # "success" | "transport_error" | "invalid_response" | ...
    route: str                       # e.g. "call_transport", "summarize_on_budget"
    billing_route: BillingRoute
    usage: CanonicalUsage | None
    cost: CostResult
    conduct: LearningConductMetrics | None = None

    @property
    def provider(self) -> str:
        """Compatibility view of the active billing provider."""
        return self.billing_route.provider

    @property
    def model(self) -> str:
        """Compatibility view of the active billing model."""
        return self.billing_route.model

    @property
    def input_tokens(self) -> int | None:
        return self.usage.input_tokens if self.usage is not None else None

    @property
    def output_tokens(self) -> int | None:
        return self.usage.output_tokens if self.usage is not None else None

    @property
    def pricing_version(self) -> str | None:
        return self.cost.pricing_version

    @property
    def cost_amount(self) -> Decimal | None:
        return self.cost.amount_usd

    @property
    def cost_currency(self) -> str | None:
        return "USD" if self.cost.amount_usd is not None else None


# ── Sink protocol ────────────────────────────────────────────────────────

class UsageEventSink(Protocol):
    """Optional side-channel that receives every transport-attempt event.

    Exceptions raised by the sink are logged and must not change the agent
    result or retry path.
    """
    def on_attempt(self, event: UsageEvent) -> None: ...


# ── Ledger ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class UsageSnapshot:
    """Immutable view of a completed (or abandoned) turn's usage ledger."""
    complete: bool
    total_cost: Decimal | None       # None when any event has unknown cost
    events: tuple[UsageEvent, ...] = ()


class UsageLedger:
    """In-memory collector and optional sink for per-attempt usage events.

    Scoped to one synchronously recorded turn; not designed for cross-turn reuse.
    """

    def __init__(self, sink: UsageEventSink | None = None) -> None:
        self._events: list[UsageEvent] = []
        self._sink = sink
        self._has_unknown: bool = False

    def record(self, event: UsageEvent) -> None:
        """Append an event and forward it to the optional sink."""
        self._events.append(event)
        if (
            event.usage is None
            or event.cost.amount_usd is None
            or event.cost.status not in _COMPLETE_COST_STATUSES
        ):
            self._has_unknown = True
        if self._sink is not None:
            try:
                self._sink.on_attempt(event)
            except Exception:
                logger.warning("usage event sink failed", exc_info=True)

    def on_attempt(self, event: UsageEvent) -> None:
        """Implement ``UsageEventSink`` by recording the attempt locally."""
        self.record(event)

    def snapshot(self) -> UsageSnapshot:
        """Return a stable view of the current ledger.

        *complete* is ``True`` when every recorded attempt has a known
        numeric cost.  *total_cost* is ``None`` when the ledger is
        incomplete.
        """
        if self._has_unknown:
            return UsageSnapshot(
                complete=False, total_cost=None, events=tuple(self._events)
            )
        total = sum(
            (
                event.cost.amount_usd
                for event in self._events
                if event.cost.amount_usd is not None
            ),
            Decimal("0.00"),
        )
        return UsageSnapshot(
            complete=True, total_cost=total, events=tuple(self._events)
        )
