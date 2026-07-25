# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Regression test for active platform documentation convergence."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "scripts" / "audit_active_platform_docs.py"


class ActivePlatformDocsTests(unittest.TestCase):
    def test_active_platform_docs_match_c0_manifest(self):
        result = subprocess.run(
            [sys.executable, str(AUDIT)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("retained=6 removed_advertisements=0", result.stdout)

    def test_audit_covers_registries_and_user_facing_surfaces(self):
        text = AUDIT.read_text(encoding="utf-8")

        for surface in (
            "environment-variables.md",
            "toolsets-reference.md",
            "features/cron.md",
            "cli-commands.md",
            "messaging",
            "hermes_core/README.md",
        ):
            self.assertIn(surface, text)


if __name__ == "__main__":
    unittest.main()
