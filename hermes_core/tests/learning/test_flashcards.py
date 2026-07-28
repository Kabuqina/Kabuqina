"""Tests for the STUDY M2 flashcard service.

M2 turns ``flashcard_deck`` artifacts into real practice state: trusted UI/API
activation materializes cards into learning items, and reviews update item state
while recording genuine user activity. Model tools still only create drafts.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from learning.flashcards import FLASHCARD_REVIEW_ACTIVITY, FlashcardService
from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningStore
from learning.output_writer import OutputWriter
from learning.study_preferences import StudyPreferencesService


T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture()
def ctx(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    context = LearningExecutionContext(store, owner_id="owner-A")
    context.create_space(title="Algebra", space_id="s1")
    try:
        yield context
    finally:
        store.close()


def _deck_payload():
    return {
        "cards": [
            {"front": "2+2", "back": "4", "hint": "arithmetic", "tags": ["math"]},
            {"front": "3+3", "back": "6"},
        ]
    }


def _draft_deck(ctx, title="Chapter 1"):
    return OutputWriter(ctx).write_artifact(
        kind="flashcard_deck",
        title=title,
        payload=_deck_payload(),
    )["artifact_id"]


def test_activate_deck_materializes_flashcards_as_items(ctx):
    artifact_id = _draft_deck(ctx)
    service = FlashcardService(ctx, now=lambda: T0)

    result = service.activate_deck(artifact_id)

    assert result["artifact_id"] == artifact_id
    assert result["status"] == "active"
    assert result["materialized"] == 2

    cards = service.list_cards()
    assert [card["front"] for card in cards] == ["2+2", "3+3"]
    assert all(card["artifact_id"] == artifact_id for card in cards)
    assert all(card["dueAt"] == T0.isoformat() for card in cards)


def test_reject_deck_does_not_materialize_cards(ctx):
    artifact_id = _draft_deck(ctx)
    service = FlashcardService(ctx, now=lambda: T0)

    result = service.reject_deck(artifact_id)

    assert result["status"] == "rejected"
    assert service.list_cards() == []


def test_review_card_updates_schedule_and_records_activity(ctx):
    artifact_id = _draft_deck(ctx)
    service = FlashcardService(ctx, now=lambda: T0)
    service.activate_deck(artifact_id)
    card = service.list_cards(due_only=True)[0]

    reviewed = service.review_card(card["item_id"], "good")

    assert reviewed["item_id"] == card["item_id"]
    assert reviewed["grade"] == "good"
    assert reviewed["repetitions"] == 1
    assert reviewed["intervalDays"] == 2
    assert reviewed["dueAt"].startswith("2026-01-03")

    activities = ctx.list_activities()
    assert len(activities) == 1
    assert activities[0]["activity_type"] == FLASHCARD_REVIEW_ACTIVITY
    assert activities[0]["artifact_id"] == artifact_id
    assert activities[0]["item_id"] == card["item_id"]
    assert activities[0]["detail"]["grade"] == "good"


def test_due_cards_sort_fresh_before_overdue_reviewed_cards(ctx):
    artifact_id = _draft_deck(ctx)
    service = FlashcardService(ctx, now=lambda: T0)
    service.activate_deck(artifact_id)
    first, second = service.list_cards()

    overdue = {
        **first,
        "repetitions": 2,
        "lastReviewedAt": "2025-12-20T00:00:00+00:00",
        "dueAt": "2025-12-31T00:00:00+00:00",
    }
    ctx.update_item_state(first["item_id"], overdue)
    due = service.list_cards(due_only=True)

    assert [card["item_id"] for card in due] == [second["item_id"], first["item_id"]]


def test_daily_queue_enforces_separate_new_and_review_budgets_across_refreshes(ctx):
    payload = {
        "cards": [
            {"front": f"q{index}", "back": f"a{index}"}
            for index in range(4)
        ]
    }
    artifact_id = OutputWriter(ctx).write_artifact(
        kind="flashcard_deck", title="Daily queue", payload=payload
    )["artifact_id"]
    clock = [T0]
    service = FlashcardService(ctx, now=lambda: clock[0])
    service.activate_deck(artifact_id)
    cards = service.list_cards()
    for card in cards[:2]:
        ctx.update_item_state(
            card["item_id"],
            {
                **card,
                "repetitions": 2,
                "lastReviewedAt": "2025-12-20T00:00:00+00:00",
                "dueAt": "2025-12-31T00:00:00+00:00",
            },
        )
    StudyPreferencesService(ctx).update(
        {"daily_new_card_limit": 1, "daily_review_card_limit": 1}
    )

    first_queue = service.daily_queue()
    assert first_queue["queue"]["available"] == {"new": 2, "review": 2}
    assert first_queue["queue"]["shown"] == {"new": 1, "review": 1}
    fresh = next(card for card in first_queue["cards"] if card["repetitions"] == 0)
    review = next(card for card in first_queue["cards"] if card["repetitions"] > 0)
    service.review_card(fresh["item_id"], "good")
    service.review_card(review["item_id"], "good")

    refreshed = service.daily_queue()
    assert refreshed["cards"] == []
    assert refreshed["queue"]["completedToday"] == {"new": 1, "review": 1}
    remaining_fresh = next(card for card in service.list_cards(due_only=True) if card["repetitions"] == 0)
    with pytest.raises(ValueError, match="daily new card limit reached"):
        service.review_card(remaining_fresh["item_id"], "good")

    clock[0] = T0 + timedelta(days=1)
    next_day = service.daily_queue()
    assert len(next_day["cards"]) == 2
    assert next_day["queue"]["completedToday"] == {"new": 0, "review": 0}
