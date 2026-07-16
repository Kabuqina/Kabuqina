# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""One-release environment-name compatibility for desktop children."""

from __future__ import annotations

import logging
import os
from pathlib import Path


def legacy_name(name: str) -> str:
    return name.replace("KABUQINA_", "HERMESDESK_", 1)


def lookup(name: str) -> str | None:
    """Return a value while preserving missing-versus-explicit-empty semantics."""
    if name in os.environ:
        return os.environ[name]
    legacy = legacy_name(name)
    return os.environ[legacy] if legacy in os.environ else None


def get(name: str, default: str = "") -> str:
    """Read the Kabuqina name first, then its deprecated HermesDesk alias."""
    value = lookup(name)
    return value if value is not None else default


def require(name: str) -> str:
    value = get(name)
    if not value:
        raise KeyError(name)
    return value


def home(default: str = "") -> str:
    """Read ``KABUQINA_HOME`` first, then the one-release legacy name."""
    if "KABUQINA_HOME" in os.environ:
        return os.environ["KABUQINA_HOME"]
    return os.environ.get("HERMES_HOME", default)


def export_home(path: str | os.PathLike[str]) -> None:
    """Expose the canonical home plus its one-release process alias."""
    value = str(path)
    os.environ["KABUQINA_HOME"] = value
    os.environ["HERMES_HOME"] = value


def normalize() -> None:
    """Expose both spellings, with Kabuqina taking precedence if both exist."""
    for key, value in tuple(os.environ.items()):
        if key.startswith("HERMESDESK_"):
            current = key.replace("HERMESDESK_", "KABUQINA_", 1)
            os.environ.setdefault(current, value)
    for key, value in tuple(os.environ.items()):
        if key.startswith("KABUQINA_"):
            # Consumers still using the deprecated spelling must observe the
            # same value; otherwise one process can split its safety boundary.
            os.environ[legacy_name(key)] = value


def resolve_desktop_home(
    data_dir: str | os.PathLike[str],
    *,
    logger: logging.Logger | None = None,
) -> Path:
    """Resolve and, when safe, migrate the desktop home directory.

    ``kabuqina-home`` is canonical. An old-only ``hermes-home`` directory is
    renamed atomically in place so databases and profiles move together. If
    rename fails, the old directory remains active for this release; no copy,
    merge, or deletion is attempted. If both directories exist, the new one
    wins and the old one is left untouched for manual recovery.
    """
    root = Path(data_dir)
    current = root / "kabuqina-home"
    legacy = root / "hermes-home"
    if current.exists() or not legacy.exists():
        return current
    try:
        legacy.rename(current)
    except OSError as exc:
        if current.exists():
            return current
        if logger is not None:
            logger.warning(
                "Kabuqina home migration failed; using legacy directory for "
                "this launch: %s",
                exc,
            )
        return legacy
    if logger is not None:
        logger.info("Migrated legacy desktop home to %s", current)
    return current
