# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Confirmed photographed-work entries on the shared learning spine."""

from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from typing import Any, Mapping

from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningConflictError
from learning.study_capture_contract import (
    StudyCaptureContractError,
    validate_study_review_draft,
    validate_study_transcription,
)


EXTERNAL_WRONGBOOK_ITEM_TYPE = "external_wrongbook"
EXTERNAL_WRONGBOOK_ACTIVITY_TYPE = "external_wrongbook.confirmed"
_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_TEXT = 12_000


class ExternalWrongbookContractError(ValueError):
    """An external wrongbook draft or persisted entry is invalid."""


def _text(value: Any, field: str, *, required: bool = False) -> str:
    if not isinstance(value, str):
        raise ExternalWrongbookContractError(f"{field} must be text")
    normalized = value.strip()
    if (required and not normalized) or len(normalized) > _MAX_TEXT:
        raise ExternalWrongbookContractError(f"{field} is invalid")
    return normalized


def _strings(value: Any, field: str, *, maximum: int = 50) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum:
        raise ExternalWrongbookContractError(f"{field} must be a bounded array")
    return [
        _text(item, f"{field}[{index}]", required=True)
        for index, item in enumerate(value)
    ]


def _review(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    try:
        return validate_study_review_draft(value)
    except StudyCaptureContractError as exc:
        raise ExternalWrongbookContractError("review fields are invalid") from exc


def validate_wrongbook_details(value: Any) -> dict[str, Any]:
    """Validate the optional review data sent with a ``wrong`` decision."""
    if value is None:
        value = {}
    if not isinstance(value, Mapping) or not set(value).issubset(
        {"correct_work", "knowledge_points", "review"}
    ):
        raise ExternalWrongbookContractError("wrongbook fields are invalid")
    return {
        "correct_work": _text(value.get("correct_work", ""), "correct_work"),
        "knowledge_points": _strings(
            value.get("knowledge_points", []), "knowledge_points"
        ),
        "review": _review(value.get("review")),
    }


def _item_id(capture_id: str) -> str:
    return f"external-wrongbook:{capture_id}"


def _activity_id(capture_id: str) -> str:
    return f"external-wrongbook-confirmed:{capture_id}"


def _public(
    state: Mapping[str, Any], *, created_at: str = "", updated_at: str = ""
) -> dict[str, Any]:
    return copy.deepcopy(
        {
            "capture_id": state["capture_id"],
            "media_id": state["media_id"],
            "question_text": state["question_text"],
            "student_work": state["student_work"],
            "correct_work": state["correct_work"],
            "knowledge_points": state["knowledge_points"],
            "review": state["review"],
            "status": state["status"],
            "created_at": created_at or state["confirmed_at"],
            "updated_at": updated_at or state["confirmed_at"],
        }
    )


class ExternalWrongbookService:
    """Persist one active photographed wrongbook item per capture id."""

    def __init__(self, context: LearningExecutionContext):
        self._ctx = context

    def _existing(self, capture_id: str) -> dict[str, Any] | None:
        wanted = _item_id(capture_id)
        for row in self._ctx.list_items(item_type=EXTERNAL_WRONGBOOK_ITEM_TYPE):
            if row.get("item_id") == wanted:
                return row
        return None

    @staticmethod
    def _same_identity(current: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
        fields = (
            "schema_version",
            "capture_id",
            "media_id",
            "media_sha256",
            "question_text",
            "student_work",
            "correct_work",
            "knowledge_points",
            "review",
            "status",
            "provider",
            "model",
        )
        return all(current.get(field) == candidate.get(field) for field in fields)

    def activate(
        self,
        *,
        capture_id: str,
        media_id: str,
        media_sha256: str,
        transcription: Mapping[str, Any],
        details: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(capture_id, str) or not _ID_RE.fullmatch(capture_id):
            raise ExternalWrongbookContractError("capture_id is invalid")
        if (
            not isinstance(media_id, str)
            or not media_id.startswith(f"{capture_id}/")
            or ".." in media_id
            or len(media_id) > 300
        ):
            raise ExternalWrongbookContractError("media_id is invalid")
        if not isinstance(media_sha256, str) or not _SHA_RE.fullmatch(media_sha256):
            raise ExternalWrongbookContractError("media_sha256 is invalid")
        if media_id != f"{capture_id}/{media_sha256}.jpg":
            raise ExternalWrongbookContractError("media identity is invalid")
        try:
            normalized = validate_study_transcription(transcription)
        except StudyCaptureContractError as exc:
            raise ExternalWrongbookContractError(
                "transcription is invalid"
            ) from exc
        if normalized["capture_id"] != capture_id:
            raise ExternalWrongbookContractError("transcription identity changed")
        if normalized["question_match"] == "different":
            raise ExternalWrongbookContractError("capture_question_mismatch")
        draft = validate_wrongbook_details(details)
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        state = {
            "schema_version": 1,
            "revision": 1,
            "capture_id": capture_id,
            "media_id": media_id,
            "media_sha256": media_sha256,
            "question_text": normalized["question_text"],
            "student_work": normalized["student_work"],
            "correct_work": draft["correct_work"],
            "knowledge_points": draft["knowledge_points"],
            "review": draft["review"],
            "status": "active",
            "confirmed_at": now,
            # Kept for internal quality tracing; projections intentionally omit them.
            "provider": normalized["provider"],
            "model": normalized["model"],
        }
        existing = self._existing(capture_id)
        if existing is not None:
            current = (
                existing.get("state")
                if isinstance(existing.get("state"), dict)
                else {}
            )
            if not self._same_identity(current, state):
                raise LearningConflictError("wrongbook_idempotency_conflict")
            self._record_confirmation(capture_id, media_id, media_sha256)
            return _public(
                current,
                created_at=str(existing.get("created_at") or ""),
                updated_at=str(existing.get("updated_at") or ""),
            )

        item_id = _item_id(capture_id)
        try:
            self._ctx.compare_and_put_item_state_revision(
                item_id=item_id,
                item_type=EXTERNAL_WRONGBOOK_ITEM_TYPE,
                expected_revision=0,
                state=state,
            )
        except LearningConflictError:
            raced = self._existing(capture_id)
            current = (
                raced.get("state")
                if raced and isinstance(raced.get("state"), dict)
                else {}
            )
            if not raced or not self._same_identity(current, state):
                raise LearningConflictError("wrongbook_idempotency_conflict")
            existing = raced
        self._record_confirmation(capture_id, media_id, media_sha256)
        persisted = existing or self._existing(capture_id)
        return _public(
            persisted["state"] if persisted else state,
            created_at=str((persisted or {}).get("created_at") or now),
            updated_at=str((persisted or {}).get("updated_at") or now),
        )

    def _record_confirmation(
        self, capture_id: str, media_id: str, media_sha256: str
    ) -> None:
        self._ctx.record_bounded_activity_once(
            activity_id=_activity_id(capture_id),
            activity_type=EXTERNAL_WRONGBOOK_ACTIVITY_TYPE,
            artifact_id=None,
            item_id=_item_id(capture_id),
            detail={
                "capture_id": capture_id,
                "media_id": media_id,
                "media_sha256": media_sha256,
            },
            max_occurrences=1,
        )


__all__ = [
    "EXTERNAL_WRONGBOOK_ACTIVITY_TYPE",
    "EXTERNAL_WRONGBOOK_ITEM_TYPE",
    "ExternalWrongbookContractError",
    "ExternalWrongbookService",
    "validate_wrongbook_details",
]
