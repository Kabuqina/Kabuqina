# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Unused bundled image_gen backends are seeded into plugins.disabled."""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_root = Path(__file__).resolve().parent.parent
_overlays = _root / "overlays"
_hermes = _root.parent / "hermes_core"
for p in (_root, _overlays, _hermes):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

_EXPECTED = ["image_gen/openai", "image_gen/xai"]


def _fresh_overlay():
    import importlib

    import overlays.disable_image_gen_backends as mod

    mod._INSTALLED = False
    importlib.reload(mod)
    return mod


class TestDisableImageGenBackends(unittest.TestCase):
    def test_seeds_all_three_into_empty_config(self):
        saved = {}
        load = MagicMock(return_value={})
        save = MagicMock(side_effect=lambda cfg: saved.update(cfg))
        with patch("kabuqina_cli.config.load_config", load), patch(
            "kabuqina_cli.config.save_config", save
        ):
            mod = _fresh_overlay()
            mod.install()

        save.assert_called_once()
        self.assertEqual(saved["plugins"]["disabled"], _EXPECTED)
        self.assertTrue(mod._INSTALLED)

    def test_is_additive_and_preserves_user_entries(self):
        saved = {}
        existing = {"plugins": {"disabled": ["some-user-plugin", "image_gen/openai"]}}
        load = MagicMock(return_value=existing)
        save = MagicMock(side_effect=lambda cfg: saved.update(cfg))
        with patch("kabuqina_cli.config.load_config", load), patch(
            "kabuqina_cli.config.save_config", save
        ):
            mod = _fresh_overlay()
            mod.install()

        save.assert_called_once()
        disabled = saved["plugins"]["disabled"]
        # User entry kept, no duplicate of the already-present key, both
        # remaining backends appended.
        self.assertEqual(
            disabled,
            ["some-user-plugin", "image_gen/openai", "image_gen/xai"],
        )

    def test_noop_when_all_already_disabled(self):
        existing = {"plugins": {"disabled": list(_EXPECTED)}}
        load = MagicMock(return_value=existing)
        save = MagicMock()
        with patch("kabuqina_cli.config.load_config", load), patch(
            "kabuqina_cli.config.save_config", save
        ):
            mod = _fresh_overlay()
            mod.install()

        save.assert_not_called()
        self.assertTrue(mod._INSTALLED)

    def test_tolerates_malformed_plugins_section(self):
        saved = {}
        existing = {"plugins": "not-a-dict"}
        load = MagicMock(return_value=existing)
        save = MagicMock(side_effect=lambda cfg: saved.update(cfg))
        with patch("kabuqina_cli.config.load_config", load), patch(
            "kabuqina_cli.config.save_config", save
        ):
            mod = _fresh_overlay()
            mod.install()

        save.assert_called_once()
        self.assertEqual(saved["plugins"]["disabled"], _EXPECTED)


if __name__ == "__main__":
    unittest.main()
