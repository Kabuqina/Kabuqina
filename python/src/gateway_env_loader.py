# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Load host ``kabuqina-home/.env`` and wire web-child cron/messaging egress.

``gateway.run`` loads dotenv at import time. The **web child** (cron ticker,
``send_message_tool`` standalone sends) must do the same or **every** remote
bot delivery fails the same way — missing platform credentials in
``os.environ``, unresolved ``*_HOME_CHANNEL``, and (for httpx-based platforms)
network-allowlist blocks on API hosts.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from kabuqina_env import home as kabuqina_home_env
from typing import Iterable
from urllib.parse import urlparse

log = logging.getLogger("kabuqina.gateway.env")

_LOADED = False

_PROFILE_URL_KEYS: dict[str, tuple[str, ...]] = {
    "mainland_cn": ("WEIXIN_BASE_URL", "WEIXIN_CDN_BASE_URL", "DINGTALK_WEBHOOK_URL"),
    "sea": ("TELEGRAM_PROXY", "EMAIL_OAUTH2_TOKEN_URL"),
}

_PROFILE_CREDENTIAL_HOSTS: dict[str, tuple[tuple[tuple[str, ...], tuple[str, ...]], ...]] = {
    "mainland_cn": (
        (("QQ_APP_ID", "QQ_CLIENT_SECRET"), ("api.sgroup.qq.com",)),
        (("DINGTALK_CLIENT_ID", "DINGTALK_CLIENT_SECRET"), (
            "api.dingtalk.com", "oapi.dingtalk.com", "wss-open-connection.dingtalk.com",
        )),
    ),
    "sea": (
        (("TELEGRAM_BOT_TOKEN",), ("api.telegram.org",)),
    ),
}


def _host_from_value(value: str) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"https://{raw}"
    try:
        return (urlparse(raw).hostname or "").strip().lower() or None
    except Exception:
        return None


def collect_messaging_hosts_from_environ() -> set[str]:
    """Collect API hosts for configured messaging platforms from ``os.environ``."""
    from product_profile_policy import ProductProfilePolicy

    hosts: set[str] = set()
    profile = ProductProfilePolicy.resolve_gateway_profile()
    if profile is None:
        return hosts

    for key in _PROFILE_URL_KEYS.get(profile, ()):
        h = _host_from_value(os.getenv(key, ""))
        if h:
            hosts.add(h)

    for cred_keys, api_hosts in _PROFILE_CREDENTIAL_HOSTS.get(profile, ()):
        if all(os.getenv(k) for k in cred_keys):
            hosts.update(api_hosts)

    # Weixin iLink defaults when token present but URL env omitted
    if profile == "mainland_cn" and os.getenv("WEIXIN_TOKEN") and os.getenv("WEIXIN_ACCOUNT_ID"):
        for default in (
            os.getenv("WEIXIN_BASE_URL", ""),
            os.getenv("WEIXIN_CDN_BASE_URL", ""),
            "https://ilink-api.weixin.qq.com",
            "https://novac2c.cdn.weixin.qq.com",
        ):
            h = _host_from_value(default)
            if h:
                hosts.add(h)

    return hosts


def refresh_messaging_network_allowlist(extra_hosts: Iterable[str] | None = None) -> None:
    """Extend the httpx/requests allowlist with messaging API hosts (idempotent)."""
    if os.environ.get("HERMESDESK_NET_OPEN") == "1":
        return
    hosts = set(collect_messaging_hosts_from_environ())
    if extra_hosts:
        log.warning("Ignoring caller-supplied messaging hosts; CTL-C02 requires profile-derived hosts")

    if not hosts:
        return

    try:
        from overlays import network_allowlist as na
    except ImportError:
        log.debug("messaging network allowlist: overlays.network_allowlist unavailable")
        return

    policy = getattr(na, "_policy", None)
    if policy is None:
        log.debug("messaging network allowlist: policy not installed yet")
        return

    before = len(policy.allowed_hosts)
    policy.extend_hosts(hosts)
    added = len(policy.allowed_hosts) - before
    if added:
        log.info(
            "messaging network allowlist: added %d host(s), sample=%s",
            added,
            sorted(hosts)[:8],
        )


def ensure_gateway_env_loaded() -> None:
    """Idempotent: load ``KABUQINA_HOME/.env`` and refresh messaging egress allowlist."""
    global _LOADED
    if _LOADED:
        return
    home = kabuqina_home_env().strip()
    if not home:
        log.warning(
            "gateway env: KABUQINA_HOME unset; cron/messaging remote delivery will fail "
            "for all platforms"
        )
        _LOADED = True
        return
    try:
        from kabuqina_cli.env_loader import load_kabuqina_dotenv

        paths = load_kabuqina_dotenv(kabuqina_home=Path(home))
        if paths:
            log.info("gateway env: loaded %s", ", ".join(str(p) for p in paths))
    except Exception:
        log.exception("gateway env: failed to load kabuqina-home .env")
    refresh_messaging_network_allowlist()
    try:
        from desktop_timezone import apply_desktop_timezone

        apply_desktop_timezone(Path(home))
    except Exception:
        log.exception("gateway env: failed to apply desktop timezone")
    _LOADED = True


def ensure_gateway_env_for_delivery() -> None:
    """Like ``ensure_gateway_env_loaded`` but safe to call before each cron remote send.

    Re-reads dotenv (cheap) so credentials saved after process start are visible.
    Always refreshes the messaging allowlist from current ``os.environ``.
    """
    home = kabuqina_home_env().strip()
    if not home:
        log.warning("gateway env: KABUQINA_HOME unset; skipping delivery prep")
        return
    try:
        from kabuqina_cli.env_loader import load_kabuqina_dotenv

        load_kabuqina_dotenv(kabuqina_home=Path(home))
    except Exception:
        log.exception("gateway env: failed to reload kabuqina-home .env for delivery")
    refresh_messaging_network_allowlist()
