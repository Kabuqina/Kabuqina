# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Desk routes for optional large load packages."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from load_packages import delete_package, list_load_packages, package_status, start_download_package

router = APIRouter()
log = logging.getLogger("kabuqina.load_packages")


def _error_response(code: str, exc: Exception, status_code: int = 500) -> JSONResponse:
    if isinstance(exc, ValueError):
        status_code = 404
    return JSONResponse({"error": code, "detail": str(exc)}, status_code=status_code)


@router.get("/api/desk/load-packages")
async def desk_load_packages():
    try:
        return JSONResponse({"packages": list_load_packages()})
    except Exception as exc:
        log.exception("load-packages list failed")
        return _error_response("load_packages_list_failed", exc)


@router.get("/api/desk/load-packages/{package_id}/status")
async def desk_load_package_status(package_id: str):
    try:
        return JSONResponse(package_status(package_id))
    except Exception as exc:
        log.exception("load-package status failed: %s", package_id)
        return _error_response("load_package_status_failed", exc)


@router.post("/api/desk/load-packages/{package_id}/download")
async def desk_load_package_download(package_id: str):
    try:
        return JSONResponse(start_download_package(package_id))
    except Exception as exc:
        log.exception("load-package download failed: %s", package_id)
        return _error_response("load_package_download_failed", exc)


@router.delete("/api/desk/load-packages/{package_id}")
async def desk_load_package_delete(package_id: str):
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, delete_package, package_id)
        return JSONResponse(result)
    except Exception as exc:
        log.exception("load-package delete failed: %s", package_id)
        return _error_response("load_package_delete_failed", exc)
