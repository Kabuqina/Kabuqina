"""Tests for learning/learning_store.py + learning/learning_context.py.

Covers the isolated ``learning.db`` store (v1 schema reconciliation, WAL, busy
retry, concurrency) and the owner/space isolation guarantees enforced by
``LearningExecutionContext`` — owner is injected by the runtime, never by the
model, and every read/write is constrained by both ``owner_id`` and ``space_id``.

Every test points the store at ``tmp_path`` — never the real Hermes root.
"""

import sqlite3
import threading

import pytest

from learning.learning_contract import ContractError
from learning.learning_store import LearningStore
from learning.learning_context import LearningExecutionContext


V1_TABLES = {
    "learning_spaces",
    "learning_artifacts",
    "learning_items",
    "learning_activities",
    "learning_migrations",
}


def _flashcard_envelope(space_id="s1", title="Deck"):
    return {
        "version": 1,
        "kind": "flashcard_deck",
        "space_id": space_id,
        "title": title,
        "source_refs": [],
        "payload": {"cards": [{"front": "q", "back": "a"}]},
    }


@pytest.fixture()
def store(tmp_path):
    st = LearningStore(db_path=tmp_path / "learning.db")
    yield st
    st.close()


# --------------------------------------------------------------------------- #
# Schema / pragmas
# --------------------------------------------------------------------------- #

def test_fresh_db_reconciles_v1_schema(store, tmp_path):
    raw = sqlite3.connect(str(tmp_path / "learning.db"))
    try:
        names = {
            r[0]
            for r in raw.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        raw.close()
    assert V1_TABLES <= names


def test_wal_mode_enabled(store):
    assert store.journal_mode().lower() == "wal"


def test_startup_reconciles_missing_column(tmp_path):
    # Simulate an older db missing a column; opening the store should ADD it.
    path = tmp_path / "learning.db"
    raw = sqlite3.connect(str(path))
    raw.execute(
        "CREATE TABLE learning_artifacts (owner_id TEXT, space_id TEXT, "
        "artifact_id TEXT, PRIMARY KEY (owner_id, space_id, artifact_id))"
    )
    raw.commit()
    raw.close()

    st = LearningStore(db_path=path)
    try:
        cols = st.table_columns("learning_artifacts")
    finally:
        st.close()
    # A column declared in the v1 schema was reconciled onto the old table.
    assert "status" in cols
    assert "review_status" in cols


# --------------------------------------------------------------------------- #
# Spaces
# --------------------------------------------------------------------------- #

def test_create_and_get_space(store):
    sid = store.create_space("owner-A", title="Algebra")
    space = store.get_space("owner-A", sid)
    assert space is not None
    assert space["title"] == "Algebra"
    assert store.get_current_space("owner-A") == sid


def test_space_is_owner_scoped(store):
    sid = store.create_space("owner-A", title="Algebra")
    assert store.get_space("owner-B", sid) is None
    assert store.list_spaces("owner-B") == []


def test_empty_owner_id_rejected(store):
    with pytest.raises(ValueError):
        store.create_space("", title="x")
    with pytest.raises(ValueError):
        store.get_space("", "s1")


# --------------------------------------------------------------------------- #
# Artifacts — owner/space scoping
# --------------------------------------------------------------------------- #

def test_insert_and_get_artifact(store):
    sid = store.create_space("owner-A", title="Algebra")
    res = store.insert_artifact("owner-A", sid, _flashcard_envelope(space_id=sid))
    assert res["version"] == 1
    got = store.get_artifact("owner-A", sid, res["artifact_id"])
    assert got is not None
    assert got["kind"] == "flashcard_deck"
    assert got["status"] == "draft"  # AI content persisted as draft
    assert got["review"]["status"] == "pending"


def test_cross_owner_read_returns_nothing(store):
    sid = store.create_space("owner-A", title="Algebra")
    res = store.insert_artifact("owner-A", sid, _flashcard_envelope(space_id=sid))
    assert store.get_artifact("owner-B", sid, res["artifact_id"]) is None
    assert store.list_artifacts("owner-B", sid) == []


def test_cross_space_read_returns_nothing(store):
    sid_a = store.create_space("owner-A", title="Algebra")
    sid_b = store.create_space("owner-A", title="Biology")
    res = store.insert_artifact("owner-A", sid_a, _flashcard_envelope(space_id=sid_a))
    assert store.get_artifact("owner-A", sid_b, res["artifact_id"]) is None
    assert store.list_artifacts("owner-A", sid_b) == []


def test_list_artifacts_filters(store):
    sid = store.create_space("owner-A", title="Algebra")
    store.insert_artifact("owner-A", sid, _flashcard_envelope(space_id=sid, title="D1"))
    store.insert_artifact(
        "owner-A",
        sid,
        {
            "version": 1,
            "kind": "quiz",
            "space_id": sid,
            "title": "Q1",
            "source_refs": [],
            "payload": {
                "questions": [{"type": "true_false", "prompt": "?", "answer": True}]
            },
        },
    )
    decks = store.list_artifacts("owner-A", sid, kind="flashcard_deck")
    assert len(decks) == 1 and decks[0]["kind"] == "flashcard_deck"
    drafts = store.list_artifacts("owner-A", sid, status="draft")
    assert len(drafts) == 2


def test_invalid_envelope_rejected(store):
    sid = store.create_space("owner-A", title="Algebra")
    with pytest.raises(ContractError):
        store.insert_artifact(
            "owner-A",
            sid,
            {
                "version": 1,
                "kind": "flashcard_deck",
                "space_id": sid,
                "title": "bad",
                "source_refs": [],
                "payload": {"cards": []},  # empty deck — invalid
            },
        )


def test_model_supplied_owner_in_envelope_ignored(store):
    # A model may smuggle an owner_id into the envelope; the store uses only the
    # scoping argument. Contract ignores unknown keys, store never reads owner.
    sid = store.create_space("owner-A", title="Algebra")
    env = _flashcard_envelope(space_id=sid)
    env["owner_id"] = "attacker"
    res = store.insert_artifact("owner-A", sid, env)
    assert store.get_artifact("owner-A", sid, res["artifact_id"]) is not None
    assert store.list_artifacts("attacker", sid) == []


# --------------------------------------------------------------------------- #
# Artifact lifecycle transitions
# --------------------------------------------------------------------------- #

def test_status_transition_allowed(store):
    sid = store.create_space("owner-A", title="Algebra")
    res = store.insert_artifact("owner-A", sid, _flashcard_envelope(space_id=sid))
    store.update_artifact_status("owner-A", sid, res["artifact_id"], "active")
    assert store.get_artifact("owner-A", sid, res["artifact_id"])["status"] == "active"
    store.update_artifact_status("owner-A", sid, res["artifact_id"], "archived")
    assert store.get_artifact("owner-A", sid, res["artifact_id"])["status"] == "archived"


def test_status_transition_illegal_rejected(store):
    sid = store.create_space("owner-A", title="Algebra")
    res = store.insert_artifact("owner-A", sid, _flashcard_envelope(space_id=sid))
    with pytest.raises(ContractError):
        store.update_artifact_status("owner-A", sid, res["artifact_id"], "archived")


def test_status_update_cross_owner_is_noop(store):
    sid = store.create_space("owner-A", title="Algebra")
    res = store.insert_artifact("owner-A", sid, _flashcard_envelope(space_id=sid))
    with pytest.raises(KeyError):
        store.update_artifact_status("owner-B", sid, res["artifact_id"], "active")
    assert store.get_artifact("owner-A", sid, res["artifact_id"])["status"] == "draft"


# --------------------------------------------------------------------------- #
# Activities + migrations
# --------------------------------------------------------------------------- #

def test_record_and_list_activity_scoped(store):
    sid = store.create_space("owner-A", title="Algebra")
    store.insert_activity(
        "owner-A", sid, activity_type="review", detail={"grade": 5}
    )
    acts = store.list_activities("owner-A", sid)
    assert len(acts) == 1 and acts[0]["activity_type"] == "review"
    assert store.list_activities("owner-B", sid) == []


def test_migration_markers_owner_scoped(store):
    assert store.is_migrated("owner-A", "localStorage:flashcards") is False
    store.mark_migration("owner-A", "localStorage:flashcards", detail={"n": 3})
    assert store.is_migrated("owner-A", "localStorage:flashcards") is True
    assert store.is_migrated("owner-B", "localStorage:flashcards") is False


# --------------------------------------------------------------------------- #
# Concurrency (WAL + busy-retry) with owner isolation — Step 3
# --------------------------------------------------------------------------- #

def test_concurrent_writers_stay_isolated(tmp_path):
    path = tmp_path / "learning.db"
    per_owner = 25
    owners = ["gateway:discord:hashA", "desktop:local"]
    errors = []

    def worker(owner_id):
        # Each worker owns its own connection — the web-child / gateway-child
        # shape (separate processes sharing one learning.db). Construction is
        # inside the try so concurrent first-time schema-init errors surface too.
        st = None
        try:
            st = LearningStore(db_path=path)
            sid = st.create_space(owner_id, title="Course", space_id=f"space-{owner_id}")
            for i in range(per_owner):
                st.insert_artifact(
                    owner_id, sid, _flashcard_envelope(space_id=sid, title=f"D{i}")
                )
        except Exception as exc:  # noqa: BLE001 — surface to assertion
            errors.append(exc)
        finally:
            if st is not None:
                st.close()

    threads = [threading.Thread(target=worker, args=(o,)) for o in owners]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"concurrent writers raised: {errors}"

    verify = LearningStore(db_path=path)
    try:
        for owner_id in owners:
            sid = f"space-{owner_id}"
            mine = verify.list_artifacts(owner_id, sid)
            assert len(mine) == per_owner
            # No cross-owner bleed: the other owner's space is invisible.
            for other in owners:
                if other != owner_id:
                    assert verify.list_artifacts(owner_id, f"space-{other}") == []
    finally:
        verify.close()


# --------------------------------------------------------------------------- #
# LearningExecutionContext — owner injection is the only owner source
# --------------------------------------------------------------------------- #

def test_context_requires_owner(store):
    with pytest.raises(ValueError):
        LearningExecutionContext(store, owner_id="")


def test_context_owner_is_read_only(store):
    ctx = LearningExecutionContext(store, owner_id="owner-A")
    assert ctx.owner_id == "owner-A"
    with pytest.raises(AttributeError):
        ctx.owner_id = "owner-B"  # type: ignore[misc]


def test_context_put_artifact_writes_draft_under_context_owner(store):
    ctx = LearningExecutionContext(store, owner_id="owner-A")
    ctx.create_space(title="Algebra")
    res = ctx.put_artifact(
        kind="flashcard_deck",
        title="Chapter 1",
        payload={"cards": [{"front": "q", "back": "a"}]},
    )
    got = ctx.get_artifact(res["artifact_id"])
    assert got["status"] == "draft"
    assert got["space_id"] == ctx.space_id


def test_context_ignores_model_supplied_owner_and_space(store):
    ctx = LearningExecutionContext(store, owner_id="owner-A")
    ctx.create_space(title="Algebra", space_id="real-space")
    res = ctx.put_artifact(
        kind="flashcard_deck",
        title="Chapter 1",
        payload={"cards": [{"front": "q", "back": "a"}]},
        owner_id="attacker",        # model-supplied — must be ignored
        space_id="other-space",     # model-supplied — must be ignored
    )
    # Stored under the context's identity, not the model's.
    got = ctx.get_artifact(res["artifact_id"])
    assert got is not None
    assert got["space_id"] == "real-space"
    # The attacker owner sees nothing.
    attacker = LearningExecutionContext(store, owner_id="attacker", space_id="real-space")
    assert attacker.get_artifact(res["artifact_id"]) is None


def test_context_artifact_ops_require_selected_space(store):
    ctx = LearningExecutionContext(store, owner_id="owner-A")
    with pytest.raises(ValueError):
        ctx.put_artifact(
            kind="flashcard_deck",
            title="x",
            payload={"cards": [{"front": "q", "back": "a"}]},
        )


def test_two_contexts_different_owners_isolated(store):
    # web-child / gateway-child shape over one store.
    web = LearningExecutionContext(store, owner_id="desktop:local")
    web.create_space(title="Algebra", space_id="shared-name")
    web.put_artifact(
        kind="flashcard_deck",
        title="Web deck",
        payload={"cards": [{"front": "q", "back": "a"}]},
    )
    gw = LearningExecutionContext(store, owner_id="gateway:discord:hashA")
    gw.create_space(title="Algebra", space_id="shared-name")
    # Same space *name*, different owner → fully isolated content.
    assert gw.list_artifacts() == []
    assert len(web.list_artifacts()) == 1
