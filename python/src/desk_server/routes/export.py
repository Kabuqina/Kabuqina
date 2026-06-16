# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Desk export routes for shell-owned save flows."""
from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/desk/export/pdf")
async def desk_export_pdf(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"ok": False, "error": "invalid_body"}, status_code=400)

    html_source = str(body.get("html") or "")
    if not html_source.strip():
        return JSONResponse(
            {"ok": False, "error": "empty_html", "detail": "html is required"},
            status_code=400,
        )

    try:
        from tools.document_tools import render_pdf_from_html_source

        pdf_bytes, page_count, renderer = render_pdf_from_html_source(html_source)
    except Exception as exc:
        log.exception("desk export pdf: render failed")
        return JSONResponse(
            {
                "ok": False,
                "error": "pdf_render_failed",
                "detail": str(exc) or type(exc).__name__,
            },
            status_code=500,
        )

    return JSONResponse(
        {
            "ok": True,
            "pdfBase64": base64.b64encode(pdf_bytes).decode("ascii"),
            "pageCount": page_count,
            "renderer": renderer,
            "bytes": len(pdf_bytes),
        }
    )
