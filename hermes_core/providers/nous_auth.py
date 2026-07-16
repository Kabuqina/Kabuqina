# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Nous Portal runtime auth: device-code flow, token refresh, agent-key minting,
pool snapshot, and SSL verification helpers.

Extracted from kabuqina_cli.auth to keep the CLI facade thin.  kabuqina_cli.auth
re-exports every public name so existing imports and test monkeypatches keep
hitting the same objects.
"""

from __future__ import annotations

import logging
import os
import ssl
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from providers.auth_errors import AuthError
from providers.auth_store import (
    _auth_store_lock,
    _load_auth_store,
    _load_provider_state,
    _save_auth_store,
    _save_provider_state,
    get_provider_auth_state,
)
from providers.oauth_helpers import (
    _coerce_ttl_seconds,
    _is_expiring,
    _oauth_trace,
    _optional_base_url,
    _parse_iso_timestamp,
    _token_fingerprint,
)

# Constants live in the zero-import leaf providers.auth_constants (NOT
# kabuqina_cli.auth — importing the facade here would be a circular import, since
# the facade re-exports this module's functions).
from providers.auth_constants import (
    ACCESS_TOKEN_REFRESH_SKEW_SECONDS,
    DEFAULT_AGENT_KEY_MIN_TTL_SECONDS,
    DEFAULT_NOUS_CLIENT_ID,
    DEFAULT_NOUS_INFERENCE_URL,
    DEFAULT_NOUS_PORTAL_URL,
    DEFAULT_NOUS_SCOPE,
    DEVICE_AUTH_POLL_INTERVAL_CAP_SECONDS,
)

logger = logging.getLogger(__name__)


# =============================================================================
# TLS verification helper
# =============================================================================

def _default_verify() -> bool | ssl.SSLContext:
    """Platform-aware default SSL verify for httpx clients.

    On macOS with Homebrew Python, the system OpenSSL cannot locate the
    system trust store and valid public certs fail verification. When
    certifi is importable we pin its bundle explicitly; elsewhere we
    defer to httpx's built-in default (certifi via its own dependency).
    Mirrors the weixin fix in 3a0ec1d93.
    """
    if sys.platform == "darwin":
        try:
            import certifi
            return ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            pass
    return True


def _resolve_verify(
    *,
    insecure: Optional[bool] = None,
    ca_bundle: Optional[str] = None,
    auth_state: Optional[Dict[str, Any]] = None,
) -> bool | ssl.SSLContext:
    tls_state = auth_state.get("tls") if isinstance(auth_state, dict) else {}
    tls_state = tls_state if isinstance(tls_state, dict) else {}

    effective_insecure = (
        bool(insecure) if insecure is not None
        else bool(tls_state.get("insecure", False))
    )
    effective_ca = (
        ca_bundle
        or tls_state.get("ca_bundle")
        or os.getenv("HERMES_CA_BUNDLE")
        or os.getenv("SSL_CERT_FILE")
        or os.getenv("REQUESTS_CA_BUNDLE")
    )

    if effective_insecure:
        return False
    if effective_ca:
        ca_path = str(effective_ca)
        if not os.path.isfile(ca_path):
            logger.warning(
                "CA bundle path does not exist: %s — falling back to default certificates",
                ca_path,
            )
            return _default_verify()
        return ssl.create_default_context(cafile=ca_path)
    return _default_verify()


# =============================================================================
# OAuth Device Code Flow — generic, parameterized by provider
# =============================================================================

def _request_device_code(
    client: httpx.Client,
    portal_base_url: str,
    client_id: str,
    scope: Optional[str],
) -> Dict[str, Any]:
    """POST to the device code endpoint. Returns device_code, user_code, etc."""
    response = client.post(
        f"{portal_base_url}/api/oauth/device/code",
        data={
            "client_id": client_id,
            **({"scope": scope} if scope else {}),
        },
    )
    response.raise_for_status()
    data = response.json()

    required_fields = [
        "device_code", "user_code", "verification_uri",
        "verification_uri_complete", "expires_in", "interval",
    ]
    missing = [f for f in required_fields if f not in data]
    if missing:
        raise ValueError(f"Device code response missing fields: {', '.join(missing)}")
    return data


def _poll_for_token(
    client: httpx.Client,
    portal_base_url: str,
    client_id: str,
    device_code: str,
    expires_in: int,
    poll_interval: int,
) -> Dict[str, Any]:
    """Poll the token endpoint until the user approves or the code expires."""
    deadline = time.time() + max(1, expires_in)
    current_interval = max(1, min(poll_interval, DEVICE_AUTH_POLL_INTERVAL_CAP_SECONDS))

    while time.time() < deadline:
        response = client.post(
            f"{portal_base_url}/api/oauth/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": client_id,
                "device_code": device_code,
            },
        )

        if response.status_code == 200:
            payload = response.json()
            if "access_token" not in payload:
                raise ValueError("Token response did not include access_token")
            return payload

        try:
            error_payload = response.json()
        except Exception:
            response.raise_for_status()
            raise RuntimeError("Token endpoint returned a non-JSON error response")

        error_code = error_payload.get("error", "")
        if error_code == "authorization_pending":
            time.sleep(current_interval)
            continue
        if error_code == "slow_down":
            current_interval = min(current_interval + 1, 30)
            time.sleep(current_interval)
            continue

        description = error_payload.get("error_description") or "Unknown authentication error"
        raise RuntimeError(f"{error_code}: {description}")

    raise TimeoutError("Timed out waiting for device authorization")


# =============================================================================
# Nous Portal — token refresh, agent key minting, model discovery
# =============================================================================

def _refresh_access_token(
    *,
    client: httpx.Client,
    portal_base_url: str,
    client_id: str,
    refresh_token: str,
) -> Dict[str, Any]:
    response = client.post(
        f"{portal_base_url}/api/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": refresh_token,
        },
    )

    if response.status_code == 200:
        payload = response.json()
        if "access_token" not in payload:
            raise AuthError("Refresh response missing access_token",
                            provider="nous", code="invalid_token", relogin_required=True)
        return payload

    try:
        error_payload = response.json()
    except Exception as exc:
        raise AuthError("Refresh token exchange failed",
                        provider="nous", relogin_required=True) from exc

    code = str(error_payload.get("error", "invalid_grant"))
    description = str(error_payload.get("error_description") or "Refresh token exchange failed")
    relogin = code in {"invalid_grant", "invalid_token"}

    # Detect the OAuth 2.1 "refresh token reuse" signal from the Nous portal
    # server and surface an actionable message.  This fires when an external
    # process (health-check script, monitoring tool, custom self-heal hook)
    # called POST /api/oauth/token with Kabuqina's refresh_token without
    # persisting the rotated token back to auth.json — the server then
    # retires the original RT, Kabuqina's next refresh uses it, and the whole
    # session chain gets revoked as a token-theft signal (#15099).
    lowered = description.lower()
    if "reuse" in lowered or "reuse detected" in lowered:
        description = (
            "Nous Portal detected refresh-token reuse and revoked this session.\n"
            "This usually means an external process (monitoring script, "
            "custom self-heal hook, or another Kabuqina install sharing "
            "~/.kabuqina/auth.json) called POST /api/oauth/token with Kabuqina's "
            "refresh token without persisting the rotated token back.\n"
            "Nous refresh tokens are single-use — only Kabuqina may call the "
            "refresh endpoint. For health checks, use `kabuqina auth status` "
            "instead.\n"
            "Re-authenticate with: kabuqina auth add nous"
        )

    raise AuthError(description, provider="nous", code=code, relogin_required=relogin)


def _mint_agent_key(
    *,
    client: httpx.Client,
    portal_base_url: str,
    access_token: str,
    min_ttl_seconds: int,
) -> Dict[str, Any]:
    """Mint (or reuse) a short-lived inference API key."""
    response = client.post(
        f"{portal_base_url}/api/oauth/agent-key",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"min_ttl_seconds": max(60, int(min_ttl_seconds))},
    )

    if response.status_code == 200:
        payload = response.json()
        if "api_key" not in payload:
            raise AuthError("Mint response missing api_key",
                            provider="nous", code="server_error")
        return payload

    try:
        error_payload = response.json()
    except Exception as exc:
        raise AuthError("Agent key mint request failed",
                        provider="nous", code="server_error") from exc

    code = str(error_payload.get("error", "server_error"))
    description = str(error_payload.get("error_description") or "Agent key mint request failed")
    relogin = code in {"invalid_token", "invalid_grant"}
    raise AuthError(description, provider="nous", code=code, relogin_required=relogin)


def fetch_nous_models(
    *,
    inference_base_url: str,
    api_key: str,
    timeout_seconds: float = 15.0,
    verify: bool | str = True,
) -> List[str]:
    """Fetch available model IDs from the Nous inference API."""
    timeout = httpx.Timeout(timeout_seconds)
    with httpx.Client(timeout=timeout, headers={"Accept": "application/json"}, verify=verify) as client:
        response = client.get(
            f"{inference_base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )

    if response.status_code != 200:
        description = f"/models request failed with status {response.status_code}"
        try:
            err = response.json()
            description = str(err.get("error_description") or err.get("error") or description)
        except Exception as e:
            logger.debug("Could not parse error response: %s", e)
        raise AuthError(description, provider="nous", code="models_fetch_failed")

    payload = response.json()
    data = payload.get("data")
    if not isinstance(data, list):
        return []

    model_ids: List[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        if isinstance(model_id, str) and model_id.strip():
            mid = model_id.strip()
            # Skip Kabuqina models — they're not reliable for agentic tool-calling
            if "hermes" in mid.lower():
                continue
            model_ids.append(mid)

    # Sort: prefer opus > pro > haiku/flash > sonnet (sonnet is cheap/fast,
    # users who want the best model should see opus first).
    def _model_priority(mid: str) -> tuple:
        low = mid.lower()
        if "opus" in low:
            return (0, mid)
        if "pro" in low and "sonnet" not in low:
            return (1, mid)
        if "sonnet" in low:
            return (3, mid)
        return (2, mid)

    model_ids.sort(key=_model_priority)
    return list(dict.fromkeys(model_ids))


def _agent_key_is_usable(state: Dict[str, Any], min_ttl_seconds: int) -> bool:
    key = state.get("agent_key")
    if not isinstance(key, str) or not key.strip():
        return False
    return not _is_expiring(state.get("agent_key_expires_at"), min_ttl_seconds)


def resolve_nous_access_token(
    *,
    timeout_seconds: float = 15.0,
    insecure: Optional[bool] = None,
    ca_bundle: Optional[str] = None,
    refresh_skew_seconds: int = ACCESS_TOKEN_REFRESH_SKEW_SECONDS,
) -> str:
    """Resolve a refresh-aware Nous Portal access token for managed tool gateways."""
    with _auth_store_lock():
        auth_store = _load_auth_store()
        state = _load_provider_state(auth_store, "nous")

        if not state:
            raise AuthError(
                "Kabuqina is not logged into Nous Portal.",
                provider="nous",
                relogin_required=True,
            )

        portal_base_url = (
            _optional_base_url(state.get("portal_base_url"))
            or os.getenv("HERMES_PORTAL_BASE_URL")
            or os.getenv("NOUS_PORTAL_BASE_URL")
            or DEFAULT_NOUS_PORTAL_URL
        ).rstrip("/")
        client_id = str(state.get("client_id") or DEFAULT_NOUS_CLIENT_ID)
        verify = _resolve_verify(insecure=insecure, ca_bundle=ca_bundle, auth_state=state)

        access_token = state.get("access_token")
        refresh_token = state.get("refresh_token")
        if not isinstance(access_token, str) or not access_token:
            raise AuthError(
                "No access token found for Nous Portal login.",
                provider="nous",
                relogin_required=True,
            )

        if not _is_expiring(state.get("expires_at"), refresh_skew_seconds):
            return access_token

        if not isinstance(refresh_token, str) or not refresh_token:
            raise AuthError(
                "Session expired and no refresh token is available.",
                provider="nous",
                relogin_required=True,
            )

        timeout = httpx.Timeout(timeout_seconds if timeout_seconds else 15.0)
        with httpx.Client(
            timeout=timeout,
            headers={"Accept": "application/json"},
            verify=verify,
        ) as client:
            refreshed = _refresh_access_token(
                client=client,
                portal_base_url=portal_base_url,
                client_id=client_id,
                refresh_token=refresh_token,
            )

        now = datetime.now(timezone.utc)
        access_ttl = _coerce_ttl_seconds(refreshed.get("expires_in"))
        state["access_token"] = refreshed["access_token"]
        state["refresh_token"] = refreshed.get("refresh_token") or refresh_token
        state["token_type"] = refreshed.get("token_type") or state.get("token_type") or "Bearer"
        state["scope"] = refreshed.get("scope") or state.get("scope")
        state["obtained_at"] = now.isoformat()
        state["expires_in"] = access_ttl
        state["expires_at"] = datetime.fromtimestamp(
            now.timestamp() + access_ttl,
            tz=timezone.utc,
        ).isoformat()
        state["portal_base_url"] = portal_base_url
        state["client_id"] = client_id
        state["tls"] = {
            "insecure": verify is False,
            "ca_bundle": verify if isinstance(verify, str) else None,
        }
        _save_provider_state(auth_store, "nous", state)
        _save_auth_store(auth_store)
        return state["access_token"]


def refresh_nous_oauth_pure(
    access_token: str,
    refresh_token: str,
    client_id: str,
    portal_base_url: str,
    inference_base_url: str,
    *,
    token_type: str = "Bearer",
    scope: str = DEFAULT_NOUS_SCOPE,
    obtained_at: Optional[str] = None,
    expires_at: Optional[str] = None,
    agent_key: Optional[str] = None,
    agent_key_expires_at: Optional[str] = None,
    min_key_ttl_seconds: int = DEFAULT_AGENT_KEY_MIN_TTL_SECONDS,
    timeout_seconds: float = 15.0,
    insecure: Optional[bool] = None,
    ca_bundle: Optional[str] = None,
    force_refresh: bool = False,
    force_mint: bool = False,
) -> Dict[str, Any]:
    """Refresh Nous OAuth state without mutating auth.json."""
    state: Dict[str, Any] = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "client_id": client_id or DEFAULT_NOUS_CLIENT_ID,
        "portal_base_url": (portal_base_url or DEFAULT_NOUS_PORTAL_URL).rstrip("/"),
        "inference_base_url": (inference_base_url or DEFAULT_NOUS_INFERENCE_URL).rstrip("/"),
        "token_type": token_type or "Bearer",
        "scope": scope or DEFAULT_NOUS_SCOPE,
        "obtained_at": obtained_at,
        "expires_at": expires_at,
        "agent_key": agent_key,
        "agent_key_expires_at": agent_key_expires_at,
        "tls": {
            "insecure": bool(insecure),
            "ca_bundle": ca_bundle,
        },
    }
    verify = _resolve_verify(insecure=insecure, ca_bundle=ca_bundle, auth_state=state)
    timeout = httpx.Timeout(timeout_seconds if timeout_seconds else 15.0)

    with httpx.Client(timeout=timeout, headers={"Accept": "application/json"}, verify=verify) as client:
        if force_refresh or _is_expiring(state.get("expires_at"), ACCESS_TOKEN_REFRESH_SKEW_SECONDS):
            refreshed = _refresh_access_token(
                client=client,
                portal_base_url=state["portal_base_url"],
                client_id=state["client_id"],
                refresh_token=state["refresh_token"],
            )
            now = datetime.now(timezone.utc)
            access_ttl = _coerce_ttl_seconds(refreshed.get("expires_in"))
            state["access_token"] = refreshed["access_token"]
            state["refresh_token"] = refreshed.get("refresh_token") or state["refresh_token"]
            state["token_type"] = refreshed.get("token_type") or state.get("token_type") or "Bearer"
            state["scope"] = refreshed.get("scope") or state.get("scope")
            refreshed_url = _optional_base_url(refreshed.get("inference_base_url"))
            if refreshed_url:
                state["inference_base_url"] = refreshed_url
            state["obtained_at"] = now.isoformat()
            state["expires_in"] = access_ttl
            state["expires_at"] = datetime.fromtimestamp(
                now.timestamp() + access_ttl, tz=timezone.utc
            ).isoformat()

        if force_mint or not _agent_key_is_usable(state, max(60, int(min_key_ttl_seconds))):
            mint_payload = _mint_agent_key(
                client=client,
                portal_base_url=state["portal_base_url"],
                access_token=state["access_token"],
                min_ttl_seconds=min_key_ttl_seconds,
            )
            now = datetime.now(timezone.utc)
            state["agent_key"] = mint_payload.get("api_key")
            state["agent_key_id"] = mint_payload.get("key_id")
            state["agent_key_expires_at"] = mint_payload.get("expires_at")
            state["agent_key_expires_in"] = mint_payload.get("expires_in")
            state["agent_key_reused"] = bool(mint_payload.get("reused", False))
            state["agent_key_obtained_at"] = now.isoformat()
            minted_url = _optional_base_url(mint_payload.get("inference_base_url"))
            if minted_url:
                state["inference_base_url"] = minted_url

    return state


def refresh_nous_oauth_from_state(
    state: Dict[str, Any],
    *,
    min_key_ttl_seconds: int = DEFAULT_AGENT_KEY_MIN_TTL_SECONDS,
    timeout_seconds: float = 15.0,
    force_refresh: bool = False,
    force_mint: bool = False,
) -> Dict[str, Any]:
    """Refresh Nous OAuth from a state dict. Thin wrapper around refresh_nous_oauth_pure."""
    tls = state.get("tls") or {}
    return refresh_nous_oauth_pure(
        state.get("access_token", ""),
        state.get("refresh_token", ""),
        state.get("client_id", "kabuqina-cli"),
        state.get("portal_base_url", DEFAULT_NOUS_PORTAL_URL),
        state.get("inference_base_url", DEFAULT_NOUS_INFERENCE_URL),
        token_type=state.get("token_type", "Bearer"),
        scope=state.get("scope", DEFAULT_NOUS_SCOPE),
        obtained_at=state.get("obtained_at"),
        expires_at=state.get("expires_at"),
        agent_key=state.get("agent_key"),
        agent_key_expires_at=state.get("agent_key_expires_at"),
        min_key_ttl_seconds=min_key_ttl_seconds,
        timeout_seconds=timeout_seconds,
        insecure=tls.get("insecure"),
        ca_bundle=tls.get("ca_bundle"),
        force_refresh=force_refresh,
        force_mint=force_mint,
    )


NOUS_DEVICE_CODE_SOURCE = "device_code"


def persist_nous_credentials(
    creds: Dict[str, Any],
    *,
    label: Optional[str] = None,
):
    """Persist minted Nous OAuth credentials as the singleton provider state
    and ensure the credential pool is in sync.

    Nous credentials are read at runtime from two independent locations:

    - ``providers.nous``: singleton state read by
      ``resolve_nous_runtime_credentials()`` during 401 recovery and by
      ``_seed_from_singletons()`` during pool load.
    - ``credential_pool.nous``: used by the runtime ``pool.select()`` path.

    Historically ``kabuqina auth add nous`` wrote a ``manual:device_code`` pool
    entry only, skipping ``providers.nous``.  When the 24h agent_key TTL
    expired, the recovery path read the empty singleton state and raised
    ``AuthError`` silently (``logger.debug`` at INFO level).

    This helper writes ``providers.nous`` then calls ``load_pool("nous")`` so
    ``_seed_from_singletons`` materialises the canonical ``device_code`` pool
    entry from the singleton.  Re-running login upserts the same entry in
    place; the pool never accumulates duplicate device_code rows.

    ``label`` is an optional user-chosen display name (from
    ``kabuqina auth add nous --label <name>``).  It gets embedded in the
    singleton state so that ``_seed_from_singletons`` uses it as the pool
    entry's label on every subsequent ``load_pool("nous")`` instead of the
    auto-derived token fingerprint.  When ``None``, the auto-derived label
    via ``label_from_token`` is used (unchanged default behaviour).

    Returns the upserted :class:`PooledCredential` entry (or ``None`` if
    seeding somehow produced no match — shouldn't happen).
    """
    from providers.credential_pool import load_pool

    state = dict(creds)
    if label and str(label).strip():
        state["label"] = str(label).strip()

    with _auth_store_lock():
        auth_store = _load_auth_store()
        _save_provider_state(auth_store, "nous", state)
        _save_auth_store(auth_store)

    pool = load_pool("nous")
    return next(
        (e for e in pool.entries() if e.source == NOUS_DEVICE_CODE_SOURCE),
        None,
    )


def resolve_nous_runtime_credentials(
    *,
    min_key_ttl_seconds: int = DEFAULT_AGENT_KEY_MIN_TTL_SECONDS,
    timeout_seconds: float = 15.0,
    insecure: Optional[bool] = None,
    ca_bundle: Optional[str] = None,
    force_mint: bool = False,
) -> Dict[str, Any]:
    """
    Resolve Nous inference credentials for runtime use.

    Ensures access_token is valid (refreshes if needed) and a short-lived
    inference key is present with minimum TTL (mints/reuses as needed).
    Concurrent processes coordinate through the auth store file lock.

    Returns dict with: provider, base_url, api_key, key_id, expires_at,
    expires_in, source ("cache" or "portal").
    """
    min_key_ttl_seconds = max(60, int(min_key_ttl_seconds))
    sequence_id = uuid.uuid4().hex[:12]

    with _auth_store_lock():
        auth_store = _load_auth_store()
        state = _load_provider_state(auth_store, "nous")

        if not state:
            raise AuthError("Kabuqina is not logged into Nous Portal.",
                            provider="nous", relogin_required=True)

        portal_base_url = (
            _optional_base_url(state.get("portal_base_url"))
            or os.getenv("HERMES_PORTAL_BASE_URL")
            or os.getenv("NOUS_PORTAL_BASE_URL")
            or DEFAULT_NOUS_PORTAL_URL
        ).rstrip("/")
        inference_base_url = (
            _optional_base_url(state.get("inference_base_url"))
            or os.getenv("NOUS_INFERENCE_BASE_URL")
            or DEFAULT_NOUS_INFERENCE_URL
        ).rstrip("/")
        client_id = str(state.get("client_id") or DEFAULT_NOUS_CLIENT_ID)

        def _persist_state(reason: str) -> None:
            try:
                _save_provider_state(auth_store, "nous", state)
                _save_auth_store(auth_store)
            except Exception as exc:
                _oauth_trace(
                    "nous_state_persist_failed",
                    sequence_id=sequence_id,
                    reason=reason,
                    error_type=type(exc).__name__,
                )
                raise
            _oauth_trace(
                "nous_state_persisted",
                sequence_id=sequence_id,
                reason=reason,
                refresh_token_fp=_token_fingerprint(state.get("refresh_token")),
                access_token_fp=_token_fingerprint(state.get("access_token")),
            )

        verify = _resolve_verify(insecure=insecure, ca_bundle=ca_bundle, auth_state=state)
        timeout = httpx.Timeout(timeout_seconds if timeout_seconds else 15.0)
        _oauth_trace(
            "nous_runtime_credentials_start",
            sequence_id=sequence_id,
            force_mint=bool(force_mint),
            min_key_ttl_seconds=min_key_ttl_seconds,
            refresh_token_fp=_token_fingerprint(state.get("refresh_token")),
        )

        with httpx.Client(timeout=timeout, headers={"Accept": "application/json"}, verify=verify) as client:
            access_token = state.get("access_token")
            refresh_token = state.get("refresh_token")

            if not isinstance(access_token, str) or not access_token:
                raise AuthError("No access token found for Nous Portal login.",
                                provider="nous", relogin_required=True)

            # Step 1: refresh access token if expiring
            if _is_expiring(state.get("expires_at"), ACCESS_TOKEN_REFRESH_SKEW_SECONDS):
                if not isinstance(refresh_token, str) or not refresh_token:
                    raise AuthError("Session expired and no refresh token is available.",
                                    provider="nous", relogin_required=True)

                _oauth_trace(
                    "refresh_start",
                    sequence_id=sequence_id,
                    reason="access_expiring",
                    refresh_token_fp=_token_fingerprint(refresh_token),
                )
                refreshed = _refresh_access_token(
                    client=client, portal_base_url=portal_base_url,
                    client_id=client_id, refresh_token=refresh_token,
                )
                now = datetime.now(timezone.utc)
                access_ttl = _coerce_ttl_seconds(refreshed.get("expires_in"))
                previous_refresh_token = refresh_token
                state["access_token"] = refreshed["access_token"]
                state["refresh_token"] = refreshed.get("refresh_token") or refresh_token
                state["token_type"] = refreshed.get("token_type") or state.get("token_type") or "Bearer"
                state["scope"] = refreshed.get("scope") or state.get("scope")
                refreshed_url = _optional_base_url(refreshed.get("inference_base_url"))
                if refreshed_url:
                    inference_base_url = refreshed_url
                state["obtained_at"] = now.isoformat()
                state["expires_in"] = access_ttl
                state["expires_at"] = datetime.fromtimestamp(
                    now.timestamp() + access_ttl, tz=timezone.utc
                ).isoformat()
                access_token = state["access_token"]
                refresh_token = state["refresh_token"]
                _oauth_trace(
                    "refresh_success",
                    sequence_id=sequence_id,
                    reason="access_expiring",
                    previous_refresh_token_fp=_token_fingerprint(previous_refresh_token),
                    new_refresh_token_fp=_token_fingerprint(refresh_token),
                )
                # Persist immediately so downstream mint failures cannot drop rotated refresh tokens.
                _persist_state("post_refresh_access_expiring")

            # Step 2: mint agent key if missing/expiring
            used_cached_key = False
            mint_payload: Optional[Dict[str, Any]] = None

            if not force_mint and _agent_key_is_usable(state, min_key_ttl_seconds):
                used_cached_key = True
                _oauth_trace("agent_key_reuse", sequence_id=sequence_id)
            else:
                try:
                    _oauth_trace(
                        "mint_start",
                        sequence_id=sequence_id,
                        access_token_fp=_token_fingerprint(access_token),
                    )
                    mint_payload = _mint_agent_key(
                        client=client, portal_base_url=portal_base_url,
                        access_token=access_token, min_ttl_seconds=min_key_ttl_seconds,
                    )
                except AuthError as exc:
                    _oauth_trace(
                        "mint_error",
                        sequence_id=sequence_id,
                        code=exc.code,
                    )
                    # Retry path: access token may be stale server-side despite local checks
                    latest_refresh_token = state.get("refresh_token")
                    if (
                        exc.code in {"invalid_token", "invalid_grant"}
                        and isinstance(latest_refresh_token, str)
                        and latest_refresh_token
                    ):
                        _oauth_trace(
                            "refresh_start",
                            sequence_id=sequence_id,
                            reason="mint_retry_after_invalid_token",
                            refresh_token_fp=_token_fingerprint(latest_refresh_token),
                        )
                        refreshed = _refresh_access_token(
                            client=client, portal_base_url=portal_base_url,
                            client_id=client_id, refresh_token=latest_refresh_token,
                        )
                        now = datetime.now(timezone.utc)
                        access_ttl = _coerce_ttl_seconds(refreshed.get("expires_in"))
                        state["access_token"] = refreshed["access_token"]
                        state["refresh_token"] = refreshed.get("refresh_token") or latest_refresh_token
                        state["token_type"] = refreshed.get("token_type") or state.get("token_type") or "Bearer"
                        state["scope"] = refreshed.get("scope") or state.get("scope")
                        refreshed_url = _optional_base_url(refreshed.get("inference_base_url"))
                        if refreshed_url:
                            inference_base_url = refreshed_url
                        state["obtained_at"] = now.isoformat()
                        state["expires_in"] = access_ttl
                        state["expires_at"] = datetime.fromtimestamp(
                            now.timestamp() + access_ttl, tz=timezone.utc
                        ).isoformat()
                        access_token = state["access_token"]
                        refresh_token = state["refresh_token"]
                        _oauth_trace(
                            "refresh_success",
                            sequence_id=sequence_id,
                            reason="mint_retry_after_invalid_token",
                            previous_refresh_token_fp=_token_fingerprint(latest_refresh_token),
                            new_refresh_token_fp=_token_fingerprint(refresh_token),
                        )
                        # Persist retry refresh immediately for crash safety and cross-process visibility.
                        _persist_state("post_refresh_mint_retry")

                        mint_payload = _mint_agent_key(
                            client=client, portal_base_url=portal_base_url,
                            access_token=access_token, min_ttl_seconds=min_key_ttl_seconds,
                        )
                    else:
                        raise

            if mint_payload is not None:
                now = datetime.now(timezone.utc)
                state["agent_key"] = mint_payload.get("api_key")
                state["agent_key_id"] = mint_payload.get("key_id")
                state["agent_key_expires_at"] = mint_payload.get("expires_at")
                state["agent_key_expires_in"] = mint_payload.get("expires_in")
                state["agent_key_reused"] = bool(mint_payload.get("reused", False))
                state["agent_key_obtained_at"] = now.isoformat()
                minted_url = _optional_base_url(mint_payload.get("inference_base_url"))
                if minted_url:
                    inference_base_url = minted_url
                _oauth_trace(
                    "mint_success",
                    sequence_id=sequence_id,
                    reused=bool(mint_payload.get("reused", False)),
                )

            # Persist routing and TLS metadata for non-interactive refresh/mint
            state["portal_base_url"] = portal_base_url
            state["inference_base_url"] = inference_base_url
            state["client_id"] = client_id
            state["tls"] = {
                "insecure": verify is False,
                "ca_bundle": verify if isinstance(verify, str) else None,
            }

        _persist_state("resolve_nous_runtime_credentials_final")

    api_key = state.get("agent_key")
    if not isinstance(api_key, str) or not api_key:
        raise AuthError("Failed to resolve a Nous inference API key",
                        provider="nous", code="server_error")

    expires_at = state.get("agent_key_expires_at")
    expires_epoch = _parse_iso_timestamp(expires_at)
    expires_in = (
        max(0, int(expires_epoch - time.time()))
        if expires_epoch is not None
        else _coerce_ttl_seconds(state.get("agent_key_expires_in"))
    )

    return {
        "provider": "nous",
        "base_url": inference_base_url,
        "api_key": api_key,
        "key_id": state.get("agent_key_id"),
        "expires_at": expires_at,
        "expires_in": expires_in,
        "source": "cache" if used_cached_key else "portal",
    }


# =============================================================================
# Status helpers
# =============================================================================


def _empty_nous_auth_status() -> Dict[str, Any]:
    return {
        "logged_in": False,
        "portal_base_url": None,
        "inference_base_url": None,
        "access_expires_at": None,
        "agent_key_expires_at": None,
        "has_refresh_token": False,
    }


def _snapshot_nous_pool_status() -> Dict[str, Any]:
    """Best-effort status from the credential pool.

    This is a fallback only. The auth-store provider state is the runtime source
    of truth because it is what ``resolve_nous_runtime_credentials()`` refreshes
    and mints against.
    """
    try:
        from providers.credential_pool import load_pool

        pool = load_pool("nous")
        if not pool or not pool.has_credentials():
            return _empty_nous_auth_status()

        entries = list(pool.entries())
        if not entries:
            return _empty_nous_auth_status()

        def _entry_sort_key(entry: Any) -> tuple[float, float, int]:
            agent_exp = _parse_iso_timestamp(getattr(entry, "agent_key_expires_at", None)) or 0.0
            access_exp = _parse_iso_timestamp(getattr(entry, "expires_at", None)) or 0.0
            priority = int(getattr(entry, "priority", 0) or 0)
            return (agent_exp, access_exp, -priority)

        entry = max(entries, key=_entry_sort_key)
        access_token = (
            getattr(entry, "access_token", None)
            or getattr(entry, "runtime_api_key", "")
        )
        if not access_token:
            return _empty_nous_auth_status()

        return {
            "logged_in": True,
            "portal_base_url": getattr(entry, "portal_base_url", None)
            or getattr(entry, "base_url", None),
            "inference_base_url": getattr(entry, "inference_base_url", None)
            or getattr(entry, "base_url", None),
            "access_token": access_token,
            "access_expires_at": getattr(entry, "expires_at", None),
            "agent_key_expires_at": getattr(entry, "agent_key_expires_at", None),
            "has_refresh_token": bool(getattr(entry, "refresh_token", None)),
            "source": f"pool:{getattr(entry, 'label', 'unknown')}",
        }
    except Exception:
        return _empty_nous_auth_status()


def get_nous_auth_status() -> Dict[str, Any]:
    """Status snapshot for Nous auth.

    Prefer the auth-store provider state, because that is the live source of
    truth for refresh + mint operations. When provider state exists, validate it
    by resolving runtime credentials so revoked refresh sessions do not show up
    as a healthy login. If provider state is absent, fall back to the credential
    pool for the just-logged-in / not-yet-promoted case.
    """
    state = get_provider_auth_state("nous")
    if state:
        base_status = {
            "logged_in": bool(state.get("access_token")),
            "portal_base_url": state.get("portal_base_url"),
            "inference_base_url": state.get("inference_base_url"),
            "access_expires_at": state.get("expires_at"),
            "agent_key_expires_at": state.get("agent_key_expires_at"),
            "has_refresh_token": bool(state.get("refresh_token")),
            "access_token": state.get("access_token"),
            "source": "auth_store",
        }
        try:
            creds = resolve_nous_runtime_credentials(min_key_ttl_seconds=60)
            refreshed_state = get_provider_auth_state("nous") or state
            base_status.update(
                {
                    "logged_in": True,
                    "portal_base_url": refreshed_state.get("portal_base_url") or base_status.get("portal_base_url"),
                    "inference_base_url": creds.get("base_url")
                    or refreshed_state.get("inference_base_url")
                    or base_status.get("inference_base_url"),
                    "access_expires_at": refreshed_state.get("expires_at") or base_status.get("access_expires_at"),
                    "agent_key_expires_at": creds.get("expires_at")
                    or refreshed_state.get("agent_key_expires_at")
                    or base_status.get("agent_key_expires_at"),
                    "has_refresh_token": bool(refreshed_state.get("refresh_token")),
                    "source": f"runtime:{creds.get('source', 'portal')}",
                    "key_id": creds.get("key_id"),
                }
            )
            return base_status
        except AuthError as exc:
            base_status.update({
                "logged_in": False,
                "error": str(exc),
                "relogin_required": bool(getattr(exc, "relogin_required", False)),
                "error_code": getattr(exc, "code", None),
            })
            return base_status

    return _snapshot_nous_pool_status()
