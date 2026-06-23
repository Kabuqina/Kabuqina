# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""MiniMax OAuth runtime auth: PKCE, user-code flow, token polling, refresh,
and status helpers.

Extracted from hermes_cli.auth to keep the CLI facade thin.  hermes_cli.auth
re-exports every public name so existing imports and test monkeypatches keep
hitting the same objects.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from providers.auth_errors import AuthError
from providers.auth_store import (
    _auth_store_lock,
    _load_auth_store,
    _save_auth_store,
    _save_provider_state,
    get_provider_auth_state,
)

# Constants live in the zero-import leaf providers.auth_constants (NOT
# hermes_cli.auth — importing the facade here would be a circular import, since
# the facade re-exports this module's functions).
from providers.auth_constants import (
    MINIMAX_OAUTH_GRANT_TYPE,
    MINIMAX_OAUTH_REFRESH_SKEW_SECONDS,
    MINIMAX_OAUTH_SCOPE,
)

logger = logging.getLogger(__name__)


# =============================================================================
# MiniMax Portal OAuth — runtime helpers
# =============================================================================

def _minimax_pkce_pair() -> tuple:
    """Generate (code_verifier, code_challenge_S256, state) for MiniMax OAuth."""
    import secrets
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    state = secrets.token_urlsafe(16)
    return verifier, challenge, state


def _minimax_request_user_code(
    client: httpx.Client, *, portal_base_url: str, client_id: str,
    code_challenge: str, state: str,
) -> Dict[str, Any]:
    response = client.post(
        f"{portal_base_url}/oauth/code",
        data={
            "response_type": "code",
            "client_id": client_id,
            "scope": MINIMAX_OAUTH_SCOPE,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "x-request-id": str(uuid.uuid4()),
        },
    )
    if response.status_code != 200:
        raise AuthError(
            f"MiniMax OAuth authorization failed: {response.text or response.reason_phrase}",
            provider="minimax-oauth", code="authorization_failed",
        )
    payload = response.json()
    for field in ("user_code", "verification_uri", "expired_in"):
        if field not in payload:
            raise AuthError(
                f"MiniMax OAuth response missing field: {field}",
                provider="minimax-oauth", code="authorization_incomplete",
            )
    if payload.get("state") != state:
        raise AuthError(
            "MiniMax OAuth state mismatch (possible CSRF).",
            provider="minimax-oauth", code="state_mismatch",
        )
    return payload


def _minimax_poll_token(
    client: httpx.Client, *, portal_base_url: str, client_id: str,
    user_code: str, code_verifier: str, expired_in: int, interval_ms: Optional[int],
) -> Dict[str, Any]:
    # OpenClaw treats expired_in as a unix-ms timestamp (Date.now() < expireTimeMs).
    # Defensive parsing: if it's small enough to be a duration, treat as seconds.
    import time as _time
    now_ms = int(_time.time() * 1000)
    if expired_in > now_ms // 2:
        # Looks like a unix-ms timestamp.
        deadline = expired_in / 1000.0
    else:
        # Treat as duration in seconds from now.
        deadline = _time.time() + max(1, expired_in)
    interval = max(2.0, (interval_ms or 2000) / 1000.0)

    while _time.time() < deadline:
        response = client.post(
            f"{portal_base_url}/oauth/token",
            data={
                "grant_type": MINIMAX_OAUTH_GRANT_TYPE,
                "client_id": client_id,
                "user_code": user_code,
                "code_verifier": code_verifier,
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
        try:
            payload = response.json() if response.text else {}
        except Exception:
            payload = {}

        if response.status_code != 200:
            msg = (payload.get("base_resp", {}) or {}).get("status_msg") or response.text
            raise AuthError(
                f"MiniMax OAuth error: {msg or 'unknown'}",
                provider="minimax-oauth", code="token_exchange_failed",
            )

        status = payload.get("status")
        if status == "error":
            raise AuthError(
                "MiniMax OAuth reported an error. Please try again later.",
                provider="minimax-oauth", code="authorization_denied",
            )
        if status == "success":
            if not all(payload.get(k) for k in ("access_token", "refresh_token", "expired_in")):
                raise AuthError(
                    "MiniMax OAuth success payload missing required token fields.",
                    provider="minimax-oauth", code="token_incomplete",
                )
            return payload
        # "pending" or any other status -> keep polling
        _time.sleep(interval)

    raise AuthError(
        "MiniMax OAuth timed out before authorization completed.",
        provider="minimax-oauth", code="timeout",
    )


def _minimax_save_auth_state(auth_state: Dict[str, Any]) -> None:
    """Persist MiniMax OAuth state to Hermes auth store (~/.hermes/auth.json)."""
    with _auth_store_lock():
        auth_store = _load_auth_store()
        _save_provider_state(auth_store, "minimax-oauth", auth_state)
        _save_auth_store(auth_store)


def _refresh_minimax_oauth_state(
    state: Dict[str, Any], *, timeout_seconds: float = 15.0,
    force: bool = False,
) -> Dict[str, Any]:
    """Refresh MiniMax OAuth access token if close to expiry (or forced)."""
    if not state.get("refresh_token"):
        raise AuthError(
            "MiniMax OAuth state has no refresh_token; please re-login.",
            provider="minimax-oauth", code="no_refresh_token", relogin_required=True,
        )
    try:
        expires_at = datetime.fromisoformat(state.get("expires_at", "")).timestamp()
    except Exception:
        expires_at = 0.0
    now = time.time()
    if not force and (expires_at - now) > MINIMAX_OAUTH_REFRESH_SKEW_SECONDS:
        return state

    portal_base_url = state["portal_base_url"]
    with httpx.Client(timeout=httpx.Timeout(timeout_seconds)) as client:
        response = client.post(
            f"{portal_base_url}/oauth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": state["client_id"],
                "refresh_token": state["refresh_token"],
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
    if response.status_code != 200:
        body = response.text.lower()
        relogin = any(m in body for m in
                      ("invalid_grant", "refresh_token_reused", "invalid_refresh_token"))
        raise AuthError(
            f"MiniMax OAuth refresh failed: {response.text or response.reason_phrase}",
            provider="minimax-oauth", code="refresh_failed",
            relogin_required=relogin,
        )
    payload = response.json()
    if payload.get("status") != "success":
        raise AuthError(
            "MiniMax OAuth refresh did not return success.",
            provider="minimax-oauth", code="refresh_failed",
            relogin_required=True,
        )
    now_dt = datetime.now(timezone.utc)
    expires_in_s = int(payload["expired_in"])
    new_state = dict(state)
    new_state.update({
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token", state["refresh_token"]),
        "obtained_at": now_dt.isoformat(),
        "expires_at": datetime.fromtimestamp(now_dt.timestamp() + expires_in_s,
                                             tz=timezone.utc).isoformat(),
        "expires_in": expires_in_s,
    })
    _minimax_save_auth_state(new_state)
    return new_state


def resolve_minimax_oauth_runtime_credentials(
    *, min_token_ttl_seconds: int = MINIMAX_OAUTH_REFRESH_SKEW_SECONDS,
) -> Dict[str, Any]:
    """Return {provider, api_key, base_url, source} for minimax-oauth."""
    state = get_provider_auth_state("minimax-oauth")
    if not state or not state.get("access_token"):
        raise AuthError(
            "Not logged into MiniMax OAuth. Run `hermes model` and select "
            "MiniMax (OAuth).",
            provider="minimax-oauth", code="not_logged_in", relogin_required=True,
        )
    state = _refresh_minimax_oauth_state(state)
    return {
        "provider": "minimax-oauth",
        "api_key": state["access_token"],
        "base_url": state["inference_base_url"].rstrip("/"),
        "source": "oauth",
    }


def get_minimax_oauth_auth_status() -> Dict[str, Any]:
    """Return auth status dict for MiniMax OAuth provider."""
    state = get_provider_auth_state("minimax-oauth")
    if not state or not state.get("access_token"):
        return {"logged_in": False, "provider": "minimax-oauth"}
    try:
        expires_at = datetime.fromisoformat(state.get("expires_at", "")).timestamp()
        token_valid = (expires_at - time.time()) > 0
    except Exception:
        token_valid = bool(state.get("access_token"))
    return {
        "logged_in": token_valid,
        "provider": "minimax-oauth",
        "region": state.get("region", "global"),
        "expires_at": state.get("expires_at"),
    }
