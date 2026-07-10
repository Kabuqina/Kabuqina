"""Learning Index skeleton — a deterministic read-only snapshot of one space.

The index is what a Planner reads *before* planning. It is assembled purely from
saved learning data:

- includes only ``active`` artifacts (as lightweight references, never full
  payloads) and allowed direct activities;
- excludes ``draft``/``rejected``/``archived`` — unreviewed content is never
  presented as course fact;
- never calls an LLM and never mutates the store or the Material Index;
- is versioned and size-bounded for one ``space_id``.

M4 adds bounded state, evaluation, current-plan, due-review, and weak-point
projections. Draft content never enters the snapshot.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from learning.evaluations import EvaluationService
from learning.flashcards import FlashcardService
from learning.learning_context import LearningExecutionContext
from learning.learning_plans import LearningPlanService
from learning.student_state import StudentStateService

INDEX_VERSION: int = 1

MAX_INDEX_ARTIFACTS: int = 1_000
MAX_INDEX_ACTIVITIES: int = 1_000
MAX_INDEX_BYTES: int = 256 * 1024
MAX_DUE_REVIEWS: int = 100
MAX_WEAK_POINTS: int = 24
MAX_CURRENT_PLAN_ITEMS: int = 100


def _artifact_ref(a: Dict[str, Any]) -> Dict[str, Any]:
    """Project a stored artifact to a lightweight index reference (no payload)."""
    return {
        "artifact_id": a["artifact_id"],
        "kind": a["kind"],
        "title": a["title"],
        "version": a["version"],
        "review": a["review"],
        "updated_at": a["updated_at"],
    }


def _activity_ref(a: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "activity_id": a["activity_id"],
        "activity_type": a["activity_type"],
        "artifact_id": a["artifact_id"],
        "item_id": a["item_id"],
        "created_at": a["created_at"],
    }


def _safe_strings(value: Any, *, limit: int = 24, text_limit: int = 800) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, str) or not raw.strip():
            continue
        item = raw.strip()[:text_limit]
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def _dedupe_strings(values: List[str], limit: int = MAX_WEAK_POINTS) -> List[str]:
    return _safe_strings(values, limit=limit)


def _safe_student_state(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    preferences = payload.get("preferences")
    safe_preferences = {
        str(key)[:80]: value.strip()[:800]
        for key, value in (preferences.items() if isinstance(preferences, dict) else [])
        if isinstance(value, str) and value.strip()
    }
    return {
        "course": str(payload.get("course") or "").strip()[:800],
        "goals": _safe_strings(payload.get("goals")),
        "preferences": safe_preferences,
        "constraints": _safe_strings(payload.get("constraints")),
        "progress_notes": _safe_strings(payload.get("progress_notes")),
        "current_stage": str(payload.get("current_stage") or "").strip()[:800],
        "next_adjustment": str(payload.get("next_adjustment") or "").strip()[:800],
    }


def _safe_plan_item(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "item_id": str(item.get("item_id") or "")[:160],
        "artifact_id": str(item.get("artifact_id") or "")[:160],
        "phaseIndex": item.get("phaseIndex") if isinstance(item.get("phaseIndex"), int) else 0,
        "taskIndex": item.get("taskIndex") if isinstance(item.get("taskIndex"), int) else 0,
        "title": str(item.get("title") or "").strip()[:800],
        "done_when": str(item.get("done_when") or "").strip()[:800],
        "status": str(item.get("status") or "open")[:40],
        "completedAt": str(item.get("completedAt") or "")[:80],
        "skippedAt": str(item.get("skippedAt") or "")[:80],
        "note": str(item.get("note") or "").strip()[:800],
    }


def _safe_activity_summary(a: Dict[str, Any]) -> Dict[str, Any]:
    ref = _activity_ref(a)
    detail = a.get("detail") if isinstance(a.get("detail"), dict) else {}
    activity_type = a.get("activity_type")
    if activity_type == "quiz.attempt":
        ref["summary"] = {
            key: detail.get(key)
            for key in ("score", "maxScore", "percent")
            if isinstance(detail.get(key), (int, float))
            and not isinstance(detail.get(key), bool)
        }
        ref["summary"]["weakTags"] = _safe_strings(
            detail.get("weakTags"), limit=MAX_WEAK_POINTS, text_limit=200
        )
    elif activity_type == "flashcard.review":
        summary: Dict[str, Any] = {}
        if isinstance(detail.get("grade"), str):
            summary["grade"] = detail["grade"][:40]
        if isinstance(detail.get("repetitions"), int):
            summary["repetitions"] = detail["repetitions"]
        if isinstance(detail.get("dueAt"), str):
            summary["dueAt"] = detail["dueAt"][:80]
        ref["summary"] = summary
    elif isinstance(activity_type, str) and activity_type.startswith("learning_plan.item."):
        ref["summary"] = {
            "status": str(detail.get("status") or "")[:40],
            "title": str(detail.get("title") or "").strip()[:800],
        }
    return ref


class LearningIndex:
    """Builds the read-only per-space snapshot from a runtime context."""

    def __init__(self, context: LearningExecutionContext):
        self._ctx = context

    def build(
        self,
        *,
        max_artifacts: int = MAX_INDEX_ARTIFACTS,
        max_activities: int = MAX_INDEX_ACTIVITIES,
        max_bytes: int = MAX_INDEX_BYTES,
    ) -> Dict[str, Any]:
        space_id = self._ctx._require_space()

        # Deterministic order: most-recent first, tie-broken by id.
        active = sorted(
            self._ctx.list_artifacts(status="active"),
            key=lambda a: (a["updated_at"], a["artifact_id"]),
            reverse=True,
        )
        activities = sorted(
            self._ctx.list_activities(),
            key=lambda a: (a["created_at"], a["activity_id"]),
            reverse=True,
        )

        truncated = len(active) > max_artifacts or len(activities) > max_activities
        artifacts = [_artifact_ref(a) for a in active[:max_artifacts]]
        acts = [_safe_activity_summary(a) for a in activities[:max_activities]]

        student = StudentStateService(self._ctx).get_current_state()
        evaluations = EvaluationService(self._ctx).active_evaluation_projections()
        plan_service = LearningPlanService(self._ctx)
        active_plans = sorted(
            plan_service.list_plans(status="active"),
            key=lambda row: (row["updated_at"], row["artifact_id"]),
            reverse=True,
        )
        current_plan = None
        if active_plans:
            plan = active_plans[0]
            current_plan = {
                "artifact_id": plan["artifact_id"],
                "title": str(plan.get("title") or "")[:800],
                "updated_at": plan["updated_at"],
                "items": [
                    _safe_plan_item(item)
                    for item in plan_service.list_plan_items(
                        artifact_id=plan["artifact_id"]
                    )[:MAX_CURRENT_PLAN_ITEMS]
                ],
            }

        weak_candidates = [
            point
            for evaluation in evaluations
            for point in evaluation.get("weak_points", [])
        ]
        for activity in activities:
            if activity.get("activity_type") != "quiz.attempt":
                continue
            detail = activity.get("detail")
            if isinstance(detail, dict):
                weak_candidates.extend(_safe_strings(detail.get("weakTags")))
        weak_points = _dedupe_strings(weak_candidates)

        due_reviews = [
            {
                "item_id": str(card.get("item_id") or "")[:160],
                "artifact_id": str(card.get("artifact_id") or "")[:160],
                "dueAt": str(card.get("dueAt") or "")[:80],
            }
            for card in FlashcardService(self._ctx).list_cards(due_only=True)[
                :MAX_DUE_REVIEWS
            ]
        ]

        snapshot: Dict[str, Any] = {
            "index_version": INDEX_VERSION,
            "space_id": space_id,
            "artifacts": artifacts,
            "activities": acts,
            "student_state": _safe_student_state(student["payload"]) if student else {},
            "evaluations": evaluations,
            "current_plan": current_plan,
            "due_reviews": due_reviews,
            "weak_points": weak_points,
            "truncated": truncated,
        }

        if self._exceeds(snapshot, max_bytes):
            truncated = True
            self._trim_to_bytes(snapshot, max_bytes)
            snapshot["truncated"] = True

        return snapshot

    @staticmethod
    def _exceeds(snapshot: Dict[str, Any], max_bytes: int) -> bool:
        return LearningIndex._byte_size(snapshot) > max_bytes

    @staticmethod
    def _byte_size(snapshot: Dict[str, Any]) -> int:
        return len(json.dumps(snapshot, ensure_ascii=False).encode("utf-8"))

    @staticmethod
    def _trim_to_bytes(snapshot: Dict[str, Any], max_bytes: int) -> None:
        """Deterministically shed the least essential bounded projections."""
        list_keys: List[str] = [
            "activities",
            "artifacts",
            "due_reviews",
            "evaluations",
            "weak_points",
        ]
        for key in list_keys:
            while snapshot[key] and LearningIndex._byte_size(snapshot) > max_bytes:
                snapshot[key].pop()

        plan = snapshot.get("current_plan")
        if isinstance(plan, dict):
            items = plan.get("items")
            while isinstance(items, list) and items and LearningIndex._byte_size(snapshot) > max_bytes:
                items.pop()
            if LearningIndex._byte_size(snapshot) > max_bytes:
                snapshot["current_plan"] = None

        state = snapshot.get("student_state")
        if isinstance(state, dict):
            for key in ("progress_notes", "constraints", "goals"):
                values = state.get(key)
                while isinstance(values, list) and values and LearningIndex._byte_size(snapshot) > max_bytes:
                    values.pop()
            preferences = state.get("preferences")
            while isinstance(preferences, dict) and preferences and LearningIndex._byte_size(snapshot) > max_bytes:
                preferences.pop(sorted(preferences)[-1])
            for key in ("next_adjustment", "current_stage", "course"):
                while (
                    isinstance(state.get(key), str)
                    and state[key]
                    and LearningIndex._byte_size(snapshot) > max_bytes
                ):
                    state[key] = state[key][: len(state[key]) // 2]
            if LearningIndex._byte_size(snapshot) > max_bytes:
                snapshot["student_state"] = {}
