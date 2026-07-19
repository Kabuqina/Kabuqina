"""Kabuqina v0.5 delivery target contract (CTL-C02).

This module is intentionally small and dependency-free so write and execution
boundaries can reject before loading platform config, adapters, or network code.
"""

from __future__ import annotations

import os
from typing import Any, Mapping, Optional

CONTRACT_VERSION = "kabuqina.delivery/v1"

PROFILE_PLATFORMS = {
    "mainland_cn": frozenset({"weixin", "qqbot", "dingtalk"}),
    "sea": frozenset({"telegram", "whatsapp", "email"}),
}

LOCAL_TARGETS = frozenset({"local", "desktop"})


def active_profile() -> Optional[str]:
    raw = os.getenv("KABUQINA_PRODUCT_PROFILE", "").strip().lower()
    if not raw:
        # Standalone upstream-style CLI/core use has no desktop product
        # profile. The Tauri desktop always injects this variable.
        return None
    return raw if raw in PROFILE_PLATFORMS else None


def allowed_platforms(profile: Optional[str] = None) -> frozenset[str]:
    selected = active_profile() if profile is None else str(profile).strip().lower()
    return PROFILE_PLATFORMS.get(selected, frozenset())


def _origin_platform(origin: Optional[Mapping[str, Any]]) -> str:
    return str((origin or {}).get("platform") or "").strip().lower()


def unsupported_delivery_reason(
    deliver: Any,
    *,
    origin: Optional[Mapping[str, Any]] = None,
    profile: Optional[str] = None,
) -> Optional[str]:
    """Return a stable reason when a target is outside the active profile."""
    raw_profile = os.getenv("KABUQINA_PRODUCT_PROFILE", "").strip().lower()
    if profile is None and not raw_profile:
        return None
    selected = (active_profile() or raw_profile) if profile is None else str(profile).strip().lower()
    allowed = allowed_platforms(selected)
    if selected not in PROFILE_PLATFORMS:
        return f"unsupported_delivery [{CONTRACT_VERSION}]: unknown product profile {selected!r}"

    if deliver is None or deliver == "":
        return None
    if isinstance(deliver, (list, tuple)):
        parts = [str(item).strip() for item in deliver if str(item).strip()]
    else:
        parts = [part.strip() for part in str(deliver).split(",") if part.strip()]

    for part in parts:
        head = part.split(":", 1)[0].strip().lower()
        if head in LOCAL_TARGETS:
            continue
        if head == "origin":
            origin_platform = _origin_platform(origin)
            if not origin_platform or origin_platform in LOCAL_TARGETS or origin_platform in allowed:
                continue
            head = origin_platform
        if head not in allowed:
            return (
                f"unsupported_delivery [{CONTRACT_VERSION}]: target {head!r} is not "
                f"available in product profile {selected!r}; choose one of "
                f"{', '.join(sorted(allowed | LOCAL_TARGETS))}"
            )
    return None


def validate_new_delivery(
    deliver: Any,
    *,
    origin: Optional[Mapping[str, Any]] = None,
    profile: Optional[str] = None,
) -> None:
    reason = unsupported_delivery_reason(deliver, origin=origin, profile=profile)
    if reason:
        raise ValueError(reason)
