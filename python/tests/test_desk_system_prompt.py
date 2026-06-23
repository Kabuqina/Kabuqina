# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Test desk_system_prompt overlay — search behavior & prompt blocks."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_PY_ROOT = Path(__file__).resolve().parents[1]
if str(_PY_ROOT) not in sys.path:
    sys.path.insert(0, str(_PY_ROOT))


class TestDeskSystemPrompt(unittest.TestCase):
    """Test _block_search_behavior and related prompt-building functions."""

    def setUp(self) -> None:
        os.environ.pop("HERMESDESK_WORKSPACE", None)
        os.environ.pop("HERMES_WORKSPACE", None)

    # ── _block_search_behavior ────────────────────────────────────────

    def test_block_search_behavior_contains_student_friendly_sources(self) -> None:
        from overlays.desk_system_prompt import _block_search_behavior

        text = _block_search_behavior()
        self.assertIn("domestic", text, "should mention domestic sources")
        self.assertIn("Baidu Baike", text, "should include Baidu Baike as example")
        self.assertIn("Zhihu", text, "should include Zhihu as example")
        self.assertIn("Bilibili", text, "should include Bilibili as example")
        self.assertIn("last resort", text, "should mention last resort")
        self.assertIn("site:zhihu.com", text, "should show site: operator example")

    def test_block_search_behavior_no_enterprise_content(self) -> None:
        """Student-oriented agent: no enterprise / corporate / intranet references."""
        from overlays.desk_system_prompt import _block_search_behavior

        text = _block_search_behavior()
        self.assertNotIn("enterprise", text)
        self.assertNotIn("corporate", text)
        self.assertNotIn("Confluence", text)
        self.assertNotIn("SearXNG", text)

    def test_block_search_behavior_respects_explicit_request(self) -> None:
        from overlays.desk_system_prompt import _block_search_behavior

        text = _block_search_behavior()
        self.assertIn("respect that request", text,
                      "should respect user's explicit external source request")

    # ── _block_power_off ──────────────────────────────────────────────

    def test_block_power_off_contains_search_behavior(self) -> None:
        from overlays.desk_system_prompt import _block_power_off

        text = _block_power_off()
        self.assertIn("Search preference", text,
                      "power-off prompt should include search behavior")
        self.assertIn("小娜", text,
                      "power-off prompt should include 小娜")

    def test_block_power_off_contains_workspace_guidance(self) -> None:
        from overlays.desk_system_prompt import _block_power_off

        text = _block_power_off()
        self.assertIn("Workspace file access", text)

    def test_block_power_off_no_terminal(self) -> None:
        """Non-power-user prompt should mention no terminal."""
        from overlays.desk_system_prompt import _block_power_off

        text = _block_power_off()
        self.assertNotIn("Power user mode is on", text)
        self.assertIn("do not have the `terminal` tool", text)

    # ── _block_power_on ───────────────────────────────────────────────

    def test_block_power_on_contains_search_behavior(self) -> None:
        from overlays.desk_system_prompt import _block_power_on

        text = _block_power_on()
        self.assertIn("Search preference", text,
                      "power-on prompt should include search behavior")

    def test_block_power_on_has_power_user_mode(self) -> None:
        from overlays.desk_system_prompt import _block_power_on

        text = _block_power_on()
        self.assertIn("Power user mode is on", text)

    def test_block_power_on_contains_workspace_guidance(self) -> None:
        from overlays.desk_system_prompt import _block_power_on

        text = _block_power_on()
        self.assertIn("Workspace file access", text)

    # ── _workspace_hint ───────────────────────────────────────────────

    def test_workspace_hint_default_when_unset(self) -> None:
        from overlays.desk_system_prompt import _workspace_hint

        hint = _workspace_hint()
        self.assertIn("Documents/KabuqinaWork", hint,
                      "default hint should mention default workspace")

    # ── _has_power_user_style_tools ───────────────────────────────────

    def test_has_power_user_style_tools_true_for_terminal(self) -> None:
        from overlays.desk_system_prompt import _has_power_user_style_tools

        self.assertTrue(_has_power_user_style_tools({"terminal"}))

    def test_has_power_user_style_tools_false_for_web(self) -> None:
        from overlays.desk_system_prompt import _has_power_user_style_tools

        self.assertFalse(_has_power_user_style_tools({"web", "file"}))

    def test_has_power_user_style_tools_empty(self) -> None:
        from overlays.desk_system_prompt import _has_power_user_style_tools

        self.assertFalse(_has_power_user_style_tools(set()))


if __name__ == "__main__":
    unittest.main()
