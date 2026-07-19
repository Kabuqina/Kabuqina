# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Trusted desktop STUDY routes for course spaces, flashcards, capture, and quizzes."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

from fastapi import APIRouter, HTTPException, Query

from learning.builtin_course_seed import seed_builtin_course
from learning.evaluations import EvaluationService
from learning.flashcards import FlashcardService
from learning.knowledge_graph import KnowledgeGraphService
from learning.learning_contract import ContractError
from learning.learning_plans import LearningPlanService
from learning.learning_store import LearningStore
from learning.output_writer import OutputWriter
from learning.quizzes import QuizService
from learning.student_state import LEGACY_CONTEXT_MIGRATION_KEY, StudentStateService
from learning_owner import desktop_learning_scope

router = APIRouter()

FLASHCARD_MIGRATION_KEY = "localStorage:kabuqina.study.flashcards.v1"
QUIZ_MIGRATION_KEY = "localStorage:kabuqina.study.quiz.v1"
DEFAULT_SPACE_TITLE = "Default course"
_SOURCE_KEYS = ("origin", "session_id", "source_label", "confidence", "gist")


@contextmanager
def _desktop_ctx() -> Iterator[Any]:
    store = LearningStore()
    try:
        with desktop_learning_scope(store) as ctx:
            yield ctx
    finally:
        store.close()


def _workspace_root() -> Optional[str]:
    """Workspace root for materials, mirroring load_packages._workspace_root."""
    raw = (
        os.environ.get("HERMESDESK_WORKSPACE")
        or os.environ.get("HERMES_WORKSPACE")
        or ""
    ).strip()
    return raw or None


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ContractError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


def _artifact_ref(artifact: Dict[str, Any]) -> Dict[str, Any]:
    ref = {
        "artifact_id": artifact["artifact_id"],
        "kind": artifact["kind"],
        "title": artifact["title"],
        "version": artifact["version"],
        "status": artifact["status"],
        "review": artifact["review"],
        "created_at": artifact["created_at"],
        "updated_at": artifact["updated_at"],
    }
    # Reviewable STUDY panels carry their payload so the UI can render content
    # without a second round-trip, and active items remain visible after trust
    # transition.
    if artifact.get("kind") in (
        "resource_pack",
        "knowledge_base",
        "student_state",
        "learning_plan",
        "evaluation",
    ):
        ref["payload"] = (artifact.get("envelope") or {}).get("payload")
    return ref


def _resource_artifact_detail(artifact: Dict[str, Any]) -> Dict[str, Any]:
    """Return the trusted desktop projection for one resource-pack artifact."""
    if artifact.get("kind") != "resource_pack":
        raise ValueError("artifact is not a resource_pack")
    envelope = artifact.get("envelope") or {}
    detail = _artifact_ref(artifact)
    detail["space_id"] = artifact["space_id"]
    detail["payload"] = envelope.get("payload") or {}
    detail["source_refs"] = envelope.get("source_refs") or []
    return detail


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


def _normalized_front(value: Any) -> str:
    return _clean_text(value).casefold()


def _has_legacy_context_data(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(_has_legacy_context_data(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_legacy_context_data(item) for item in value)
    return False


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


@router.post("/api/desk/study/cache/clear")
async def study_cache_clear():
    """Clear only the authenticated desktop owner's learning cache."""
    try:
        with _desktop_ctx() as ctx:
            return {"cleared": True, "counts": ctx.clear_owner_data()}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/student-state")
async def study_student_state():
    try:
        with _desktop_ctx() as ctx:
            if not ctx.current_space():
                return {"state": None}
            return {"state": StudentStateService(ctx).get_current_state()}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.put("/api/desk/study/student-state")
async def study_student_state_save(body: Dict[str, Any]):
    try:
        with _desktop_ctx() as ctx:
            _ensure_space(ctx)
            state = body.get("state") if isinstance(body.get("state"), dict) else {}
            saved_state = StudentStateService(ctx).save_state(state)
            evaluation = None
            evaluation_payload = body.get("evaluation")
            if isinstance(evaluation_payload, dict):
                result = OutputWriter(ctx).write_artifact(
                    kind="evaluation",
                    title="Learner profile update",
                    payload=evaluation_payload,
                    source_refs=[{"origin": "study_profile_editor"}],
                )
                evaluation = EvaluationService(ctx).activate_evaluation(
                    result["artifact_id"]
                )
            return {"state": saved_state, "evaluation": evaluation}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/migrations/context")
async def study_context_migrate(body: Dict[str, Any]):
    """Import the legacy Web study context once without seeding empty data."""
    try:
        with _desktop_ctx() as ctx:
            if ctx.is_migrated(LEGACY_CONTEXT_MIGRATION_KEY):
                return {"migrated": False}
            legacy = body.get("context") if isinstance(body.get("context"), dict) else {}
            if not _has_legacy_context_data(legacy):
                ctx.mark_migration(LEGACY_CONTEXT_MIGRATION_KEY, detail={"empty": True})
                return {"migrated": True, "student_state": None, "evaluation": None}

            _ensure_space(ctx)
            state_payload, evaluation_payload = StudentStateService.legacy_context_to_payloads(legacy)
            state = StudentStateService(ctx).save_state(state_payload, title="Imported study context")
            evaluation = None
            if evaluation_payload:
                res = OutputWriter(ctx).write_artifact(
                    kind="evaluation",
                    title="Imported study evaluation",
                    payload=evaluation_payload,
                    source_refs=[
                        {
                            "origin": "legacy_local_storage",
                            "key": LEGACY_CONTEXT_MIGRATION_KEY,
                        }
                    ],
                )
                evaluation = EvaluationService(ctx).activate_evaluation(res["artifact_id"])
            ctx.mark_migration(
                LEGACY_CONTEXT_MIGRATION_KEY,
                detail={"student_state": state["artifact_id"], "evaluation": evaluation},
            )
            return {"migrated": True, "student_state": state, "evaluation": evaluation}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/evaluations")
async def study_evaluations():
    try:
        with _desktop_ctx() as ctx:
            if not ctx.current_space():
                return {"evaluations": []}
            rows = EvaluationService(ctx).list_evaluations(status="active")
            return {"evaluations": [_artifact_ref(row) for row in rows]}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/evaluations/{artifact_id}")
async def study_evaluation_detail(artifact_id: str):
    try:
        with _desktop_ctx() as ctx:
            artifact = EvaluationService(ctx).get_evaluation(artifact_id)
            return {"evaluation": _artifact_ref(artifact)}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/learning-plans")
async def study_learning_plans():
    try:
        with _desktop_ctx() as ctx:
            if not ctx.current_space():
                return {"plans": []}
            rows = LearningPlanService(ctx).list_plans(status="active")
            return {"plans": [_artifact_ref(row) for row in rows]}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/learning-plans/{artifact_id}/items")
async def study_learning_plan_items(artifact_id: str):
    try:
        with _desktop_ctx() as ctx:
            artifact = _require_artifact(ctx, artifact_id)
            if artifact["kind"] != "learning_plan":
                raise ValueError("artifact is not a learning_plan")
            return {
                "items": LearningPlanService(ctx).list_plan_items(artifact_id=artifact_id)
            }
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/learning-plans/items/{item_id}/complete")
async def study_learning_plan_item_complete(item_id: str, body: Dict[str, Any]):
    try:
        with _desktop_ctx() as ctx:
            return LearningPlanService(ctx).complete_item(
                item_id, note=str(body.get("note") or "")
            )
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/learning-plans/items/{item_id}/skip")
async def study_learning_plan_item_skip(item_id: str, body: Dict[str, Any]):
    try:
        with _desktop_ctx() as ctx:
            return LearningPlanService(ctx).skip_item(
                item_id, note=str(body.get("note") or "")
            )
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/drafts")
async def study_drafts(kind: Optional[str] = Query(default=None)):
    try:
        with _desktop_ctx() as ctx:
            if not ctx.current_space():
                return {"drafts": []}
            # Panel-rendered artifacts have no separate "active" surface like
            # flashcards/quizzes, so return draft + active together — activation
            # should keep them visible, not hide them.
            statuses = (
                ("draft", "active")
                if kind
                in (
                    "resource_pack",
                    "knowledge_base",
                    "student_state",
                    "learning_plan",
                    "evaluation",
                )
                else ("draft",)
            )
            items = []
            for st in statuses:
                items.extend(ctx.list_artifacts(kind=kind, status=st))
            return {"drafts": [_artifact_ref(item) for item in items]}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/knowledge-graph")
async def study_knowledge_graph():
    """Project the current course space's reviewed knowledge bases as a graph."""
    try:
        with _desktop_ctx() as ctx:
            if not ctx.current_space():
                return {"nodes": [], "edges": [], "courses": []}
            return KnowledgeGraphService(ctx).build()
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get(
    "/api/desk/study/knowledge-concepts/{artifact_id}/{concept_index}"
)
async def study_knowledge_concept(artifact_id: str, concept_index: int):
    """Read one reviewed concept in the authenticated owner's current space."""
    try:
        with _desktop_ctx() as ctx:
            if not ctx.current_space():
                raise KeyError("concept not found")
            concept = KnowledgeGraphService(ctx).get_concept(
                artifact_id, concept_index
            )
            return {"concept": concept}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/artifacts/{artifact_id}")
async def study_artifact_detail(artifact_id: str):
    """Read one resource pack in the authenticated owner's current space."""
    try:
        with _desktop_ctx() as ctx:
            artifact = _require_artifact(ctx, artifact_id)
            return {"artifact": _resource_artifact_detail(artifact)}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/artifacts/{artifact_id}/activate")
async def study_artifact_activate(artifact_id: str):
    try:
        with _desktop_ctx() as ctx:
            artifact = _require_artifact(ctx, artifact_id)
            if artifact["kind"] == "flashcard_deck":
                return FlashcardService(ctx).activate_deck(artifact_id)
            if artifact["kind"] == "quiz":
                return QuizService(ctx).activate_quiz(artifact_id)
            if artifact["kind"] == "student_state":
                return StudentStateService(ctx).activate_state(artifact_id)
            if artifact["kind"] == "evaluation":
                return EvaluationService(ctx).activate_evaluation(artifact_id)
            if artifact["kind"] == "learning_plan":
                return LearningPlanService(ctx).activate_plan(artifact_id)
            if artifact["kind"] in ("resource_pack", "knowledge_base"):
                # M3: generated reference resources activate via a plain
                # trust-boundary status transition (no per-item study state).
                ctx.set_artifact_status(artifact_id, "active")
                return {"artifact_id": artifact_id, "status": "active", **_space_payload(ctx)}
            raise ValueError(f"unsupported artifact kind: {artifact['kind']}")
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
            if artifact["kind"] in ("resource_pack", "knowledge_base"):
                ctx.set_artifact_status(artifact_id, "rejected")
                return {"artifact_id": artifact_id, "status": "rejected", **_space_payload(ctx)}
            raise ValueError(f"unsupported artifact kind: {artifact['kind']}")
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/flashcards")
async def study_flashcards(due_only: bool = Query(default=False)):
    try:
        with _desktop_ctx() as ctx:
            if not ctx.current_space():
                return {"cards": []}
            return {"cards": FlashcardService(ctx).list_cards(due_only=due_only)}
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
        with _desktop_ctx() as ctx:
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
        raise _http_error(exc) from exc


@router.get("/api/desk/study/quizzes")
async def study_quizzes():
    try:
        with _desktop_ctx() as ctx:
            if not ctx.current_space():
                return {"quizzes": []}
            quizzes = QuizService(ctx).list_quizzes(status="active")
            return {"quizzes": [_artifact_ref(item) for item in quizzes]}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/quizzes/{artifact_id}/questions")
async def study_quiz_questions(artifact_id: str):
    try:
        with _desktop_ctx() as ctx:
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
        with _desktop_ctx() as ctx:
            responses = body.get("responses") if isinstance(body.get("responses"), dict) else {}
            return QuizService(ctx).submit_attempt(artifact_id, responses)
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
        raise _http_error(exc) from exc
