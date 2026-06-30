"""Tests for durable, profile-local goal run state (Bounded Goal Runner Task 1).

Covers the engine-neutral persistence contract:
  - GoalRunState model defaults and frozen-ness
  - job-id validation and path confinement (``^[a-f0-9]{12}$`` under goal-runs)
  - missing state -> None
  - atomic state.json replacement (state.json.tmp -> state.json)
  - stale .tmp recovery (never treated as committed state)
  - malformed committed JSON and unknown schema versions raise GoalStateError
  - immutable, exclusive-create iteration record files

These tests never touch the real profile: they monkeypatch
``cron.goal_state.get_hermes_home`` at a per-test tmp dir, as the plan mandates.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest


@pytest.fixture()
def goal_home(tmp_path, monkeypatch):
    """Point goal_state at an isolated HERMES_HOME for the test."""
    home = tmp_path / "ghome"
    home.mkdir()
    monkeypatch.setattr("cron.goal_state.get_hermes_home", lambda: home)
    return home


# A valid 12-char lowercase-hex job id, matching uuid4().hex[:12].
JOB_ID = "abc123def456"


def _now() -> datetime:
    return datetime(2026, 6, 28, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class TestNewGoalState:
    def test_initial_fields(self, goal_home):
        from cron.goal_state import new_goal_state

        state = new_goal_state(JOB_ID, now=_now())
        assert state.schema_version == 1
        assert state.job_id == JOB_ID
        assert state.status == "scheduled"
        assert state.iteration == 0
        assert state.accumulated_cost_usd == Decimal("0")
        assert state.cost_accounting == "complete"
        assert state.accumulated_wall_seconds == 0.0
        assert state.no_progress_count == 0
        assert state.infrastructure_failures == 0
        assert state.last_evidence_hash is None
        assert state.last_verifier_outcome is None
        assert state.pause_reason is None
        assert state.last_error is None
        assert state.started_at is None
        assert state.completed_at is None
        assert state.updated_at == _now()

    def test_state_is_frozen(self, goal_home):
        from cron.goal_state import new_goal_state

        state = new_goal_state(JOB_ID, now=_now())
        with pytest.raises(Exception):
            state.status = "running"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Job-id validation & path confinement
# ---------------------------------------------------------------------------

class TestJobIdValidation:
    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "short",
            "ABC123DEF456",          # uppercase
            "abc123def45",           # 11 chars
            "abc123def4567",         # 13 chars
            "abc123def45g",          # non-hex char
            "../../../etc/passwd",
            "abc/../def",
            "abc123def456/x",
        ],
    )
    def test_bad_job_id_rejected(self, goal_home, bad):
        from cron.goal_state import GoalStateError, goal_run_dir, new_goal_state

        with pytest.raises(GoalStateError):
            goal_run_dir(bad)
        with pytest.raises(GoalStateError):
            new_goal_state(bad, now=_now())

    def test_goal_run_dir_confined_under_goal_runs_root(self, goal_home):
        from cron.goal_state import goal_run_dir

        d = goal_run_dir(JOB_ID)
        root = (goal_home / "cron" / "goal-runs").resolve()
        assert d == (root / JOB_ID)
        assert d.parent == root


# ---------------------------------------------------------------------------
# Save / load round-trip
# ---------------------------------------------------------------------------

class TestSaveLoadRoundTrip:
    def test_missing_state_returns_none(self, goal_home):
        from cron.goal_state import load_goal_state

        assert load_goal_state(JOB_ID) is None

    def test_round_trip_simple(self, goal_home):
        from cron.goal_state import load_goal_state, new_goal_state, save_goal_state

        state = new_goal_state(JOB_ID, now=_now())
        save_goal_state(state)
        loaded = load_goal_state(JOB_ID)
        assert loaded == state

    def test_round_trip_with_all_fields_populated(self, goal_home):
        from cron.goal_state import GoalRunState, load_goal_state, save_goal_state

        state = GoalRunState(
            schema_version=1,
            job_id=JOB_ID,
            status="paused",
            iteration=7,
            accumulated_cost_usd=Decimal("1.2345"),
            cost_accounting="incomplete",
            accumulated_wall_seconds=12.5,
            no_progress_count=2,
            infrastructure_failures=1,
            last_evidence_hash="a" * 64,
            last_summary="did a thing",
            last_verifier_outcome="fail",
            pause_reason="cost_unknown",
            last_error="boom",
            started_at=datetime(2026, 6, 28, 10, 0, 0, tzinfo=timezone.utc),
            completed_at=None,
            updated_at=_now(),
        )
        save_goal_state(state)
        assert load_goal_state(JOB_ID) == state

    def test_atomic_replace_leaves_no_tmp(self, goal_home):
        from cron.goal_state import goal_run_dir, new_goal_state, save_goal_state

        path = save_goal_state(new_goal_state(JOB_ID, now=_now()))
        assert path.name == "state.json"
        assert path.exists()
        assert not (goal_run_dir(JOB_ID) / "state.json.tmp").exists()

    def test_stale_tmp_is_ignored_and_overwritten(self, goal_home):
        from cron.goal_state import (
            goal_run_dir,
            load_goal_state,
            new_goal_state,
            save_goal_state,
        )

        run_dir = goal_run_dir(JOB_ID)
        run_dir.mkdir(parents=True, exist_ok=True)
        stale = run_dir / "state.json.tmp"
        stale.write_text("garbage not json {", encoding="utf-8")

        # A stale tmp is never committed state.
        assert load_goal_state(JOB_ID) is None

        save_goal_state(new_goal_state(JOB_ID, now=_now()))
        assert not stale.exists()
        assert load_goal_state(JOB_ID) is not None


# ---------------------------------------------------------------------------
# Corruption / schema rejection
# ---------------------------------------------------------------------------

class TestRejectsCorruptState:
    def test_malformed_json_raises(self, goal_home):
        from cron.goal_state import GoalStateError, goal_run_dir, load_goal_state

        run_dir = goal_run_dir(JOB_ID)
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "state.json").write_text("{ not valid json", encoding="utf-8")

        with pytest.raises(GoalStateError):
            load_goal_state(JOB_ID)

    def test_unknown_schema_version_raises(self, goal_home):
        from cron.goal_state import GoalStateError, goal_run_dir, load_goal_state

        run_dir = goal_run_dir(JOB_ID)
        run_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 2,
            "job_id": JOB_ID,
            "status": "scheduled",
            "iteration": 0,
            "accumulated_cost_usd": "0",
            "cost_accounting": "complete",
            "accumulated_wall_seconds": 0.0,
            "no_progress_count": 0,
            "infrastructure_failures": 0,
            "last_evidence_hash": None,
            "last_summary": None,
            "last_verifier_outcome": None,
            "pause_reason": None,
            "last_error": None,
            "started_at": None,
            "completed_at": None,
            "updated_at": _now().isoformat(),
        }
        (run_dir / "state.json").write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(GoalStateError):
            load_goal_state(JOB_ID)

    def test_committed_job_id_must_match_its_goal_directory(self, goal_home):
        from cron.goal_state import (
            GoalStateError,
            goal_run_dir,
            load_goal_state,
            new_goal_state,
            save_goal_state,
        )

        other_job_id = "def456abc123"
        state_path = save_goal_state(new_goal_state(JOB_ID, now=_now()))
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        payload["job_id"] = other_job_id
        state_path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(GoalStateError, match="job id mismatch"):
            load_goal_state(JOB_ID)

        assert not goal_run_dir(other_job_id).exists()


# ---------------------------------------------------------------------------
# Immutable iteration records
# ---------------------------------------------------------------------------

class TestIterationRecords:
    def test_record_layout(self, goal_home):
        from cron.goal_state import goal_run_dir, save_iteration_record

        path = save_iteration_record(JOB_ID, 1, "report", {"summary": "ok"})
        expected = goal_run_dir(JOB_ID) / "iterations" / "000001" / "report.json"
        assert path == expected
        assert json.loads(path.read_text(encoding="utf-8")) == {"summary": "ok"}

    def test_records_are_immutable(self, goal_home):
        from cron.goal_state import GoalStateError, save_iteration_record

        save_iteration_record(JOB_ID, 1, "report", {"a": 1})
        with pytest.raises(GoalStateError):
            save_iteration_record(JOB_ID, 1, "report", {"a": 2})

    def test_serialization_failure_does_not_publish_a_partial_record(self, goal_home):
        from cron.goal_state import goal_run_dir, save_iteration_record

        target = goal_run_dir(JOB_ID) / "iterations" / "000001" / "report.json"

        with pytest.raises(TypeError):
            save_iteration_record(
                JOB_ID,
                1,
                "report",
                {"bad": object()},  # type: ignore[dict-item]
            )

        assert not target.exists()
        assert save_iteration_record(JOB_ID, 1, "report", {"ok": True}) == target

    def test_distinct_kinds_and_iterations_coexist(self, goal_home):
        from cron.goal_state import save_iteration_record

        save_iteration_record(JOB_ID, 1, "report", {"a": 1})
        save_iteration_record(JOB_ID, 1, "verification", {"b": 2})
        save_iteration_record(JOB_ID, 1, "transition", {"c": 3})
        save_iteration_record(JOB_ID, 2, "report", {"d": 4})  # must not raise

    def test_unknown_kind_rejected(self, goal_home):
        from cron.goal_state import GoalStateError, save_iteration_record

        with pytest.raises(GoalStateError):
            save_iteration_record(JOB_ID, 1, "bogus", {"a": 1})  # type: ignore[arg-type]
