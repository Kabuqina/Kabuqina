# STUDY M4 Implementation Plan (+H3 ephemeral injection, +LG6 due reminders)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** implement STUDY M4 exactly per
[2026-07-04-study-m4-state-evaluation-plan-design.md](../specs/2026-07-04-study-m4-state-evaluation-plan-design.md)
— durable `student_state`, evidence-based `evaluation`, active `learning_plan`
with materialized plan items and item activities, `context.v1` migration, and
Learning Index projections — plus two riders scheduled with M4 by
[learning-runtime-alignment.md](../../learning-runtime-alignment.md):
**H3** (Learning Index → ephemeral prompt slot) and **LG6** (goal-runner due
review reminder, opt-in).

**Slice id:** B-1 of the
[v0.4.0 development plan](2026-07-06-v0.4.0-development-plan.md).

**Tech Stack:** Python 3.11 (hermes_core learning services + desk_server
routes), Tauri thin proxies, TypeScript web (minimal surface), TDD throughout.

## Progress Notes

**2026-07-10 — B-1 complete.** Before code changes, the M1-M3 review closure
was re-read and confirmed not to alter lifecycle, route, migration, refresh, or
index contracts. Tasks 1-3 and 5-6 landed with TDD. The v0.4 master plan now
assigns all notebook UI/minimal Web surfaces to D track, so Task 4's
`StudySection` work was deliberately superseded; B-1 supplies desk/Tauri
contracts without editing D's components. Focused evidence: core learning 174
tests, cron reminder 11 tests, desk/H3/route/reminder suites, and `cargo test
study` pass (Tauri test used `TAURI_CONFIG` to omit the 1.5GB bundle resources
from test-only build-script scanning). Graph/loop internals were not changed.

---

## Guardrails

- **Soak discipline: zero engine changes.** No edits to
  `hermes_core/agent/graph_engine/**`, `run_agent.py` loop internals, or
  engine selection. H3 is implemented entirely in the desk layer by
  reassigning `agent.ephemeral_system_prompt` per request — the attribute is
  read at API-call time (`run_agent.py:9272/10112`), so per-request
  reassignment gives per-turn freshness without touching core.
- **Trust boundary unchanged:** model tools create drafts only. Save/activate/
  reject/complete/skip are trusted desk API operations. No new model tools
  for state mutation.
- **Contract rules:** `student_state` must reject fixed ability labels
  (`capability_labels` etc.); `evaluation` gains bounded `evidence_refs`;
  activation never writes hidden learner labels. Reviewer-unavailable drafts
  stay `pending` (existing §4.3 semantics — do not touch).
- **M4 review gate:** before writing code, re-read the M4 spec's Review Gate
  section and confirm none of the v0.3.0 review findings changed artifact
  lifecycle, route naming, migration rules, or index shape. Record the
  confirmation (one paragraph) at the top of the progress notes.
- New-code naming uses `kabuqina` where a new identifier is product-scoped
  (v0.4.0 rename Ring 1 discipline); existing `hermes_*` module names are NOT
  renamed in this slice.
- Commit locally per task; do NOT push; stop for review at plan end.

---

### Task 1: Core services (TDD)

**Files:**
- Add: `hermes_core/learning/student_state.py`, `evaluations.py`,
  `learning_plans.py`
- Add: `hermes_core/tests/learning/test_student_state.py`,
  `test_evaluations.py`, `test_learning_plans.py`
- Modify: `hermes_core/learning/learning_contract.py` (evaluation
  `evidence_refs`, plan-item bounds)

- [ ] **Step 1: failing tests first** — per M4 spec "Core Services": state
  save/archive-previous, legacy context normalization (12 legacy fields →
  canonical shape; weak/evidence/evaluation fields routed to `evaluation`,
  NOT `student_state`), fixed-label rejection, evaluation activate/reject,
  plan activate archives previous active plan, item materialization
  (`item_type="learning_plan_item"`, ids `f"{artifact_id}-{index:04d}"`
  convention), `learning_plan.item.complete|skip` activities, invalid item
  actions raise instead of silently recording, owner/space isolation.
- [ ] **Step 2: implement the three services** mirroring the
  FlashcardService/QuizService shapes (constructor takes
  `LearningExecutionContext`, injected `now`).
- [ ] **Step 3: gate**

```powershell
cd hermes_core
python -m pytest tests/learning -o "addopts=" -p no:cacheprovider -q
```

Expected: all pass, no regressions.

### Task 2: Learning Index projections

**Files:**
- Modify: `hermes_core/learning/learning_index.py`
- Modify: `hermes_core/tests/learning/test_learning_index.py`

- [ ] **Step 1:** add bounded projections per M4 spec: `student_state`
  (active payload, sanitized/size-limited), `evaluations` (recent active
  refs), `current_plan` (+ materialized item statuses), `weak_points`
  (deduplicated from active evaluations + recent `quiz.attempt` summaries +
  `flashcard.capture` origins), safe summary fields for
  `quiz.attempt`/`flashcard.review`/`learning_plan.item.*` activities.
- [ ] **Step 2:** tests prove drafts NEVER enter projections; index stays
  deterministic, read-only, owner/space scoped, byte-bounded.

### Task 3: Desk API + Tauri

**Files:**
- Modify: `python/src/desk_server/routes/study_routes.py`
- Modify: `tauri/src/study.rs`, `tauri/src/lib.rs`
- Add: `python/tests/test_study_m4_routes.py`

- [ ] **Step 1:** routes exactly per M4 spec: `GET/PUT /student-state`,
  `POST /migrations/context` (migration id
  `localStorage:kabuqina.study.context.v1`, idempotent, writes active
  `student_state` + optional active `evaluation` only when legacy
  weak/evidence/evaluation fields are non-empty), `GET /evaluations[/{id}]`,
  `GET /learning-plans`, `GET /learning-plans/{id}/items`,
  `POST /learning-plans/items/{item_id}/complete|skip`; extend generic
  activate/reject dispatch to the three new kinds. Error mapping
  `ValueError→400 / KeyError→404 / ContractError→409`.
- [ ] **Step 2:** Tauri thin proxies (`cmd_study_student_state_get/put`,
  `cmd_study_migrate_context`, `cmd_study_evaluations`,
  `cmd_study_learning_plans`, `cmd_study_plan_items`,
  `cmd_study_plan_item_complete/skip`), existing path-id validation.
- [ ] **Step 3: gates**

```powershell
cd python
python -m pytest tests/test_study_m4_routes.py tests/test_study_routes.py -o "addopts=" -p no:cacheprovider -q
cd ..\tauri
cargo test study
```

### Task 4: Web minimal surface

**Files:**
- Modify: `web/src/chat/study/study-api.ts` (typed M4 wrappers)
- Add: `web/src/chat/study/studyContextMapper.ts` + `.test.mjs` (pure legacy
  `StudyContext` → `student_state`/`evaluation` payload mapper)
- Modify: `web/src/chat/study/StudySection.tsx` (load spaces + backend
  student state; one-time context migration; save via PUT; list active
  evaluations; list plan items with complete/skip)
- Modify: `web/src/locales/strings.ts`, `web/src/chat/chatUx.test.mjs`

- [ ] **Step 1:** mapper tests first (12 legacy fields, empty-field routing
  rules, no fabricated values).
- [ ] **Step 2:** StudySection wiring; DB-unavailable keeps textarea state in
  memory and shows save failure; failed migration never erases old
  localStorage.
- [ ] **Step 3: gates**

```powershell
cd web
node src/chat/study/studyContextMapper.test.mjs
npm run test:chat-ux; npm run test:study-store
npm run lint; npm run build
```

### Task 5: Rider H3 — Learning Index → ephemeral slot (desk layer only)

**Files:**
- Modify: `python/src/desk_server/chat_core.py` (or the per-request handler)
- Add: `python/tests/test_desk_learning_ephemeral.py`

- [ ] **Step 1:** before each desk chat turn, recompose
  `agent.ephemeral_system_prompt = base_ephemeral + learning_block` where
  `learning_block` renders a **byte-bounded** (≤2KB) snapshot from
  `LearningIndex.build()` for the current owner/space: due-card count,
  top weak points, current plan item. No space → no block. Draft content
  must never appear (guaranteed by Task 2 tests, re-asserted here).
- [ ] **Step 2:** tests: block present when state exists, absent when not,
  size cap enforced, recomputed between two consecutive turns (freshness),
  and the cached base system prompt is untouched (prefix-cache safety).

### Task 6: Rider LG6 — due review reminder (opt-in, quiet)

**Files:**
- Discovery first: reuse the existing cron `mode:notify` + desktop delivery
  path (see `cron/scheduler.py`, reminder session feed) — do NOT build a new
  scheduler.
- Add: a `study_review_reminder` job handler that queries
  `FlashcardService.list_cards(due_only=True)` count for the desktop owner
  and delivers a single quiet line ("今日有 N 张卡片到期") ONLY when N>0.
- Modify: STUDY settings surface — one opt-in toggle + time-of-day picker,
  **default OFF**.

- [ ] **Step 1:** discovery note: exact reuse points in cron/goal runner.
- [ ] **Step 2:** handler + tests (owner scoping, N=0 sends nothing,
  opt-out removes the job).
- [ ] **Step 3:** UI toggle + i18n (zh/en), chatUx/companion assertions
  updated if the reminder feed shape changes (it should not).

### Task 7: Final gate and handoff

- [ ] Full focused re-run: learning + agent + study routes + web suites +
  `cargo test study`; update
  [四层设计](../specs/2026-07-01-study-four-layer-learning-pipeline-design.md)
  with an M4 收口记录 paragraph (same style as M2/M3); DECISIONS.md entry.
- [ ] Commit locally, do not push, stop for review.

---

## Acceptance Criteria

- All M4 spec behaviors implemented with the M2/M3 service/route/test shape;
  migration idempotent (`{"migrated": false}` on re-run) and never destroys
  legacy localStorage on failure.
- Drafts never reach planner context; ability labels rejected at contract
  level; item actions are activities, never artifact versions.
- H3: ephemeral learning block fresh per turn, bounded, absent without a
  space, zero core/engine edits.
- LG6: default-off, quiet, N=0 silent, owner-scoped.
- Zero non-allowlisted test failures; work committed locally only.
