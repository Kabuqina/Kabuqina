"""Tests for learning/learning_index.py — the Learning Index skeleton.

The index is a deterministic, read-only, size-bounded snapshot of one course
space: it includes only ``active`` artifacts (as lightweight references, never
full payloads) plus allowed direct activities, excludes draft/rejected/archived
(unreviewed content is never treated as course fact), never calls an LLM, and
never mutates the store.
"""

import copy
import json

import pytest

from learning.learning_store import LearningStore
from learning.learning_context import LearningExecutionContext
from learning.output_writer import OutputWriter
from learning.learning_index import LearningIndex, INDEX_VERSION


def _cards():
    return {"cards": [{"front": "q", "back": "a"}]}


@pytest.fixture()
def env(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    ctx = LearningExecutionContext(store, owner_id="owner-A")
    ctx.create_space(title="Algebra", space_id="s1")
    writer = OutputWriter(ctx)
    yield store, ctx, writer
    store.close()


def _write_active(writer, ctx, title="D"):
    res = writer.write_artifact(kind="flashcard_deck", title=title, payload=_cards())
    ctx.set_artifact_status(res["artifact_id"], "active")
    return res["artifact_id"]


# --------------------------------------------------------------------------- #
# Inclusion / exclusion by lifecycle status
# --------------------------------------------------------------------------- #

def test_index_includes_only_active_artifacts(env):
    store, ctx, writer = env
    active_id = _write_active(writer, ctx, "active-deck")
    writer.write_artifact(kind="flashcard_deck", title="draft-deck", payload=_cards())

    snap = LearningIndex(ctx).build()
    ids = [a["artifact_id"] for a in snap["artifacts"]]
    assert ids == [active_id]


def test_index_excludes_rejected_and_archived(env):
    store, ctx, writer = env
    # rejected
    r = writer.write_artifact(kind="flashcard_deck", title="r", payload=_cards())
    ctx.set_artifact_status(r["artifact_id"], "rejected")
    # archived (via active)
    a = writer.write_artifact(kind="flashcard_deck", title="a", payload=_cards())
    ctx.set_artifact_status(a["artifact_id"], "active")
    ctx.set_artifact_status(a["artifact_id"], "archived")

    snap = LearningIndex(ctx).build()
    assert snap["artifacts"] == []


def test_index_artifacts_are_lightweight_references(env):
    store, ctx, writer = env
    _write_active(writer, ctx)
    art = LearningIndex(ctx).build()["artifacts"][0]
    assert set(art) >= {"artifact_id", "kind", "title", "version", "review"}
    # No full payload/envelope in the index — it carries references only.
    assert "payload" not in art
    assert "envelope" not in art


def test_index_includes_activities(env):
    store, ctx, writer = env
    ctx.record_activity(activity_type="review", detail={"grade": 5})
    snap = LearningIndex(ctx).build()
    assert len(snap["activities"]) == 1
    assert snap["activities"][0]["activity_type"] == "review"
    # Activities are lightweight too.
    assert "detail" not in snap["activities"][0]


# --------------------------------------------------------------------------- #
# Versioning / shape / placeholders
# --------------------------------------------------------------------------- #

def test_index_is_versioned_and_scoped(env):
    store, ctx, writer = env
    snap = LearningIndex(ctx).build()
    assert snap["index_version"] == INDEX_VERSION
    assert snap["space_id"] == "s1"


def test_index_has_placeholders(env):
    store, ctx, writer = env
    snap = LearningIndex(ctx).build()
    assert snap["due_reviews"] == []
    assert snap["weak_points"] == []


def test_index_requires_selected_space(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    try:
        ctx = LearningExecutionContext(store, owner_id="owner-A")  # no space
        with pytest.raises(ValueError):
            LearningIndex(ctx).build()
    finally:
        store.close()


# --------------------------------------------------------------------------- #
# Determinism + read-only
# --------------------------------------------------------------------------- #

def test_index_is_deterministic(env):
    store, ctx, writer = env
    _write_active(writer, ctx, "d1")
    _write_active(writer, ctx, "d2")
    ctx.record_activity(activity_type="review")
    first = LearningIndex(ctx).build()
    second = LearningIndex(ctx).build()
    assert first == second


def test_build_does_not_mutate_store(env):
    store, ctx, writer = env
    _write_active(writer, ctx, "d1")
    writer.write_artifact(kind="flashcard_deck", title="draft", payload=_cards())
    before = copy.deepcopy(store.list_artifacts("owner-A", "s1"))
    before_acts = copy.deepcopy(store.list_activities("owner-A", "s1"))

    LearningIndex(ctx).build()

    assert store.list_artifacts("owner-A", "s1") == before
    assert store.list_activities("owner-A", "s1") == before_acts


def test_index_is_owner_scoped(env):
    store, ctx, writer = env
    _write_active(writer, ctx)
    other = LearningExecutionContext(store, owner_id="owner-B", space_id="s1")
    snap = LearningIndex(other).build()
    assert snap["artifacts"] == []


# --------------------------------------------------------------------------- #
# Size bounding
# --------------------------------------------------------------------------- #

def test_index_count_capped_and_flagged(env):
    store, ctx, writer = env
    for i in range(5):
        _write_active(writer, ctx, f"d{i}")
    snap = LearningIndex(ctx).build(max_artifacts=3)
    assert len(snap["artifacts"]) == 3
    assert snap["truncated"] is True


def test_index_byte_cap_trims_lists(env):
    store, ctx, writer = env
    _write_active(writer, ctx, "d1")
    ctx.record_activity(activity_type="review")
    # A tiny byte cap forces the reference lists to be emptied while the base
    # snapshot structure survives.
    snap = LearningIndex(ctx).build(max_bytes=10)
    assert snap["artifacts"] == []
    assert snap["activities"] == []
    assert snap["truncated"] is True


def test_index_not_truncated_when_within_caps(env):
    store, ctx, writer = env
    _write_active(writer, ctx)
    snap = LearningIndex(ctx).build()
    assert snap["truncated"] is False
    # Snapshot is JSON-serializable (a real snapshot for a planner to consume).
    json.dumps(snap)


# --------------------------------------------------------------------------- #
# M4 projections
# --------------------------------------------------------------------------- #

def test_index_projects_active_state_evaluations_plan_and_due_cards(env):
    from datetime import datetime, timezone

    from learning.evaluations import EvaluationService
    from learning.flashcards import FlashcardService
    from learning.learning_plans import LearningPlanService
    from learning.student_state import StudentStateService

    store, ctx, writer = env
    StudentStateService(ctx).save_state(
        {"course": "Algebra", "goals": ["Midterm"]}
    )
    evaluation_id = writer.write_artifact(
        kind="evaluation",
        title="Eval",
        payload={"observations": ["Missed primes"], "weak_points": ["Prime numbers"]},
    )["artifact_id"]
    EvaluationService(ctx).activate_evaluation(evaluation_id)
    plan_id = writer.write_artifact(
        kind="learning_plan",
        title="Plan",
        payload={"phases": [{"title": "P1", "tasks": [{"title": "Drill", "order": 1}]}]},
    )["artifact_id"]
    LearningPlanService(ctx).activate_plan(plan_id)
    FlashcardService(
        ctx, now=lambda: datetime(2020, 1, 1, tzinfo=timezone.utc)
    ).capture_card(front="Prime", back="Divisible only by one and itself")

    snap = LearningIndex(ctx).build()

    assert snap["student_state"]["course"] == "Algebra"
    assert snap["evaluations"][0]["weak_points"] == ["Prime numbers"]
    assert snap["current_plan"]["artifact_id"] == plan_id
    assert snap["current_plan"]["items"][0]["title"] == "Drill"
    assert snap["weak_points"] == ["Prime numbers"]
    assert len(snap["due_reviews"]) == 1
    assert "front" not in snap["due_reviews"][0]


def test_index_excludes_draft_m4_artifacts(env):
    store, ctx, writer = env
    writer.write_artifact(
        kind="student_state", title="Draft state", payload={"course": "Draft"}
    )
    writer.write_artifact(
        kind="evaluation",
        title="Draft eval",
        payload={"observations": ["Not active"], "weak_points": ["draft"]},
    )
    writer.write_artifact(
        kind="learning_plan",
        title="Draft plan",
        payload={"phases": [{"title": "P", "tasks": [{"title": "Hidden"}]}]},
    )

    snap = LearningIndex(ctx).build()

    assert snap["student_state"] == {}
    assert snap["evaluations"] == []
    assert snap["current_plan"] is None
    assert snap["weak_points"] == []


def test_index_deduplicates_evaluation_and_quiz_weak_points(env):
    from learning.evaluations import EvaluationService

    store, ctx, writer = env
    evaluation_id = writer.write_artifact(
        kind="evaluation",
        title="Eval",
        payload={"observations": ["x"], "weak_points": ["Prime", "Fractions"]},
    )["artifact_id"]
    EvaluationService(ctx).activate_evaluation(evaluation_id)
    ctx.record_activity(
        activity_type="quiz.attempt",
        detail={
            "score": 1,
            "maxScore": 2,
            "percent": 50,
            "weakTags": ["prime", "Factoring"],
            "perQuestion": [{"prompt": "must not leak"}],
        },
    )

    snap = LearningIndex(ctx).build()

    assert snap["weak_points"] == ["Prime", "Fractions", "Factoring"]
    assert snap["activities"][0]["summary"] == {
        "score": 1,
        "maxScore": 2,
        "percent": 50,
        "weakTags": ["prime", "Factoring"],
    }
    assert "perQuestion" not in snap["activities"][0]["summary"]


def test_index_m4_payloads_are_trimmed_under_realistic_byte_cap(env):
    from learning.student_state import StudentStateService

    store, ctx, writer = env
    StudentStateService(ctx).save_state(
        {
            "course": "A" * 800,
            "goals": [f"goal-{index}-" + "x" * 200 for index in range(24)],
            "progress_notes": ["y" * 400 for _ in range(24)],
        }
    )

    snap = LearningIndex(ctx).build(max_bytes=2_048)

    assert len(json.dumps(snap, ensure_ascii=False).encode("utf-8")) <= 2_048
    assert snap["truncated"] is True
