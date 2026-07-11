# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Load host ``hermes-home/.env`` and wire web-child cron/messaging egress.

``gateway.run`` loads dotenv at import time. The **web child** (cron ticker,
``send_message_tool`` standalone sends) must do the same or **every** remote
bot delivery fails the same way — missing ``WEIXIN_*`` / ``FEISHU_*`` in
``os.environ``, unresolved ``*_HOME_CHANNEL``, and (for httpx-based platforms)
network-allowlist blocks on API hosts.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

log = logging.getLogger("kabuqina.gateway.env")

_LOADED = False

# Env suffixes that hold outbound API base URLs (any platform).
_URL_ENV_SUFFIXES = (
    "_BASE_URL",
    "_SERVER_URL",
    "_API_URL",
    "_WEBHOOK_URL",
    "_WEBSOCKET_URL",
)

# When credentials are present, allow known API hosts (httpx-based send paths).
_CREDENTIAL_API_HOSTS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("FEISHU_APP_ID", "FEISHU_APP_SECRET"), ("open.feishu.cn", "open.larkoffice.com")),
    (("WECOM_BOT_ID", "WECOM_SECRET"), ("qyapi.weixin.qq.com",)),
    (("WECOM_CALLBACK_CORP_ID", "WECOM_CALLBACK_CORP_SECRET"), ("qyapi.weixin.qq.com",)),
    (("WEIXIN_TOKEN",), ()),  # hosts come from WEIXIN_BASE_URL / CDN env
    (("WEIXIN_ACCOUNT_ID",), ()),
    (("QQBOT_APP_ID", "QQBOT_CLIENT_SECRET"), ("api.sgroup.qq.com",)),
)


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
    hosts: set[str] = set()

    for key, value in os.environ.items():
        if not value:
            continue
        ku = key.upper()
        if any(ku.endswith(suffix) for suffix in _URL_ENV_SUFFIXES):
            h = _host_from_value(value)
            if h:
                hosts.add(h)
        # MATRIX_HOMESERVER may be a bare URL without suffix match above
        if ku == "MATRIX_HOMESERVER":
            h = _host_from_value(value)
            if h:
                hosts.add(h)

    for cred_keys, api_hosts in _CREDENTIAL_API_HOSTS:
        if all(os.getenv(k) for k in cred_keys):
            hosts.update(api_hosts)

    # Weixin iLink defaults when token present but URL env omitted
    if os.getenv("WEIXIN_TOKEN") or os.getenv("WEIXIN_ACCOUNT_ID"):
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
        hosts.update(h.lower() for h in extra_hosts if h)

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
    """Idempotent: load ``HERMES_HOME/.env`` and refresh messaging egress allowlist."""
    global _LOADED
    if _LOADED:
        return
    home = (os.environ.get("HERMES_HOME") or "").strip()
    if not home:
        log.warning(
            "gateway env: HERMES_HOME unset; cron/messaging remote delivery will fail "
            "for all platforms"
        )
        _LOADED = True
        return
    try:
        from hermes_cli.env_loader import load_hermes_dotenv

        paths = load_hermes_dotenv(hermes_home=Path(home))
        if paths:
            log.info("gateway env: loaded %s", ", ".join(str(p) for p in paths))
    except Exception:
        log.exception("gateway env: failed to load hermes-home .env")
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
    home = (os.environ.get("HERMES_HOME") or "").strip()
    if not home:
        log.warning("gateway env: HERMES_HOME unset; skipping delivery prep")
        return
    try:
        from hermes_cli.env_loader import load_hermes_dotenv

        load_hermes_dotenv(hermes_home=Path(home))
    except Exception:
        log.exception("gateway env: failed to reload hermes-home .env for delivery")
    refresh_messaging_network_allowlist()
