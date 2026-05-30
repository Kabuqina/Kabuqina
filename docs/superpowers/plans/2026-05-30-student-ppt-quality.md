# Student PPT Quality Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Kabuqina's three student PPT workflows so generated decks can contain diagrams, tables, polished placeholders, backup slides, and readable claim-style content while preserving the current simple bullet schema.

**Architecture:** The core implementation lives in `hermes_core/tools/document_tools.py`, because PPT generation semantics belong in the owned Hermes core and should work consistently across web and gateway children. The web layer only updates the three workspace quick-action prompts so agents request the richer slide schema and apply lightweight quality rules before `review_outline`.

**Tech Stack:** Python 3.11, `python-pptx`, pytest, React/TypeScript workspace quick-action prompts, Node-based frontend tests.

---

## Files And Responsibilities

- `hermes_core/tools/document_tools.py`
  - Extend `pptx_write` schema.
  - Normalize slide type and structured payloads.
  - Render `claim_bullets`, `agenda`, `diagram`, `table`, `screenshot_placeholder`, `chart_placeholder`, `qa_backup`, and `closing`.
  - Preserve existing `title + bullets + notes` behavior.

- `hermes_core/tests/tools/test_document_tools.py`
  - Add focused tests for each structured slide type.
  - Verify graceful fallback behavior.
  - Verify old format compatibility and template background behavior still pass.

- `web/src/chat/WorkspacePanel.tsx`
  - Update the three quick-action prompts to request high-quality deliverable outlines.
  - Ask for `slide_type`, evidence placeholders, speaker notes, and backup slides.
  - Keep the existing `review_outline` then `pptx_write` workflow.

- `web/src/chat/chatUx.test.mjs`
  - Update prompt assertions so the test locks in the high-quality workflow vocabulary.

## Task 1: Add Structured PPT Tests First

**Files:**
- Modify: `hermes_core/tests/tools/test_document_tools.py`

- [ ] **Step 1: Add a test for old schema compatibility**
  - Use `pptx_write` with existing `{title, bullets, notes}` slides.
  - Assert the deck opens, slide count is correct, and content appears.

- [ ] **Step 2: Add a test for all new slide types in one deck**
  - Include slides with `slide_type` values:
    - `agenda`
    - `claim_bullets`
    - `diagram`
    - `table`
    - `screenshot_placeholder`
    - `chart_placeholder`
    - `qa_backup`
    - `closing`
  - Assert the deck opens and contains expected labels/text.

- [ ] **Step 3: Add a fallback test for unknown slide types**
  - Pass `slide_type: "mystery"`.
  - Assert generation succeeds and bullet text appears.

- [ ] **Step 4: Run the focused test file and confirm new tests fail**
  - Command:
    ```powershell
    cd hermes_core; python -m pytest tests/tools/test_document_tools.py -q
    ```
  - Expected: new structured slide tests fail before implementation.

## Task 2: Implement Slide Type Normalization And Helpers

**Files:**
- Modify: `hermes_core/tools/document_tools.py`

- [ ] **Step 1: Add slide type constants/helpers**
  - Add `_PPTX_SLIDE_TYPES`.
  - Add `_normalize_slide_type(raw)` returning `claim_bullets` for missing or unknown values.

- [ ] **Step 2: Add safe list/object normalizers**
  - Add helpers for bullets, tags, diagram steps, table headers/rows, and placeholder fields.
  - Keep invalid payloads readable rather than fatal.

- [ ] **Step 3: Add text-box utility helpers**
  - Add small helpers for drawing subtitles, captions, and body text.
  - Reuse existing theme colors.

- [ ] **Step 4: Run existing PPT tests**
  - Command:
    ```powershell
    cd hermes_core; python -m pytest tests/tools/test_document_tools.py -q
    ```
  - Expected: old tests still pass or only new tests still fail.

## Task 3: Implement Renderers For Structured Slides

**Files:**
- Modify: `hermes_core/tools/document_tools.py`

- [ ] **Step 1: Refactor `_apply_content_slide` into a dispatcher**
  - Keep existing layout setup and title styling.
  - Dispatch by normalized `slide_type`.
  - Use `claim_bullets` as the fallback renderer.

- [ ] **Step 2: Implement `agenda` and `claim_bullets`**
  - Agenda should render numbered items cleanly.
  - Claim bullets should cap visible bullets and preserve notes.

- [ ] **Step 3: Implement `diagram`**
  - Support simple horizontal flow boxes with arrows.
  - Support vertical fallback when there are too many nodes.
  - Ensure node labels are regular editable PowerPoint text.

- [ ] **Step 4: Implement `table`**
  - Render a compact editable table from `headers` and `rows`.
  - Limit row count to a readable amount.
  - Render fallback bullets when the payload is invalid.

- [ ] **Step 5: Implement placeholders**
  - Render `screenshot_placeholder` and `chart_placeholder` as framed areas with label and caption.
  - Put `source_hint` in speaker notes when present.
  - Do not imply a real screenshot/chart was inserted.

- [ ] **Step 6: Implement `qa_backup` and `closing`**
  - Backup slides should visibly mark themselves as backup.
  - Closing slides should support concise summary bullets and notes.

- [ ] **Step 7: Run focused core tests**
  - Command:
    ```powershell
    cd hermes_core; python -m pytest tests/tools/test_document_tools.py -q
    ```
  - Expected: all document tool tests pass.

## Task 4: Update The Tool Schema

**Files:**
- Modify: `hermes_core/tools/document_tools.py`

- [ ] **Step 1: Extend `PPTX_WRITE_SCHEMA`**
  - Add `slide_type`, `subtitle`, `diagram`, `table`, `placeholder`, and `tags` to slide properties.
  - Keep `title` and `bullets` requirements compatible with current callers.

- [ ] **Step 2: Improve schema description**
  - Mention structured slide types and high-quality student deliverables.
  - Keep templates documented as `course_report`, `paper_report`, `code_defense`.

- [ ] **Step 3: Run focused core tests again**
  - Command:
    ```powershell
    cd hermes_core; python -m pytest tests/tools/test_document_tools.py -q
    ```

## Task 5: Update Workspace Prompts

**Files:**
- Modify: `web/src/chat/WorkspacePanel.tsx`
- Modify: `web/src/chat/chatUx.test.mjs`

- [ ] **Step 1: Update prompt tests first**
  - Add assertions for:
    - `高质量可交付`
    - `slide_type`
    - `screenshot_placeholder`
    - `chart_placeholder`
    - `qa_backup`
    - `review_outline`
    - `pptx_write`

- [ ] **Step 2: Run the frontend chat UX test and confirm failure**
  - Command:
    ```powershell
    cd web; node src/chat/chatUx.test.mjs
    ```

- [ ] **Step 3: Update the three prompt strings**
  - `paper_report`: require research framework/architecture, evidence/placeholder, innovation, limitations, backup Q&A.
  - `course_report`: require knowledge map, example/application, comparison/process object, reflection, backup concepts.
  - `code_defense`: require architecture, implementation/data flow, screenshot/evidence placeholder, tests, problem-solution, deployment/backup.
  - Keep the confirmed workflow: read material, draft outline, call `review_outline`, then call `pptx_write`.

- [ ] **Step 4: Run frontend test**
  - Command:
    ```powershell
    cd web; node src/chat/chatUx.test.mjs
    ```
  - Expected: prompt assertions pass.

## Task 6: Final Verification

**Files:**
- No additional file edits unless verification exposes a defect.

- [ ] **Step 1: Run core focused tests**
  - Command:
    ```powershell
    cd hermes_core; python -m pytest tests/tools/test_document_tools.py -q
    ```

- [ ] **Step 2: Run frontend focused tests**
  - Command:
    ```powershell
    cd web; node src/chat/chatUx.test.mjs
    ```

- [ ] **Step 3: Optionally generate a sample PPTX**
  - Use `pptx_write` directly with one slide of each new type.
  - Open the PPTX with `python-pptx` and inspect shape/text counts.

- [ ] **Step 4: Review git diff**
  - Command:
    ```powershell
    git diff -- hermes_core/tools/document_tools.py hermes_core/tests/tools/test_document_tools.py web/src/chat/WorkspacePanel.tsx web/src/chat/chatUx.test.mjs
    ```

- [ ] **Step 5: Commit implementation**
  - Commit only files touched by this implementation plan.
  - Do not include unrelated dirty worktree changes.

## Acceptance Criteria

- `pptx_write` still supports the old simple slide schema.
- `pptx_write` can create editable slides for agenda, diagram, table, placeholders, backup, and closing.
- Missing or invalid structured payloads do not crash deck generation.
- Three PPT quick actions request high-quality deliverable outlines and structured slide types.
- Focused core and frontend tests pass.
