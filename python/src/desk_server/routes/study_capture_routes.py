# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Trusted loopback routes for photographed Study work."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from learning.study_capture import (
    ProviderStudyReasoningPort,
    ProviderStudyVisionPort,
    StudyCaptureService,
    StudyVisionContractInvalid,
    StudyVisionError,
    StudyVisionNotConfigured,
    StudyQuestionMismatch,
    StudyReasoningContractInvalid,
    StudyReasoningError,
    StudyReasoningService,
)
from learning.external_wrongbook import (
    ExternalWrongbookContractError,
    ExternalWrongbookService,
    validate_wrongbook_details,
)
from learning.learning_store import LearningConflictError, LearningStore
from learning_owner import desktop_learning_scope
from study_capture_media import CaptureMediaError, StudyCaptureMediaStore


router = APIRouter()


def _env(canonical: str, legacy: str = "") -> str:
    return (
        os.environ.get(canonical)
        or (os.environ.get(legacy) if legacy else "")
        or ""
    ).strip()


def _media_store() -> StudyCaptureMediaStore:
    return StudyCaptureMediaStore()


@contextmanager
def _wrongbook_context(space_id: str):
    store = LearningStore()
    try:
        with desktop_learning_scope(store, space_id=space_id) as context:
            space = next(
                (row for row in context.list_spaces() if row.get("space_id") == space_id),
                None,
            )
            if not space or space.get("kind", "course") != "course":
                raise KeyError("learning space is unavailable")
            yield context
    finally:
        store.close()


def _vision_port() -> ProviderStudyVisionPort:
    configured = _env("KABUQINA_VISION_CONFIGURED", "HERMESDESK_VISION_CONFIGURED")
    provider = _env("KABUQINA_VISION_PROVIDER", "HERMESDESK_VISION_PROVIDER")
    model = _env("KABUQINA_VISION_MODEL", "HERMESDESK_VISION_MODEL")
    base_url = _env(
        "KABUQINA_VISION_API_BASE_URL", "HERMESDESK_VISION_API_BASE_URL"
    )
    api_key = os.environ.get("KABUQINA_VISION_API_KEY", "").strip()
    if configured != "1" or not all((provider, model, base_url, api_key)):
        raise StudyVisionNotConfigured(
            "independent Study vision provider is not configured"
        )
    return ProviderStudyVisionPort(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
    )


def _reasoning_service() -> StudyReasoningService:
    return StudyReasoningService(ProviderStudyReasoningPort())


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, CaptureMediaError):
        return HTTPException(
            status_code=exc.status,
            detail={"code": exc.code, "message": str(exc)},
        )
    if isinstance(exc, StudyQuestionMismatch):
        status, code = 409, "capture_question_mismatch"
    elif isinstance(exc, StudyReasoningContractInvalid):
        status, code = 422, "vision_contract_invalid"
    elif isinstance(exc, StudyReasoningError):
        status, code = 503, "vision_unavailable"
    elif isinstance(exc, LearningConflictError):
        status, code = 409, "wrongbook_idempotency_conflict"
    elif isinstance(exc, ExternalWrongbookContractError):
        status, code = (
            409,
            (
                "capture_question_mismatch"
                if str(exc) == "capture_question_mismatch"
                else "wrongbook_idempotency_conflict"
            ),
        )
    elif isinstance(exc, KeyError):
        status, code = 404, "capture_invalid_image"
    elif isinstance(exc, StudyVisionNotConfigured):
        status, code = 409, "vision_not_configured"
    elif isinstance(exc, StudyVisionContractInvalid):
        status, code = 422, "vision_contract_invalid"
    elif isinstance(exc, StudyVisionError):
        status, code = 503, "vision_unavailable"
    else:
        status, code = 500, "study_internal_error"
    return HTTPException(
        status_code=status,
        detail={"code": code, "message": str(exc)},
    )


@router.post("/api/desk/study/captures/stage")
async def study_capture_stage(body: Any = Body(...)):
    try:
        store = _media_store()
        store.cleanup_orphans()
        return store.register_staged(body)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/captures/{capture_id}/normalize")
async def study_capture_normalize(capture_id: str, body: Any = Body(...)):
    try:
        if not isinstance(body, dict) or body.get("capture_id") != capture_id:
            raise CaptureMediaError(
                "capture_invalid_image", "capture identity does not match route"
            )
        return _media_store().normalize(body)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/captures/{capture_id}/transcribe")
async def study_capture_transcribe(capture_id: str, body: Any = Body(...)):
    store: StudyCaptureMediaStore | None = None
    try:
        if not isinstance(body, dict) or not set(body).issubset(
            {"expected_revision", "question_context"}
        ):
            raise CaptureMediaError(
                "capture_invalid_image", "transcribe fields are invalid"
            )
        expected_revision = body.get("expected_revision")
        if type(expected_revision) is not int or expected_revision < 1:
            raise CaptureMediaError(
                "capture_revision_conflict",
                "expected_revision is required",
                status=409,
            )
        question_context = body.get("question_context", "")
        if not isinstance(question_context, str) or len(question_context) > 12_000:
            raise CaptureMediaError(
                "capture_invalid_image", "question_context is invalid"
            )
        store = _media_store()
        service = StudyCaptureService(_vision_port())
        return await store.transcribe(
            capture_id,
            expected_revision=expected_revision,
            service=service,
            question_context=question_context,
        )
    except StudyVisionContractInvalid as exc:
        if store is not None:
            store.discard_failed_transcription(capture_id)
        raise _http_error(exc) from exc


@router.post("/api/desk/study/captures/{capture_id}/assistance")
async def study_capture_assistance(capture_id: str, body: Any = Body(...)):
    try:
        if not isinstance(body, dict) or set(body) != {"expected_revision", "mode"}:
            raise CaptureMediaError(
                "capture_invalid_image", "assistance fields are invalid"
            )
        expected_revision = body.get("expected_revision")
        if type(expected_revision) is not int or expected_revision < 1:
            raise CaptureMediaError(
                "capture_revision_conflict", "expected_revision is invalid", status=409
            )
        transcription = _media_store().transcription_for_reasoning(
            capture_id, expected_revision=expected_revision
        )
        return await _reasoning_service().assistance(
            transcription, mode=body.get("mode")
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/captures/{capture_id}/review")
async def study_capture_review(capture_id: str, body: Any = Body(...)):
    try:
        if not isinstance(body, dict) or set(body) != {"expected_revision"}:
            raise CaptureMediaError("capture_invalid_image", "review fields are invalid")
        expected_revision = body.get("expected_revision")
        if type(expected_revision) is not int or expected_revision < 1:
            raise CaptureMediaError(
                "capture_revision_conflict", "expected_revision is invalid", status=409
            )
        transcription = _media_store().transcription_for_reasoning(
            capture_id, expected_revision=expected_revision
        )
        return await _reasoning_service().review(transcription)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/captures/{capture_id}/confirm")
async def study_capture_confirm(capture_id: str, body: Any = Body(...)):
    try:
        if not isinstance(body, dict):
            raise CaptureMediaError(
                "capture_invalid_image", "confirm body must be an object"
            )
        details = None
        if body.get("decision") == "wrong":
            details = validate_wrongbook_details(body.get("wrongbook"))
        elif "wrongbook" in body:
            raise CaptureMediaError(
                "capture_invalid_image", "wrongbook details require a wrong decision"
            )
        store = _media_store()
        capture = store.confirm(capture_id, body)
        if capture["status"] != "confirmed":
            return capture
        managed = store.managed_manifest(capture_id)
        with _wrongbook_context(capture["space_id"]) as context:
            entry = ExternalWrongbookService(context).activate(
                capture_id=capture_id,
                media_id=managed["media_id"],
                media_sha256=managed["sha256"],
                transcription=managed["transcription"],
                details=details,
            )
        return {**capture, "wrongbook_entry": entry}
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/captures/{capture_id}/abandon")
async def study_capture_abandon(capture_id: str, body: Any = Body(...)):
    try:
        if not isinstance(body, dict) or not set(body).issubset({"expected_revision"}):
            raise CaptureMediaError(
                "capture_invalid_image", "abandon fields are invalid"
            )
        expected_revision = body.get("expected_revision")
        if expected_revision is not None and (
            type(expected_revision) is not int or expected_revision < 1
        ):
            raise CaptureMediaError(
                "capture_revision_conflict", "expected_revision is invalid", status=409
            )
        return _media_store().abandon(capture_id, expected_revision)
    except Exception as exc:
        raise _http_error(exc) from exc


__all__ = ["router"]
