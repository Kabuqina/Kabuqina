# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Trusted global Activity read projection."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from fastapi import APIRouter, HTTPException, Query

from activity_projection import ActivityProjectionService, normalize_statuses
from learning.knowledge_core_compilation_store import (
    KnowledgeCoreCompilationStore,
)
from learning.learning_store import LearningStore, default_learning_db_path
from learning.tutor_contract import TutorContractError
from learning.tutor_runtime_store import TutorRuntimeStore
import learning_owner
from studio_store import StudioStore


router = APIRouter()


@contextmanager
def _activity_projection() -> Iterator[ActivityProjectionService]:
    learning_store = LearningStore()
    runtime_store: TutorRuntimeStore | None = None
    compilation_store: KnowledgeCoreCompilationStore | None = None
    studio_store: StudioStore | None = None
    try:
        runtime_store = TutorRuntimeStore(
            learning_store.db_path.parent / "tutor_runtime.db",
            coordinator=learning_store.coordinator,
            secure_permissions=(
                learning_store.db_path == default_learning_db_path().resolve()
            ),
        )
        compilation_store = KnowledgeCoreCompilationStore(
            learning_store.db_path.parent / "knowledge_core_compilations.db"
        )
        studio_store = StudioStore()
        owner_id = learning_owner.desktop_owner_id()
        # Use the same process-local execution truth as the domain route.  A
        # restart must first turn abandoned running rows into interrupted rows;
        # live executions in this process must remain running.
        from desk_server.routes import study_activity_routes

        runtime_store.reconcile_abandoned(
            owner_id, study_activity_routes._live_execution_snapshot()
        )
        yield ActivityProjectionService(
            owner_id=owner_id,
            learning_store=learning_store,
            runtime_store=runtime_store,
            studio_store=studio_store,
            compilation_store=compilation_store,
        )
    finally:
        if studio_store is not None:
            studio_store.close()
        if runtime_store is not None:
            runtime_store.close()
        if compilation_store is not None:
            compilation_store.close()
        learning_store.close()


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, (ValueError, TutorContractError)):
        status, code = 400, "activity_invalid_request"
    else:
        status, code = 500, "activity_internal_error"
    return HTTPException(
        status_code=status,
        detail={"code": code, "message": str(exc)},
    )


@router.get("/api/desk/activity")
async def activity_records(
    statuses: list[str] | None = Query(default=None),
    limit: int = Query(default=100),
):
    try:
        with _activity_projection() as service:
            return service.list_records(
                statuses=normalize_statuses(statuses),
                limit=limit,
            )
    except Exception as exc:
        raise _error(exc) from exc
