# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Trusted desktop STUDY routes for course state, practice, and plans."""

from __future__ import annotations

import os
import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, Optional

from fastapi import APIRouter, HTTPException, Query

from learning.builtin_course_seed import seed_builtin_course
from learning.evaluations import EvaluationService
from learning.flashcards import FlashcardService
from learning.learning_contract import ContractError, LIFECYCLE_STATUSES
from learning.learning_plans import LearningPlanService
from learning.learning_data_service import CompositeLearningDataService
from learning.lifecycle import ArtifactLifecycleService
from learning.learning_store import (
    LearningConflictError,
    LearningStore,
    default_learning_db_path,
)
from learning.operation_coordinator import LearningCoordinationError
from learning.output_writer import OutputWriter
from learning.practice_generator import PracticeGenerator
from learning.practice_contract import PracticeContractError
from learning.practice_hints import PracticeHintService
from learning.quizzes import QuizService
from learning.semantic_review import requires_semantic_review
from learning.semantic_review import SemanticReviewService
from learning.student_state import LEGACY_CONTEXT_MIGRATION_KEY, StudentStateService
from learning.tutor_contract import TutorConflictError, TutorContractError
from learning.tutor_runtime_store import TutorRuntimeError, TutorRuntimeStore
from learning.wrongbook import WrongbookService
import learning_owner
from learning_owner import desktop_learning_scope
from study_review_reminder import StudyReviewReminderService
import kabuqina_time

router = APIRouter()

FLASHCARD_MIGRATION_KEY = "localStorage:kabuqina.study.flashcards.v1"
QUIZ_MIGRATION_KEY = "localStorage:kabuqina.study.quiz.v1"
DEFAULT_SPACE_TITLE = "Default course"
_SOURCE_KEYS = ("origin", "session_id", "source_label", "confidence", "gist")


@contextmanager
def _desktop_ctx(space_id: Optional[str] = None) -> Iterator[Any]:
    store = LearningStore()
    try:
        with desktop_learning_scope(store, space_id=space_id) as ctx:
            if space_id and not any(
                row.get("space_id") == space_id for row in ctx.list_spaces()
            ):
                raise KeyError("learning space is unavailable")
            yield ctx
    finally:
        store.close()


@contextmanager
def _desktop_data_service() -> Iterator[tuple[str, CompositeLearningDataService]]:
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
        service = CompositeLearningDataService(
            learning_store, runtime_store, learning_store.coordinator
        )
        yield learning_owner.desktop_owner_id(), service
    finally:
        if runtime_store is not None:
            runtime_store.close()
        learning_store.close()


def _workspace_root() -> Optional[str]:
    """Workspace root for materials, mirroring load_packages._workspace_root."""
    raw = (
        os.environ.get("HERMESDESK_WORKSPACE")
        or os.environ.get("HERMES_WORKSPACE")
        or ""
    ).strip()
    return raw or None


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (TutorConflictError, LearningCoordinationError, TutorRuntimeError)):
        status, code = 409, "study_conflict"
    elif isinstance(exc, (TutorContractError, PracticeContractError)):
        status, code = 400, "study_invalid_request"
    elif isinstance(exc, (ContractError, LearningConflictError)):
        status, code = 409, "study_conflict"
    elif isinstance(exc, ValueError):
        status, code = 400, "study_invalid_request"
    elif isinstance(exc, KeyError):
        status, code = 404, "study_not_found"
    else:
        status, code = 500, "study_internal_error"
    return HTTPException(
        status_code=status,
        detail={"code": code, "message": str(exc)},
    )


def _artifact_ref(artifact: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "artifact_id": artifact["artifact_id"],
        "kind": artifact["kind"],
        "title": artifact["title"],
        "version": artifact["version"],
        "status": artifact["status"],
        "review": artifact["review"],
        "created_at": artifact["created_at"],
        "updated_at": artifact["updated_at"],
    }


def _public_quiz_attempt(result: Dict[str, Any]) -> Dict[str, Any]:
    """Keep one attempt result useful without exposing answer or grader internals."""
    public_questions = []
    for question in result.get("perQuestion") or []:
        if not isinstance(question, dict):
            continue
        item = {
            key: question[key]
            for key in (
                "item_id", "prompt", "type", "correct", "earned", "points",
                "explanation", "tags", "mode", "timed_out", "ungraded",
                "gradable", "scored", "ungraded_steps", "failure_kind",
                "outcome", "grader_provenance",
            )
            if key in question
        }
        summary = question.get("failure_summary")
        if isinstance(summary, str) and summary:
            item["failure_summary"] = summary[:1200]
        public_questions.append(item)
    return {
        key: result[key]
        for key in (
            "activity_id", "score", "maxScore", "percent", "correctCount", "total", "weakTags"
        )
        if key in result
    } | {"perQuestion": public_questions}


def _space_payload(ctx) -> Dict[str, Any]:
    current = ctx.current_space()
    return {
        "currentSpaceId": current,
        "spaces": [
            {
                "space_id": s["space_id"],
                "title": s["title"],
                "status": s["status"],
                "is_current": bool(s["is_current"]),
            }
            for s in ctx.list_spaces()
        ],
    }


def _ensure_space(ctx) -> str:
    current = ctx.current_space()
    if current:
        return current
    return ctx.create_space(title=DEFAULT_SPACE_TITLE)


def _require_artifact(ctx, artifact_id: str) -> Dict[str, Any]:
    artifact = ctx.get_artifact(artifact_id)
    if not artifact:
        raise KeyError(f"artifact {artifact_id!r} not found")
    return artifact

def _activate_artifact(ctx, artifact: Dict[str, Any]) -> Dict[str, Any]:
    artifact_id, kind = artifact["artifact_id"], artifact["kind"]
    if kind == "flashcard_deck":
        return FlashcardService(ctx).activate_deck(artifact_id)
    if kind == "quiz":
        return QuizService(ctx).activate_quiz(artifact_id)
    if kind == "student_state":
        return StudentStateService(ctx).activate_state(artifact_id)
    if kind == "evaluation":
        return EvaluationService(ctx).activate_evaluation(artifact_id)
    if kind == "learning_plan":
        return LearningPlanService(ctx).activate_plan(artifact_id)
    if kind in {"knowledge_base", "resource_pack", "tutoring_note"}:
        if (
            requires_semantic_review(artifact)
            and artifact.get("review", {}).get("status") != "passed"
        ):
            raise ValueError("semantic review must be approved before activation")
        ctx.set_artifact_status(artifact_id, "active")
        return {"artifact_id": artifact_id, "status": "active"}
    raise ValueError(f"unsupported artifact kind: {kind}")

def _record_migration_failure(key: str, exc: Exception) -> None:
    try:
        with _desktop_ctx() as ctx:
            ctx.mark_migration_failure(
                key,
                {
                    "error_type": type(exc).__name__,
                    "message": str(exc)[:300],
                },
            )
    except Exception:
        pass


def _token_usage_window(window: str) -> tuple[datetime, datetime]:
    current = kabuqina_time.now()
    if window == "week":
        start = current.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
            days=current.weekday()
        )
    elif window == "month":
        start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        raise ValueError("window must be week or month")
    return start, current


def _utc_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _token_usage_payload(
    *,
    window: str,
    starts_at: datetime,
    ends_at: datetime,
    rows: list[dict[str, Any]],
    spaces: list[dict[str, Any]],
) -> dict[str, Any]:
    titles = {str(space["space_id"]): str(space["title"]) for space in spaces}
    courses: dict[str, dict[str, Any]] = {}
    totals = {
        "inputTokens": 0,
        "outputTokens": 0,
        "totalTokens": 0,
        "succeededAttempts": 0,
        "inputMeasuredAttempts": 0,
        "outputMeasuredAttempts": 0,
        "incomplete": False,
    }

    for row in rows:
        space_id = str(row["space_id"])
        course = courses.setdefault(
            space_id,
            {
                "spaceId": space_id,
                "title": titles.get(space_id, "Unknown course"),
                "inputTokens": 0,
                "outputTokens": 0,
                "totalTokens": 0,
                "succeededAttempts": 0,
                "inputMeasuredAttempts": 0,
                "outputMeasuredAttempts": 0,
                "incomplete": False,
                "models": [],
            },
        )
        input_tokens = int(row["input_tokens"])
        output_tokens = int(row["output_tokens"])
        succeeded = int(row["succeeded_attempts"])
        input_measured = int(row["input_measured_attempts"])
        output_measured = int(row["output_measured_attempts"])
        incomplete = input_measured != succeeded or output_measured != succeeded
        model = {
            "providerId": str(row["provider_id"]),
            "modelId": str(row["model_id"]),
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
            "totalTokens": input_tokens + output_tokens,
            "succeededAttempts": succeeded,
            "inputMeasuredAttempts": input_measured,
            "outputMeasuredAttempts": output_measured,
            "incomplete": incomplete,
        }
        course["models"].append(model)
        for target in (course, totals):
            target["inputTokens"] += input_tokens
            target["outputTokens"] += output_tokens
            target["totalTokens"] += input_tokens + output_tokens
            target["succeededAttempts"] += succeeded
            target["inputMeasuredAttempts"] += input_measured
            target["outputMeasuredAttempts"] += output_measured
            target["incomplete"] = bool(target["incomplete"] or incomplete)

    ordered_courses = sorted(
        courses.values(), key=lambda item: (item["title"].casefold(), item["spaceId"])
    )
    for course in ordered_courses:
        course["models"].sort(key=lambda item: (item["providerId"], item["modelId"]))
    return {
        "window": window,
        "startsAt": _utc_timestamp(starts_at),
        "endsAt": _utc_timestamp(ends_at),
        "totals": totals,
        "courses": ordered_courses,
    }


def _empty_summary_page(*, limit: int, offset: int) -> Dict[str, Any]:
    return {
        "items": [],
        "count": 0,
        "counts": {name: 0 for name in sorted(LIFECYCLE_STATUSES)},
        "kind_counts": {},
        "returned": 0,
        "limit": limit,
        "offset": offset,
        "truncated": False,
    }


def _source_refs_from_body(body: Dict[str, Any]) -> list[Dict[str, str]]:
    source = body.get("source") if isinstance(body.get("source"), dict) else {}
    ref: Dict[str, str] = {}
    for key in _SOURCE_KEYS:
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            ref[key] = value.strip()
    return [ref] if ref else []


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _required_space_id(body: Dict[str, Any]) -> str:
    space_id = str(body.get("space_id") or "").strip()
    if not space_id:
        raise ValueError("space_id is required")
    return space_id


def _normalized_front(value: Any) -> str:
    return _clean_text(value).casefold()


def _legacy_cards_to_import(ctx, cards: Any) -> list[Any]:
    if not isinstance(cards, list):
        return []

    service = FlashcardService(ctx)
    seen = {
        normalized
        for card in service.list_cards()
        for normalized in [_normalized_front(card.get("front"))]
        if normalized
    }
    out: list[Any] = []
    for card in cards:
        if not isinstance(card, dict):
            out.append(card)
            continue
        normalized = _normalized_front(card.get("front"))
        if normalized and normalized in seen:
            continue
        if normalized:
            seen.add(normalized)
        out.append(card)
    return out


@router.get("/api/desk/study/spaces")
async def study_spaces():
    with _desktop_ctx() as ctx:
        return _space_payload(ctx)


@router.post("/api/desk/study/spaces")
async def study_space_create(body: Dict[str, Any]):
    title = str(body.get("title") or "").strip()
    try:
        with _desktop_ctx() as ctx:
            sid = ctx.create_space(title=title, space_id=body.get("space_id"))
            return {"space_id": sid, **_space_payload(ctx)}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/spaces/{space_id}/select")
async def study_space_select(space_id: str):
    try:
        with _desktop_ctx() as ctx:
            ctx.select_space(space_id)
            return {"space_id": space_id, **_space_payload(ctx)}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/migrations/builtin-course")
async def study_seed_builtin_course():
    """Seed the built-in 'Python 高级程序设计' course once for this owner."""
    try:
        with _desktop_ctx() as ctx:
            return seed_builtin_course(ctx, workspace_root=_workspace_root())
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/drafts")
async def study_drafts(
    kind: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    try:
        with _desktop_ctx() as ctx:
            if not ctx.current_space():
                return _empty_summary_page(limit=limit, offset=offset)
            return ArtifactLifecycleService(ctx).summaries(
                kind=kind, status="draft", limit=limit, offset=offset
            )
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/artifacts")
async def study_artifact_summaries(
    space_id: str = Query(...),
    kind: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    try:
        with _desktop_ctx(space_id=space_id) as ctx:
            if not ctx.current_space():
                return _empty_summary_page(limit=limit, offset=offset)
            return ArtifactLifecycleService(ctx).summaries(
                kind=kind, status=status, limit=limit, offset=offset
            )
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/artifacts/{artifact_id}/activate")
async def study_artifact_activate(artifact_id: str):
    try:
        with _desktop_ctx() as ctx:
            artifact = _require_artifact(ctx, artifact_id)
            return _activate_artifact(ctx, artifact)
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/artifacts/{artifact_id}/reject")
async def study_artifact_reject(artifact_id: str):
    try:
        with _desktop_ctx() as ctx:
            artifact = _require_artifact(ctx, artifact_id)
            if artifact["kind"] == "flashcard_deck":
                return FlashcardService(ctx).reject_deck(artifact_id)
            if artifact["kind"] == "quiz":
                return QuizService(ctx).reject_quiz(artifact_id)
            if artifact["kind"] == "student_state":
                return StudentStateService(ctx).reject_state(artifact_id)
            if artifact["kind"] == "evaluation":
                return EvaluationService(ctx).reject_evaluation(artifact_id)
            if artifact["kind"] == "learning_plan":
                return LearningPlanService(ctx).reject_plan(artifact_id)
            if artifact["kind"] in {"knowledge_base", "resource_pack", "tutoring_note"}:
                ctx.set_artifact_status(artifact_id, "rejected")
                return {"artifact_id": artifact_id, "status": "rejected"}
            raise ValueError(f"unsupported artifact kind: {artifact['kind']}")
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/flashcards")
async def study_flashcards(
    space_id: str = Query(...), due_only: bool = Query(default=False)
):
    try:
        with _desktop_ctx(space_id=space_id) as ctx:
            if not ctx.current_space():
                return {"cards": []}
            return {"cards": FlashcardService(ctx).list_cards(due_only=due_only)}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc

@router.get("/api/desk/study/artifacts/{artifact_id}")
async def study_artifact_detail(
    artifact_id: str, space_id: str = Query(...)
):
    try:
        with _desktop_ctx(space_id=space_id) as ctx:
            return {"artifact": _require_artifact(ctx, artifact_id)}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc

@router.post("/api/desk/study/artifacts/{artifact_id}/status")
async def study_artifact_status(artifact_id: str, body: Dict[str, Any]):
    requested = str(body.get("status") or "").strip()
    try:
        space_id = _required_space_id(body)
        with _desktop_ctx(space_id=space_id) as ctx:
            artifact = _require_artifact(ctx, artifact_id)
            if requested == "active":
                return _activate_artifact(ctx, artifact)
            if requested in {"rejected", "archived"}:
                ctx.set_artifact_status(artifact_id, requested)
                return {"artifact_id": artifact_id, "status": requested}
            raise ValueError("status must be active, rejected, or archived")
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc

@router.get("/api/desk/study/data/export")
async def study_data_export():
    try:
        with _desktop_data_service() as (owner_id, service):
            return {"bundle": service.export_owner_bundle(owner_id)}
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/token-usage")
async def study_token_usage(window: str = Query(default="week")):
    try:
        starts_at, ends_at = _token_usage_window(window)
        with _desktop_data_service() as (owner_id, service):
            rows = service.runtime_store.aggregate_token_usage(
                owner_id,
                starts_at=_utc_timestamp(starts_at),
                ends_at=_utc_timestamp(ends_at),
            )
            spaces = service.learning_store.list_spaces(owner_id)
        return _token_usage_payload(
            window=window,
            starts_at=starts_at,
            ends_at=ends_at,
            rows=rows,
            spaces=spaces,
        )
    except (ValueError, KeyError, TutorContractError, TutorRuntimeError) as exc:
        raise _http_error(exc) from exc

@router.post("/api/desk/study/data/import")
async def study_data_import(body: Dict[str, Any]):
    try:
        if "owner_id" in body:
            raise ValueError("public import request must not contain owner_id")
        bundle = body.get("bundle") if isinstance(body.get("bundle"), dict) else {}
        mode = str(body.get("mode") or "replace_empty_owner")
        with _desktop_data_service() as (owner_id, service):
            return {
                "imported": service.import_owner_bundle(
                    owner_id, bundle, mode=mode
                )
            }
    except Exception as exc:
        raise _http_error(exc) from exc

@router.delete("/api/desk/study/data")
async def study_data_delete(body: Dict[str, Any]):
    try:
        if "owner_id" in body:
            raise ValueError("public delete request must not contain owner_id")
        if body.get("confirm") != "DELETE ALL LEARNING DATA":
            raise ValueError("explicit delete confirmation required")
        with _desktop_data_service() as (owner_id, service):
            return {
                "deleted": True,
                "counts": service.delete_owner_data(owner_id),
            }
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/data/prepare-downgrade")
async def study_data_prepare_downgrade(body: Dict[str, Any]):
    try:
        if body:
            raise ValueError("prepare-downgrade request body must be empty")
        with _desktop_data_service() as (owner_id, service):
            return service.prepare_downgrade(owner_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/data/prepare-downgrade/commit")
async def study_data_prepare_downgrade_commit(body: Dict[str, Any]):
    try:
        if "owner_id" in body:
            raise ValueError("public downgrade request must not contain owner_id")
        if set(body) != {"bundle_sha256"}:
            raise ValueError("bundle_sha256 is required")
        expected = body.get("bundle_sha256")
        if not isinstance(expected, str):
            raise ValueError("bundle_sha256 must be a string")
        with _desktop_data_service() as (owner_id, service):
            return service.commit_prepare_downgrade(owner_id, expected)
    except Exception as exc:
        raise _http_error(exc) from exc

@router.get("/api/desk/study/migrations/status")
async def study_migration_status():
    try:
        with _desktop_ctx() as ctx:
            rows = ctx.list_migrations()
            return {"migrations": rows, "count": len(rows)}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc

@router.get("/api/desk/study/migrations/failures/export")
async def study_migration_failures_export():
    try:
        with _desktop_ctx() as ctx:
            rows = ctx.list_migrations(status="failed")
            return {"version": 1, "failures": rows, "count": len(rows)}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc

@router.get("/api/desk/study/wrongbook")
async def study_wrongbook(
    space_id: str = Query(...),
    limit: int = Query(default=50, ge=1, le=100),
):
    try:
        with _desktop_ctx(space_id=space_id) as ctx:
            if not ctx.current_space():
                return {"weak_points": [], "evidence": [], "count": 0, "returned": 0, "limit": limit, "truncated": False}
            return WrongbookService(ctx).projection(limit=limit)
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/activities")
async def study_activities(
    space_id: str = Query(...),
    limit: int = Query(default=50, ge=1, le=100),
):
    try:
        with _desktop_ctx(space_id=space_id) as ctx:
            if not ctx.current_space():
                return {
                    "items": [], "count": 0, "returned": 0,
                    "limit": limit, "truncated": False,
                }
            page = ctx.activity_summary_page(limit=limit)
            items = page["rows"]
            return {
                "items": items,
                "count": page["count"],
                "returned": len(items),
                "limit": limit,
                "truncated": page["count"] > len(items),
            }
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/student-state")
async def study_student_state(space_id: str = Query(...)):
    try:
        with _desktop_ctx(space_id=space_id) as ctx:
            if not ctx.current_space():
                return {"state": None}
            return {"state": StudentStateService(ctx).get_current_state()}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc

@router.get("/api/desk/study/artifacts/{artifact_id}/source-audit")
async def study_source_audit(
    artifact_id: str, space_id: str = Query(...)
):
    try:
        with _desktop_ctx(space_id=space_id) as ctx:
            artifact = _require_artifact(ctx, artifact_id)
            return {"artifact_id": artifact_id, "source_refs": artifact["envelope"].get("source_refs") or []}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc

@router.post("/api/desk/study/artifacts/{artifact_id}/semantic-review")
async def study_semantic_review(artifact_id: str, body: Dict[str, Any]):
    """Run the production LLM reviewer; unavailable/invalid output stays pending."""
    from study_semantic_reviewer import review_artifact_with_model
    try:
        space_id = _required_space_id(body)
        with _desktop_ctx(space_id=space_id) as ctx:
            artifact = _require_artifact(ctx, artifact_id)
            decision = await asyncio.to_thread(review_artifact_with_model, artifact)
            return SemanticReviewService(ctx, lambda _artifact: decision).review(artifact_id)
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/knowledge-points")
async def study_knowledge_points(
    space_id: str = Query(...),
    limit: int = Query(default=50, ge=1, le=100),
):
    """Return only cards explicitly captured from trusted ``kq-kp`` source refs.

    The learning page needs a current-space projection for already captured
    knowledge points.  It must not infer provenance from a localized card tag,
    expose the source reference itself, or reconstruct capture details in Web.
    """
    try:
        with _desktop_ctx(space_id=space_id) as ctx:
            if not ctx.current_space():
                return {
                    "items": [], "count": 0, "returned": 0,
                    "limit": limit, "truncated": False,
                }
            items = []
            for card in FlashcardService(ctx).list_cards():
                artifact = ctx.get_artifact(str(card.get("artifact_id") or ""))
                if not artifact:
                    continue
                refs = artifact.get("envelope", {}).get("source_refs") or []
                source = next(
                    (
                        ref for ref in refs
                        if isinstance(ref, dict) and ref.get("origin") == "kq-kp"
                    ),
                    None,
                )
                if not source:
                    continue
                item = {
                    "item_id": str(card.get("item_id") or ""),
                    "artifact_id": str(card.get("artifact_id") or ""),
                    "front": str(card.get("front") or ""),
                    "gist": str(card.get("back") or ""),
                    "captured": True,
                }
                confidence = source.get("confidence")
                if isinstance(confidence, str) and confidence:
                    item["confidence"] = confidence
                items.append(item)
            count = len(items)
            page = items[:limit]
            return {
                "items": page,
                "count": count,
                "returned": len(page),
                "limit": limit,
                "truncated": count > len(page),
            }
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.put("/api/desk/study/student-state")
async def study_student_state_save(body: Dict[str, Any]):
    try:
        space_id = _required_space_id(body)
        with _desktop_ctx(space_id=space_id) as ctx:
            _ensure_space(ctx)
            state = body.get("state") if isinstance(body.get("state"), dict) else {}
            return {"state": StudentStateService(ctx).save_state(state)}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/migrations/context")
async def study_context_migrate(body: Dict[str, Any]):
    try:
        space_id = _required_space_id(body)
        with _desktop_ctx(space_id=space_id) as ctx:
            if ctx.is_migrated(LEGACY_CONTEXT_MIGRATION_KEY):
                return {"migrated": False}
            _ensure_space(ctx)
            legacy = body.get("context") if isinstance(body.get("context"), dict) else {}
            state_payload, evaluation_payload = StudentStateService.legacy_context_to_payloads(legacy)
            state = StudentStateService(ctx).save_state(
                state_payload, title="Legacy study context"
            )
            evaluation = None
            if evaluation_payload:
                result = OutputWriter(ctx).write_artifact(
                    kind="evaluation",
                    title="Legacy study evaluation",
                    payload=evaluation_payload,
                    source_refs=[
                        {
                            "origin": "legacy_local_storage",
                            "key": LEGACY_CONTEXT_MIGRATION_KEY,
                        }
                    ],
                )
                evaluation = EvaluationService(ctx).activate_evaluation(
                    result["artifact_id"]
                )
            ctx.mark_migration(
                LEGACY_CONTEXT_MIGRATION_KEY,
                detail={
                    "student_state": state["artifact_id"],
                    "evaluation": evaluation["artifact_id"] if evaluation else "",
                },
            )
            return {
                "migrated": True,
                "student_state": state,
                "evaluation": evaluation,
            }
    except (ValueError, KeyError, ContractError) as exc:
        _record_migration_failure(LEGACY_CONTEXT_MIGRATION_KEY, exc)
        raise _http_error(exc) from exc


@router.get("/api/desk/study/evaluations")
async def study_evaluations(space_id: str = Query(...)):
    try:
        with _desktop_ctx(space_id=space_id) as ctx:
            if not ctx.current_space():
                return {"evaluations": []}
            return {
                "evaluations": EvaluationService(ctx).active_evaluation_projections()
            }
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/evaluations/{artifact_id}")
async def study_evaluation_detail(
    artifact_id: str, space_id: str = Query(...)
):
    try:
        with _desktop_ctx(space_id=space_id) as ctx:
            artifact = EvaluationService(ctx).get_evaluation(artifact_id)
            return {
                "evaluation": {
                    **_artifact_ref(artifact),
                    "payload": artifact["envelope"]["payload"],
                }
            }
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/learning-plans")
async def study_learning_plans(space_id: str = Query(...)):
    try:
        with _desktop_ctx(space_id=space_id) as ctx:
            if not ctx.current_space():
                return {"plans": []}
            rows = LearningPlanService(ctx).list_plans(status="active")
            return {"plans": [_artifact_ref(row) for row in rows]}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/learning-plans/{artifact_id}/items")
async def study_learning_plan_items(
    artifact_id: str, space_id: str = Query(...)
):
    try:
        with _desktop_ctx(space_id=space_id) as ctx:
            artifact = _require_artifact(ctx, artifact_id)
            if artifact["kind"] != "learning_plan":
                raise ValueError("artifact is not a learning_plan")
            return {
                "items": LearningPlanService(ctx).list_plan_items(
                    artifact_id=artifact_id
                )
            }
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/learning-plans/items/{item_id}/complete")
async def study_learning_plan_item_complete(item_id: str, body: Dict[str, Any]):
    try:
        space_id = _required_space_id(body)
        with _desktop_ctx(space_id=space_id) as ctx:
            return LearningPlanService(ctx).complete_item(
                item_id, note=str(body.get("note") or "")
            )
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/learning-plans/items/{item_id}/skip")
async def study_learning_plan_item_skip(item_id: str, body: Dict[str, Any]):
    try:
        space_id = _required_space_id(body)
        with _desktop_ctx(space_id=space_id) as ctx:
            return LearningPlanService(ctx).skip_item(
                item_id, note=str(body.get("note") or "")
            )
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/review-reminder")
async def study_review_reminder_get():
    try:
        with _desktop_ctx() as ctx:
            return StudyReviewReminderService(ctx.owner_id).get_settings()
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.put("/api/desk/study/review-reminder")
async def study_review_reminder_put(body: Dict[str, Any]):
    try:
        with _desktop_ctx() as ctx:
            return StudyReviewReminderService(ctx.owner_id).configure(
                enabled=body.get("enabled") is True,
                time_of_day=str(body.get("time_of_day") or "20:00"),
            )
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/flashcards/capture")
async def study_flashcard_capture(body: Dict[str, Any]):
    try:
        with _desktop_ctx() as ctx:
            _ensure_space(ctx)
            return FlashcardService(ctx).capture_card(
                front=str(body.get("front") or ""),
                back=str(body.get("back") or ""),
                hint=str(body.get("hint") or ""),
                tags=body.get("tags") if isinstance(body.get("tags"), list) else [],
                source_refs=_source_refs_from_body(body),
            )
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/flashcards/review")
async def study_flashcard_review(body: Dict[str, Any]):
    try:
        space_id = _required_space_id(body)
        with _desktop_ctx(space_id=space_id) as ctx:
            item_id = str(body.get("item_id") or "").strip()
            grade = str(body.get("grade") or "").strip()
            return FlashcardService(ctx).review_card(item_id, grade)
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/migrations/flashcards")
async def study_flashcards_migrate(body: Dict[str, Any]):
    try:
        with _desktop_ctx() as ctx:
            if ctx.is_migrated(FLASHCARD_MIGRATION_KEY):
                return {"migrated": False, "cards": 0}
            _ensure_space(ctx)
            deck = body.get("deck") if isinstance(body.get("deck"), dict) else {}
            cards = deck.get("cards") if isinstance(deck, dict) else []
            cards_to_import = _legacy_cards_to_import(ctx, cards)
            if not cards_to_import:
                ctx.mark_migration(
                    FLASHCARD_MIGRATION_KEY,
                    detail={"artifact_id": "", "cards": 0},
                )
                return {"migrated": True, "cards": 0, "status": "active"}

            title = str(body.get("title") or "Legacy flashcards").strip()
            writer = OutputWriter(ctx)
            res = writer.write_artifact(
                kind="flashcard_deck",
                title=title,
                payload={"cards": cards_to_import},
                source_refs=[{"origin": "legacy_local_storage", "key": FLASHCARD_MIGRATION_KEY}],
            )
            result = FlashcardService(ctx).activate_deck(res["artifact_id"])
            ctx.mark_migration(
                FLASHCARD_MIGRATION_KEY,
                detail={"artifact_id": res["artifact_id"], "cards": result["materialized"]},
            )
            return {
                "migrated": True,
                "artifact_id": res["artifact_id"],
                "cards": result["materialized"],
                "status": result["status"],
            }
    except (ValueError, KeyError, ContractError) as exc:
        _record_migration_failure(FLASHCARD_MIGRATION_KEY, exc)
        raise _http_error(exc) from exc


@router.get("/api/desk/study/quizzes")
async def study_quizzes(space_id: str = Query(...)):
    try:
        with _desktop_ctx(space_id=space_id) as ctx:
            if not ctx.current_space():
                return {"quizzes": []}
            quizzes = QuizService(ctx).list_quizzes(status="active")
            return {"quizzes": [_artifact_ref(item) for item in quizzes]}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/quizzes/{artifact_id}/questions")
async def study_quiz_questions(artifact_id: str, space_id: str = Query(...)):
    try:
        with _desktop_ctx(space_id=space_id) as ctx:
            artifact = _require_artifact(ctx, artifact_id)
            if artifact["kind"] != "quiz":
                raise ValueError("artifact is not a quiz")
            questions = QuizService(ctx).list_questions(artifact_id=artifact_id)
            return {"questions": questions}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/quizzes/{artifact_id}/submit")
async def study_quiz_submit(artifact_id: str, body: Dict[str, Any]):
    try:
        space_id = _required_space_id(body)
        with _desktop_ctx(space_id=space_id) as ctx:
            responses = body.get("responses") if isinstance(body.get("responses"), dict) else {}
            raw_item_ids = body.get("item_ids")
            if raw_item_ids is not None and not (
                isinstance(raw_item_ids, list)
                and all(isinstance(item_id, str) for item_id in raw_item_ids)
            ):
                raise ValueError("item_ids must be a list of question ids")
            return _public_quiz_attempt(
                QuizService(ctx).submit_attempt(
                    artifact_id,
                    responses,
                    item_ids=raw_item_ids,
                )
            )
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/quizzes/{artifact_id}/practice")
async def study_quiz_generate_practice(artifact_id: str, body: Dict[str, Any]):
    """Create a reviewable deterministic transcription or variant quiz draft."""
    try:
        space_id = _required_space_id(body)
        with _desktop_ctx(space_id=space_id) as ctx:
            item_id = _clean_text(body.get("item_id"))
            practice_kind = _clean_text(body.get("practice_kind"))
            if not item_id:
                raise ValueError("item_id is required")
            return PracticeGenerator(ctx).generate(
                artifact_id=artifact_id,
                item_id=item_id,
                practice_kind=practice_kind,
            )
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.post(
    "/api/desk/study/quizzes/{artifact_id}/questions/{item_id}/hints"
)
async def study_practice_hint(
    artifact_id: str, item_id: str, body: Dict[str, Any]
):
    """Return one explicit activated-question hint level with zero model calls."""
    try:
        if set(body) != {
            "schema_version",
            "space_id",
            "idempotency_key",
            "level",
        }:
            raise ValueError("hint request fields are invalid")
        space_id = _required_space_id(body)
        with _desktop_ctx(space_id=space_id) as ctx:
            return PracticeHintService(ctx).request_hint(
                {
                    "schema_version": body.get("schema_version"),
                    "artifact_id": artifact_id,
                    "item_id": item_id,
                    "idempotency_key": body.get("idempotency_key"),
                    "level": body.get("level"),
                }
            )
    except (
        ValueError,
        KeyError,
        ContractError,
        PracticeContractError,
        LearningConflictError,
    ) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/practice-source")
async def study_practice_source(
    space_id: str = Query(...), activity_id: str = Query(...)
):
    try:
        with _desktop_ctx(space_id=space_id) as ctx:
            return {"source": WrongbookService(ctx).retry_target(activity_id)}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/migrations/quizzes")
async def study_quizzes_migrate(body: Dict[str, Any]):
    try:
        with _desktop_ctx() as ctx:
            if ctx.is_migrated(QUIZ_MIGRATION_KEY):
                return {"migrated": False, "questions": 0}
            _ensure_space(ctx)
            quiz = body.get("quiz") if isinstance(body.get("quiz"), dict) else {}
            questions = quiz.get("questions") if isinstance(quiz, dict) else []
            title = str(quiz.get("title") or body.get("title") or "Legacy quiz").strip()
            writer = OutputWriter(ctx)
            res = writer.write_artifact(
                kind="quiz",
                title=title,
                payload={"questions": questions if isinstance(questions, list) else []},
                source_refs=[{"origin": "legacy_local_storage", "key": QUIZ_MIGRATION_KEY}],
            )
            result = QuizService(ctx).activate_quiz(res["artifact_id"])
            ctx.mark_migration(
                QUIZ_MIGRATION_KEY,
                detail={"artifact_id": res["artifact_id"], "questions": result["materialized"]},
            )
            return {
                "migrated": True,
                "artifact_id": res["artifact_id"],
                "questions": result["materialized"],
                "status": result["status"],
            }
    except (ValueError, KeyError, ContractError) as exc:
        _record_migration_failure(QUIZ_MIGRATION_KEY, exc)
        raise _http_error(exc) from exc
