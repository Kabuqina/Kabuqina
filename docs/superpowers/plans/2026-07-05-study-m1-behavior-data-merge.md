# STUDY M1 Behavior/Data Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** merge only the M1 learning data foundation from `student/study-module` into current `main`, while preserving the immersive-learning M1 behavior work already on `main`.

**Architecture:** treat this as a selective integration, not a full branch merge. Current `main` owns the behavior/interaction M1 work: learning soul, `LEARNING_CONDUCT_GUIDANCE`, `kq-kp` parsing/chips, and conversational STUDY quick actions. `student/study-module` contributes only the M1 shared data spine: `learning_contract`, `learning.db`, owner/space isolation, Output Writer, Learning Index, PlannerSpec registry, minimal `learning` toolset, and capability/policy drift tests.

**Tech Stack:** Python 3.11, SQLite/WAL, pytest/unittest, TypeScript/Vite node tests, Tauri 2/Rust only for verification. No M2/M3 desk routes, Tauri commands, or backend-driven Flashcard/Quiz UI enter this merge.

---

## Guardrails

- Do not run a normal `git merge student/study-module`. That branch already contains M2/M3 implementation and M4 planning docs.
- Cherry-pick only the M1 commit range listed below, skipping the branch merge commit.
- Preserve current `main` behavior files unless a deliberate M1 data-foundation change is required.
- `hermes_core/agent/prompt_builder.py` must end with both:
  - current `LEARNING_CONDUCT_GUIDANCE`;
  - M1 `deliverable_planner_is_active()`.
- `web/src/chat/study/studyPrompts.ts` must keep current conversational M1 prompts. Do not take the M2/M3 tool-driven flashcard/quiz prompt text.
- `web/src/chat/study/KnowledgePointChips.tsx` may still write to legacy `flashcardStore` for this stop-at-M1 merge. Record this as an intentional temporary bridge; do not introduce `learning.db` single-card UI/API yet.
- Do not add these M2/M3 files in this merge:
  - `hermes_core/learning/flashcards.py`
  - `hermes_core/learning/quizzes.py`
  - `python/src/desk_server/routes/study_routes.py`
  - `tauri/src/study.rs`
  - `web/src/chat/study/study-api.ts`
  - `web/src/chat/study/flashcardLearningStore.ts`
  - `web/src/chat/study/quizLearningStore.ts`

## Source Commits

Cherry-pick these commits from `student/study-module`, in order:

```powershell
633268ae253d091d9958d0df2b8654f4d8adf9e0
46109bda1dc8832ae1b03590c69e191173481546
8d1b5f0e81ea6f4ee43cd4da70e102b33a3c62ae
edbdf731af42724f110e0874e8879ddceafcf627
3dba1166532b70aecb500e9f4efe0e5534a589b5
336ed270a5a7a607d22e173484bf6ee1a319967e
cbec47f362e153f4e1072d8370d9702c2702d451
5cf2ccb0d8b96a3395b1bf728303b9dbf507b1e8
3f2f3359e9ccb151caa18f0ebb8c260c4e01db73
51c879232e32eb1636a6bfff6e4b8bb6d087c84e
19dba81fd56c18d028ed3f9ec1f9961388c1264d
ec4831e739437a1bfbd7bae42cb2da60a7573b18
2f0e9bbd401a528a42d1faef0fd21e9eac40695d
```

Do not cherry-pick:

```powershell
1ed46f15839ed3f66d7e70a6b1eeaa15b21eb2b7
b47cbf85450059a8afb1b583f2d355003b3ca31b
fb08d3d84abab489612650201b02311ba56f478a
170b3debe27749c9b092a69ac3230049f68cf469
caa82a774e1fbff46dde41152e3ba9a376f29bb7
```

---

### Task 1: Create Integration Branch and Baseline

**Files:**
- No intended file modifications.

- [ ] **Step 1: verify the working tree is clean**

Run:

```powershell
git status --short --branch
```

Expected:

```text
## main...origin/main [ahead 3]
```

No untracked or modified files except this plan if it has not yet been committed.

- [ ] **Step 2: create the merge branch**

Run:

```powershell
git switch -c codex/study-m1-merge
```

Expected:

```text
Switched to a new branch 'codex/study-m1-merge'
```

- [ ] **Step 3: record baseline file set**

Run:

```powershell
git diff --name-status main...student/study-module
git log --reverse --oneline --no-abbrev 9e599a5bf34b27cc7fd6d59e4a8683d2e32ff6ab..student/study-module
```

Expected: diff includes M2/M3 files, confirming why this plan uses selective cherry-picks.

---

### Task 2: Cherry-Pick Documentation and M1 Core Foundation

**Files:**
- Add: `docs/superpowers/specs/2026-07-01-study-four-layer-learning-pipeline-design.md`
- Add: `docs/superpowers/plans/2026-07-03-study-m1-shared-foundation.md`
- Modify: `DECISIONS.md`
- Add/modify: `hermes_core/learning/*`
- Add/modify: `hermes_core/tests/learning/*`
- Modify: `hermes_core/agent/prompt_builder.py`
- Modify: `hermes_core/pyproject.toml`
- Modify: `hermes_core/tests/tools/test_registry.py`
- Add: `hermes_core/tools/learning_tools.py`
- Modify: `python/src/capability_registry.py`
- Add: `python/src/learning_owner.py`
- Modify: `python/src/tool_policy.py`
- Add/modify: `python/tests/test_capability_registry_learning.py`
- Add/modify: `python/tests/test_learning_owner_context.py`
- Modify: `python/tests/test_policy_contract.py`

- [ ] **Step 1: cherry-pick the M1 sequence without committing if conflict review is desired**

Preferred run:

```powershell
git cherry-pick -x 633268ae253d091d9958d0df2b8654f4d8adf9e0 46109bda1dc8832ae1b03590c69e191173481546 8d1b5f0e81ea6f4ee43cd4da70e102b33a3c62ae edbdf731af42724f110e0874e8879ddceafcf627 3dba1166532b70aecb500e9f4efe0e5534a589b5 336ed270a5a7a607d22e173484bf6ee1a319967e cbec47f362e153f4e1072d8370d9702c2702d451 5cf2ccb0d8b96a3395b1bf728303b9dbf507b1e8 3f2f3359e9ccb151caa18f0ebb8c260c4e01db73 51c879232e32eb1636a6bfff6e4b8bb6d087c84e 19dba81fd56c18d028ed3f9ec1f9961388c1264d ec4831e739437a1bfbd7bae42cb2da60a7573b18 2f0e9bbd401a528a42d1faef0fd21e9eac40695d
```

Expected: commits apply, or conflicts appear only in files touched by both M1 tracks.

- [ ] **Step 2: if `prompt_builder.py` conflicts, keep both M1 tracks**

Final requirement in `hermes_core/agent/prompt_builder.py`:

```python
LEARNING_CONDUCT_GUIDANCE = (
    "# Learning conduct\n"
    ...
)

def build_deliverable_planner_prompt(valid_tool_names: "set[str] | None" = None) -> str:
    ...

def deliverable_planner_is_active(valid_tool_names: "set[str] | None" = None) -> bool:
    """Whether the Deliverable Planner applies for the given tool set."""
    try:
        from tools.deliverable_contract import DELIVERABLE_WRITER_TOOLS
    except Exception as exc:  # pragma: no cover - defensive import
        logger.debug("Failed to import deliverable contract: %s", exc)
        return False
    valid_names = set(valid_tool_names or set())
    return any(tool in valid_names for tool in DELIVERABLE_WRITER_TOOLS)
```

Also confirm `hermes_core/run_agent.py` still imports and appends `LEARNING_CONDUCT_GUIDANCE`.

- [ ] **Step 3: if policy/capability files conflict, keep append-only behavior**

Required post-merge checks:

```powershell
rg -n '"learning"|learning-' python/src/tool_policy.py python/src/capability_registry.py python/tests/test_policy_contract.py python/tests/test_capability_registry_learning.py
```

Expected: learning toolset and capability references are present, with no removed existing entries.

- [ ] **Step 4: confirm M2/M3 files did not enter**

Run:

```powershell
git status --short
Test-Path hermes_core\learning\flashcards.py
Test-Path hermes_core\learning\quizzes.py
Test-Path python\src\desk_server\routes\study_routes.py
Test-Path tauri\src\study.rs
Test-Path web\src\chat\study\study-api.ts
Test-Path web\src\chat\study\flashcardLearningStore.ts
Test-Path web\src\chat\study\quizLearningStore.ts
```

Expected: every `Test-Path` result is `False`.

---

### Task 3: Reconcile Current Immersive M1 Behavior

**Files:**
- Modify if needed: `docs/immersive-learning-redesign.md`
- Modify if needed: `web/src/chat/study/studyPrompts.ts`
- Modify if needed: `web/src/chat/study/KnowledgePointChips.tsx`
- Modify if needed: `web/src/chat/study/knowledgePoints.ts`
- Modify if needed: `web/src/chat/ChatMessage.tsx`
- Modify if needed: `web/src/chat/chatExport.ts`
- Modify if needed: `web/src/chat/chatUx.test.mjs`

- [ ] **Step 1: preserve conversational STUDY prompts**

Run:

```powershell
rg -n "一次只问一个问题|输出格式请固定|learning_draft_create|不要把卡片 JSON 直接贴给我" web/src/chat/study/studyPrompts.ts
```

Expected:

```text
一次只问一个问题
```

Expected absent:

```text
输出格式请固定
learning_draft_create
不要把卡片 JSON 直接贴给我
```

- [ ] **Step 2: preserve `kq-kp` frontend protocol**

Run:

```powershell
rg -n "kq-kp|KnowledgePointChips|stripKnowledgePointBlocks|knowledgePoints" web/src/chat web/src/chat/study
```

Expected: parser, chips component, `ChatMessage.tsx`, and export path all still reference the protocol.

- [ ] **Step 3: add a short merge note to `docs/immersive-learning-redesign.md`**

Add under the 2026-07-05 comparison section:

```markdown
**M1 merge decision (2026-07-05):** stop at M1 by integrating only the shared
learning foundation (`learning_contract`, `learning.db`, owner/space isolation,
Learning Index, Output Writer, PlannerSpec, minimal `learning` toolset) while
keeping the immersive behavior M1 UI (`kq-kp` chips and conversational STUDY
prompts). M2/M3 backend-driven Flashcard/Quiz UI, desk routes, Tauri study
commands, and M4 state/evaluation work remain out of this merge.
```

---

### Task 4: Verify M1 Data Foundation

**Files:**
- No intended source edits unless tests expose merge breakage.

- [ ] **Step 1: run core learning tests**

Run:

```powershell
cd hermes_core
python -m pytest tests/learning -o "addopts=" -p no:cacheprovider -q
```

Expected: all tests pass.

- [ ] **Step 2: run prompt regression tests**

Run:

```powershell
cd hermes_core
python -m pytest tests/agent/test_prompt_builder.py tests/run_agent/test_run_agent.py -o "addopts=" -p no:cacheprovider -q
```

Expected: deliverable planner tests pass, and learning conduct remains injected.

- [ ] **Step 3: run core registry drift tests**

Run:

```powershell
cd hermes_core
python -m pytest tests/tools/test_registry.py -o "addopts=" -p no:cacheprovider -q
```

Expected: tool registry tests pass with `learning` registered.

---

### Task 5: Verify Desktop Policy and Owner Injection

**Files:**
- No intended source edits unless tests expose merge breakage.

- [ ] **Step 1: run Python policy and learning owner tests**

Run:

```powershell
cd python
python -m pytest tests/test_capability_registry_learning.py tests/test_learning_owner_context.py tests/test_policy_contract.py -o "addopts=" -p no:cacheprovider -q
```

Expected: capability drift, owner injection, and tool-policy tests pass.

- [ ] **Step 2: run existing Python unit suite if the focused tests pass**

Run:

```powershell
cd python
python -m unittest discover -s tests -p "test_*.py" -v
```

Expected: no regressions. If old environment-sensitive tests fail, record exact failures and keep the focused M1 gate as the release blocker.

---

### Task 6: Verify Web M1 Behavior Stayed Intact

**Files:**
- No intended source edits unless tests expose merge breakage.

- [ ] **Step 1: run study behavior tests**

Run:

```powershell
cd web
npm run test:chat-ux
npm run test:knowledge-points
npm run test:flashcard-store
npm run test:quiz-store
```

Expected: conversational quick-action contract, `kq-kp` parser, and legacy Flashcard/Quiz stores pass.

- [ ] **Step 2: run lint/build**

Run:

```powershell
cd web
npm run lint
npm run build
```

Expected: lint and TypeScript/Vite build pass.

---

### Task 7: Final Diff Audit and Commit

**Files:**
- All files changed by Tasks 2-3.

- [ ] **Step 1: audit changed files**

Run:

```powershell
git diff --name-status main...HEAD
```

Expected included:

```text
docs/superpowers/specs/2026-07-01-study-four-layer-learning-pipeline-design.md
docs/superpowers/plans/2026-07-03-study-m1-shared-foundation.md
hermes_core/learning/*
hermes_core/tests/learning/*
hermes_core/tools/learning_tools.py
python/src/learning_owner.py
```

Expected excluded:

```text
hermes_core/learning/flashcards.py
hermes_core/learning/quizzes.py
python/src/desk_server/routes/study_routes.py
tauri/src/study.rs
web/src/chat/study/study-api.ts
web/src/chat/study/flashcardLearningStore.ts
web/src/chat/study/quizLearningStore.ts
```

- [ ] **Step 2: inspect semantic hotspots**

Run:

```powershell
git diff -- hermes_core/agent/prompt_builder.py hermes_core/run_agent.py web/src/chat/study/studyPrompts.ts web/src/chat/study/KnowledgePointChips.tsx docs/immersive-learning-redesign.md
```

Expected:

- `prompt_builder.py` has both learning conduct and deliverable planner activation helper.
- `run_agent.py` still injects learning conduct.
- `studyPrompts.ts` remains conversational and does not mention `learning_draft_create`.
- `KnowledgePointChips.tsx` still uses the current legacy flashcard bridge.
- `docs/immersive-learning-redesign.md` records the M1-only merge boundary.

- [ ] **Step 3: commit**

Run:

```powershell
git add DECISIONS.md docs/superpowers docs/immersive-learning-redesign.md hermes_core python
git commit -m "feat(study): merge M1 learning foundation"
```

Expected: one integration commit on `codex/study-m1-merge`.

---

## Acceptance Criteria

- Current immersive-learning M1 behavior is preserved.
- Shared data foundation M1 is present and tested.
- No M2/M3 backend Flashcard/Quiz UI or desk/Tauri study API enters the merge.
- `kq-kp` chips remain intentionally legacy-store backed for this M1 stop point.
- `docs/immersive-learning-redesign.md` explicitly records the deferred conflict: chips should later write through a trusted `learning.db` single-card path.
- Focused Python/Core/Web verification passes, or failures are documented with exact commands and tracebacks.
