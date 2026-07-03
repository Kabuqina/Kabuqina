# STUDY M1 — Shared Foundation Implementation Plan

> **For agentic workers:** bounded, one-task-per-cycle. For each task: write the
> failing tests first, implement, run the deterministic gate, record evidence,
> then STOP for human review. Commit locally per task; do NOT push. Steps use
> checkbox (`- [ ]`) syntax.

**Goal:** deliver M1 (the shared four-layer *learning* foundation) of the STUDY
four-layer pipeline: the single-source learning contract, a lightweight Planner
strategy framework with a **behaviour-equivalent** Deliverable Planner
adaptation, an isolated `learning.db` store with owner/space isolation, minimal
Learning Index + Output Writer skeletons, and capability-registry references with
drift tests — **without changing existing PPT/document planning behaviour** and
**without any agent-engine coupling**.

**Architecture:** engine-decoupled. All agent turns still run through the stable
public `AIAgent.run_conversation` seam (graph is the current default); this plan
touches no engine code. Core/overlay split follows the design §9. Runs in
parallel with the (currently G2-blocked) Goal Runner track — the only shared
files are additive.

**Tech stack:** Python 3.11, SQLite WAL (reusing SessionDB concurrency
principles), pytest; existing shared Agent Core (`agent/prompt_builder.py`);
`python/src` desk layer; React/TypeScript UI arrives in later milestones (M2+).

Date: 2026-07-03

Source design: `docs/superpowers/specs/2026-07-01-study-four-layer-learning-pipeline-design.md` (§13 milestone M1)

## Dependencies & non-conflicts (verified 2026-07-03)

- **Not blocked by Phase 3.5 Task 11 Step 5** (legacy-loop removal). STUDY runs
  through the stable `run_conversation` seam and only *adapts*
  `build_deliverable_planner_prompt` (which lives in `agent/prompt_builder.py`,
  not the engine). Step 5 deletes only `_run_conversation_loop` + the selector
  flag + loop-only tests — none of STUDY's surface.
- **Orthogonal to Goal Runner** (different domain, storage `learning.db` vs
  `cron/goal-runs/`, toolset `learning` vs `goal_internal`, isolation
  `owner_id`+`space_id` vs per-`HERMES_HOME`). The only shared files are
  `python/src/desk_server/app.py` (router list), `web/src/locales/strings.ts`,
  `capability_registry.py`, and the toolset keep-list — **keep every touch
  append-only** so merges stay trivial. `capability_registry.py` currently has
  no goal/cron refs, so STUDY owns its additions there.

## Proposed paths (confirm before Task 1)

New core package `hermes_core/learning/`:
`learning_contract.py`, `learning_store.py`, `learning_context.py`,
`learning_index.py`, `output_writer.py`, `planner_spec.py`, `planner_registry.py`.
Toolset: `hermes_core/tools/learning_tools.py`. Desktop owner: `python/src` desk
layer. Tests mirror under `hermes_core/tests/learning/` and `python/tests/`.

---

## Non-negotiable invariants (M1)

- The existing Deliverable Planner (PPT/document) prompt is **provably
  unchanged** — a before/after equivalence test gates the adaptation.
- `owner_id` never appears in a model tool schema; it is injected only by
  `LearningExecutionContext` from the runtime; a model-supplied owner is rejected.
- Every learning read/write is constrained by **both** `owner_id` and `space_id`.
- AI-generated content is written as `draft`; only **deterministic** validation
  runs at write time. Per-kind **semantic** review is M5, not M1.
- Learning Index reads only saved + `active` data; it never calls an LLM and
  never mutates Material Index.
- `learning.db` is a **separate** database under the common Hermes root (not
  `state.db`): SQLite WAL, short transactions, busy-timeout, write-lock retry,
  startup schema reconciliation.
- Shared-file touches (`app.py`, `strings.ts`, `capability_registry.py`,
  keep-list) are **append-only**; no reorganisation.

---

## Task 1 — `learning_contract.py`: single source of truth + per-kind schemas

**Files:** Create `hermes_core/learning/learning_contract.py`,
`hermes_core/tests/learning/test_learning_contract.py`.

- [ ] **Step 1: write failing contract + per-kind schema tests.** Cover valid
  and invalid samples for each v1 `kind` (`student_state`, `knowledge_base`,
  `learning_plan`, `resource_pack`, `flashcard_deck`, `quiz`, `tutoring_note`,
  `evaluation`). `quiz` question types (choice / true-false / short-answer) each
  validate under their own sub-schema; front-end never guesses fields. Assert the
  frozen vocabulary (kinds, statuses, review levels) is stable.
- [ ] **Step 2: define the contract.** Envelope `version = 1`; lifecycle statuses
  `draft | active | rejected | archived`; the allowed transitions
  (`draft→active`, `draft→rejected`, `active→archived`); review levels
  `deterministic | semantic` and review status; `LearningOutputEnvelope` common
  fields (`version`, `kind`, `space_id`, `title`, `source_refs`, `payload`,
  `review`); a discriminated-union payload schema per kind with size limits and a
  per-kind migration hook. All are module constants — the *only* source of these
  values; Planner/Writer/registry import from here.
- [ ] **Step 3: verify + commit.** `pytest tests/learning/test_learning_contract.py`.

## Task 2 — `learning.db` store + `LearningExecutionContext` (owner/space isolation)

**Files:** Create `hermes_core/learning/learning_store.py`,
`hermes_core/learning/learning_context.py`,
`hermes_core/tests/learning/test_learning_store.py`.

- [ ] **Step 1: write failing store + isolation tests.** Assert: a fresh db
  reconciles the v1 schema on startup (`learning_spaces`, `learning_artifacts`,
  `learning_items`, `learning_activities`, `learning_migrations`); WAL mode +
  busy-retry survive a concurrent writer; every query/write requires an
  `owner_id`+`space_id` and a cross-owner or cross-space read returns nothing; a
  model-supplied `owner_id` is ignored in favour of the context. Point the store
  at `tmp_path` — never the real Hermes root.
- [ ] **Step 2: implement the store + context.** Separate `learning.db` under the
  common Hermes root; short transactions, busy timeout, write-lock retry, startup
  reconciliation (reuse SessionDB principles). `LearningExecutionContext` carries
  the resolved `owner_id` and current `space_id` and is the *only* owner source.
  CRUD scoped to `(owner_id, space_id)`; create/select space; version + status on
  artifacts.
- [ ] **Step 3: prove concurrency + isolation.** Two connections (web-child /
  gateway-child shape) writing the same db under different owners stay isolated.
- [ ] **Step 4: verify + commit.**

## Task 3 — Output Writer skeleton

**Files:** Create `hermes_core/learning/output_writer.py`,
`hermes_core/tests/learning/test_output_writer.py`.

- [ ] **Step 1: write failing writer tests.** Envelope + per-kind payload
  validation (reject unknown kind / bad payload / oversize); owner injected from
  context and a model-supplied owner rejected; AI content persisted as `draft`;
  the state machine enforces only allowed transitions; each write yields an
  artifact id + version; a real user *activity* (not an AI artifact) writes
  straight to `learning_activities`/item state; a `learning.output.created`-shaped
  signal is emitted (in-process callback in M1; the non-blocking desktop event
  bridge is M2).
- [ ] **Step 2: implement.** Validate against Task 1's schemas; inject owner from
  Task 2's context; write via Task 2's store; enforce transitions; emit the
  create signal. No LLM calls here.
- [ ] **Step 3: verify + commit.**

## Task 4 — Learning Index skeleton

**Files:** Create `hermes_core/learning/learning_index.py`,
`hermes_core/tests/learning/test_learning_index.py`.

- [ ] **Step 1: write failing index tests.** `learning_index_build` is
  deterministic: it includes only `active` artifacts and allowed direct
  activities; it excludes `draft`/`rejected`/`archived`; it never calls an LLM,
  never mutates Material Index, and never treats unreviewed content as course
  fact; output is a versioned, size-bounded snapshot for one `space_id`.
- [ ] **Step 2: implement the minimal skeleton.** Read-only over Task 2's store;
  assemble the space snapshot (metadata, active artifacts, allowed activities,
  due-review/weak-point placeholders) with a version + size cap.
- [ ] **Step 3: verify + commit.**

## Task 5 — Planner strategy framework + Deliverable Planner adaptation

**Files:** Create `hermes_core/learning/planner_spec.py`,
`hermes_core/learning/planner_registry.py`,
`hermes_core/tests/learning/test_planner_registry.py`; touch
`hermes_core/agent/prompt_builder.py` (adapt, do not rewrite).

- [ ] **Step 1: write the failing equivalence test first (critical).** Assert the
  Deliverable Planner prompt produced *through the new `PlannerSpec`* is
  byte-identical to today's `build_deliverable_planner_prompt(...)` across the
  same `valid_tool_names` inputs (empty, typical, full). This is the guarantee
  that "existing PPT/document planning behaviour is unchanged".
- [ ] **Step 2: define `PlannerSpec` + registry.** `PlannerSpec` declares only:
  planner id + domain, activation condition, prompt builder, accepted
  index/context contract, allowed artifact kinds, and the deterministic/semantic
  review policy — it does not execute tools, own a retry loop, or replace
  `AIAgent`. Register a **Deliverable PlannerSpec** whose prompt builder delegates
  to the existing `build_deliverable_planner_prompt`, and a **Learning
  PlannerSpec** stub (activation + accepted `LearningIndex` contract + allowed
  learning kinds; prompt builder minimal in M1). Add registry activation /
  allowed-kind / review-policy tests.
- [ ] **Step 3: verify both prompt families + commit.** Run the equivalence test
  plus the existing prompt-builder tests (`tests/agent/test_prompt_builder.py`)
  to prove no PPT/document regression.

## Task 6 — `learning` toolset (minimal) + keep-list

**Files:** Create `hermes_core/tools/learning_tools.py`,
`hermes_core/tests/.../test_learning_tools.py`; **append** `learning` to the
toolset keep-list (locate the same list that carries `goal_internal`).

- [ ] **Step 1: write failing toolset tests.** The M1 subset — list/create/select
  space, `learning_index_build`, create a typed draft, list drafts/active — with:
  `owner_id` absent from every tool schema; owner injected from context; and
  trust-boundary ops (activate/reject/archive) **not** exposed as model tools
  (they belong to trusted UI/API or deterministic Gateway commands, M2+).
- [ ] **Step 2: implement + register.** Thin tools delegating to Tasks 2–4;
  append `learning` to the keep-list (append-only). Skills/preload untouched.
- [ ] **Step 3: verify + commit.**

## Task 7 — Capability registry references + drift tests

**Files:** touch `python/src/capability_registry.py` (**append-only**); Create
`python/tests/test_capability_registry_learning.py`.

- [ ] **Step 1: write the failing drift test.** The registry references the new
  Planner ids, learning artifact kinds, and stage ids **by stable id only** (no
  duplicated prompts or schemas); the drift test asserts every referenced id
  actually exists in the contract/registry, and vice-versa for the learning
  entries.
- [ ] **Step 2: add references.** Append learning pipeline entries to the
  capability catalog referencing stable ids from Tasks 1/5; no prompt/schema
  duplication.
- [ ] **Step 3: verify + commit.**

## Task 8 — Desktop owner id + injection (python/src)

**Files:** `python/src` desk layer (owner establishment/injection);
`python/tests/test_learning_owner_context.py`.

- [ ] **Step 1: write failing tests.** A stable local desktop `owner_id` is
  established and injected into `LearningExecutionContext`; the gateway shape
  (`gateway:<platform>:<hashed-user-id>`) is derived, not guessed from nickname;
  a request can never override the injected owner.
- [ ] **Step 2: implement injection.** Desktop owner id + wiring into the context
  for the desk path (learning desk routes land in M2 with the UI; M1 only proves
  owner establishment/injection).
- [ ] **Step 3: verify + commit.**

---

## M1 gate — run before declaring M1 done

```powershell
cd hermes_core
python -m pytest tests/learning -o "addopts=" -p no:cacheprovider -q
python -m pytest tests/agent/test_prompt_builder.py tests/run_agent/test_run_agent.py::"<deliverable planner cases>" -o "addopts=" -p no:cacheprovider -q
cd ..\python
python -m pytest tests/test_capability_registry_learning.py tests/test_learning_owner_context.py -o "addopts=" -p no:cacheprovider -q
```

**Acceptance (design §13 M1):**

- [ ] Existing PPT / PDF / HTML / DOCX Planner behaviour is unchanged (the
  equivalence test + `test_prompt_builder.py` are green).
- [ ] Two children (web-child / gateway-child shape) read and write **isolated**
  course spaces under **different owners** safely (store + context + owner-injection
  tests green).
- [ ] `capability_registry` validation + drift tests green; no id duplication.
- [ ] No agent-engine files touched; shared-file additions are append-only.

When M1 is green and reviewed, proceed to **M2 — course space + flashcards**
(space selection, flashcard draft→review→activate, real scoring/review
activities, localStorage flashcard migration, the non-blocking desktop event
`learning.output.created`).

---

## Risks & constraints (M1-specific, from design §15)

- **PlannerSpec must not become a second executor.** If a field does not drive
  activation, prompt, contract, or review, leave it out.
- **Contract drift.** Planner, Output Writer, capability registry, and (later)
  Web types must be bound by shared ids / generated types / drift tests — Task 7
  is the enforcement point.
- **Two-process concurrency.** Desktop and Gateway share no memory; the selected
  space + owner must be explicitly persisted or injected (Tasks 2/8).
- **Keep the UI for last.** M1 ships no STUDY UI change; the information-architecture
  rebuild is M6. M1 proves the data/contract spine only.
