# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Trusted desktop STUDY routes for kq-kp flashcard capture."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterator

from fastapi import APIRouter, HTTPException, Query

from learning.flashcards import FlashcardService
from learning.learning_contract import ContractError
from learning.learning_store import LearningStore
from learning_owner import desktop_learning_scope

router = APIRouter()

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


def _ensure_space(ctx) -> str:
    current = ctx.current_space()
    if current:
        return current
    return ctx.create_space(title=DEFAULT_SPACE_TITLE)


def _source_refs_from_body(body: Dict[str, Any]) -> list[Dict[str, str]]:
    source = body.get("source") if isinstance(body.get("source"), dict) else {}
    ref: Dict[str, str] = {}
    for key in _SOURCE_KEYS:
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            ref[key] = value.strip()
    return [ref] if ref else []


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
