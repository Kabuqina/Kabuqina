# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""'What is missing from the config / .env / skills' detection for hermes_cli.

Extracted from ``hermes_cli/config.py``: the checklist helpers used by setup /
migration to find env vars, config fields, and skill config vars the user hasn't
filled in yet. Builds on the loader / schema / env siblings.
``hermes_cli.config`` re-exports every name.
"""

from __future__ import annotations

from typing import Any, Dict, List

from hermes_cli.config_defaults import DEFAULT_CONFIG
from hermes_cli.config_env_schema import OPTIONAL_ENV_VARS, REQUIRED_ENV_VARS
from hermes_cli.config_env import get_env_value
from hermes_cli.config_loader import load_config


def get_missing_env_vars(required_only: bool = False) -> List[Dict[str, Any]]:
    """
    Check which environment variables are missing.
    
    Returns list of dicts with var info for missing variables.
    """
    missing = []
    
    # Check required vars
    for var_name, info in REQUIRED_ENV_VARS.items():
        if not get_env_value(var_name):
            missing.append({"name": var_name, **info, "is_required": True})
    
    # Check optional vars (if not required_only)
    if not required_only:
        for var_name, info in OPTIONAL_ENV_VARS.items():
            if not get_env_value(var_name):
                missing.append({"name": var_name, **info, "is_required": False})
    
    return missing


def _set_nested(config, dotted_key: str, value):
    """Set a value at an arbitrarily nested dotted key path.

    Supports both dict and list navigation:
      _set_nested(c, "a.b.c", 1)     → c["a"]["b"]["c"] = 1
      _set_nested(c, "a.0.b", 1)     → c["a"][0]["b"] = 1
      _set_nested(c, "providers.1", "x") → c["providers"][1] = "x"

    Intermediate dicts are created on demand.  List indices are parsed
    from numeric path segments; the referenced index must already exist
    (we do not grow lists — the user is navigating into structure they
    wrote themselves).  If a segment targets a non-container leaf
    (scalar), the leaf is replaced with a fresh dict so the write can
    proceed — this preserves the pre-existing behavior for bare scalar
    overrides (e.g. setting ``a.b.c`` where ``a.b`` was previously a
    string).

    Guards against #17876: before this fix the code unconditionally
    replaced any non-dict value (including lists) with ``{}``, silently
    destroying list-typed config like ``custom_providers`` whenever a
    caller used an indexed path.
    """
    parts = dotted_key.split(".")
    current = config
    for part in parts[:-1]:
        if isinstance(current, list):
            try:
                idx = int(part)
            except (TypeError, ValueError):
                raise TypeError(
                    f"Cannot navigate into list at key {dotted_key!r}: "
                    f"segment {part!r} is not a numeric index"
                )
            current = current[idx]
        elif isinstance(current, dict):
            existing = current.get(part)
            # Preserve dicts and lists; replace missing/scalar with a fresh dict.
            if part not in current or not isinstance(existing, (dict, list)):
                current[part] = {}
            current = current[part]
        else:
            raise TypeError(
                f"Cannot navigate into {type(current).__name__} at key {dotted_key!r}"
            )
    last = parts[-1]
    if isinstance(current, list):
        current[int(last)] = value
    else:
        current[last] = value


def get_missing_config_fields() -> List[Dict[str, Any]]:
    """
    Check which config fields are missing or outdated (recursive).
    
    Walks the DEFAULT_CONFIG tree at arbitrary depth and reports any keys
    present in defaults but absent from the user's loaded config.
    """
    config = load_config()
    missing = []

    def _check(defaults: dict, current: dict, prefix: str = ""):
        for key, default_value in defaults.items():
            if key.startswith('_'):
                continue
            full_key = key if not prefix else f"{prefix}.{key}"
            if key not in current:
                missing.append({
                    "key": full_key,
                    "default": default_value,
                    "description": f"New config option: {full_key}",
                })
            elif isinstance(default_value, dict) and isinstance(current.get(key), dict):
                _check(default_value, current[key], full_key)

    _check(DEFAULT_CONFIG, config)
    return missing


def get_missing_skill_config_vars() -> List[Dict[str, Any]]:
    """Return skill-declared config vars that are missing or empty in config.yaml.

    Scans all enabled skills for ``metadata.hermes.config`` entries, then checks
    which ones are absent or empty under ``skills.config.<key>`` in the user's
    config.yaml.  Returns a list of dicts suitable for prompting.
    """
    try:
        from agent.skill_utils import discover_all_skill_config_vars, SKILL_CONFIG_PREFIX
    except Exception:
        return []

    all_vars = discover_all_skill_config_vars()
    if not all_vars:
        return []

    config = load_config()
    missing: List[Dict[str, Any]] = []
    for var in all_vars:
        # Skill config is stored under skills.config.<logical_key>
        storage_key = f"{SKILL_CONFIG_PREFIX}.{var['key']}"
        parts = storage_key.split(".")
        current = config
        value = None
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
                value = current
            else:
                value = None
                break
        # Missing = key doesn't exist or is empty string
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(var)
    return missing
