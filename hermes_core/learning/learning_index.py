"""Learning Index skeleton — a deterministic read-only snapshot of one space.

The index is what a Planner reads *before* planning. It is assembled purely from
saved learning data:

- includes only ``active`` artifacts (as lightweight references, never full
  payloads) and allowed direct activities;
- excludes ``draft``/``rejected``/``archived`` — unreviewed content is never
  presented as course fact;
- never calls an LLM and never mutates the store or the Material Index;
- is versioned and size-bounded for one ``space_id``.

M1 ships the data spine only: ``due_reviews`` and ``weak_points`` are present but
empty; deriving them from activities/items is a later milestone.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from learning.learning_context import LearningExecutionContext

INDEX_VERSION: int = 1

MAX_INDEX_ARTIFACTS: int = 1_000
MAX_INDEX_ACTIVITIES: int = 1_000
MAX_INDEX_BYTES: int = 256 * 1024


def _artifact_ref(a: Dict[str, Any]) -> Dict[str, Any]:
    """Project a stored artifact to a lightweight index reference (no payload)."""
    return {
        "artifact_id": a["artifact_id"],
        "kind": a["kind"],
        "title": a["title"],
        "version": a["version"],
        "review": a["review"],
        "updated_at": a["updated_at"],
    }


def _activity_ref(a: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "activity_id": a["activity_id"],
        "activity_type": a["activity_type"],
        "artifact_id": a["artifact_id"],
        "item_id": a["item_id"],
        "created_at": a["created_at"],
    }


class LearningIndex:
    """Builds the read-only per-space snapshot from a runtime context."""

    def __init__(self, context: LearningExecutionContext):
        self._ctx = context

    def build(
        self,
        *,
        max_artifacts: int = MAX_INDEX_ARTIFACTS,
        max_activities: int = MAX_INDEX_ACTIVITIES,
        max_bytes: int = MAX_INDEX_BYTES,
    ) -> Dict[str, Any]:
        space_id = self._ctx._require_space()

        # Deterministic order: most-recent first, tie-broken by id.
        active = sorted(
            self._ctx.list_artifacts(status="active"),
            key=lambda a: (a["updated_at"], a["artifact_id"]),
            reverse=True,
        )
        activities = sorted(
            self._ctx.list_activities(),
            key=lambda a: (a["created_at"], a["activity_id"]),
            reverse=True,
        )

        truncated = len(active) > max_artifacts or len(activities) > max_activities
        artifacts = [_artifact_ref(a) for a in active[:max_artifacts]]
        acts = [_activity_ref(a) for a in activities[:max_activities]]

        snapshot: Dict[str, Any] = {
            "index_version": INDEX_VERSION,
            "space_id": space_id,
            "artifacts": artifacts,
            "activities": acts,
            "due_reviews": [],   # M1 placeholder
            "weak_points": [],   # M1 placeholder
            "truncated": truncated,
        }

        if self._exceeds(snapshot, max_bytes):
            truncated = True
            self._trim_to_bytes(snapshot, max_bytes)
            snapshot["truncated"] = True

        return snapshot

    @staticmethod
    def _exceeds(snapshot: Dict[str, Any], max_bytes: int) -> bool:
        return LearningIndex._byte_size(snapshot) > max_bytes

    @staticmethod
    def _byte_size(snapshot: Dict[str, Any]) -> int:
        return len(json.dumps(snapshot, ensure_ascii=False).encode("utf-8"))

    @staticmethod
    def _trim_to_bytes(snapshot: Dict[str, Any], max_bytes: int) -> None:
        """Drop least-recent references (activities first, then artifacts) until
        the snapshot fits, or the reference lists are empty. Deterministic."""
        lists: List[str] = ["activities", "artifacts"]
        for key in lists:
            while snapshot[key] and LearningIndex._byte_size(snapshot) > max_bytes:
                snapshot[key].pop()  # least-recent sits at the tail
