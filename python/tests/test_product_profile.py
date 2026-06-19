# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for ProductProfilePolicy resolution (v0.3.0 Phase A)."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Add python/src to path for test-time imports
_src = str(Path(__file__).resolve().parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from product_profile_policy import (
    DEFAULT_PROFILE,
    GLOBAL_STUDENT_CUT,
    MAINLAND_CN,
    SEA,
    ProductProfilePolicy,
)


class ProductProfileResolveTests(unittest.TestCase):
    def test_missing_profile_resolves_to_mainland_cn(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(ProductProfilePolicy.resolve_profile(), MAINLAND_CN)
        self.assertEqual(DEFAULT_PROFILE, MAINLAND_CN)

    def test_kabuqina_var_selects_profile(self):
        with patch.dict(os.environ, {"KABUQINA_PRODUCT_PROFILE": "sea"}, clear=True):
            self.assertEqual(ProductProfilePolicy.resolve_profile(), SEA)

    def test_hermesdesk_var_is_accepted_as_fallback(self):
        with patch.dict(os.environ, {"HERMESDESK_PRODUCT_PROFILE": "sea"}, clear=True):
            self.assertEqual(ProductProfilePolicy.resolve_profile(), SEA)

    def test_kabuqina_var_wins_over_hermesdesk(self):
        env = {
            "KABUQINA_PRODUCT_PROFILE": "mainland_cn",
            "HERMESDESK_PRODUCT_PROFILE": "sea",
        }
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(ProductProfilePolicy.resolve_profile(), MAINLAND_CN)

    def test_unknown_profile_falls_back_to_default(self):
        with patch.dict(os.environ, {"KABUQINA_PRODUCT_PROFILE": "antarctica"}, clear=True):
            self.assertEqual(ProductProfilePolicy.resolve_profile(), DEFAULT_PROFILE)

    def test_value_is_normalized(self):
        with patch.dict(os.environ, {"KABUQINA_PRODUCT_PROFILE": "  SEA  "}, clear=True):
            self.assertEqual(ProductProfilePolicy.resolve_profile(), SEA)

    def test_empty_value_resolves_to_default_without_error(self):
        with patch.dict(os.environ, {"KABUQINA_PRODUCT_PROFILE": ""}, clear=True):
            self.assertEqual(ProductProfilePolicy.resolve_profile(), MAINLAND_CN)

    def test_is_mainland_cn_helper(self):
        with patch.dict(os.environ, {"KABUQINA_PRODUCT_PROFILE": "mainland_cn"}, clear=True):
            self.assertTrue(ProductProfilePolicy.is_mainland_cn())
        with patch.dict(os.environ, {"KABUQINA_PRODUCT_PROFILE": "sea"}, clear=True):
            self.assertFalse(ProductProfilePolicy.is_mainland_cn())


class MainlandContractTests(unittest.TestCase):
    """The mainland_cn visibility lists must match the approved design."""

    def test_visible_providers_equal_whitelist(self):
        self.assertEqual(
            ProductProfilePolicy.visible_providers(MAINLAND_CN),
            (
                "deepseek", "zai", "kimi-coding", "kimi-coding-cn",
                "stepfun", "minimax-cn", "alibaba", "custom",
            ),
        )

    def test_visible_gateways_equal_whitelist(self):
        self.assertEqual(
            ProductProfilePolicy.visible_gateways(MAINLAND_CN),
            ("weixin", "qqbot", "feishu", "wecom"),
        )

    def test_hidden_toolsets_include_hard_cuts(self):
        hidden = ProductProfilePolicy.hidden_toolsets(MAINLAND_CN)
        for name in (
            "moa", "rl", "homeassistant", "discord", "discord_admin",
            "spotify", "feishu_doc", "feishu_drive", "yuanbao", "delegation",
            "image_gen",
        ):
            self.assertIn(name, hidden)

    def test_hidden_skill_categories_include_approved(self):
        hidden = ProductProfilePolicy.hidden_skill_categories(MAINLAND_CN)
        for name in (
            "apple", "gaming", "red-teaming", "mcp", "mlops", "github",
            "inference-sh", "smart-home", "social-media",
        ):
            self.assertIn(name, hidden)

    def test_default_network_hosts_include_china_providers(self):
        hosts = ProductProfilePolicy.default_network_hosts(MAINLAND_CN)
        for host in ("api.deepseek.com", "api.kimi.com", "dashscope-intl.aliyuncs.com"):
            self.assertIn(host, hosts)

    def test_cut_gateways_are_not_visible_or_autostart(self):
        visible = ProductProfilePolicy.visible_gateways(MAINLAND_CN)
        autostart = ProductProfilePolicy.autostart_gateways(MAINLAND_CN)
        for name in ("telegram", "discord", "dingtalk", "email", "slack", "webhook"):
            self.assertNotIn(name, visible)
            self.assertNotIn(name, autostart)


class GlobalStudentCutTests(unittest.TestCase):
    """global_student_cut is a delete-everywhere list, not a region decision."""

    def test_global_cut_absent_from_visible_lists_both_profiles(self):
        for profile in (MAINLAND_CN, SEA):
            providers = set(ProductProfilePolicy.visible_providers(profile))
            gateways = set(ProductProfilePolicy.visible_gateways(profile))
            self.assertEqual(providers & GLOBAL_STUDENT_CUT, set())
            self.assertEqual(gateways & GLOBAL_STUDENT_CUT, set())

    def test_sea_keepers_are_not_global_cuts(self):
        # Providers/gateways reserved for the future sea branch must not be
        # marked as global deletions.
        for name in (
            "openai", "google", "gemini", "anthropic", "claude", "openrouter",
            "groq", "mistral", "huggingface",
            "telegram", "whatsapp", "email", "discord",
        ):
            self.assertNotIn(name, GLOBAL_STUDENT_CUT)

    def test_global_cut_contains_expected_deletions(self):
        for name in (
            "bedrock", "openai-codex", "copilot-acp", "opencode",
            "homeassistant", "slack", "webhook", "api_server", "moa",
        ):
            self.assertIn(name, GLOBAL_STUDENT_CUT)


if __name__ == "__main__":
    unittest.main()
