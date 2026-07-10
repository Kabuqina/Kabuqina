# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Regression tests for desk startup latency safeguards."""

from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

_root = Path(__file__).resolve().parent.parent.parent
_hermes = _root / "hermes_core"
_src = _root / "python" / "src"
for p in (_hermes, _src):
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))


class TestDeskWarm(unittest.TestCase):
    def setUp(self):
        from desk_server import warm

        self.warm = warm
        warm._warm_event.clear()
        warm._auto_load_packages_started.clear()

    def tearDown(self):
        self.warm._warm_event.set()
        self.warm._auto_load_packages_started.clear()

    def test_server_warm_primes_agent_but_defers_optional_downloads(self):
        with patch("model_tools.ensure_tools_discovered"), patch.object(
            self.warm, "_warm_agent_runtime"
        ) as runtime_warm, patch.object(self.warm, "_start_auto_load_packages") as downloads:
            self.warm.ensure_desk_warmed()
            for _ in range(100):
                if runtime_warm.called:
                    break
                threading.Event().wait(0.01)

        self.assertTrue(runtime_warm.called)
        downloads.assert_not_called()

    def test_optional_downloads_start_once_after_first_chat(self):
        called = threading.Event()

        def mark_started():
            called.set()

        with patch.object(self.warm, "_start_auto_load_packages", side_effect=mark_started) as downloads:
            self.warm.start_auto_load_packages_after_first_chat()
            self.assertTrue(called.wait(1))
            self.warm.start_auto_load_packages_after_first_chat()

        downloads.assert_called_once()


if __name__ == "__main__":
    unittest.main()
