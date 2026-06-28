"""Engine-neutral orchestration for exactly one bounded-goal iteration."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Protocol

from cron.goal_state import (
    GoalDefinition,
    GoalReport,
    GoalRunState,
    GoalStateError,
    JSONValue,
    goal_run_dir,
    load_goal_state,
    new_goal_state,
    save_goal_state,
    save_iteration_record,
)
from cron.goal_transitions import (
    GoalTransition,
    InvalidGoalTransition,
    IterationObservation,
    reduce_iteration,
)
from cron.goal_usage import (
    GoalUsageSnapshot,
    summarize_usage_events,
    usage_snapshot_to_json,
)
from cron.goal_verifiers import VerifierResult

__all__ = [
    "GoalRunnerError",
    "WorkerObservation",
    "GoalWorker",
    "GoalVerifier",
    "GoalIterationResult",
    "build_evidence_fingerprint",
    "run_goal_iteration",
]


class GoalRunnerError(RuntimeError):
    """Raised when durable state and the requested definition disagree."""


def _sanitized_exception(component: str, exc: Exception) -> str:
    """Return stable diagnostics without persisting provider-controlled text."""
    return f"{component}_exception:{type(exc).__name__}"


@dataclass(frozen=True)
class WorkerObservation:
    report: GoalReport | None
    usage: GoalUsageSnapshot
    full_output: str
    wall_seconds: float
    infrastructure_error: str | None
    ambiguous_external_effect: bool


class GoalWorker(Protocol):
    def run_iteration(
        self,
        definition: GoalDefinition,
        state: GoalRunState,
    ) -> WorkerObservation: ...


class GoalVerifier(Protocol):
    def verify(
        self,
        definition: GoalDefinition,
        report: GoalReport,
        previous_evidence_hash: str | None,
    ) -> VerifierResult: ...


@dataclass(frozen=True)
class GoalIterationResult:
    transition: GoalTransition
    full_output: str
    delivery_text: str
    evidence_path: Path


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_fingerprints(
    definition: GoalDefinition, report: GoalReport
) -> list[dict[str, JSONValue]]:
    root = definition.workdir.resolve()
    artifacts: list[dict[str, JSONValue]] = []
    for value in report.artifacts:
        candidate = Path(value)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise GoalRunnerError("reported artifact must be relative and confined")
        resolved = (root / candidate).resolve()
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise GoalRunnerError("reported artifact escapes the goal workdir") from exc
        artifacts.append(
            {
                "path": relative,
                "sha256": _file_sha256(resolved) if resolved.is_file() else None,
            }
        )
    artifacts.sort(key=lambda item: str(item["path"]))
    return artifacts


def build_evidence_fingerprint(
    definition: GoalDefinition,
    report: GoalReport,
    verifier: VerifierResult | None,
) -> str:
    """Hash deterministic artifact and verifier evidence only."""
    payload: dict[str, JSONValue] = {
        "artifacts": _artifact_fingerprints(definition, report),
        "verifier": (
            None
            if verifier is None
            else {"outcome": verifier.outcome, "evidence": dict(verifier.evidence)}
        ),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _report_to_json(report: GoalReport | None) -> JSONValue:
    if report is None:
        return None
    return {
        "status": report.status,
        "summary": report.summary,
        "artifacts": list(report.artifacts),
        "evidence": dict(report.evidence),
        "next_step": report.next_step,
        "external_side_effects": list(report.external_side_effects),
    }


def _verifier_to_json(result: VerifierResult) -> dict[str, JSONValue]:
    return {
        "outcome": result.outcome,
        "summary": result.summary,
        "evidence": dict(result.evidence),
    }


def _transition_to_json(transition: GoalTransition) -> dict[str, JSONValue]:
    state = transition.next_state
    return {
        "previous_status": transition.previous_status,
        "next_status": state.status,
        "iteration": state.iteration,
        "reason": transition.reason,
        "should_deliver": transition.should_deliver,
        "accumulated_cost_usd": str(state.accumulated_cost_usd),
        "cost_accounting": state.cost_accounting,
        "accumulated_wall_seconds": state.accumulated_wall_seconds,
        "no_progress_count": state.no_progress_count,
        "infrastructure_failures": state.infrastructure_failures,
        "last_evidence_hash": state.last_evidence_hash,
        "updated_at": state.updated_at.isoformat(),
    }


def _pause_transition(
    state: GoalRunState,
    reason: str,
    *,
    now: datetime,
    last_error: str | None = None,
) -> GoalTransition:
    return GoalTransition(
        previous_status=state.status,
        next_state=replace(
            state,
            status="paused",
            pause_reason=reason,
            last_error=last_error,
            updated_at=now,
        ),
        reason=reason,
        should_deliver=True,
    )


def _preflight_reason(
    definition: GoalDefinition, state: GoalRunState, now: datetime
) -> str | None:
    limits = definition.limits
    if state.cost_accounting == "incomplete":
        return "cost_unknown"
    if state.iteration >= limits.max_runs:
        return "max_runs"
    if (
        limits.max_cost_usd is not None
        and state.accumulated_cost_usd >= limits.max_cost_usd
    ):
        return "max_cost_usd"
    if state.accumulated_wall_seconds >= limits.max_wall_seconds:
        return "max_wall_seconds"
    if limits.deadline is not None and now >= limits.deadline:
        return "deadline"
    return None


def _delivery_text(transition: GoalTransition) -> str:
    if not transition.should_deliver:
        return ""
    return (
        f"Goal {transition.next_state.job_id} "
        f"{transition.next_state.status}: {transition.reason}"
    )


def _persist_transition(
    transition: GoalTransition,
    *,
    record_iteration: int,
) -> Path:
    path = save_iteration_record(
        transition.next_state.job_id,
        record_iteration,
        "transition",
        _transition_to_json(transition),
    )
    save_goal_state(transition.next_state)
    return path


def _recover_inflight(state: GoalRunState, *, now: datetime) -> GoalIterationResult:
    transition = _pause_transition(
        state,
        "recovery_review",
        now=now,
        last_error="prior iteration stopped while in flight; automatic replay refused",
    )
    iteration = max(1, state.iteration)
    transition_path = goal_run_dir(state.job_id) / "iterations" / f"{iteration:06d}" / "transition.json"
    if not transition_path.exists():
        transition_path = save_iteration_record(
            state.job_id,
            iteration,
            "transition",
            _transition_to_json(transition),
        )
    save_goal_state(transition.next_state)
    return GoalIterationResult(
        transition=transition,
        full_output="",
        delivery_text=_delivery_text(transition),
        evidence_path=transition_path,
    )


def run_goal_iteration(
    definition: GoalDefinition,
    *,
    worker: GoalWorker,
    verifier: GoalVerifier,
    now: datetime,
) -> GoalIterationResult:
    """Run at most one worker turn and durably commit its transition."""
    state = load_goal_state(definition.job_id)
    if state is None:
        state = new_goal_state(definition.job_id, now=now)
    if state.job_id != definition.job_id:
        raise GoalRunnerError("goal definition does not match committed state")
    if state.status in {"paused", "completed", "failed", "cancelled"}:
        raise InvalidGoalTransition(
            f"cannot run goal {state.job_id!r} from state {state.status!r}"
        )
    if state.status in {"running", "verifying"}:
        return _recover_inflight(state, now=now)

    preflight_reason = _preflight_reason(definition, state, now)
    if preflight_reason is not None:
        transition = _pause_transition(state, preflight_reason, now=now)
        state_path = save_goal_state(transition.next_state)
        return GoalIterationResult(
            transition=transition,
            full_output="",
            delivery_text=_delivery_text(transition),
            evidence_path=state_path,
        )

    iteration = state.iteration + 1
    running_state = replace(
        state,
        status="running",
        iteration=iteration,
        started_at=state.started_at or now,
        pause_reason=None,
        last_error=None,
        updated_at=now,
    )
    save_goal_state(running_state)

    try:
        worker_observation = worker.run_iteration(definition, running_state)
    except Exception as exc:
        worker_observation = WorkerObservation(
            report=None,
            usage=summarize_usage_events(()),
            full_output="",
            wall_seconds=0.0,
            infrastructure_error=_sanitized_exception("worker", exc),
            ambiguous_external_effect=False,
        )
    if worker_observation.infrastructure_error is not None:
        worker_observation = replace(
            worker_observation,
            infrastructure_error="worker_infrastructure_error",
        )

    report_record: dict[str, JSONValue] = {
        "job_id": definition.job_id,
        "iteration": iteration,
        "report": _report_to_json(worker_observation.report),
        "usage": usage_snapshot_to_json(worker_observation.usage),
        "wall_seconds": worker_observation.wall_seconds,
        "infrastructure_error": worker_observation.infrastructure_error,
        "ambiguous_external_effect": worker_observation.ambiguous_external_effect,
    }
    save_iteration_record(
        definition.job_id, iteration, "report", report_record
    )

    verifier_result: VerifierResult | None = None
    if (
        worker_observation.report is not None
        and worker_observation.report.status == "candidate_done"
        and worker_observation.usage.complete
        and worker_observation.usage.amount_usd is not None
    ):
        verifying_state = replace(running_state, status="verifying", updated_at=now)
        save_goal_state(verifying_state)
        try:
            verifier_result = verifier.verify(
                definition,
                worker_observation.report,
                state.last_evidence_hash,
            )
        except Exception as exc:
            verifier_result = VerifierResult(
                "error", _sanitized_exception("verifier", exc), {}
            )
        save_iteration_record(
            definition.job_id,
            iteration,
            "verification",
            _verifier_to_json(verifier_result),
        )

    reducer_state = replace(running_state, iteration=state.iteration)
    if (
        worker_observation.report is None
        and worker_observation.infrastructure_error is None
        and worker_observation.usage.complete
    ):
        transition = _pause_transition(
            running_state,
            "missing_report",
            now=now,
            last_error="worker returned without a goal_report",
        )
    else:
        evidence_hash = (
            build_evidence_fingerprint(
                definition, worker_observation.report, verifier_result
            )
            if worker_observation.report is not None
            else None
        )
        transition = reduce_iteration(
            reducer_state,
            definition.limits,
            IterationObservation(
                report=worker_observation.report,
                verifier=verifier_result,
                usage=worker_observation.usage,
                wall_seconds=worker_observation.wall_seconds,
                evidence_hash=evidence_hash,
                infrastructure_error=worker_observation.infrastructure_error,
                ambiguous_external_effect=(
                    worker_observation.ambiguous_external_effect
                    or bool(
                        worker_observation.infrastructure_error
                        and worker_observation.report is not None
                        and worker_observation.report.external_side_effects
                    )
                ),
            ),
            now=now,
        )

    cadence = definition.progress_delivery_every
    if (
        transition.next_state.status == "scheduled"
        and cadence is not None
        and cadence > 0
        and transition.next_state.iteration % cadence == 0
    ):
        transition = replace(transition, should_deliver=True)

    transition_path = _persist_transition(
        transition,
        record_iteration=iteration,
    )
    return GoalIterationResult(
        transition=transition,
        full_output=worker_observation.full_output,
        delivery_text=_delivery_text(transition),
        evidence_path=transition_path,
    )
