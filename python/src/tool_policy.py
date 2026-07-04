# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""ToolPolicy — resolve active toolset list from runtime mode.

Extracted from ``overlays/default_toolset.py``.
Target replacement: policy-driven toolset resolution.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger("hermesdesk.toolset")

KEEP_LIST = [
    "web", "file", "vision", "image_gen", "tts", "skills", "clock", "todo", "browser",
    "clarify",
    "documents",
    "math",
    "learning",
    "cronjob",    # scheduled tasks (create-once-approve, then auto-run)
    "messaging",  # cross-channel message delivery (cron delivery + proactive send)
]
POWER_USER_EXTRA = ["terminal", "code_execution", "moa"]
GATEWAY_KEEP_LIST = [
    "web", "file", "vision", "image_gen", "tts", "skills", "clock", "todo", "browser",
    "clarify",
    "documents",
    "math",
    "learning",
    "cronjob",
    "messaging",
]


class ToolPolicy:
    """Map a runtime mode to the list of active toolsets."""

    @staticmethod
    def _profile_hidden() -> frozenset[str]:
        """Toolsets the active product profile removes from default surfaces.

        For mainland_cn this drops e.g. image_gen (no China backend). The sea
        profile keeps them. Falls back to empty so a missing policy module never
        breaks toolset resolution.
        """
        try:
            from product_profile_policy import ProductProfilePolicy

            return ProductProfilePolicy.hidden_toolsets()
        except Exception:
            return frozenset()

    @staticmethod
    def resolve(power_user: bool) -> list[str]:
        hidden = ToolPolicy._profile_hidden()
        keep = [t for t in KEEP_LIST if t not in hidden]
        if power_user:
            return keep + POWER_USER_EXTRA
        return keep

    @staticmethod
    def is_power_user() -> bool:
        return os.environ.get("HERMESDESK_POWER_USER") == "1"

    @staticmethod
    def gateway_keep_list() -> list[str]:
        hidden = ToolPolicy._profile_hidden()
        return [t for t in GATEWAY_KEEP_LIST if t not in hidden]
