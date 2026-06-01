# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""CapabilityPolicy — visibility and action labels for desktop catalogs.

The catalog is user-facing, so hiding entries only in React is not enough.
This policy object is intentionally Hermes-light: it can be imported by tests,
overlays, or the embedded web server without pulling in the agent runtime.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable


ROLE_DEFAULT = "default"
ROLE_ADVANCED = "advanced"
ROLE_POWER = "power"
VALID_ROLES = (ROLE_DEFAULT, ROLE_ADVANCED, ROLE_POWER)
ROLE_RANK = {role: idx for idx, role in enumerate(VALID_ROLES)}

SAFE_TOOLSETS = {"web", "file", "vision", "image_gen", "tts", "skills", "todo", "browser"}
POWER_TOOLSETS = {"terminal", "code_execution", "moa"}
COMMUNITY_SOURCES = {"community", "external", "github", "url", "hub", "third_party", "third-party"}
COMMUNITY_TRUST = {"community", "untrusted", "unknown"}
OFFICIAL_SOURCES = {"official", "builtin", "bundled", "installed", "core", "upstream"}


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, dict)):
        return [str(item) for item in value if str(item).strip()]
    return []


def _clean_roles(value: Any) -> list[str]:
    roles = []
    for raw in _as_list(value):
        role = raw.strip().lower()
        if role in VALID_ROLES and role not in roles:
            roles.append(role)
    return roles


def _nested(mapping: dict[str, Any], *keys: str) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


class CapabilityPolicy:
    """Map current desktop mode to catalog visibility and action hints."""

    def __init__(self, role: str | None = None) -> None:
        self.role = role if role in VALID_ROLES else self.effective_role()

    @staticmethod
    def effective_role(
        power_user: bool | None = None,
        show_recipe_market: bool | None = None,
    ) -> str:
        if power_user is None:
            power_user = os.environ.get("HERMESDESK_POWER_USER") == "1"
        if power_user:
            return ROLE_POWER

        if show_recipe_market is None:
            show_recipe_market = CapabilityPolicy._read_show_recipe_market()
        return ROLE_ADVANCED if show_recipe_market else ROLE_DEFAULT

    @staticmethod
    def _read_show_recipe_market() -> bool:
        env_value = os.environ.get("HERMESDESK_SHOW_RECIPE_MARKET")
        if env_value is not None:
            return _as_bool(env_value)

        data_dir = os.environ.get("HERMESDESK_DATA_DIR")
        if not data_dir:
            return False
        try:
            raw = (Path(data_dir) / "hermesdesk_show_recipe_market.txt").read_text(
                encoding="utf-8"
            )
        except OSError:
            return False
        return _as_bool(raw)

    @staticmethod
    def roles_from_min(min_role: str | None) -> list[str]:
        role = (min_role or ROLE_DEFAULT).strip().lower()
        if role not in VALID_ROLES:
            role = ROLE_DEFAULT
        min_rank = ROLE_RANK[role]
        return [candidate for candidate in VALID_ROLES if ROLE_RANK[candidate] >= min_rank]

    def can_view(self, roles: Iterable[str]) -> bool:
        allowed = {role for role in roles if role in VALID_ROLES}
        return not allowed or self.role in allowed

    def skill_visibility(self, skill: dict[str, Any]) -> dict[str, Any]:
        hermesdesk = self._skill_hermesdesk_meta(skill)
        visibility = hermesdesk.get("visibility")
        if not isinstance(visibility, dict):
            visibility = {}

        roles = _clean_roles(visibility.get("roles") or hermesdesk.get("roles"))
        min_role = visibility.get("min_role") or hermesdesk.get("min_role")
        if not roles:
            roles = self.roles_from_min(str(min_role)) if min_role else self._default_skill_roles(skill, hermesdesk)

        source = str(hermesdesk.get("source") or skill.get("source") or "installed")
        trust = str(hermesdesk.get("trust") or skill.get("trust") or "official")
        recommended = _as_bool(hermesdesk.get("recommended") or skill.get("recommended"))
        can_edit = self.role == ROLE_POWER

        return {
            "roles": roles,
            "visible": self.can_view(roles),
            "source": source,
            "trust": trust,
            "recommended": recommended,
            "risk": self._risk_for(source, trust, roles),
            "can_edit": can_edit,
            "action_mode": "agent_assisted" if can_edit else "view_only",
        }

    def tool_visibility(self, toolset: dict[str, Any]) -> dict[str, Any]:
        name = str(toolset.get("name") or "")
        source = str(toolset.get("source") or "official")
        trust = str(toolset.get("trust") or "official")
        if name in POWER_TOOLSETS:
            roles = [ROLE_POWER]
            risk = "high"
        elif name in SAFE_TOOLSETS:
            roles = list(VALID_ROLES)
            risk = "low"
        else:
            roles = self.roles_from_min(ROLE_ADVANCED)
            risk = "medium"
        return {
            "roles": roles,
            "visible": True,
            "source": source,
            "trust": trust,
            "risk": risk,
            "locked": self.role not in roles,
            "can_edit": False,
            "action_mode": "agent_assisted",
        }

    def plugin_visibility(self, plugin: dict[str, Any]) -> dict[str, Any]:
        hermesdesk = plugin.get("hermesdesk")
        if not isinstance(hermesdesk, dict):
            hermesdesk = _nested(plugin, "metadata", "hermesdesk") or {}
        visibility = hermesdesk.get("visibility")
        if not isinstance(visibility, dict):
            visibility = {}

        roles = _clean_roles(visibility.get("roles") or hermesdesk.get("roles"))
        if not roles:
            roles = self.roles_from_min(str(visibility.get("min_role") or hermesdesk.get("min_role") or ROLE_ADVANCED))
        source = str(hermesdesk.get("source") or plugin.get("source") or "installed")
        trust_value = hermesdesk.get("trust") or plugin.get("trust")
        if trust_value:
            trust = str(trust_value)
        else:
            trust = "official" if source.strip().lower() in OFFICIAL_SOURCES else "unknown"
        return {
            "roles": roles,
            "visible": self.can_view(roles),
            "source": source,
            "trust": trust,
            "recommended": _as_bool(hermesdesk.get("recommended") or plugin.get("recommended")),
            "risk": self._risk_for(source, trust, roles),
            "can_edit": False,
            "action_mode": "agent_assisted",
        }

    @staticmethod
    def _skill_hermesdesk_meta(skill: dict[str, Any]) -> dict[str, Any]:
        metadata = skill.get("metadata")
        if not isinstance(metadata, dict):
            return {}
        hermesdesk = metadata.get("hermesdesk")
        return hermesdesk if isinstance(hermesdesk, dict) else {}

    @staticmethod
    def _default_skill_roles(skill: dict[str, Any], hermesdesk: dict[str, Any]) -> list[str]:
        source = str(hermesdesk.get("source") or skill.get("source") or "").strip().lower()
        trust = str(hermesdesk.get("trust") or skill.get("trust") or "").strip().lower()
        if source in COMMUNITY_SOURCES or trust in COMMUNITY_TRUST:
            return [ROLE_POWER]
        return list(VALID_ROLES)

    @staticmethod
    def _risk_for(source: str, trust: str, roles: list[str]) -> str:
        source_l = source.strip().lower()
        trust_l = trust.strip().lower()
        if source_l in COMMUNITY_SOURCES or trust_l in COMMUNITY_TRUST:
            return "high"
        if roles == [ROLE_POWER]:
            return "high"
        if ROLE_DEFAULT in roles:
            return "low"
        return "medium"
