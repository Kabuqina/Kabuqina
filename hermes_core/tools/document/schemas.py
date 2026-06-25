# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""JSON tool schemas for the document read/write tools.

Extracted verbatim from tools/document_tools.py (large-file split, step 1).
Pure data, no logic; document_tools re-imports these for tool registration.
"""

PDF_READ_PRECISE_SCHEMA = {
    "name": "pdf_read_precise",
    "description": (
        "Read a PDF for student work. Path must be inside the Kabuqina "
        "workspace (file tools cannot read D: or other folders directly). "
        "If the PDF is elsewhere, copy it into the workspace with terminal first. "
        "DEFAULT to mode=auto: it extracts text in well under a second and is the "
        "right choice for understanding or summarizing a document. Only escalate to "
        "the much slower mode=precise (layout + tables) or mode=math (LaTeX formula "
        "enrichment) when the user explicitly needs faithful tables, layout, or "
        "formulas — those run heavy ML models and take minutes on a CPU-only machine. "
        "Do not use vision_analyze for a normal PDF unless this reader fails or the "
        "user explicitly asks for visual image description."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "mode": {"type": "string", "description": "auto (default, fast text — use this unless told otherwise), precise (slow: layout + tables, no formulas), or math (slow: layout + LaTeX formula extraction, tables skipped for speed — use precise when you need tables). precise/math run ML models on CPU and take longer the more pages/formulas/tables the document has."},
            "page_start": {"type": "integer", "description": "Optional 1-based first page for Docling precise/math reads. Use with mode=math to extract formulas from a focused page range instead of the whole PDF."},
            "page_end": {"type": "integer", "description": "Optional 1-based last page for Docling precise/math reads. If omitted while page_start is set, only page_start is read."},
            "include_content": {
                "type": "boolean",
                "description": "Return extracted content inline. Set false to return only read_id/cache metadata for downstream tools.",
            },
        },
        "required": ["path"],
    },
}

DOCUMENT_READ_PRECISE_SCHEMA = {
    "name": "document_read_precise",
    "description": (
        "Read student documents (PDF, DOCX, PPTX, XLSX, HTML, Markdown, CSV, common "
        "images, text). Legacy .doc must be converted to .docx or .pdf first. "
        "DEFAULT to mode=auto: fast text extraction, the right choice for reading or "
        "summarizing. Only escalate to the much slower mode=precise (layout + tables) "
        "or mode=math (LaTeX formula enrichment) when the user explicitly needs "
        "faithful tables, layout, or formulas — those run ML models that take minutes "
        "on a CPU-only machine. Uses format-specific text fallbacks when Docling fails "
        "and reports the real Docling error."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "mode": {"type": "string", "description": "auto (default, fast text — use this unless told otherwise), precise (slow: layout + tables, no formulas), or math (slow: layout + LaTeX formula extraction, tables skipped for speed — use precise when you need tables). precise/math run ML models on CPU and take longer the more pages/formulas/tables the document has."},
            "page_start": {"type": "integer", "description": "Optional 1-based first page for PDF Docling precise/math reads. Use with mode=math to extract formulas from a focused page range instead of the whole PDF."},
            "page_end": {"type": "integer", "description": "Optional 1-based last page for PDF Docling precise/math reads. If omitted while page_start is set, only page_start is read."},
            "include_content": {
                "type": "boolean",
                "description": "Return extracted content inline. Set false to return only read_id/cache metadata for downstream tools.",
            },
        },
        "required": ["path"],
    },
}

PDF_WRITE_SCHEMA = {
    "name": "pdf_write",
    "description": (
        "Create a print-ready .pdf file from structured report content and save an "
        "adjacent HTML source file for inspection. Use this as the normal writer-layer "
        "PDF path for reports, math/code explanations, tables, checklists, formulas, "
        "and visual placeholders. The v1 renderer builds normalized blocks, treats "
        "the HTML source as the canonical print input, renders it with Chromium "
        "(renderer chromium_print_v1), and falls back to ReportLab only when the "
        "HTML print backend is unavailable."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Output PDF path. The .pdf suffix is added when omitted."},
            "title": {"type": "string"},
            "template": {
                "type": "string",
                "description": "academic_report, code_report, math_report, or brief. Unknown values fall back to academic_report.",
            },
            "visual_master": {
                "type": "string",
                "description": "Optional print styling label. Defaults to default_print.",
            },
            "document": {
                "type": "object",
                "description": (
                    "Structured document spec passed as a JSON OBJECT, not a JSON "
                    "string. Do not stringify it and do not hand-build escaped JSON — "
                    "emit a real object so quotes in the source text are handled for "
                    "you. Prefer sections or blocks. Supported block types: heading, "
                    "paragraph, bullets, table, code, formula, image_placeholder, "
                    "page_break."
                ),
                "properties": {
                    "sections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "paragraphs": {"type": "array", "items": {"type": "string"}},
                                "bullets": {"type": "array", "items": {"type": "string"}},
                                "table": {"type": "object", "description": "Use headers and rows arrays."},
                                "code": {"type": "string"},
                                "language": {"type": "string"},
                                "formula": {"type": "string"},
                                "placeholder": {"type": "object"},
                            },
                        },
                    },
                    "blocks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "text": {"type": "string"},
                                "level": {"type": "integer"},
                                "items": {"type": "array", "items": {"type": "string"}},
                                "headers": {"type": "array", "items": {"type": "string"}},
                                "rows": {"type": "array"},
                                "code": {"type": "string"},
                                "language": {"type": "string"},
                                "latex": {"type": "string"},
                                "label": {"type": "string"},
                                "caption": {"type": "string"},
                                "source_hint": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        "required": ["path", "title", "document"],
    },
}

HTML_WRITE_SCHEMA = {
    "name": "html_write",
    "description": (
        "Create a standalone, responsive .html file from structured report content. "
        "Use this as the writer-layer HTML path for web reports, study notes, "
        "summaries, and shareable documents. Consumes the same structured "
        "document/blocks contract as pdf_write (sections or blocks of heading, "
        "paragraph, bullets, table, code, formula, image_placeholder, page_break), "
        "so the same outline can be rendered to PDF or HTML."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Output HTML path. The .html suffix is added when omitted."},
            "title": {"type": "string"},
            "template": {
                "type": "string",
                "description": "academic_report, code_report, math_report, or brief. Unknown values fall back to academic_report.",
            },
            "visual_master": {
                "type": "string",
                "description": "Optional styling label. Defaults to default_web.",
            },
            "document": {
                "type": "object",
                "description": (
                    "Structured document spec passed as a JSON OBJECT, not a JSON "
                    "string. Do not stringify it and do not hand-build escaped JSON — "
                    "emit a real object so quotes in the source text are handled for "
                    "you. Prefer sections or blocks. Supported block types: heading, "
                    "paragraph, bullets, table, code, formula, image_placeholder, "
                    "page_break."
                ),
                "properties": {
                    "sections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "paragraphs": {"type": "array", "items": {"type": "string"}},
                                "bullets": {"type": "array", "items": {"type": "string"}},
                                "table": {"type": "object", "description": "Use headers and rows arrays."},
                                "code": {"type": "string"},
                                "language": {"type": "string"},
                                "formula": {"type": "string"},
                                "placeholder": {"type": "object"},
                            },
                        },
                    },
                    "blocks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "text": {"type": "string"},
                                "level": {"type": "integer"},
                                "items": {"type": "array", "items": {"type": "string"}},
                                "headers": {"type": "array", "items": {"type": "string"}},
                                "rows": {"type": "array"},
                                "code": {"type": "string"},
                                "language": {"type": "string"},
                                "latex": {"type": "string"},
                                "label": {"type": "string"},
                                "caption": {"type": "string"},
                                "source_hint": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        "required": ["path", "title", "document"],
    },
}

DOCX_WRITE_SCHEMA = {
    "name": "docx_write",
    "description": (
        "Create an editable .docx (Word) file from structured report content. Use "
        "this as the writer-layer Word path for reports, study notes, summaries, and "
        "documents the user wants to keep editing in Word. Consumes the same "
        "structured document/blocks contract as pdf_write and html_write (sections "
        "or blocks of heading, paragraph, bullets, table, code, formula, "
        "image_placeholder, page_break), so the same outline can target Word, PDF, "
        "or HTML."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Output DOCX path. The .docx suffix is added when omitted."},
            "title": {"type": "string"},
            "template": {
                "type": "string",
                "description": "academic_report, code_report, math_report, or brief. Unknown values fall back to academic_report.",
            },
            "visual_master": {
                "type": "string",
                "description": "Optional styling label. Defaults to default_docx.",
            },
            "document": {
                "type": "object",
                "description": (
                    "Structured document spec passed as a JSON OBJECT, not a JSON "
                    "string. Do not stringify it and do not hand-build escaped JSON — "
                    "emit a real object so quotes in the source text are handled for "
                    "you. Prefer sections or blocks. Supported block types: heading, "
                    "paragraph, bullets, table, code, formula, image_placeholder, "
                    "page_break."
                ),
                "properties": {
                    "sections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "paragraphs": {"type": "array", "items": {"type": "string"}},
                                "bullets": {"type": "array", "items": {"type": "string"}},
                                "table": {"type": "object", "description": "Use headers and rows arrays."},
                                "code": {"type": "string"},
                                "language": {"type": "string"},
                                "formula": {"type": "string"},
                                "placeholder": {"type": "object"},
                            },
                        },
                    },
                    "blocks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "text": {"type": "string"},
                                "level": {"type": "integer"},
                                "items": {"type": "array", "items": {"type": "string"}},
                                "headers": {"type": "array", "items": {"type": "string"}},
                                "rows": {"type": "array"},
                                "code": {"type": "string"},
                                "language": {"type": "string"},
                                "latex": {"type": "string"},
                                "label": {"type": "string"},
                                "caption": {"type": "string"},
                                "source_hint": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        "required": ["path", "title", "document"],
    },
}

PPTX_WRITE_SCHEMA = {
    "name": "pptx_write",
    "description": (
        "Create a high-quality student-facing .pptx deck from structured slide content. "
        "Slides can use editable structured types such as agenda, claim_bullets, "
        "diagram, table, screenshot_placeholder, chart_placeholder, qa_backup, and closing. "
        "Templates apply distinct visual themes: course_report (blue classroom), "
        "paper_report (green academic), code_defense (indigo/orange tech defense), "
        "sandtable_review (navy/gold business review). "
        "The deck is rendered by PptxGenJS in the Kabuqina desktop UI using the selected "
        "visual_master palette. Always CALL this tool to generate the deck — do not "
        "refuse or claim the renderer is unavailable in advance. Only if the call itself "
        "returns an error (e.g. code pptx_render_unavailable) should you report that."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "title": {"type": "string"},
            "template": {"type": "string", "description": "course_report, paper_report, code_defense, or sandtable_review"},
            "visual_master": {
                "type": "string",
                "description": (
                    "default_native, soft_editorial, blue_professional, signal, "
                    "neo_grid_bold, or editorial_forest. Use the visual master selected by the user."
                ),
            },
            "meta": {
                "type": "object",
                "description": (
                    "Deck-level cover metadata: author, affiliation, date, citation. "
                    "Put presenter / source info HERE so it renders on the cover — never "
                    "cram author or citation lines into an agenda or content slide."
                ),
                "properties": {
                    "author": {"type": "string"},
                    "affiliation": {"type": "string"},
                    "date": {"type": "string"},
                    "citation": {"type": "string"},
                },
            },
            "template_path": {
                "type": "string",
                "description": (
                    "Optional path to a school/course-provided .pptx the student uploaded "
                    "(must be inside the workspace). Its colours and fonts are extracted and "
                    "applied so the deck matches the required look. Unreadable templates are "
                    "ignored and the selected visual_master is used instead."
                ),
            },
            "slides": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "slide_type": {
                            "type": "string",
                            "description": (
                                "agenda, claim_bullets, diagram, table, screenshot_placeholder, "
                                "chart_placeholder, qa_backup, closing. Unknown values fall back to claim_bullets."
                            ),
                        },
                        "title": {"type": "string"},
                        "subtitle": {"type": "string"},
                        "layout": {
                            "type": "string",
                            "description": (
                                "Optional per-slide layout: hero_statement, standard_bullets, "
                                "two_column_bullets, comparison_cards, process_flow_horizontal, "
                                "process_flow_vertical, data_table, media_placeholder, section_divider, "
                                "stat_callout, big_number_grid, pull_quote, icon_grid, timeline, "
                                "image_text_split. "
                                "Omit to let the renderer auto-select by this page's content."
                            ),
                        },
                        "bullets": {"type": "array", "items": {"type": "string"}},
                        "notes": {"type": "string"},
                        "diagram": {
                            "type": "object",
                            "description": "For diagram slides. Use nodes or steps as an array of short labels.",
                        },
                        "table": {
                            "type": "object",
                            "description": (
                                "For table, comparison, experiment, and evidence slides. Use headers "
                                "and rows arrays so the renderer can create designed evidence cards or "
                                "editable tables instead of plain bullet columns."
                            ),
                        },
                        "placeholder": {
                            "type": "object",
                            "description": (
                                "For screenshot/chart placeholders. Use label, caption, and optional source_hint. "
                                "For chart_placeholder, include numeric clues in bullets or caption when the "
                                "source has values. Do not claim a real asset was inserted when using a placeholder."
                            ),
                        },
                        "metrics": {
                            "type": "array",
                            "description": (
                                "Optional structured numbers for metric slides: array of {value, label} "
                                "(e.g. {\"value\": \"84%\", \"label\": \"准确率\"}). The renderer shows these as "
                                "large stat callouts — prefer this over burying numbers in bullet prose."
                            ),
                        },
                        "emphasis": {
                            "type": "object",
                            "description": (
                                "Optional design intent for one spotlight element: {kind: \"stat\"|\"quote\", "
                                "value, label}. kind=stat highlights the key number; kind=quote renders value as "
                                "a large thesis/contribution line."
                            ),
                        },
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title", "bullets"],
                },
            },
        },
        "required": ["path", "title", "slides"],
    },
}
