# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Config file/dir path resolvers for kabuqina_cli.

Extracted from ``kabuqina_cli/config.py`` as a clean leaf (only ``get_kabuqina_home``
from ``kabuqina_constants``): the ``config.yaml`` path, the install/project root,
and the atomic dotted-key writer. Sits below the loader core; ``kabuqina_cli.config``
re-exports every name so existing imports keep working.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from kabuqina_constants import get_kabuqina_home

logger = logging.getLogger(__name__)


def get_config_path() -> Path:
    """Get the main config file path."""
    return get_kabuqina_home() / "config.yaml"


def save_config_value(key_path: str, value: Any) -> bool:
    """Save a dotted key-path value into ``config.yaml`` atomically.

    e.g. ``save_config_value("approvals.mcp_reload_confirm", False)``.

    Relocated from the upstream ``cli.py`` so the gateway/desktop runtime no
    longer imports the CLI for this. Targets the user config
    (:func:`get_config_path`); the old project-level ``cli-config.yaml`` fallback
    is intentionally dropped along with the CLI.
    """
    config_path = get_config_path()
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        else:
            config = {}

        keys = key_path.split(".")
        current = config
        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value

        from utils import atomic_yaml_write
        atomic_yaml_write(config_path, config)

        # config.yaml can hold API keys — keep it owner-only.
        try:
            os.chmod(config_path, 0o600)
        except (OSError, NotImplementedError):
            pass
        return True
    except Exception as e:
        logger.error("Failed to save config value %s: %s", key_path, e)
        return False


def get_project_root() -> Path:
    """Get the project installation directory."""
    return Path(__file__).parent.parent.resolve()
