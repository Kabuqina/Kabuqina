# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Read-only global Activity projection over owned Study and Studio truth."""

from __future__ import annotations

from typing import Any, Iterable
from urllib.parse import quote, urlencode

from learning.learning_context import LearningExecutionContext
from learning.knowledge_core_compilation_store import (
    KnowledgeCoreCompilationStore,
)
from learning.learning_map import LearningMapService
from learning.learning_store import LearningStore
from learning.tutor_runtime_store import TutorRuntimeStore
from studio_store import StudioStore


ACTIVITY_STATUSES = frozenset(
    {"running", "waiting", "interrupted", "failed", "completed", "recoverable"}
)
MAX_RECENT_COMPLETED = 20

_STATUS_MAP = {
    "created": "waiting",
    "running": "running",
    "waiting_for_learner": "waiting",
    "interrupted": "interrupted",
    "blocked": "failed",
    "cancelled": "completed",
    "completed": "completed",
}

_COMPILATION_STATUS_MAP = {
    "queued": "waiting",
    "reading": "running",
    "generating": "running",
    "validating": "running",
    "draft_ready": "completed",
    "needs_source": "waiting",
    "failed": "failed",
    "cancelled": "completed",
}


def normalize_statuses(value: Iterable[str] | None) -> set[str] | None:
    if value is None:
        return None
    statuses = {item.strip() for item in value if isinstance(item, str) and item.strip()}
    if not statuses.issubset(ACTIVITY_STATUSES):
        raise ValueError("activity statuses are invalid")
    return statuses


class ActivityProjectionService:
    """Aggregate persisted lifecycle rows without owning domain mutations."""

    def __init__(
        self,
        *,
        owner_id: str,
        learning_store: LearningStore,
        runtime_store: TutorRuntimeStore,
        studio_store: StudioStore,
        compilation_store: KnowledgeCoreCompilationStore | None = None,
    ) -> None:
        self.owner_id = owner_id
        self.learning_store = learning_store
        self.runtime_store = runtime_store
        self.studio_store = studio_store
        self.compilation_store = compilation_store

    def _study_target(
        self, space_id: str, space_exists: bool
    ) -> tuple[str, str, dict[str, Any] | None]:
        fallback = "/study"
        if not space_exists:
            return fallback, fallback, None
        base = f"/study/{quote(space_id, safe='')}"
        try:
            context = LearningExecutionContext(
                self.learning_store, self.owner_id, space_id
            )
            location = LearningMapService(context).get_location()
        except Exception:
            location = None
        if not location:
            return base, fallback, None
        page = str(location.get("page") or "plan")
        if location.get("stale"):
            return f"{base}/plan", fallback, location
        params = {}
        if location.get("knowledgeCoreId"):
            params["knowledgeCoreId"] = str(location["knowledgeCoreId"])
        if location.get("exerciseId"):
            params["exerciseId"] = str(location["exerciseId"])
        target = f"{base}/{page}"
        if params:
            target = f"{target}?{urlencode(params)}"
        return target, fallback, location

    def _study_records(self) -> list[dict[str, Any]]:
        spaces = {
            str(item["space_id"]): item
            for item in self.learning_store.list_spaces(self.owner_id)
            if item.get("kind", "course") == "course"
        }
        records: list[dict[str, Any]] = []
        completed = 0
        for run in self.runtime_store.list_owner_projection_runs(
            self.owner_id, limit=500
        ):
            public_status = _STATUS_MAP.get(str(run.get("status") or ""))
            if public_status is None:
                continue
            if public_status == "completed":
                if completed >= MAX_RECENT_COMPLETED:
                    continue
                completed += 1
            space_id = str(run.get("space_id") or "")
            space = spaces.get(space_id)
            target, fallback, location = self._study_target(
                space_id, space is not None
            )
            course_title = (
                str(space.get("title") or space_id) if space else "已移除的课程"
            )
            label = str(run.get("label") or "学习活动")
            source_status = str(run.get("status") or "")
            records.append(
                {
                    "id": f"study:{run.get('activity_kind')}:{run.get('activity_id')}",
                    "domain": "study",
                    "kind": str(run.get("activity_kind") or "tutor"),
                    "status": public_status,
                    "title": f"{course_title} · {label}",
                    "scopeTitle": course_title,
                    "updatedAt": str(run.get("updated_at") or ""),
                    "returnTarget": target,
                    "fallbackTarget": fallback,
                    "canResume": source_status
                    in {"created", "waiting_for_learner", "interrupted"}
                    and run.get("activity_kind") == "tutor",
                    "canRetry": False,
                    "revision": int(run.get("revision") or 0),
                    "spaceId": space_id,
                    "activityId": str(run.get("activity_id") or ""),
                    "activityKind": str(run.get("activity_kind") or ""),
                    "sourceStatus": source_status,
                    "targetAvailable": space is not None,
                    **({"returnContext": location} if location else {}),
                }
            )
        return records

    def _studio_records(self) -> list[dict[str, Any]]:
        return [
            {
                "id": f"studio:project:{project['id']}",
                "domain": "studio",
                "kind": "project_scene",
                "status": "recoverable",
                "title": str(project.get("title") or "Studio Project"),
                "updatedAt": str(project.get("updatedAt") or ""),
                "returnTarget": f"/studio/{quote(str(project['id']), safe='')}",
                "fallbackTarget": "/studio",
                "canResume": False,
                "canRetry": False,
                "projectId": str(project["id"]),
                "targetAvailable": True,
            }
            for project in self.studio_store.list_projects()
        ]

    def _compilation_records(self) -> list[dict[str, Any]]:
        if self.compilation_store is None:
            return []
        spaces = {
            str(item["space_id"]): item
            for item in self.learning_store.list_spaces(self.owner_id)
            if item.get("kind", "course") == "course"
        }
        records: list[dict[str, Any]] = []
        for run in self.compilation_store.list_runs(self.owner_id, limit=500):
            source_status = str(run.get("status") or "")
            public_status = _COMPILATION_STATUS_MAP.get(source_status)
            if public_status is None:
                continue
            space_id = str(run.get("space_id") or "")
            outline_node_id = str(run.get("outline_node_id") or "")
            space = spaces.get(space_id)
            fallback = "/study"
            target = fallback
            if space is not None:
                target = f"/study/{quote(space_id, safe='')}/plan"
                if outline_node_id:
                    target += "?" + urlencode(
                        {"outlineNodeId": outline_node_id}
                    )
            course_title = (
                str(space.get("title") or space_id) if space else "已移除的课程"
            )
            records.append(
                {
                    "id": (
                        "study:knowledge_core_compilation:"
                        + str(run.get("run_id") or "")
                    ),
                    "domain": "study",
                    "kind": "knowledge_core_compilation",
                    "status": public_status,
                    "title": f"{course_title} · 整理知识核",
                    "scopeTitle": course_title,
                    "updatedAt": str(run.get("updated_at") or ""),
                    "returnTarget": target,
                    "fallbackTarget": fallback,
                    "canResume": False,
                    "canRetry": source_status in {"failed", "needs_source"},
                    "revision": 0,
                    "spaceId": space_id,
                    "activityId": str(run.get("run_id") or ""),
                    "activityKind": "knowledge_core_compilation",
                    "sourceStatus": source_status,
                    "targetAvailable": space is not None,
                    "compilationRunId": str(run.get("run_id") or ""),
                    "outlineNodeId": outline_node_id,
                    "planItemId": str(run.get("plan_item_id") or "") or None,
                    "draftArtifactId": (
                        str(run.get("draft_artifact_id") or "") or None
                    ),
                    "reasonCode": str(run.get("reason_code") or "") or None,
                }
            )
        return records

    def list_records(
        self, *, statuses: set[str] | None = None, limit: int = 100
    ) -> dict[str, Any]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be within 1..100")
        normalized = normalize_statuses(statuses)
        items = [
            *self._study_records(),
            *self._compilation_records(),
            *self._studio_records(),
        ]
        if normalized is not None:
            items = [item for item in items if item["status"] in normalized]
        items.sort(key=lambda item: (item["updatedAt"], item["id"]), reverse=True)
        page = items[:limit]
        return {"items": page, "count": len(page), "limit": limit}


__all__ = ["ACTIVITY_STATUSES", "ActivityProjectionService", "normalize_statuses"]
