"""Contracts for the course-less Study scratch notebook (B-12)."""

from __future__ import annotations

import sqlite3

import pytest

from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningStore
from learning.scratch_notebook import ensure_scratch_notebook


def test_old_spaces_reconcile_to_course_kind(tmp_path):
    path = tmp_path / "learning.db"
    raw = sqlite3.connect(path)
    raw.execute(
        "CREATE TABLE learning_spaces ("
        "owner_id TEXT NOT NULL, space_id TEXT NOT NULL, title TEXT NOT NULL DEFAULT '', "
        "status TEXT NOT NULL DEFAULT 'active', is_current INTEGER NOT NULL DEFAULT 0, "
        "created_at TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT '', "
        "PRIMARY KEY(owner_id, space_id))"
    )
    raw.execute(
        "INSERT INTO learning_spaces VALUES (?,?,?,?,?,?,?)",
        ("owner", "course", "Course", "active", 1, "now", "now"),
    )
    raw.commit()
    raw.close()

    store = LearningStore(db_path=path)
    try:
        assert store.get_space("owner", "course")["kind"] == "course"
    finally:
        store.close()


def test_seed_is_idempotent_and_does_not_steal_current_course(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    try:
        ctx = LearningExecutionContext(store, "owner")
        ctx.create_space(title="Course", space_id="course")

        first = ensure_scratch_notebook(ctx)
        second = ensure_scratch_notebook(ctx)

        assert first["space_id"] == second["space_id"]
        assert first["kind"] == "scratch"
        assert ctx.current_space() == "course"
        assert [space["kind"] for space in ctx.list_spaces()] == ["course", "scratch"]
    finally:
        store.close()


def test_pad_and_notes_return_no_task_metrics(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    try:
        ctx = LearningExecutionContext(store, "owner")
        scratch = ensure_scratch_notebook(ctx)["space_id"]
        ctx.save_scratch_pad(scratch, "一页随手写")
        ctx.add_scratch_note(
            scratch, text="等号表示两个写法指向同一个东西。", origin="来自对话", note_id="note-1"
        )

        page = ctx.get_scratch_page(scratch)
        assert page["pad"] == "一页随手写"
        assert page["notes"] == [
            {
                "id": "note-1",
                "text": "等号表示两个写法指向同一个东西。",
                "origin": "来自对话",
                "createdAt": page["notes"][0]["createdAt"],
            }
        ]
        assert not ({"count", "pending", "unfiled"} & set(page))
    finally:
        store.close()


def test_filing_is_atomic_and_creates_a_course_draft(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    try:
        ctx = LearningExecutionContext(store, "owner")
        ctx.create_space(title="Course", space_id="course")
        scratch = ensure_scratch_notebook(ctx)["space_id"]
        ctx.add_scratch_note(
            scratch, text="极限描述趋近过程。", origin="来自对话", note_id="note-1"
        )

        filed = ctx.file_scratch_note(scratch, "note-1", "course")

        assert filed["status"] == "draft"
        assert ctx.get_scratch_page(scratch)["notes"] == []
        artifact = store.get_artifact("owner", "course", filed["artifact_id"])
        assert artifact is not None
        assert artifact["kind"] == "knowledge_base"
        assert artifact["status"] == "draft"
        assert artifact["review"] == {"mode": "semantic", "status": "pending"}
    finally:
        store.close()


def test_scratch_space_and_page_round_trip_in_owner_bundle(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    try:
        source = LearningExecutionContext(store, "source")
        source.create_space(title="Course", space_id="course")
        scratch = ensure_scratch_notebook(source)["space_id"]
        source.save_scratch_pad(scratch, "保留这页")
        source.add_scratch_note(
            scratch, text="保留这条", origin="来自对话", note_id="note-1"
        )

        bundle = source.export_owner_bundle()
        target = LearningExecutionContext(store, "target")
        target.import_owner_bundle(bundle)

        restored_scratch = next(
            space for space in target.list_spaces() if space["kind"] == "scratch"
        )
        assert restored_scratch["is_current"] == 0
        assert target.get_scratch_page(restored_scratch["space_id"])["pad"] == "保留这页"
        assert target.get_scratch_page(restored_scratch["space_id"])["notes"][0]["text"] == "保留这条"
    finally:
        store.close()


def test_failed_filing_keeps_the_source_note(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    try:
        ctx = LearningExecutionContext(store, "owner")
        scratch = ensure_scratch_notebook(ctx)["space_id"]
        ctx.add_scratch_note(scratch, text="留在这里", origin="来自对话", note_id="note-1")

        with pytest.raises(KeyError):
            ctx.file_scratch_note(scratch, "note-1", "missing-course")

        assert [note["id"] for note in ctx.get_scratch_page(scratch)["notes"]] == ["note-1"]
    finally:
        store.close()
