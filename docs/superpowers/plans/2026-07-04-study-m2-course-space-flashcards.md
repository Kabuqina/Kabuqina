# STUDY M2 Course Space + Flashcards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** deliver the STUDY M2 vertical slice: course-space selection, flashcard deck draft review/activation, real flashcard practice activities, legacy flashcard localStorage migration, and non-blocking `learning.output.created` UI refresh.

**Architecture:** keep learning semantics in `hermes_core/learning`, desktop-only HTTP and owner injection in `python/src`, Tauri as a thin authenticated proxy, and React as a compact workspace surface. The model can create `flashcard_deck` drafts through the existing `learning` toolset; trusted UI/API activates or rejects drafts and records real practice.

**Tech Stack:** Python 3.11 + SQLite WAL, FastAPI desk routes, Tauri 2 Rust commands, React/Vite TypeScript, existing unit-test harnesses.

**Closure evidence (2026-07-04):** M2 is implemented as a vertical slice across core, desk API, Tauri, and React. Flashcard decks are still created as `draft` artifacts by the learning toolset; trusted STUDY routes activate/reject them and materialize active cards into `learning_items`. Reviews write `flashcard.review` activities and update persisted scheduling state. The legacy key `kabuqina.study.flashcards.v1` migrates idempotently through migration id `localStorage:kabuqina.study.flashcards.v1`. Desk chat binds `desktop_learning_scope` and emits non-blocking `learning.output.created` stream events, which the web shell converts to `study-learning-event` for refresh.

**Verified gate:** `hermes_core` learning tests, desk STUDY/chat tests, web mapper test, `npm run build`, and `cargo test study` all passed during closure. `cargo test study` required a temporary empty `python/dist/runtime` resource directory because Tauri's build script validates bundle resources before compiling tests; the directory was removed afterwards. M3 remains quiz-specific, and Gateway `/study` commands remain M5 scope.

---

## File Structure

- `hermes_core/learning/flashcards.py`: flashcard-specific materialization and review scheduling over active `flashcard_deck` artifacts.
- `hermes_core/learning/learning_store.py`: focused item helpers for `learning_items`; no flashcard-specific SQL here.
- `hermes_core/learning/learning_context.py`: thin context wrappers for item helpers.
- `hermes_core/learning/output_writer.py`: context-scoped `learning.output.created` callback bridge used by desk chat.
- `python/src/desk_server/routes/study_routes.py`: trusted desktop STUDY API for spaces, drafts, activation/rejection, migration, cards, and reviews.
- `python/src/desk_server/chat_core.py`: wrap desk agent turns in `desktop_learning_scope` and emit created events without blocking the turn.
- `tauri/src/study.rs` and `tauri/src/lib.rs`: authenticated `cmd_study_*` proxy commands.
- `web/src/chat/study/study-api.ts`: typed invoke wrapper for M2 desk commands.
- `web/src/chat/study/flashcardLearningStore.ts`: pure mappers for backend cards/decks, migration payloads, and review summaries.
- `web/src/chat/study/FlashcardPanel.tsx`: switch from copy-JSON/localStorage as primary path to course-space + draft + active deck workflow.
- Tests mirror each layer: `hermes_core/tests/learning/test_flashcards.py`, `python/tests/test_study_routes.py`, `python/tests/test_desk_chat_learning_context.py`, `web/src/chat/study/flashcardLearningStore.test.mjs`.

---

## Task 1: Core Flashcard Item Service

**Files:**
- Create: `hermes_core/learning/flashcards.py`
- Modify: `hermes_core/learning/learning_store.py`
- Modify: `hermes_core/learning/learning_context.py`
- Test: `hermes_core/tests/learning/test_flashcards.py`
- Test: `hermes_core/tests/learning/test_learning_store.py`

- [x] **Step 1: Write failing item helper tests.**

Add tests proving `LearningStore` can upsert, list, and update `learning_items` under `(owner_id, space_id)`, with cross-owner and cross-space reads returning nothing.

- [x] **Step 2: Run RED.**

Run: `python -m pytest tests/learning/test_learning_store.py::test_learning_items_are_owner_and_space_scoped -o "addopts=" -p no:cacheprovider -q`

Expected: FAIL because item helpers do not exist.

- [x] **Step 3: Implement generic item helpers.**

Add store/context methods:

```python
upsert_item(owner_id, space_id, *, item_id, item_type, artifact_id=None, state=None) -> str
list_items(owner_id, space_id, *, item_type=None, artifact_id=None) -> list[dict]
update_item_state(owner_id, space_id, item_id, state) -> None
```

Every method validates owner/space/item strings, JSON-serializes `state`, and scopes SQL by both owner and space.

- [x] **Step 4: Write failing flashcard service tests.**

Cover:
- activating a draft `flashcard_deck` marks it active and materializes cards into `learning_items`;
- rejecting a draft never materializes cards;
- reviewing a due card updates SM-2 style state and writes `flashcard.review` activity;
- due cards sort fresh cards first, then older due dates.

- [x] **Step 5: Run RED.**

Run: `python -m pytest tests/learning/test_flashcards.py -o "addopts=" -p no:cacheprovider -q`

Expected: FAIL because `learning.flashcards` does not exist.

- [x] **Step 6: Implement `FlashcardService`.**

Implement constants and public methods:

```python
FLASHCARD_REVIEW_ACTIVITY = "flashcard.review"

class FlashcardService:
    def __init__(self, context: LearningExecutionContext, *, now: Callable[[], datetime] | None = None): ...
    def activate_deck(self, artifact_id: str) -> dict: ...
    def reject_deck(self, artifact_id: str) -> dict: ...
    def list_decks(self, *, status: str | None = None) -> list[dict]: ...
    def list_cards(self, *, due_only: bool = False) -> list[dict]: ...
    def review_card(self, item_id: str, grade: str) -> dict: ...
```

Use the same four grades as the existing web scheduler: `again`, `hard`, `good`, `easy`. Invalid grade is conservative `again`. Store state fields: `front`, `back`, `hint`, `tags`, `ease`, `intervalDays`, `repetitions`, `lapses`, `createdAt`, `dueAt`, `lastReviewedAt`.

- [x] **Step 7: Run GREEN.**

Run: `python -m pytest tests/learning/test_flashcards.py tests/learning/test_learning_store.py -o "addopts=" -p no:cacheprovider -q`

Expected: PASS.

---

## Task 2: Trusted Desk STUDY API

**Files:**
- Create: `python/src/desk_server/routes/study_routes.py`
- Modify: `python/src/desk_server/app.py`
- Test: `python/tests/test_study_routes.py`

- [x] **Step 1: Write failing FastAPI route tests.**

Use `TestClient(create_app())` with `HERMESDESK_BRIDGE_SECRET`. Cover:
- `GET /api/desk/study/spaces`;
- `POST /api/desk/study/spaces`;
- `POST /api/desk/study/spaces/{space_id}/select`;
- `GET /api/desk/study/drafts?kind=flashcard_deck`;
- `POST /api/desk/study/artifacts/{artifact_id}/activate`;
- `POST /api/desk/study/artifacts/{artifact_id}/reject`;
- `POST /api/desk/study/flashcards/review`;
- `POST /api/desk/study/migrations/flashcards`.

- [x] **Step 2: Run RED.**

Run: `python -m pytest tests/test_study_routes.py -o "addopts=" -p no:cacheprovider -q`

Expected: FAIL with 404 for new routes.

- [x] **Step 3: Implement routes.**

Each route opens `LearningStore()`, establishes `desktop_learning_scope(store)`, delegates to context or `FlashcardService`, maps `ValueError` to 400, `KeyError` to 404, and `ContractError` to 409. Request `owner_id` is ignored.

- [x] **Step 4: Implement legacy flashcard migration.**

`POST /api/desk/study/migrations/flashcards` accepts `{ "deck": { "cards": [...] } }`; if not already migrated, it creates or uses the current/default course space, writes a `flashcard_deck` artifact titled `Legacy flashcards`, activates it, materializes cards, marks migration `localStorage:kabuqina.study.flashcards.v1`, and returns counts. Already migrated returns `{"migrated": false}`.

- [x] **Step 5: Run GREEN.**

Run: `python -m pytest tests/test_study_routes.py tests/test_learning_owner_context.py -o "addopts=" -p no:cacheprovider -q`

Expected: PASS.

---

## Task 3: Desk Chat Learning Context + Non-Blocking Created Event

**Files:**
- Modify: `hermes_core/learning/output_writer.py`
- Modify: `python/src/desk_server/chat_core.py`
- Test: `hermes_core/tests/learning/test_output_writer.py`
- Test: `python/tests/test_desk_chat_learning_context.py`

- [x] **Step 1: Write failing output-writer callback-scope test.**

Assert `OutputWriter(ctx)` uses an active context callback when no explicit callback is passed, and a raising callback never rolls back a stored artifact.

- [x] **Step 2: Implement callback scope.**

Add `learning_created_callback_scope(callback)` and have `OutputWriter.__init__` default to the active callback.

- [x] **Step 3: Write failing desk chat test.**

Patch `run_agent.AIAgent` with a fake that calls `learning_draft_create` during `run_conversation`. Assert the desk chat runner has an active learning context and emits a stream payload with `type: "learning.output.created"`.

- [x] **Step 4: Implement chat wrapping.**

In `_desk_chat_run_in_thread`, open `LearningStore()`, wrap the `run_conversation` call with `desktop_learning_scope(store)` and `learning_created_callback_scope(emit_created)`. `emit_created` forwards `{"type": "learning.output.created", ...signal}` through `progress_event_callback` if present.

- [x] **Step 5: Run GREEN.**

Run: `python -m pytest tests/test_desk_chat_learning_context.py -o "addopts=" -p no:cacheprovider -q`

Expected: PASS.

---

## Task 4: Tauri Study Proxy Commands

**Files:**
- Create: `tauri/src/study.rs`
- Modify: `tauri/src/lib.rs`
- Modify: `web/src/chat/chat-api.ts`

- [x] **Step 1: Write command validation tests.**

Add Rust unit tests for path-safe `space_id`, `artifact_id`, and `item_id` validation: lowercase/uppercase UUID-like ids pass; path separators, query strings, and empty ids fail.

- [x] **Step 2: Implement thin proxy commands.**

Add `cmd_study_spaces`, `cmd_study_space_create`, `cmd_study_space_select`, `cmd_study_drafts`, `cmd_study_artifact_activate`, `cmd_study_artifact_reject`, `cmd_study_flashcards`, `cmd_study_flashcard_review`, and `cmd_study_migrate_flashcards`. Each calls `chat::desk_json_request`.

- [x] **Step 3: Register commands.**

Add `mod study;` and all `study::cmd_study_*` entries to `tauri::generate_handler!`.

- [x] **Step 4: Add TypeScript command wrappers.**

Expose typed wrappers from `web/src/chat/chat-api.ts` or `web/src/chat/study/study-api.ts` using `invoke`.

---

## Task 5: React STUDY Flashcard Workflow

**Files:**
- Create: `web/src/chat/study/study-api.ts`
- Create: `web/src/chat/study/flashcardLearningStore.ts`
- Modify: `web/src/chat/study/FlashcardPanel.tsx`
- Modify: `web/src/chat/hooks/useSendMessage.ts`
- Modify: `web/src/locales/strings.ts`
- Test: `web/src/chat/study/flashcardLearningStore.test.mjs`
- Modify: `web/package.json`

- [x] **Step 1: Write failing pure mapper/migration tests.**

Test that legacy `FlashcardDeck` maps to the migration payload, backend card rows map to review queue rows, and review summary text is generated from backend counts without reading old localStorage progress.

- [x] **Step 2: Run RED.**

Run: `cd web; node src/chat/study/flashcardLearningStore.test.mjs`

Expected: FAIL because the module does not exist.

- [x] **Step 3: Implement pure mappers.**

Keep SM-2 math in core for persisted cards; frontend only renders and submits grades. Provide `legacyDeckToMigrationPayload`, `backendCardsToQueue`, and `formatReviewSummary`.

- [x] **Step 4: Update `useSendMessage` event forwarding.**

When stream event type is `learning.output.created`, dispatch `window.dispatchEvent(new CustomEvent("study-learning-event", { detail: event }))`.

- [x] **Step 5: Update `FlashcardPanel`.**

Replace the primary import/localStorage flow with:
- load/create/select course space;
- display draft `flashcard_deck` artifacts with activate/reject buttons;
- display active cards from backend;
- start review from due backend cards;
- submit grades through `cmd_study_flashcard_review`;
- run one-time legacy flashcard migration from localStorage, then keep old localStorage read-only for fallback.

- [x] **Step 6: Run GREEN.**

Run:

```powershell
cd web
node src/chat/study/flashcardLearningStore.test.mjs
npm run build
```

Expected: PASS/build succeeds.

---

## Task 6: M2 Gate, Docs, Commit

**Files:**
- Modify: `docs/superpowers/specs/2026-07-01-study-four-layer-learning-pipeline-design.md`
- Modify: `DECISIONS.md`

- [x] **Step 1: Run full M2 gate.**

```powershell
cd hermes_core
python -m pytest tests/learning -o "addopts=" -p no:cacheprovider -q
cd ..\python
python -m pytest tests/test_study_routes.py tests/test_desk_chat_learning_context.py tests/test_learning_owner_context.py -o "addopts=" -p no:cacheprovider -q
cd ..\web
node src/chat/study/flashcardLearningStore.test.mjs
npm run build
cd ..\tauri
cargo test study
```

- [x] **Step 2: Update docs.**

Record M2 closure evidence and the API/event names. Note that M3 remains quiz-specific and Gateway `/study` commands remain M5 unless intentionally pulled forward.

- [x] **Step 3: Review diff.**

Run: `git diff --check && git diff --stat`

- [x] **Step 4: Commit.**

```powershell
git add DECISIONS.md docs/superpowers/specs/2026-07-01-study-four-layer-learning-pipeline-design.md hermes_core python tauri web
git commit -m "feat: complete study m2 flashcard slice"
```
