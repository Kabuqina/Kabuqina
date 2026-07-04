# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Trusted desktop STUDY routes for course spaces, flashcards, capture, and quizzes."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

from fastapi import APIRouter, HTTPException, Query

from learning.flashcards import FlashcardService
from learning.learning_contract import ContractError
from learning.learning_store import LearningStore
from learning.output_writer import OutputWriter
from learning.quizzes import QuizService
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


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ContractError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


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


@router.get("/api/desk/study/drafts")
async def study_drafts(kind: Optional[str] = Query(default=None)):
    try:
        with _desktop_ctx() as ctx:
            if not ctx.current_space():
                return {"drafts": []}
            drafts = ctx.list_artifacts(kind=kind, status="draft")
            return {"drafts": [_artifact_ref(item) for item in drafts]}
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
