# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Desk-minimal lazy tool discovery."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_root = Path(__file__).resolve().parent.parent.parent
_hermes = _root / "hermes_core"
if _hermes.is_dir() and str(_hermes) not in sys.path:
    sys.path.insert(0, str(_hermes))


class TestDeskMinimalLazyTools(unittest.TestCase):
    def test_ensure_tools_discovered_is_lazy_under_desk_minimal(self):
        with patch.dict(os.environ, {"HERMESDESK_DESK_MINIMAL": "1"}, clear=False):
            import importlib
            import model_tools

            importlib.reload(model_tools)
            self.assertFalse(model_tools._TOOLS_DISCOVERED)

            with patch.object(model_tools, "discover_builtin_tools") as mock_discover:
                model_tools.ensure_tools_discovered()
                mock_discover.assert_called_once()
            self.assertTrue(model_tools._TOOLS_DISCOVERED)


if __name__ == "__main__":
    unittest.main()
