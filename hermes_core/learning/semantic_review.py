"""M5 semantic-review seam: reviewer failures never approve a draft."""
from __future__ import annotations
from typing import Any, Callable, Dict, Optional
from learning.learning_context import LearningExecutionContext

Reviewer = Callable[[Dict[str, Any]], Optional[bool]]

def requires_semantic_review(artifact: Dict[str, Any]) -> bool:
    if artifact.get("kind") in {
        "flashcard_deck",
        "knowledge_base",
        "material_alignment",
        "resource_pack",
    }:
        return True
    if artifact.get("kind") != "tutoring_note":
        return False
    envelope = artifact.get("envelope") or {}
    payload = envelope.get("payload") if isinstance(envelope, dict) else {}
    return bool(envelope.get("source_refs")) or bool(payload.get("answers"))

class SemanticReviewService:
    def __init__(self, context: LearningExecutionContext, reviewer: Reviewer):
        self._ctx, self._reviewer = context, reviewer

    def review(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self._ctx.get_artifact(artifact_id)
        if not artifact:
            raise KeyError(f"artifact {artifact_id!r} not found")
        if artifact["status"] != "draft":
            raise ValueError("only draft artifacts can be reviewed")
        if not requires_semantic_review(artifact):
            raise ValueError("artifact kind has no M5 semantic reviewer")
        try:
            decision = self._reviewer(artifact)
        except Exception:
            decision = None
        status = "passed" if decision is True else "failed" if decision is False else "pending"
        self._ctx.set_artifact_review(artifact_id, status, review_mode="semantic")
        return {"artifact_id": artifact_id, "status": status, "reviewed": decision is not None}
