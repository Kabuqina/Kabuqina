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

    def test_desktop_requirements_include_click_for_uvicorn(self):
        path = ROOT / "python" / "requirements-desktop.txt"
        lines = path.read_text("utf-8").splitlines()
        normalized = [
            line.split("#", 1)[0].strip().lower()
            for line in lines
            if line.split("#", 1)[0].strip()
        ]
        self.assertIn("click>=8.1.8,<9", normalized)

    def test_bundle_verifier_checks_click_choice(self):
        path = ROOT / "python" / "tools" / "verify_bundle_site_packages.py"
        text = path.read_text("utf-8")
        self.assertIn("import click", text)
        self.assertIn('hasattr(click, "Choice")', text)

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
