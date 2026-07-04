# STUDY M3 Quiz Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** deliver the STUDY M3 quiz vertical slice: durable quiz drafts, trusted activation/rejection, deterministic quiz attempts, legacy quiz migration, and backend-driven QuizPanel.

**Architecture:** keep quiz semantics in `hermes_core/learning/quizzes.py`; extend the existing desk STUDY router and Tauri `study.rs` as thin trusted proxies; keep React focused on rendering, response collection, and backend calls. M3 intentionally uses deterministic grading only; semantic/LLM grading stays for later quality gates.

**Tech Stack:** Python 3.11 + SQLite WAL, FastAPI desk routes, Tauri 2 Rust commands, React/Vite TypeScript, existing `node:test`-style pure Web tests.

---

## File Structure

- Create `hermes_core/learning/quizzes.py`: quiz activation, question materialization, deterministic grading, and `quiz.attempt` activity writes.
- Create `hermes_core/tests/learning/test_quizzes.py`: core service TDD coverage.
- Modify `python/src/desk_server/routes/study_routes.py`: add quiz routes, quiz migration, and artifact activation/rejection dispatch.
- Modify `python/tests/test_study_routes.py`: add M3 route tests.
- Modify `tauri/src/study.rs` and `tauri/src/lib.rs`: add `cmd_study_quizzes`, `cmd_study_quiz_questions`, `cmd_study_quiz_submit`, `cmd_study_migrate_quizzes`.
- Modify `web/src/chat/study/study-api.ts`: add quiz types and invoke wrappers.
- Create `web/src/chat/study/quizLearningStore.ts`: pure quiz mappers for legacy migration, backend questions, submit payloads, and summaries.
- Create `web/src/chat/study/quizLearningStore.test.mjs`: pure mapper tests.
- Modify `web/src/chat/study/QuizPanel.tsx`: switch primary quiz workflow to backend.
- Modify `web/src/chat/study/studyPrompts.ts`: instruct the agent to create a `kind=quiz` learning draft, not paste JSON.
- Modify `web/src/locales/strings.ts`: add backend quiz UI strings.
- Modify docs/decisions after implementation: M3 closure in `DECISIONS.md` and the four-layer spec.

---

## Task 1: Core Quiz Service

**Files:**
- Create: `hermes_core/learning/quizzes.py`
- Create: `hermes_core/tests/learning/test_quizzes.py`

- [ ] **Step 1: Write failing activation and rejection tests.**

Add tests proving `QuizService.activate_quiz()` activates a draft `quiz` artifact and materializes one item per question with `item_type="quiz_question"`, while `reject_quiz()` rejects without materializing items.

- [ ] **Step 2: Run RED.**

Run: `cd hermes_core; python -m pytest tests/learning/test_quizzes.py -o "addopts=" -p no:cacheprovider -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'learning.quizzes'`.

- [ ] **Step 3: Implement minimal `QuizService` activation/rejection.**

Implement constants:

```python
QUIZ_QUESTION_ITEM_TYPE = "quiz_question"
QUIZ_ATTEMPT_ACTIVITY = "quiz.attempt"
```

Implement:

```python
class QuizService:
    def __init__(self, context: LearningExecutionContext, *, now=None): ...
    def activate_quiz(self, artifact_id: str) -> dict: ...
    def reject_quiz(self, artifact_id: str) -> dict: ...
    def list_quizzes(self, *, status: str | None = None) -> list[dict]: ...
    def list_questions(self, *, artifact_id: str | None = None, include_answers: bool = False) -> list[dict]: ...
```

Use item ids `f"{artifact_id}-{index:04d}"`. Store question state with prompt, type, options, answer, accepted, explanation, tags, points, createdAt, and artifact_id. Public question payloads hide answer/accepted unless `include_answers=True`.

- [ ] **Step 4: Write failing deterministic grading tests.**

Cover exact choice matching, true/false matching, short-answer normalized matching, incorrect answers, weak tag aggregation, and `quiz.attempt` activity details.

- [ ] **Step 5: Run RED for grading.**

Expected: FAIL because `submit_attempt()` is missing.

- [ ] **Step 6: Implement deterministic grading.**

Add:

```python
def submit_attempt(self, artifact_id: str, responses: dict) -> dict: ...
```

Normalize responses as `{question_item_id: {"selected": [...], "text": "...", "value": true}}`. Score all-or-nothing per question; default `points=1`; invalid/out-of-range responses are incorrect. Record a `quiz.attempt` activity with score, maxScore, percent, correctCount, total, responses, and perQuestion.

- [ ] **Step 7: Run GREEN.**

Run: `cd hermes_core; python -m pytest tests/learning/test_quizzes.py -o "addopts=" -p no:cacheprovider -q`

Expected: PASS.

---

## Task 2: Desk STUDY Quiz Routes

**Files:**
- Modify: `python/src/desk_server/routes/study_routes.py`
- Modify: `python/tests/test_study_routes.py`

- [ ] **Step 1: Write failing route tests.**

Add tests for:

- activating a `quiz` draft through `/api/desk/study/artifacts/{artifact_id}/activate`;
- `GET /api/desk/study/quizzes`;
- `GET /api/desk/study/quizzes/{artifact_id}/questions`;
- `POST /api/desk/study/quizzes/{artifact_id}/submit`;
- `POST /api/desk/study/migrations/quizzes` idempotency.

- [ ] **Step 2: Run RED.**

Run: `cd python; python -m pytest tests/test_study_routes.py -o "addopts=" -p no:cacheprovider -q`

Expected: FAIL with 404 for quiz routes and/or non-quiz activation behavior.

- [ ] **Step 3: Implement route dispatch.**

In `study_artifact_activate`, inspect artifact kind and dispatch `flashcard_deck` to `FlashcardService.activate_deck()` and `quiz` to `QuizService.activate_quiz()`. Do the same for reject.

- [ ] **Step 4: Implement quiz endpoints and migration.**

Use migration key `localStorage:kabuqina.study.quiz.v1`. Migration body accepts `{ "quiz": { "title": "...", "questions": [...] } }`, writes a `kind="quiz"` artifact, activates it, marks migration, and returns `{ migrated, artifact_id, questions, status }`.

- [ ] **Step 5: Run GREEN.**

Run: `cd python; python -m pytest tests/test_study_routes.py tests/test_learning_owner_context.py -o "addopts=" -p no:cacheprovider -q`

Expected: PASS.

---

## Task 3: Tauri Proxy Commands

**Files:**
- Modify: `tauri/src/study.rs`
- Modify: `tauri/src/lib.rs`

- [ ] **Step 1: Add Rust command coverage.**

Extend the existing study path-id validation test to cover quiz item/artifact ids. The existing `cargo test study` should continue to compile command registration.

- [ ] **Step 2: Implement commands.**

Add:

```rust
cmd_study_quizzes(app: AppHandle) -> Result<Value, String>
cmd_study_quiz_questions(app: AppHandle, artifact_id: String) -> Result<Value, String>
cmd_study_quiz_submit(app: AppHandle, artifact_id: String, responses: Value) -> Result<Value, String>
cmd_study_migrate_quizzes(app: AppHandle, quiz: Value) -> Result<Value, String>
```

Each validates path ids and calls `crate::chat::desk_json_request`.

- [ ] **Step 3: Register commands.**

Add all four commands to `tauri::generate_handler!`.

- [ ] **Step 4: Run GREEN.**

Run: `cd tauri; cargo test study`

Expected: PASS. In this repo, create a temporary empty `python/dist/runtime` directory only for the command if the Tauri build script requires bundle resources, then remove it afterwards.

---

## Task 4: Web Quiz API And Pure Mappers

**Files:**
- Modify: `web/src/chat/study/study-api.ts`
- Create: `web/src/chat/study/quizLearningStore.ts`
- Create: `web/src/chat/study/quizLearningStore.test.mjs`
- Modify: `web/package.json`

- [ ] **Step 1: Write failing mapper tests.**

Test:

- legacy `QuizState.quiz` maps to backend `quiz` migration payload with `choice`/`short_answer` types;
- backend questions map to UI question rows without answers;
- responses map to backend submit payload;
- result summaries produce zh/en text from backend result.

- [ ] **Step 2: Run RED.**

Run: `cd web; node src/chat/study/quizLearningStore.test.mjs`

Expected: FAIL because `quizLearningStore.ts` does not exist.

- [ ] **Step 3: Implement mappers and API wrappers.**

Add `StudyQuiz`, `StudyQuizQuestion`, `StudyQuizResult`, and command wrappers to `study-api.ts`. Implement mapper functions in `quizLearningStore.ts` without React/Tauri imports except type-only imports.

- [ ] **Step 4: Run GREEN.**

Run: `cd web; node src/chat/study/quizLearningStore.test.mjs`

Expected: PASS.

---

## Task 5: Backend-Driven QuizPanel

**Files:**
- Modify: `web/src/chat/study/QuizPanel.tsx`
- Modify: `web/src/chat/study/studyPrompts.ts`
- Modify: `web/src/locales/strings.ts`

- [ ] **Step 1: Update prompt.**

Change `QUIZ_GENERATION_PROMPT` so it asks the agent to use STUDY learning tools: confirm/create course space, call `learning_index_build`, then create `kind=quiz` via `learning_draft_create`. It must not ask the student to copy/paste JSON.

- [ ] **Step 2: Replace primary QuizPanel data flow.**

Load spaces, drafts, active quizzes, and questions from backend. Keep old `quizStore` only for migration payload reading and local result summary compatibility.

- [ ] **Step 3: Implement quiz taking and submit.**

Collect responses by backend `item_id`; call `cmdStudyQuizSubmit(artifactId, responses)`; render returned score and per-question answers/explanations. Write summary back to study context using backend result.

- [ ] **Step 4: Implement legacy migration and refresh event.**

On first load, convert `loadQuizState().quiz` to migration payload and call `cmdStudyMigrateQuizzes()` if it contains questions. Listen for `STUDY_LEARNING_EVENT` and refresh.

- [ ] **Step 5: Run Web gate.**

Run:

```powershell
cd web
node src/chat/study/quizLearningStore.test.mjs
node src/chat/study/quizStore.test.mjs
npm run build
```

Expected: PASS/build succeeds.

---

## Task 6: M3 Gate, Docs, Commit

**Files:**
- Modify: `DECISIONS.md`
- Modify: `docs/superpowers/specs/2026-07-01-study-four-layer-learning-pipeline-design.md`
- Modify: `docs/superpowers/specs/2026-07-04-study-m3-quiz-design.md`
- Modify: `docs/superpowers/plans/2026-07-04-study-m3-quiz-slice.md`

- [ ] **Step 1: Run full M3 gate.**

```powershell
cd hermes_core
python -m pytest tests/learning -o "addopts=" -p no:cacheprovider -q
cd ..\python
python -m pytest tests/test_study_routes.py tests/test_desk_chat_learning_context.py tests/test_learning_owner_context.py -o "addopts=" -p no:cacheprovider -q
cd ..\web
node src/chat/study/quizLearningStore.test.mjs
node src/chat/study/quizStore.test.mjs
npm run build
cd ..\tauri
cargo test study
```

- [ ] **Step 2: Update docs.**

Record M3 closure evidence, API names, event behavior, deterministic short-answer grading, and migration key. Reconfirm Gateway `/study` commands remain M5.

- [ ] **Step 3: Review diff.**

Run: `git diff --check && git diff --stat`

- [ ] **Step 4: Commit.**

```powershell
git add DECISIONS.md docs/superpowers/specs docs/superpowers/plans hermes_core python tauri web
git commit -m "feat: complete study m3 quiz slice"
```

