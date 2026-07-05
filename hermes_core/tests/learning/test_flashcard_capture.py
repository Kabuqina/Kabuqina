"""Tests for trusted kq-kp single-card capture into learning.db."""

from datetime import datetime, timezone

import pytest

from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningStore


FIXED_NOW = datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def store(tmp_path):
    st = LearningStore(db_path=tmp_path / "learning.db")
    yield st
    st.close()


@pytest.fixture()
def ctx(store):
    c = LearningExecutionContext(store, owner_id="owner-A")
    c.create_space(title="Algebra", space_id="s1")
    return c


def test_capture_creates_active_single_card_artifact_and_item(ctx):
    from learning.flashcards import FlashcardService

    service = FlashcardService(ctx, now=lambda: FIXED_NOW)
    result = service.capture_card(
        front=" Bayes theorem ",
        back="Posterior = prior x likelihood / evidence.",
        hint="Formula shape",
        tags=["Knowledge point", "Knowledge point", "Bayes"],
        source_refs=[
            {
                "origin": "kq-kp",
                "session_id": "session-1",
                "confidence": "confirmed",
                "gist": "Posterior formula",
            }
        ],
    )

    assert result["duplicate"] is False
    assert result["artifact_id"]
    assert result["item_id"] == f"{result['artifact_id']}-0000"
    assert result["front"] == "Bayes theorem"
    assert result["dueAt"] == FIXED_NOW.isoformat()

    artifact = ctx.get_artifact(result["artifact_id"])
    assert artifact["status"] == "active"
    assert artifact["envelope"]["kind"] == "flashcard_deck"
    assert artifact["envelope"]["source_refs"][0]["origin"] == "kq-kp"

    cards = service.list_cards()
    assert len(cards) == 1
    assert cards[0]["item_id"] == result["item_id"]
    assert cards[0]["artifact_id"] == result["artifact_id"]
    assert cards[0]["front"] == "Bayes theorem"
    assert cards[0]["back"] == "Posterior = prior x likelihood / evidence."
    assert cards[0]["hint"] == "Formula shape"
    assert cards[0]["tags"] == ["Knowledge point", "Bayes"]
    assert cards[0]["ease"] == 2.5
    assert cards[0]["intervalDays"] == 0
    assert cards[0]["repetitions"] == 0
    assert cards[0]["lapses"] == 0
    assert cards[0]["createdAt"] == FIXED_NOW.isoformat()
    assert cards[0]["dueAt"] == FIXED_NOW.isoformat()
    assert cards[0]["lastReviewedAt"] == ""


def test_capture_duplicate_front_is_idempotent(ctx):
    from learning.flashcards import FlashcardService

    service = FlashcardService(ctx, now=lambda: FIXED_NOW)
    first = service.capture_card(front=" Bayes ", back="First")
    second = service.capture_card(front="bayes", back="Second")

    assert second == {"duplicate": True, "item_id": first["item_id"]}
    assert len(service.list_cards()) == 1
    assert len(ctx.list_artifacts(kind="flashcard_deck")) == 1


def test_capture_enforces_space_card_cap(ctx, monkeypatch):
    import learning.flashcards as flashcards
    from learning.flashcards import FlashcardService

    monkeypatch.setattr(flashcards, "FLASHCARD_SPACE_CAP", 1)
    service = FlashcardService(ctx, now=lambda: FIXED_NOW)
    service.capture_card(front="One", back="A")

    with pytest.raises(ValueError, match="flashcard space cap"):
        service.capture_card(front="Two", back="B")


def test_capture_records_activity_with_origin_and_confidence(ctx):
    from learning.flashcards import FLASHCARD_CAPTURE_ACTIVITY, FlashcardService

    service = FlashcardService(ctx, now=lambda: FIXED_NOW)
    result = service.capture_card(
        front="Gradient",
        back="Direction of steepest increase.",
        source_refs=[{"origin": "kq-kp", "confidence": "inferred"}],
    )

    activities = ctx.list_activities()
    assert len(activities) == 1
    assert activities[0]["activity_type"] == FLASHCARD_CAPTURE_ACTIVITY
    assert activities[0]["artifact_id"] == result["artifact_id"]
    assert activities[0]["item_id"] == result["item_id"]
    assert activities[0]["detail"] == {"origin": "kq-kp", "confidence": "inferred"}


def test_capture_is_owner_and_space_isolated(store):
    from learning.flashcards import FlashcardService

    ctx_a = LearningExecutionContext(store, owner_id="owner-A")
    ctx_a.create_space(title="Course", space_id="shared")
    ctx_b = LearningExecutionContext(store, owner_id="owner-B")
    ctx_b.create_space(title="Course", space_id="shared")

    service_a = FlashcardService(ctx_a, now=lambda: FIXED_NOW)
    service_b = FlashcardService(ctx_b, now=lambda: FIXED_NOW)
    first = service_a.capture_card(front="Bayes", back="A")

    assert service_b.list_cards() == []
    second = service_b.capture_card(front="bayes", back="B")
    assert second["duplicate"] is False
    assert second["item_id"] != first["item_id"]
    assert len(service_a.list_cards()) == 1
    assert len(service_b.list_cards()) == 1


@pytest.mark.parametrize(
    ("front", "back"),
    [("", "answer"), ("question", ""), ("   ", "answer"), ("question", "   ")],
)
def test_capture_requires_front_and_back(ctx, front, back):
    from learning.flashcards import FlashcardService

    service = FlashcardService(ctx, now=lambda: FIXED_NOW)
    with pytest.raises(ValueError, match="front and back"):
        service.capture_card(front=front, back=back)
