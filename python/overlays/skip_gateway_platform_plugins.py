# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Skip bundled gateway platform plugins in the desk-minimal web child.

Upstream Hermes auto-loads ``kind: platform`` bundled plugins (IRC, Teams)
during ``discover_plugins()``. Kabuqina's web child only needs the ``desktop``
virtual platform (registered in ``desktop_entrypoint``); messaging adapters
belong in the optional gateway child process.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger("hermesdesk.skip_gateway_platform_plugins")

_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    if os.environ.get("HERMESDESK_DESK_MINIMAL") != "1":
        return

    from kabuqina_cli.plugins import LoadedPlugin, PluginManager

    _orig_load = PluginManager._load_plugin

    def _load_plugin(self, manifest):  # type: ignore[no-untyped-def]
        if manifest.source == "bundled" and manifest.kind == "platform":
            lookup_key = manifest.key or manifest.name
            loaded = LoadedPlugin(manifest=manifest, enabled=False)
            loaded.error = "skipped in desk-minimal (gateway-only)"
            self._plugins[lookup_key] = loaded
            log.debug(
                "Skipping bundled platform plugin '%s' (desk-minimal)",
                lookup_key,
            )
            return
        return _orig_load(self, manifest)

    PluginManager._load_plugin = _load_plugin  # type: ignore[method-assign]
    _INSTALLED = True
    log.info("desk-minimal: bundled gateway platform plugins will not auto-load")
