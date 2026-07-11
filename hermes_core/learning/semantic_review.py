"""M5 semantic-review seam: reviewer failures never approve a draft."""
from __future__ import annotations
from typing import Any, Callable, Dict, Optional
from learning.learning_context import LearningExecutionContext

SEMANTIC_KINDS = frozenset({"knowledge_base", "resource_pack", "tutoring_note"})
Reviewer = Callable[[Dict[str, Any]], Optional[bool]]

class SemanticReviewService:
    def __init__(self, context: LearningExecutionContext, reviewer: Reviewer):
        self._ctx, self._reviewer = context, reviewer

    def review(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self._ctx.get_artifact(artifact_id)
        if not artifact:
            raise KeyError(f"artifact {artifact_id!r} not found")
        if artifact["status"] != "draft":
            raise ValueError("only draft artifacts can be reviewed")
        if artifact["kind"] not in SEMANTIC_KINDS:
            raise ValueError("artifact kind has no M5 semantic reviewer")
        try:
            decision = self._reviewer(artifact)
        except Exception:
            decision = None
        status = "approved" if decision is True else "rejected" if decision is False else "pending"
        self._ctx.set_artifact_review(artifact_id, status)
        return {"artifact_id": artifact_id, "status": status, "reviewed": decision is not None}
