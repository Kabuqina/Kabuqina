# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Goal Runner Task 9 Step 2 — per-profile isolation.

Host and gateway profiles are distinct `KABUQINA_HOME` trees. The same job id in
two homes must resolve, lock, and project only its active home, and Pilot 1
must not execute a goal in a gateway-shaped profile (its `cron.goal_loop` gate
stays disabled) even if a goal job file is copied there.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest
import yaml

from cron.goal_state import load_goal_state, new_goal_state, save_goal_state

NOW = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)
JOB_ID = "abc123def456"


def _use_home(monkeypatch, home):
    from kabuqina_cli import config_loader

    monkeypatch.setenv("KABUQINA_HOME", str(home))
    config_loader._LOAD_CONFIG_CACHE.clear()


def _write_state(status):
    save_goal_state(
        replace(new_goal_state(JOB_ID, now=NOW), status=status, updated_at=NOW)
    )


def _enable_goal_loop(home):
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text(
        yaml.safe_dump({"cron": {"goal_loop": {"enabled": True}}}), encoding="utf-8"
    )


def _make_goal_job(home_dir, status):
    from cron.jobs import create_job

    workdir = home_dir / "wd"
    workdir.mkdir(parents=True, exist_ok=True)
    job = create_job(
        prompt="do one unit",
        schedule="every 1h",
        mode="goal",
        goal="obj",
        workdir=str(workdir),
        verifier={"kind": "artifact_exists", "config": {}},
        limits={"max_runs": 5, "max_wall_seconds": 600},
    )
    save_goal_state(
        replace(new_goal_state(job["id"], now=NOW), status=status, updated_at=NOW)
    )
    return job


class _FakeWorker:
    def __init__(self):
        self.calls = 0

    def run_iteration(self, definition, state):
        from decimal import Decimal

        from cron.goal_runner import WorkerObservation
        from cron.goal_state import GoalReport
        from cron.goal_usage import GoalUsageSnapshot

        self.calls += 1
        return WorkerObservation(
            report=GoalReport("progress", "did work", (), {"n": 1}, "go", ()),
            usage=GoalUsageSnapshot(
                events=(), amount_usd=Decimal("0.01"), complete=True, incomplete_reason=None
            ),
            full_output="out",
            wall_seconds=1.0,
            infrastructure_error=None,
            ambiguous_external_effect=False,
        )


def test_goal_state_is_isolated_across_homes(tmp_path, monkeypatch):
    host = tmp_path / "host"
    gateway = tmp_path / "gateway"

    _use_home(monkeypatch, host)
    _write_state("scheduled")
    _use_home(monkeypatch, gateway)
    _write_state("paused")

    _use_home(monkeypatch, host)
    assert load_goal_state(JOB_ID).status == "scheduled"
    _use_home(monkeypatch, gateway)
    assert load_goal_state(JOB_ID).status == "paused"


def test_lock_file_path_follows_active_home(tmp_path, monkeypatch):
    from cron.goal_controls import _lock_file

    _use_home(monkeypatch, tmp_path / "host")
    host_lock = _lock_file()
    _use_home(monkeypatch, tmp_path / "gateway")
    gateway_lock = _lock_file()

    assert host_lock != gateway_lock
    assert host_lock.parent.parent.name == "host"
    assert gateway_lock.parent.parent.name == "gateway"


def test_gateway_home_pauses_execution_while_host_runs(tmp_path, monkeypatch):
    from cron.scheduler import _run_goal_job

    host = tmp_path / "host"
    gateway = tmp_path / "gateway"

    # Host profile: gate enabled → one iteration runs.
    _enable_goal_loop(host)
    _use_home(monkeypatch, host)
    host_job = _make_goal_job(host, "scheduled")
    worker = _FakeWorker()
    host_result = _run_goal_job(host_job, worker=worker, verifier=None, now=NOW)
    assert worker.calls == 1
    assert host_result.transition.next_state.status == "scheduled"

    # Gateway profile: gate stays default-disabled → copied job pauses, no model.
    _use_home(monkeypatch, gateway)
    gw_job = _make_goal_job(gateway, "scheduled")
    blocked = _FakeWorker()
    gw_result = _run_goal_job(gw_job, worker=blocked, verifier=None, now=NOW)
    assert blocked.calls == 0
    assert gw_result.transition.next_state.status == "paused"
    assert gw_result.transition.next_state.pause_reason == "feature_disabled"
