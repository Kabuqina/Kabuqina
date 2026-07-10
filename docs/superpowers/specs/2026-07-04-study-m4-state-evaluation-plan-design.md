# STUDY M4 State, Evaluation, and Learning Plan Design

**Date:** 2026-07-04

**Status:** Implemented and verified (2026-07-10). The M1-M3 review gate was
re-checked before implementation; no finding changed the artifact lifecycle,
route naming, migration rules, or Learning Index shape.

**Scope:** STUDY M4 only: durable student state, evidence-based evaluations, active learning plans, plan-item activities, and Learning Index projections for subsequent planning. Gateway `/study` commands, semantic reviewer quality gates, knowledge bases, resource packs, tutoring notes, and the lifecycle UI rewrite remain out of scope.

## Context

M1 established the learning contract, owner-scoped `learning.db`, `LearningExecutionContext`, `LearningIndex`, `OutputWriter`, and the model-facing `learning` toolset. M2 and M3 added trusted desktop practice slices for `flashcard_deck` and `quiz`: AI content enters as drafts, trusted UI/API activates or rejects it, and real learner behavior is recorded as activities.

The remaining Web STUDY context still lives in `localStorage` under `kabuqina.study.context.v1`. It contains useful course goals, preferences, weak points, progress notes, assessment evidence, evaluation summary, and adjustment notes, but it is not owner/space scoped and is only injected into prompts as free text. M4 moves that material into the same durable pipeline without turning it into a fixed learner label system.

## Options Considered

1. **Recommended: state/evaluation/plan vertical slice.** Add thin core services for the three existing M4 artifact kinds, migrate the current localStorage context, activate evaluations and plans through trusted APIs, materialize plan tasks into `learning_items`, and record plan-item actions as real activities. This reuses the M1-M3 shape and gives later planners durable evidence.
2. **Full lifecycle UI now.** Rebuild the STUDY panel around setup, plan, learn, practice, evaluate, and adjust in one pass. This is attractive, but it mixes M4 data semantics with M6 layout work and would be hard to review while M1-M3 are still pending.
3. **Planner-only M4.** Leave Web localStorage alone and only teach the planner to read evaluations or plans when they happen to exist. This avoids UI work but fails the migration goal and keeps STUDY split across storage systems.

M4 uses option 1. It produces reviewable backend semantics first and only a minimal Web surface.

## Design

### Core Services

Create three small services under `hermes_core/learning/`:

- `StudentStateService`: saves the current editable `student_state` as a trusted active artifact, activates or rejects AI-authored `student_state` drafts, archives the previous active `student_state`, reads the current state, and migrates legacy context payloads. It must reject fixed labels such as `capability_labels`, matching the existing contract.
- `EvaluationService`: lists active/draft `evaluation` artifacts, activates or rejects an evaluation draft, and exposes the active evaluation summary for UI and Learning Index projection. It does not run an LLM; AI can already create evaluation drafts through `learning_draft_create`.
- `LearningPlanService`: activates/rejects `learning_plan` drafts, archives any previous active learning plan when a new one is activated, materializes each phase task into `learning_items` with `item_type="learning_plan_item"`, and records `learning_plan.item.complete` or `learning_plan.item.skip` activities when the user acts on a plan item.

Only trusted UI/API paths can save state, activate/reject evaluations, activate/reject plans, or mark plan items. Model tools continue to create drafts only.

### Student State

`student_state` stores editable facts and preferences, not a diagnosis. The M4 canonical payload shape is:

```json
{
  "course": "Algebra",
  "goals": ["Pass the midterm"],
  "preferences": {
    "profile_summary": "Prefers worked examples",
    "study_time": "30 minutes on weekdays"
  },
  "constraints": ["Needs mobile-friendly review"],
  "progress_notes": ["Finished linear equations"],
  "current_stage": "Practice",
  "next_adjustment": "Add mixed review twice a week"
}
```

The service accepts legacy Web fields and normalizes them into this shape. It deliberately keeps `weakPoints`, `assessmentEvidence`, and `evaluationSummary` out of `student_state` when they are better represented as `evaluation`.

### Evaluations

`evaluation` artifacts are evidence summaries. They may be AI-authored drafts or trusted user-created summaries, but they become planning input only after trusted activation.

```json
{
  "observations": [
    "Recent quiz attempts show errors on prime identification."
  ],
  "weak_points": ["prime numbers"],
  "suggestions": ["Add short mixed drills before the next quiz"],
  "evidence_refs": [
    { "activity_id": "abc", "activity_type": "quiz.attempt" }
  ]
}
```

The existing contract allows `observations`, `weak_points`, and `suggestions`. M4 should extend deterministic validation to permit bounded `evidence_refs` for `evaluation`. It must continue to forbid fixed ability/personality labels. Evaluation activation never updates hidden learner labels; it only makes the evaluation visible to the Learning Index and future planner prompts.

### Learning Plans

`learning_plan` remains an artifact because plans are authored content. Activation makes one plan current and archives older active plans in the same owner/space. Each task becomes a plan item:

```json
{
  "goals": ["Master factoring"],
  "phases": [
    {
      "title": "Refresh basics",
      "tasks": [
        {
          "title": "Review factor pairs",
          "order": 1,
          "done_when": "Can list factor pairs for 10 numbers"
        }
      ]
    }
  ]
}
```

Materialized item state includes `artifact_id`, `phaseIndex`, `taskIndex`, `title`, `done_when`, `status`, `completedAt`, `skippedAt`, and optional `note`. Item status is direct learner state; it is not a new artifact version. Replanning creates a new draft/active plan and preserves old plan items and activities for history.

### Learning Index Projection

M4 extends `LearningIndex.build()` with bounded projections:

- `student_state`: the current active `student_state` payload, sanitized and size-limited.
- `evaluations`: recent active evaluation references with observations, weak points, suggestions, and evidence refs.
- `current_plan`: the active learning plan reference plus materialized item statuses.
- `weak_points`: deduplicated weak points from active evaluations and recent quiz attempt activity summaries.
- `activities`: lightweight activities remain present, but safe summary fields may be included for `quiz.attempt`, `flashcard.review`, and `learning_plan.item.*`.

The index remains deterministic, owner/space scoped, read-only, and byte-bounded. Draft evaluations and draft plans never enter planner context.

### Desk API

Extend the existing STUDY router instead of adding a second router:

- `GET /api/desk/study/student-state`
- `PUT /api/desk/study/student-state`
- `POST /api/desk/study/migrations/context`
- `GET /api/desk/study/evaluations`
- `GET /api/desk/study/evaluations/{artifact_id}`
- `GET /api/desk/study/learning-plans`
- `GET /api/desk/study/learning-plans/{artifact_id}/items`
- `POST /api/desk/study/learning-plans/items/{item_id}/complete`
- `POST /api/desk/study/learning-plans/items/{item_id}/skip`

Generic artifact activate/reject dispatch is extended to `student_state`, `evaluation`, and `learning_plan`.

Legacy migration uses migration id `localStorage:kabuqina.study.context.v1`. It creates or uses the current/default course space, writes an active `student_state`, writes an active `evaluation` only when legacy weak/evidence/evaluation fields are non-empty, marks the migration idempotently, and leaves old localStorage readable for one release.

### Tauri and Web

Tauri remains a thin proxy in `tauri/src/study.rs`, using the existing path-id validation for artifact and item ids.

Web changes stay minimal:

- `study-api.ts` gains typed wrappers for M4 routes.
- A pure mapper module converts legacy `StudyContext` into backend `student_state` and optional `evaluation` payloads.
- `StudySection.tsx` loads spaces and backend student state, runs one-time context migration, saves edits through `PUT /student-state`, lists active evaluations, lists active plan items, and lets the user complete or skip plan items.
- Existing flashcard and quiz panels remain separate. M6 can later reorganize layout.

Prompts for learning profile, learning path, and evaluation should tell the agent to use `learning_index_build` and `learning_draft_create` with `kind=student_state`, `kind=learning_plan`, or `kind=evaluation`, instead of asking the user to paste JSON.

## Error Handling

Reuse the M2/M3 mapping: `ValueError` -> 400, `KeyError` -> 404, `ContractError` -> 409. Invalid plan item actions fail instead of silently creating activities. Legacy migration is idempotent and returns `{ migrated: false }` after the first successful migration.

When the database is unavailable, Web should keep the existing local textarea state in memory and show save failure. It must not erase the old localStorage value during a failed migration.

## Testing

M4 implementation should use TDD:

- Core service tests for state save/archive, legacy context normalization, evaluation activation/rejection, plan activation, item materialization, item complete/skip activities, and owner/space isolation.
- Learning Index tests proving draft content is excluded, active state/evaluation/current plan projections are included, plan item status appears, weak points are bounded/deduplicated, and build remains read-only.
- Desk route tests for student state, context migration, evaluation list/detail, learning plan item actions, and idempotency.
- Tauri command tests through `cargo test study`.
- Web pure mapper tests for legacy context migration payloads and plan item status formatting.
- Web build gate via `npm run build`.

Final M4 gate should include:

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

## Review Gate

This design is intentionally planning-only. Before M4 implementation starts, re-read M1-M3 review findings and update this spec if those findings change the artifact lifecycle, route naming, migration rules, Web refresh behavior, or Learning Index shape.

## Closure Record (2026-07-10)

M4 landed as three trusted core services (`student_state`, `evaluation`, and
`learning_plan`), bounded active-only Learning Index projections, owner-scoped
desk routes, and Tauri proxy contracts. Legacy
`kabuqina.study.context.v1` migration preserves all twelve fields, is
idempotent, and never puts weak/evaluation evidence into `student_state`.
Plan tasks materialize as stable `learning_plan_item` rows; complete/skip are
direct activities and invalid repeat or archived-plan actions fail.

The two B-1 riders also landed: H3 recomputes a ≤2KB due-card/weak-point/current-
plan projection in the desk ephemeral prompt before every turn, without
touching the cached base prompt or graph/loop internals; LG6 reuses cron
`mode=notify` plus desktop delivery, remains default-off, dynamically counts
due cards for the persisted owner, emits `[SILENT]` for zero, and removes its
job on opt-out. The learning-data charter T1 gap was closed by applying and
auditing an owner-only ACL on the default production `learning.db` root.

Per the newer v0.4 workstream boundary, notebook page/UI work is owned by D
track. B-1 therefore exposes backend/Tauri contracts but does not modify
`StudySection` or create a competing minimal page.
