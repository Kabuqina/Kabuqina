# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""FastAPI application factory for Kabuqina desk server."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from desk_server.auth import install_middleware
from desk_server.routes import (
    activity_routes,
    chat,
    export,
    goal_routes,
    knowledge_core_compilation_routes,
    load_packages,
    sessions,
    status,
    studio_routes,
    study_activity_routes,
    study_capture_routes,
    study_routes,
    study_whiteboard_routes,
    voice,
)
from kabuqina_cli import __version__


def create_app() -> FastAPI:
    app = FastAPI(title="Kabuqina Desk", version=__version__)

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    install_middleware(app)

    for mod in (
        activity_routes,
        knowledge_core_compilation_routes,
        status,
        chat,
        sessions,
        voice,
        load_packages,
        export,
        goal_routes,
        studio_routes,
        study_routes,
        study_capture_routes,
        study_activity_routes,
        study_whiteboard_routes,
    ):
        app.include_router(mod.router)

    return app
