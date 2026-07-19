import pytest
from gateway import study_commands
from learning.learning_store import LearningStore
from learning.learning_context import LearningExecutionContext
from learning.output_writer import OutputWriter
from learning.operation_coordinator import (
    LearningOperationCoordinator,
    LearningOperationInProgressError,
)

def test_study_commands_are_sender_scoped(tmp_path, monkeypatch):
    db = tmp_path / "learning.db"
    monkeypatch.setattr(study_commands, "LearningStore", lambda: LearningStore(db_path=db))
    assert "created" in study_commands.handle_study_command("telegram", "alice", "new Algebra")
    assert "Algebra" in study_commands.handle_study_command("telegram", "alice", "list")
    assert study_commands.handle_study_command("telegram", "bob", "list") == "No study spaces."


def test_gateway_production_constructor_obeys_shared_owner_fence(tmp_path, monkeypatch):
    import learning.learning_store as store_module

    db = tmp_path / "learning.db"
    monkeypatch.setattr(store_module, "default_learning_db_path", lambda: db)
    owner = study_commands.gateway_owner_id("telegram", "alice")
    coordinator = LearningOperationCoordinator.from_learning_db_path(db)
    lease = coordinator.begin_operation(owner, "", "delete")
    try:
        with pytest.raises(LearningOperationInProgressError):
            study_commands.handle_study_command("telegram", "alice", "new Algebra")
    finally:
        coordinator.finish_operation(lease)

def test_study_approve_and_reject_are_owned_and_deterministic(tmp_path, monkeypatch):
    db = tmp_path / "learning.db"
    monkeypatch.setattr(study_commands, "LearningStore", lambda: LearningStore(db_path=db))
    study_commands.handle_study_command("telegram", "alice", "new Algebra")
    store = LearningStore(db_path=db)
    try:
        ctx = LearningExecutionContext(store, study_commands.gateway_owner_id("telegram", "alice"))
        artifact_id = OutputWriter(ctx).write_artifact(
            kind="flashcard_deck", title="Deck", payload={"cards":[{"front":"q", "back":"a"}]}
        )["artifact_id"]
    finally:
        store.close()
    assert "approved" in study_commands.handle_study_command("telegram", "alice", f"approve {artifact_id}")
    store = LearningStore(db_path=db)
    try:
        ctx = LearningExecutionContext(store, study_commands.gateway_owner_id("telegram", "alice"))
        assert len(ctx.list_items(item_type="flashcard")) == 1
    finally:
        store.close()
    assert "failed" in study_commands.handle_study_command("telegram", "bob", f"reject {artifact_id}")
