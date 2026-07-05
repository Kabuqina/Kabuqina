"""Trusted flashcard capture and practice service for STUDY.

The model-facing ``learning`` tools can create ``flashcard_deck`` drafts. This
module is the trusted UI/API layer for kq-kp single-card capture: a user click
creates one active deck, materializes one ``learning_items`` row, and records a
real ``flashcard.capture`` activity.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from learning.learning_context import LearningExecutionContext
from learning.output_writer import OutputWriter

FLASHCARD_ITEM_TYPE = "flashcard"
FLASHCARD_CAPTURE_ACTIVITY = "flashcard.capture"
FLASHCARD_SPACE_CAP = 500
DEFAULT_EASE = 2.5


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


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


class FlashcardService:
    """Trusted operations for active flashcards."""

    def __init__(
        self,
        context: LearningExecutionContext,
        *,
        now: Optional[Callable[[], datetime]] = None,
    ):
        self._ctx = context
        self._now = now or _now_utc

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

    def list_cards(self, *, due_only: bool = False) -> List[Dict[str, Any]]:
        rows = self._ctx.list_items(item_type=FLASHCARD_ITEM_TYPE)
        cards = [self._card_from_item(row) for row in rows]
        if due_only:
            now = _iso(self._now())
            cards = [card for card in cards if not card.get("dueAt") or str(card["dueAt"]) <= now]
        return sorted(cards, key=lambda card: (str(card.get("dueAt") or ""), str(card.get("item_id") or "")))

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
        for card in self.list_cards():
            if _normalized_front(card.get("front")) == normalized:
                return {"duplicate": True, "item_id": card["item_id"]}

        if len(self.list_cards()) >= FLASHCARD_SPACE_CAP:
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
        return {
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
