# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Review-only Level ⑤ explanation evaluation seam.

This module does not construct a network client.  A trusted caller may inject
one exact ``evaluate_once`` port.  The request is durably reserved before that
single call; a replay never calls the evaluator again.  Valid semantic output
can create only a pending-review ``evaluation`` draft and has no pass/fail or
branch authority.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from learning.learning_context import LearningExecutionContext
from learning.output_writer import OutputWriter
from learning.practice_contract import (
    PracticeContractError,
    PracticeExplanationRequestV1,
    PracticeSemanticResultV1,
    explanation_rubric_hash,
)
from learning.quizzes import QuizService


PRACTICE_EXPLANATION_ACTIVITY = "practice.explanation_submitted"
MAX_EXPLANATION_REQUESTS_PER_ITEM = 8


class PracticeEvaluatorPort(Protocol):
    def evaluate_once(
        self,
        request: PracticeExplanationRequestV1,
        rubric: Mapping[str, Any],
    ) -> Mapping[str, Any] | None: ...


class PracticeEvaluationDraftService:
    def __init__(self, context: LearningExecutionContext):
        self._ctx = context

    def evaluate_once(
        self,
        request: PracticeExplanationRequestV1 | Mapping[str, Any],
        evaluator: PracticeEvaluatorPort,
    ) -> dict[str, Any]:
        normalized = (
            request
            if isinstance(request, PracticeExplanationRequestV1)
            else PracticeExplanationRequestV1.from_mapping(request)
        )
        question = self._active_question(normalized)
        rubric = question.get("explanation_rubric")
        if not isinstance(rubric, dict):
            raise ValueError("explanation_rubric_unavailable")
        pinned_hash = explanation_rubric_hash(rubric)
        if normalized.rubric_sha256 != pinned_hash:
            raise PracticeContractError("explanation rubric hash mismatch")

        reservation = self._ctx.record_bounded_activity_once(
            activity_id=normalized.activity_id,
            activity_type=PRACTICE_EXPLANATION_ACTIVITY,
            artifact_id=normalized.artifact_id,
            item_id=normalized.item_id,
            detail={
                "schema_version": 1,
                "request_fingerprint": normalized.request_fingerprint,
                "rubric_sha256": pinned_hash,
                "learner_explanation": normalized.learner_explanation,
                "provider_attempts_reserved": 1,
            },
            max_occurrences=MAX_EXPLANATION_REQUESTS_PER_ITEM,
        )
        if not reservation["created"]:
            return self._pending(
                reservation["activity_id"],
                "idempotent_replay_not_reissued",
                provider_attempts=0,
            )

        try:
            raw_result = evaluator.evaluate_once(normalized, rubric)
        except Exception:
            return self._pending(
                reservation["activity_id"],
                "evaluator_unavailable",
                provider_attempts=1,
            )
        if raw_result is None:
            return self._pending(
                reservation["activity_id"],
                "evaluator_unavailable",
                provider_attempts=1,
            )
        try:
            result = PracticeSemanticResultV1.from_mapping(raw_result)
        except PracticeContractError:
            return self._pending(
                reservation["activity_id"],
                "invalid_evaluator_output",
                provider_attempts=1,
            )
        expected_criteria = {
            item["criterion_id"] for item in rubric.get("criteria") or []
        }
        actual_criteria = {item["criterion_id"] for item in result.criteria}
        if (
            result.rubric_sha256 != pinned_hash
            or actual_criteria != expected_criteria
            or result.usage_summary["provider_attempts"] != 1
        ):
            return self._pending(
                reservation["activity_id"],
                "invalid_evaluator_output",
                provider_attempts=1,
            )

        weak_points: list[str] = []
        seen: set[str] = set()
        for criterion in result.criteria:
            if criterion["status"] not in {"gap", "uncertain"}:
                continue
            for tag in criterion.get("tags") or []:
                folded = tag.casefold()
                if folded not in seen:
                    seen.add(folded)
                    weak_points.append(tag)
        for tag in result.tags:
            folded = tag.casefold()
            if folded not in seen:
                seen.add(folded)
                weak_points.append(tag)

        evidence_ref = {
            "origin": "practice_explanation",
            "artifact_id": normalized.artifact_id,
            "item_id": normalized.item_id,
            "activity_id": reservation["activity_id"],
            "rubric_sha256": pinned_hash,
        }
        written = OutputWriter(self._ctx).write_artifact(
            kind="evaluation",
            title=f"Explanation review: {str(question.get('prompt') or '')[:240]}",
            payload={
                "observations": list(result.observations),
                "weak_points": weak_points,
                "suggestions": list(result.suggestions),
                "evidence_refs": [evidence_ref],
                "practice_evaluation": {
                    "schema_version": 1,
                    "rubric_sha256": pinned_hash,
                    "evidence_activity_id": reservation["activity_id"],
                    "criteria": [dict(item) for item in result.criteria],
                    "usage_summary": dict(result.usage_summary),
                },
            },
            source_refs=[evidence_ref],
            review={"mode": "semantic"},
        )
        return {
            "schema_version": 1,
            "status": "draft",
            "activity_id": reservation["activity_id"],
            "artifact_id": written["artifact_id"],
            "review": {"mode": "semantic", "status": "pending"},
            "budget_summary": dict(result.usage_summary),
        }

    @staticmethod
    def _pending(
        activity_id: str, reason_code: str, *, provider_attempts: int
    ) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "status": "pending",
            "activity_id": activity_id,
            "reason_code": reason_code,
            "budget_summary": {
                "provider_attempts": provider_attempts,
                "input_tokens": 0,
                "output_tokens": 0,
                "wall_ms": 0,
            },
        }

    def _active_question(
        self, request: PracticeExplanationRequestV1
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
    "MAX_EXPLANATION_REQUESTS_PER_ITEM",
    "PRACTICE_EXPLANATION_ACTIVITY",
    "PracticeEvaluationDraftService",
    "PracticeEvaluatorPort",
]
