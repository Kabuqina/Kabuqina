# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""NetworkPolicy — egress host allowlist.

Extracted from ``overlays/network_allowlist.py``.
Target replacement: injected policy that checks outbound hosts.
"""

from __future__ import annotations

import logging
import os
from typing import Iterable
from urllib.parse import urlparse

log = logging.getLogger("kabuqina.net")

DEFAULT_ALLOW: set[str] = {
    "localhost",
    "127.0.0.1",
    "speech.platform.bing.com",
    "agentskills.io",
    "raw.githubusercontent.com",
    "github.com",
    "api.github.com",
    "huggingface.co",
    "us.aws.cdn.hf.co",
    "hf-mirror.com",
    "kabuqina.com",
    "nanapackages-1428509047.cos.ap-guangzhou.myqcloud.com",
}


class NetworkPolicy:
    """Check whether an outbound URL is on the allowlist."""

    def __init__(self, *, llm_host: str = "", extra_hosts: str = "") -> None:
        self._allow = set(DEFAULT_ALLOW)
        # Seed the active product profile's default provider hosts (e.g. the
        # retained China LLM providers for mainland_cn) so switching providers
        # does not require re-validating the egress allowlist. Additive only.
        try:
            from product_profile_policy import ProductProfilePolicy

            self._allow.update(ProductProfilePolicy.default_network_hosts())
        except Exception:  # pragma: no cover - keep allowlist usable if import fails
            pass
        for v in (llm_host, extra_hosts):
            for h in v.split(","):
                h = h.strip().lower()
                if h:
                    self._allow.add(h)

    def check_url(self, url: str) -> None:
        host = urlparse(url).hostname
        if host is None:
            raise PermissionError(
                f"HermesDesk network allowlist could not parse host from URL: {url}"
            )
        allow = host.lower() in self._allow
        # Allow bare IPs in RFC1918 if they match loopback (handled above).
        if not allow and host.startswith("127."):
            allow = True
        if not allow and host == "::1":
            allow = True
        if not allow:
            raise PermissionError(
                f"HermesDesk network allowlist blocked outbound request to {host}. "
                f"To grant access, add the host in Settings or enable "
                f"HERMESDESK_NET_OPEN=1."
            )

    def extend_hosts(self, hosts: Iterable[str]) -> None:
        """Add messaging / gateway API hosts (cron ``_send_to_platform`` egress)."""
        for raw in hosts:
            h = (raw or "").strip().lower()
            if h:
                self._allow.add(h)

    @property
    def allowed_hosts(self) -> set[str]:
        return set(self._allow)
