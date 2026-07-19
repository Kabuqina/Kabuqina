"""Application service for the B02 Tutor lifecycle candidate.

The service deliberately exposes persisted lifecycle truth while keeping
start/resume behind a hard readiness gate.  B02 therefore cannot manufacture
a running activity before the deterministic graph/provider work exists.
"""

from __future__ import annotations

from typing import Any, Mapping
import uuid

from .checkpoint_store import LearningActivityRecordV1
from .tutor_contract import (
    ACTIVITY_STATUSES,
    LearningActivityKeyV1,
    LearningActivitySnapshotV1,
    LearningInterruptV1,
    TutorConflictError,
    TutorContractError,
    validate_cancel_request,
    validate_resume_request,
    validate_start_request,
)
from .tutor_runtime_store import TutorRuntimeStore


class TutorActivityNotReadyError(RuntimeError):
    reason_code = "study_activity_not_ready"

    def __init__(self) -> None:
        super().__init__("Tutor activity execution is not ready")


class TutorActivityNotFoundError(LookupError):
    reason_code = "study_activity_not_found"

    def __init__(self) -> None:
        super().__init__("Tutor activity was not found")


def _interrupt_from_record(
    record: LearningActivityRecordV1,
) -> LearningInterruptV1 | None:
    checkpoint = record.checkpoint
    if checkpoint is None or record.status != "waiting_for_learner":
        return None
    pending = checkpoint.state.get("pending_interrupt")
    if not isinstance(pending, Mapping):
        return None
    return LearningInterruptV1(
        interrupt_id=pending.get("interrupt_id"),
        key=record.key,
        checkpoint_revision=pending.get("checkpoint_revision"),
        prompt=dict(pending.get("prompt") or {}),
        expected_input=pending.get("expected_input"),
        created_at=pending.get("created_at"),
        kind=pending.get("kind"),
        schema_version=pending.get("schema_version"),
    )


def _latest_output(record: LearningActivityRecordV1) -> dict[str, str] | None:
    checkpoint = record.checkpoint
    if checkpoint is None:
        return None
    candidate = checkpoint.state.get("latest_output")
    if not isinstance(candidate, Mapping):
        return None
    kind = candidate.get("kind")
    markdown = candidate.get("markdown")
    if kind not in {"explanation", "feedback"} or not isinstance(markdown, str):
        return None
    if len(markdown) > 24_000:
        raise TutorContractError("latest_output exceeds 24000 characters")
    return {"kind": kind, "markdown": markdown}


def _terminal_projection(run: Mapping[str, Any]) -> dict[str, Any] | None:
    status = run["status"]
    if status not in {"completed", "blocked", "cancelled"}:
        return None
    terminal: dict[str, Any] = {
        "outcome": status,
        "budget_summary": {
            "nodes_used": int(run["budget_nodes_used"]),
            "attempts_used": int(run["budget_attempts_used"]),
            "reserved_input_tokens": int(run["budget_reserved_input_tokens"]),
            "reserved_output_tokens": int(run["budget_reserved_output_tokens"]),
            "reserved_wall_ms": int(run["budget_reserved_wall_ms"]),
            "active_elapsed_ms": int(run["budget_active_elapsed_ms"]),
        },
    }
    if run.get("completion_basis") is not None:
        terminal["completion_basis"] = run["completion_basis"]
    if status != "completed" and run.get("terminal_code") is not None:
        terminal["reason_code"] = run["terminal_code"]
    return terminal


def _snapshot(
    record: LearningActivityRecordV1, run: Mapping[str, Any]
) -> LearningActivitySnapshotV1:
    return LearningActivitySnapshotV1(
        key=record.key,
        status=record.status,
        revision=record.revision,
        label=str(run["label"]),
        latest_output=_latest_output(record),
        interrupt=_interrupt_from_record(record),
        terminal=_terminal_projection(run),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


class TutorActivityService:
    """B02 lifecycle service with a deliberately closed execution gate."""

    def __init__(self, runtime_store: TutorRuntimeStore) -> None:
        self.runtime_store = runtime_store

    def start(
        self, owner_id: str, body: Mapping[str, Any]
    ) -> LearningActivitySnapshotV1:
        # Validate before readiness so malformed/public-owner requests never
        # get disguised as transient availability failures.  Validation has no
        # persistence side effects.
        validate_start_request(
            body,
            owner_id=owner_id,
            activity_id=f"tact_{uuid.uuid4().hex}",
        )
        raise TutorActivityNotReadyError()

    def resume(
        self,
        owner_id: str,
        activity_kind: str,
        activity_id: str,
        body: Mapping[str, Any],
    ) -> LearningActivitySnapshotV1:
        request = validate_resume_request(body)
        key = LearningActivityKeyV1(
            owner_id, request.space_id, activity_kind, activity_id
        )
        if self.runtime_store.load_projection_source(key) is None:
            raise TutorActivityNotFoundError()
        raise TutorActivityNotReadyError()

    def get(
        self,
        owner_id: str,
        space_id: str,
        activity_kind: str,
        activity_id: str,
    ) -> LearningActivitySnapshotV1:
        key = LearningActivityKeyV1(
            owner_id, space_id, activity_kind, activity_id
        )
        source = self.runtime_store.load_projection_source(key)
        if source is None:
            raise TutorActivityNotFoundError()
        return _snapshot(*source)

    def list(
        self,
        owner_id: str,
        space_id: str,
        activity_kind: str,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[LearningActivitySnapshotV1]:
        # Constructing one key applies the same owner/space/kind validation as
        # get/cancel without inventing a second public identity parser.
        LearningActivityKeyV1(owner_id, space_id, activity_kind, "list")
        if status is not None and status not in ACTIVITY_STATUSES:
            raise TutorContractError("activity status is invalid")
        return [
            _snapshot(record, run)
            for record, run in self.runtime_store.list_projection_sources(
                owner_id,
                space_id,
                activity_kind,
                status=status,
                limit=limit,
            )
        ]

    def cancel(
        self,
        owner_id: str,
        activity_kind: str,
        activity_id: str,
        body: Mapping[str, Any],
    ) -> LearningActivitySnapshotV1:
        request = validate_cancel_request(body)
        key = LearningActivityKeyV1(
            owner_id, request.space_id, activity_kind, activity_id
        )
        try:
            self.runtime_store.cancel(
                key, expected_revision=request.expected_revision
            )
        except TutorConflictError as exc:
            if exc.reason_code == "activity_not_found":
                raise TutorActivityNotFoundError() from exc
            raise
        source = self.runtime_store.load_projection_source(key)
        if source is None:  # Defensive: terminal retention cannot remove new rows.
            raise TutorActivityNotFoundError()
        return _snapshot(*source)


__all__ = [
    "TutorActivityNotFoundError",
    "TutorActivityNotReadyError",
    "TutorActivityService",
]
