# STUDY M4 State, Evaluation, and Learning Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** deliver the STUDY M4 vertical slice for durable student state, evidence-based evaluations, active learning plans, and plan-item activities without implementing Gateway `/study` commands or the M6 lifecycle UI rewrite.

**Architecture:** keep M4 semantics in small core services under `hermes_core/learning/`, expose them through the existing trusted desk STUDY router, keep Tauri as a thin proxy, and make Web use pure mapper functions plus typed `study-api.ts` wrappers. `LearningIndex` remains deterministic and read-only, but gains bounded projections for active state, active evaluations, current plan, and safe activity summaries.

**Tech Stack:** Python 3.11 + SQLite WAL, pytest, FastAPI desk routes, Tauri 2 Rust commands, React/Vite TypeScript, Node pure mapper tests.

**Execution Gate:** Do not execute this plan until M1-M3 review feedback is resolved. If review findings change M1-M3 lifecycle, route naming, migration, or Web refresh semantics, update this plan first.

---

## File Structure

- Create `hermes_core/learning/student_state.py`: trusted active `student_state` save/read/archive and legacy context normalization.
- Create `hermes_core/learning/evaluations.py`: evaluation list/detail/activate/reject helpers and safe projection helpers.
- Create `hermes_core/learning/learning_plans.py`: plan activation, item materialization, item listing, complete/skip activity writes.
- Create `hermes_core/tests/learning/test_student_state.py`: core student state and migration normalization tests.
- Create `hermes_core/tests/learning/test_evaluations.py`: core evaluation lifecycle tests.
- Create `hermes_core/tests/learning/test_learning_plans.py`: core plan activation and plan item activity tests.
- Modify `hermes_core/learning/learning_contract.py`: allow bounded `evaluation.evidence_refs`.
- Modify `hermes_core/learning/learning_index.py`: add M4 projections and safe activity summaries.
- Modify `hermes_core/tests/learning/test_learning_contract.py`: cover `evaluation.evidence_refs` and fixed-label rejection.
- Modify `hermes_core/tests/learning/test_learning_index.py`: cover M4 projections and read-only behavior.
- Modify `python/src/desk_server/routes/study_routes.py`: add M4 routes and generic activate/reject dispatch.
- Modify `python/tests/test_study_routes.py`: add M4 route and migration tests.
- Modify `tauri/src/study.rs` and `tauri/src/lib.rs`: add M4 proxy commands and registration.
- Modify `web/src/chat/study/study-api.ts`: add M4 types and invoke wrappers.
- Create `web/src/chat/study/studyLearningStore.ts`: pure mapper helpers for legacy context migration, backend state forms, and plan item labels.
- Create `web/src/chat/study/studyLearningStore.test.mjs`: mapper tests.
- Modify `web/src/chat/study/StudySection.tsx`: switch primary context save/read to backend and show minimal evaluation/plan surfaces.
- Modify `web/src/chat/study/studyPrompts.ts`: update profile/path/evaluation prompts to use learning tools.
- Modify `web/src/locales/strings.ts`: add M4 UI strings.
- Modify docs after implementation: M4 closure in `DECISIONS.md` and `docs/superpowers/specs/2026-07-01-study-four-layer-learning-pipeline-design.md`.

---

## Task 1: Student State Core Service

**Files:**
- Create: `hermes_core/learning/student_state.py`
- Create: `hermes_core/tests/learning/test_student_state.py`

- [ ] **Step 1: Write failing student state tests.**

Add `hermes_core/tests/learning/test_student_state.py`:

```python
from __future__ import annotations

import pytest

from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningStore
from learning.student_state import StudentStateService


@pytest.fixture()
def ctx(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    context = LearningExecutionContext(store, owner_id="owner-A")
    context.create_space(title="Algebra", space_id="s1")
    try:
        yield context
    finally:
        store.close()


def test_save_state_creates_single_active_student_state(ctx):
    service = StudentStateService(ctx)

    first = service.save_state({
        "course": "Algebra",
        "goals": ["Pass the midterm"],
        "preferences": {"study_time": "30 minutes"},
        "constraints": ["mobile review"],
        "progress_notes": ["linear equations"],
        "current_stage": "Practice",
        "next_adjustment": "mixed drills",
    })
    second = service.save_state({
        "course": "Algebra II",
        "goals": ["Prepare for finals"],
        "preferences": {"study_time": "45 minutes"},
    })

    assert first["status"] == "active"
    assert second["status"] == "active"
    active = ctx.list_artifacts(kind="student_state", status="active")
    archived = ctx.list_artifacts(kind="student_state", status="archived")
    assert [a["artifact_id"] for a in active] == [second["artifact_id"]]
    assert [a["artifact_id"] for a in archived] == [first["artifact_id"]]
    assert service.get_current_state()["payload"]["course"] == "Algebra II"


def test_activate_state_uses_existing_draft(ctx):
    from learning.output_writer import OutputWriter

    draft_id = OutputWriter(ctx).write_artifact(
        kind="student_state",
        title="AI profile",
        payload={"course": "Geometry", "goals": ["Proof practice"]},
    )["artifact_id"]

    activated = StudentStateService(ctx).activate_state(draft_id)

    assert activated["artifact_id"] == draft_id
    assert activated["status"] == "active"
    assert ctx.get_artifact(draft_id)["status"] == "active"


def test_save_state_rejects_fixed_labels(ctx):
    service = StudentStateService(ctx)

    with pytest.raises(ValueError):
        service.save_state({"course": "Algebra", "capability_labels": ["weak"]})


def test_legacy_context_maps_state_and_evaluation_payloads():
    state, evaluation = StudentStateService.legacy_context_to_payloads({
        "course": "Calculus",
        "goal": "Pass",
        "profileSummary": "Likes examples",
        "weakPoints": "limits\nchain rule",
        "preferences": "20 minutes daily",
        "progressNotes": "Finished derivatives",
        "assessmentEvidence": "Quiz 1: 60%",
        "currentStage": "Review",
        "evaluationSummary": "Application is weak",
        "nextAdjustment": "More mixed practice",
    })

    assert state == {
        "course": "Calculus",
        "goals": ["Pass"],
        "preferences": {
            "profile_summary": "Likes examples",
            "study_preferences": "20 minutes daily",
        },
        "constraints": [],
        "progress_notes": ["Finished derivatives"],
        "current_stage": "Review",
        "next_adjustment": "More mixed practice",
    }
    assert evaluation == {
        "observations": ["Application is weak", "Quiz 1: 60%"],
        "weak_points": ["limits", "chain rule"],
        "suggestions": ["More mixed practice"],
        "evidence_refs": [{"origin": "legacy_local_storage", "key": "kabuqina.study.context.v1"}],
    }
```

- [ ] **Step 2: Run RED for student state.**

Run:

```powershell
cd hermes_core
python -m pytest tests/learning/test_student_state.py -o "addopts=" -p no:cacheprovider -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'learning.student_state'`.

- [ ] **Step 3: Implement `StudentStateService`.**

Create `hermes_core/learning/student_state.py` with this public surface:

```python
"""Trusted STUDY M4 student state service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from learning.learning_context import LearningExecutionContext

LEGACY_CONTEXT_MIGRATION_KEY = "localStorage:kabuqina.study.context.v1"
FIXED_LABEL_KEYS = {"capability_labels", "ability_labels", "personality", "personality_labels"}
TEXT_LIMIT = 800
MAX_LIST = 24


def _clean_text(value: Any, limit: int = TEXT_LIMIT) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _lines(value: Any) -> List[str]:
    text = _clean_text(value)
    if not text:
        return []
    out: List[str] = []
    seen: set[str] = set()
    for raw in text.replace("；", "\n").replace(";", "\n").splitlines():
        item = raw.strip(" -\t")
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= MAX_LIST:
            break
    return out


class StudentStateService:
    def __init__(self, context: LearningExecutionContext):
        self._ctx = context

    def save_state(self, payload: Dict[str, Any], *, title: str = "Student state") -> Dict[str, Any]:
        normalized = self.normalize_payload(payload)
        res = self._ctx.put_artifact(kind="student_state", title=title, payload=normalized)
        return self.activate_state(res["artifact_id"])

    def activate_state(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self._require_state(artifact_id)
        for active in self._ctx.list_artifacts(kind="student_state", status="active"):
            if active["artifact_id"] != artifact_id:
                self._ctx.set_artifact_status(active["artifact_id"], "archived")
        if artifact["status"] != "active":
            self._ctx.set_artifact_status(artifact_id, "active")
        artifact = self._ctx.get_artifact(artifact_id)
        if not artifact:
            raise KeyError(artifact_id)
        return {
            "artifact_id": artifact["artifact_id"],
            "status": artifact["status"],
            "payload": artifact["envelope"]["payload"],
        }

    def reject_state(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self._require_state(artifact_id)
        if artifact["status"] != "rejected":
            self._ctx.set_artifact_status(artifact_id, "rejected")
        return {"artifact_id": artifact_id, "status": "rejected"}

    def get_current_state(self) -> Optional[Dict[str, Any]]:
        rows = self._ctx.list_artifacts(kind="student_state", status="active")
        if not rows:
            return None
        artifact = sorted(rows, key=lambda a: (a["updated_at"], a["artifact_id"]), reverse=True)[0]
        return {
            "artifact_id": artifact["artifact_id"],
            "status": artifact["status"],
            "payload": artifact["envelope"]["payload"],
        }

    def _require_state(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self._ctx.get_artifact(artifact_id)
        if not artifact:
            raise KeyError(f"artifact {artifact_id!r} not found")
        if artifact.get("kind") != "student_state":
            raise ValueError("artifact is not a student_state")
        return artifact

    @staticmethod
    def normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        if any(key in payload for key in FIXED_LABEL_KEYS):
            raise ValueError("student_state must not include fixed learner labels")
        preferences = payload.get("preferences") if isinstance(payload.get("preferences"), dict) else {}
        return {
            "course": _clean_text(payload.get("course")),
            "goals": _lines(payload.get("goals")) if isinstance(payload.get("goals"), str) else [g for g in payload.get("goals", []) if isinstance(g, str)][:MAX_LIST],
            "preferences": {str(k): _clean_text(v) for k, v in preferences.items() if _clean_text(v)},
            "constraints": _lines(payload.get("constraints")) if isinstance(payload.get("constraints"), str) else [c for c in payload.get("constraints", []) if isinstance(c, str)][:MAX_LIST],
            "progress_notes": _lines(payload.get("progress_notes")) if isinstance(payload.get("progress_notes"), str) else [n for n in payload.get("progress_notes", []) if isinstance(n, str)][:MAX_LIST],
            "current_stage": _clean_text(payload.get("current_stage")),
            "next_adjustment": _clean_text(payload.get("next_adjustment")),
        }

    @staticmethod
    def legacy_context_to_payloads(context: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        state = {
            "course": _clean_text(context.get("course")),
            "goals": _lines(context.get("goal")),
            "preferences": {
                **({"profile_summary": _clean_text(context.get("profileSummary"))} if _clean_text(context.get("profileSummary")) else {}),
                **({"study_preferences": _clean_text(context.get("preferences"))} if _clean_text(context.get("preferences")) else {}),
            },
            "constraints": [],
            "progress_notes": _lines(context.get("progressNotes")),
            "current_stage": _clean_text(context.get("currentStage")),
            "next_adjustment": _clean_text(context.get("nextAdjustment")),
        }
        observations = _lines(context.get("evaluationSummary")) + _lines(context.get("assessmentEvidence"))
        weak_points = _lines(context.get("weakPoints"))
        suggestions = _lines(context.get("nextAdjustment"))
        evaluation = None
        if observations or weak_points or suggestions:
            evaluation = {
                "observations": observations or ["Legacy study context imported."],
                "weak_points": weak_points,
                "suggestions": suggestions,
                "evidence_refs": [{"origin": "legacy_local_storage", "key": "kabuqina.study.context.v1"}],
            }
        return state, evaluation
```

- [ ] **Step 4: Run GREEN for student state.**

Run:

```powershell
cd hermes_core
python -m pytest tests/learning/test_student_state.py -o "addopts=" -p no:cacheprovider -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1.**

```powershell
git add hermes_core/learning/student_state.py hermes_core/tests/learning/test_student_state.py
git commit -m "feat: add study m4 student state service"
```

---

## Task 2: Evaluation Contract and Service

**Files:**
- Modify: `hermes_core/learning/learning_contract.py`
- Modify: `hermes_core/tests/learning/test_learning_contract.py`
- Create: `hermes_core/learning/evaluations.py`
- Create: `hermes_core/tests/learning/test_evaluations.py`

- [ ] **Step 1: Write failing contract test for evaluation evidence refs.**

Append to `hermes_core/tests/learning/test_learning_contract.py`:

```python
def test_evaluation_evidence_refs_are_valid():
    env = validate_envelope(
        {
            "version": 1,
            "kind": "evaluation",
            "space_id": "s1",
            "title": "Weekly evaluation",
            "payload": {
                "observations": ["Quiz score improved."],
                "weak_points": ["prime numbers"],
                "suggestions": ["Add mixed drills"],
                "evidence_refs": [
                    {"activity_id": "act-1", "activity_type": "quiz.attempt"},
                    {"artifact_id": "quiz-1"},
                ],
            },
        }
    )
    assert env.kind == "evaluation"


def test_evaluation_evidence_refs_must_be_bounded_list():
    with pytest.raises(ContractError):
        validate_envelope(
            {
                "version": 1,
                "kind": "evaluation",
                "space_id": "s1",
                "title": "Bad evaluation",
                "payload": {
                    "observations": ["x"],
                    "evidence_refs": ["not an object"],
                },
            }
        )
```

- [ ] **Step 2: Run RED for contract.**

Run:

```powershell
cd hermes_core
python -m pytest tests/learning/test_learning_contract.py::test_evaluation_evidence_refs_are_valid tests/learning/test_learning_contract.py::test_evaluation_evidence_refs_must_be_bounded_list -o "addopts=" -p no:cacheprovider -q
```

Expected: FAIL because `evidence_refs` validation does not exist yet.

- [ ] **Step 3: Extend evaluation validation.**

In `hermes_core/learning/learning_contract.py`, add a helper near the other validators:

```python
def _opt_evidence_refs(p: Mapping[str, Any], ctx: str) -> None:
    refs = p.get("evidence_refs")
    if refs is None:
        return
    if not isinstance(refs, list) or len(refs) > MAX_SOURCE_REFS:
        raise ContractError(f"{ctx}: 'evidence_refs' must be a bounded list")
    for i, ref in enumerate(refs):
        rctx = f"{ctx}.evidence_refs[{i}]"
        rm = _mapping(ref, rctx)
        for key, value in rm.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ContractError(f"{rctx}: keys and values must be strings")
```

Then update `_v_evaluation`:

```python
def _v_evaluation(p: Mapping[str, Any]) -> None:
    _forbid_keys(p, _FIXED_LABEL_KEYS, "evaluation")
    _req_nonempty_list(p, "observations", "evaluation")
    _opt_str_list(p, "weak_points", "evaluation")
    _opt_str_list(p, "suggestions", "evaluation")
    _opt_evidence_refs(p, "evaluation")
```

- [ ] **Step 4: Write failing evaluation service tests.**

Create `hermes_core/tests/learning/test_evaluations.py`:

```python
from __future__ import annotations

import pytest

from learning.evaluations import EvaluationService
from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningStore
from learning.output_writer import OutputWriter


@pytest.fixture()
def ctx(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    context = LearningExecutionContext(store, owner_id="owner-A")
    context.create_space(title="Algebra", space_id="s1")
    try:
        yield context
    finally:
        store.close()


def _draft(ctx):
    return OutputWriter(ctx).write_artifact(
        kind="evaluation",
        title="Weekly evaluation",
        payload={
            "observations": ["Missed prime questions."],
            "weak_points": ["prime numbers"],
            "suggestions": ["Add mixed drills"],
            "evidence_refs": [{"activity_id": "a1", "activity_type": "quiz.attempt"}],
        },
    )["artifact_id"]


def test_activate_and_reject_evaluations(ctx):
    service = EvaluationService(ctx)
    artifact_id = _draft(ctx)

    activated = service.activate_evaluation(artifact_id)

    assert activated["status"] == "active"
    assert service.list_evaluations(status="active")[0]["artifact_id"] == artifact_id


def test_reject_keeps_evaluation_out_of_active_list(ctx):
    service = EvaluationService(ctx)
    artifact_id = _draft(ctx)

    rejected = service.reject_evaluation(artifact_id)

    assert rejected["status"] == "rejected"
    assert service.list_evaluations(status="active") == []


def test_projection_is_bounded_and_omits_fixed_labels(ctx):
    service = EvaluationService(ctx)
    artifact_id = _draft(ctx)
    service.activate_evaluation(artifact_id)

    projected = service.active_evaluation_projections()

    assert projected == [
        {
            "artifact_id": artifact_id,
            "title": "Weekly evaluation",
            "observations": ["Missed prime questions."],
            "weak_points": ["prime numbers"],
            "suggestions": ["Add mixed drills"],
            "evidence_refs": [{"activity_id": "a1", "activity_type": "quiz.attempt"}],
        }
    ]
```

- [ ] **Step 5: Run RED for evaluation service.**

Run:

```powershell
cd hermes_core
python -m pytest tests/learning/test_evaluations.py -o "addopts=" -p no:cacheprovider -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'learning.evaluations'`.

- [ ] **Step 6: Implement `EvaluationService`.**

Create `hermes_core/learning/evaluations.py`:

```python
"""Trusted STUDY M4 evaluation service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from learning.learning_context import LearningExecutionContext

MAX_PROJECTED_EVALUATIONS = 5
MAX_FIELD_ITEMS = 12


def _strings(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [v.strip()[:800] for v in value if isinstance(v, str) and v.strip()][:MAX_FIELD_ITEMS]


class EvaluationService:
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

    def list_evaluations(self, *, status: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._ctx.list_artifacts(kind="evaluation", status=status)

    def get_evaluation(self, artifact_id: str) -> Dict[str, Any]:
        return self._require_evaluation(artifact_id)

    def active_evaluation_projections(self) -> List[Dict[str, Any]]:
        rows = sorted(
            self.list_evaluations(status="active"),
            key=lambda a: (a["updated_at"], a["artifact_id"]),
            reverse=True,
        )[:MAX_PROJECTED_EVALUATIONS]
        return [self._project(a) for a in rows]

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
        if not isinstance(refs, list):
            refs = []
        return {
            "artifact_id": artifact["artifact_id"],
            "title": artifact["title"],
            "observations": _strings(payload.get("observations")),
            "weak_points": _strings(payload.get("weak_points")),
            "suggestions": _strings(payload.get("suggestions")),
            "evidence_refs": [r for r in refs if isinstance(r, dict)][:MAX_FIELD_ITEMS],
        }
```

- [ ] **Step 7: Run GREEN for contract and service.**

Run:

```powershell
cd hermes_core
python -m pytest tests/learning/test_learning_contract.py tests/learning/test_evaluations.py -o "addopts=" -p no:cacheprovider -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 2.**

```powershell
git add hermes_core/learning/learning_contract.py hermes_core/tests/learning/test_learning_contract.py hermes_core/learning/evaluations.py hermes_core/tests/learning/test_evaluations.py
git commit -m "feat: add study m4 evaluation lifecycle"
```

---

## Task 3: Learning Plan Core Service

**Files:**
- Create: `hermes_core/learning/learning_plans.py`
- Create: `hermes_core/tests/learning/test_learning_plans.py`

- [ ] **Step 1: Write failing learning plan tests.**

Create `hermes_core/tests/learning/test_learning_plans.py`:

```python
from __future__ import annotations

import pytest

from learning.learning_context import LearningExecutionContext
from learning.learning_plans import LEARNING_PLAN_ITEM_TYPE, PLAN_ITEM_COMPLETE_ACTIVITY, LearningPlanService
from learning.learning_store import LearningStore
from learning.output_writer import OutputWriter


@pytest.fixture()
def ctx(tmp_path):
    store = LearningStore(db_path=tmp_path / "learning.db")
    context = LearningExecutionContext(store, owner_id="owner-A")
    context.create_space(title="Algebra", space_id="s1")
    try:
        yield context
    finally:
        store.close()


def _plan_payload(title="Refresh basics"):
    return {
        "goals": ["Master factoring"],
        "phases": [
            {
                "title": title,
                "tasks": [
                    {"title": "Review factor pairs", "order": 1, "done_when": "Can list pairs"},
                    {"title": "Do mixed drill", "order": 2, "done_when": "Score at least 80%"},
                ],
            }
        ],
    }


def _draft(ctx, title="Plan"):
    return OutputWriter(ctx).write_artifact(
        kind="learning_plan",
        title=title,
        payload=_plan_payload(),
    )["artifact_id"]


def test_activate_plan_archives_previous_active_and_materializes_items(ctx):
    service = LearningPlanService(ctx)
    first = _draft(ctx, "First")
    second = _draft(ctx, "Second")

    service.activate_plan(first)
    result = service.activate_plan(second)

    assert result["status"] == "active"
    assert result["materialized"] == 2
    assert [p["artifact_id"] for p in service.list_plans(status="active")] == [second]
    assert [p["artifact_id"] for p in ctx.list_artifacts(kind="learning_plan", status="archived")] == [first]
    items = service.list_plan_items(artifact_id=second)
    assert [item["title"] for item in items] == ["Review factor pairs", "Do mixed drill"]
    assert all(item["status"] == "open" for item in items)


def test_complete_and_skip_plan_items_record_real_activities(ctx):
    service = LearningPlanService(ctx)
    artifact_id = _draft(ctx)
    service.activate_plan(artifact_id)
    items = service.list_plan_items(artifact_id=artifact_id)

    completed = service.complete_item(items[0]["item_id"], note="done")
    skipped = service.skip_item(items[1]["item_id"], note="already know it")

    assert completed["status"] == "completed"
    assert skipped["status"] == "skipped"
    activities = ctx.list_activities()
    assert [a["activity_type"] for a in activities] == [
        PLAN_ITEM_COMPLETE_ACTIVITY,
        "learning_plan.item.skip",
    ]
    assert activities[0]["item_id"] == items[0]["item_id"]


def test_reject_plan_does_not_materialize_items(ctx):
    service = LearningPlanService(ctx)
    artifact_id = _draft(ctx)

    rejected = service.reject_plan(artifact_id)

    assert rejected["status"] == "rejected"
    assert ctx.list_items(item_type=LEARNING_PLAN_ITEM_TYPE) == []
```

- [ ] **Step 2: Run RED for learning plans.**

Run:

```powershell
cd hermes_core
python -m pytest tests/learning/test_learning_plans.py -o "addopts=" -p no:cacheprovider -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'learning.learning_plans'`.

- [ ] **Step 3: Implement `LearningPlanService`.**

Create `hermes_core/learning/learning_plans.py` with this public surface:

```python
"""Trusted STUDY M4 learning plan service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from learning.learning_context import LearningExecutionContext

LEARNING_PLAN_ITEM_TYPE = "learning_plan_item"
PLAN_ITEM_COMPLETE_ACTIVITY = "learning_plan.item.complete"
PLAN_ITEM_SKIP_ACTIVITY = "learning_plan.item.skip"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any, limit: int = 800) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _item_id(artifact_id: str, phase_index: int, task_index: int) -> str:
    return f"{artifact_id}:phase-{phase_index:02d}:task-{task_index:02d}"


class LearningPlanService:
    def __init__(self, context: LearningExecutionContext):
        self._ctx = context

    def activate_plan(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self._require_plan(artifact_id)
        for active in self._ctx.list_artifacts(kind="learning_plan", status="active"):
            if active["artifact_id"] != artifact_id:
                self._ctx.set_artifact_status(active["artifact_id"], "archived")
        if artifact["status"] != "active":
            self._ctx.set_artifact_status(artifact_id, "active")
            artifact = self._require_plan(artifact_id)
        created = self._materialize_items(artifact)
        return {"artifact_id": artifact_id, "status": "active", "materialized": created}

    def reject_plan(self, artifact_id: str) -> Dict[str, Any]:
        artifact = self._require_plan(artifact_id)
        if artifact["status"] != "rejected":
            self._ctx.set_artifact_status(artifact_id, "rejected")
        return {"artifact_id": artifact_id, "status": "rejected"}

    def list_plans(self, *, status: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._ctx.list_artifacts(kind="learning_plan", status=status)

    def list_plan_items(self, *, artifact_id: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = self._ctx.list_items(item_type=LEARNING_PLAN_ITEM_TYPE, artifact_id=artifact_id)
        return [dict(row.get("state") or {}, item_id=row["item_id"], artifact_id=row.get("artifact_id") or "") for row in rows]

    def complete_item(self, item_id: str, *, note: str = "") -> Dict[str, Any]:
        return self._mark_item(item_id, "completed", PLAN_ITEM_COMPLETE_ACTIVITY, note)

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
        existing = {row["item_id"] for row in self._ctx.list_items(item_type=LEARNING_PLAN_ITEM_TYPE, artifact_id=artifact_id)}
        payload = artifact.get("envelope", {}).get("payload", {})
        phases = payload.get("phases") if isinstance(payload, dict) else []
        created = 0
        for phase_index, phase in enumerate(phases if isinstance(phases, list) else []):
            tasks = phase.get("tasks") if isinstance(phase, dict) else []
            for task_index, task in enumerate(tasks if isinstance(tasks, list) else []):
                iid = _item_id(artifact_id, phase_index, task_index)
                if iid in existing:
                    continue
                self._ctx.upsert_item(
                    item_id=iid,
                    item_type=LEARNING_PLAN_ITEM_TYPE,
                    artifact_id=artifact_id,
                    state={
                        "artifact_id": artifact_id,
                        "phaseIndex": phase_index,
                        "phaseTitle": _clean(phase.get("title")) if isinstance(phase, dict) else "",
                        "taskIndex": task_index,
                        "title": _clean(task.get("title")) if isinstance(task, dict) else "",
                        "order": task.get("order") if isinstance(task, dict) and isinstance(task.get("order"), int) else task_index + 1,
                        "done_when": _clean(task.get("done_when")) if isinstance(task, dict) else "",
                        "status": "open",
                        "note": "",
                        "createdAt": _now(),
                    },
                )
                created += 1
        return created

    def _mark_item(self, item_id: str, status: str, activity_type: str, note: str) -> Dict[str, Any]:
        rows = [row for row in self._ctx.list_items(item_type=LEARNING_PLAN_ITEM_TYPE) if row["item_id"] == item_id]
        if not rows:
            raise KeyError(f"plan item {item_id!r} not found")
        state = dict(rows[0].get("state") or {})
        state["status"] = status
        state["note"] = _clean(note)
        state["completedAt" if status == "completed" else "skippedAt"] = _now()
        self._ctx.update_item_state(item_id, state)
        self._ctx.record_activity(
            activity_type=activity_type,
            artifact_id=rows[0].get("artifact_id"),
            item_id=item_id,
            detail={"status": status, "note": state["note"], "title": state.get("title", "")},
        )
        return {**state, "item_id": item_id, "artifact_id": rows[0].get("artifact_id") or ""}
```

- [ ] **Step 4: Run GREEN for learning plans.**

Run:

```powershell
cd hermes_core
python -m pytest tests/learning/test_learning_plans.py -o "addopts=" -p no:cacheprovider -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3.**

```powershell
git add hermes_core/learning/learning_plans.py hermes_core/tests/learning/test_learning_plans.py
git commit -m "feat: add study m4 learning plan service"
```

---

## Task 4: Learning Index M4 Projections

**Files:**
- Modify: `hermes_core/learning/learning_index.py`
- Modify: `hermes_core/tests/learning/test_learning_index.py`

- [ ] **Step 1: Write failing Learning Index projection tests.**

Append to `hermes_core/tests/learning/test_learning_index.py`:

```python
def test_index_projects_active_student_state_evaluations_and_plan(env):
    store, ctx, writer = env
    from learning.student_state import StudentStateService
    from learning.evaluations import EvaluationService
    from learning.learning_plans import LearningPlanService

    StudentStateService(ctx).save_state({"course": "Algebra", "goals": ["Midterm"]})
    evaluation_id = writer.write_artifact(
        kind="evaluation",
        title="Eval",
        payload={"observations": ["Missed primes"], "weak_points": ["prime numbers"]},
    )["artifact_id"]
    EvaluationService(ctx).activate_evaluation(evaluation_id)
    plan_id = writer.write_artifact(
        kind="learning_plan",
        title="Plan",
        payload={"phases": [{"title": "P1", "tasks": [{"title": "Drill", "order": 1}]}]},
    )["artifact_id"]
    LearningPlanService(ctx).activate_plan(plan_id)

    snap = LearningIndex(ctx).build()

    assert snap["student_state"]["course"] == "Algebra"
    assert snap["evaluations"][0]["weak_points"] == ["prime numbers"]
    assert snap["current_plan"]["artifact_id"] == plan_id
    assert snap["current_plan"]["items"][0]["title"] == "Drill"
    assert snap["weak_points"] == ["prime numbers"]


def test_index_excludes_draft_m4_artifacts(env):
    store, ctx, writer = env
    writer.write_artifact(
        kind="evaluation",
        title="Draft eval",
        payload={"observations": ["Not active"], "weak_points": ["draft"]},
    )

    snap = LearningIndex(ctx).build()

    assert snap["evaluations"] == []
    assert snap["weak_points"] == []
```

- [ ] **Step 2: Run RED for index projections.**

Run:

```powershell
cd hermes_core
python -m pytest tests/learning/test_learning_index.py::test_index_projects_active_student_state_evaluations_and_plan tests/learning/test_learning_index.py::test_index_excludes_draft_m4_artifacts -o "addopts=" -p no:cacheprovider -q
```

Expected: FAIL because `student_state`, `evaluations`, and `current_plan` are absent from the index.

- [ ] **Step 3: Implement projection helpers.**

In `hermes_core/learning/learning_index.py`, import the services:

```python
from learning.evaluations import EvaluationService
from learning.learning_plans import LearningPlanService
from learning.student_state import StudentStateService
```

Add helpers:

```python
def _dedupe_strings(values: List[str], limit: int = 24) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.lower()
        if not value or key in seen:
            continue
        seen.add(key)
        out.append(value)
        if len(out) >= limit:
            break
    return out


def _safe_activity_summary(a: Dict[str, Any]) -> Dict[str, Any]:
    ref = _activity_ref(a)
    detail = a.get("detail") if isinstance(a.get("detail"), dict) else {}
    if a["activity_type"] == "quiz.attempt":
        ref["summary"] = {
            "score": detail.get("score"),
            "maxScore": detail.get("maxScore"),
            "percent": detail.get("percent"),
            "weakTags": detail.get("weakTags") if isinstance(detail.get("weakTags"), list) else [],
        }
    elif a["activity_type"].startswith("learning_plan.item."):
        ref["summary"] = {
            "status": detail.get("status"),
            "title": detail.get("title"),
        }
    elif a["activity_type"] == "flashcard.review":
        ref["summary"] = {
            "grade": detail.get("grade"),
            "repetitions": detail.get("repetitions"),
            "dueAt": detail.get("dueAt"),
        }
    return ref
```

Then in `LearningIndex.build()`, compute M4 projections before `snapshot`:

```python
student = StudentStateService(self._ctx).get_current_state()
evaluations = EvaluationService(self._ctx).active_evaluation_projections()
plan_service = LearningPlanService(self._ctx)
active_plans = plan_service.list_plans(status="active")
current_plan = None
if active_plans:
    plan = sorted(active_plans, key=lambda a: (a["updated_at"], a["artifact_id"]), reverse=True)[0]
    current_plan = {
        "artifact_id": plan["artifact_id"],
        "title": plan["title"],
        "updated_at": plan["updated_at"],
        "items": plan_service.list_plan_items(artifact_id=plan["artifact_id"]),
    }
weak_points = _dedupe_strings([
    point
    for evaluation in evaluations
    for point in evaluation.get("weak_points", [])
])
```

Replace activity projection with safe summaries:

```python
acts = [_safe_activity_summary(a) for a in activities[:max_activities]]
```

Add these keys to `snapshot`:

```python
"student_state": student["payload"] if student else {},
"evaluations": evaluations,
"current_plan": current_plan,
"weak_points": weak_points,
```

- [ ] **Step 4: Run GREEN for Learning Index.**

Run:

```powershell
cd hermes_core
python -m pytest tests/learning/test_learning_index.py -o "addopts=" -p no:cacheprovider -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4.**

```powershell
git add hermes_core/learning/learning_index.py hermes_core/tests/learning/test_learning_index.py
git commit -m "feat: project study m4 state into learning index"
```

---

## Task 5: Desk STUDY M4 Routes

**Files:**
- Modify: `python/src/desk_server/routes/study_routes.py`
- Modify: `python/tests/test_study_routes.py`

- [ ] **Step 1: Write failing desk route tests.**

Append to `python/tests/test_study_routes.py`:

```python
def test_student_state_save_and_legacy_context_migration_routes(study_client):
    client, _db_path = study_client

    saved = client.put(
        "/api/desk/study/student-state",
        json={"state": {"course": "Algebra", "goals": ["Midterm"]}},
        headers=_headers(),
    )
    assert saved.status_code == 200
    assert saved.json()["state"]["payload"]["course"] == "Algebra"

    loaded = client.get("/api/desk/study/student-state", headers=_headers())
    assert loaded.status_code == 200
    assert loaded.json()["state"]["payload"]["goals"] == ["Midterm"]

    migrated = client.post(
        "/api/desk/study/migrations/context",
        json={"context": {"course": "Calculus", "goal": "Pass", "weakPoints": "limits"}},
        headers=_headers(),
    )
    assert migrated.status_code == 200
    assert migrated.json()["migrated"] is True
    assert migrated.json()["student_state"]["payload"]["course"] == "Calculus"
    assert migrated.json()["evaluation"]["status"] == "active"

    second = client.post(
        "/api/desk/study/migrations/context",
        json={"context": {"course": "Ignored"}},
        headers=_headers(),
    )
    assert second.status_code == 200
    assert second.json()["migrated"] is False


def test_evaluation_and_learning_plan_routes(study_client):
    client, db_path = study_client
    store = LearningStore(db_path=db_path)
    try:
        ctx = LearningExecutionContext(store, owner_id=OWNER)
        ctx.create_space(title="Algebra", space_id="s1")
        evaluation_id = OutputWriter(ctx).write_artifact(
            kind="evaluation",
            title="Eval",
            payload={"observations": ["Missed primes"], "weak_points": ["prime numbers"]},
        )["artifact_id"]
        plan_id = OutputWriter(ctx).write_artifact(
            kind="learning_plan",
            title="Plan",
            payload={"phases": [{"title": "P1", "tasks": [{"title": "Drill", "order": 1}]}]},
        )["artifact_id"]
    finally:
        store.close()

    activated_eval = client.post(
        f"/api/desk/study/artifacts/{evaluation_id}/activate",
        headers=_headers(),
    )
    assert activated_eval.status_code == 200

    evaluations = client.get("/api/desk/study/evaluations", headers=_headers())
    assert [e["artifact_id"] for e in evaluations.json()["evaluations"]] == [evaluation_id]

    activated_plan = client.post(
        f"/api/desk/study/artifacts/{plan_id}/activate",
        headers=_headers(),
    )
    assert activated_plan.status_code == 200
    assert activated_plan.json()["materialized"] == 1

    items = client.get(f"/api/desk/study/learning-plans/{plan_id}/items", headers=_headers())
    item_id = items.json()["items"][0]["item_id"]

    completed = client.post(
        f"/api/desk/study/learning-plans/items/{item_id}/complete",
        json={"note": "done"},
        headers=_headers(),
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
```

- [ ] **Step 2: Run RED for desk routes.**

Run:

```powershell
cd python
python -m pytest tests/test_study_routes.py -o "addopts=" -p no:cacheprovider -q
```

Expected: FAIL with 404 for new routes or unsupported artifact kinds.

- [ ] **Step 3: Add imports and migration key.**

In `python/src/desk_server/routes/study_routes.py`, add:

```python
from learning.evaluations import EvaluationService
from learning.learning_plans import LearningPlanService
from learning.student_state import LEGACY_CONTEXT_MIGRATION_KEY, StudentStateService
```

- [ ] **Step 4: Extend generic activate/reject dispatch.**

Update `study_artifact_activate`:

```python
            if artifact["kind"] == "student_state":
                return StudentStateService(ctx).activate_state(artifact_id)
            if artifact["kind"] == "evaluation":
                return EvaluationService(ctx).activate_evaluation(artifact_id)
            if artifact["kind"] == "learning_plan":
                return LearningPlanService(ctx).activate_plan(artifact_id)
```

Update `study_artifact_reject`:

```python
            if artifact["kind"] == "evaluation":
                return EvaluationService(ctx).reject_evaluation(artifact_id)
            if artifact["kind"] == "learning_plan":
                return LearningPlanService(ctx).reject_plan(artifact_id)
            if artifact["kind"] == "student_state":
                return StudentStateService(ctx).reject_state(artifact_id)
```

- [ ] **Step 5: Add M4 routes.**

Add these route handlers near the other STUDY routes:

```python
@router.get("/api/desk/study/student-state")
async def study_student_state():
    try:
        with _desktop_ctx() as ctx:
            if not ctx.current_space():
                return {"state": None}
            return {"state": StudentStateService(ctx).get_current_state()}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.put("/api/desk/study/student-state")
async def study_student_state_save(body: Dict[str, Any]):
    try:
        with _desktop_ctx() as ctx:
            _ensure_space(ctx)
            state = body.get("state") if isinstance(body.get("state"), dict) else {}
            return {"state": StudentStateService(ctx).save_state(state)}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/migrations/context")
async def study_context_migrate(body: Dict[str, Any]):
    try:
        with _desktop_ctx() as ctx:
            if ctx.is_migrated(LEGACY_CONTEXT_MIGRATION_KEY):
                return {"migrated": False}
            _ensure_space(ctx)
            legacy = body.get("context") if isinstance(body.get("context"), dict) else {}
            state_payload, evaluation_payload = StudentStateService.legacy_context_to_payloads(legacy)
            state = StudentStateService(ctx).save_state(state_payload, title="Legacy study context")
            evaluation = None
            if evaluation_payload:
                res = OutputWriter(ctx).write_artifact(
                    kind="evaluation",
                    title="Legacy study evaluation",
                    payload=evaluation_payload,
                    source_refs=[{"origin": "legacy_local_storage", "key": LEGACY_CONTEXT_MIGRATION_KEY}],
                )
                evaluation = EvaluationService(ctx).activate_evaluation(res["artifact_id"])
            ctx.mark_migration(
                LEGACY_CONTEXT_MIGRATION_KEY,
                detail={"student_state": state["artifact_id"], "evaluation": evaluation},
            )
            return {"migrated": True, "student_state": state, "evaluation": evaluation}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc
```

Also add evaluation and plan routes:

```python
@router.get("/api/desk/study/evaluations")
async def study_evaluations():
    try:
        with _desktop_ctx() as ctx:
            if not ctx.current_space():
                return {"evaluations": []}
            rows = EvaluationService(ctx).list_evaluations(status="active")
            return {"evaluations": [_artifact_ref(row) for row in rows]}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/evaluations/{artifact_id}")
async def study_evaluation_detail(artifact_id: str):
    try:
        with _desktop_ctx() as ctx:
            artifact = EvaluationService(ctx).get_evaluation(artifact_id)
            return {"evaluation": {**_artifact_ref(artifact), "payload": artifact["envelope"]["payload"]}}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/learning-plans")
async def study_learning_plans():
    try:
        with _desktop_ctx() as ctx:
            if not ctx.current_space():
                return {"plans": []}
            rows = LearningPlanService(ctx).list_plans(status="active")
            return {"plans": [_artifact_ref(row) for row in rows]}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.get("/api/desk/study/learning-plans/{artifact_id}/items")
async def study_learning_plan_items(artifact_id: str):
    try:
        with _desktop_ctx() as ctx:
            _require_artifact(ctx, artifact_id)
            return {"items": LearningPlanService(ctx).list_plan_items(artifact_id=artifact_id)}
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/learning-plans/items/{item_id}/complete")
async def study_learning_plan_item_complete(item_id: str, body: Dict[str, Any]):
    try:
        with _desktop_ctx() as ctx:
            return LearningPlanService(ctx).complete_item(item_id, note=str(body.get("note") or ""))
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc


@router.post("/api/desk/study/learning-plans/items/{item_id}/skip")
async def study_learning_plan_item_skip(item_id: str, body: Dict[str, Any]):
    try:
        with _desktop_ctx() as ctx:
            return LearningPlanService(ctx).skip_item(item_id, note=str(body.get("note") or ""))
    except (ValueError, KeyError, ContractError) as exc:
        raise _http_error(exc) from exc
```

- [ ] **Step 6: Run GREEN for desk routes.**

Run:

```powershell
cd python
python -m pytest tests/test_study_routes.py tests/test_learning_owner_context.py -o "addopts=" -p no:cacheprovider -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 5.**

```powershell
git add python/src/desk_server/routes/study_routes.py python/tests/test_study_routes.py
git commit -m "feat: expose study m4 desktop routes"
```

---

## Task 6: Tauri M4 Proxy Commands

**Files:**
- Modify: `tauri/src/study.rs`
- Modify: `tauri/src/lib.rs`

- [ ] **Step 1: Extend path-id validation test.**

In `tauri/src/study.rs`, add this assertion to `study_path_id_validation_rejects_path_and_query_chars`:

```rust
        assert!(validate_study_path_id("plan_01:phase-00:task-01").is_ok());
```

- [ ] **Step 2: Add M4 commands.**

Add to `tauri/src/study.rs`:

```rust
#[tauri::command]
pub async fn cmd_study_student_state(app: AppHandle) -> Result<Value, String> {
    crate::chat::desk_json_request(&app, reqwest::Method::GET, "/api/desk/study/student-state", None).await
}

#[tauri::command]
pub async fn cmd_study_student_state_save(app: AppHandle, state: Value) -> Result<Value, String> {
    crate::chat::desk_json_request(
        &app,
        reqwest::Method::PUT,
        "/api/desk/study/student-state",
        Some(json!({ "state": state })),
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_migrate_context(app: AppHandle, context: Value) -> Result<Value, String> {
    crate::chat::desk_json_request(
        &app,
        reqwest::Method::POST,
        "/api/desk/study/migrations/context",
        Some(json!({ "context": context })),
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_evaluations(app: AppHandle) -> Result<Value, String> {
    crate::chat::desk_json_request(&app, reqwest::Method::GET, "/api/desk/study/evaluations", None).await
}

#[tauri::command]
pub async fn cmd_study_evaluation_detail(app: AppHandle, artifact_id: String) -> Result<Value, String> {
    validate_study_path_id(&artifact_id)?;
    crate::chat::desk_json_request(
        &app,
        reqwest::Method::GET,
        &format!("/api/desk/study/evaluations/{artifact_id}"),
        None,
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_learning_plans(app: AppHandle) -> Result<Value, String> {
    crate::chat::desk_json_request(&app, reqwest::Method::GET, "/api/desk/study/learning-plans", None).await
}

#[tauri::command]
pub async fn cmd_study_learning_plan_items(app: AppHandle, artifact_id: String) -> Result<Value, String> {
    validate_study_path_id(&artifact_id)?;
    crate::chat::desk_json_request(
        &app,
        reqwest::Method::GET,
        &format!("/api/desk/study/learning-plans/{artifact_id}/items"),
        None,
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_learning_plan_item_complete(app: AppHandle, item_id: String, note: String) -> Result<Value, String> {
    validate_study_path_id(&item_id)?;
    crate::chat::desk_json_request(
        &app,
        reqwest::Method::POST,
        &format!("/api/desk/study/learning-plans/items/{item_id}/complete"),
        Some(json!({ "note": note })),
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_learning_plan_item_skip(app: AppHandle, item_id: String, note: String) -> Result<Value, String> {
    validate_study_path_id(&item_id)?;
    crate::chat::desk_json_request(
        &app,
        reqwest::Method::POST,
        &format!("/api/desk/study/learning-plans/items/{item_id}/skip"),
        Some(json!({ "note": note })),
    )
    .await
}
```

- [ ] **Step 3: Register commands.**

In `tauri/src/lib.rs`, add all new `study::cmd_study_*` functions to `tauri::generate_handler!`.

- [ ] **Step 4: Run GREEN for Tauri.**

Run from `tauri/` with the existing temporary runtime workaround if `python/dist/runtime` is absent:

```powershell
cargo test study
```

Expected: PASS.

- [ ] **Step 5: Commit Task 6.**

```powershell
git add tauri/src/study.rs tauri/src/lib.rs
git commit -m "feat: proxy study m4 desktop commands"
```

---

## Task 7: Web API and Pure Mappers

**Files:**
- Modify: `web/src/chat/study/study-api.ts`
- Create: `web/src/chat/study/studyLearningStore.ts`
- Create: `web/src/chat/study/studyLearningStore.test.mjs`
- Modify: `web/package.json`

- [ ] **Step 1: Write failing mapper tests.**

Create `web/src/chat/study/studyLearningStore.test.mjs`:

```javascript
import assert from "node:assert/strict";
import fs from "node:fs";
import ts from "typescript";

async function importTs(path) {
  const source = fs.readFileSync(new URL(path, import.meta.url), "utf8");
  const js = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const url = `data:text/javascript;base64,${Buffer.from(js).toString("base64")}`;
  return import(url);
}

const store = await importTs("./studyLearningStore.ts");

const legacy = {
  course: "Algebra",
  goal: "Pass",
  profileSummary: "Likes examples",
  weakPoints: "prime numbers\nfactoring",
  preferences: "30 minutes daily",
  progressNotes: "Finished chapter 1",
  assessmentEvidence: "Quiz 1: 70%",
  currentStage: "Practice",
  evaluationSummary: "Application is weak",
  nextAdjustment: "Add mixed review",
};

assert.deepEqual(store.legacyContextToStudentState(legacy), {
  course: "Algebra",
  goals: ["Pass"],
  preferences: {
    profile_summary: "Likes examples",
    study_preferences: "30 minutes daily",
  },
  constraints: [],
  progress_notes: ["Finished chapter 1"],
  current_stage: "Practice",
  next_adjustment: "Add mixed review",
});

assert.deepEqual(store.legacyContextToEvaluation(legacy), {
  observations: ["Application is weak", "Quiz 1: 70%"],
  weak_points: ["prime numbers", "factoring"],
  suggestions: ["Add mixed review"],
  evidence_refs: [{ origin: "legacy_local_storage", key: "kabuqina.study.context.v1" }],
});

assert.equal(store.formatPlanItemStatus("completed", "zh"), "已完成");
assert.equal(store.formatPlanItemStatus("skipped", "en"), "Skipped");

console.log("studyLearningStore.test.mjs: ok");
```

- [ ] **Step 2: Run RED for mapper.**

Run:

```powershell
cd web
node src/chat/study/studyLearningStore.test.mjs
```

Expected: FAIL because `studyLearningStore.ts` does not exist.

- [ ] **Step 3: Add Web API types and wrappers.**

In `web/src/chat/study/study-api.ts`, add:

```ts
export type StudyStudentStatePayload = {
  course?: string;
  goals?: string[];
  preferences?: Record<string, string>;
  constraints?: string[];
  progress_notes?: string[];
  current_stage?: string;
  next_adjustment?: string;
};

export type StudyStudentStateResponse = {
  state: null | { artifact_id: string; status: string; payload: StudyStudentStatePayload };
};

export type StudyEvaluationDetailResponse = {
  evaluation: StudyArtifact & { payload: { observations: string[]; weak_points?: string[]; suggestions?: string[]; evidence_refs?: unknown[] } };
};

export type StudyEvaluationsResponse = {
  evaluations: StudyArtifact[];
};

export type StudyLearningPlansResponse = {
  plans: StudyArtifact[];
};

export type StudyLearningPlanItem = {
  item_id: string;
  artifact_id: string;
  phaseIndex: number;
  phaseTitle?: string;
  taskIndex: number;
  title: string;
  order?: number;
  done_when?: string;
  status: "open" | "completed" | "skipped";
  note?: string;
};

export type StudyLearningPlanItemsResponse = {
  items: StudyLearningPlanItem[];
};

export function cmdStudyStudentState(): Promise<StudyStudentStateResponse> {
  return invoke("cmd_study_student_state");
}

export function cmdStudyStudentStateSave(state: StudyStudentStatePayload): Promise<StudyStudentStateResponse> {
  return invoke("cmd_study_student_state_save", { state });
}

export function cmdStudyMigrateContext(context: unknown): Promise<unknown> {
  return invoke("cmd_study_migrate_context", { context });
}

export function cmdStudyEvaluations(): Promise<StudyEvaluationsResponse> {
  return invoke("cmd_study_evaluations");
}

export function cmdStudyEvaluationDetail(artifactId: string): Promise<StudyEvaluationDetailResponse> {
  return invoke("cmd_study_evaluation_detail", { artifactId });
}

export function cmdStudyLearningPlans(): Promise<StudyLearningPlansResponse> {
  return invoke("cmd_study_learning_plans");
}

export function cmdStudyLearningPlanItems(artifactId: string): Promise<StudyLearningPlanItemsResponse> {
  return invoke("cmd_study_learning_plan_items", { artifactId });
}

export function cmdStudyLearningPlanItemComplete(itemId: string, note = ""): Promise<StudyLearningPlanItem> {
  return invoke("cmd_study_learning_plan_item_complete", { itemId, note });
}

export function cmdStudyLearningPlanItemSkip(itemId: string, note = ""): Promise<StudyLearningPlanItem> {
  return invoke("cmd_study_learning_plan_item_skip", { itemId, note });
}
```

- [ ] **Step 4: Implement pure mappers.**

Create `web/src/chat/study/studyLearningStore.ts`:

```ts
// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { StudyContext } from "./studyStore";

export const LEGACY_CONTEXT_MIGRATION_REF = { origin: "legacy_local_storage", key: "kabuqina.study.context.v1" };

function cleanText(value: unknown, limit = 800): string {
  return typeof value === "string" ? value.trim().slice(0, limit) : "";
}

function lines(value: unknown): string[] {
  const text = cleanText(value);
  if (!text) return [];
  const out: string[] = [];
  const seen = new Set<string>();
  for (const raw of text.replaceAll("；", "\n").replaceAll(";", "\n").split(/\r?\n/)) {
    const item = raw.trim().replace(/^[-\s]+/, "");
    if (!item) continue;
    const key = item.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(item);
    if (out.length >= 24) break;
  }
  return out;
}

export function legacyContextToStudentState(context: StudyContext | Record<string, unknown>) {
  return {
    course: cleanText(context.course),
    goals: lines(context.goal),
    preferences: {
      ...(cleanText(context.profileSummary) ? { profile_summary: cleanText(context.profileSummary) } : {}),
      ...(cleanText(context.preferences) ? { study_preferences: cleanText(context.preferences) } : {}),
    },
    constraints: [],
    progress_notes: lines(context.progressNotes),
    current_stage: cleanText(context.currentStage),
    next_adjustment: cleanText(context.nextAdjustment),
  };
}

export function legacyContextToEvaluation(context: StudyContext | Record<string, unknown>) {
  const observations = [...lines(context.evaluationSummary), ...lines(context.assessmentEvidence)];
  const weak_points = lines(context.weakPoints);
  const suggestions = lines(context.nextAdjustment);
  if (!observations.length && !weak_points.length && !suggestions.length) return null;
  return {
    observations: observations.length ? observations : ["Legacy study context imported."],
    weak_points,
    suggestions,
    evidence_refs: [LEGACY_CONTEXT_MIGRATION_REF],
  };
}

export function formatPlanItemStatus(status: string, locale: "zh" | "en" = "zh"): string {
  const zh: Record<string, string> = { open: "待完成", completed: "已完成", skipped: "已跳过" };
  const en: Record<string, string> = { open: "Open", completed: "Completed", skipped: "Skipped" };
  return (locale === "en" ? en : zh)[status] || status;
}
```

- [ ] **Step 5: Add package script.**

In `web/package.json`, add:

```json
"test:study-learning-store": "node src/chat/study/studyLearningStore.test.mjs"
```

- [ ] **Step 6: Run GREEN for mapper.**

Run:

```powershell
cd web
node src/chat/study/studyLearningStore.test.mjs
```

Expected: PASS with `studyLearningStore.test.mjs: ok`.

- [ ] **Step 7: Commit Task 7.**

```powershell
git add web/src/chat/study/study-api.ts web/src/chat/study/studyLearningStore.ts web/src/chat/study/studyLearningStore.test.mjs web/package.json
git commit -m "feat: add study m4 web mappers and api"
```

---

## Task 8: Backend-Driven StudySection Minimal Surface

**Files:**
- Modify: `web/src/chat/study/StudySection.tsx`
- Modify: `web/src/chat/study/studyPrompts.ts`
- Modify: `web/src/locales/strings.ts`

- [ ] **Step 1: Update prompts.**

In `web/src/chat/study/studyPrompts.ts`, update these prompt constants:

```ts
learningProfile: [
  "请使用 STUDY learning 工具完成：先确认或创建当前课程空间，调用 learning_index_build 读取当前 Learning Index，然后用 learning_draft_create 创建 kind=student_state 的草稿。",
  "只总结可编辑的目标、偏好、约束和进度，不要写入固定能力标签、人格标签或不可改变的结论。",
].join("\n"),
learningPath: [
  "请使用 STUDY learning 工具完成：先确认或创建当前课程空间，调用 learning_index_build 读取当前 Learning Index，然后用 learning_draft_create 创建 kind=learning_plan 的草稿。",
  "计划必须包含 goals 与 phases，每个 phase 包含 tasks；每个 task 需要 title，可选 order 和 done_when。",
].join("\n"),
learningEvaluation: [
  "请使用 STUDY learning 工具完成：先确认或创建当前课程空间，调用 learning_index_build 读取当前 Learning Index，然后用 learning_draft_create 创建 kind=evaluation 的草稿。",
  "评估只能写 observations、weak_points、suggestions 和 evidence_refs；不要自动固化能力标签。",
].join("\n"),
```

- [ ] **Step 2: Replace context persistence with backend calls.**

In `web/src/chat/study/StudySection.tsx`, import M4 API and mapper helpers:

```ts
import {
  cmdStudyEvaluations,
  cmdStudyLearningPlanItemComplete,
  cmdStudyLearningPlanItemSkip,
  cmdStudyLearningPlanItems,
  cmdStudyLearningPlans,
  cmdStudyMigrateContext,
  cmdStudyStudentState,
  cmdStudyStudentStateSave,
  type StudyArtifact,
  type StudyLearningPlanItem,
} from "./study-api";
import {
  formatPlanItemStatus,
  legacyContextToStudentState,
} from "./studyLearningStore";
```

Add state:

```ts
const [backendStatus, setBackendStatus] = useState<"idle" | "loading" | "saved" | "failed">("idle");
const [evaluations, setEvaluations] = useState<StudyArtifact[]>([]);
const [plans, setPlans] = useState<StudyArtifact[]>([]);
const [planItems, setPlanItems] = useState<StudyLearningPlanItem[]>([]);
```

Add refresh helper:

```ts
const refreshBackendStudy = async () => {
  setBackendStatus("loading");
  try {
    await cmdStudyMigrateContext(loadStudyContext());
    const state = await cmdStudyStudentState();
    if (state.state?.payload) {
      setContext((current) => ({
        ...current,
        course: state.state?.payload.course || "",
        goal: (state.state?.payload.goals || []).join("\n"),
        preferences: state.state?.payload.preferences?.study_preferences || "",
        profileSummary: state.state?.payload.preferences?.profile_summary || "",
        progressNotes: (state.state?.payload.progress_notes || []).join("\n"),
        currentStage: state.state?.payload.current_stage || "",
        nextAdjustment: state.state?.payload.next_adjustment || "",
      }));
    }
    const evalRes = await cmdStudyEvaluations();
    setEvaluations(evalRes.evaluations || []);
    const planRes = await cmdStudyLearningPlans();
    const activePlans = planRes.plans || [];
    setPlans(activePlans);
    if (activePlans[0]) {
      const itemRes = await cmdStudyLearningPlanItems(activePlans[0].artifact_id);
      setPlanItems(itemRes.items || []);
    } else {
      setPlanItems([]);
    }
    setBackendStatus("idle");
  } catch {
    setBackendStatus("failed");
  }
};
```

Use `refreshBackendStudy()` in the existing mount effect after local `sync()`.

Replace `persistContext` body with:

```ts
const persistContext = async () => {
  setBackendStatus("loading");
  const local = saveStudyContext(context);
  setContext(local.context);
  try {
    const statePayload = legacyContextToStudentState(local.context);
    const saved = await cmdStudyStudentStateSave(statePayload);
    setSaveStatus(saved.state ? "saved" : "failed");
    setBackendStatus(saved.state ? "saved" : "failed");
  } catch {
    setSaveStatus("failed");
    setBackendStatus("failed");
  }
};
```

- [ ] **Step 3: Render minimal active evaluation and plan item surface.**

Below the context save buttons, render:

```tsx
{backendStatus === "failed" ? (
  <p className="text-[12px] text-[var(--kq-color-danger)]">{t("chat.studyBackendUnavailable")}</p>
) : null}

{evaluations.length ? (
  <div className="grid gap-1 text-[12px] text-[var(--kq-color-muted)]">
    <span className="font-medium text-[var(--kq-color-ink)]">{t("chat.studyActiveEvaluations")}</span>
    {evaluations.slice(0, 3).map((evaluation) => (
      <span key={evaluation.artifact_id}>{evaluation.title}</span>
    ))}
  </div>
) : null}

{plans.length ? (
  <div className="grid gap-1 text-[12px] text-[var(--kq-color-muted)]">
    <span className="font-medium text-[var(--kq-color-ink)]">{t("chat.studyCurrentPlan")}: {plans[0].title}</span>
    {planItems.map((item) => (
      <div key={item.item_id} className="flex items-center gap-2">
        <span className="min-w-0 flex-1 truncate">{item.title}</span>
        <span>{formatPlanItemStatus(item.status, "zh")}</span>
        <button type="button" onClick={() => cmdStudyLearningPlanItemComplete(item.item_id).then(refreshBackendStudy)}>
          {t("chat.studyPlanComplete")}
        </button>
        <button type="button" onClick={() => cmdStudyLearningPlanItemSkip(item.item_id).then(refreshBackendStudy)}>
          {t("chat.studyPlanSkip")}
        </button>
      </div>
    ))}
  </div>
) : null}
```

Adjust classes to match existing compact workspace controls; do not introduce a landing page or nested cards.

- [ ] **Step 4: Add locale strings.**

In `web/src/locales/strings.ts`, add zh/en keys:

```ts
"chat.studyBackendUnavailable": "学习状态暂时无法同步，本地输入仍保留。",
"chat.studyActiveEvaluations": "已激活评估",
"chat.studyCurrentPlan": "当前学习计划",
"chat.studyPlanComplete": "完成",
"chat.studyPlanSkip": "跳过",
```

and English equivalents:

```ts
"chat.studyBackendUnavailable": "Study state cannot sync right now. Local input is still kept.",
"chat.studyActiveEvaluations": "Active evaluations",
"chat.studyCurrentPlan": "Current learning plan",
"chat.studyPlanComplete": "Complete",
"chat.studyPlanSkip": "Skip",
```

- [ ] **Step 5: Run Web gate.**

Run:

```powershell
cd web
node src/chat/study/studyLearningStore.test.mjs
node src/chat/study/studyStore.test.mjs
npm run build
```

Expected: mapper tests pass and production build succeeds.

- [ ] **Step 6: Commit Task 8.**

```powershell
git add web/src/chat/study/StudySection.tsx web/src/chat/study/studyPrompts.ts web/src/locales/strings.ts
git commit -m "feat: connect study m4 state to web"
```

---

## Task 9: Final M4 Gate and Documentation

**Files:**
- Modify: `DECISIONS.md`
- Modify: `docs/superpowers/specs/2026-07-01-study-four-layer-learning-pipeline-design.md`
- Modify: `docs/superpowers/specs/2026-07-04-study-m4-state-evaluation-plan-design.md`
- Modify: `docs/superpowers/plans/2026-07-04-study-m4-state-evaluation-plan-slice.md`

- [ ] **Step 1: Run full M4 verification gate.**

```powershell
cd hermes_core
python -m pytest tests/learning -o "addopts=" -p no:cacheprovider -q
cd ..\python
python -m pytest tests/test_study_routes.py tests/test_desk_chat_learning_context.py tests/test_learning_owner_context.py -o "addopts=" -p no:cacheprovider -q
cd ..\web
node src/chat/study/studyLearningStore.test.mjs
node src/chat/study/studyStore.test.mjs
npm run build
cd ..\tauri
cargo test study
cd ..
git diff --check
```

Expected: all tests pass, build succeeds, and `git diff --check` reports no whitespace errors. Windows line-ending conversion warnings are acceptable.

- [ ] **Step 2: Update `DECISIONS.md`.**

Add a row under the STUDY four-layer learning pipeline table:

```markdown
| M4 closure (2026-07-04) | M4 is closed as the durable state/evaluation/plan slice. Trusted UI/API paths save active `student_state`, activate evidence-based `evaluation` artifacts, activate one current `learning_plan`, materialize plan tasks as `learning_plan_item`, and write `learning_plan.item.complete|skip` activities for real learner actions. `LearningIndex` now projects active state, active evaluations, current plan items, and safe activity summaries; it still excludes drafts and does not auto-fossilize learner ability labels. Legacy `kabuqina.study.context.v1` imports idempotently with migration id `localStorage:kabuqina.study.context.v1`. Gateway `/study`, semantic reviewer gates, knowledge/resource/tutoring, and the lifecycle UI rewrite remain later milestones. |
```

- [ ] **Step 3: Update the four-layer spec.**

In `docs/superpowers/specs/2026-07-01-study-four-layer-learning-pipeline-design.md`, change the status line to:

```markdown
**状态：** 已确认，M1-M4 已收口，M5 待实施
```

Add this M4 closure record under the M4 section:

```markdown
收口记录（2026-07-04）：M4 以 `student_state`、`evaluation`、`learning_plan` 纵向切片落地。Web legacy `kabuqina.study.context.v1` 迁移为 owner/space scoped backend state；active evaluation 只保存观察、薄弱点、建议与证据引用，不写固定能力标签；active learning plan materialize 为 `learning_plan_item`，完成/跳过作为真实 activity 写入。`LearningIndex` 纳入 active state/evaluation/current plan 和安全 activity 摘要，供后续 Planner 使用。Gateway `/study`、语义 reviewer 完整质量门、知识/资源/辅导和 M6 生命周期 UI 仍未提前实现。
```

- [ ] **Step 4: Update M4 design and plan closure evidence.**

Append to `docs/superpowers/specs/2026-07-04-study-m4-state-evaluation-plan-design.md`:

```markdown
## Closure Evidence

Implemented after M1-M3 review feedback was resolved. Fresh verification evidence:

- `hermes_core`: `python -m pytest tests/learning -o "addopts=" -p no:cacheprovider -q`
- `python`: `python -m pytest tests/test_study_routes.py tests/test_desk_chat_learning_context.py tests/test_learning_owner_context.py -o "addopts=" -p no:cacheprovider -q`
- `web`: `node src/chat/study/studyLearningStore.test.mjs`, `node src/chat/study/studyStore.test.mjs`, and `npm run build`
- `tauri`: `cargo test study`
- `git diff --check`
```

Then mark completed checkboxes in `docs/superpowers/plans/2026-07-04-study-m4-state-evaluation-plan-slice.md`.

- [ ] **Step 5: Review final diff.**

```powershell
git diff --check
git diff --stat
```

Expected: no whitespace errors and a scoped M4 diff.

- [ ] **Step 6: Commit M4 closure.**

```powershell
git add DECISIONS.md docs/superpowers/specs docs/superpowers/plans hermes_core python tauri web
git commit -m "feat: complete study m4 state evaluation plan slice"
```

---

## Self-Review Checklist

- [ ] Spec coverage: every M4 design requirement maps to at least one task above.
- [ ] Placeholder scan: no task depends on unspecified behavior or unnamed files.
- [ ] Type consistency: service method names, route names, Tauri command names, and Web wrapper names match across tasks.
- [ ] Review gate: M4 execution remains blocked until M1-M3 review feedback is incorporated.
