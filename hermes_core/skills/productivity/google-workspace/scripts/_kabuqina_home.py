"""Resolve KABUQINA_HOME for standalone skill scripts.

Skill scripts may run outside the Hermes process (e.g. system Python,
nix env, CI) where ``kabuqina_constants`` is not importable.  This module
provides the same ``get_kabuqina_home()`` and ``display_kabuqina_home()``
contracts as ``kabuqina_constants`` without requiring it on ``sys.path``.

When ``kabuqina_constants`` IS available it is used directly so that any
future enhancements (profile resolution, Docker detection, etc.) are
picked up automatically.  The fallback path replicates the core logic
from ``kabuqina_constants.py`` using only the stdlib.

All scripts under ``google-workspace/scripts/`` should import from here
instead of duplicating the ``KABUQINA_HOME = Path(os.getenv(...))`` pattern.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from kabuqina_constants import display_kabuqina_home as display_kabuqina_home
    from kabuqina_constants import get_kabuqina_home as get_kabuqina_home
except (ModuleNotFoundError, ImportError):

    def get_kabuqina_home() -> Path:
        """Return the Kabuqina home directory (default: ~/.kabuqina).

        Mirrors ``kabuqina_constants.get_kabuqina_home()``."""
        if "KABUQINA_HOME" in os.environ:
            val = os.environ["KABUQINA_HOME"].strip()
            return Path(val) if val else Path.home() / ".kabuqina"
        legacy_env = os.environ.get("HERMES_HOME", "").strip()
        if legacy_env:
            return Path(legacy_env)
        current = Path.home() / ".kabuqina"
        legacy = Path.home() / ".hermes"
        return legacy if legacy.exists() and not current.exists() else current

    def display_kabuqina_home() -> str:
        """Return a user-friendly ``~/``-shortened display string.

        Mirrors ``kabuqina_constants.display_kabuqina_home()``."""
        home = get_kabuqina_home()
        try:
            return "~/" + home.relative_to(Path.home()).as_posix()
        except ValueError:
            return home.as_posix()
