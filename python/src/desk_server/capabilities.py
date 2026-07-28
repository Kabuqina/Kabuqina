# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Internal runtime capability facts used to keep the agent honest.

The v0.5 product no longer exposes a capability catalog, role browser, or skill
detail API. The registry remains internal because load-package dependencies and
writer pipeline instructions still need one authoritative runtime calculation.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from kabuqina_cli.config import load_config

log = logging.getLogger(__name__)
_DESK_SRC = Path(__file__).resolve().parents[1]


def _load_runtime_modules():
    try:
        from capability_registry import list_capability_defs
        from capability_status import build_all_capability_statuses
    except ImportError:
        if _DESK_SRC.exists() and str(_DESK_SRC) not in sys.path:
            sys.path.insert(0, str(_DESK_SRC))
        from capability_registry import list_capability_defs
        from capability_status import build_all_capability_statuses
    return list_capability_defs, build_all_capability_statuses


def _enabled_toolsets() -> set[str]:
    from kabuqina_cli.tools_config import (
        CONFIGURABLE_TOOLSETS,
        _get_platform_tools,
    )
    from tool_policy import ToolPolicy

    configured = {
        str(name)
        for name in _get_platform_tools(
            load_config(),
            "cli",
            include_default_mcp_servers=False,
        )
    }
    configurable = {key for key, _, _ in CONFIGURABLE_TOOLSETS}
    always_on = {
        str(name)
        for name in ToolPolicy.resolve(ToolPolicy.is_power_user())
        if str(name) not in configurable
    }
    return configured | always_on


def _fallback_packages(
    definitions: list[dict[str, Any]], exc: Exception
) -> list[dict[str, Any]]:
    package_ids = sorted(
        {
            str(package_id)
            for definition in definitions
            for package_id in (
                list(definition.get("required_load_packages") or [])
                + list(definition.get("optional_load_packages") or [])
            )
        }
    )
    return [
        {
            "id": package_id,
            "title": package_id,
            "downloaded": False,
            "sizeMb": 0,
            "job": {"status": "error", "phase": "error", "error": str(exc)},
        }
        for package_id in package_ids
    ]


def get_runtime_capabilities() -> list[dict[str, Any]]:
    """Return fresh internal statuses for prompt and dependency enforcement."""
    from load_packages import list_load_packages

    list_definitions, build_statuses = _load_runtime_modules()
    definitions = list_definitions()
    try:
        packages = list_load_packages()
    except Exception as exc:
        log.warning("load-package status unavailable for agent runtime facts: %s", exc)
        packages = _fallback_packages(definitions, exc)
    return build_statuses(
        definitions,
        packages,
        enabled_toolsets=_enabled_toolsets(),
    )


__all__ = ["get_runtime_capabilities"]
