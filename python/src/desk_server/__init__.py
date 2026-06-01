# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Kabuqina desk HTTP server — product API decoupled from Hermes dashboard web_server."""
from __future__ import annotations

import logging
import time

from desk_server.app import create_app
from desk_server.auth import SESSION_TOKEN
from desk_server.warm import start_desk_warm_background

_log = logging.getLogger(__name__)

# Tauri reads this from desktop_entrypoint after import.
_SESSION_TOKEN = SESSION_TOKEN

__all__ = [
    "SESSION_TOKEN",
    "_SESSION_TOKEN",
    "app",
    "create_app",
    "start_desk_warm_background",
    "start_server",
]

app = create_app()


def start_server(
    host: str = "127.0.0.1",
    port: int = 9119,
    open_browser: bool = False,
    allow_public: bool = False,
    **kwargs,
):
    """Start the Kabuqina desk server (uvicorn)."""
    import uvicorn

    _LOCALHOST = ("127.0.0.1", "localhost", "::1")
    if host not in _LOCALHOST and not allow_public:
        raise SystemExit(
            f"Refusing to bind to {host} — the desk server exposes API keys "
            f"and config without robust authentication.\n"
            f"Use allow_public=True only on trusted networks."
        )
    if host not in _LOCALHOST:
        _log.warning(
            "Binding to %s on a non-loopback interface — use only on trusted networks.",
            host,
        )

    app.state.bound_host = host
    app.state.bound_port = port

    if open_browser:
        import threading
        import webbrowser

        def _open():
            time.sleep(1.0)
            webbrowser.open(f"http://{host}:{port}")

        threading.Thread(target=_open, daemon=True).start()

    _log.info("Kabuqina desk server → http://%s:%s", host, port)
    uvicorn.run(app, host=host, port=port, log_level="warning")
