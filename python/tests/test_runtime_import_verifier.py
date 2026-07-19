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
LEGACY_VERIFIER = ROOT / "python" / "tools" / "verify_legacy_runtime_imports.py"
PROFILE_PLATFORM_VERIFIER = ROOT / "python" / "tools" / "verify_profile_platform_imports.py"


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
        self.assertIn("verify_legacy_runtime_imports.py", build_script)
        self.assertIn("verify_legacy_runtime_imports.py", sync_script)
        self.assertIn("verify_profile_platform_imports.py", build_script)
        self.assertIn("verify_profile_platform_imports.py", sync_script)

    def test_profile_verifier_has_exact_retained_and_removed_contracts(self):
        text = PROFILE_PLATFORM_VERIFIER.read_text(encoding="utf-8")
        for module in (
            "gateway.platforms.weixin", "gateway.platforms.qqbot.adapter",
            "gateway.platforms.dingtalk", "gateway.platforms.telegram",
            "gateway.platforms.whatsapp", "gateway.platforms.email",
        ):
            self.assertIn(module, text)
        for removed in ("feishu", "wecom", "discord", "yuanbao", "api_server"):
            self.assertIn(f'"{removed}"', text)
        self.assertIn("_enforce_desktop_single_platform", text)
        self.assertIn('os.environ["KABUQINA_PRODUCT_PROFILE"] = "mainland_cn"', text)
        self.assertIn('os.environ["KABUQINA_GATEWAY_PLATFORM"] = "weixin"', text)

    def test_legacy_verifier_checks_stateful_modules_in_both_orders(self):
        text = LEGACY_VERIFIER.read_text(encoding="utf-8")

        for module in ("config", "config_home", "auth"):
            self.assertIn(f'"{module}"', text)
        self.assertIn('("legacy-first", "canonical-first")', text)
        self.assertIn("PROVIDER_REGISTRY", text)

    def test_bundle_replaces_desk_server_tree_before_copy(self):
        build_script = (ROOT / "python" / "build_bundle.ps1").read_text(encoding="utf-8")

        destination = '$deskServerDest = Join-Path $Dist "desk_server"'
        remove = "Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $deskServerDest"
        copy = (
            'Copy-Item -Recurse -Force (Join-Path $PSScriptRoot "src\\desk_server") '
            "$deskServerDest"
        )
        self.assertIn(destination, build_script)
        self.assertLess(build_script.index(remove), build_script.index(copy))

    def test_bundle_and_fast_sync_copy_desk_route_dependencies(self):
        build_script = (ROOT / "python" / "build_bundle.ps1").read_text(encoding="utf-8")
        sync_script = (ROOT / "scripts" / "sync-runtime-sources.ps1").read_text(encoding="utf-8")

        for name in ("kabuqina_env.py", "study_review_reminder.py"):
            self.assertIn(f"src\\{name}", build_script)
            self.assertIn(f'"{name}"', sync_script)


if __name__ == "__main__":
    unittest.main()
