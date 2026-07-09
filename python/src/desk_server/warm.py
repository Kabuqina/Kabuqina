# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Background tool/plugin warm for desk server startup."""
from __future__ import annotations

import logging
import threading
import time

from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)

_warm_event = threading.Event()


def desk_is_warming() -> bool:
    return not _warm_event.is_set()


def warming_http_response():
    if desk_is_warming():
        return JSONResponse({"ok": False, "status": "warming"}, status_code=503)
    return None


def ensure_desk_warmed() -> None:
    if _warm_event.is_set():
        return
    t0 = time.monotonic()
    try:
        from model_tools import ensure_tools_discovered

        ensure_tools_discovered()
    except Exception:
        log.exception("desk warm: tool discovery failed")
    _warm_event.set()
    try:
        from desk_server.capabilities import invalidate_desk_catalog_cache

        invalidate_desk_catalog_cache()
    except Exception:
        pass
    # Kick off optional load-package downloads once the server is warm. This is a
    # single, idempotent, serial self-heal decoupled from onboarding and the first
    # chat turn — enqueue-and-return, so it never blocks warm or the event loop.
    try:
        import load_packages

        load_packages.start_auto_downloads()
    except Exception:
        log.exception("desk warm: auto load-package downloads failed to start")
    log.info("desk warm complete in %.0fms", (time.monotonic() - t0) * 1000)


def start_desk_warm_background() -> None:
    if _warm_event.is_set():
        return
    threading.Thread(target=ensure_desk_warmed, name="desk-warm", daemon=True).start()
