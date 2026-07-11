# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""One-release environment-name compatibility for desktop children."""

from __future__ import annotations

import os


def legacy_name(name: str) -> str:
    return name.replace("KABUQINA_", "HERMESDESK_", 1)


def get(name: str, default: str = "") -> str:
    """Read the Kabuqina name first, then its deprecated HermesDesk alias."""
    return os.environ.get(name) or os.environ.get(legacy_name(name)) or default


def require(name: str) -> str:
    value = get(name)
    if not value:
        raise KeyError(name)
    return value


def normalize() -> None:
    """Expose both spellings, with Kabuqina taking precedence if both exist."""
    for key, value in tuple(os.environ.items()):
        if key.startswith("KABUQINA_"):
            os.environ.setdefault(legacy_name(key), value)
        elif key.startswith("HERMESDESK_"):
            current = key.replace("HERMESDESK_", "KABUQINA_", 1)
            os.environ.setdefault(current, value)
