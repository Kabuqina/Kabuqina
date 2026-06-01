# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""HermesDesk capability HTTP routes."""
from __future__ import annotations
import asyncio
from fastapi import APIRouter, HTTPException
from desk_server.capabilities import (
    _desk_skill_detail_sync as desk_skill_detail_sync,
    get_desk_catalog_payload_cached,
)
router = APIRouter()

@router.get("/api/hermesdesk/capabilities")
async def get_hermesdesk_capabilities():
    return await asyncio.to_thread(get_desk_catalog_payload_cached)


@router.get("/api/hermesdesk/skills/{skill_name:path}")
async def get_hermesdesk_skill_detail(skill_name: str):
    try:
        return await asyncio.to_thread(desk_skill_detail_sync, skill_name)
    except KeyError:
        raise HTTPException(status_code=404, detail="Skill not found") from None
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=f"Could not load skill: {exc}") from exc
