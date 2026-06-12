# PDF writer path implementation plan

## Goal

Add a first-class writer-layer path for producing PDFs so agents can call a normal tool instead of improvising HTML files or claiming PDF output is unavailable.

## Scope

- Add `pdf_write` in `hermes_core/tools/document_tools.py`.
- Accept a structured document spec that can cover reports, math/code explanations, tables, checklists, formulas, and visual placeholders.
- Produce a PDF file plus an adjacent HTML preview/source file.
- Register the tool and expose it in capability prompts.
- Add desktop dependency metadata for the renderer.
- Keep the change core-owned; no overlay behavior is needed.

## Content model

The first version supports print-friendly blocks:

- `heading`
- `paragraph`
- `bullets`
- `table`
- `code`
- `formula`
- `image_placeholder`
- `page_break`

## Rendering path

`document spec -> normalized blocks -> HTML source -> ReportLab PDF`

ReportLab is the concrete PDF backend for v1 because it is deterministic in Python, works without a browser subprocess, and fits the owned core writer layer. The HTML source is still generated as a sidecar for inspectability and future HTML-to-PDF backend swaps.

## Verification

- Unit tests for `pdf_write` path validation, PDF + HTML sidecar output, schema registration, and capability prompt guidance.
- Run existing document tool tests and capability tests.
- Run broader Python test suite if targeted tests pass.
