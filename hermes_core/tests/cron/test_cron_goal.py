# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Goal Runner Task 8 — `mode: goal` scheduler integration behind a flag.

Step 1: the `cron.goal_loop.enabled` gate ships disabled and is resolvable
per profile without disturbing the rest of the `cron` config.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import yaml

from hermes_cli.config_defaults import DEFAULT_CONFIG


class TestGoalLoopGateDefault:
    def test_gate_is_disabled_in_defaults(self):
        assert DEFAULT_CONFIG["cron"]["goal_loop"]["enabled"] is False

    def test_load_config_resolves_disabled_without_override(self):
        from hermes_cli.config import load_config

        cfg = load_config()

        assert cfg["cron"]["goal_loop"]["enabled"] is False

    def test_gate_enables_per_profile_without_disturbing_cron_siblings(self):
        from hermes_cli import config_loader
        from hermes_cli.config import load_config
        from hermes_constants import get_config_path

        path = get_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump({"cron": {"goal_loop": {"enabled": True}}}),
            encoding="utf-8",
        )
        config_loader._LOAD_CONFIG_CACHE.clear()

        cfg = load_config()

        assert cfg["cron"]["goal_loop"]["enabled"] is True
        # A deep merge must not clobber sibling cron defaults.
        assert cfg["cron"]["wrap_response"] is True
        assert cfg["cron"]["max_parallel_jobs"] is None


def _goal_kwargs(workdir_dir, **overrides):
    kwargs = {
        "prompt": "process one item",
        "schedule": "every 1h",
        "mode": "goal",
        "goal": "complete the inventory",
        "workdir": str(workdir_dir),
        "verifier": {"kind": "artifact_exists", "config": {"paths": ["manifest.json"]}},
        "limits": {"max_runs": 10, "max_wall_seconds": 3600},
        "approval_mode": "ask_before_external_side_effect",
    }
    kwargs.update(overrides)
    return kwargs


class TestLegacyModeNormalizationUnchanged:
    """Adding `goal` must not disturb agent/notify normalization."""

    def test_missing_mode_normalizes_to_agent(self):
        from cron.jobs import create_job

        job = create_job(prompt="check status", schedule="every 1h")

        assert job["mode"] == "agent"
        assert "goal" not in job

    def test_unknown_mode_normalizes_to_agent(self):
        from cron.jobs import create_job

        job = create_job(prompt="check status", schedule="every 1h", mode="bogus")

        assert job["mode"] == "agent"
        assert "goal" not in job

    @pytest.mark.parametrize("alias", ["notify", "static", "message"])
    def test_notify_aliases_still_normalize_to_notify(self, alias):
        from cron.jobs import create_job

        job = create_job(prompt="喝水", schedule="every 1h", mode=alias)

        assert job["mode"] == "notify"
        assert "goal" not in job


class TestGoalJobCreation:
    def test_goal_mode_persists_nested_spec(self, tmp_path):
        from cron.jobs import create_job, get_job

        job = create_job(**_goal_kwargs(tmp_path))

        assert job["mode"] == "goal"
        spec = job["goal"]
        assert spec["objective"] == "complete the inventory"
        assert spec["verifier"] == {
            "kind": "artifact_exists",
            "config": {"paths": ["manifest.json"]},
        }
        assert spec["limits"]["max_runs"] == 10
        assert spec["limits"]["max_wall_seconds"] == 3600
        assert spec["limits"]["max_cost_usd"] is None
        assert spec["limits"]["deadline"] is None
        assert spec["limits"]["no_progress_limit"] == 3
        assert spec["limits"]["max_infrastructure_failures"] == 3
        assert spec["approval_mode"] == "ask_before_external_side_effect"
        assert spec["progress_delivery_every"] is None
        # Round-trips through persistence.
        assert get_job(job["id"])["goal"] == spec

    def test_cost_and_deadline_are_normalized(self, tmp_path):
        from cron.jobs import create_job

        deadline = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
        job = create_job(
            **_goal_kwargs(
                tmp_path,
                limits={
                    "max_runs": 5,
                    "max_wall_seconds": 600,
                    "max_cost_usd": 5,
                    "deadline": deadline.isoformat(),
                    "no_progress_limit": 2,
                },
            )
        )

        assert job["goal"]["limits"]["max_cost_usd"] == "5"
        assert job["goal"]["limits"]["deadline"] == deadline.isoformat()
        assert job["goal"]["limits"]["no_progress_limit"] == 2

    @pytest.mark.parametrize(
        "overrides",
        [
            {"goal": None},
            {"goal": "   "},
            {"workdir": None},
            {"verifier": {"kind": "bogus", "config": {}}},
            {"verifier": {"config": {}}},
            {"verifier": "artifact_exists"},
            {"limits": None},
            {"limits": {"max_wall_seconds": 3600}},
            {"limits": {"max_runs": 0, "max_wall_seconds": 3600}},
            {"limits": {"max_runs": 10, "max_wall_seconds": -1}},
            {"limits": {"max_runs": 10, "max_wall_seconds": 3600, "max_cost_usd": "-1"}},
            {
                "limits": {
                    "max_runs": 10,
                    "max_wall_seconds": 3600,
                    "deadline": "2026-08-01T12:00:00",  # naive
                }
            },
            {"approval_mode": "whatever"},
            {"progress_delivery_every": 0},
            {"prompt": ""},
        ],
    )
    def test_goal_validation_rejects_bad_spec(self, tmp_path, overrides):
        from cron.jobs import create_job

        with pytest.raises(ValueError):
            create_job(**_goal_kwargs(tmp_path, **overrides))

    def test_relative_workdir_is_rejected(self, tmp_path):
        from cron.jobs import create_job

        with pytest.raises(ValueError):
            create_job(**_goal_kwargs(tmp_path, workdir="relative/dir"))


class TestGoalFieldTypoGuard:
    @pytest.mark.parametrize(
        "field",
        ["goal", "verifier", "limits", "approval_mode", "progress_delivery_every"],
    )
    def test_goal_fields_rejected_on_agent_mode(self, field):
        from cron.jobs import create_job

        values = {
            "goal": "x",
            "verifier": {"kind": "artifact_exists"},
            "limits": {"max_runs": 1, "max_wall_seconds": 1},
            "approval_mode": "always",
            "progress_delivery_every": 1,
        }
        with pytest.raises(ValueError):
            create_job(prompt="hi", schedule="every 1h", **{field: values[field]})

    def test_goal_fields_rejected_on_notify_mode(self, tmp_path):
        from cron.jobs import create_job

        with pytest.raises(ValueError):
            create_job(
                prompt="hi",
                schedule="every 1h",
                mode="notify",
                message="hi",
                goal="x",
            )
