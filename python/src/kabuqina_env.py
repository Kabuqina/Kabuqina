# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""One-release environment-name compatibility for desktop children."""

from __future__ import annotations

import os


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
