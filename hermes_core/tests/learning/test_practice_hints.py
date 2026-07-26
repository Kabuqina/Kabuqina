# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningConflictError, LearningStore
from learning.output_writer import OutputWriter
from learning.practice_hints import (
    MAX_HINT_REQUESTS_PER_ITEM,
    PRACTICE_HINT_ACTIVITY,
    PracticeHintService,
)
from learning.quizzes import QuizService


OWNER = "owner-A"
SPACE = "s1"


def _seed(db_path, *, activate=True, ladder=None):
    store = LearningStore(db_path=db_path)
    try:
        ctx = LearningExecutionContext(store, owner_id=OWNER)
        ctx.create_space(title="Algebra", space_id=SPACE)
        artifact_id = OutputWriter(ctx).write_artifact(
            kind="quiz",
            title="Hints",
            payload={
                "questions": [
                    {
                        "type": "short_answer",
                        "prompt": "Why?",
                        "answer": "definition",
                        "hint_ladder": ladder
                        or {
                            "schema_version": 1,
                            "direction": "Start from the definition.",
                            "next_step": "Substitute the named quantity.",
                            "scaffold": "Write definition -> substitution -> simplify.",
                            "full_solution": "Apply the definition, substitute, then simplify.",
                        },
                    }
                ]
            },
        )["artifact_id"]
        if activate:
            QuizService(ctx).activate_quiz(artifact_id)
            item_id = QuizService(ctx).list_questions(
                artifact_id=artifact_id
            )[0]["item_id"]
        else:
            item_id = f"{artifact_id}-0000"
        return artifact_id, item_id
    finally:
        store.close()


def _request(artifact_id, item_id, key, level="direction"):
    return {
        "schema_version": 1,
        "artifact_id": artifact_id,
        "item_id": item_id,
        "idempotency_key": key,
        "level": level,
    }


def _service(db_path, *, owner=OWNER):
    store = LearningStore(db_path=db_path)
    ctx = LearningExecutionContext(store, owner_id=owner, space_id=SPACE)
    return store, ctx, PracticeHintService(ctx)


def test_hint_can_jump_directly_to_full_solution_with_zero_provider_cost(tmp_path):
    db_path = tmp_path / "learning.db"
    artifact_id, item_id = _seed(db_path)
    store, _ctx, service = _service(db_path)
    try:
        result = service.request_hint(
            _request(artifact_id, item_id, "hint-1", "full_solution")
        )
    finally:
        store.close()

    assert result["ordinal"] == 1
    assert result["content"].startswith("Apply the definition")
    assert result["budget_summary"] == {
        "provider_attempts": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "wall_ms": 0,
    }


def test_hint_replay_is_idempotent_and_evidence_does_not_store_content(tmp_path):
    db_path = tmp_path / "learning.db"
    artifact_id, item_id = _seed(db_path)
    store, ctx, service = _service(db_path)
    try:
        first = service.request_hint(_request(artifact_id, item_id, "hint-1"))
        replay = service.request_hint(_request(artifact_id, item_id, "hint-1"))
        activities = ctx.list_activities()
    finally:
        store.close()

    assert first["activity_id"] == replay["activity_id"]
    assert first["replayed"] is False
    assert replay["replayed"] is True
    assert len(activities) == 1
    assert activities[0]["activity_type"] == PRACTICE_HINT_ACTIVITY
    assert "Start from" not in str(activities[0]["detail"])
    assert activities[0]["detail"]["provider_attempts"] == 0
    assert activities[0]["detail"]["ordinal"] == 1


def test_same_idempotency_key_with_different_payload_conflicts(tmp_path):
    db_path = tmp_path / "learning.db"
    artifact_id, item_id = _seed(db_path)
    store, ctx, service = _service(db_path)
    try:
        service.request_hint(_request(artifact_id, item_id, "hint-1", "direction"))
        with pytest.raises(LearningConflictError, match="idempotency"):
            service.request_hint(
                _request(artifact_id, item_id, "hint-1", "next_step")
            )
        assert len(ctx.list_activities()) == 1
    finally:
        store.close()


def test_missing_level_draft_and_cross_owner_fail_before_activity(tmp_path):
    missing_path = tmp_path / "missing.db"
    artifact_id, item_id = _seed(
        missing_path,
        ladder={"schema_version": 1, "direction": "Only direction."},
    )
    store, ctx, service = _service(missing_path)
    try:
        with pytest.raises(ValueError, match="hint_unavailable"):
            service.request_hint(
                _request(artifact_id, item_id, "hint-1", "scaffold")
            )
        assert ctx.list_activities() == []
    finally:
        store.close()

    draft_path = tmp_path / "draft.db"
    draft_id, draft_item = _seed(draft_path, activate=False)
    store, ctx, service = _service(draft_path)
    try:
        with pytest.raises(ValueError, match="not active"):
            service.request_hint(_request(draft_id, draft_item, "hint-2"))
        assert ctx.list_activities() == []
    finally:
        store.close()

    store, _ctx, service = _service(missing_path, owner="owner-B")
    try:
        with pytest.raises(KeyError):
            service.request_hint(_request(artifact_id, item_id, "hint-3"))
    finally:
        store.close()


def test_hint_count_cap_allows_replay_but_rejects_ninth_request(tmp_path):
    db_path = tmp_path / "learning.db"
    artifact_id, item_id = _seed(db_path)
    store, ctx, service = _service(db_path)
    try:
        for index in range(MAX_HINT_REQUESTS_PER_ITEM):
            result = service.request_hint(
                _request(artifact_id, item_id, f"hint-{index}")
            )
            assert result["ordinal"] == index + 1
        assert service.request_hint(
            _request(artifact_id, item_id, "hint-0")
        )["replayed"] is True
        with pytest.raises(LearningConflictError, match="limit"):
            service.request_hint(
                _request(artifact_id, item_id, "hint-overflow")
            )
        assert len(ctx.list_activities()) == MAX_HINT_REQUESTS_PER_ITEM
    finally:
        store.close()


def test_concurrent_same_hint_has_one_insert_winner(tmp_path):
    db_path = tmp_path / "learning.db"
    artifact_id, item_id = _seed(db_path)
    request = _request(artifact_id, item_id, "same-request", "next_step")

    def invoke():
        store, _ctx, service = _service(db_path)
        try:
            return service.request_hint(request)
        finally:
            store.close()

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _index: invoke(), range(4)))

    assert len({item["activity_id"] for item in results}) == 1
    assert sum(not item["replayed"] for item in results) == 1
    store, ctx, _service_instance = _service(db_path)
    try:
        assert len(ctx.list_activities()) == 1
    finally:
        store.close()
