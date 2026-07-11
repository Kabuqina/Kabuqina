"""Bounded lifecycle projections for the M6 notebook UI."""

from __future__ import annotations

from typing import Any, Dict, Optional

from learning.learning_context import LearningExecutionContext
from learning.learning_contract import KINDS, LIFECYCLE_STATUSES

MAX_SUMMARIES = 100


class ArtifactLifecycleService:
    def __init__(self, context: LearningExecutionContext):
        self._ctx = context

    def summaries(
        self,
        *,
        kind: Optional[str] = None,
        status: Optional[str] = "draft",
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        if kind is not None and kind not in KINDS:
            raise ValueError("unknown artifact kind")
        if status is not None and status not in LIFECYCLE_STATUSES:
            raise ValueError("unknown artifact status")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= MAX_SUMMARIES
        ):
            raise ValueError(f"limit must be within 1..{MAX_SUMMARIES}")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        result = self._ctx.artifact_summary_page(
            kind=kind, status=status, limit=limit, offset=offset
        )
        counts = {name: 0 for name in sorted(LIFECYCLE_STATUSES)}
        counts.update(result["counts"])
        items = [
            {
                "artifact_id": row["artifact_id"],
                "kind": row["kind"],
                "title": str(row.get("title") or "")[:300],
                "status": row["status"],
                "review": {
                    "mode": str((row.get("review") or {}).get("mode") or "")[:40],
                    "status": str((row.get("review") or {}).get("status") or "")[:40],
                },
                "updated_at": row["updated_at"],
            }
            for row in result["rows"]
        ]
        return {
            "items": items,
            "count": result["count"],
            "counts": counts,
            "returned": len(items),
            "limit": limit,
            "offset": offset,
            "truncated": offset + len(items) < result["count"],
        }
