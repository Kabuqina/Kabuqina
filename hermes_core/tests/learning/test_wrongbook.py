from unittest.mock import patch

from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningStore
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
