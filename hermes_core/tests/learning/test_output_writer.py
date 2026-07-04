"""Tests for learning/output_writer.py — the Output Writer skeleton.

The Output Writer turns AI-authored content into validated ``draft`` artifacts
(owner injected by the context, never the model), enforces lifecycle transitions
for trusted callers, records real user *activities* directly (not disguised as AI
artifacts), and emits an in-process ``learning.output.created`` signal on each
successful artifact write. No LLM calls happen here.
"""

import pytest

from learning.learning_contract import ContractError
from learning.learning_store import LearningStore
from learning.learning_context import LearningExecutionContext
from learning.output_writer import OutputWriter, SIGNAL_OUTPUT_CREATED


def _cards():
    return {"cards": [{"front": "q", "back": "a"}]}


@pytest.fixture()
def env(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    ctx = LearningExecutionContext(store, owner_id="owner-A")
    ctx.create_space(title="Algebra", space_id="s1")
    signals = []
    writer = OutputWriter(ctx, on_created=signals.append)
    yield writer, ctx, signals
    store.close()


# --------------------------------------------------------------------------- #
# Draft persistence + return shape
# --------------------------------------------------------------------------- #

def test_write_persists_draft_and_returns_id_version(env):
    writer, ctx, _ = env
    res = writer.write_artifact(
        kind="flashcard_deck", title="Chapter 1", payload=_cards()
    )
    assert res["artifact_id"] and res["version"] == 1
    got = ctx.get_artifact(res["artifact_id"])
    assert got["status"] == "draft"


def test_write_emits_created_signal_shape(env):
    writer, ctx, signals = env
    res = writer.write_artifact(
        kind="flashcard_deck", title="Chapter 1", payload=_cards()
    )
    assert len(signals) == 1
    sig = signals[0]
    assert sig["event"] == SIGNAL_OUTPUT_CREATED
    assert sig["owner_id"] == "owner-A"
    assert sig["space_id"] == "s1"
    assert sig["artifact_id"] == res["artifact_id"]
    assert sig["kind"] == "flashcard_deck"
    assert sig["version"] == 1
    assert sig["status"] == "draft"


def test_multiple_writes_emit_distinct_signals(env):
    writer, _, signals = env
    a = writer.write_artifact(kind="flashcard_deck", title="D1", payload=_cards())
    b = writer.write_artifact(kind="flashcard_deck", title="D2", payload=_cards())
    assert len(signals) == 2
    assert a["artifact_id"] != b["artifact_id"]
    assert {s["artifact_id"] for s in signals} == {a["artifact_id"], b["artifact_id"]}


def test_write_forces_review_status_pending(env):
    # A model tool must not be able to ship its own content as already-reviewed.
    writer, ctx, _ = env
    res = writer.write_artifact(
        kind="flashcard_deck",
        title="Chapter 1",
        payload=_cards(),
        review={"mode": "deterministic", "status": "passed"},
    )
    got = ctx.get_artifact(res["artifact_id"])
    assert got["review"]["status"] == "pending"
    assert got["review"]["mode"] == "deterministic"  # requested mode preserved


# --------------------------------------------------------------------------- #
# Validation — reject + no signal
# --------------------------------------------------------------------------- #

def test_unknown_kind_rejected_no_signal(env):
    writer, _, signals = env
    with pytest.raises(ContractError):
        writer.write_artifact(kind="space_diagram", title="x", payload={})
    assert signals == []


def test_bad_payload_rejected_no_signal(env):
    writer, _, signals = env
    with pytest.raises(ContractError):
        writer.write_artifact(
            kind="flashcard_deck", title="x", payload={"cards": []}
        )
    assert signals == []


def test_oversize_rejected_no_signal(env):
    writer, _, signals = env
    huge = {"cards": [{"front": "a", "back": "b" * 2000} for _ in range(2000)]}
    with pytest.raises(ContractError):
        writer.write_artifact(kind="flashcard_deck", title="x", payload=huge)
    assert signals == []


# --------------------------------------------------------------------------- #
# Owner injection
# --------------------------------------------------------------------------- #

def test_model_supplied_owner_rejected(env):
    writer, ctx, _ = env
    res = writer.write_artifact(
        kind="flashcard_deck",
        title="Chapter 1",
        payload=_cards(),
        owner_id="attacker",  # ignored
    )
    assert ctx.get_artifact(res["artifact_id"]) is not None
    attacker = LearningExecutionContext(
        ctx._store, owner_id="attacker", space_id="s1"
    )
    assert attacker.get_artifact(res["artifact_id"]) is None


def test_write_requires_selected_space(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    try:
        ctx = LearningExecutionContext(store, owner_id="owner-A")  # no space
        writer = OutputWriter(ctx)
        with pytest.raises(ValueError):
            writer.write_artifact(kind="flashcard_deck", title="x", payload=_cards())
    finally:
        store.close()


# --------------------------------------------------------------------------- #
# Lifecycle transitions (trusted caller)
# --------------------------------------------------------------------------- #

def test_transition_allowed(env):
    writer, ctx, _ = env
    res = writer.write_artifact(kind="flashcard_deck", title="D", payload=_cards())
    writer.transition_artifact(res["artifact_id"], "active")
    assert ctx.get_artifact(res["artifact_id"])["status"] == "active"


def test_transition_illegal_rejected(env):
    writer, ctx, _ = env
    res = writer.write_artifact(kind="flashcard_deck", title="D", payload=_cards())
    with pytest.raises(ContractError):
        writer.transition_artifact(res["artifact_id"], "archived")  # must go active first
    assert ctx.get_artifact(res["artifact_id"])["status"] == "draft"


# --------------------------------------------------------------------------- #
# Real user activity — direct, not an AI artifact, no created signal
# --------------------------------------------------------------------------- #

def test_record_activity_writes_direct_no_artifact_no_signal(env):
    writer, ctx, signals = env
    activity_id = writer.record_activity(
        activity_type="review", detail={"grade": 5}
    )
    assert activity_id
    acts = ctx.list_activities()
    assert len(acts) == 1 and acts[0]["activity_type"] == "review"
    # A user activity is not an artifact and emits no output-created signal.
    assert ctx.list_artifacts() == []
    assert signals == []
