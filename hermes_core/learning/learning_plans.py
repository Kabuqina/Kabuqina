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


def _task_outline_node_id(task: Any) -> str:
    """Read the canonical binding plus the legacy Web/model camelCase alias."""
    if not isinstance(task, dict):
        return ""
    return _clean(task.get("outline_node_id")) or _clean(task.get("outlineNodeId"))


class LearningPlanService:
    def __init__(
        self,
        context: LearningExecutionContext,
        *,
        now: Optional[Callable[[], datetime]] = None,
    ):
        self._ctx = context
        self._now = now or _now_utc

    def activate_plan(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self._require_plan(artifact_id)
        self._validate_outline_bindings(artifact)
        for active in self._ctx.list_artifacts(
            kind="learning_plan", status="active"
        ):
            if active["artifact_id"] != artifact_id:
                self._ctx.set_artifact_status(active["artifact_id"], "archived")
        if artifact["status"] != "active":
            self._ctx.set_artifact_status(artifact_id, "active")
            artifact = self._require_plan(artifact_id)
        created = self._materialize_items(artifact)
        return {
            "artifact_id": artifact_id,
            "status": "active",
            "materialized": created,
        }

    def reconcile_plan_items(self, artifact_id: str) -> Dict[str, int]:
        """Repair materialized plan items from their immutable active plan.

        This is intentionally narrow: it creates missing rows and restores only
        a non-empty outline binding from the plan artifact. Learner progress and
        notes in existing item state are preserved.
        """
        artifact = self._require_plan(artifact_id)
        if artifact.get("status") != "active":
            raise ValueError("only an active learning plan can be reconciled")
        self._validate_outline_bindings(artifact)
        created, repaired = self._reconcile_items(artifact)
        return {"created": created, "repaired": repaired}

    def reject_plan(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self._require_plan(artifact_id)
        if artifact["status"] != "rejected":
            self._ctx.set_artifact_status(artifact_id, "rejected")
        return {"artifact_id": artifact_id, "status": "rejected"}

    def _validate_outline_bindings(self, artifact: Dict[str, Any]) -> None:
        payload = artifact.get("envelope", {}).get("payload", {})
        phases = payload.get("phases") if isinstance(payload, dict) else []
        bound_ids = {
            _task_outline_node_id(task)
            for phase in (phases if isinstance(phases, list) else [])
            for task in (
                phase.get("tasks")
                if isinstance(phase, dict) and isinstance(phase.get("tasks"), list)
                else []
            )
            if isinstance(task, dict) and _task_outline_node_id(task)
        }
        if not bound_ids:
            return
        # Import locally so the map projection can inspect plan items without a
        # module cycle while activation still validates current Course truth.
        from learning.learning_map import LearningMapService

        outline_ids = {
            node["id"] for node in LearningMapService(self._ctx).get_map()["outlineNodes"]
        }
        unknown = sorted(bound_ids - outline_ids)
        if unknown:
            raise ValueError(
                "learning plan references unavailable outline nodes: "
                + ", ".join(unknown[:10])
            )

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

    def compilation_intents(self, artifact_id: str) -> List[Dict[str, Any]]:
        """Return the current and next open ``learn`` actions after activation.

        This is a pure core scheduling decision.  The desktop host owns enqueue
        and model execution, so activation itself never waits on a provider.
        """
        artifact = self._require_plan(artifact_id)
        if artifact.get("status") != "active":
            return []
        learn_items = [
            item
            for item in self.list_plan_items(artifact_id=artifact_id)
            if item.get("status") == "open"
            and item.get("mode", "learn") == "learn"
            and _clean(item.get("outlineNodeId"))
        ][:2]
        return [
            {
                "space_id": self._ctx.current_space(),
                "outline_node_id": item["outlineNodeId"],
                "plan_item_id": item["item_id"],
                "trigger": "plan_activated" if index == 0 else "prefetch",
                "priority": 10 if index == 0 else 0,
            }
            for index, item in enumerate(learn_items)
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
        created, _ = self._reconcile_items(artifact)
        return created

    def _reconcile_items(self, artifact: Dict[str, Any]) -> tuple[int, int]:
        artifact_id = artifact["artifact_id"]
        existing = {
            row["item_id"]: row
            for row in self._ctx.list_items(
                item_type=LEARNING_PLAN_ITEM_TYPE, artifact_id=artifact_id
            )
        }
        payload = artifact.get("envelope", {}).get("payload", {})
        phases = payload.get("phases") if isinstance(payload, dict) else []
        created = 0
        repaired = 0
        item_index = 0
        now = _iso(self._now())
        for phase_index, phase in enumerate(phases if isinstance(phases, list) else []):
            tasks = phase.get("tasks") if isinstance(phase, dict) else []
            for task_index, task in enumerate(tasks if isinstance(tasks, list) else []):
                iid = _item_id(artifact_id, item_index)
                item_index += 1
                task_mode = _clean(task.get("mode")) if isinstance(task, dict) else ""
                if task_mode not in {"learn", "practice", "review"}:
                    task_mode = "learn"
                outline_node_id = _task_outline_node_id(task)
                current = existing.get(iid)
                if current is not None:
                    current_state = dict(current.get("state") or {})
                    if (
                        outline_node_id
                        and not _clean(current_state.get("outlineNodeId"))
                    ):
                        current_state["outlineNodeId"] = outline_node_id
                        self._ctx.update_item_state(iid, current_state)
                        repaired += 1
                    continue
                state = {
                    "artifact_id": artifact_id,
                    "phaseIndex": phase_index,
                    "phaseTitle": _clean(phase.get("title")),
                    "taskIndex": task_index,
                    "title": _clean(task.get("title")) if isinstance(task, dict) else "",
                    "order": task.get("order")
                    if isinstance(task, dict) and isinstance(task.get("order"), int)
                    else task_index + 1,
                    "done_when": _clean(task.get("done_when"))
                    if isinstance(task, dict)
                    else "",
                    "mode": task_mode,
                    "outlineNodeId": outline_node_id,
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
        return created, repaired

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
