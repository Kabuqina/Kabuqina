from __future__ import annotations

from datetime import datetime, timezone

from cron.scheduler import _study_review_due_count
from learning.flashcards import FlashcardService
from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningStore
from learning.operation_coordinator import (
    LearningOperationCoordinator,
    LearningOperationInProgressError,
)
import pytest


def test_due_count_is_owner_scoped_across_spaces(tmp_path, monkeypatch):
    db_path = tmp_path / "learning.db"
    store = LearningStore(db_path=db_path)
    try:
        for owner_id, card_count in (("owner-A", 2), ("owner-B", 1)):
            for space_index in range(card_count):
                ctx = LearningExecutionContext(store, owner_id=owner_id)
                ctx.create_space(
                    title=f"Course {space_index}",
                    space_id=f"s{space_index}",
                )
                FlashcardService(
                    ctx, now=lambda: datetime(2020, 1, 1, tzinfo=timezone.utc)
                ).capture_card(front=f"Q-{owner_id}-{space_index}", back="A")
    finally:
        store.close()

    monkeypatch.setattr(
        "learning.learning_store.default_learning_db_path", lambda: db_path
    )
    assert _study_review_due_count({"owner_id": "owner-A"}) == 2
    assert _study_review_due_count({"owner_id": "owner-B"}) == 1


def test_cron_production_constructor_obeys_shared_owner_fence(tmp_path, monkeypatch):
    db_path = tmp_path / "learning.db"
    monkeypatch.setattr(
        "learning.learning_store.default_learning_db_path", lambda: db_path
    )
    coordinator = LearningOperationCoordinator.from_learning_db_path(db_path)
    lease = coordinator.begin_operation("owner-A", "", "delete")
    try:
        with pytest.raises(LearningOperationInProgressError):
            _study_review_due_count({"owner_id": "owner-A"})
    finally:
        coordinator.finish_operation(lease)
