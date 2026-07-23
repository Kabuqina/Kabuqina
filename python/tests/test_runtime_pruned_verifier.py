# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Contract tests for v0.3.0 runtime residual pruning."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "python" / "tools" / "verify_runtime_pruned.py"


class RuntimePrunedVerifierTests(unittest.TestCase):
    def test_verifier_reports_cut_runtime_residuals(self):
        self.assertTrue(VERIFIER.exists(), "missing verify_runtime_pruned.py")

        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            residual = runtime / "kabuqina" / "plugins" / "spotify"
            residual.mkdir(parents=True)
            template = (
                runtime
                / "kabuqina"
                / "skills"
                / "creative"
                / "popular-web-designs"
                / "templates"
                / "spotify.md"
            )
            template.parent.mkdir(parents=True)
            template.write_text("cut template", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(VERIFIER), str(runtime)],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("forbidden runtime residual: kabuqina/plugins/spotify", result.stderr)
        self.assertIn(
            "forbidden runtime residual: "
            "kabuqina/skills/creative/popular-web-designs/templates/spotify.md",
            result.stderr,
        )

    def test_verifier_reports_removed_discord_source_and_packages(self):
        self.assertTrue(VERIFIER.exists(), "missing verify_runtime_pruned.py")

        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            source = runtime / "kabuqina" / "gateway" / "platforms" / "discord.py"
            source.parent.mkdir(parents=True)
            source.write_text("# removed adapter\n", encoding="utf-8")
            package = runtime / "site-packages" / "discord"
            package.mkdir(parents=True)
            dist_info = runtime / "site-packages" / "discord_py-2.7.1.dist-info"
            dist_info.mkdir()
            nacl = runtime / "site-packages" / "nacl"
            nacl.mkdir()
            pynacl_info = runtime / "site-packages" / "PyNaCl-1.5.0.dist-info"
            pynacl_info.mkdir()

            result = subprocess.run(
                [sys.executable, str(VERIFIER), str(runtime)],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        for residual in (
            "kabuqina/gateway/platforms/discord.py",
            "site-packages/discord",
            "site-packages/discord_py-2.7.1.dist-info",
            "site-packages/nacl",
            "site-packages/PyNaCl-1.5.0.dist-info",
        ):
            self.assertIn(f"forbidden runtime residual: {residual}", result.stderr)

    def test_verifier_reports_removed_feishu_sources_worker_and_package(self):
        self.assertTrue(VERIFIER.exists(), "missing verify_runtime_pruned.py")

        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            residuals = (
                "feishu_qr_worker.py",
                "kabuqina/gateway/platforms/feishu.py",
                "kabuqina/gateway/platforms/feishu_comment.py",
                "kabuqina/gateway/platforms/feishu_comment_rules.py",
                "kabuqina/tools/feishu_doc_tool.py",
                "kabuqina/tools/feishu_drive_tool.py",
            )
            for residual in residuals:
                path = runtime / residual
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# removed Feishu/Lark surface\n", encoding="utf-8")
            (runtime / "site-packages" / "lark_oapi").mkdir(parents=True)
            (runtime / "site-packages" / "lark_oapi-1.7.1.dist-info").mkdir()

            result = subprocess.run(
                [sys.executable, str(VERIFIER), str(runtime)],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        for residual in (
            *residuals,
            "site-packages/lark_oapi",
            "site-packages/lark_oapi-1.7.1.dist-info",
        ):
            self.assertIn(f"forbidden runtime residual: {residual}", result.stderr)

    def test_verifier_reports_removed_wecom_sources_and_worker(self):
        self.assertTrue(VERIFIER.exists(), "missing verify_runtime_pruned.py")

        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            residuals = (
                "wecom_qr_worker.py",
                "kabuqina/gateway/platforms/wecom.py",
                "kabuqina/gateway/platforms/wecom_callback.py",
                "kabuqina/gateway/platforms/wecom_crypto.py",
            )
            for residual in residuals:
                path = runtime / residual
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# removed WeCom surface\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(VERIFIER), str(runtime)],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        for residual in residuals:
            self.assertIn(f"forbidden runtime residual: {residual}", result.stderr)

    def test_verifier_accepts_clean_runtime(self):
        self.assertTrue(VERIFIER.exists(), "missing verify_runtime_pruned.py")

        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            (runtime / "kabuqina" / "gateway" / "platforms" / "weixin").mkdir(parents=True)
            (runtime / "kabuqina" / "plugins" / "image_gen").mkdir(parents=True)
            toolsets = runtime / "kabuqina" / "toolsets.py"
            toolsets.parent.mkdir(parents=True, exist_ok=True)
            toolsets.write_text("TOOLSETS = {}\n", encoding="utf-8")
            tools_config = runtime / "kabuqina" / "kabuqina_cli" / "tools_config.py"
            tools_config.parent.mkdir(parents=True)
            tools_config.write_text("CONFIGURABLE_TOOLSETS = []\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(VERIFIER), str(runtime)],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("runtime pruning ok", result.stdout)

    def test_verifier_reports_cut_runtime_content(self):
        self.assertTrue(VERIFIER.exists(), "missing verify_runtime_pruned.py")

        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            toolsets = runtime / "kabuqina" / "toolsets.py"
            toolsets.parent.mkdir(parents=True)
            toolsets.write_text('TOOLSETS = {"spotify": {}}\n', encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(VERIFIER), str(runtime)],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "forbidden runtime content: kabuqina/toolsets.py contains 'spotify'",
            result.stderr,
        )

    def test_bundle_and_sync_scripts_run_pruned_verifier(self):
        self.assertTrue(VERIFIER.exists(), "missing verify_runtime_pruned.py")

        build_script = (ROOT / "python" / "build_bundle.ps1").read_text(encoding="utf-8")
        sync_script = (ROOT / "scripts" / "sync-runtime-sources.ps1").read_text(encoding="utf-8")

        self.assertIn("verify_runtime_pruned.py", build_script)
        self.assertIn("verify_runtime_pruned.py", sync_script)

    def test_bundle_does_not_copy_removed_feishu_worker(self):
        build_script = (ROOT / "python" / "build_bundle.ps1").read_text(encoding="utf-8")

        self.assertNotIn(
            'Join-Path $PSScriptRoot "src\\feishu_qr_worker.py"',
            build_script,
        )
        self.assertIn(
            'foreach ($retiredRootPath in @("feishu_qr_worker.py", "wecom_qr_worker.py"))',
            build_script,
        )

    def test_lark_dependency_is_absent_from_desktop_core_and_lock(self):
        sources = (
            ROOT / "python" / "requirements-desktop.txt",
            ROOT / "hermes_core" / "pyproject.toml",
            ROOT / "hermes_core" / "uv.lock",
        )

        for source in sources:
            text = source.read_text(encoding="utf-8").lower()
            self.assertNotIn("lark-oapi", text, source)
            self.assertNotIn("lark_oapi", text, source)


if __name__ == "__main__":
    unittest.main()
