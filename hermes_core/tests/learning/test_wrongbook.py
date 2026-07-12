from unittest.mock import patch

from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningStore
from learning.output_writer import OutputWriter
from learning.wrongbook import WrongbookService

def test_wrongbook_is_bounded_and_excludes_answer_content(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    try:
        ctx = LearningExecutionContext(store, "owner")
        ctx.create_space(title="Course", space_id="s")
        for index in range(3):
            ctx.record_activity(activity_type="quiz.attempt", artifact_id=f"q{index}", detail={
                "score": 0, "maxScore": 1, "percent": 0, "weakTags": ["algebra"],
                "perQuestion": [{"response": "SECRET ANSWER", "failure_summary": "INJECT"}],
            })
        with patch.object(
            LearningExecutionContext,
            "list_activities",
            side_effect=AssertionError("wrongbook query must not scan every activity"),
        ):
            result = WrongbookService(ctx).projection(limit=2)
        assert result["count"] == 3 and result["returned"] == 2 and result["truncated"] is True
        assert result["weak_points"] == ["algebra"]
        assert "SECRET ANSWER" not in str(result) and "INJECT" not in str(result)
    finally:
        store.close()


def test_retry_target_returns_only_scoped_opaque_identifiers(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    try:
        ctx = LearningExecutionContext(store, "owner")
        ctx.create_space(title="Course", space_id="s")
        quiz_id = OutputWriter(ctx).write_artifact(
            kind="quiz",
            title="Private quiz",
            payload={"questions": [{"type": "choice", "prompt": "q", "options": ["a", "b"], "answer": 0}]},
        )["artifact_id"]
        ctx.set_artifact_status(quiz_id, "active")
        activity_id = ctx.record_activity(
            activity_type="quiz.attempt",
            artifact_id=quiz_id,
            detail={
                "response": "SECRET ANSWER",
                "perQuestion": [
                    {"item_id": "item-wrong", "correct": False, "response": "SECRET"},
                    {"item_id": "item-right", "correct": True},
                    {"item_id": "item-wrong", "correct": False},
                ],
            },
        )

        result = WrongbookService(ctx).retry_target(activity_id)
        assert result == {"artifact_id": quiz_id, "item_ids": ["item-wrong"]}
        assert "SECRET" not in str(result)
        try:
            WrongbookService(ctx).retry_target("missing")
        except KeyError:
            pass
        else:
            raise AssertionError("unknown retry activity must not resolve")
    finally:
        store.close()
