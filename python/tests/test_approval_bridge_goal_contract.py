# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Regression guards for Goal Task fields at the desktop approval seam."""

from __future__ import annotations

import unittest
from pathlib import Path


class ApprovalBridgeGoalContractTests(unittest.TestCase):
    def test_cron_wrapper_preserves_goal_contract_and_local_delivery(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "overlays"
            / "approval_bridge.py"
        ).read_text(encoding="utf-8")

        for field in (
            "goal",
            "verifier",
            "limits",
            "approval_mode",
            "progress_delivery_every",
        ):
            self.assertIn(f"{field}=", source)
            self.assertIn(f'args.get("{field}")', source)

        self.assertIn(
            'goal_mode = isinstance(mode, str) and mode.strip().lower() == "goal"',
            source,
        )
        self.assertIn(
            'if normalized_action in ("create", "update") and not goal_mode:',
            source,
        )
        self.assertIn("description=(goal or prompt or name or \"\")", source)


if __name__ == "__main__":
    unittest.main()
