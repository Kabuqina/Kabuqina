# STUDY Knowledge-Point Capture Implementation Plan (M1 postfix)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** rewire the kq-kp knowledge-point chips from legacy localStorage
(`flashcardStore`) to a trusted single-card capture path into `learning.db`,
per [2026-07-05-study-knowledge-point-capture-design.md](../specs/2026-07-05-study-knowledge-point-capture-design.md).

**Sequencing:** this plan runs **after** the M1 selective merge
([2026-07-05-study-m1-behavior-data-merge.md](2026-07-05-study-m1-behavior-data-merge.md))
is complete on the integration branch, and **before** any M2 merge. It does
NOT wait for M2. The M1 merge plan intentionally left chips on the legacy
store ("temporary bridge"); this plan removes that bridge.

**Architecture:** minimal vertical slice on the M1 data foundation: one core
service method family (`FlashcardService.capture_card` + `list_cards`), one
desk route file, one Tauri proxy module, one web API wrapper + session-level
capture index, chips rewiring. Every new file deliberately reuses the **same
path, module, class and wire shapes** as the M2 implementation on
`student/study-module`, so the later M2 merge is a union of methods/routes,
not a rename fight.

**Tech Stack:** Python 3.11 + FastAPI (desk_server), SQLite/WAL via M1
learning store, Tauri 2/Rust thin proxy, TypeScript + node:test/transpileModule.

---

## Guardrails

- **Preconditions (verify before Task 2):** M1 foundation exists on the
  branch — `hermes_core/learning/{learning_contract,learning_store,learning_context,output_writer,learning_index}.py`,
  `hermes_core/tools/learning_tools.py`, `python/src/learning_owner.py`.
  If any is missing, STOP: the M1 merge plan has not run.
- **Shape compatibility with branch M2 is a hard requirement.** Reference
  implementations are read via git (do not cherry-pick them):

  ```powershell
  git show student/study-module:hermes_core/learning/flashcards.py
  git show student/study-module:python/src/desk_server/routes/study_routes.py
  git show student/study-module:tauri/src/study.rs
  git show student/study-module:web/src/chat/study/study-api.ts
  ```

  Must match the branch exactly: item id scheme `f"{artifact_id}-{index:04d}"`,
  `item_type="flashcard"`, item state fields
  (`front/back/hint/tags/ease/intervalDays/repetitions/lapses/createdAt/dueAt/lastReviewedAt`
  with `ease=2.5`, `intervalDays=0`, `dueAt=createdAt=now`), artifact kind
  `flashcard_deck`, `GET /api/desk/study/flashcards` response shape
  `{"cards": [...]}`.
- **Trust boundary unchanged:** capture is desk-API/UI only. Do NOT add a
  capture tool to `hermes_core/tools/learning_tools.py`; model tools keep
  draft-only powers.
- **Do not modify** `web/src/chat/study/knowledgePoints.ts` (parser) or
  `hermes_core/agent/prompt_builder.py` — parsing/behavior layers are done.
- **Do not remove** `flashcardStore.ts` or the legacy FlashcardPanel; they
  stay until M2/M6 per the four-layer plan §12.
- New test files use capture-specific names (`test_flashcard_capture.py`,
  `test_study_capture_routes.py`, `captureIndex.test.mjs`) so the M2 merge's
  own test files (`test_flashcards.py`, `test_study_routes.py`) land without
  conflict.
- Known accepted gap (record, don't fix): between this patch and the M2
  merge, captured cards live in `learning.db` but the legacy FlashcardPanel
  cannot review them. Dev-only window; M1 is unreleased.

---

### Task 1: Branch and Precondition Audit

**Files:**
- No file modifications.

- [ ] **Step 1: verify base branch and clean tree**

```powershell
git status --short --branch
```

Expected: on `codex/study-m1-merge` (or a branch created from it), clean tree.
If the M1 merge landed on `main` already, create `codex/study-kp-capture`
from `main` instead.

- [ ] **Step 2: verify M1 foundation presence**

```powershell
Test-Path hermes_core\learning\learning_contract.py
Test-Path hermes_core\learning\output_writer.py
Test-Path hermes_core\learning\learning_context.py
Test-Path python\src\learning_owner.py
Test-Path hermes_core\learning\flashcards.py
Test-Path python\src\desk_server\routes\study_routes.py
```

Expected: first four `True`, last two `False` (this plan creates them).

- [ ] **Step 3: read the reference shapes**

```powershell
git show student/study-module:hermes_core/learning/flashcards.py
git show student/study-module:python/src/desk_server/routes/study_routes.py
```

Confirm the item id/state field conventions listed in Guardrails before
writing any code.

---

### Task 2: Core — minimal `FlashcardService` with `capture_card`

**Files:**
- Add: `hermes_core/learning/flashcards.py`
- Add: `hermes_core/tests/learning/test_flashcard_capture.py`

- [ ] **Step 1: write the failing tests first**

Cover, using the same in-memory/tmp learning store fixtures as
`hermes_core/tests/learning/test_output_writer.py`:

- capture creates one active single-card `flashcard_deck` artifact and one
  materialized item; returned `item_id` is `f"{artifact_id}-0000"`.
- duplicate front (strip + casefold) returns `{"duplicate": True}` with the
  existing item id and does not write a second artifact.
- `FLASHCARD_SPACE_CAP` (500) is enforced with `ValueError`.
- `flashcard.capture` activity is recorded with
  `detail={"origin": "kq-kp", "confidence": ...}`.
- owner/space isolation: a second owner context does not see the first
  owner's cards and can capture the same front independently.
- missing front/back raises `ValueError`.

- [ ] **Step 2: implement `hermes_core/learning/flashcards.py`**

Port from the branch reference ONLY: module docstring shape, constants
(`FLASHCARD_ITEM_TYPE`, `_clean_text`, `_clean_tags`, `_item_id`),
`_initial_state`, and a private materialize helper. Then add what M2 does
not have:

```python
FLASHCARD_CAPTURE_ACTIVITY = "flashcard.capture"
FLASHCARD_SPACE_CAP = 500

class FlashcardService:
    def __init__(self, context: LearningExecutionContext, *, now=None): ...

    def list_cards(self, *, due_only: bool = False) -> List[Dict[str, Any]]:
        # identical to branch M2 (port verbatim, including _sort_key/_is_due)

    def capture_card(self, *, front, back, hint="", tags=None, source_refs=None) -> Dict[str, Any]:
        # 1. clean/validate (front/back required)
        # 2. dedupe by normalized front over list_cards()
        # 3. cap check (FLASHCARD_SPACE_CAP)
        # 4. OutputWriter(self._ctx).write_artifact(kind="flashcard_deck",
        #        title=front[:60], payload={"cards": [card]},
        #        source_refs=source_refs or [])
        # 5. transition to active + materialize the single item
        # 6. record FLASHCARD_CAPTURE_ACTIVITY
        # 7. return {"duplicate": False, "artifact_id", "item_id", "front", "dueAt"}
```

Review mode: single-card capture is the non-batch case (contract §6:
`flashcard_deck` semantic review applies 批量时 only) — deterministic
validation via `write_artifact` is sufficient; activation is the trusted
caller's decision, mirroring the M2 migration route precedent.

- [ ] **Step 3: run the core tests**

```powershell
cd hermes_core
python -m pytest tests/learning/test_flashcard_capture.py -o "addopts=" -p no:cacheprovider -q
python -m pytest tests/learning -o "addopts=" -p no:cacheprovider -q
```

Expected: all pass; no regressions in existing learning tests.

---

### Task 3: Desk API — minimal `study_routes.py`

**Files:**
- Add: `python/src/desk_server/routes/study_routes.py`
- Modify: `python/src/desk_server/app.py`
- Add: `python/tests/test_study_capture_routes.py`

- [ ] **Step 1: write failing route tests**

Use the same FastAPI test-client pattern as existing
`python/tests/test_desk_server.py`. Cover: successful capture (200,
`duplicate: false`), idempotent re-capture (200, `duplicate: true`),
missing front → 400, auto space creation on first capture,
`GET /api/desk/study/flashcards` returns the captured card, and
`{"cards": []}` when no space exists yet.

- [ ] **Step 2: implement the routes**

Port `_desktop_ctx`, `_http_error`, `_ensure_space`, `_space_payload`
helpers from the branch reference verbatim (they only depend on M1
foundation + `learning_owner`). Then implement ONLY:

```text
GET  /api/desk/study/flashcards?due_only=
POST /api/desk/study/flashcards/capture
```

Capture body → whitelist `source` fields
(`origin/session_id/source_label/confidence/gist`) into a single
`source_refs` entry; never accept raw `source_refs` from the client.
Error mapping: `ValueError→400`, `KeyError→404`, `ContractError→409`.

- [ ] **Step 3: register the router**

In `python/src/desk_server/app.py`, add `study_routes` to the import and
the `include_router` tuple.

- [ ] **Step 4: run the route tests**

```powershell
cd python
python -m pytest tests/test_study_capture_routes.py -o "addopts=" -p no:cacheprovider -q
python -m pytest tests/test_desk_server.py -o "addopts=" -p no:cacheprovider -q
```

Expected: all pass.

---

### Task 4: Tauri — minimal `study.rs` proxy

**Files:**
- Add: `tauri/src/study.rs`
- Modify: `tauri/src/lib.rs`

- [ ] **Step 1: implement the proxy module**

Port the branch `tauri/src/study.rs` structure but keep only:

```rust
cmd_study_flashcards(due_only: Option<bool>)
cmd_study_flashcard_capture(body: serde_json::Value)
```

Follow the existing thin-proxy pattern (loopback desk URL + shared client)
used by neighboring commands; validate nothing beyond what sibling proxies
validate (no path ids are involved in these two commands).

- [ ] **Step 2: register**

In `tauri/src/lib.rs`: add `mod study;` and both commands to the
`invoke_handler` list (same placement as the branch, so the M2 merge extends
the list instead of conflicting).

- [ ] **Step 3: verify**

```powershell
cd tauri
cargo check
cargo test study
```

Expected: compiles; study tests (if any are added by the proxy pattern) pass.

---

### Task 5: Web — `study-api.ts`, `captureIndex.ts`, chips rewiring

**Files:**
- Add: `web/src/chat/study/study-api.ts`
- Add: `web/src/chat/study/captureIndex.ts`
- Add: `web/src/chat/study/captureIndex.test.mjs`
- Modify: `web/src/chat/study/KnowledgePointChips.tsx`
- Modify: `web/src/locales/strings.ts`
- Modify: `web/src/chat/chatUx.test.mjs`

- [ ] **Step 1: minimal `study-api.ts`**

Match the branch file's naming/`invoke` pattern but export only
`cmdStudyFlashcards(dueOnly?)` and
`cmdStudyFlashcardCapture(payload)` with typed request/response
(`StudyCaptureResponse { duplicate, artifact_id?, item_id, dueAt? }`).

- [ ] **Step 2: `captureIndex.ts` + tests**

Session-level module (no React): lazy-initialized `Set<normalizedFront>`
filled from one `cmdStudyFlashcards()` call, `has(front)`,
`markCaptured(front)`, `subscribe(fn)`, refresh on window event
`study-learning-event` (same event name M2 uses). Failure of the initial
fetch leaves the index in `unavailable` state exposed via `status()`.
Test with injected fetcher (no Tauri): lazy init, dedupe check, event
refresh, unavailable fallback.

- [ ] **Step 3: rewire `KnowledgePointChips.tsx`**

- Replace `loadDeck/upsertCards/saveDeck` usage with
  `captureIndex` + `cmdStudyFlashcardCapture`.
- Per-chip state machine: `idle → saving → added | failed(retryable)`;
  `added` also when `captureIndex.has(front)`.
- Optional `session_id` from `readPersistedSession()`
  (`web/src/chat/hooks/useChatState.ts`) — no prop plumbing.
- Source payload: `{ origin: "kq-kp", session_id?, confidence, gist }`.
- `captureIndex.status() === "unavailable"` → buttons disabled with
  `chat.kpUnavailable` tooltip. No localStorage fallback writes.
- i18n: add `chat.kpAddFailed`（zh: "保存失败，点击重试" / en:
  "Save failed — click to retry"）and `chat.kpUnavailable`（zh:
  "学习存储未就绪" / en: "Learning storage not ready"）.

- [ ] **Step 4: update chatUx assertions**

Replace the `upsertCards\(loadDeck\(\), \[card\]\)` assertion with
`cmdStudyFlashcardCapture`; add an assertion that
`KnowledgePointChips.tsx` no longer imports from `./flashcardStore`.
Keep all kq-kp parser/strip assertions unchanged.

- [ ] **Step 5: run web gates**

```powershell
cd web
node src/chat/study/captureIndex.test.mjs
npm run test:knowledge-points
npm run test:chat-ux
npm run test:flashcard-store
npm run lint
npm run build
```

Expected: all pass (`test:flashcard-store` still passes — the store remains
for migration/panel use).

Add `"test:capture-index": "node src/chat/study/captureIndex.test.mjs"` to
`web/package.json` scripts.

---

### Task 6: Docs and M2-merge Handoff Notes

**Files:**
- Modify: `docs/superpowers/specs/2026-07-05-study-knowledge-point-capture-design.md`
- Modify: `docs/immersive-learning-redesign.md`
- Modify: `DECISIONS.md`

- [ ] **Step 1: mark the capture spec status**

Change status to "已实施（M1 后置补丁,commit <hash>）" and record any
deviations made during implementation.

- [ ] **Step 2: update the immersive doc conflict list**

In the "与 STUDY 四层学习管线的关系" section, mark conflict #1 (chips
write target) as resolved by this patch.

- [ ] **Step 3: add the M2-merge handoff note to DECISIONS.md**

Record three obligations for whoever merges M2 later:

1. `hermes_core/learning/flashcards.py`, `study_routes.py`, `study.rs`,
   `study-api.ts` now exist on main as capture-minimal versions —
   M2 merge must UNION methods/routes/commands into these files, not
   replace them (shapes were kept identical on purpose).
2. M2's legacy flashcard migration must **dedupe by normalized front
   against existing `learning_items`** before import — capture-created
   cards may predate the migration, and the branch's migration route does
   not dedupe.
3. FlashcardPanel stays legacy until M2; captured cards are invisible to
   the review UI until then (accepted dev-only gap).

---

### Task 7: Final Audit and Commit

**Files:**
- All files changed by Tasks 2-6.

- [ ] **Step 1: audit**

```powershell
git status --short
git diff --stat
rg -n "flashcardStore" web/src/chat/study/KnowledgePointChips.tsx
rg -n "learning_flashcard_capture|capture" hermes_core/tools/learning_tools.py
```

Expected: chips no longer reference `flashcardStore`; NO capture tool in
`learning_tools.py`.

- [ ] **Step 2: full focused gate**

```powershell
cd hermes_core; python -m pytest tests/learning -o "addopts=" -p no:cacheprovider -q; cd ..
cd python; python -m pytest tests/test_study_capture_routes.py tests/test_learning_owner_context.py -o "addopts=" -p no:cacheprovider -q; cd ..
cd web; npm run test:capture-index; npm run test:knowledge-points; npm run test:chat-ux; npm run build; cd ..
cd tauri; cargo check; cd ..
git diff --check
```

Expected: all green.

- [ ] **Step 3: commit locally (do not push; stop for review)**

```powershell
git add hermes_core python tauri web docs DECISIONS.md
git commit -m "feat(study): trusted knowledge-point capture path (kq-kp chips -> learning.db)"
```

---

## Acceptance Criteria

- Clicking a kq-kp chip writes an active single-card `flashcard_deck`
  artifact + materialized item into `learning.db` under the injected
  owner/current space; repeat clicks are idempotent (`duplicate: true`).
- A `flashcard.capture` activity with `origin=kq-kp` is recorded per capture.
- Chips never write to legacy localStorage; failure shows a retryable state.
- Model tools gained no capture/activation capability.
- All new files are shape-compatible with `student/study-module` M2
  counterparts (same paths, ids, wire formats), and DECISIONS.md carries the
  three M2-merge obligations (union-merge, migration dedupe, panel gap).
- Focused core/python/web/tauri gates pass; work is committed locally on the
  integration branch and left unpushed for review.
