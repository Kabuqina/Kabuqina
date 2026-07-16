# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Slim /api/status for Kabuqina shell boot readiness."""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter

from desk_server.warm import desk_is_warming
from kabuqina_cli import __release_date__, __version__
from kabuqina_cli.config import check_config_version, get_config_path, get_env_path, get_kabuqina_home
from gateway.status import get_running_pid

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/status")
async def get_status():
    current_ver, latest_ver = check_config_version()
    gateway_pid = get_running_pid()
    gateway_running = gateway_pid is not None

    active_sessions = 0
    try:
        from kabuqina_state import SessionDB

        db = SessionDB()
        try:
            sessions = db.list_sessions_rich(limit=50)
            now = time.time()
            active_sessions = sum(
                1
                for s in sessions
                if s.get("ended_at") is None
                and (now - s.get("last_active", s.get("started_at", 0))) < 300
            )
        finally:
            db.close()
    except Exception:
        pass

    return {
        "version": __version__,
        "release_date": __release_date__,
        "hermes_home": str(get_kabuqina_home()),
        "config_path": str(get_config_path()),
        "env_path": str(get_env_path()),
        "config_version": current_ver,
        "latest_config_version": latest_ver,
        "gateway_running": gateway_running,
        "gateway_pid": gateway_pid,
        "gateway_health_url": None,
        "gateway_state": None,
        "gateway_platforms": {},
        "gateway_exit_reason": None,
        "gateway_updated_at": None,
        "active_sessions": active_sessions,
        "desk_minimal": True,
        "desk_warming": desk_is_warming(),
    }
