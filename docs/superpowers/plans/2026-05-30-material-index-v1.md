# Material Index v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lightweight, format-agnostic Material Index layer that turns already-read student materials into a stable, reusable JSON evidence package for downstream file generation workflows.

**Architecture:** Material Index v1 lives in `hermes_core` as a documents tool because it is agent/document-generation semantics, not desktop shell glue. It does not read files directly; it consumes content returned by the Read基础层 (`document_read_precise`, `pdf_read_precise`, file tools, or attachment extraction) and produces bounded structured metadata for planners and writers. PPT is the first consumer, but the index must also be suitable for future Word reports, summaries, study notes, project documentation, and other generated files. Writers remain independent and consume planner-specific outputs, not the index directly.

**Tech Stack:** Python 3.11, stdlib `re`/`json`/dataclasses, pytest, existing Hermes tool registry, React/TypeScript prompt tests.

---

## Files And Responsibilities

- `hermes_core/tools/material_index_tools.py`
  - New core tool module.
  - Defines the Material Index v1 contract.
  - Normalizes read outputs into `source_files`, `sections`, `key_points`, `tables`, `figures`, `screenshots`, `code_files`, `evidence`, `citations`, `uncertain_parts`, and `generation_hints`.
  - Registers `material_index_build`.

- `hermes_core/tools/document_tools.py`
  - No direct dependency required in v1.
  - Optional: share tiny constants only if duplication becomes meaningful. Prefer keeping v1 independent.

- `hermes_core/toolsets.py`
  - Add `material_index_build` to the `documents` toolset.

- `hermes_core/tests/tools/test_material_index_tools.py`
  - New focused tests for schema, extraction, truncation, source references, and profile-specific hints.

- `web/src/chat/WorkspacePanel.tsx`
  - Update the three PPT quick-action prompts to add a Material Index step after reading and before outline generation. This is the first consumer of the general index, not the reason the index exists.

- `web/src/chat/chatUx.test.mjs`
  - Lock in the PPT prompt contract: read materials, build material index, draft outline, review, write PPT.

## Contract

`material_index_build` input:

```json
{
  "profile": "paper_report | course_report | code_defense | auto",
  "materials": [
    {
      "name": "source.pdf",
      "path": "optional workspace path",
      "mime": "optional mime type",
      "kind": "pdf | docx | pptx | image | code | text | unknown",
      "content": "read text or markdown",
      "metadata": {
        "engine": "docling",
        "pages": 12
      }
    }
  ]
}
```

Output:

```json
{
  "ok": true,
  "version": 1,
  "profile": "paper_report",
  "source_files": [],
  "sections": [],
  "key_points": [],
  "tables": [],
  "figures": [],
  "screenshots": [],
  "code_files": [],
  "evidence": [],
  "citations": [],
  "uncertain_parts": [],
  "generation_hints": {
    "missing_assets": [],
    "quality_warnings": [],
    "ppt": {
      "recommended_slide_types": []
    },
    "report": {
      "recommended_sections": []
    }
  }
}
```

Each extracted item must include a stable `id`, `source_id`, and short `text`/`title` field. Items derived from long source text must be bounded so the tool response does not become another giant document dump.

## Scope Rules

- v1 consumes read results; it does not open paths or perform OCR.
- v1 uses deterministic heuristics only. No LLM call inside the tool.
- v1 is allowed to be imperfect, but it must preserve source references and uncertainty.
- v1 should produce helpful placeholders when assets are implied but missing.
- v1 must not invent real figures, screenshots, citations, or test results.
- v1 is format-agnostic. PPT-specific hints live under `generation_hints.ppt`; future document types must add their own hint namespace instead of changing the core index into a PPT schema.

## Task 1: Write Material Index Tests First

**Files:**
- Create: `hermes_core/tests/tools/test_material_index_tools.py`

- [ ] **Step 1: Test minimal index shape**
  - Build an index from one markdown material with a title and paragraphs.
  - Assert `ok`, `version`, `profile`, `source_files`, `sections`, `key_points`, and `generation_hints` exist.

- [ ] **Step 2: Test markdown heading extraction**
  - Input markdown with `#`, `##`, and paragraph content.
  - Assert section titles and source references are present.

- [ ] **Step 3: Test table extraction**
  - Input markdown with a pipe table.
  - Assert `tables[0].headers`, `rows`, `source_id`, and a short `title` are present.

- [ ] **Step 4: Test figure and screenshot cues**
  - Input markdown containing `![系统截图](dashboard.png)` and text like `图 2 系统架构`.
  - Assert `figures` or `screenshots` include the cue without claiming the image file was embedded.

- [ ] **Step 5: Test code profile cues**
  - Input materials with names like `src/main/java/App.java`, `README.md`, and `pom.xml`.
  - Assert `code_files`, architecture-related evidence, and code-defense hints exist under `generation_hints.ppt`.

- [ ] **Step 6: Test truncation and uncertainty**
  - Input very long content plus phrases like `识别不清` or `OCR uncertain`.
  - Assert snippets are bounded and `uncertain_parts` includes the warning.

- [ ] **Step 7: Run tests and confirm failure**
  - Command:
    ```powershell
    cd hermes_core; python -m pytest tests/tools/test_material_index_tools.py -q
    ```
  - Expected: fails because the tool does not exist yet.

## Task 2: Implement Core Builder

**Files:**
- Create: `hermes_core/tools/material_index_tools.py`

- [ ] **Step 1: Add constants and helpers**
  - Define max counts and max snippet lengths.
  - Add `_safe_text`, `_safe_list`, `_truncate`, `_make_id`, and `_normalize_profile`.

- [ ] **Step 2: Normalize source files**
  - Convert input materials into `source_files`.
  - Preserve `name`, `path`, `mime`, `kind`, metadata, and a generated `source_id`.

- [ ] **Step 3: Extract sections**
  - Parse markdown headings.
  - Attach following paragraph snippets when available.
  - Fall back to first paragraphs when no headings exist.

- [ ] **Step 4: Extract key points**
  - Collect bullet lines and strong short paragraphs.
  - Cap count and snippet length.
  - Keep `source_id` and optional `section_id`.

- [ ] **Step 5: Extract markdown tables**
  - Detect simple pipe tables.
  - Normalize headers and up to a readable number of rows.
  - Store as editable planning data, not rendered output for any specific file type.

- [ ] **Step 6: Extract figure/screenshot cues**
  - Detect markdown images, `图 N`, `Figure N`, `截图`, `界面`, `dashboard`, `运行结果`.
  - Classify into `figures` or `screenshots`.
  - If cue lacks a real path, add a `missing_assets` hint.

- [ ] **Step 7: Extract code file cues**
  - For `code_defense`, identify source/config/test files from material names and paths.
  - Add evidence for README, project config, entrypoints, tests, and result files.

- [ ] **Step 8: Extract citations and uncertainty**
  - Capture page markers like `<!-- page:3 -->`, `[1]`, DOI-like text, and bibliography headings.
  - Capture uncertainty phrases from OCR/read fallbacks.

- [ ] **Step 9: Generate `generation_hints`**
  - Add shared `missing_assets` and `quality_warnings`.
  - Add `generation_hints.ppt` for the current PPT workflows:
    - `paper_report`: recommend `diagram`, `table`, `chart_placeholder`, `qa_backup` based on available evidence.
    - `course_report`: recommend `diagram`, `table`, `claim_bullets`, `qa_backup`.
    - `code_defense`: recommend `diagram`, `screenshot_placeholder`, `table`, `qa_backup`.
  - Add a small `generation_hints.report.recommended_sections` list so the v1 contract demonstrates that the layer is not PPT-only.

- [ ] **Step 10: Return JSON**
  - Add `material_index_build(profile, materials)` returning `json.dumps(..., ensure_ascii=False)`.
  - Use `tool_error` for invalid top-level input only.

## Task 3: Register Tool And Toolset

**Files:**
- Modify: `hermes_core/tools/material_index_tools.py`
- Modify: `hermes_core/toolsets.py`

- [ ] **Step 1: Add `MATERIAL_INDEX_BUILD_SCHEMA`**
  - Describe that it consumes already-read material and creates a general planning index for downstream file generation.
  - Include `profile` and `materials`.

- [ ] **Step 2: Register `material_index_build`**
  - Toolset: `documents`.
  - Emoji can be `🗂️` or similar.

- [ ] **Step 3: Add to documents toolset**
  - Update `hermes_core/toolsets.py`:
    ```python
    "tools": ["document_read_precise", "pdf_read_precise", "material_index_build", "pptx_write"]
    ```

- [ ] **Step 4: Run focused tests**
  - Command:
    ```powershell
    cd hermes_core; python -m pytest tests/tools/test_material_index_tools.py tests/tools/test_document_tools.py -q -k "material_index or pptx"
    ```

## Task 4: Update PPT Workflow Prompts

**Files:**
- Modify: `web/src/chat/WorkspacePanel.tsx`
- Modify: `web/src/chat/chatUx.test.mjs`

- [ ] **Step 1: Update frontend test first**
  - Assert prompts mention:
    - `material_index_build`
    - `素材索引`
    - read material first
    - outline after index
    - `review_outline`
    - `pptx_write`

- [ ] **Step 2: Confirm test failure**
  - Command:
    ```powershell
    cd web; node src/chat/chatUx.test.mjs
    ```

- [ ] **Step 3: Update three quick-action prompts**
  - Insert a step between reading and outline:
    - "调用 `material_index_build` 生成素材索引"
    - "根据素材索引再生成大纲"
  - Keep current high-quality slide type rules.
  - Make clear that missing screenshots/charts become placeholders.
  - Make clear that the PPT workflows are consuming the general Material Index, not defining its full scope.

- [ ] **Step 4: Run frontend test**
  - Command:
    ```powershell
    cd web; node src/chat/chatUx.test.mjs
    ```

## Task 5: Add A Small Documentation Note

**Files:**
- Create or modify: `docs/material-index.md`
- Optionally modify: `docs/README.md`

- [ ] **Step 1: Document the layer boundary**
  - Read基础层 reads files.
  - Material Index organizes read results into reusable evidence.
  - Planners choose story, format, and output structure.
  - Writers render specific file formats such as PPTX today and future document types later.

- [ ] **Step 2: Document v1 limitations**
  - No file reading.
  - No OCR.
  - No LLM inside the tool.
  - No automatic asset embedding yet.
  - PPT is the first consumer, not the only target.

- [ ] **Step 3: Link from docs index if appropriate**
  - Add to `docs/README.md` only if that file already lists related docs.

## Task 6: Final Verification

**Files:**
- No additional edits unless verification exposes defects.

- [ ] **Step 1: Run Material Index tests**
  - Command:
    ```powershell
    cd hermes_core; python -m pytest tests/tools/test_material_index_tools.py -q
    ```

- [ ] **Step 2: Run PPT-focused document tests**
  - Command:
    ```powershell
    cd hermes_core; python -m pytest tests/tools/test_document_tools.py -q -k pptx
    ```

- [ ] **Step 3: Run frontend prompt test**
  - Command:
    ```powershell
    cd web; node src/chat/chatUx.test.mjs
    ```

- [ ] **Step 4: Inspect diff**
  - Command:
    ```powershell
    git diff -- hermes_core/tools/material_index_tools.py hermes_core/toolsets.py hermes_core/tests/tools/test_material_index_tools.py web/src/chat/WorkspacePanel.tsx web/src/chat/chatUx.test.mjs docs/material-index.md docs/README.md
    ```

- [ ] **Step 5: Commit only related files**
  - Do not stage unrelated dirty worktree files.

## Acceptance Criteria

- `material_index_build` exists in the `documents` toolset.
- It consumes already-read materials and returns a bounded Material Index v1 JSON object.
- It preserves source references for sections, tables, figures/screenshots, evidence, and uncertainty.
- It produces generic `generation_hints` plus PPT-specific hints for `paper_report`, `course_report`, and `code_defense`.
- The three PPT quick actions require a material-index step before outline review.
- Focused core and frontend tests pass.

## Follow-Up Ideas

- Feed real image paths from Read基础层 into `figures`/`screenshots`.
- Let `pptx_write` embed real assets when slide objects reference verified workspace image paths.
- Add richer planners that convert Material Index into PPT slides, Word reports, study notes, project documentation, or other generated files.
- Add UI preview of the material index before outline generation if students need more control.
