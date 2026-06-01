# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Bundled gateway platform plugins are skipped in desk-minimal mode."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_root = Path(__file__).resolve().parent.parent
_overlays = _root / "overlays"
_hermes = _root.parent / "hermes_core"
for p in (_root, _overlays, _hermes):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)


class TestSkipGatewayPlatformPlugins(unittest.TestCase):
    def test_load_plugin_skips_bundled_platform_in_desk_minimal(self):
        with patch.dict(os.environ, {"HERMESDESK_DESK_MINIMAL": "1"}, clear=False):
            import importlib
            import overlays.skip_gateway_platform_plugins as sgpp

            sgpp._INSTALLED = False
            importlib.reload(sgpp)
            sgpp.install()

            from hermes_cli.plugins import PluginManager, PluginManifest

            mgr = PluginManager()
            manifest = PluginManifest(
                name="irc-platform",
                kind="platform",
                source="bundled",
                key="platforms/irc",
            )
            mgr._load_plugin(manifest)

            loaded = mgr._plugins["platforms/irc"]
            self.assertFalse(loaded.enabled)
            self.assertIn("desk-minimal", loaded.error or "")

    def test_install_is_noop_without_desk_minimal(self):
        env = {k: v for k, v in os.environ.items() if k != "HERMESDESK_DESK_MINIMAL"}
        with patch.dict(os.environ, env, clear=True):
            import importlib
            import overlays.skip_gateway_platform_plugins as sgpp
            from hermes_cli.plugins import PluginManager

            orig = PluginManager._load_plugin
            sgpp._INSTALLED = False
            importlib.reload(sgpp)
            sgpp.install()
            self.assertFalse(sgpp._INSTALLED)
            self.assertIs(PluginManager._load_plugin, orig)


if __name__ == "__main__":
    unittest.main()
