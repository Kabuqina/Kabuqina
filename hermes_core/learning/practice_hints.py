# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Trusted, zero-provider hint requests for activated Practice questions."""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

from learning.learning_context import LearningExecutionContext
from learning.practice_contract import PracticeHintRequestV1
from learning.quizzes import QuizService


PRACTICE_HINT_ACTIVITY = "practice.hint_requested"
MAX_HINT_REQUESTS_PER_ITEM = 8


class PracticeHintService:
    """Return one explicit hint level and persist only bounded hash evidence."""

    def __init__(self, context: LearningExecutionContext):
        self._ctx = context

    def request_hint(
        self, request: PracticeHintRequestV1 | Mapping[str, Any]
    ) -> dict[str, Any]:
        normalized = (
            request
            if isinstance(request, PracticeHintRequestV1)
            else PracticeHintRequestV1.from_mapping(request)
        )
        question = self._active_question(normalized)
        ladder = question.get("hint_ladder")
        if not isinstance(ladder, dict):
            raise ValueError("hint_unavailable")
        content = ladder.get(normalized.level)
        if not isinstance(content, str) or not content:
            raise ValueError("hint_unavailable")

        content_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        recorded = self._ctx.record_bounded_activity_once(
            activity_id=normalized.activity_id,
            activity_type=PRACTICE_HINT_ACTIVITY,
            artifact_id=normalized.artifact_id,
            item_id=normalized.item_id,
            detail={
                "schema_version": 1,
                "level": normalized.level,
                "request_fingerprint": normalized.request_fingerprint,
                "content_sha256": content_sha256,
                "provider_attempts": 0,
            },
            max_occurrences=MAX_HINT_REQUESTS_PER_ITEM,
        )
        return {
            "schema_version": 1,
            "activity_id": recorded["activity_id"],
            "replayed": not recorded["created"],
            "artifact_id": normalized.artifact_id,
            "item_id": normalized.item_id,
            "level": normalized.level,
            "ordinal": recorded["ordinal"],
            "content": content,
            "budget_summary": {
                "provider_attempts": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "wall_ms": 0,
            },
        }

    def _active_question(
        self, request: PracticeHintRequestV1
    ) -> dict[str, Any]:
        artifact = self._ctx.get_artifact(request.artifact_id)
        if not artifact:
            raise KeyError(f"artifact {request.artifact_id!r} not found")
        if artifact.get("kind") != "quiz":
            raise ValueError("artifact is not a quiz")
        if artifact.get("status") != "active":
            raise ValueError("quiz is not active")
        for question in QuizService(self._ctx).list_questions(
            artifact_id=request.artifact_id, include_answers=True
        ):
            if question.get("item_id") == request.item_id:
                return question
        raise KeyError(f"question {request.item_id!r} not found")


__all__ = [
    "MAX_HINT_REQUESTS_PER_ITEM",
    "PRACTICE_HINT_ACTIVITY",
    "PracticeHintService",
]
