# File Generation Pipeline

Kabuqina's file generation should be designed as a general pipeline, not as a PPT-only feature.

PPT is the first visible product branch, but the same pipeline should support future Word reports, study notes, summaries, project documentation, spreadsheets, and other generated files.

## Four Layers

```text
Read Layer
  -> Material Index
    -> Planner
      -> Writer
```

Each layer owns a different responsibility. Keeping these boundaries clear prevents every output type from inventing its own file-reading and material-selection logic.

This pipeline covers **generated deliverables**. Live chat presentation is a
separate surface: `Read Layer / Agent Output -> Chat Display Layer`. Chat Display
owns Markdown, LaTeX/math rendering, source references, warnings, and interactive
copy/inspection affordances in the conversation UI. See
`docs/chat-display-layer.md`.

Learning interactions are another surface above chat display:
`Read Layer / Agent Output / Student State -> Chat Display Layer -> Learning
Interaction Layer`. That layer owns explanation, hinting, quiz, derivation, and
formula-code learning workflows. See `docs/learning-layer.md`.

### What exists today vs. what is prompt-orchestrated

Not every layer is a code module. Be precise about this when reasoning about guarantees:

| Layer | Form today | Anti-hallucination enforcement |
|-------|-----------|--------------------------------|
| Read | Tools in `hermes_core` (`pdf_read_precise`, `document_read_precise`, attachment extraction) | N/A (reports uncertainty) |
| Material Index | Tool `material_index_build` (deterministic, regex/heuristic, **no LLM**) | **Code-enforced** — it physically cannot invent facts |
| Planner | The LLM agent, steered by a **shared prompt sunk into the core**: `build_deliverable_planner_prompt` in `hermes_core/agent/prompt_builder.py`, injected by `run_agent._build_system_prompt` for **both** the desk and gateway children. Web quick-actions (`WorkspacePanel.tsx`) are now thin (intent + structure + visual master). | **Prompt-only** — no code guardrail; this is where fabrication risk lives. But the slide vocabulary is single-sourced from `tools/deliverable_contract.py`, so the planner cannot be told to emit a slide type the writer would silently rewrite. |
| Writer | Tools in `hermes_core/tools/document_tools.py` (`pptx_write`, `pdf_write`, `html_write`, `docx_write`) | Renders placeholders instead of inventing assets |

The guarantee is **asymmetric**: Material Index's "does not invent screenshots/charts/citations" is enforced by code (it only extracts what the Read layer produced). The Planner's identical-sounding non-responsibilities are enforced only by prompt. The strongest factual guardrail is at Material Index; the Planner is the open risk surface. Do not read the two as equally hard guarantees.

### Which output covers which layer (do not hand-maintain this)

The authoritative "output x layer" matrix is **generated from the capability
registry**, not written by hand. Each capability in
[python/src/capability_registry.py](../python/src/capability_registry.py)
declares `pipelines[].steps[].stage`, and:

- `validate_capability_definitions()` enforces that a pipeline's declared
  `stages` are **exactly** the stages with a real step — no "phantom" layer can
  be labelled on a pipeline that no step implements. Guarded by
  `test_no_phantom_pipeline_stages` in
  [python/tests/test_capability_registry.py](../python/tests/test_capability_registry.py).
- `build_framework_coverage()` / `render_framework_coverage_table()` emit the
  current matrix (Markdown) straight from those steps.

As of the Phase C pass, the real coverage is: **PPTX**, **PDF**
(`document-report-pdf`), **HTML** (`document-report-html`), and **DOCX**
(`document-report-docx`) are each wired through all four layers; PDF, HTML, and
DOCX also keep a non-primary writer-only direct path (`document-pdf-writer-v1`,
`document-html-writer-v1`, `document-docx-writer-v1`). The **math/code** outputs
remain writer-only (their reader/material-index inputs come from *other*
capabilities, not from steps these pipelines own). Treat any claim that an output
"covers Material Index / Planner" as false unless the generated matrix shows a
step for it.

PDF, HTML, and DOCX share the same structured document contract
(sections/blocks). `pdf_write` and `html_write` share the per-block renderer
(`_block_to_html`); `docx_write` renders the same normalized blocks via
python-docx. So one reviewed planner outline can be emitted as `.pdf`, `.html`,
or `.docx`. `html_write` produces a self-contained responsive page
(`standalone_html_v1`); `docx_write` produces an editable Word file
(`python_docx_v1`); the `.html` that `pdf_write` emits stays a print-oriented
inspection sidecar, not the first-class HTML deliverable.

## 1. Read Layer

The Read layer sees source files.

Responsibilities:

- Open files and attachments.
- Parse formats such as PDF, DOCX, PPTX, images, code projects, markdown, text, CSV, and Excel.
- Preserve source metadata such as file name, path, MIME type, page count, parser engine, and uncertainty.
- Return readable text or markdown plus metadata.
- Mark unclear OCR, missing pages, failed table extraction, or unsupported assets.

Non-responsibilities:

- It should not decide the final output story.
- It should not decide PPT slide types.
- It should not write generated files.
- It should not hide uncertainty just to make downstream generation look clean.

Typical outputs:

- `document_read_precise`
- `pdf_read_precise`
- `mode=math` for formula-heavy papers or textbooks where LaTeX-oriented formula extraction matters more than speed
- attachment text extraction
- future image/OCR/code/project readers

## 2. Material Index

Material Index organizes already-read material into reusable evidence.

It is a general document-generation layer, not a PPT schema. It consumes Read-layer results and returns a bounded structured index.

**It is deterministic and heuristic, by design.** `material_index_build` extracts structure with regex/string rules (markdown headings, bullets, pipe tables, `![]()` images, and cue words such as `截图 / 界面 / Figure / 图N`). It calls **no LLM**. This is a deliberate trade-off:

- **Why no LLM:** determinism, traceability (every item points back to a source), zero token cost, and a hard "cannot fabricate" guarantee.
- **The cost — limited recall:** quality depends on the Read layer emitting clean markdown. A figure with no alt text and no cue word, a table that lost its pipe formatting during extraction, or code outside the `code_defense` profile will be missed. `code_files` is only populated for `code_defense`, and snippets are truncated.

Semantic, judgement-based selection ("which of these 30 points actually matter for this deck") is **not** this layer's job — it belongs to the Planner. Do not add an LLM here to improve recall; that would break the contract above. If recall is the problem, fix the Read layer or enrich the Planner.

Responsibilities:

- Normalize source files into `source_files`.
- Extract `sections`, `key_points`, `tables`, `figures`, `screenshots`, `code_files`, `evidence`, `citations`, and `uncertain_parts`.
- Preserve source references for traceability.
- Keep snippets bounded so the index does not become another raw document dump.
- Produce general `generation_hints`, with format-specific hints under namespaces such as `generation_hints.ppt` or `generation_hints.report`.

> **`generation_hints` are advisory, not decisions.** Material Index today emits `generation_hints.ppt.recommended_slide_types` and `generation_hints.report.recommended_sections` (hardcoded per profile in `material_index_tools.py`). Per the Design Rule below, *choosing* slide order/types is the Planner's job — so treat these strictly as **hints the Planner may override**, never as the deck structure. If this list keeps growing per new format, that is a signal to move the recommendation logic into the per-format Planner branch instead of Material Index.

Non-responsibilities:

- It does not open paths.
- It does not OCR files.
- It does not call an LLM.
- It does not invent screenshots, charts, citations, test results, or conclusions.
- It does not choose the final narrative.
- It does not render PPTX, DOCX, PDF, or any other file.

Current v1 tool:

- `material_index_build`

## 3. Planner

The Planner decides how to turn indexed material into a specific generated artifact.

> **The Planner is the LLM agent steered by a shared prompt sunk into the core.** The canonical planner rules — four-layer flow, slide_type/layout vocabulary, placeholder discipline, and per-structure must-cover outlines — live in `build_deliverable_planner_prompt` (`hermes_core/agent/prompt_builder.py`), injected by `run_agent._build_system_prompt` and self-gated on the deliverable writer tools, so the **desk child and the gateway child plan identically** (satisfying the AGENTS.md "same behavior in both children → prefer `hermes_core`" rule). The `web/src/chat/WorkspacePanel.tsx` quick-actions are now thin: intent + structure id + the dynamic visual-master selection. The Planner's "non-responsibilities" below are still **prompt conventions, not enforced contracts** — but the slide vocabulary is single-sourced from `tools/deliverable_contract.py` (shared with the writer), so a vocabulary drift between planner guidance and writer normalization is structurally impossible.

> **Source format and deliverable format are independent — the layers compose freely.** There is no pipeline *executor*; the registry pipelines are descriptive, and the agent calls the reader / `material_index_build` / `review_outline` / writer tools directly. Because the reader normalizes every input to text/markdown, the material index and outline are format-agnostic, and the PDF/HTML/DOCX writers share one sections/blocks contract, the agent can improvise any reader×writer combination (e.g. read a `.docx` and emit `.html`, or read a `.pdf` and emit `.docx`). The sunk planner prompt states this explicitly so the agent matches the writer to the requested *output*, not to the input file type. (PPTX uses a separate `slides` contract, so doc↔ppt requires the planner to emit the other shape.)

For a PPT, the planner chooses the story spine, slide order, slide types, claims, evidence placement, speaker notes, backup slides, and missing-asset placeholders.

For future file types, the same planner layer may choose:

- report sections for Word/PDF;
- study-note hierarchy;
- project documentation structure;
- summary format;
- spreadsheet tabs and tables;
- citation and appendix strategy.

Responsibilities:

- Interpret the user's requested output type.
- Choose what evidence matters.
- Decide structure, order, emphasis, and omissions.
- Convert Material Index items into output-specific intermediate objects.
- Ask for user review when the workflow requires confirmation.

Non-responsibilities:

- It should not parse source files itself when the Read layer can do it.
- It should not render final binary files.
- It should not mutate Material Index facts.

PPT-specific examples:

- Markdown PPT outline.
- `review_outline` interaction.
- Slide objects with `slide_type`, `title`, `bullets`, `diagram`, `table`, `placeholder`, and `notes`.

These are PPT planner artifacts, not the whole file-generation architecture.

## 4. Writer

The Writer renders a concrete file format from planner output.

Responsibilities:

- Create files such as PPTX today and future DOCX/PDF/XLSX outputs later.
- Apply visual or document templates.
- Keep output editable where possible.
- Handle format-specific fallback behavior.
- Return file paths and generation metadata.

Non-responsibilities:

- It should not read source files.
- It should not build the Material Index.
- It should not decide the full story.
- It should not pretend missing assets exist.

Current PPT branch:

- `pptx_write`
- structured PPT slide types such as `agenda`, `claim_bullets`, `diagram`, `table`, `screenshot_placeholder`, `chart_placeholder`, `qa_backup`, and `closing`

This is only one Writer branch. Future Writer branches can consume their own planner outputs while still reusing the same Read and Material Index layers.

## PPT Workflow As First Consumer

The current student PPT workflow should follow:

```text
Read material
  -> Build Material Index
    -> Plan PPT outline and slide objects
      -> User reviews outline
        -> Write PPTX
```

Concrete sequence:

1. Use `pdf_read_precise`, `document_read_precise`, file tools, or attachment extraction.
2. Call `material_index_build` with already-read material.
3. Generate a PPT-specific outline from the Material Index.
4. Call `review_outline`.
5. After confirmation, call `pptx_write`.

## Design Rule

If a feature is useful for more than one generated file type, it belongs at or above Material Index.

If a feature is only about slide order, slide type, or speaker notes, it belongs in the PPT planner branch.

If a feature is only about PowerPoint layout or PPTX rendering, it belongs in `pptx_write`.

If a feature is about opening files, OCR, precise extraction, or parser fallback, it belongs in the Read layer.

## Contract and cost notes

- **Index contract is versioned.** `material_index_build` returns `version: 1`. Because Material Index is "the stable bridge" between raw materials and every downstream generator, evolve it additively: new fields default safely, old consumers keep working, and bump `version` only on breaking shape changes. Planners should tolerate unknown fields.
- **Token round-trip is real.** For small student decks, inline `materials[].content` remains the simplest path. For larger inputs, Read tools now persist each read into a local Read cache and return `read_id`/`cache_path`; callers may set `include_content=false` and pass `read_id` into `material_index_build`, letting Material Index read the source **by reference** instead of round-tripping the full content through the model.

## Why This Matters

Without this separation, every output feature would repeat the same work:

- PDF parsing would be reimplemented by PPT, Word, and summary flows.
- Screenshots and figures would be detected differently in each workflow.
- Uncertainty would be lost before final generation.
- PPT-specific assumptions would leak into future document generation.

With this separation, Read improvements automatically benefit every downstream file generator, and Material Index becomes the stable bridge between raw materials and generated deliverables.
