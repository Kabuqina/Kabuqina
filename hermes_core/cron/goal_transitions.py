"""Pure state-transition rules for one bounded goal iteration."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from cron.goal_state import GoalLimits, GoalReport, GoalRunState, GoalStatus
from cron.goal_usage import GoalUsageSnapshot

if TYPE_CHECKING:
    from cron.goal_verifiers import VerifierResult

__all__ = [
    "InvalidGoalTransition",
    "IterationObservation",
    "GoalTransition",
    "reduce_iteration",
]


class InvalidGoalTransition(ValueError):
    """Raised when an iteration is reduced from a terminal state."""


@dataclass(frozen=True)
class IterationObservation:
    report: GoalReport | None
    verifier: VerifierResult | None
    usage: GoalUsageSnapshot
    wall_seconds: float
    evidence_hash: str | None
    infrastructure_error: str | None
    ambiguous_external_effect: bool


@dataclass(frozen=True)
class GoalTransition:
    previous_status: GoalStatus
    next_state: GoalRunState
    reason: str
    should_deliver: bool


_TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})


def reduce_iteration(
    state: GoalRunState,
    limits: GoalLimits,
    observation: IterationObservation,
    *,
    now: datetime,
) -> GoalTransition:
    """Reduce an injected observation without reading clock, I/O, or config."""
    if state.status in _TERMINAL_STATUSES:
        raise InvalidGoalTransition(
            f"cannot run goal {state.job_id!r} from terminal state {state.status!r}"
        )
    if observation.wall_seconds < 0:
        raise ValueError("wall_seconds must be non-negative")

    iteration = state.iteration + 1
    accumulated_wall = state.accumulated_wall_seconds + observation.wall_seconds
    usage_complete = observation.usage.complete and observation.usage.amount_usd is not None
    accumulated_cost = state.accumulated_cost_usd
    if usage_complete:
        accumulated_cost += observation.usage.amount_usd or Decimal("0")

    infrastructure_failures = (
        state.infrastructure_failures + 1
        if observation.infrastructure_error is not None
        else 0
    )
    verifier_outcome = (
        observation.verifier.outcome if observation.verifier is not None else None
    )
    verified_candidate = (
        observation.report is not None
        and observation.report.status == "candidate_done"
        and verifier_outcome == "pass"
    )

    no_progress_count = state.no_progress_count
    checks_progress = observation.report is not None and (
        observation.report.status == "progress"
        or (
            observation.report.status == "candidate_done"
            and verifier_outcome != "pass"
        )
    )
    if checks_progress and observation.evidence_hash is not None:
        if observation.evidence_hash == state.last_evidence_hash:
            no_progress_count += 1
        else:
            no_progress_count = 0

    diagnostics: list[str] = []
    if observation.ambiguous_external_effect:
        diagnostics.append("ambiguous_external_effect")
    if not usage_complete:
        diagnostics.append("cost_unknown")
    if observation.report is not None and observation.report.status == "blocked":
        diagnostics.append("worker_blocked")
    if (
        verifier_outcome == "error"
        or (
            observation.report is not None
            and observation.report.status == "candidate_done"
            and observation.verifier is None
        )
    ):
        diagnostics.append("verifier_error")
    if iteration >= limits.max_runs and not verified_candidate:
        diagnostics.append("max_runs")
    if limits.max_cost_usd is not None and accumulated_cost > limits.max_cost_usd:
        diagnostics.append("max_cost_usd")
    if accumulated_wall > limits.max_wall_seconds:
        diagnostics.append("max_wall_seconds")
    if limits.deadline is not None and now >= limits.deadline:
        diagnostics.append("deadline")
    if checks_progress and no_progress_count >= limits.no_progress_limit:
        diagnostics.append("no_progress")

    status: GoalStatus
    reason: str
    if diagnostics:
        status = "paused"
        reason = diagnostics[0]
    elif infrastructure_failures >= limits.max_infrastructure_failures:
        status = "failed"
        reason = "infrastructure_failure_limit"
    elif observation.infrastructure_error is not None:
        status = "scheduled"
        reason = "infrastructure_retry"
    elif verified_candidate:
        status = "completed"
        reason = "verified_complete"
    elif (
        observation.report is not None
        and observation.report.status == "candidate_done"
        and verifier_outcome == "fail"
    ):
        status = "scheduled"
        reason = "verification_failed"
    else:
        status = "scheduled"
        reason = "progress"

    last_error_parts = list(diagnostics)
    if observation.infrastructure_error:
        last_error_parts.append(observation.infrastructure_error)
    if verifier_outcome == "error" and observation.verifier is not None:
        last_error_parts.append(observation.verifier.summary)

    next_state = replace(
        state,
        status=status,
        iteration=iteration,
        accumulated_cost_usd=accumulated_cost,
        cost_accounting="complete" if usage_complete else "incomplete",
        accumulated_wall_seconds=accumulated_wall,
        no_progress_count=no_progress_count,
        infrastructure_failures=infrastructure_failures,
        last_evidence_hash=observation.evidence_hash or state.last_evidence_hash,
        last_summary=(
            observation.report.summary
            if observation.report is not None
            else state.last_summary
        ),
        last_verifier_outcome=verifier_outcome,
        pause_reason=reason if status == "paused" else None,
        last_error="; ".join(last_error_parts) if last_error_parts else None,
        started_at=state.started_at or now,
        completed_at=now if status == "completed" else state.completed_at,
        updated_at=now,
    )
    return GoalTransition(
        previous_status=state.status,
        next_state=next_state,
        reason=reason,
        should_deliver=status in {"completed", "paused", "failed", "cancelled"},
    )

