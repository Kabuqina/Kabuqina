# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Managed-install and container detection for kabuqina_cli.

Extracted from ``kabuqina_cli/config.py`` as a self-contained leaf (depends only
on ``get_kabuqina_home`` from ``kabuqina_constants``): whether this install is
"managed" (and how it should be updated) and the container exec context. Sits
below the rest of config — config_env / load helpers import ``is_managed`` etc.
from here. ``kabuqina_cli.config`` re-exports every name so existing imports work.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

from kabuqina_constants import get_kabuqina_home

_MANAGED_TRUE_VALUES = ("true", "1", "yes")
_MANAGED_SYSTEM_NAMES = {
    "brew": "Homebrew",
    "homebrew": "Homebrew",
    "nix": "NixOS",
    "nixos": "NixOS",
}


def get_managed_system() -> Optional[str]:
    """Return the package manager owning this install, if any."""
    raw = os.getenv("HERMES_MANAGED", "").strip()
    if raw:
        normalized = raw.lower()
        if normalized in _MANAGED_TRUE_VALUES:
            return "NixOS"
        return _MANAGED_SYSTEM_NAMES.get(normalized, raw)

    managed_marker = get_kabuqina_home() / ".managed"
    if managed_marker.exists():
        return "NixOS"
    return None


def is_managed() -> bool:
    """Check if Kabuqina is running in package-manager-managed mode.

    Two signals: the HERMES_MANAGED env var (set by the systemd service),
    or a .managed marker file in HERMES_HOME (set by the NixOS activation
    script, so interactive shells also see it).
    """
    return get_managed_system() is not None


def get_managed_update_command() -> Optional[str]:
    """Return the preferred upgrade command for a managed install."""
    managed_system = get_managed_system()
    if managed_system == "Homebrew":
        return "brew upgrade kabuqina-agent"
    if managed_system == "NixOS":
        return "sudo nixos-rebuild switch"
    return None


def recommended_update_command() -> str:
    """Return the best update command for the current installation."""
    return get_managed_update_command() or "kabuqina update"


def format_managed_message(action: str = "modify this Kabuqina installation") -> str:
    """Build a user-facing error for managed installs."""
    managed_system = get_managed_system() or "a package manager"
    raw = os.getenv("HERMES_MANAGED", "").strip().lower()

    if managed_system == "NixOS":
        env_hint = "true" if raw in _MANAGED_TRUE_VALUES else raw or "true"
        return (
            f"Cannot {action}: this Kabuqina installation is managed by NixOS "
            f"(HERMES_MANAGED={env_hint}).\n"
            "Edit services.kabuqina-agent.settings in your configuration.nix and run:\n"
            "  sudo nixos-rebuild switch"
        )

    if managed_system == "Homebrew":
        env_hint = raw or "homebrew"
        return (
            f"Cannot {action}: this Kabuqina installation is managed by Homebrew "
            f"(HERMES_MANAGED={env_hint}).\n"
            "Use:\n"
            "  brew upgrade kabuqina-agent"
        )

    return (
        f"Cannot {action}: this Kabuqina installation is managed by {managed_system}.\n"
        "Use your package manager to upgrade or reinstall Kabuqina."
    )


def managed_error(action: str = "modify configuration"):
    """Print user-friendly error for managed mode."""
    print(format_managed_message(action), file=sys.stderr)


def get_container_exec_info() -> Optional[dict]:
    """Read container mode metadata from KABUQINA_HOME/.container-mode.

    Returns a dict with keys: backend, container_name, exec_user, kabuqina_bin
    or None if container mode is not active, we're already inside the
    container, or HERMES_DEV=1 is set.

    The .container-mode file is written by the NixOS activation script when
    container.enable = true. It tells the host CLI to exec into the container
    instead of running locally.
    """
    if os.environ.get("HERMES_DEV") == "1":
        return None

    from kabuqina_constants import is_container
    if is_container():
        return None

    container_mode_file = get_kabuqina_home() / ".container-mode"

    try:
        info = {}
        with open(container_mode_file, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    info[key.strip()] = value.strip()
    except FileNotFoundError:
        return None
    # All other exceptions (PermissionError, malformed data, etc.) propagate

    backend = info.get("backend", "docker")
    container_name = info.get("container_name", "kabuqina-agent")
    exec_user = info.get("exec_user", "hermes")
    kabuqina_bin = (
        info.get("kabuqina_bin")
        or info.get("hermes_bin")  # one-release legacy metadata key
        or "/data/current-package/bin/kabuqina"
    )

    return {
        "backend": backend,
        "container_name": container_name,
        "exec_user": exec_user,
        "kabuqina_bin": kabuqina_bin,
        "hermes_bin": kabuqina_bin,  # one-release caller compatibility
    }
