"""Bounded, content-minimized wrongbook evidence projection."""

from __future__ import annotations

from typing import Any, Dict

from learning.evaluations import EvaluationService
from learning.learning_context import LearningExecutionContext

MAX_WRONGBOOK_ATTEMPTS = 100


def _bounded_int(value: Any, *, minimum: int = 0, maximum: int = 1_000_000) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return minimum
    return min(max(number, minimum), maximum)


class WrongbookService:
    def __init__(self, context: LearningExecutionContext):
        self._ctx = context

    def projection(self, *, limit: int = 50) -> Dict[str, Any]:
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= MAX_WRONGBOOK_ATTEMPTS
        ):
            raise ValueError(f"limit must be within 1..{MAX_WRONGBOOK_ATTEMPTS}")
        weak: list[str] = []
        seen: set[str] = set()
        for evaluation in EvaluationService(self._ctx).active_evaluation_projections():
            for value in evaluation.get("weak_points") or []:
                text = str(value)[:200]
                if text and text.casefold() not in seen:
                    seen.add(text.casefold())
                    weak.append(text)
        attempts = self._ctx.quiz_attempt_page(limit=limit)
        evidence = []
        for row in attempts["rows"]:
            detail = row.get("detail") if isinstance(row.get("detail"), dict) else {}
            raw_tags = detail.get("weakTags")
            if not isinstance(raw_tags, list):
                raw_tags = []
            tags = [
                str(tag)[:40]
                for tag in raw_tags[:8]
                if isinstance(tag, str)
            ]
            for tag in tags:
                if tag.casefold() not in seen:
                    seen.add(tag.casefold())
                    weak.append(tag)
            evidence.append(
                {
                    "activity_id": row["activity_id"],
                    "artifact_id": row.get("artifact_id") or "",
                    "activity_type": "quiz.attempt",
                    "created_at": row["created_at"],
                    "score": _bounded_int(detail.get("score")),
                    "max_score": _bounded_int(detail.get("maxScore")),
                    "percent": _bounded_int(detail.get("percent"), maximum=100),
                    "weak_tags": tags,
                }
            )
        return {
            "weak_points": weak[:100],
            "evidence": evidence,
            "count": attempts["count"],
            "returned": len(evidence),
            "limit": limit,
            "truncated": attempts["count"] > len(evidence),
        }
