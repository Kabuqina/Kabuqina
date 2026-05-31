# Material Index

Material Index is Kabuqina's general evidence layer for generated files.

It sits between file reading and file writing:

1. **Read layer** reads files and attachments.
2. **Material Index** organizes already-read content into reusable evidence.
3. **Planners** choose story, format, and output structure.
4. **Writers** render concrete files such as PPTX today and other formats later.

Material Index is not a PPT-specific schema. PPT is the first consumer because the current student deliverable work starts with PPT generation, but the same index should support future Word reports, study notes, summaries, project documentation, and other generated documents.

## v1 Contract

`material_index_build` consumes already-read materials:

```json
{
  "profile": "paper_report",
  "materials": [
    {
      "name": "source.pdf",
      "kind": "pdf",
      "content": "markdown or text from the read layer",
      "read_id": "optional-read-cache-handle",
      "metadata": {
        "engine": "docling",
        "pages": 12
      }
    }
  ]
}
```

It returns bounded structured evidence:

```json
{
  "ok": true,
  "version": 1,
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

## Boundaries

- It does not open paths.
- It does not OCR files.
- It does not call an LLM.
- It does not invent real screenshots, charts, citations, or test results.
- It preserves source references so planners can cite or trace material.
- Format-specific hints live under `generation_hints.<format>`.

For large materials, `content` may be omitted when the material includes a
`read_id` returned by `document_read_precise` or `pdf_read_precise`; Material
Index will load the cached Read-layer content directly.
