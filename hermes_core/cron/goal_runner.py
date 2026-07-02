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
    goal_state_from_json,
    goal_state_to_json,
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
    usage_snapshot_to_json,
)
from cron.goal_verifiers import VerifierResult

__all__ = [
    "GoalRunnerError",
    "WorkerObservation",
    "GoalWorker",
    "GoalVerifier",
    "GoalIterationResult",
    "build_artifact_fingerprint",
    "build_evidence_fingerprint",
    "run_goal_iteration",
    "pause_goal_iteration",
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
        previous_artifact_hash: str | None,
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
        if not resolved.is_file():
            raise GoalRunnerError("reported artifact is missing or not a regular file")
        artifacts.append(
            {
                "path": relative,
                "sha256": _file_sha256(resolved),
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


def build_artifact_fingerprint(
    definition: GoalDefinition,
    report: GoalReport,
) -> str:
    """Hash only declared artifact paths and contents for cross-run comparison."""
    encoded = json.dumps(
        _artifact_fingerprints(definition, report),
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
        "last_artifact_hash": state.last_artifact_hash,
        "updated_at": state.updated_at.isoformat(),
        "next_state": goal_state_to_json(state),
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
    iteration = max(1, state.iteration)
    transition_path = goal_run_dir(state.job_id) / "iterations" / f"{iteration:06d}" / "transition.json"
    if transition_path.exists():
        try:
            raw = json.loads(transition_path.read_text(encoding="utf-8"))
            next_state = goal_state_from_json(raw["next_state"], state.job_id)
            previous_status = raw["previous_status"]
            reason = raw["reason"]
            should_deliver = raw["should_deliver"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError, GoalStateError) as exc:
            raise GoalRunnerError(
                f"committed transition for {state.job_id!r}#{iteration} is invalid"
            ) from exc
        if (
            raw.get("next_status") != next_state.status
            or raw.get("iteration") != next_state.iteration
            or next_state.iteration != state.iteration
            or previous_status not in {"scheduled", "running", "verifying"}
            or not isinstance(reason, str)
            or not isinstance(should_deliver, bool)
        ):
            raise GoalRunnerError(
                f"committed transition for {state.job_id!r}#{iteration} is inconsistent"
            )
        transition = GoalTransition(
            previous_status=previous_status,
            next_state=next_state,
            reason=reason,
            should_deliver=should_deliver,
        )
        save_goal_state(next_state)
        return GoalIterationResult(
            transition=transition,
            full_output="",
            delivery_text=_delivery_text(transition),
            evidence_path=transition_path,
        )

    transition = _pause_transition(
        state,
        "recovery_review",
        now=now,
        last_error="prior iteration stopped while in flight; automatic replay refused",
    )
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


def pause_goal_iteration(
    definition: GoalDefinition,
    reason: str,
    *,
    now: datetime,
    last_error: str | None = None,
) -> GoalIterationResult:
    """Pause a goal without running a worker turn.

    Used when a gate forbids invoking a model on this wake (e.g. the
    ``cron.goal_loop`` feature flag is disabled). Durable evidence is preserved;
    only a paused transition is committed so the state stays inspectable. An
    in-flight (running/verifying) state is recovered rather than overwritten,
    and a terminal state is rejected.
    """
    state = load_goal_state(definition.job_id)
    if state is None:
        state = new_goal_state(definition.job_id, now=now)
    if state.job_id != definition.job_id:
        raise GoalRunnerError("goal definition does not match committed state")
    if state.status in {"running", "verifying"}:
        return _recover_inflight(state, now=now)
    if state.status in {"completed", "failed", "cancelled"}:
        raise InvalidGoalTransition(
            f"cannot pause goal {state.job_id!r} from state {state.status!r}"
        )
    transition = _pause_transition(state, reason, now=now, last_error=last_error)
    # No iteration ran, so persist only the paused state — like the preflight
    # pause path — rather than writing an iteration transition record.
    state_path = save_goal_state(transition.next_state)
    return GoalIterationResult(
        transition=transition,
        full_output="",
        delivery_text=_delivery_text(transition),
        evidence_path=state_path,
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
            usage=GoalUsageSnapshot(
                events=(),
                amount_usd=None,
                complete=False,
                incomplete_reason="worker_exception",
            ),
            full_output="",
            wall_seconds=0.0,
            infrastructure_error=_sanitized_exception("worker", exc),
            ambiguous_external_effect=True,
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

    usage_complete = (
        worker_observation.usage.complete
        and worker_observation.usage.amount_usd is not None
    )
    verifier_result: VerifierResult | None = None
    artifact_hash = None
    artifact_error = False
    if usage_complete and worker_observation.report is not None:
        try:
            artifact_hash = build_artifact_fingerprint(
                definition, worker_observation.report
            )
        except GoalRunnerError:
            artifact_error = True
    if (
        worker_observation.report is not None
        and worker_observation.report.status == "candidate_done"
        and usage_complete
        and not artifact_error
    ):
        verifying_state = replace(running_state, status="verifying", updated_at=now)
        save_goal_state(verifying_state)
        try:
            verifier_result = verifier.verify(
                definition,
                worker_observation.report,
                state.last_artifact_hash,
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
    evidence_hash = (
        build_evidence_fingerprint(
            definition, worker_observation.report, verifier_result
        )
        if worker_observation.report is not None
        and usage_complete
        and not artifact_error
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

    forced_pause_reason = None
    forced_last_error = None
    if usage_complete and artifact_error:
        forced_pause_reason = "invalid_artifact"
        forced_last_error = "reported artifact was missing or outside the workdir"
    elif (
        usage_complete
        and worker_observation.report is None
        and worker_observation.infrastructure_error is None
    ):
        forced_pause_reason = "missing_report"
        forced_last_error = "worker returned without a goal_report"
    if forced_pause_reason is not None:
        transition = replace(
            transition,
            next_state=replace(
                transition.next_state,
                status="paused",
                pause_reason=forced_pause_reason,
                last_error=forced_last_error,
            ),
            reason=forced_pause_reason,
            should_deliver=True,
        )

    if artifact_hash is not None:
        transition = replace(
            transition,
            next_state=replace(
                transition.next_state,
                last_artifact_hash=artifact_hash,
            ),
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
