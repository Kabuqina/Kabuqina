# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""HermesDesk capability catalog."""
from __future__ import annotations
import json, logging, os, sys, time
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from hermes_cli.config import load_config
log = logging.getLogger(__name__)

_DESK_SRC = Path(__file__).resolve().parents[1]

from desk_server.plugins import get_desk_plugins  # noqa: E402


def _load_capability_policy():
    try:
        from capability_policy import CapabilityPolicy
    except ImportError:
        if _DESK_SRC.exists() and str(_DESK_SRC) not in sys.path:
            sys.path.insert(0, str(_DESK_SRC))
        from capability_policy import CapabilityPolicy
    return CapabilityPolicy


def _capability_policy():
    return _load_capability_policy()()


def _strip_internal_plugin_fields(plugin: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in plugin.items() if not k.startswith("_")}


def _desk_catalog_skills(policy) -> List[Dict[str, Any]]:
    from tools.skills_tool import _find_all_skills
    from hermes_cli.skills_config import get_disabled_skills

    config = load_config()
    disabled = get_disabled_skills(config)
    out: List[Dict[str, Any]] = []
    for skill in _find_all_skills(skip_disabled=True):
        visibility = policy.skill_visibility(skill)
        if not visibility["visible"]:
            continue
        item = dict(skill)
        item["enabled"] = item["name"] not in disabled
        item["roles"] = visibility["roles"]
        item["source"] = visibility["source"]
        item["trust"] = visibility["trust"]
        item["recommended"] = visibility["recommended"]
        item["risk"] = visibility["risk"]
        item["can_edit"] = visibility["can_edit"]
        item["action_mode"] = visibility["action_mode"]
        out.append(item)
    return sorted(out, key=lambda s: (s.get("category") or "", s.get("name") or ""))


@lru_cache(maxsize=256)
def _resolve_toolset_names_cached(name: str) -> Tuple[str, ...]:
    """Memoize toolset → tool names for desktop catalog (stable per process)."""
    from toolsets import resolve_toolset

    try:
        return tuple(sorted(set(resolve_toolset(name))))
    except Exception:
        return tuple()


def _desk_catalog_toolsets(policy) -> List[Dict[str, Any]]:
    from hermes_cli.tools_config import (
        _get_effective_configurable_toolsets,
        _get_platform_tools,
        _toolset_has_keys,
    )

    config = load_config()
    enabled_toolsets = _get_platform_tools(
        config,
        "cli",
        include_default_mcp_servers=False,
    )
    result: List[Dict[str, Any]] = []
    for name, label, desc in _get_effective_configurable_toolsets():
        tools = list(_resolve_toolset_names_cached(name))
        # source = provenance (core-built-in toolsets); trust = curation/safety.
        visibility = policy.tool_visibility({"name": name, "source": "builtin", "trust": "official"})
        if not policy.can_view(visibility["roles"]):
            continue
        is_enabled = name in enabled_toolsets
        result.append({
            "name": name,
            "label": label,
            "description": desc,
            "enabled": is_enabled,
            "available": is_enabled and not visibility["locked"],
            "configured": _toolset_has_keys(name, config),
            "tools": tools,
            "roles": visibility["roles"],
            "source": visibility["source"],
            "trust": visibility["trust"],
            "risk": visibility["risk"],
            "locked": visibility["locked"],
            "can_edit": visibility["can_edit"],
            "action_mode": visibility["action_mode"],
        })
    return result


def _desk_catalog_plugins(policy) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for plugin in get_desk_plugins():
        clean = _strip_internal_plugin_fields(plugin)
        if not clean.get("source"):
            clean["source"] = "bundled"
        source_l = str(clean.get("source") or "").strip().lower()
        if source_l in {"bundled", "installed", "user", "project"} and not clean.get("trust"):
            clean["trust"] = "official"
        visibility = policy.plugin_visibility(clean)
        if not visibility["visible"]:
            continue
        clean["roles"] = visibility["roles"]
        clean["source"] = visibility["source"]
        clean["trust"] = visibility["trust"]
        clean["recommended"] = visibility["recommended"]
        clean["risk"] = visibility["risk"]
        clean["can_edit"] = visibility["can_edit"]
        clean["action_mode"] = visibility["action_mode"]
        out.append(clean)
    return sorted(out, key=lambda p: (p.get("label") or p.get("name") or ""))


_DESK_CATALOG_TTL_SEC = 20.0
_desk_catalog_cache_payload: Optional[Dict[str, Any]] = None
_desk_catalog_cache_role: Optional[str] = None
_desk_catalog_cache_expires: float = 0.0


def invalidate_desk_catalog_cache() -> None:
    """Drop HermesDesk capability catalog cache (skills/toolsets/plugins lists)."""
    global _desk_catalog_cache_payload, _desk_catalog_cache_role, _desk_catalog_cache_expires
    _desk_catalog_cache_payload = None
    _desk_catalog_cache_role = None
    _desk_catalog_cache_expires = 0.0
    _resolve_toolset_names_cached.cache_clear()


def _build_desk_catalog_payload_unlocked() -> Dict[str, Any]:
    policy = _capability_policy()
    return {
        "role": policy.role,
        "skills": _desk_catalog_skills(policy),
        "toolsets": _desk_catalog_toolsets(policy),
        "plugins": _desk_catalog_plugins(policy),
    }


def get_desk_catalog_payload_cached() -> Dict[str, Any]:
    """Build or return cached /api/hermesdesk/capabilities body (short TTL, keyed by role)."""
    global _desk_catalog_cache_payload, _desk_catalog_cache_role, _desk_catalog_cache_expires
    policy = _capability_policy()
    now = time.monotonic()
    if (
        _desk_catalog_cache_payload is not None
        and _desk_catalog_cache_role == policy.role
        and now < _desk_catalog_cache_expires
    ):
        return _desk_catalog_cache_payload
    payload = _build_desk_catalog_payload_unlocked()
    _desk_catalog_cache_payload = payload
    _desk_catalog_cache_role = policy.role
    _desk_catalog_cache_expires = now + _DESK_CATALOG_TTL_SEC
    return payload


def _desk_skill_detail_sync(skill_name: str) -> Dict[str, Any]:
    from tools.skills_tool import skill_view

    policy = _capability_policy()
    catalog = get_desk_catalog_payload_cached()
    skills = {s["name"]: s for s in catalog["skills"]}
    if skill_name not in skills:
        raise KeyError(skill_name)
    try:
        detail = json.loads(skill_view(skill_name, preprocess=False))
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc
    if not detail.get("success"):
        raise KeyError(skill_name)
    visibility = policy.skill_visibility({**skills[skill_name], **detail})
    if not visibility["visible"]:
        raise KeyError(skill_name)
    detail["roles"] = visibility["roles"]
    detail["source"] = visibility["source"]
    detail["trust"] = visibility["trust"]
    detail["recommended"] = visibility["recommended"]
    detail["risk"] = visibility["risk"]
    detail["can_edit"] = visibility["can_edit"]
    detail["action_mode"] = visibility["action_mode"]
    return detail
