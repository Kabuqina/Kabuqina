"""Bounded, content-minimized wrongbook evidence projection."""

from __future__ import annotations

from typing import Any, Dict

from learning.evaluations import EvaluationService
from learning.external_wrongbook import (
    EXTERNAL_WRONGBOOK_ACTIVITY_TYPE,
    EXTERNAL_WRONGBOOK_ITEM_TYPE,
)
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
        external = []
        for row in self._ctx.list_items(item_type=EXTERNAL_WRONGBOOK_ITEM_TYPE):
            state = row.get("state") if isinstance(row.get("state"), dict) else {}
            if state.get("status") == "active":
                external.append(row)
        for row in external:
            state = row["state"]
            raw_points = state.get("knowledge_points")
            points = (
                [str(value)[:200] for value in raw_points[:50] if isinstance(value, str)]
                if isinstance(raw_points, list)
                else []
            )
            for point in points:
                if point and point.casefold() not in seen:
                    seen.add(point.casefold())
                    weak.append(point)
            capture_id = str(state.get("capture_id") or "")
            evidence.append(
                {
                    "activity_id": f"external-wrongbook-confirmed:{capture_id}",
                    "artifact_id": "",
                    "item_id": row["item_id"],
                    "activity_type": EXTERNAL_WRONGBOOK_ACTIVITY_TYPE,
                    "created_at": row["created_at"],
                    "capture_id": capture_id,
                    "media_id": str(state.get("media_id") or ""),
                    "question_text": str(state.get("question_text") or "")[:2_000],
                    "knowledge_points": points,
                }
            )
        evidence.sort(
            key=lambda item: (str(item.get("created_at") or ""), item["activity_id"]),
            reverse=True,
        )
        total = attempts["count"] + len(external)
        evidence = evidence[:limit]
        return {
            "weak_points": weak[:100],
            "evidence": evidence,
            "count": total,
            "returned": len(evidence),
            "limit": limit,
            "truncated": total > len(evidence),
        }

    def retry_target(self, activity_id: str) -> Dict[str, Any]:
        """Resolve an opaque wrongbook activity to a safe retry target.

        The route deliberately exposes only artifact and item identifiers.  The
        durable attempt detail is never returned to the desktop client.
        """
        row = self._ctx.quiz_attempt_by_id(activity_id)
        if not row:
            prefix = "external-wrongbook-confirmed:"
            if activity_id.startswith(prefix):
                capture_id = activity_id[len(prefix) :]
                wanted = f"external-wrongbook:{capture_id}"
                external = next(
                    (
                        item
                        for item in self._ctx.list_items(
                            item_type=EXTERNAL_WRONGBOOK_ITEM_TYPE
                        )
                        if item.get("item_id") == wanted
                    ),
                    None,
                )
                state = (
                    external.get("state")
                    if external and isinstance(external.get("state"), dict)
                    else {}
                )
                if state.get("status") == "active":
                    return {
                        "source_kind": "external_wrongbook",
                        "capture_id": capture_id,
                        "item_ids": [wanted],
                        "media_id": str(state.get("media_id") or ""),
                    }
            raise KeyError(f"wrongbook activity {activity_id!r} not found")
        artifact_id = str(row.get("artifact_id") or "").strip()
        artifact = self._ctx.get_artifact(artifact_id) if artifact_id else None
        if not artifact or artifact.get("kind") != "quiz" or artifact.get("status") != "active":
            raise KeyError("quiz retry source is unavailable")

        detail = row.get("detail") if isinstance(row.get("detail"), dict) else {}
        per_question = detail.get("perQuestion") if isinstance(detail.get("perQuestion"), list) else []
        item_ids: list[str] = []
        seen: set[str] = set()
        for result in per_question:
            if not isinstance(result, dict) or result.get("correct") is True:
                continue
            item_id = str(result.get("item_id") or "").strip()
            if item_id and item_id not in seen:
                seen.add(item_id)
                item_ids.append(item_id)
            if len(item_ids) >= 50:
                break
        return {"artifact_id": artifact_id, "item_ids": item_ids}
