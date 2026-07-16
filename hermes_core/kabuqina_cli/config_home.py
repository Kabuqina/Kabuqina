# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Kabuqina home-directory setup and file/dir security for ``kabuqina_cli``.

Extracted from ``kabuqina_cli/config.py``: secure dir/file permission helpers,
container detection, default ``soul.md`` seeding, and the managed-aware home
bootstrap. Sits above ``config_managed`` (uses ``is_managed``) and below the
env/load layers (``config_env`` uses ``ensure_kabuqina_home``/``_secure_file``).
``kabuqina_cli.config`` re-exports every name so existing imports keep working.
"""

from __future__ import annotations

import os
from pathlib import Path

from kabuqina_constants import get_kabuqina_home
from kabuqina_cli.config_managed import is_managed
from kabuqina_cli.default_soul import DEFAULT_SOUL_MD


def _secure_dir(path):
    """Set directory to owner-only access (0700 by default). No-op on Windows.

    Skipped in managed mode — the NixOS module sets group-readable
    permissions (0750) so interactive users in the hermes group can
    share state with the gateway service.

    The mode can be overridden via ``KABUQINA_HOME_MODE``. The former
    ``HERMES_HOME_MODE`` spelling remains readable for one release.
    The execute-only bit on a directory permits cd-through without exposing
    directory listings.
    """
    if is_managed():
        return
    try:
        mode_str = (
            os.environ["KABUQINA_HOME_MODE"].strip()
            if "KABUQINA_HOME_MODE" in os.environ
            else os.environ.get("HERMES_HOME_MODE", "").strip()
        )
        mode = int(mode_str, 8) if mode_str else 0o700
    except ValueError:
        mode = 0o700
    try:
        os.chmod(path, mode)
    except (OSError, NotImplementedError):
        pass


def _is_container() -> bool:
    """Detect if we're running inside a Docker/Podman/LXC container.

    When Kabuqina runs in a container with volume-mounted config files, forcing
    0o600 permissions breaks multi-process setups where the gateway and
    dashboard run as different UIDs or the volume mount requires broader
    permissions.
    """
    # Explicit opt-out
    if os.environ.get("HERMES_CONTAINER") or os.environ.get("HERMES_SKIP_CHMOD"):
        return True
    # Docker / Podman marker file
    if os.path.exists("/.dockerenv"):
        return True
    # LXC / cgroup-based detection
    try:
        with open("/proc/1/cgroup", "r") as f:
            cgroup_content = f.read()
        if "docker" in cgroup_content or "lxc" in cgroup_content or "kubepods" in cgroup_content:
            return True
    except (OSError, IOError):
        pass
    return False


def _secure_file(path):
    """Set file to owner-only read/write (0600). No-op on Windows.

    Skipped in managed mode — the NixOS activation script sets
    group-readable permissions (0640) on config files.

    Skipped in containers — Docker/Podman volume mounts often need broader
    permissions.  Set HERMES_SKIP_CHMOD=1 to force-skip on other systems.
    """
    if is_managed() or _is_container():
        return
    try:
        if os.path.exists(str(path)):
            os.chmod(path, 0o600)
    except (OSError, NotImplementedError):
        pass


def _ensure_default_soul_md(home: Path) -> None:
    """Seed a default SOUL.md into KABUQINA_HOME if missing."""
    soul_path = home / "SOUL.md"
    if soul_path.exists():
        return
    soul_path.write_text(DEFAULT_SOUL_MD, encoding="utf-8")
    _secure_file(soul_path)


def ensure_kabuqina_home():
    """Ensure the active Kabuqina home structure exists securely.

    In managed mode (NixOS), dirs are created by the activation script with
    setgid + group-writable (2770). We skip mkdir and set umask(0o007) so
    any files created (e.g. SOUL.md) are group-writable (0660).
    """
    home = get_kabuqina_home()
    if is_managed():
        old_umask = os.umask(0o007)
        try:
            _ensure_kabuqina_home_managed(home)
        finally:
            os.umask(old_umask)
    else:
        home.mkdir(parents=True, exist_ok=True)
        _secure_dir(home)
        for subdir in ("cron", "sessions", "logs", "logs/curator", "memories"):
            d = home / subdir
            d.mkdir(parents=True, exist_ok=True)
            _secure_dir(d)
        _ensure_default_soul_md(home)


def _ensure_kabuqina_home_managed(home: Path):
    """Managed-mode variant: verify dirs exist (activation creates them), seed SOUL.md."""
    if not home.is_dir():
        raise RuntimeError(
            f"KABUQINA_HOME {home} does not exist. "
            "Run 'sudo nixos-rebuild switch' first."
        )
    for subdir in ("cron", "sessions", "logs", "memories"):
        d = home / subdir
        if not d.is_dir():
            raise RuntimeError(
                f"{d} does not exist. "
                "Run 'sudo nixos-rebuild switch' first."
            )
    # Curator reports dir is a sub-path of logs/; create it if missing.
    # In managed mode the activation script may not know about this subdir,
    # so we mkdir it ourselves (it's inside an already-secured logs/ dir).
    (home / "logs" / "curator").mkdir(parents=True, exist_ok=True)
    # Inside umask(0o007) scope — SOUL.md will be created as 0660
    _ensure_default_soul_md(home)


# One-release source compatibility for plugins using the old public helpers.
ensure_hermes_home = ensure_kabuqina_home
_ensure_hermes_home_managed = _ensure_kabuqina_home_managed
