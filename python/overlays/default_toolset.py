# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Seed Hermes' tool config to the HermesDesk keep-list.

# DEPRECATED: tool_policy.remove_when=Phase4
# Target replacement: ``python/src/tool_policy.py``

Hermes selects the active toolsets by reading
``~/.kabuqina/config.yaml`` (under KABUQINA_HOME) at the
``platform_toolsets["cli"]`` key. The CLI's `hermes tools` configurator
maintains it interactively. There is no programmatic "default" function
to monkey-patch; the source of truth is the file.

For HermesDesk we *write* a deterministic config on first launch (and on
every launch when the Power-user toggle changes), so the user never has
to use `hermes tools` from a terminal they don't have.

Beyond the desktop (``cli``) key, this overlay **locks every gateway platform
key** (``weixin``, ``feishu``, ``qqbot``, etc.) to the non-power-user
keep-list.  Gateway bots never receive expanded tools regardless of the
power-user toggle.  See ``ToolPolicy.gateway_keep_list()``.

The toolset-resolution logic is delegated to
``python/src/tool_policy.py`` (Phase 3D).  This overlay only
writes the config file.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

log = logging.getLogger("hermesdesk.toolset")

try:
    from tool_policy import ToolPolicy  # type: ignore[import-untyped]
except ImportError:
    _src = str(Path(__file__).resolve().parent.parent / "src")
    if _src not in sys.path:
        sys.path.insert(0, _src)
    from tool_policy import ToolPolicy  # type: ignore[import-untyped]


def _resolved_set() -> list[str]:
    return ToolPolicy.resolve(ToolPolicy.is_power_user())


def install() -> None:
    enabled = _resolved_set()
    wrote = False

    try:
        from kabuqina_cli.config import load_config, save_config  # type: ignore
    except Exception as e:
        log.warning("kabuqina_cli.config not importable; skipping toolset seed (%s)", e)
        return

    try:
        cfg = load_config() or {}
    except Exception as e:
        log.warning("could not load existing config; starting fresh (%s)", e)
        cfg = {}

    pts = cfg.setdefault("platform_toolsets", {})
    current = pts.get("cli")

    # Only overwrite if missing or differs from desired set. This way the
    # user can still flip individual toolsets via the Settings UI later
    # without us stomping on it on every launch (the Settings UI must
    # also call this overlay's `install()` after writing).
    if current != enabled:
        pts["cli"] = enabled
        wrote = True
        log.info("seeded platform_toolsets[cli] -> %s", enabled)
    else:
        log.debug("toolset config already matches desired set")

    # Force all gateway platform toolset keys to non-power-user keep-list.
    # Gateway bots (weixin, feishu, qqbot, etc.) never get expanded tools.
    try:
        from kabuqina_cli.platforms import PLATFORMS as _PLATFORMS
        gw_list = ToolPolicy.gateway_keep_list()
        for key in _PLATFORMS.keys():
            if key == "cli":
                continue
            if pts.get(key) != gw_list:
                pts[key] = gw_list
                wrote = True
                log.info("locked platform_toolsets[%s] -> %s", key, gw_list)
    except Exception as e:
        log.warning("could not seed gateway platform toolsets: %s", e)

    if wrote:
        try:
            save_config(cfg)
            log.info("toolset config saved")
        except Exception as e:
            log.warning("could not save toolset config: %s", e)
