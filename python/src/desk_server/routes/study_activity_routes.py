"""Trusted desktop routes for the Tutor lifecycle candidate wire."""

from __future__ import annotations

from contextlib import contextmanager
import threading
from typing import Any, Dict, Iterator, Optional

from fastapi import APIRouter, HTTPException, Query

from learning.learning_store import LearningStore, default_learning_db_path
from learning.operation_coordinator import LearningCoordinationError
from learning.tutor_activity import (
    TutorActivityNotFoundError,
    TutorActivityNotReadyError,
    TutorActivityService,
)
from learning.tutor_contract import TutorConflictError, TutorContractError
from learning.tutor_runtime_store import TutorRuntimeError, TutorRuntimeStore
from learning.tutor_whiteboard import TutorWhiteboardPort
from learning.whiteboard import WhiteboardService
import learning_owner


router = APIRouter()
_LIVE_EXECUTIONS: set[str] = set()
_LIVE_EXECUTIONS_LOCK = threading.Lock()


def _execution_started(execution_id: str) -> None:
    with _LIVE_EXECUTIONS_LOCK:
        _LIVE_EXECUTIONS.add(execution_id)


def _execution_finished(execution_id: str) -> None:
    with _LIVE_EXECUTIONS_LOCK:
        _LIVE_EXECUTIONS.discard(execution_id)


def _live_execution_snapshot() -> set[str]:
    with _LIVE_EXECUTIONS_LOCK:
        return set(_LIVE_EXECUTIONS)


def _build_tutor_executor(
    runtime_store: TutorRuntimeStore,
    learning_store: LearningStore,
):
    from agent.graph_engine.tutor_engine import TutorActivityExecutor
    from learning.tutor_practice import TutorPracticeAdapter

    def practice_adapter(key):
        context = learning_owner.establish_desktop_context(
            learning_store,
            space_id=key.space_id,
        )
        if context.owner_id != key.owner_id:
            raise TutorContractError("Tutor owner context mismatch")
        return TutorPracticeAdapter(context)

    return TutorActivityExecutor(
        runtime_store,
        practice_adapter_factory=practice_adapter,
        execution_started=_execution_started,
        execution_finished=_execution_finished,
    )


@contextmanager
def _desktop_activity_service() -> Iterator[tuple[str, TutorActivityService]]:
    learning_store = LearningStore()
    runtime_store: TutorRuntimeStore | None = None
    try:
        runtime_store = TutorRuntimeStore(
            learning_store.db_path.parent / "tutor_runtime.db",
            coordinator=learning_store.coordinator,
            secure_permissions=(
                learning_store.db_path == default_learning_db_path().resolve()
            ),
        )
        owner_id = learning_owner.desktop_owner_id()
        # The set is process-local by design. After a desktop restart it is
        # empty, so the first trusted activity request conservatively charges
        # and interrupts abandoned running segments. Concurrent live requests
        # in this process are preserved by their registered execution_id.
        runtime_store.reconcile_abandoned(owner_id, _live_execution_snapshot())
        yield (
            owner_id,
            TutorActivityService(
                runtime_store,
                _build_tutor_executor(runtime_store, learning_store),
            ),
        )
    finally:
        if runtime_store is not None:
            runtime_store.close()
        learning_store.close()


@contextmanager
def _desktop_tutor_whiteboard(
    space_id: str,
) -> Iterator[tuple[str, TutorRuntimeStore, TutorWhiteboardPort]]:
    learning_store = LearningStore()
    runtime_store: TutorRuntimeStore | None = None
    try:
        runtime_store = TutorRuntimeStore(
            learning_store.db_path.parent / "tutor_runtime.db",
            coordinator=learning_store.coordinator,
            secure_permissions=(
                learning_store.db_path == default_learning_db_path().resolve()
            ),
        )
        owner_id = learning_owner.desktop_owner_id()
        runtime_store.reconcile_abandoned(owner_id, _live_execution_snapshot())
        yield (
            owner_id,
            runtime_store,
            TutorWhiteboardPort(
                runtime_store,
                WhiteboardService(learning_store, owner_id, space_id),
            ),
        )
    finally:
        if runtime_store is not None:
            runtime_store.close()
        learning_store.close()


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, TutorActivityNotReadyError):
        status, code, message = 503, exc.reason_code, str(exc)
    elif isinstance(exc, TutorActivityNotFoundError) or (
        isinstance(exc, TutorConflictError) and exc.reason_code == "activity_not_found"
    ):
        status, code, message = (
            404,
            "study_activity_not_found",
            "Tutor activity was not found",
        )
    elif isinstance(
        exc, (TutorConflictError, LearningCoordinationError, TutorRuntimeError)
    ):
        status, code, message = 409, "study_activity_conflict", str(exc)
    elif isinstance(exc, (TutorContractError, ValueError)):
        status, code, message = 400, "study_activity_invalid_request", str(exc)
    else:
        status, code, message = (
            500,
            "study_activity_internal_error",
            "Tutor activity request failed",
        )
    return HTTPException(
        status_code=status,
        detail={"code": code, "message": message},
    )


def _exact_body(body: Dict[str, Any], fields: set[str]) -> None:
    if not isinstance(body, dict) or set(body) != fields:
        raise TutorContractError("Tutor whiteboard request fields are invalid")


def _whiteboard_error(
    exc: Exception,
    port: TutorWhiteboardPort,
    key,
) -> HTTPException:
    error = _http_error(exc)
    detail = dict(error.detail) if isinstance(error.detail, dict) else {}
    try:
        detail["fallback"] = port.fallback_projection(key)
    except Exception:
        pass
    return HTTPException(status_code=error.status_code, detail=detail)


def _whiteboard_key(owner_id: str, space_id: str, activity_id: str):
    from learning.tutor_contract import LearningActivityKeyV1

    return LearningActivityKeyV1(
        owner_id, space_id, "tutor", activity_id
    )


@router.post("/api/desk/study/activity-runs")
def study_activity_start(body: Dict[str, Any]):
    try:
        with _desktop_activity_service() as (owner_id, service):
            return service.start(owner_id, body).to_public_dict()
    except Exception as exc:
        raise _http_error(exc) from exc


def _tutor_whiteboard_call(
    activity_id: str,
    body: Dict[str, Any],
    fields: set[str],
    invoke,
):
    try:
        _exact_body(body, fields)
    except Exception as exc:
        raise _http_error(exc) from exc
    with _desktop_tutor_whiteboard(body["space_id"]) as (
        owner_id,
        _runtime,
        port,
    ):
        key = _whiteboard_key(owner_id, body["space_id"], activity_id)
        try:
            return invoke(port, key)
        except Exception as exc:
            raise _whiteboard_error(exc, port, key) from exc


@router.post(
    "/api/desk/study/activity-runs/tutor/{activity_id}/whiteboard/preview"
)
def study_tutor_whiteboard_preview(activity_id: str, body: Dict[str, Any]):
    return _tutor_whiteboard_call(
        activity_id,
        body,
        {
            "space_id",
            "expected_tutor_revision",
            "expected_working_revision",
            "command_batch",
        },
        lambda port, key: port.preview(
            key,
            expected_tutor_revision=body["expected_tutor_revision"],
            expected_working_revision=body["expected_working_revision"],
            command_batch=body["command_batch"],
        ),
    )


@router.post(
    "/api/desk/study/activity-runs/tutor/{activity_id}/whiteboard/apply"
)
def study_tutor_whiteboard_apply(activity_id: str, body: Dict[str, Any]):
    return _tutor_whiteboard_call(
        activity_id,
        body,
        {
            "space_id",
            "expected_tutor_revision",
            "expected_working_revision",
            "command_batch",
            "preview_sha256",
            "idempotency_key",
        },
        lambda port, key: port.apply(
            key,
            expected_tutor_revision=body["expected_tutor_revision"],
            expected_working_revision=body["expected_working_revision"],
            command_batch=body["command_batch"],
            preview_sha256=body["preview_sha256"],
            idempotency_key=body["idempotency_key"],
        ),
    )


@router.post(
    "/api/desk/study/activity-runs/tutor/{activity_id}/whiteboard/snapshot"
)
def study_tutor_whiteboard_snapshot(activity_id: str, body: Dict[str, Any]):
    return _tutor_whiteboard_call(
        activity_id,
        body,
        {
            "space_id",
            "expected_tutor_revision",
            "expected_working_revision",
            "idempotency_key",
        },
        lambda port, key: port.snapshot(
            key,
            expected_tutor_revision=body["expected_tutor_revision"],
            expected_working_revision=body["expected_working_revision"],
            idempotency_key=body["idempotency_key"],
        ),
    )


@router.post(
    "/api/desk/study/activity-runs/tutor/{activity_id}/whiteboard/"
    "snapshots/{artifact_id}/attach"
)
def study_tutor_whiteboard_attach(
    activity_id: str, artifact_id: str, body: Dict[str, Any]
):
    return _tutor_whiteboard_call(
        activity_id,
        body,
        {"space_id", "expected_tutor_revision", "idempotency_key"},
        lambda port, key: port.attach(
            key,
            artifact_id,
            expected_tutor_revision=body["expected_tutor_revision"],
            idempotency_key=body["idempotency_key"],
        ),
    )


@router.post(
    "/api/desk/study/activity-runs/tutor/{activity_id}/whiteboard/"
    "snapshots/{artifact_id}/recover"
)
def study_tutor_whiteboard_recover(
    activity_id: str, artifact_id: str, body: Dict[str, Any]
):
    return _tutor_whiteboard_call(
        activity_id,
        body,
        {
            "space_id",
            "expected_tutor_revision",
            "expected_working_revision",
            "idempotency_key",
        },
        lambda port, key: port.recover(
            key,
            artifact_id,
            expected_tutor_revision=body["expected_tutor_revision"],
            expected_working_revision=body["expected_working_revision"],
            idempotency_key=body["idempotency_key"],
        ),
    )


@router.post(
    "/api/desk/study/activity-runs/tutor/{activity_id}/whiteboard/cancel"
)
def study_tutor_whiteboard_cancel(activity_id: str, body: Dict[str, Any]):
    return _tutor_whiteboard_call(
        activity_id,
        body,
        {
            "space_id",
            "expected_tutor_revision",
            "expected_working_revision",
            "idempotency_key",
        },
        lambda port, key: port.cancel(
            key,
            expected_tutor_revision=body["expected_tutor_revision"],
            expected_working_revision=body["expected_working_revision"],
            idempotency_key=body["idempotency_key"],
        ),
    )


@router.get("/api/desk/study/activity-runs")
async def study_activity_list(
    space_id: str = Query(...),
    activity_kind: str = Query(...),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=100),
):
    try:
        with _desktop_activity_service() as (owner_id, service):
            items = service.list(
                owner_id,
                space_id,
                activity_kind,
                status=status,
                limit=limit,
            )
            return {
                "items": [item.to_public_dict() for item in items],
                "count": len(items),
                "limit": limit,
            }
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/activity-runs/{activity_kind}/{activity_id}")
async def study_activity_get(
    activity_kind: str,
    activity_id: str,
    space_id: str = Query(...),
):
    try:
        with _desktop_activity_service() as (owner_id, service):
            return service.get(
                owner_id, space_id, activity_kind, activity_id
            ).to_public_dict()
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/activity-runs/{activity_kind}/{activity_id}/resume")
def study_activity_resume(
    activity_kind: str,
    activity_id: str,
    body: Dict[str, Any],
):
    try:
        with _desktop_activity_service() as (owner_id, service):
            return service.resume(
                owner_id, activity_kind, activity_id, body
            ).to_public_dict()
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/activity-runs/{activity_kind}/{activity_id}/cancel")
async def study_activity_cancel(
    activity_kind: str,
    activity_id: str,
    body: Dict[str, Any],
):
    try:
        with _desktop_activity_service() as (owner_id, service):
            return service.cancel(
                owner_id, activity_kind, activity_id, body
            ).to_public_dict()
    except Exception as exc:
        raise _http_error(exc) from exc
