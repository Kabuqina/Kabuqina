# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""G1 Task 7: a thin adapter from one bounded goal iteration to the public agent.

This module connects the engine-neutral Goal Runner controller to the product's
`AIAgent` through its *public* ``run_conversation`` seam. It is deliberately
narrow:

* It never imports ``langgraph``, ``agent.graph_engine``, ``GraphEngine``, or a
  graph node, and it never calls ``_run_conversation_loop`` /
  ``_run_conversation_graph`` directly. Which engine actually runs is the
  selector's decision, propagated as an explicit ``agent_engine``.
* Cost is measured by an injected per-attempt :class:`UsageLedger`, never
  inferred from the presence or absence of result-dict keys. Any attempt whose
  cost is unknown yields an *incomplete* snapshot so the controller pauses
  before it can verify or complete on an unpriced iteration.
* A ``goal_report`` is evidence submitted through the iteration-scoped internal
  tool, not a return value. A missing report is reported as ``report=None``; the
  adapter never infers from a missing report that no tool ran.
* An exception raised *before* ``run_conversation`` is entered (agent setup)
  cannot have run a tool, so it is a safe infrastructure failure. An exception
  raised *after* entry is conservatively ``ambiguous_external_effect=True`` and
  pauses, because a tool may already have mutated external state.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Mapping

from agent.usage_events import UsageEvent, UsageLedger, UsageSnapshot
from cron.goal_report import goal_report_scope
from cron.goal_runner import WorkerObservation, _sanitized_exception
from cron.goal_state import GoalDefinition, GoalRunState
from cron.goal_usage import (
    GoalUsageEvent,
    GoalUsageSnapshot,
    summarize_usage_events,
)

__all__ = ["GoalAgentWorker", "AgentFactory"]

# The internal report toolset is always available to a goal iteration; a job's
# allowlist can only ever *add* to it, and the agent's own policy still
# intersects the result against the profile — the adapter cannot broaden it.
_GOAL_INTERNAL_TOOLSET = "goal_internal"

_OUTCOME_MAP = {
    "success": "response",
    "response": "response",
    "transport_error": "transport_error",
    "invalid_response": "invalid_response",
}
_VALID_COST_STATUSES = frozenset({"actual", "estimated", "included", "unknown"})
_COMPLETE_COST_STATUSES = frozenset({"actual", "estimated", "included"})

AgentFactory = Callable[..., Any]


def _default_agent_factory(**kwargs: Any) -> Any:
    """Lazily construct the real ``AIAgent`` through its public constructor.

    Imported lazily so this module keeps a clean engine-neutral import graph and
    tests can inject a fake factory without loading the whole agent runtime.
    """
    from run_agent import AIAgent

    return AIAgent(**kwargs)


@dataclass
class GoalAgentWorker:
    """Adapt one iteration onto ``AIAgent.run_conversation`` (loop or graph)."""

    agent_engine: str
    agent_factory: AgentFactory = _default_agent_factory
    model: str = ""
    extra_agent_kwargs: Mapping[str, Any] = field(default_factory=dict)

    def run_iteration(
        self,
        definition: GoalDefinition,
        state: GoalRunState,
    ) -> WorkerObservation:
        """Run exactly one agent turn and return an engine-neutral observation.

        ``state`` is the ``running`` state the controller already persisted, so
        ``state.iteration`` is the current (1-based) iteration number.
        """
        session_id = self._session_id(definition.job_id, state.iteration)
        system_message = self._build_system_message(definition, state)
        enabled_toolsets = self._enabled_toolsets(definition)
        ledger = UsageLedger()

        # --- Setup phase: an exception here ran no tool -> safe infra failure ---
        try:
            agent = self.agent_factory(
                model=self.model,
                session_id=session_id,
                enabled_toolsets=list(enabled_toolsets),
                usage_sink=ledger,
                agent_engine=self.agent_engine,
                **dict(self.extra_agent_kwargs),
            )
        except Exception as exc:
            return WorkerObservation(
                report=None,
                usage=summarize_usage_events(()),
                full_output="",
                wall_seconds=0.0,
                infrastructure_error=_sanitized_exception("worker_setup", exc),
                ambiguous_external_effect=False,
            )

        # --- Run phase: an exception after entry is conservatively ambiguous ---
        started = time.monotonic()
        try:
            with goal_report_scope(definition.job_id, state.iteration) as collector:
                result = agent.run_conversation(
                    user_message=definition.iteration_prompt,
                    system_message=system_message,
                )
                report = collector.report
        except Exception as exc:
            return WorkerObservation(
                report=None,
                usage=self._to_goal_usage(ledger.snapshot()),
                full_output="",
                wall_seconds=time.monotonic() - started,
                infrastructure_error=_sanitized_exception("worker_run", exc),
                ambiguous_external_effect=True,
            )

        return WorkerObservation(
            report=report,
            usage=self._to_goal_usage(ledger.snapshot()),
            full_output=_extract_output(result),
            wall_seconds=time.monotonic() - started,
            infrastructure_error=None,
            ambiguous_external_effect=False,
        )

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _session_id(job_id: str, iteration: int) -> str:
        return f"goal-{job_id}-{iteration:04d}-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _enabled_toolsets(definition: GoalDefinition) -> tuple[str, ...]:
        # De-duplicate while preserving order, then guarantee the internal
        # report toolset. The adapter only ever unions in goal_internal; it
        # cannot remove or broaden the job's declared allowlist.
        ordered = dict.fromkeys(definition.enabled_toolsets)
        ordered[_GOAL_INTERNAL_TOOLSET] = None
        return tuple(ordered)

    def _build_system_message(
        self, definition: GoalDefinition, state: GoalRunState
    ) -> str:
        limits = definition.limits
        remaining_runs = max(limits.max_runs - state.iteration, 0)
        lines = [
            "You are executing exactly one bounded iteration of a persistent "
            "Goal Task. Do the smallest correct unit of work, then report.",
            f"Objective: {definition.objective}",
            f"Current iteration: {state.iteration} of at most {limits.max_runs}.",
            f"Remaining iterations after this one: {remaining_runs}.",
        ]
        if limits.max_cost_usd is not None:
            remaining_cost = limits.max_cost_usd - state.accumulated_cost_usd
            lines.append(f"Remaining cost budget (USD): {remaining_cost}.")
        if limits.deadline is not None:
            lines.append(f"Hard deadline (UTC): {limits.deadline.isoformat()}.")
        # Compact carry-over only: a one-line summary and a fingerprint, never
        # prior raw transcripts or evidence bodies.
        if state.last_summary:
            lines.append(f"Previous iteration summary: {state.last_summary}")
        if state.last_evidence_hash:
            lines.append(f"Last evidence fingerprint: {state.last_evidence_hash}")
        if state.last_verifier_outcome:
            lines.append(
                f"Last verifier outcome: {state.last_verifier_outcome}."
            )
        lines.append(
            "Allowed working directory (every file path you touch must stay "
            f"inside it): {definition.workdir.as_posix()}"
        )
        lines.append(
            f"Completion is decided by an independent verifier "
            f"({definition.verifier_kind}); your report is evidence, not "
            "authority."
        )
        lines.append(
            "Finish by calling the goal_report tool exactly once with: status "
            "('progress' | 'candidate_done' | 'blocked'), a short summary, "
            "relative artifact paths, structured evidence (small values only — "
            "never paste large file bodies), an optional next_step, and any "
            "external_side_effects you caused."
        )
        return "\n".join(lines)

    def _to_goal_usage(self, snapshot: UsageSnapshot) -> GoalUsageSnapshot:
        events = tuple(_to_goal_event(event) for event in snapshot.events)
        if snapshot.complete:
            amount = snapshot.total_cost
            return GoalUsageSnapshot(
                events=events,
                amount_usd=amount if amount is not None else Decimal("0"),
                complete=True,
                incomplete_reason=None,
            )
        return GoalUsageSnapshot(
            events=events,
            amount_usd=None,
            complete=False,
            incomplete_reason=_incomplete_reason(snapshot),
        )


def _extract_output(result: object) -> str:
    if not isinstance(result, Mapping):
        return ""
    for key in ("response", "final_response", "content", "output"):
        value = result.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _incomplete_reason(snapshot: UsageSnapshot) -> str:
    for event in snapshot.events:
        if event.usage is None:
            return "missing_usage"
        if event.cost.amount_usd is None:
            return "missing_amount"
        if event.cost.status not in _COMPLETE_COST_STATUSES:
            return "unknown_cost"
    return "incomplete"


def _to_goal_event(event: UsageEvent) -> GoalUsageEvent:
    usage = event.usage
    status = event.cost.status if event.cost.status in _VALID_COST_STATUSES else "unknown"
    return GoalUsageEvent(
        attempt_index=event.attempt_index,
        outcome=_OUTCOME_MAP.get(event.outcome, "invalid_response"),
        provider=event.billing_route.provider,
        model=event.billing_route.model,
        api_mode=event.billing_route.billing_mode,
        input_tokens=usage.input_tokens if usage is not None else 0,
        output_tokens=usage.output_tokens if usage is not None else 0,
        cache_read_tokens=usage.cache_read_tokens if usage is not None else 0,
        cache_write_tokens=usage.cache_write_tokens if usage is not None else 0,
        reasoning_tokens=usage.reasoning_tokens if usage is not None else 0,
        amount_usd=event.cost.amount_usd,
        cost_status=status,
        cost_source=str(event.cost.source),
        pricing_version=event.cost.pricing_version,
    )
