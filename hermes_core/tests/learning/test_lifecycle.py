from unittest.mock import patch

from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningStore
from learning.lifecycle import ArtifactLifecycleService
from learning.output_writer import OutputWriter

def test_summaries_are_bounded_counted_and_hide_envelopes(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    try:
        ctx = LearningExecutionContext(store, "owner")
        ctx.create_space(title="Course", space_id="s")
        for index in range(3):
            OutputWriter(ctx).write_artifact(
                kind="tutoring_note", title=f"Note {index}",
                payload={"goal":"g", "hints":["secret hint"]},
            )
        with patch.object(
            LearningExecutionContext,
            "list_artifacts",
            side_effect=AssertionError("summary query must not load full artifacts"),
        ):
            result = ArtifactLifecycleService(ctx).summaries(limit=2)
        assert result["count"] == 3
        assert result["returned"] == 2
        assert result["truncated"] is True
        assert result["counts"]["draft"] == 3
        assert all("envelope" not in item for item in result["items"])
        assert "secret hint" not in str(result)
    finally:
        store.close()
