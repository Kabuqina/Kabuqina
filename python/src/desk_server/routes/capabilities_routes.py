# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Kabuqina capability HTTP routes."""
from __future__ import annotations
import asyncio
from fastapi import APIRouter, HTTPException
from desk_server.capabilities import (
    _desk_skill_detail_sync as desk_skill_detail_sync,
    get_desk_catalog_payload_cached,
)
router = APIRouter()

@router.get("/api/kabuqina/capabilities")
@router.get("/api/hermesdesk/capabilities", deprecated=True)
async def get_kabuqina_capabilities():
    return await asyncio.to_thread(get_desk_catalog_payload_cached)


@router.get("/api/kabuqina/skills/{skill_name:path}")
@router.get("/api/hermesdesk/skills/{skill_name:path}", deprecated=True)
async def get_kabuqina_skill_detail(skill_name: str):
    try:
        return await asyncio.to_thread(desk_skill_detail_sync, skill_name)
    except KeyError:
        raise HTTPException(status_code=404, detail="Skill not found") from None
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=f"Could not load skill: {exc}") from exc
