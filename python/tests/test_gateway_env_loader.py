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

_PYTHON_ROOT = Path(__file__).resolve().parents[1]
_SRC = _PYTHON_ROOT / "src"
_HERMES_CORE = Path(__file__).resolve().parents[2] / "hermes_core"
for _p in (_PYTHON_ROOT, _SRC, _HERMES_CORE):
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
                "KABUQINA_PRODUCT_PROFILE": "mainland_cn",
                "WEIXIN_TOKEN": "t",
                "WEIXIN_ACCOUNT_ID": "a",
                "WEIXIN_BASE_URL": "https://ilink.example.com",
            },
            clear=True,
        ):
            hosts = gel.collect_messaging_hosts_from_environ()
        self.assertIn("ilink.example.com", hosts)

    def test_collect_messaging_hosts_ignores_removed_platform_credentials(self):
        import gateway_env_loader as gel

        with patch.dict(
            os.environ,
            {
                "KABUQINA_PRODUCT_PROFILE": "mainland_cn",
                "DISCORD_BOT_TOKEN": "discord-token",
                "SLACK_BOT_TOKEN": "slack-token",
                "FEISHU_APP_ID": "x",
                "FEISHU_APP_SECRET": "y",
                "WECOM_BOT_ID": "b",
                "WECOM_SECRET": "s",
                "MALICIOUS_API_URL": "https://evil.example.test/api",
            },
            clear=True,
        ):
            hosts = gel.collect_messaging_hosts_from_environ()

        self.assertNotIn("discord.com", hosts)
        self.assertNotIn("gateway.discord.gg", hosts)
        self.assertNotIn("slack.com", hosts)
        self.assertNotIn("files.slack.com", hosts)
        self.assertNotIn("open.feishu.cn", hosts)
        self.assertNotIn("qyapi.weixin.qq.com", hosts)
        self.assertNotIn("evil.example.test", hosts)

    def test_refresh_extends_network_policy(self):
        import gateway_env_loader as gel
        from network_policy import NetworkPolicy
        from overlays import network_allowlist as na

        na._policy = NetworkPolicy(llm_host="")
        na._net_open = False
        with patch.dict(os.environ, {
            "KABUQINA_PRODUCT_PROFILE": "mainland_cn",
            "QQ_APP_ID": "x",
            "QQ_CLIENT_SECRET": "y",
        }, clear=True):
            gel.refresh_messaging_network_allowlist()
        self.assertIn("api.sgroup.qq.com", na._policy.allowed_hosts)

    def test_sea_hosts_are_exact_and_unknown_profile_is_closed(self):
        import gateway_env_loader as gel

        with patch.dict(os.environ, {
            "KABUQINA_PRODUCT_PROFILE": "sea",
            "TELEGRAM_BOT_TOKEN": "t",
            "FEISHU_APP_ID": "x",
            "FEISHU_APP_SECRET": "y",
        }, clear=True):
            self.assertEqual(gel.collect_messaging_hosts_from_environ(), {"api.telegram.org"})
        with patch.dict(os.environ, {
            "KABUQINA_PRODUCT_PROFILE": "antarctica",
            "TELEGRAM_BOT_TOKEN": "t",
            "WEIXIN_TOKEN": "t",
            "WEIXIN_ACCOUNT_ID": "a",
        }, clear=True):
            self.assertEqual(gel.collect_messaging_hosts_from_environ(), set())


if __name__ == "__main__":
    unittest.main()
