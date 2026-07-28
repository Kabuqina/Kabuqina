from __future__ import annotations

import pytest

from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningStore
from learning.study_preferences import (
    DEFAULT_STUDY_PREFERENCES,
    StudyPreferencesService,
    resolve_import_read_mode,
)


def test_preferences_default_without_writing_a_row(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    try:
        ctx = LearningExecutionContext(store, "owner-A")
        assert StudyPreferencesService(ctx).get() == DEFAULT_STUDY_PREFERENCES
        assert store.get_study_preferences("owner-A") is None
    finally:
        store.close()


def test_preferences_persist_and_roundtrip_in_owner_bundle(tmp_path):
    source = LearningStore(db_path=tmp_path / "source.db")
    target = LearningStore(db_path=tmp_path / "target.db")
    try:
        source_ctx = LearningExecutionContext(source, "owner-A")
        updated = StudyPreferencesService(source_ctx).update(
            {
                "import_read_mode": "precise",
                "daily_new_card_limit": 12,
                "daily_review_card_limit": 80,
            }
        )
        assert updated["import_read_mode"] == "precise"
        bundle = source.export_owner_bundle("owner-A")
        assert bundle["preferences"][0]["daily_new_card_limit"] == 12

        counts = target.import_owner_bundle("owner-B", bundle)
        assert counts["preferences"] == 1
        target_ctx = LearningExecutionContext(target, "owner-B")
        assert StudyPreferencesService(target_ctx).get() == updated
    finally:
        source.close()
        target.close()


@pytest.mark.parametrize(
    ("preferred", "requested", "override", "effective", "limited"),
    [
        ("auto", None, False, "auto", False),
        ("auto", "math", False, "auto", True),
        ("precise", "math", False, "precise", True),
        ("math", "precise", False, "precise", False),
        ("auto", "math", True, "math", False),
    ],
)
def test_import_read_mode_is_a_default_and_hard_cap(
    preferred, requested, override, effective, limited
):
    result = resolve_import_read_mode(preferred, requested, override=override)
    assert result["effective_mode"] == effective
    assert result["limited"] is limited


def test_preference_validation_rejects_unbounded_or_unknown_values(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    try:
        service = StudyPreferencesService(LearningExecutionContext(store, "owner-A"))
        with pytest.raises(ValueError, match="0..100"):
            service.update({"daily_new_card_limit": 101})
        with pytest.raises(ValueError, match="unknown study preference"):
            service.update({"streak_goal": 7})
    finally:
        store.close()
