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
            "learning_recovery",
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
        for retained_input in (
            "site-packages/aiohttp/__init__.py",
            "site-packages/certifi/__init__.py",
            "site-packages/cryptography/__init__.py",
            "site-packages/qrcode/__init__.py",
            "site-packages/telegram/__init__.py",
            "site-packages/python_telegram_bot-*.dist-info",
            "site-packages/dingtalk_stream/__init__.py",
            "site-packages/dingtalk_stream-0.24.3.dist-info",
            "site-packages/alibabacloud_dingtalk/__init__.py",
            "node/node.exe",
            "node/LICENSE",
            "node/VERSION",
            "kabuqina/scripts/whatsapp-bridge/bridge.js",
            "kabuqina/scripts/whatsapp-bridge/runtime_paths.js",
            "kabuqina/scripts/whatsapp-bridge/package-lock.json",
            "node_modules/@whiskeysockets/baileys/package.json",
        ):
            self.assertIn(retained_input, text)

    def test_profile_verifier_fails_before_imports_when_retained_inputs_are_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            (runtime / "site-packages").mkdir()
            result = subprocess.run(
                [sys.executable, str(PROFILE_PLATFORM_VERIFIER), str(runtime)],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "missing retained runtime input: site-packages/telegram/__init__.py",
            result.stderr,
        )
        self.assertIn(
            "missing retained runtime input: "
            "kabuqina/scripts/whatsapp-bridge/package-lock.json",
            result.stderr,
        )

    def test_whatsapp_dependencies_are_build_time_only(self):
        adapter = (
            ROOT / "hermes_core" / "gateway" / "platforms" / "whatsapp.py"
        ).read_text(encoding="utf-8")
        build_script = (ROOT / "python" / "build_bundle.ps1").read_text(encoding="utf-8")

        self.assertNotIn('["npm", "install"', adapter)
        self.assertIn("Bundled WhatsApp bridge dependencies are missing", adapter)
        self.assertIn("& $npmCommand ci --omit=dev --no-audit", build_script)
        self.assertNotIn("git+ssh://git@github.com", (
            ROOT / "hermes_core" / "scripts" / "whatsapp-bridge" / "package-lock.json"
        ).read_text(encoding="utf-8"))
        self.assertIn("whatsappLockHash", build_script)
        self.assertIn("Reusing cached WhatsApp bridge dependencies", build_script)

    def test_dingtalk_uses_modern_websockets_compatible_sdk(self):
        requirements = (
            ROOT / "python" / "requirements-desktop.txt"
        ).read_text(encoding="utf-8")
        core = (ROOT / "hermes_core" / "pyproject.toml").read_text(encoding="utf-8")
        lock = (ROOT / "hermes_core" / "uv.lock").read_text(encoding="utf-8")

        self.assertIn("dingtalk-stream==0.24.3", requirements)
        self.assertIn("alibabacloud-dingtalk>=2.2.42,<3", requirements)
        self.assertIn("websockets>=15,<17", requirements)
        self.assertIn('"dingtalk-stream==0.24.3"', core)
        self.assertIn(
            '{ name = "dingtalk-stream", marker = "extra == \'dingtalk\'", specifier = "==0.24.3" }',
            lock,
        )
        self.assertIn(
            '{ name = "alibabacloud-dingtalk", marker = "extra == \'dingtalk\'", specifier = ">=2.2.42,<3" }',
            lock,
        )
        self.assertNotIn("websockets<13", requirements)

    def test_whatsapp_owns_pinned_node_runtime(self):
        build_script = (ROOT / "python" / "build_bundle.ps1").read_text(encoding="utf-8")
        adapter = (
            ROOT / "hermes_core" / "gateway" / "platforms" / "whatsapp.py"
        ).read_text(encoding="utf-8")
        verifier = PROFILE_PLATFORM_VERIFIER.read_text(encoding="utf-8")

        self.assertIn('$NodeVersion = "24.18.0"', build_script)
        self.assertIn(
            "0ae68406b42d7725661da979b1403ec9926da205c6770827f33aac9d8f26e821",
            build_script,
        )
        self.assertIn('"node\\node.exe"', build_script)
        self.assertIn("resolve_whatsapp_node_executable", adapter)
        self.assertIn('"--cache-root"', adapter)
        self.assertIn('expected_version != "v24.18.0"', verifier)
        self.assertIn("actual_version != expected_version", verifier)

    def test_whatsapp_cache_is_validated_and_atomically_published(self):
        build_script = (ROOT / "python" / "build_bundle.ps1").read_text(encoding="utf-8")

        marker = '$whatsappCompletionMarkerName = ".kabuqina-cache-complete.json"'
        install = "$npmCommand ci --omit=dev --no-audit --no-fund"
        validate = "$npmCommand ls --omit=dev --all --json"
        publish = "Move-Item -LiteralPath $whatsappInstallTemp"
        self.assertIn(marker, build_script)
        self.assertIn(".incomplete-$PID-", build_script)
        self.assertIn('$npmCommand = Join-Path $nodeSourceDir "npm.cmd"', build_script)
        self.assertIn('$whatsappCacheKey = "$whatsappLockHash-node-$NodeVersion"', build_script)
        self.assertIn("nodeVersion = $NodeVersion", build_script)
        self.assertIn("schemaVersion = 2", build_script)
        self.assertIn(install, build_script)
        self.assertIn(validate, build_script)
        self.assertIn("Test-WhatsAppInstallCacheReady", build_script)
        self.assertLess(build_script.index(install), build_script.index(validate))
        self.assertLess(build_script.index(validate), build_script.index(publish))

    def test_bundle_cache_is_shared_across_worktrees(self):
        build_script = (ROOT / "python" / "build_bundle.ps1").read_text(encoding="utf-8")

        self.assertIn("KABUQINA_BUNDLE_CACHE", build_script)
        self.assertIn('Join-Path $env:LOCALAPPDATA "Kabuqina\\bundle-cache"', build_script)
        self.assertIn("$LegacyDownload", build_script)
        self.assertIn("One-time, non-destructive migration", build_script)

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

        for name in (
            "kabuqina_env.py",
            "learning_recovery.py",
            "study_review_reminder.py",
        ):
            self.assertIn(f"src\\{name}", build_script)
            self.assertIn(f'"{name}"', sync_script)


if __name__ == "__main__":
    unittest.main()
