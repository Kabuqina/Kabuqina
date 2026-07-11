from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningStore
from learning.output_writer import OutputWriter
from learning.semantic_review import SemanticReviewService

def _ctx(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    ctx = LearningExecutionContext(store, "owner")
    ctx.create_space(title="Course", space_id="s")
    return store, ctx

def _draft(ctx):
    return OutputWriter(ctx).write_artifact(
        kind="knowledge_base", title="KB", payload={"concepts": [{"term": "x", "explanation": "y"}]}
    )["artifact_id"]

def test_reviewer_decisions_and_failure_remain_pending(tmp_path):
    store, ctx = _ctx(tmp_path)
    try:
        artifact_id = _draft(ctx)
        assert SemanticReviewService(ctx, lambda _: True).review(artifact_id)["status"] == "approved"
        assert ctx.get_artifact(artifact_id)["review"]["status"] == "approved"
        second = _draft(ctx)
        assert SemanticReviewService(ctx, lambda _: (_ for _ in ()).throw(RuntimeError())).review(second) == {
            "artifact_id": second, "status": "pending", "reviewed": False
        }
        assert ctx.get_artifact(second)["review"]["status"] == "pending"
    finally:
        store.close()

def test_m5_semantic_kinds_are_all_reviewable(tmp_path):
    store, ctx = _ctx(tmp_path)
    try:
        samples = [
            ("knowledge_base", {"concepts": [{"term": "x", "explanation": "y"}]}),
            ("resource_pack", {"resources": [{"title": "r", "purpose": "p"}]}),
            ("tutoring_note", {"goal": "g", "hints": ["h"]}),
        ]
        for kind, payload in samples:
            artifact_id = OutputWriter(ctx).write_artifact(kind=kind, title=kind, payload=payload)["artifact_id"]
            assert SemanticReviewService(ctx, lambda _: False).review(artifact_id)["status"] == "rejected"
    finally:
        store.close()
