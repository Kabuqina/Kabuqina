# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Trusted Desktop source APIs for S-2 whiteboard state."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from fastapi import APIRouter, HTTPException, Query

from learning.learning_store import LearningStore
from learning.operation_coordinator import LearningCoordinationError
from learning.whiteboard import (
    WhiteboardConflictError,
    WhiteboardQuotaError,
    WhiteboardService,
)
from learning.whiteboard_contract import WhiteboardContractError
import learning_owner


router = APIRouter()


def _exact_body(body: Any, fields: set[str]) -> dict[str, Any]:
    if not isinstance(body, dict) or set(body) != fields:
        raise WhiteboardContractError("whiteboard request fields are invalid")
    if body.get("schema_version") != 1:
        raise WhiteboardContractError("whiteboard request version is invalid")
    return body


def _space_id(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise WhiteboardContractError("space_id is required")
    return value


@contextmanager
def _service(space_id: str) -> Iterator[WhiteboardService]:
    store = LearningStore()
    try:
        owner_id = learning_owner.desktop_owner_id()
        if store.get_space(owner_id, space_id) is None:
            raise KeyError("learning space is unavailable")
        yield WhiteboardService(store, owner_id, space_id)
    finally:
        store.close()


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(
        exc,
        (
            WhiteboardConflictError,
            WhiteboardQuotaError,
            LearningCoordinationError,
        ),
    ):
        status, code = 409, "study_conflict"
    elif isinstance(exc, WhiteboardContractError):
        status, code = 400, "study_invalid_request"
    elif isinstance(exc, KeyError):
        status, code = 404, "study_not_found"
    else:
        status, code = 500, "study_internal_error"
    return HTTPException(status_code=status, detail={"code": code, "message": str(exc)})


@router.get("/api/desk/study/whiteboards")
async def whiteboard_list(
    space_id: str = Query(...), limit: int = Query(default=50, ge=1, le=50)
):
    try:
        with _service(_space_id(space_id)) as service:
            return {"items": service.list_working(limit=limit)}
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/whiteboards/working/{activity_id}")
async def whiteboard_working_get(activity_id: str, space_id: str = Query(...)):
    try:
        with _service(_space_id(space_id)) as service:
            working = service.load_working(activity_id)
            if working is None:
                raise KeyError("whiteboard working state is unavailable")
            return working
    except Exception as exc:
        raise _http_error(exc) from exc


@router.put("/api/desk/study/whiteboards/working/{activity_id}")
async def whiteboard_working_save(activity_id: str, body: dict[str, Any]):
    try:
        request = _exact_body(
            body,
            {
                "schema_version",
                "space_id",
                "lineage_id",
                "expected_revision",
                "idempotency_key",
                "scene",
            },
        )
        with _service(_space_id(request["space_id"])) as service:
            return service.save_working(
                activity_id=activity_id,
                lineage_id=request["lineage_id"],
                expected_revision=request["expected_revision"],
                idempotency_key=request["idempotency_key"],
                scene=request["scene"],
            )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.delete("/api/desk/study/whiteboards/working/{activity_id}")
async def whiteboard_working_delete(activity_id: str, body: dict[str, Any]):
    try:
        request = _exact_body(
            body,
            {
                "schema_version",
                "space_id",
                "expected_revision",
                "idempotency_key",
            },
        )
        with _service(_space_id(request["space_id"])) as service:
            return service.delete_working(
                activity_id,
                expected_revision=request["expected_revision"],
                idempotency_key=request["idempotency_key"],
            )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/whiteboards/working/{activity_id}/snapshots")
async def whiteboard_snapshot_list(activity_id: str, space_id: str = Query(...)):
    try:
        with _service(_space_id(space_id)) as service:
            return {"items": service.list_snapshots(activity_id)}
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/whiteboards/working/{activity_id}/snapshots")
async def whiteboard_snapshot_create(activity_id: str, body: dict[str, Any]):
    try:
        request = _exact_body(
            body,
            {
                "schema_version",
                "space_id",
                "expected_working_revision",
                "idempotency_key",
            },
        )
        with _service(_space_id(request["space_id"])) as service:
            return service.create_snapshot(
                activity_id=activity_id,
                expected_working_revision=request["expected_working_revision"],
                idempotency_key=request["idempotency_key"],
            )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/whiteboards/snapshots/{artifact_id}")
async def whiteboard_snapshot_get(artifact_id: str, space_id: str = Query(...)):
    try:
        with _service(_space_id(space_id)) as service:
            return service.get_snapshot(artifact_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/whiteboards/snapshots/{artifact_id}/restore")
async def whiteboard_snapshot_restore(artifact_id: str, body: dict[str, Any]):
    try:
        request = _exact_body(
            body,
            {
                "schema_version",
                "space_id",
                "expected_working_revision",
                "idempotency_key",
            },
        )
        with _service(_space_id(request["space_id"])) as service:
            return service.restore_snapshot(
                artifact_id,
                expected_working_revision=request["expected_working_revision"],
                idempotency_key=request["idempotency_key"],
            )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/whiteboards/snapshots/{artifact_id}/attach")
async def whiteboard_snapshot_attach(artifact_id: str, body: dict[str, Any]):
    try:
        request = _exact_body(
            body,
            {"schema_version", "space_id", "idempotency_key"},
        )
        with _service(_space_id(request["space_id"])) as service:
            return service.attach_snapshot(
                artifact_id, idempotency_key=request["idempotency_key"]
            )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/whiteboards/snapshots/{artifact_id}/export")
async def whiteboard_snapshot_export(artifact_id: str, space_id: str = Query(...)):
    try:
        with _service(_space_id(space_id)) as service:
            return service.export_snapshot(artifact_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/whiteboards/snapshots/{artifact_id}/delete-preview")
async def whiteboard_snapshot_delete_preview(
    artifact_id: str, space_id: str = Query(...)
):
    try:
        with _service(_space_id(space_id)) as service:
            return service.preview_snapshot_delete(artifact_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.delete("/api/desk/study/whiteboards/snapshots/{artifact_id}")
async def whiteboard_snapshot_delete(artifact_id: str, body: dict[str, Any]):
    try:
        request = _exact_body(
            body,
            {
                "schema_version",
                "space_id",
                "target_artifact_ids",
                "idempotency_key",
            },
        )
        with _service(_space_id(request["space_id"])) as service:
            return service.delete_snapshots(
                artifact_id,
                target_artifact_ids=request["target_artifact_ids"],
                idempotency_key=request["idempotency_key"],
            )
    except Exception as exc:
        raise _http_error(exc) from exc


__all__ = ["router"]
