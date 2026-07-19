"""Trusted STUDY M4 evaluation lifecycle and bounded projections."""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from learning.learning_context import LearningExecutionContext

MAX_PROJECTED_EVALUATIONS = 5
MAX_FIELD_ITEMS = 12
MAX_FIELD_TEXT = 800


def _strings(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [
        item.strip()[:MAX_FIELD_TEXT]
        for item in value
        if isinstance(item, str) and item.strip()
    ][:MAX_FIELD_ITEMS]


class EvaluationService:
    """Trusted activation and read helpers for evidence-based evaluations."""

    def __init__(self, context: LearningExecutionContext):
        self._ctx = context

    def activate_evaluation(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self._require_evaluation(artifact_id)
        if artifact["status"] != "active":
            self._ctx.set_artifact_status(artifact_id, "active")
        return {"artifact_id": artifact_id, "status": "active"}

    def reject_evaluation(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self._require_evaluation(artifact_id)
        if artifact["status"] != "rejected":
            self._ctx.set_artifact_status(artifact_id, "rejected")
        return {"artifact_id": artifact_id, "status": "rejected"}

    def list_evaluations(
        self, *, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return self._ctx.list_artifacts(kind="evaluation", status=status)

    def get_evaluation(self, artifact_id: str) -> Dict[str, Any]:
        return self._require_evaluation(artifact_id)

    def active_evaluation_projections(self) -> List[Dict[str, Any]]:
        active = sorted(
            self.list_evaluations(status="active"),
            key=lambda row: (row["updated_at"], row["artifact_id"]),
            reverse=True,
        )[:MAX_PROJECTED_EVALUATIONS]
        return [self._project(row) for row in active]

    def _require_evaluation(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self._ctx.get_artifact(artifact_id)
        if not artifact:
            raise KeyError(f"artifact {artifact_id!r} not found")
        if artifact.get("kind") != "evaluation":
            raise ValueError("artifact is not an evaluation")
        return artifact

    @staticmethod
    def _project(artifact: Dict[str, Any]) -> Dict[str, Any]:
        payload = artifact.get("envelope", {}).get("payload", {})
        refs = payload.get("evidence_refs") if isinstance(payload, dict) else []
        safe_refs = [
            copy.deepcopy(ref)
            for ref in (refs if isinstance(refs, list) else [])
            if isinstance(ref, dict)
            and all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in ref.items()
            )
        ][:MAX_FIELD_ITEMS]
        return {
            "artifact_id": artifact["artifact_id"],
            "title": str(artifact.get("title") or "")[:MAX_FIELD_TEXT],
            "observations": _strings(payload.get("observations")),
            "weak_points": _strings(payload.get("weak_points")),
            "suggestions": _strings(payload.get("suggestions")),
            "evidence_refs": safe_refs,
        }
