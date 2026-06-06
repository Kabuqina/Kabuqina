# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Tests for gateway_env_loader (cron weixin delivery prerequisites)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_SRC = Path(__file__).resolve().parents[1] / "src"
_HERMES_CORE = Path(__file__).resolve().parents[2] / "hermes_core"
for _p in (_SRC, _HERMES_CORE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


class TestGatewayEnvLoader(unittest.TestCase):
    def test_loads_weixin_token_from_hermes_home_env(self):
        import gateway_env_loader as gel

        gel._LOADED = False
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "hermes-home"
            home.mkdir(parents=True)
            (home / ".env").write_text(
                "WEIXIN_TOKEN=test-token-abc\nWEIXIN_ACCOUNT_ID=acct-1\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["HERMES_HOME"] = str(home)
            env.pop("WEIXIN_TOKEN", None)
            env.pop("WEIXIN_ACCOUNT_ID", None)
            with patch.dict(os.environ, env, clear=True):
                gel._LOADED = False
                gel.ensure_gateway_env_loaded()
                self.assertEqual(os.environ.get("WEIXIN_TOKEN"), "test-token-abc")
                self.assertEqual(os.environ.get("WEIXIN_ACCOUNT_ID"), "acct-1")

    def test_collect_messaging_hosts_includes_weixin(self):
        import gateway_env_loader as gel

        with patch.dict(
            os.environ,
            {
                "WEIXIN_TOKEN": "t",
                "WEIXIN_BASE_URL": "https://ilink.example.com",
            },
            clear=False,
        ):
            hosts = gel.collect_messaging_hosts_from_environ()
        self.assertIn("ilink.example.com", hosts)
        # Telegram disabled — removed from Kabuqina product scope (codex/student-deliverables)
        # self.assertIn("api.telegram.org", hosts)

    def test_refresh_extends_network_policy(self):
        import gateway_env_loader as gel
        from network_policy import NetworkPolicy
        from overlays import network_allowlist as na

        na._policy = NetworkPolicy(llm_host="")
        na._net_open = False
        with patch.dict(os.environ, {"FEISHU_APP_ID": "x", "FEISHU_APP_SECRET": "y"}, clear=False):
            gel.refresh_messaging_network_allowlist()
        self.assertIn("open.feishu.cn", na._policy.allowed_hosts)


if __name__ == "__main__":
    unittest.main()
