import pytest
from gateway import study_commands
from learning.learning_store import LearningStore
from learning.learning_context import LearningExecutionContext
from learning.output_writer import OutputWriter

def test_study_commands_are_sender_scoped(tmp_path, monkeypatch):
    db = tmp_path / "learning.db"
    monkeypatch.setattr(study_commands, "LearningStore", lambda: LearningStore(db_path=db))
    assert "created" in study_commands.handle_study_command("telegram", "alice", "new Algebra")
    assert "Algebra" in study_commands.handle_study_command("telegram", "alice", "list")
    assert study_commands.handle_study_command("telegram", "bob", "list") == "No study spaces."

def test_study_approve_and_reject_are_owned_and_deterministic(tmp_path, monkeypatch):
    db = tmp_path / "learning.db"
    monkeypatch.setattr(study_commands, "LearningStore", lambda: LearningStore(db_path=db))
    study_commands.handle_study_command("telegram", "alice", "new Algebra")
    store = LearningStore(db_path=db)
    try:
        ctx = LearningExecutionContext(store, study_commands.gateway_owner_id("telegram", "alice"))
        artifact_id = OutputWriter(ctx).write_artifact(
            kind="tutoring_note", title="Hints", payload={"goal":"x", "hints":["h"]}
        )["artifact_id"]
    finally:
        store.close()
    assert "approved" in study_commands.handle_study_command("telegram", "alice", f"approve {artifact_id}")
    assert "failed" in study_commands.handle_study_command("telegram", "bob", f"reject {artifact_id}")
