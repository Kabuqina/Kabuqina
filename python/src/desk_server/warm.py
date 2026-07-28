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
_auto_load_packages_started = threading.Event()
_auto_load_packages_lock = threading.Lock()


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
    # A full AIAgent construction is expensive only once per Python process.
    # Start it after readiness so onboarding can proceed while imports and SDK
    # setup are primed for the first real turn.
    threading.Thread(
        target=_warm_agent_runtime,
        name="desk-agent-warm",
        daemon=True,
    ).start()
    log.info("desk warm complete in %.0fms", (time.monotonic() - t0) * 1000)


def _warm_agent_runtime() -> None:
    try:
        from desk_server.chat_core import warm_desk_agent_runtime

        warm_desk_agent_runtime()
    except Exception:
        log.exception("desk warm: agent runtime warm failed")


def start_auto_load_packages_after_first_chat() -> None:
    """Start boot self-heal only after the first chat turn is complete.

    Optional packages can exceed 1 GB. Running them during onboarding or the first
    request competes with the configured model endpoint for disk, CPU, and network.
    Explicit Settings downloads remain immediate.
    """
    with _auto_load_packages_lock:
        if _auto_load_packages_started.is_set():
            return
        _auto_load_packages_started.set()
    threading.Thread(
        target=_start_auto_load_packages,
        name="desk-auto-load-packages",
        daemon=True,
    ).start()


def _start_auto_load_packages() -> None:
    try:
        import load_packages

        load_packages.start_auto_downloads()
        log.info("desk auto load-package downloads started after first chat")
    except Exception:
        log.exception("desk warm: deferred auto load-package downloads failed to start")


def start_desk_warm_background() -> None:
    if _warm_event.is_set():
        return
    threading.Thread(target=ensure_desk_warmed, name="desk-warm", daemon=True).start()
