# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Goal Runner Task 8 — `mode: goal` scheduler integration behind a flag.

Step 1: the `cron.goal_loop.enabled` gate ships disabled and is resolvable
per profile without disturbing the rest of the `cron` config.
"""

from __future__ import annotations

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
