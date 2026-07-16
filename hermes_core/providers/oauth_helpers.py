# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Shared OAuth / JWT / timestamp leaf helpers for provider auth code.

Self-contained (stdlib only): OAuth trace logging plus token-expiry, TTL, ISO
timestamp, and JWT-claim parsing used across the provider runtime credential
resolvers. No dependency on the CLI command surface, the provider registry, or
the auth store, so any provider module can import these without a cycle.

``kabuqina_cli.auth`` re-exports them so existing call sites keep working.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# --- OAuth trace logging ----------------------------------------------------

def _token_fingerprint(token: Any) -> Optional[str]:
    """Return a short hash fingerprint for telemetry without leaking token bytes."""
    if not isinstance(token, str):
        return None
    cleaned = token.strip()
    if not cleaned:
        return None
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:12]

def _oauth_trace_enabled() -> bool:
    raw = os.getenv("HERMES_OAUTH_TRACE", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}

def _oauth_trace(event: str, *, sequence_id: Optional[str] = None, **fields: Any) -> None:
    if not _oauth_trace_enabled():
        return
    payload: Dict[str, Any] = {"event": event}
    if sequence_id:
        payload["sequence_id"] = sequence_id
    payload.update(fields)
    logger.info("oauth_trace %s", json.dumps(payload, sort_keys=True, ensure_ascii=False))


# --- Timestamp / TTL / JWT helpers --------------------------------------

def _parse_iso_timestamp(value: Any) -> Optional[float]:
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()

def _is_expiring(expires_at_iso: Any, skew_seconds: int) -> bool:
    expires_epoch = _parse_iso_timestamp(expires_at_iso)
    if expires_epoch is None:
        return True
    return expires_epoch <= (time.time() + skew_seconds)

def _coerce_ttl_seconds(expires_in: Any) -> int:
    try:
        ttl = int(expires_in)
    except Exception:
        ttl = 0
    return max(0, ttl)

def _optional_base_url(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    cleaned = value.strip().rstrip("/")
    return cleaned if cleaned else None

def _decode_jwt_claims(token: Any) -> Dict[str, Any]:
    if not isinstance(token, str) or token.count(".") != 2:
        return {}
    payload = token.split(".")[1]
    payload += "=" * ((4 - len(payload) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload.encode("utf-8"))
        claims = json.loads(raw.decode("utf-8"))
    except Exception:
        return {}
    return claims if isinstance(claims, dict) else {}
