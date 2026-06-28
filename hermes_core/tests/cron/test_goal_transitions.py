from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from cron.goal_state import GoalLimits, GoalReport, new_goal_state
from cron.goal_transitions import (
    InvalidGoalTransition,
    IterationObservation,
    reduce_iteration,
)
from cron.goal_usage import GoalUsageSnapshot


NOW = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)


def _state(**changes):
    return replace(new_goal_state("abc123def456", now=NOW), **changes)


def _limits(**changes):
    base = GoalLimits(
        max_runs=10,
        max_cost_usd=Decimal("5"),
        max_wall_seconds=3600,
        deadline=NOW + timedelta(hours=1),
        no_progress_limit=3,
        max_infrastructure_failures=3,
    )
    return replace(base, **changes)


def _report(status="progress", *, effects=()):
    return GoalReport(
        status=status,
        summary=f"worker reported {status}",
        artifacts=("manifest.json",),
        evidence={"count": 1},
        next_step="continue" if status == "progress" else None,
        external_side_effects=tuple(effects),
    )


def _usage(amount="0.25", *, complete=True):
    return GoalUsageSnapshot(
        events=(),
        amount_usd=Decimal(amount) if amount is not None else None,
        complete=complete,
        incomplete_reason=None if complete else "unknown_cost",
    )


def _observation(
    *,
    report=None,
    verifier=None,
    usage=None,
    wall_seconds=2.5,
    evidence_hash="hash-new",
    infrastructure_error=None,
    ambiguous_external_effect=False,
):
    return IterationObservation(
        report=report if report is not None else _report(),
        verifier=verifier,
        usage=usage if usage is not None else _usage(),
        wall_seconds=wall_seconds,
        evidence_hash=evidence_hash,
        infrastructure_error=infrastructure_error,
        ambiguous_external_effect=ambiguous_external_effect,
    )


@pytest.mark.parametrize(
    ("report", "verifier", "evidence_hash", "expected_status", "reason"),
    [
        (_report("progress"), None, "changed", "scheduled", "progress"),
        (
            _report("candidate_done"),
            SimpleNamespace(outcome="pass", summary="ok", evidence={}),
            "changed",
            "completed",
            "verified_complete",
        ),
        (
            _report("candidate_done"),
            SimpleNamespace(outcome="fail", summary="missing", evidence={}),
            "changed",
            "scheduled",
            "verification_failed",
        ),
        (_report("blocked"), None, "changed", "paused", "worker_blocked"),
        (
            _report("candidate_done"),
            SimpleNamespace(outcome="error", summary="bad verifier", evidence={}),
            "changed",
            "paused",
            "verifier_error",
        ),
    ],
)
def test_reduces_worker_and_verifier_outcomes(
    report, verifier, evidence_hash, expected_status, reason
):
    transition = reduce_iteration(
        _state(),
        _limits(),
        _observation(
            report=report, verifier=verifier, evidence_hash=evidence_hash
        ),
        now=NOW + timedelta(minutes=1),
    )

    assert transition.next_state.status == expected_status
    assert transition.reason == reason
    assert transition.should_deliver is (expected_status in {"completed", "paused", "failed"})
    assert transition.next_state.iteration == 1
    assert transition.next_state.accumulated_cost_usd == Decimal("0.25")
    assert transition.next_state.accumulated_wall_seconds == 2.5


@pytest.mark.parametrize(
    ("limits", "state_changes", "observation", "reason"),
    [
        (_limits(max_runs=1), {}, _observation(), "max_runs"),
        (
            _limits(max_cost_usd=Decimal("1")),
            {"accumulated_cost_usd": Decimal("0.9")},
            _observation(usage=_usage("0.2")),
            "max_cost_usd",
        ),
        (
            _limits(max_wall_seconds=10),
            {"accumulated_wall_seconds": 9.0},
            _observation(wall_seconds=1.5),
            "max_wall_seconds",
        ),
        (
            _limits(deadline=NOW + timedelta(seconds=10)),
            {},
            _observation(),
            "deadline",
        ),
    ],
)
def test_budget_and_deadline_limits_pause(limits, state_changes, observation, reason):
    transition = reduce_iteration(
        _state(**state_changes),
        limits,
        observation,
        now=NOW + timedelta(minutes=1),
    )

    assert transition.next_state.status == "paused"
    assert transition.next_state.pause_reason == reason
    assert transition.reason == reason


def test_incomplete_usage_pauses_before_accepting_verifier_pass():
    transition = reduce_iteration(
        _state(accumulated_cost_usd=Decimal("1.25")),
        _limits(),
        _observation(
            report=_report("candidate_done"),
            verifier=SimpleNamespace(outcome="pass", summary="ok", evidence={}),
            usage=_usage(None, complete=False),
        ),
        now=NOW + timedelta(minutes=1),
    )

    assert transition.next_state.status == "paused"
    assert transition.reason == "cost_unknown"
    assert transition.next_state.cost_accounting == "incomplete"
    assert transition.next_state.accumulated_cost_usd == Decimal("1.25")
    assert transition.next_state.completed_at is None


def test_repeated_evidence_pauses_at_no_progress_limit_and_changed_hash_resets():
    repeated = reduce_iteration(
        _state(last_evidence_hash="same", no_progress_count=2),
        _limits(no_progress_limit=3),
        _observation(evidence_hash="same"),
        now=NOW + timedelta(minutes=1),
    )
    changed = reduce_iteration(
        _state(last_evidence_hash="old", no_progress_count=2),
        _limits(no_progress_limit=3),
        _observation(evidence_hash="new"),
        now=NOW + timedelta(minutes=1),
    )

    assert repeated.next_state.status == "paused"
    assert repeated.reason == "no_progress"
    assert repeated.next_state.no_progress_count == 3
    assert changed.next_state.status == "scheduled"
    assert changed.next_state.no_progress_count == 0


def test_infrastructure_errors_retry_then_fail_at_limit():
    retry = reduce_iteration(
        _state(infrastructure_failures=1),
        _limits(max_infrastructure_failures=3),
        _observation(
            report=None,
            usage=_usage("0"),
            evidence_hash=None,
            infrastructure_error="transport unavailable",
        ),
        now=NOW + timedelta(minutes=1),
    )
    failed = reduce_iteration(
        _state(infrastructure_failures=2),
        _limits(max_infrastructure_failures=3),
        _observation(
            report=None,
            usage=_usage("0"),
            evidence_hash=None,
            infrastructure_error="transport unavailable",
        ),
        now=NOW + timedelta(minutes=1),
    )

    assert retry.next_state.status == "scheduled"
    assert retry.reason == "infrastructure_retry"
    assert retry.next_state.infrastructure_failures == 2
    assert failed.next_state.status == "failed"
    assert failed.reason == "infrastructure_failure_limit"
    assert failed.next_state.infrastructure_failures == 3


def test_ambiguous_external_effect_has_highest_pause_precedence_and_keeps_diagnostics():
    transition = reduce_iteration(
        _state(no_progress_count=2),
        _limits(max_runs=1, no_progress_limit=3),
        _observation(
            report=_report("blocked", effects=("sent remote message",)),
            usage=_usage(None, complete=False),
            evidence_hash="same",
            infrastructure_error="connection reset after send",
            ambiguous_external_effect=True,
        ),
        now=NOW + timedelta(hours=2),
    )

    assert transition.next_state.status == "paused"
    assert transition.reason == "ambiguous_external_effect"
    assert transition.next_state.pause_reason == "ambiguous_external_effect"
    assert "cost_unknown" in transition.next_state.last_error
    assert "worker_blocked" in transition.next_state.last_error
    assert "max_runs" in transition.next_state.last_error


def test_reducer_is_deterministic_for_equal_inputs():
    state = _state(last_evidence_hash="old")
    observation = _observation(
        report=_report("candidate_done"),
        verifier=SimpleNamespace(outcome="fail", summary="not yet", evidence={}),
    )

    first = reduce_iteration(state, _limits(), observation, now=NOW)
    second = reduce_iteration(state, _limits(), observation, now=NOW)

    assert first == second


@pytest.mark.parametrize("status", ["completed", "failed", "cancelled"])
def test_terminal_states_reject_new_iterations(status):
    with pytest.raises(InvalidGoalTransition):
        reduce_iteration(_state(status=status), _limits(), _observation(), now=NOW)

