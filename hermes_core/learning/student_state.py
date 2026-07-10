"""Trusted STUDY M4 student-state operations and legacy normalization."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from learning.learning_context import LearningExecutionContext

LEGACY_CONTEXT_MIGRATION_KEY = "localStorage:kabuqina.study.context.v1"
FIXED_LABEL_KEYS = frozenset(
    {"capability_labels", "ability_labels", "personality", "personality_labels"}
)
TEXT_LIMIT = 800
MAX_LIST_ITEMS = 24


def _clean_text(value: Any, limit: int = TEXT_LIMIT) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _strings(value: Any) -> List[str]:
    candidates: List[Any]
    if isinstance(value, str):
        candidates = value.replace("；", "\n").replace(";", "\n").splitlines()
    elif isinstance(value, list):
        candidates = value
    else:
        candidates = []

    out: List[str] = []
    seen: set[str] = set()
    for raw in candidates:
        item = _clean_text(raw).strip(" -\t")
        key = item.casefold()
        if not item or key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= MAX_LIST_ITEMS:
            break
    return out


class StudentStateService:
    """Trusted save/activate/read surface for one owner-scoped course state."""

    def __init__(self, context: LearningExecutionContext):
        self._ctx = context

    def save_state(
        self, payload: Dict[str, Any], *, title: str = "Student state"
    ) -> Dict[str, Any]:
        normalized = self.normalize_payload(payload)
        result = self._ctx.put_artifact(
            kind="student_state", title=title, payload=normalized
        )
        return self.activate_state(result["artifact_id"])

    def activate_state(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self._require_state(artifact_id)
        for active in self._ctx.list_artifacts(
            kind="student_state", status="active"
        ):
            if active["artifact_id"] != artifact_id:
                self._ctx.set_artifact_status(active["artifact_id"], "archived")
        if artifact["status"] != "active":
            self._ctx.set_artifact_status(artifact_id, "active")
        current = self._require_state(artifact_id)
        return self._public(current)

    def reject_state(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self._require_state(artifact_id)
        if artifact["status"] != "rejected":
            self._ctx.set_artifact_status(artifact_id, "rejected")
        return {"artifact_id": artifact_id, "status": "rejected"}

    def get_current_state(self) -> Optional[Dict[str, Any]]:
        active = sorted(
            self._ctx.list_artifacts(kind="student_state", status="active"),
            key=lambda row: (row["updated_at"], row["artifact_id"]),
            reverse=True,
        )
        return self._public(active[0]) if active else None

    def _require_state(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self._ctx.get_artifact(artifact_id)
        if not artifact:
            raise KeyError(f"artifact {artifact_id!r} not found")
        if artifact.get("kind") != "student_state":
            raise ValueError("artifact is not a student_state")
        return artifact

    @staticmethod
    def _public(artifact: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "artifact_id": artifact["artifact_id"],
            "status": artifact["status"],
            "payload": artifact["envelope"]["payload"],
        }

    @staticmethod
    def normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("student_state payload must be an object")
        if FIXED_LABEL_KEYS & set(payload):
            raise ValueError("student_state must not include fixed learner labels")
        preferences = payload.get("preferences")
        clean_preferences = {
            str(key)[:80]: _clean_text(value)
            for key, value in (preferences.items() if isinstance(preferences, dict) else [])
            if _clean_text(value)
        }
        return {
            "course": _clean_text(payload.get("course")),
            "goals": _strings(payload.get("goals")),
            "preferences": clean_preferences,
            "constraints": _strings(payload.get("constraints")),
            "progress_notes": _strings(payload.get("progress_notes")),
            "current_stage": _clean_text(payload.get("current_stage")),
            "next_adjustment": _clean_text(payload.get("next_adjustment")),
        }

    @staticmethod
    def legacy_context_to_payloads(
        context: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        if not isinstance(context, dict):
            raise ValueError("legacy study context must be an object")
        profile_summary = _clean_text(context.get("profileSummary"))
        study_preferences = _clean_text(context.get("preferences"))
        progress_notes = _strings(context.get("progressNotes"))
        progress_notes.extend(
            item
            for item in _strings(context.get("generatedResources"))
            if item.casefold() not in {note.casefold() for note in progress_notes}
        )
        state = {
            "course": _clean_text(context.get("course")),
            "goals": _strings(context.get("goal")),
            "preferences": {
                **({"profile_summary": profile_summary} if profile_summary else {}),
                **({"study_preferences": study_preferences} if study_preferences else {}),
            },
            "constraints": [],
            "progress_notes": progress_notes[:MAX_LIST_ITEMS],
            "current_stage": _clean_text(context.get("currentStage")),
            "next_adjustment": _clean_text(context.get("nextAdjustment")),
        }
        observations = (
            _strings(context.get("evaluationSummary"))
            + _strings(context.get("assessmentEvidence"))
            + _strings(context.get("tutoringNotes"))
        )
        observations = _strings(observations)
        weak_points = _strings(context.get("weakPoints"))
        suggestions = _strings(context.get("nextAdjustment"))
        if not (observations or weak_points or suggestions):
            return state, None
        return state, {
            "observations": observations or ["Legacy study context imported."],
            "weak_points": weak_points,
            "suggestions": suggestions,
            "evidence_refs": [
                {
                    "origin": "legacy_local_storage",
                    "key": "kabuqina.study.context.v1",
                }
            ],
        }
