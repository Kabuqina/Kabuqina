# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Tests for desktop_timezone bootstrap."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path as _Path

_src = str(_Path(__file__).resolve().parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)
import unittest
from pathlib import Path
from unittest import mock

from desktop_timezone import (
    apply_desktop_timezone,
    parse_timezone_from_prefs,
    resolve_desktop_timezone,
    sync_host_prefs_from_shared,
    windows_iana_timezone,
)


class TestWindowsRegistryTz(unittest.TestCase):
    def test_wa_maps_via_vendored_table(self):
        from windows_registry_tz import WIN_TZ

        self.assertEqual(WIN_TZ["W. Australia Standard Time"], "Australia/Perth")
        self.assertEqual(WIN_TZ["China Standard Time"], "Asia/Shanghai")

    def test_windows_iana_on_this_machine(self):
        tz = windows_iana_timezone()
        self.assertTrue(tz, "expected registry → IANA on Windows")


class TestParseTimezoneFromPrefs(unittest.TestCase):
    def test_parses_line(self):
        text = "language: zh\ntimezone: Asia/Shanghai\npreferred_name: x"
        self.assertEqual(parse_timezone_from_prefs(text), "Asia/Shanghai")

    def test_empty(self):
        self.assertEqual(parse_timezone_from_prefs(""), "")


class TestResolveDesktopTimezone(unittest.TestCase):
    def setUp(self):
        self._env_pop = os.environ.pop("HERMES_TIMEZONE", None)
        self._current_env_pop = os.environ.pop("KABUQINA_TIMEZONE", None)

    def tearDown(self):
        if self._env_pop is not None:
            os.environ["HERMES_TIMEZONE"] = self._env_pop
        else:
            os.environ.pop("HERMES_TIMEZONE", None)
        if self._current_env_pop is not None:
            os.environ["KABUQINA_TIMEZONE"] = self._current_env_pop
        else:
            os.environ.pop("KABUQINA_TIMEZONE", None)

    def test_prefs_win_over_stale_config(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            (home / "shared").mkdir()
            (home / "shared" / "USER_PREFS.md").write_text(
                "timezone: Asia/Shanghai\n", encoding="utf-8"
            )
            (home / "config.yaml").write_text("timezone: Asia/Yekaterinburg\n", encoding="utf-8")
            os.environ["HERMES_HOME"] = str(home)
            with mock.patch(
                "desktop_timezone.windows_iana_timezone", return_value="Asia/Shanghai"
            ):
                self.assertEqual(resolve_desktop_timezone(home), "Asia/Shanghai")

    def test_placeholder_prefs_uses_windows(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            (home / "shared").mkdir()
            (home / "shared" / "USER_PREFS.md").write_text(
                "timezone: America/New_York\n", encoding="utf-8"
            )
            os.environ["HERMES_HOME"] = str(home)
            with mock.patch(
                "desktop_timezone.windows_iana_timezone", return_value="Asia/Shanghai"
            ):
                self.assertEqual(resolve_desktop_timezone(home), "Asia/Shanghai")

    def test_apply_sets_env(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            os.environ["HERMES_HOME"] = str(home)
            os.environ.pop("HERMES_TIMEZONE", None)
            with mock.patch(
                "desktop_timezone.windows_iana_timezone", return_value="Asia/Shanghai"
            ):
                iana = apply_desktop_timezone(home)
            self.assertEqual(iana, "Asia/Shanghai")
            self.assertEqual(os.environ.get("KABUQINA_TIMEZONE"), "Asia/Shanghai")
            self.assertEqual(os.environ.get("HERMES_TIMEZONE"), "Asia/Shanghai")


class TestSyncHostPrefs(unittest.TestCase):
    def test_copies_nonempty(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            (home / "shared").mkdir()
            (home / "shared" / "USER_PREFS.md").write_text("timezone: UTC\n", encoding="utf-8")
            sync_host_prefs_from_shared(home)
            self.assertEqual(
                (home / "_host_prefs.md").read_text(encoding="utf-8"),
                "timezone: UTC\n",
            )


if __name__ == "__main__":
    unittest.main()
