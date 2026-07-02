# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""FastAPI application factory for Kabuqina desk server."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from desk_server.auth import install_middleware
from desk_server.routes import capabilities_routes, chat, export, goal_routes, load_packages, sessions, status, voice
from hermes_cli import __version__


def create_app() -> FastAPI:
    app = FastAPI(title="Kabuqina Desk", version=__version__)

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    install_middleware(app)

    for mod in (status, chat, sessions, voice, load_packages, capabilities_routes, export, goal_routes):
        app.include_router(mod.router)

    return app
