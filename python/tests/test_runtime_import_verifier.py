# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Contract tests for desktop runtime import verification."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "python" / "tools" / "verify_runtime_imports.py"


class RuntimeImportVerifierTests(unittest.TestCase):
    def test_verifier_lists_desktop_runtime_import_contract(self):
        text = VERIFIER.read_text(encoding="utf-8")

        for module in (
            "desk_server",
            "desk_server.routes.study_routes",
            "desk_server.capabilities",
            "product_profile_policy",
            "learning.flashcards",
            "learning_owner",
        ):
            self.assertIn(module, text)

    def test_verifier_reports_missing_runtime_imports(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            (runtime / "site-packages").mkdir()
            result = subprocess.run(
                [sys.executable, str(VERIFIER), str(runtime)],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("runtime import failed: desk_server", result.stderr)

    def test_bundle_and_sync_scripts_run_runtime_import_verifier(self):
        build_script = (ROOT / "python" / "build_bundle.ps1").read_text(encoding="utf-8")
        sync_script = (ROOT / "scripts" / "sync-runtime-sources.ps1").read_text(encoding="utf-8")

        self.assertIn("verify_runtime_imports.py", build_script)
        self.assertIn("verify_runtime_imports.py", sync_script)


if __name__ == "__main__":
    unittest.main()
