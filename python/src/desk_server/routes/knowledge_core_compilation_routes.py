# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Trusted HTTP boundary for knowledge-core compilation runtime."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from desk_server.knowledge_core_compile_runner import (
    get_knowledge_core_compile_runner,
)
from learning.knowledge_core_compiler import CompilationStop


router = APIRouter()


def _public(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "runId": str(run.get("run_id") or ""),
        "spaceId": str(run.get("space_id") or ""),
        "outlineNodeId": str(run.get("outline_node_id") or ""),
        "planItemId": str(run.get("plan_item_id") or "") or None,
        "trigger": str(run.get("trigger") or ""),
        "status": str(run.get("status") or ""),
        "sourceFingerprint": str(run.get("source_fingerprint") or ""),
        "policyVersion": str(run.get("policy_version") or ""),
        "draftArtifactId": str(run.get("draft_artifact_id") or "") or None,
        "reasonCode": str(run.get("reason_code") or "") or None,
        "sourceWindows": list(run.get("windows") or []),
        "createdAt": str(run.get("created_at") or ""),
        "updatedAt": str(run.get("updated_at") or ""),
    }


def _request(body: dict[str, Any]) -> tuple[dict[str, Any], int]:
    if not isinstance(body, dict):
        raise ValueError("compilation request must be an object")
    allowed = {
        "spaceId",
        "outlineNodeId",
        "planItemId",
        "trigger",
        "expectedMapRevision",
        "idempotencyKey",
        "priority",
    }
    if set(body) - allowed:
        raise ValueError("compilation request fields are invalid")
    priority = body.get("priority", 0)
    if type(priority) is not int or not -10 <= priority <= 10:
        raise ValueError("priority must be within -10..10")
    return (
        {
            "space_id": body.get("spaceId"),
            "outline_node_id": body.get("outlineNodeId"),
            "plan_item_id": body.get("planItemId"),
            "trigger": body.get("trigger"),
            "expected_map_revision": body.get("expectedMapRevision"),
            "idempotency_key": body.get("idempotencyKey"),
        },
        priority,
    )


def _error(exc: Exception) -> HTTPException:
    reason = getattr(exc, "reason_code", "")
    if reason in {
        "active_core_exists",
        "stale_learning_map",
        "plan_item_unavailable",
        "plan_item_outline_mismatch",
    }:
        status, code = 409, reason
    elif isinstance(exc, (ValueError, KeyError, CompilationStop)):
        status, code = 400, reason or "knowledge_core_compilation_invalid"
    else:
        status, code = 500, "knowledge_core_compilation_internal"
    return HTTPException(
        status_code=status,
        detail={"code": code, "message": str(exc)},
    )


@router.post("/api/desk/study/knowledge-core-compilations")
async def create_compilation(body: dict[str, Any]):
    try:
        request, priority = _request(body)
        run = get_knowledge_core_compile_runner().enqueue(
            request, priority=priority
        )
        return JSONResponse(status_code=202, content=_public(run))
    except Exception as exc:
        raise _error(exc) from exc


@router.get("/api/desk/study/knowledge-core-compilations")
async def list_compilations(
    space_id: str = Query(...),
    outline_node_id: str | None = Query(default=None),
    limit: int = Query(default=100),
):
    try:
        rows = get_knowledge_core_compile_runner().list(
            space_id=space_id,
            outline_node_id=outline_node_id,
            limit=limit,
        )
        return {"items": [_public(row) for row in rows], "count": len(rows)}
    except Exception as exc:
        raise _error(exc) from exc


@router.get("/api/desk/study/knowledge-core-compilations/{run_id}")
async def get_compilation(run_id: str, space_id: str = Query(...)):
    try:
        run = get_knowledge_core_compile_runner().get(space_id, run_id)
        if not run:
            raise KeyError("compilation run is unavailable")
        return _public(run)
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/api/desk/study/knowledge-core-compilations/{run_id}/retry")
async def retry_compilation(run_id: str, body: dict[str, Any]):
    try:
        if set(body) != {"spaceId"}:
            raise ValueError("retry request requires only spaceId")
        run = get_knowledge_core_compile_runner().retry(
            str(body["spaceId"]), run_id
        )
        return JSONResponse(status_code=202, content=_public(run))
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/api/desk/study/knowledge-core-compilations/{run_id}/cancel")
async def cancel_compilation(run_id: str, body: dict[str, Any]):
    try:
        if set(body) != {"spaceId"}:
            raise ValueError("cancel request requires only spaceId")
        return _public(
            get_knowledge_core_compile_runner().cancel(
                str(body["spaceId"]), run_id
            )
        )
    except Exception as exc:
        raise _error(exc) from exc


__all__ = ["router"]
