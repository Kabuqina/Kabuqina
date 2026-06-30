from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

import cron.goal_runner as goal_runner
import cron.goal_state as goal_state
from cron.goal_runner import (
    GoalRunnerError,
    WorkerObservation,
    build_evidence_fingerprint,
    run_goal_iteration,
)
from cron.goal_state import (
    GoalDefinition,
    GoalLimits,
    GoalReport,
    load_goal_state,
    new_goal_state,
    save_goal_state,
)
from cron.goal_transitions import InvalidGoalTransition
from cron.goal_usage import GoalUsageSnapshot
from cron.goal_verifiers import VerificationContext, VerifierResult, verify


NOW = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)
JOB_ID = "abc123def456"


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    home = tmp_path / "hermes-home"
    monkeypatch.setattr(goal_state, "get_hermes_home", lambda: home)
    return home


@pytest.fixture
def definition(tmp_path):
    workdir = tmp_path / "workspace"
    workdir.mkdir()
    (workdir / "manifest.json").write_text("{}", encoding="utf-8")
    return GoalDefinition(
        job_id=JOB_ID,
        objective="complete the inventory",
        iteration_prompt="process one item",
        workdir=workdir.resolve(),
        verifier_kind="artifact_exists",
        verifier_config={"paths": ["manifest.json"]},
        limits=GoalLimits(
            max_runs=10,
            max_cost_usd=Decimal("5"),
            max_wall_seconds=3600,
            deadline=NOW + timedelta(hours=1),
            no_progress_limit=3,
        ),
        enabled_toolsets=("file", "goal_internal"),
        approval_mode="ask_before_external_side_effect",
        progress_delivery_every=None,
    )


def _report(status="progress", **changes):
    values = {
        "status": status,
        "summary": f"reported {status}",
        "artifacts": ("manifest.json",),
        "evidence": {"model_text": "not authoritative"},
        "next_step": "continue" if status == "progress" else None,
        "external_side_effects": (),
    }
    values.update(changes)
    return GoalReport(**values)


def _usage(amount="0.25", *, complete=True):
    return GoalUsageSnapshot(
        events=(),
        amount_usd=Decimal(amount) if amount is not None else None,
        complete=complete,
        incomplete_reason=None if complete else "unknown_cost",
    )


def _worker_observation(status="progress", **changes):
    values = {
        "report": _report(status),
        "usage": _usage(),
        "full_output": "full inner-agent output",
        "wall_seconds": 1.5,
        "infrastructure_error": None,
        "ambiguous_external_effect": False,
    }
    values.update(changes)
    return WorkerObservation(**values)


class FakeWorker:
    def __init__(self, observation):
        self.observation = observation
        self.calls = []

    def run_iteration(self, definition, state):
        self.calls.append((definition, state))
        return self.observation


class FakeVerifier:
    def __init__(self, result=None):
        self.result = result or VerifierResult("pass", "verified", {"ok": True})
        self.calls = []

    def verify(self, definition, report, previous_evidence_hash):
        self.calls.append((definition, report, previous_evidence_hash))
        return self.result


def test_initializes_state_runs_worker_once_and_reschedules_progress(definition):
    worker = FakeWorker(_worker_observation())
    verifier = FakeVerifier()

    result = run_goal_iteration(
        definition, worker=worker, verifier=verifier, now=NOW
    )

    assert len(worker.calls) == 1
    assert verifier.calls == []
    assert result.transition.next_state.status == "scheduled"
    assert result.transition.next_state.iteration == 1
    assert result.full_output == "full inner-agent output"
    assert result.delivery_text == ""
    assert result.evidence_path.name == "transition.json"
    assert load_goal_state(JOB_ID) == result.transition.next_state

    iteration_dir = goal_state.goal_run_dir(JOB_ID) / "iterations" / "000001"
    report_record = json.loads((iteration_dir / "report.json").read_text(encoding="utf-8"))
    transition_record = json.loads(
        (iteration_dir / "transition.json").read_text(encoding="utf-8")
    )
    assert report_record["report"]["status"] == "progress"
    assert report_record["usage"]["amount_usd"] == "0.25"
    assert transition_record["next_status"] == "scheduled"


def test_candidate_done_verifies_once_and_persists_completion(definition):
    worker = FakeWorker(_worker_observation("candidate_done"))
    verifier = FakeVerifier(VerifierResult("pass", "complete", {"complete": True}))

    result = run_goal_iteration(
        definition, worker=worker, verifier=verifier, now=NOW
    )

    assert len(worker.calls) == 1
    assert len(verifier.calls) == 1
    assert result.transition.next_state.status == "completed"
    assert result.transition.should_deliver is True
    assert "completed" in result.delivery_text
    verification = json.loads(
        (
            goal_state.goal_run_dir(JOB_ID)
            / "iterations"
            / "000001"
            / "verification.json"
        ).read_text(encoding="utf-8")
    )
    assert verification["outcome"] == "pass"


def test_content_hash_changed_compares_same_artifact_domain_across_iterations(
    definition,
):
    class RegistryVerifier:
        def verify(self, definition, report, previous_evidence_hash):
            return verify(
                definition.verifier_kind,
                VerificationContext(
                    workdir=definition.workdir,
                    report=report,
                    config=definition.verifier_config,
                    previous_evidence_hash=previous_evidence_hash,
                ),
            )

    definition = replace(
        definition,
        verifier_kind="content_hash_changed",
        verifier_config={},
    )
    verifier = RegistryVerifier()

    first = run_goal_iteration(
        definition,
        worker=FakeWorker(_worker_observation("progress")),
        verifier=verifier,
        now=NOW,
    )
    second = run_goal_iteration(
        definition,
        worker=FakeWorker(_worker_observation("candidate_done")),
        verifier=verifier,
        now=NOW + timedelta(minutes=1),
    )

    assert first.transition.next_state.status == "scheduled"
    assert second.transition.next_state.status == "scheduled"
    assert second.transition.next_state.last_verifier_outcome == "fail"


def test_incomplete_usage_pauses_without_running_verifier(definition):
    worker = FakeWorker(
        _worker_observation(
            "candidate_done", usage=_usage(None, complete=False)
        )
    )
    verifier = FakeVerifier()

    result = run_goal_iteration(
        definition, worker=worker, verifier=verifier, now=NOW
    )

    assert verifier.calls == []
    assert result.transition.next_state.status == "paused"
    assert result.transition.reason == "cost_unknown"
    assert "cost_unknown" in result.delivery_text


def test_missing_report_becomes_controlled_pause(definition):
    worker = FakeWorker(_worker_observation(report=None))
    verifier = FakeVerifier()

    result = run_goal_iteration(
        definition, worker=worker, verifier=verifier, now=NOW
    )

    assert result.transition.next_state.status == "paused"
    assert result.transition.reason == "missing_report"
    assert verifier.calls == []


def test_paused_and_terminal_states_do_not_run_worker(definition):
    worker = FakeWorker(_worker_observation())
    verifier = FakeVerifier()
    for status in ("paused", "completed", "failed", "cancelled"):
        save_goal_state(replace(new_goal_state(JOB_ID, now=NOW), status=status))
        with pytest.raises(InvalidGoalTransition):
            run_goal_iteration(
                definition, worker=worker, verifier=verifier, now=NOW
            )
    assert worker.calls == []


@pytest.mark.parametrize("status", ["running", "verifying"])
def test_restart_from_inflight_state_pauses_without_replay(definition, status):
    inflight = replace(
        new_goal_state(JOB_ID, now=NOW),
        status=status,
        iteration=1,
        started_at=NOW,
    )
    save_goal_state(inflight)
    worker = FakeWorker(_worker_observation())

    result = run_goal_iteration(
        definition, worker=worker, verifier=FakeVerifier(), now=NOW + timedelta(minutes=1)
    )

    assert worker.calls == []
    assert result.transition.next_state.status == "paused"
    assert result.transition.reason == "recovery_review"
    assert load_goal_state(JOB_ID).status == "paused"


def test_preflight_limit_pauses_without_worker_call(definition):
    save_goal_state(
        replace(
            new_goal_state(JOB_ID, now=NOW),
            iteration=definition.limits.max_runs,
        )
    )
    worker = FakeWorker(_worker_observation())

    result = run_goal_iteration(
        definition, worker=worker, verifier=FakeVerifier(), now=NOW
    )

    assert worker.calls == []
    assert result.transition.next_state.status == "paused"
    assert result.transition.reason == "max_runs"


def test_progress_cadence_sets_delivery_only_on_exact_multiple(definition):
    definition = replace(definition, progress_delivery_every=2)
    first = run_goal_iteration(
        definition,
        worker=FakeWorker(_worker_observation()),
        verifier=FakeVerifier(),
        now=NOW,
    )
    second = run_goal_iteration(
        definition,
        worker=FakeWorker(_worker_observation()),
        verifier=FakeVerifier(),
        now=NOW + timedelta(minutes=1),
    )

    assert first.transition.should_deliver is False
    assert first.delivery_text == ""
    assert second.transition.should_deliver is True
    assert "scheduled" in second.delivery_text


def test_worker_exception_is_reduced_as_infrastructure_failure(definition):
    class RaisingWorker:
        calls = 0

        def run_iteration(self, definition, state):
            self.calls += 1
            raise RuntimeError("provider unavailable")

    worker = RaisingWorker()
    result = run_goal_iteration(
        definition, worker=worker, verifier=FakeVerifier(), now=NOW
    )

    assert worker.calls == 1
    assert result.transition.next_state.status == "scheduled"
    assert result.transition.reason == "infrastructure_retry"
    assert result.transition.next_state.infrastructure_failures == 1


def test_exception_messages_are_not_persisted_in_goal_evidence(definition):
    secret = "sk-live-secret-from-provider"

    class RaisingWorker:
        def run_iteration(self, definition, state):
            raise RuntimeError(f"provider rejected {secret}")

    run_goal_iteration(
        definition, worker=RaisingWorker(), verifier=FakeVerifier(), now=NOW
    )

    run_dir = goal_state.goal_run_dir(JOB_ID)
    assert secret not in (run_dir / "state.json").read_text(encoding="utf-8")
    assert secret not in (
        run_dir / "iterations" / "000001" / "report.json"
    ).read_text(encoding="utf-8")


def test_verifier_exception_messages_are_not_persisted(definition):
    secret = "sk-live-secret-from-verifier"

    class RaisingVerifier:
        def verify(self, definition, report, previous_evidence_hash):
            raise RuntimeError(f"verifier saw {secret}")

    run_goal_iteration(
        definition,
        worker=FakeWorker(_worker_observation("candidate_done")),
        verifier=RaisingVerifier(),
        now=NOW,
    )

    run_dir = goal_state.goal_run_dir(JOB_ID)
    assert secret not in (run_dir / "state.json").read_text(encoding="utf-8")
    assert secret not in (
        run_dir / "iterations" / "000001" / "verification.json"
    ).read_text(encoding="utf-8")


def test_worker_supplied_infrastructure_error_is_sanitized(definition):
    secret = "raw provider body with sk-live-secret"
    run_goal_iteration(
        definition,
        worker=FakeWorker(
            _worker_observation(
                report=None,
                infrastructure_error=secret,
            )
        ),
        verifier=FakeVerifier(),
        now=NOW,
    )

    run_dir = goal_state.goal_run_dir(JOB_ID)
    assert secret not in (run_dir / "state.json").read_text(encoding="utf-8")
    assert secret not in (
        run_dir / "iterations" / "000001" / "report.json"
    ).read_text(encoding="utf-8")


def test_crash_after_running_state_commit_recovers_without_second_worker_call(
    definition, monkeypatch
):
    real_save = goal_runner.save_goal_state
    calls = 0

    def crash_after_first_save(state):
        nonlocal calls
        calls += 1
        path = real_save(state)
        if calls == 1:
            raise RuntimeError("simulated process exit")
        return path

    monkeypatch.setattr(goal_runner, "save_goal_state", crash_after_first_save)
    first_worker = FakeWorker(_worker_observation())
    with pytest.raises(RuntimeError, match="simulated process exit"):
        run_goal_iteration(
            definition, worker=first_worker, verifier=FakeVerifier(), now=NOW
        )
    assert first_worker.calls == []
    assert load_goal_state(JOB_ID).status == "running"

    monkeypatch.setattr(goal_runner, "save_goal_state", real_save)
    recovery_worker = FakeWorker(_worker_observation())
    recovered = run_goal_iteration(
        definition,
        worker=recovery_worker,
        verifier=FakeVerifier(),
        now=NOW + timedelta(minutes=1),
    )
    assert recovery_worker.calls == []
    assert recovered.transition.reason == "recovery_review"


def test_evidence_fingerprint_ignores_model_text_and_metadata_but_tracks_artifacts(
    definition
):
    verifier = VerifierResult("fail", "model-authored summary", {"missing": 1})
    base = _report(
        "candidate_done",
        summary="first",
        next_step="one",
        evidence={"model": "one"},
    )
    first = build_evidence_fingerprint(definition, base, verifier)

    changed_text = replace(
        base,
        summary="different",
        next_step="different",
        evidence={"model": "different"},
    )
    assert build_evidence_fingerprint(definition, changed_text, verifier) == first

    (definition.workdir / "manifest.json").write_text(
        '{"changed": true}', encoding="utf-8"
    )
    assert build_evidence_fingerprint(definition, changed_text, verifier) != first


def test_fault_before_final_state_write_recovers_committed_transition_consistently(
    definition, monkeypatch
):
    real_save = goal_runner.save_goal_state
    calls = 0

    def fail_on_final_state(state):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("final state write failed")
        return real_save(state)

    monkeypatch.setattr(goal_runner, "save_goal_state", fail_on_final_state)
    with pytest.raises(RuntimeError, match="final state write failed"):
        run_goal_iteration(
            definition,
            worker=FakeWorker(_worker_observation()),
            verifier=FakeVerifier(),
            now=NOW,
        )

    assert load_goal_state(JOB_ID).status == "running"
    report_path = (
        goal_state.goal_run_dir(JOB_ID)
        / "iterations"
        / "000001"
        / "report.json"
    )
    assert report_path.exists()
    original = report_path.read_bytes()
    transition_path = report_path.with_name("transition.json")
    committed_transition = json.loads(transition_path.read_text(encoding="utf-8"))
    assert committed_transition["next_status"] == "scheduled"

    monkeypatch.setattr(goal_runner, "save_goal_state", real_save)
    recovery_worker = FakeWorker(_worker_observation())
    recovered = run_goal_iteration(
        definition,
        worker=recovery_worker,
        verifier=FakeVerifier(),
        now=NOW + timedelta(minutes=1),
    )
    assert recovery_worker.calls == []
    assert recovered.transition.reason == "progress"
    assert recovered.transition.next_state.status == "scheduled"
    assert load_goal_state(JOB_ID) == recovered.transition.next_state
    assert json.loads(transition_path.read_text(encoding="utf-8"))["next_status"] == load_goal_state(JOB_ID).status
    assert report_path.read_bytes() == original


def test_definition_job_id_must_match_committed_state(definition, monkeypatch):
    monkeypatch.setattr(
        goal_runner,
        "load_goal_state",
        lambda _job_id: new_goal_state("def456abc123", now=NOW),
    )

    with pytest.raises(GoalRunnerError):
        run_goal_iteration(
            definition,
            worker=FakeWorker(_worker_observation()),
            verifier=FakeVerifier(),
            now=NOW,
        )
