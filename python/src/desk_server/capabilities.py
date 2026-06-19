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


def _product_profile_policy():
    try:
        from product_profile_policy import ProductProfilePolicy
    except ImportError:
        if _DESK_SRC.exists() and str(_DESK_SRC) not in sys.path:
            sys.path.insert(0, str(_DESK_SRC))
        from product_profile_policy import ProductProfilePolicy
    return ProductProfilePolicy


def _load_product_capability_modules():
    try:
        from capability_registry import list_capability_defs
        from capability_status import build_all_capability_statuses
    except ImportError:
        if _DESK_SRC.exists() and str(_DESK_SRC) not in sys.path:
            sys.path.insert(0, str(_DESK_SRC))
        from capability_registry import list_capability_defs
        from capability_status import build_all_capability_statuses
    return list_capability_defs, build_all_capability_statuses


def _strip_internal_plugin_fields(plugin: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in plugin.items() if not k.startswith("_")}


def _desk_catalog_skills(policy) -> List[Dict[str, Any]]:
    from tools.skills_tool import _find_all_skills
    from hermes_cli.skills_config import get_disabled_skills

    profile_policy = _product_profile_policy()
    config = load_config()
    disabled = get_disabled_skills(config)
    out: List[Dict[str, Any]] = []
    for skill in _find_all_skills(skip_disabled=True):
        if profile_policy.is_skill_category_hidden(skill.get("category")):
            continue
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


# Toolsets hidden from the desktop capability catalog are now decided by the
# active product profile (ProductProfilePolicy.hidden_toolsets) instead of a
# local frozenset, so region cuts live in one place. Catalog visibility only —
# hermes_core CONFIGURABLE_TOOLSETS (CLI/TUI/tests) stays intact.


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

    hidden_toolsets = _product_profile_policy().hidden_toolsets()
    config = load_config()
    enabled_toolsets = _get_platform_tools(
        config,
        "cli",
        include_default_mcp_servers=False,
    )
    result: List[Dict[str, Any]] = []
    for name, label, desc in _get_effective_configurable_toolsets():
        if name in hidden_toolsets:
            continue
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
    profile_policy = _product_profile_policy()
    out: List[Dict[str, Any]] = []
    for plugin in get_desk_plugins():
        clean = _strip_internal_plugin_fields(plugin)
        if profile_policy.is_plugin_hidden(clean.get("name")):
            continue
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


def _fallback_load_packages_for_capabilities(exc: Exception) -> List[Dict[str, Any]]:
    list_capability_defs, _ = _load_product_capability_modules()
    definitions = list_capability_defs()
    package_ids = sorted({
        package_id
        for definition in definitions
        for package_id in (
            list(definition.get("required_load_packages") or [])
            + list(definition.get("optional_load_packages") or [])
        )
    })
    usage: Dict[str, List[Dict[str, str]]] = {}
    for definition in definitions:
        refs = list(definition.get("required_load_packages") or [])
        refs.extend(list(definition.get("optional_load_packages") or []))
        for package_id in refs:
            usage.setdefault(str(package_id), []).append({
                "id": str(definition["id"]),
                "title": str(definition["title"]),
            })
    return [
        {
            "id": package_id,
            "title": package_id,
            "downloaded": False,
            "sizeMb": 0,
            "usedByCapabilities": sorted(usage.get(package_id, []), key=lambda item: item["title"]),
            "job": {"status": "error", "phase": "error", "error": str(exc)},
        }
        for package_id in package_ids
    ]


def _fresh_load_packages_for_capabilities() -> List[Dict[str, Any]]:
    from load_packages import list_load_packages

    try:
        return list_load_packages()
    except Exception as exc:
        log.warning(
            "load-package status unavailable while building product capabilities: %s",
            exc,
        )
        return _fallback_load_packages_for_capabilities(exc)


def _always_on_toolset_names() -> set[str]:
    """Toolsets active for the desktop agent but absent from the configurable
    checklist (``CONFIGURABLE_TOOLSETS``) — e.g. ``math``.

    The catalog's toolset list (and thus its ``enabled`` flags) only covers
    user-configurable toolsets, so always-on, non-configurable ones never show
    up there. Without adding them back, their product capabilities falsely read
    as ``disabled_toolset`` even though the agent really has those tools. We
    intentionally subtract the configurable keys so a user-disabled toolset is
    never resurrected here — only the non-toggleable always-on set is added.
    """
    try:
        from tool_policy import ToolPolicy
        from hermes_cli.tools_config import CONFIGURABLE_TOOLSETS

        configurable = {key for key, _, _ in CONFIGURABLE_TOOLSETS}
        resolved = {str(name) for name in ToolPolicy.resolve(ToolPolicy.is_power_user())}
        return resolved - configurable
    except Exception as exc:  # pragma: no cover - defensive, keeps catalog usable
        log.debug("could not resolve always-on toolsets: %s", exc)
        return set()


def _desk_product_capabilities(toolsets: List[Dict[str, Any]], packages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build product capabilities from fresh load-package state."""
    list_capability_defs, build_all_capability_statuses = _load_product_capability_modules()
    enabled_toolsets = {
        str(item.get("name") or "")
        for item in toolsets
        if item.get("enabled")
    }
    enabled_toolsets |= _always_on_toolset_names()
    return build_all_capability_statuses(
        list_capability_defs(),
        packages,
        enabled_toolsets=enabled_toolsets,
    )


def _with_fresh_product_capabilities(payload: Dict[str, Any]) -> Dict[str, Any]:
    next_payload = dict(payload)
    toolsets = list(next_payload.get("toolsets") or [])
    packages = _fresh_load_packages_for_capabilities()
    next_payload["loadPackages"] = packages
    next_payload["capabilities"] = _desk_product_capabilities(toolsets, packages)
    return next_payload


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
    toolsets = _desk_catalog_toolsets(policy)
    return {
        "role": policy.role,
        "skills": _desk_catalog_skills(policy),
        "toolsets": toolsets,
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
        return _with_fresh_product_capabilities(_desk_catalog_cache_payload)
    payload = _build_desk_catalog_payload_unlocked()
    _desk_catalog_cache_payload = payload
    _desk_catalog_cache_role = policy.role
    _desk_catalog_cache_expires = now + _DESK_CATALOG_TTL_SEC
    return _with_fresh_product_capabilities(payload)


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
