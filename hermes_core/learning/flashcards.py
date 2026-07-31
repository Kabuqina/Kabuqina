"""Trusted flashcard capture and practice service for STUDY.

The model-facing ``learning`` tools create ``flashcard_deck`` drafts. This
module is the trusted UI/API layer: kq-kp clicks can capture one active card,
and STUDY UI commands can activate/reject decks, materialize cards, and record
real review activities.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import kabuqina_time
from learning.learning_context import LearningExecutionContext
from learning.output_writer import OutputWriter
from learning.study_preferences import StudyPreferencesService

FLASHCARD_ITEM_TYPE = "flashcard"
FLASHCARD_CAPTURE_ACTIVITY = "flashcard.capture"
FLASHCARD_REVIEW_ACTIVITY = "flashcard.review"
FLASHCARD_SPACE_CAP = 500

MIN_EASE = 1.3
DEFAULT_EASE = 2.5
MAX_INTERVAL_DAYS = 365

_GRADE_DELTA = {
    "again": -0.2,
    "hard": -0.15,
    "good": 0.0,
    "easy": 0.15,
}


def _now_local() -> datetime:
    return kabuqina_time.now()


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _parse_iso(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        text = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _clean_text(value: Any, limit: int = 600) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _clean_tags(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    seen: set[str] = set()
    for raw in value:
        tag = _clean_text(raw, 40)
        if not tag:
            continue
        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(tag)
        if len(out) >= 8:
            break
    return out


def _round2(value: float) -> float:
    return round(value + 1e-9, 2)


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _item_id(artifact_id: str, index: int) -> str:
    return f"{artifact_id}-{index:04d}"


def _normalized_front(value: Any) -> str:
    return _clean_text(value).casefold()


def _capture_detail(source_refs: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    source = next((ref for ref in source_refs or [] if isinstance(ref, dict)), {})
    origin = _clean_text(source.get("origin"), 40) or "unknown"
    confidence = _clean_text(source.get("confidence"), 40)
    detail = {"origin": origin}
    if confidence:
        detail["confidence"] = confidence
    return detail


def _is_fresh(card: Dict[str, Any]) -> bool:
    return int(card.get("repetitions") or 0) <= 0 and not card.get("lastReviewedAt")


class FlashcardService:
    """Trusted operations for active flashcards and review activities."""

    def __init__(
        self,
        context: LearningExecutionContext,
        *,
        now: Optional[Callable[[], datetime]] = None,
    ):
        self._ctx = context
        self._now = now or _now_local

    def activate_deck(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self._require_deck(artifact_id)
        if artifact["status"] != "active":
            self._ctx.set_artifact_status(artifact_id, "active")
            artifact = self._require_deck(artifact_id)

        cards = self._deck_cards(artifact)
        existing = {
            row["item_id"]
            for row in self._ctx.list_items(item_type=FLASHCARD_ITEM_TYPE, artifact_id=artifact_id)
        }
        created = 0
        now = _iso(self._now())
        for index, card in enumerate(cards):
            iid = _item_id(artifact_id, index)
            if iid in existing:
                continue
            state = self._initial_state(card, item_id=iid, artifact_id=artifact_id, now=now)
            self._ctx.upsert_item(
                item_id=iid,
                item_type=FLASHCARD_ITEM_TYPE,
                artifact_id=artifact_id,
                state=state,
            )
            created += 1
        return {"artifact_id": artifact_id, "status": "active", "materialized": created}

    def reject_deck(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self._require_deck(artifact_id)
        if artifact["status"] != "rejected":
            self._ctx.set_artifact_status(artifact_id, "rejected")
        return {"artifact_id": artifact_id, "status": "rejected"}

    def list_decks(self, *, status: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._ctx.list_artifacts(kind="flashcard_deck", status=status)

    def list_cards(self, *, due_only: bool = False) -> List[Dict[str, Any]]:
        rows = self._ctx.list_items(item_type=FLASHCARD_ITEM_TYPE)
        cards = [self._card_from_item(row) for row in rows]
        if due_only:
            now = self._now()
            cards = [card for card in cards if self._is_due(card, now)]
        return sorted(cards, key=self._sort_key)

    def daily_queue(self) -> Dict[str, Any]:
        """Return today's capped due queue for the current course.

        Seen and unseen cards have independent budgets. Completed reviews are
        subtracted from today's budget, so refreshing cannot reveal another full
        batch after the first batch is answered.
        """
        preferences = StudyPreferencesService(self._ctx).get()
        progress = self._daily_progress()
        new_limit = preferences["daily_new_card_limit"]
        review_limit = preferences["daily_review_card_limit"]
        remaining_new = max(0, new_limit - progress["new"])
        remaining_review = max(0, review_limit - progress["review"])
        due = self.list_cards(due_only=True)
        fresh = [card for card in due if _is_fresh(card)]
        reviews = [card for card in due if not _is_fresh(card)]
        selected_new = fresh[:remaining_new]
        selected_reviews = reviews[:remaining_review]
        return {
            "cards": [*selected_new, *selected_reviews],
            "queue": {
                "date": self._now().date().isoformat(),
                "limits": {"new": new_limit, "review": review_limit},
                "completedToday": progress,
                "remaining": {"new": remaining_new, "review": remaining_review},
                "available": {"new": len(fresh), "review": len(reviews)},
                "shown": {"new": len(selected_new), "review": len(selected_reviews)},
            },
        }

    def capture_card(
        self,
        *,
        front: str,
        back: str,
        hint: str = "",
        tags: Optional[List[str]] = None,
        source_refs: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        clean_front = _clean_text(front)
        clean_back = _clean_text(back)
        if not clean_front or not clean_back:
            raise ValueError("front and back are required")

        normalized = _normalized_front(clean_front)
        cards = self.list_cards()
        for card in cards:
            if _normalized_front(card.get("front")) == normalized:
                return {"duplicate": True, "item_id": card["item_id"]}

        if len(cards) >= FLASHCARD_SPACE_CAP:
            raise ValueError(f"flashcard space cap reached ({FLASHCARD_SPACE_CAP})")

        card = {
            "front": clean_front,
            "back": clean_back,
            "hint": _clean_text(hint),
            "tags": _clean_tags(tags),
        }
        safe_source_refs = [ref for ref in (source_refs or []) if isinstance(ref, dict)]
        writer = OutputWriter(self._ctx)
        artifact = writer.write_artifact(
            kind="flashcard_deck",
            title=clean_front[:60],
            payload={"cards": [card]},
            source_refs=safe_source_refs,
        )
        self.activate_deck(artifact["artifact_id"])
        item_id = _item_id(artifact["artifact_id"], 0)
        due_at = self._require_card(item_id).get("dueAt", "")
        self._ctx.record_activity(
            activity_type=FLASHCARD_CAPTURE_ACTIVITY,
            artifact_id=artifact["artifact_id"],
            item_id=item_id,
            detail=_capture_detail(safe_source_refs),
        )
        return {
            "duplicate": False,
            "artifact_id": artifact["artifact_id"],
            "item_id": item_id,
            "front": clean_front,
            "dueAt": due_at,
        }

    def review_card(self, item_id: str, grade: str) -> Dict[str, Any]:
        card = self._require_card(item_id)
        queue_kind = "new" if _is_fresh(card) else "review"
        preferences = StudyPreferencesService(self._ctx).get()
        progress = self._daily_progress()
        limit = preferences[
            "daily_new_card_limit"
            if queue_kind == "new"
            else "daily_review_card_limit"
        ]
        if progress[queue_kind] >= limit:
            raise ValueError(f"daily {queue_kind} card limit reached")
        normalized_grade = grade if grade in _GRADE_DELTA else "again"
        updated = self._review_state(card, normalized_grade)
        self._ctx.update_item_state(item_id, updated)
        self._ctx.record_activity(
            activity_type=FLASHCARD_REVIEW_ACTIVITY,
            artifact_id=str(card.get("artifact_id") or ""),
            item_id=item_id,
            detail={
                "grade": normalized_grade,
                "ease": updated["ease"],
                "intervalDays": updated["intervalDays"],
                "repetitions": updated["repetitions"],
                "dueAt": updated["dueAt"],
                "queueKind": queue_kind,
            },
            occurred_at=_iso(self._now()),
        )
        return {**updated, "grade": normalized_grade}

    def _daily_progress(self) -> Dict[str, int]:
        now = self._now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        activities = self._ctx.list_activities_between(
            activity_type=FLASHCARD_REVIEW_ACTIVITY,
            created_at_gte=_iso(start),
            created_at_lt=_iso(end),
        )
        progress = {"new": 0, "review": 0}
        for activity in activities:
            detail = activity.get("detail") if isinstance(activity, dict) else {}
            kind = detail.get("queueKind") if isinstance(detail, dict) else None
            # Legacy same-day activities predate queueKind. Count them as review,
            # the fail-closed choice for a workload protection feature.
            progress[kind if kind in progress else "review"] += 1
        return progress

    def _require_deck(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self._ctx.get_artifact(artifact_id)
        if not artifact:
            raise KeyError(f"artifact {artifact_id!r} not found")
        if artifact.get("kind") != "flashcard_deck":
            raise ValueError("artifact is not a flashcard_deck")
        return artifact

    def _deck_cards(self, artifact: Dict[str, Any]) -> List[Dict[str, Any]]:
        envelope = artifact.get("envelope") or {}
        payload = envelope.get("payload") if isinstance(envelope, dict) else {}
        cards = payload.get("cards") if isinstance(payload, dict) else []
        return [card for card in cards if isinstance(card, dict)]

    def _initial_state(
        self,
        card: Dict[str, Any],
        *,
        item_id: str,
        artifact_id: str,
        now: str,
    ) -> Dict[str, Any]:
        state = {
            "item_id": item_id,
            "artifact_id": artifact_id,
            "front": _clean_text(card.get("front")),
            "back": _clean_text(card.get("back")),
            "hint": _clean_text(card.get("hint")),
            "tags": _clean_tags(card.get("tags")),
            "ease": DEFAULT_EASE,
            "intervalDays": 0,
            "repetitions": 0,
            "lapses": 0,
            "createdAt": now,
            "dueAt": now,
            "lastReviewedAt": "",
        }
        if isinstance(card.get("knowledge_core_id"), str):
            state["knowledge_core_id"] = _clean_text(card["knowledge_core_id"], 200)
            state["outline_node_id"] = _clean_text(card.get("outline_node_id"), 200)
            state["order"] = max(0, int(card.get("order") or 0))
            state["source_refs"] = [
                dict(ref)
                for ref in (card.get("source_refs") or [])
                if isinstance(ref, dict)
            ]
        return state

    def _card_from_item(self, row: Dict[str, Any]) -> Dict[str, Any]:
        state = dict(row.get("state") or {})
        return {
            **state,
            "item_id": row["item_id"],
            "artifact_id": row.get("artifact_id") or state.get("artifact_id") or "",
        }

    def _require_card(self, item_id: str) -> Dict[str, Any]:
        for card in self.list_cards():
            if card["item_id"] == item_id:
                return card
        raise KeyError(f"flashcard {item_id!r} not found")

    def _review_state(self, card: Dict[str, Any], grade: str) -> Dict[str, Any]:
        now = self._now()
        ease = _round2(_clamp(float(card.get("ease") or DEFAULT_EASE) + _GRADE_DELTA[grade], MIN_EASE, 5.0))
        repetitions = int(card.get("repetitions") or 0)
        lapses = int(card.get("lapses") or 0)
        previous_interval = max(1, int(card.get("intervalDays") or 0))

        if grade == "again":
            next_repetitions = 0
            interval = 1
            lapses += 1
        else:
            next_repetitions = repetitions + 1
            if repetitions <= 0:
                interval = 4 if grade == "easy" else 1 if grade == "hard" else 2
            elif repetitions == 1:
                interval = 8 if grade == "easy" else 4 if grade == "hard" else 6
            else:
                factor = 1.2 if grade == "hard" else ease * 1.3 if grade == "easy" else ease
                interval = round(previous_interval * factor)
        interval = int(_clamp(interval, 1, MAX_INTERVAL_DAYS))
        due = now + timedelta(days=interval)
        return {
            **card,
            "ease": ease,
            "intervalDays": interval,
            "repetitions": next_repetitions,
            "lapses": lapses,
            "lastReviewedAt": _iso(now),
            "dueAt": _iso(due),
        }

    def _is_due(self, card: Dict[str, Any], now: datetime) -> bool:
        due = _parse_iso(card.get("dueAt"))
        return due is None or due <= now

    def _sort_key(self, card: Dict[str, Any]) -> tuple:
        fresh_rank = 0 if _is_fresh(card) else 1
        due = _parse_iso(card.get("dueAt")) or datetime.min.replace(tzinfo=timezone.utc)
        return (fresh_rank, due, str(card.get("item_id") or ""))
