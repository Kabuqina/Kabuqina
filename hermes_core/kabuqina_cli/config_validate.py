# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Config structure validation + version check for kabuqina_cli.

Extracted from ``kabuqina_cli/config.py``: the config schema-version check, the
``ConfigIssue`` record, structural validation (misplaced custom-provider fields,
unknown root keys, ...), and the deprecation warnings. Builds on the loader +
defaults siblings. ``kabuqina_cli.config`` re-exports every name.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from kabuqina_cli.config_defaults import DEFAULT_CONFIG
from kabuqina_cli.config_loader import load_config


_KNOWN_ROOT_KEYS = {
    "_config_version", "model", "providers", "fallback_model",
    "fallback_providers", "credential_pool_strategies", "toolsets",
    "agent", "terminal", "display", "compression", "delegation",
    "auxiliary", "custom_providers", "context", "memory", "gateway",
    "sessions",
}


_CUSTOM_PROVIDER_LIKE_FIELDS = {"base_url", "api_key", "rate_limit_delay", "api_mode"}


@dataclass
class ConfigIssue:
    """A detected config structure problem."""

    severity: str  # "error", "warning"
    message: str
    hint: str


def check_config_version() -> Tuple[int, int]:
    """
    Check config version.
    
    Returns (current_version, latest_version).
    """
    config = load_config()
    current = config.get("_config_version", 0)
    latest = DEFAULT_CONFIG.get("_config_version", 1)
    return current, latest


def validate_config_structure(config: Optional[Dict[str, Any]] = None) -> List["ConfigIssue"]:
    """Validate config.yaml structure and return a list of detected issues.

    Catches common YAML formatting mistakes that produce confusing runtime
    errors (like "Unknown provider") instead of clear diagnostics.

    Can be called with a pre-loaded config dict, or will load from disk.
    """
    if config is None:
        try:
            config = load_config()
        except Exception:
            return [ConfigIssue("error", "Could not load config.yaml", "Run 'kabuqina setup' to create a valid config")]

    issues: List[ConfigIssue] = []

    # ── custom_providers must be a list, not a dict ──────────────────────
    cp = config.get("custom_providers")
    if cp is not None:
        if isinstance(cp, dict):
            issues.append(ConfigIssue(
                "error",
                "custom_providers is a dict — it must be a YAML list (items prefixed with '-')",
                "Change to:\n"
                "  custom_providers:\n"
                "    - name: my-provider\n"
                "      base_url: https://...\n"
                "      api_key: ...",
            ))
            # Check if dict keys look like they should be list-entry fields
            cp_keys = set(cp.keys()) if isinstance(cp, dict) else set()
            suspicious = cp_keys & _CUSTOM_PROVIDER_LIKE_FIELDS
            if suspicious:
                issues.append(ConfigIssue(
                    "warning",
                    f"Root-level keys {sorted(suspicious)} look like custom_providers entry fields",
                    "These should be indented under a '- name: ...' list entry, not at root level",
                ))
        elif isinstance(cp, list):
            # Validate each entry in the list
            for i, entry in enumerate(cp):
                if not isinstance(entry, dict):
                    issues.append(ConfigIssue(
                        "warning",
                        f"custom_providers[{i}] is not a dict (got {type(entry).__name__})",
                        "Each entry should have at minimum: name, base_url",
                    ))
                    continue
                if not entry.get("name"):
                    issues.append(ConfigIssue(
                        "warning",
                        f"custom_providers[{i}] is missing 'name' field",
                        "Add a name, e.g.: name: my-provider",
                    ))
                if not entry.get("base_url"):
                    issues.append(ConfigIssue(
                        "warning",
                        f"custom_providers[{i}] is missing 'base_url' field",
                        "Add the API endpoint URL, e.g.: base_url: https://api.example.com/v1",
                    ))

    # ── fallback_model: single dict OR list of dicts (chain) ─────────────
    fb = config.get("fallback_model")
    if fb is not None:
        if isinstance(fb, list):
            # Chain fallback — validate each entry
            for i, entry in enumerate(fb):
                if not isinstance(entry, dict):
                    issues.append(ConfigIssue(
                        "error",
                        f"fallback_model[{i}] should be a dict, got {type(entry).__name__}",
                        "Each entry needs provider + model",
                    ))
                else:
                    if not entry.get("provider"):
                        issues.append(ConfigIssue(
                            "warning",
                            f"fallback_model[{i}] is missing 'provider' field",
                            "Add: provider: openrouter (or another provider)",
                        ))
                    if not entry.get("model"):
                        issues.append(ConfigIssue(
                            "warning",
                            f"fallback_model[{i}] is missing 'model' field",
                            "Add: model: <model-name>",
                        ))
        elif not isinstance(fb, dict):
            issues.append(ConfigIssue(
                "error",
                f"fallback_model should be a dict with 'provider' and 'model', got {type(fb).__name__}",
                "Change to:\n"
                "  fallback_model:\n"
                "    provider: openrouter\n"
                "    model: anthropic/claude-sonnet-4",
            ))
        elif fb:
            if not fb.get("provider"):
                issues.append(ConfigIssue(
                    "warning",
                    "fallback_model is missing 'provider' field — fallback will be disabled",
                    "Add: provider: openrouter (or another provider)",
                ))
            if not fb.get("model"):
                issues.append(ConfigIssue(
                    "warning",
                    "fallback_model is missing 'model' field — fallback will be disabled",
                    "Add: model: anthropic/claude-sonnet-4 (or another model)",
                ))

    # ── Check for fallback_model accidentally nested inside custom_providers ──
    if isinstance(cp, dict) and "fallback_model" not in config and "fallback_model" in (cp or {}):
        issues.append(ConfigIssue(
            "error",
            "fallback_model appears inside custom_providers instead of at root level",
            "Move fallback_model to the top level of config.yaml (no indentation)",
        ))

    # ── model section: should exist when custom_providers is configured ──
    model_cfg = config.get("model")
    if cp and not model_cfg:
        issues.append(ConfigIssue(
            "warning",
            "custom_providers defined but no 'model' section — Kabuqina won't know which provider to use",
            "Add a model section:\n"
            "  model:\n"
            "    provider: custom\n"
            "    default: your-model-name\n"
            "    base_url: https://...",
        ))

    # ── Root-level keys that look misplaced ──────────────────────────────
    for key in config:
        if key.startswith("_"):
            continue
        if key not in _KNOWN_ROOT_KEYS and key in _CUSTOM_PROVIDER_LIKE_FIELDS:
            issues.append(ConfigIssue(
                "warning",
                f"Root-level key '{key}' looks misplaced — should it be under 'model:' or inside a 'custom_providers' entry?",
                f"Move '{key}' under the appropriate section",
            ))

    return issues


def print_config_warnings(config: Optional[Dict[str, Any]] = None) -> None:
    """Print config structure warnings to stderr at startup.

    Called early in CLI and gateway init so users see problems before
    they hit cryptic "Unknown provider" errors.  Prints nothing if
    config is healthy.
    """
    try:
        issues = validate_config_structure(config)
    except Exception:
        return
    if not issues:
        return

    lines = ["\033[33m⚠ Config issues detected in config.yaml:\033[0m"]
    for ci in issues:
        marker = "\033[31m✗\033[0m" if ci.severity == "error" else "\033[33m⚠\033[0m"
        lines.append(f"  {marker} {ci.message}")
    lines.append("  \033[2mRun 'kabuqina doctor' for fix suggestions.\033[0m")
    sys.stderr.write("\n".join(lines) + "\n\n")


def warn_deprecated_cwd_env_vars(config: Optional[Dict[str, Any]] = None) -> None:
    """Warn if MESSAGING_CWD or TERMINAL_CWD is set in .env instead of config.yaml.

    These env vars are deprecated — the canonical setting is terminal.cwd
    in config.yaml.  Prints a migration hint to stderr.
    """
    messaging_cwd = os.environ.get("MESSAGING_CWD")
    terminal_cwd_env = os.environ.get("TERMINAL_CWD")

    if config is None:
        try:
            config = load_config()
        except Exception:
            return

    terminal_cfg = config.get("terminal", {})
    config_cwd = terminal_cfg.get("cwd", ".") if isinstance(terminal_cfg, dict) else "."
    # Only warn if config.yaml doesn't have an explicit path
    config_has_explicit_cwd = config_cwd not in (".", "auto", "cwd", "")

    lines: list[str] = []
    if messaging_cwd:
        lines.append(
            f"  \033[33m⚠\033[0m MESSAGING_CWD={messaging_cwd} found in .env — "
            f"this is deprecated."
        )
    if terminal_cwd_env and not config_has_explicit_cwd:
        # TERMINAL_CWD in env but not from config bridge — likely from .env
        lines.append(
            f"  \033[33m⚠\033[0m TERMINAL_CWD={terminal_cwd_env} found in .env — "
            f"this is deprecated."
        )
    if lines:
        hint_path = (
            os.environ["KABUQINA_HOME"]
            if "KABUQINA_HOME" in os.environ
            else os.environ.get("HERMES_HOME", "~/.kabuqina")
        )
        lines.insert(0, "\033[33m⚠ Deprecated .env settings detected:\033[0m")
        lines.append(
            f"  \033[2mMove to config.yaml instead:  "
            f"terminal:\\n    cwd: /your/project/path\033[0m"
        )
        lines.append(
            f"  \033[2mThen remove the old entries from {hint_path}/.env\033[0m"
        )
        sys.stderr.write("\n".join(lines) + "\n\n")
