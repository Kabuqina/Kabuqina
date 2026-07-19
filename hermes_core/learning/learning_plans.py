"""Trusted STUDY M4 learning-plan lifecycle and direct item activities."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from learning.learning_context import LearningExecutionContext

LEARNING_PLAN_ITEM_TYPE = "learning_plan_item"
PLAN_ITEM_COMPLETE_ACTIVITY = "learning_plan.item.complete"
PLAN_ITEM_SKIP_ACTIVITY = "learning_plan.item.skip"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _clean(value: Any, limit: int = 800) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _item_id(artifact_id: str, index: int) -> str:
    return f"{artifact_id}-{index:04d}"


class LearningPlanService:
    """Trusted current-plan lifecycle and learner item-state operations."""

    def __init__(
        self,
        context: LearningExecutionContext,
        *,
        now: Optional[Callable[[], datetime]] = None,
    ):
        self._ctx = context
        self._now = now or _now_utc

    def activate_plan(self, artifact_id: str) -> Dict[str, Any]:
        self._require_plan(artifact_id)
        self._ctx.activate_singleton_artifact(artifact_id, kind="learning_plan")
        artifact = self._require_plan(artifact_id)
        created = self._materialize_items(artifact)
        return {
            "artifact_id": artifact_id,
            "status": "active",
            "materialized": created,
        }

    def reject_plan(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self._require_plan(artifact_id)
        if artifact["status"] != "rejected":
            self._ctx.set_artifact_status(artifact_id, "rejected")
        return {"artifact_id": artifact_id, "status": "rejected"}

    def list_plans(self, *, status: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._ctx.list_artifacts(kind="learning_plan", status=status)

    def list_plan_items(
        self, *, artifact_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        rows = self._ctx.list_items(
            item_type=LEARNING_PLAN_ITEM_TYPE, artifact_id=artifact_id
        )
        return [
            {
                **dict(row.get("state") or {}),
                "item_id": row["item_id"],
                "artifact_id": row.get("artifact_id") or "",
            }
            for row in rows
        ]

    def complete_item(self, item_id: str, *, note: str = "") -> Dict[str, Any]:
        return self._mark_item(
            item_id, "completed", PLAN_ITEM_COMPLETE_ACTIVITY, note
        )

    def skip_item(self, item_id: str, *, note: str = "") -> Dict[str, Any]:
        return self._mark_item(item_id, "skipped", PLAN_ITEM_SKIP_ACTIVITY, note)

    def _require_plan(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self._ctx.get_artifact(artifact_id)
        if not artifact:
            raise KeyError(f"artifact {artifact_id!r} not found")
        if artifact.get("kind") != "learning_plan":
            raise ValueError("artifact is not a learning_plan")
        return artifact

    def _materialize_items(self, artifact: Dict[str, Any]) -> int:
        artifact_id = artifact["artifact_id"]
        existing = {
            row["item_id"]
            for row in self._ctx.list_items(
                item_type=LEARNING_PLAN_ITEM_TYPE, artifact_id=artifact_id
            )
        }
        payload = artifact.get("envelope", {}).get("payload", {})
        phases = payload.get("phases") if isinstance(payload, dict) else []
        created = 0
        item_index = 0
        now = _iso(self._now())
        for phase_index, phase in enumerate(
            phases if isinstance(phases, list) else []
        ):
            tasks = phase.get("tasks") if isinstance(phase, dict) else []
            for task_index, task in enumerate(
                tasks if isinstance(tasks, list) else []
            ):
                iid = _item_id(artifact_id, item_index)
                item_index += 1
                if iid in existing:
                    continue
                state = {
                    "artifact_id": artifact_id,
                    "phaseIndex": phase_index,
                    "phaseTitle": _clean(phase.get("title")),
                    "taskIndex": task_index,
                    "title": _clean(task.get("title"))
                    if isinstance(task, dict)
                    else "",
                    "order": task.get("order")
                    if isinstance(task, dict) and isinstance(task.get("order"), int)
                    else task_index + 1,
                    "done_when": _clean(task.get("done_when"))
                    if isinstance(task, dict)
                    else "",
                    "status": "open",
                    "completedAt": "",
                    "skippedAt": "",
                    "note": "",
                    "createdAt": now,
                }
                self._ctx.upsert_item(
                    item_id=iid,
                    item_type=LEARNING_PLAN_ITEM_TYPE,
                    artifact_id=artifact_id,
                    state=state,
                )
                created += 1
        return created

    def _mark_item(
        self, item_id: str, status: str, activity_type: str, note: str
    ) -> Dict[str, Any]:
        rows = [
            row
            for row in self._ctx.list_items(item_type=LEARNING_PLAN_ITEM_TYPE)
            if row["item_id"] == item_id
        ]
        if not rows:
            raise KeyError(f"plan item {item_id!r} not found")
        row = rows[0]
        artifact = self._require_plan(str(row.get("artifact_id") or ""))
        if artifact["status"] != "active":
            raise ValueError("plan item parent is not active")
        state = dict(row.get("state") or {})
        current = state.get("status") or "open"
        if current != "open":
            raise ValueError(f"plan item is already {current}")
        state["status"] = status
        state["note"] = _clean(note)
        timestamp_key = "completedAt" if status == "completed" else "skippedAt"
        state[timestamp_key] = _iso(self._now())
        self._ctx.update_item_state(item_id, state)
        self._ctx.record_activity(
            activity_type=activity_type,
            artifact_id=artifact["artifact_id"],
            item_id=item_id,
            detail={
                "status": status,
                "note": state["note"],
                "title": state.get("title", ""),
            },
        )
        return {
            **state,
            "item_id": item_id,
            "artifact_id": artifact["artifact_id"],
        }
