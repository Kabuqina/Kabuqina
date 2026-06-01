# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Session token and HTTP auth middleware for the Kabuqina desk server."""
from __future__ import annotations

import hmac
import os
import secrets

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

SESSION_TOKEN = secrets.token_urlsafe(32)
SESSION_HEADER_NAME = "X-Hermes-Session-Token"

# Kabuqina shell: only /api/status is public (boot readiness probe).
PUBLIC_API_PATHS: frozenset[str] = frozenset({"/api/status"})

_LOOPBACK_HOST_VALUES: frozenset[str] = frozenset({
    "localhost", "127.0.0.1", "::1",
})


def has_valid_session_token(request: Request) -> bool:
    session_header = request.headers.get(SESSION_HEADER_NAME, "")
    if session_header and hmac.compare_digest(
        session_header.encode(),
        SESSION_TOKEN.encode(),
    ):
        return True
    auth = request.headers.get("authorization", "")
    expected = f"Bearer {SESSION_TOKEN}"
    return hmac.compare_digest(auth.encode(), expected.encode())


def require_token(request: Request) -> None:
    if not has_valid_session_token(request):
        raise HTTPException(status_code=401, detail="Unauthorized")


def is_accepted_host(host_header: str, bound_host: str) -> bool:
    if not host_header:
        return False
    h = host_header.strip()
    if h.startswith("["):
        close = h.find("]")
        host_only = h[1:close] if close != -1 else h.strip("[]")
    else:
        host_only = h.rsplit(":", 1)[0] if ":" in h else h
    host_only = host_only.lower()

    if bound_host in ("0.0.0.0", "::"):
        return True

    bound_lc = bound_host.lower()
    if bound_lc in _LOOPBACK_HOST_VALUES:
        return host_only in _LOOPBACK_HOST_VALUES

    return host_only == bound_lc


def install_middleware(app) -> None:
    @app.middleware("http")
    async def host_header_middleware(request: Request, call_next):
        bound_host = getattr(app.state, "bound_host", None)
        if bound_host:
            host_header = request.headers.get("host", "")
            if not is_accepted_host(host_header, bound_host):
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": (
                            "Invalid Host header. Requests must use "
                            "the hostname the server was bound to."
                        ),
                    },
                )
        return await call_next(request)

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/") and path not in PUBLIC_API_PATHS:
            if has_valid_session_token(request):
                return await call_next(request)
            bridge_secret = (os.environ.get("HERMESDESK_BRIDGE_SECRET") or "").strip()
            if bridge_secret:
                desk_auth = (request.headers.get("x-hermesdesk-auth") or "").strip()
                if desk_auth and hmac.compare_digest(
                    desk_auth.encode("utf-8"), bridge_secret.encode("utf-8")
                ):
                    return await call_next(request)
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        return await call_next(request)
