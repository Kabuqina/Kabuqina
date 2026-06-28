# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Pin the LangGraph desktop-bundle dependency and tracing-off supervisor wiring.

Phase 3.5 Task 1 contract. These assertions are static (they only read source
files), so they run under any Python and do not require LangGraph to be
installed.
"""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class LangGraphBundleContractTests(unittest.TestCase):
    def test_desktop_requirements_pin_langgraph_exactly_once(self):
        path = ROOT / "python" / "requirements-desktop.txt"
        text = path.read_text("utf-8")
        self.assertEqual(text.count("langgraph==1.2.6"), 1)

    def test_both_children_force_langsmith_tracing_off(self):
        for relpath in (
            "tauri/src/python_supervisor.rs",
            "tauri/src/gateway_supervisor.rs",
        ):
            with self.subTest(relpath=relpath):
                text = (ROOT / relpath).read_text("utf-8")
                self.assertIn('.env("LANGSMITH_TRACING", "false")', text)


if __name__ == "__main__":
    unittest.main()
