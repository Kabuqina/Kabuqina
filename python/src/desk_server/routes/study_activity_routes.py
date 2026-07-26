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


@router.post("/api/desk/study/activity-runs")
def study_activity_start(body: Dict[str, Any]):
    try:
        with _desktop_activity_service() as (owner_id, service):
            return service.start(owner_id, body).to_public_dict()
    except Exception as exc:
        raise _http_error(exc) from exc


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
