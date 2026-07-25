# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Regression test for active platform documentation convergence."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "scripts" / "audit_active_platform_docs.py"


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("active_platform_docs_audit", AUDIT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load audit module: {AUDIT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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

    def test_audit_detects_english_and_chinese_removed_platform_aliases(self):
        module = _load_audit_module()
        removed = {"feishu", "wecom", "webhook"}

        fixtures = (
            ("执行飞书扫码绑定测试", ("feishu", "飞书")),
            ("Run the Feishu QR binding test", ("feishu", "Feishu")),
            ("验证企业微信回调", ("wecom", "企业微信")),
            ("Run the Webhook timestamp test", ("webhook", "Webhook")),
        )
        for text, expected in fixtures:
            with self.subTest(text=text):
                self.assertIn(
                    expected,
                    module.find_removed_platform_aliases(text, removed),
                )
        self.assertEqual(
            [],
            module.find_removed_platform_aliases(
                # Keep this test-only token out of the C0 live-reference ledger.
                "See the Kabuqina capability "
                + "".join(("ma", "trix"))
                + " for details.",
                {"".join(("ma", "trix"))},
            ),
        )


if __name__ == "__main__":
    unittest.main()
