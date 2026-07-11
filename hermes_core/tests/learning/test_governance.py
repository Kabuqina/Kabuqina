from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningStore
from learning.output_writer import OutputWriter

def test_owner_bundle_roundtrip_and_complete_delete(tmp_path):
    db = tmp_path / "learning.db"
    store = LearningStore(db_path=db)
    try:
        source = LearningExecutionContext(store, "source")
        source.create_space(title="Course", space_id="s")
        artifact_id = OutputWriter(source).write_artifact(
            kind="tutoring_note", title="Note", payload={"goal":"g", "hints":["h"]}
        )["artifact_id"]
        source.record_activity(activity_type="note.open", artifact_id=artifact_id, detail={"count":1})
        source.mark_migration("legacy:test", detail={"sample":"ok"})
        bundle = source.export_owner_bundle()
        assert "owner_id" not in str(bundle)

        target = LearningExecutionContext(store, "target")
        imported = target.import_owner_bundle(bundle)
        assert imported == {"spaces":1,"artifacts":1,"items":0,"activities":1,"migrations":1}
        target.select_space("s")
        assert target.get_artifact(artifact_id)["title"] == "Note"
        assert target.list_activities()[0]["activity_type"] == "note.open"

        deleted = target.delete_all_learning_data()
        assert deleted["learning_spaces"] == 1
        assert store.list_spaces("target") == []
        assert store.list_migrations("target") == []
    finally:
        store.close()

def test_import_refuses_to_overwrite_existing_owner(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    try:
        ctx = LearningExecutionContext(store, "owner")
        ctx.create_space(title="Existing", space_id="s")
        try:
            ctx.import_owner_bundle({"version":1,"spaces":[]})
            assert False
        except ValueError as exc:
            assert "already has" in str(exc)
    finally:
        store.close()

def test_import_is_atomic_and_rejects_orphan_references(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    try:
        ctx = LearningExecutionContext(store, "owner")
        bundle = {
            "version": 1,
            "spaces": [{"space_id": "s", "title": "Course", "is_current": 1}],
            "items": [{
                "space_id": "s",
                "item_id": "i",
                "artifact_id": "missing",
                "item_type": "flashcard",
                "state": {},
            }],
        }
        try:
            ctx.import_owner_bundle(bundle)
            assert False
        except ValueError as exc:
            assert "unknown artifact" in str(exc)
        assert store.list_spaces("owner") == []
    finally:
        store.close()

def test_import_refuses_owner_with_migration_only(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    try:
        ctx = LearningExecutionContext(store, "owner")
        ctx.mark_migration("legacy:test")
        try:
            ctx.import_owner_bundle({"version": 1})
            assert False
        except ValueError as exc:
            assert "already has" in str(exc)
    finally:
        store.close()
