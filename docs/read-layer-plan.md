# Read Layer Generalization and Performance Plan

> Status: **Phase 1 implemented**  
> Last updated: 2026-05-31

The Read layer is Kabuqina's source-material ingestion layer. It is the shared
foundation for PPT generation, Word/report generation, study notes, summaries,
code defense workflows, and future file-based agent tasks.

It should be strong enough that downstream layers can assume:

- source files have been opened through one consistent tool contract;
- parser uncertainty is preserved rather than hidden;
- large content can be passed by reference when inline content would waste
  context;
- improvements to one reader benefit every downstream generator.

## Position in the Pipeline

```text
Read Layer
  -> Material Index
    -> Planner
      -> Writer
```

Read belongs in `hermes_core` because reading source files is agent/tool
semantics, not Tauri shell glue. Desktop-only runtime concerns, such as bundled
Python paths and Docling model packaging, remain in `python/` or `tauri/`.

## Tool Contract

Current public tools:

- `document_read_precise`
- `pdf_read_precise`

`pdf_read_precise` is now a PDF-specific wrapper around the common document read
pipeline. New format behavior should normally be added to the common pipeline
first, then exposed through specialized wrappers only when the UX really needs a
named action.

Common result fields:

```json
{
  "ok": true,
  "engine": "docling | pypdf | python-docx | python-pptx | openpyxl | text",
  "mode": "auto | fast | precise | math | fallback",
  "path": "D:/.../source.pdf",
  "content": "markdown or extracted text",
  "read_id": "read-cache-handle",
  "cache_path": "D:/.../read-cache/<read_id>.json",
  "content_chars": 12345,
  "metadata": {
    "kind": "pdf | docx | pptx | xlsx | markdown | text | ...",
    "suffix": ".pdf",
    "source_name": "source.pdf",
    "parser_engine": "docling",
    "read_id": "read-cache-handle"
  }
}
```

When `include_content=false`, the tool returns the same metadata but omits the
inline `content` field:

```json
{
  "ok": true,
  "read_id": "read-cache-handle",
  "cache_path": "D:/.../read-cache/<read_id>.json",
  "content": "",
  "content_omitted": true,
  "content_hint": "Content is stored in read-cache; pass read_id to material_index_build."
}
```

This is the preferred path for large materials that will be consumed by
`material_index_build`, because it avoids sending the same full document through
the model twice.

## Format Routing

The common Read pipeline chooses between Docling and local lightweight parsers.

| Format | `auto` / `fast` behavior | `precise` behavior | `math` behavior | Fallback |
|--------|--------------------------|--------------------|-----------------|----------|
| `.pdf` | Docling first | Docling precise profile | Docling with formula enrichment | `pypdf` text |
| `.docx` | `python-docx` first | Docling first | Docling with formula enrichment where supported | `python-docx` text/tables |
| `.pptx` | `python-pptx` first | Docling first | Docling with formula enrichment where supported | `python-pptx` slides/tables |
| `.xlsx` | `openpyxl` first | Docling first | Docling first | `openpyxl` sheets |
| `.md`, `.txt`, `.csv`, `.html` | plain text first | Docling first where supported | Docling first where supported | plain text |
| common images | Docling first | Docling first | Docling with formula enrichment where supported | no local fallback yet |
| `.doc` | rejected with conversion hint | rejected with conversion hint | rejected with conversion hint | none |

The intent is conservative:

- PDF keeps Docling-first semantics because "precise PDF" is the important user
  path.
- Office/text-like formats avoid torch/Docling cold-start cost in `auto` mode
  when local parsers can return useful text immediately.
- `precise` remains available when structure/OCR fidelity matters more than
  speed.
- `math` is explicit because formula enrichment can be much slower and may need
  additional Docling model artifacts. It should be used for papers, textbooks,
  and formula-heavy homework, not ordinary document reads.

## Read Cache

Every successful read is persisted into a local Read cache. The cache record is a
JSON copy of the Read result including `content`, parser metadata, warnings, and
any `docling_error`.

Cache root resolution:

1. `HERMESDESK_DATA_DIR/read-cache`
2. `HERMES_HOME/read-cache`
3. `%LOCALAPPDATA%/read-cache`
4. temp directory fallback

`read_id` is a stable content-derived handle for the parsed result. It is not a
security boundary; normal workspace/path policy still applies to the original
read. Downstream tools should treat the cached payload as trusted only to the
same degree as the original Read tool output.

## Material Index Integration

`material_index_build` still accepts inline content:

```json
{
  "name": "paper.pdf",
  "kind": "pdf",
  "content": "...",
  "metadata": {"engine": "docling"}
}
```

It also accepts a Read-layer handle:

```json
{
  "name": "paper.pdf",
  "read_id": "read-cache-handle",
  "metadata": {"engine": "docling"}
}
```

If `content` is empty and `read_id` is present, Material Index loads the cached
Read content directly. This keeps Material Index deterministic and non-LLM while
removing the expensive content round-trip for large files.

## Error and Uncertainty Policy

Read failures should distinguish:

- unsupported file type;
- workspace/path policy denial;
- Docling import/runtime/backend failure;
- local fallback failure;
- successful fallback with reduced fidelity.

Docling errors are surfaced in `docling_error` when a fallback succeeds. The Read
layer should not pretend the result is precise when it is text-only fallback.
Downstream layers should use `warning`, `docling_error`, and Material Index's
`uncertain_parts` to decide whether to ask the user for verification.

## Performance Strategy

Implemented in Phase 1:

- single common read pipeline for PDF and general documents;
- Docling converter cache retained;
- Docling/torch work serialized on one worker thread;
- lightweight-first routing for text-like and Office formats in `auto`/`fast`;
- local Read cache for all successful reads;
- `include_content=false` for by-reference downstream consumption;
- `material_index_build` can consume `read_id` directly.
- `mode=math` as a real Docling profile, with
  `PdfPipelineOptions.do_formula_enrichment=True` and code enrichment disabled.

Expected effect:

- first PDF precise read still pays Docling cost, but no longer defines the
  performance profile for every document type;
- Markdown/text/CSV and Office reads can complete without torch initialization;
- large generation workflows avoid duplicate token transfer between Read and
  Material Index.

## Non-Goals

The Read layer does not:

- decide PPT/story/report structure;
- select which evidence matters most;
- generate output files;
- call an LLM to repair or interpret extracted content;
- fabricate missing figures, screenshots, formulas, tables, or citations.

Formula-to-LaTeX, formula-to-code, image OCR, and richer layout reconstruction
belong here when implemented, but they should still report uncertainty rather
than silently inventing missing material.

## Next Phases

1. **Structured formula output**
   `mode=math` now enables Docling formula enrichment, but the public Read result
   still primarily returns Markdown/text. Next, expose detected formulas as a
   structured `formulas[]` collection with page/source references and uncertainty
   markers where Docling provides enough signal.

2. **Legacy Office conversion**
   Add optional LibreOffice headless conversion for `.doc`/`.ppt` if bundle size
   and operational cost become acceptable.

3. **Image and screenshot reading**
   Add a first-class image/OCR branch that can produce source metadata and
   uncertainty in the same Read contract.

4. **Cache lifecycle**
   Add retention policy, cache pruning, and possibly session-scoped cache
   ownership so long-running student workflows do not leak stale files forever.

5. **Structured read artifacts**
   Evolve beyond one `content` string toward optional structured sections,
   tables, figures, equations, pages/slides, and assets while keeping backward
   compatibility.

6. **Bundle/runtime observability**
   Keep Docling runtime diagnostics precise: Python executable, torch version,
   model artifact path, parser profile, and fallback engine should remain easy
   to inspect from tool output/logs.

## Test Coverage

Primary tests live in:

- `hermes_core/tests/tools/test_document_tools.py`
- `hermes_core/tests/tools/test_material_index_tools.py`

Important contracts covered:

- workspace path rejection;
- PDF fallback behavior;
- Docling converter caching/profile selection;
- torch/runtime error formatting;
- lightweight text reads skip Docling in `auto` mode;
- reads write `read_id`/`cache_path`;
- `include_content=false` omits inline content but preserves cache;
- `pdf_read_precise` uses the common pipeline;
- `material_index_build` can load cached content by `read_id`.
