# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Regression: gateway.platforms must not be a leaf stub (cron weixin delivery)."""

from __future__ import annotations

import sys
import unittest
import importlib.util
from pathlib import Path
from unittest.mock import patch


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


class TestStripShimsGatewayPlatforms(unittest.TestCase):
    def test_install_does_not_stub_gateway_platforms(self) -> None:
        root = _repo_root()
        overlays = root / "python" / "overlays"
        hermes = root / "hermes_core"
        for p in (str(overlays.parent), str(hermes)):
            if p not in sys.path:
                sys.path.insert(0, p)

        # Simulate a stale stub from an older build.
        import types

        stale = types.ModuleType("gateway.platforms")
        stale.__hermesdesk_stubbed__ = True  # type: ignore[attr-defined]
        sys.modules["gateway.platforms"] = stale

        from overlays import strip_shims

        strip_shims.install()
        self.assertNotIn("gateway.platforms", strip_shims._STUBBED)
        self.assertNotIn("gateway.platforms", sys.modules)

    def test_extract_media_import_after_evict(self) -> None:
        root = _repo_root()
        overlays = root / "python" / "overlays"
        hermes = root / "hermes_core"
        for p in (str(overlays.parent), str(hermes)):
            if p not in sys.path:
                sys.path.insert(0, p)

        from overlays.strip_shims import evict_gateway_platforms_stub

        evict_gateway_platforms_stub()
        sys.modules.pop("gateway.platforms", None)
        sys.modules.pop("gateway.platforms.base", None)

        from gateway.platforms.base import BasePlatformAdapter  # noqa: F401

        media, text = BasePlatformAdapter.extract_media("hello")
        self.assertEqual(text, "hello")
        self.assertEqual(media, [])

    def test_stub_module_metadata_is_not_noop_callable(self) -> None:
        root = _repo_root()
        overlays = root / "python" / "overlays"
        for p in (str(overlays.parent),):
            if p not in sys.path:
                sys.path.insert(0, p)

        sys.modules.pop("gateway.status", None)
        sys.modules.pop("gateway.run", None)

        from overlays import strip_shims

        strip_shims.install()
        status = sys.modules["gateway.status"]

        self.assertIsInstance(status.__file__, str)
        self.assertFalse(callable(status.__file__))
        self.assertIsNotNone(importlib.util.find_spec("gateway.status"))
        with self.assertRaises(AttributeError):
            getattr(status, "__path__")

    def test_install_does_not_preload_third_party_optional_ml_modules(self) -> None:
        root = _repo_root()
        overlays = root / "python" / "overlays"
        if str(overlays.parent) not in sys.path:
            sys.path.insert(0, str(overlays.parent))

        for name in ("wandb", "atroposlib", "tinker"):
            sys.modules.pop(name, None)

        from overlays import strip_shims

        strip_shims.install()

        self.assertNotIn("wandb", sys.modules)
        self.assertNotIn("atroposlib", sys.modules)
        self.assertNotIn("tinker", sys.modules)


if __name__ == "__main__":
    unittest.main()
