"""Document read/write tools for student deliverables."""

from __future__ import annotations

import json
import logging
import os
import sys
import hashlib
import html
import io
import tempfile
import threading
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tools.deliverable_contract import slide_layout_set, slide_type_set
from tools.registry import registry, tool_error
from tools.document.common import (
    _text, _list, _string_list, _dict, DocumentSpecError, Rgb,
    _PDF_BLOCK_TYPES, _PDF_TEMPLATES, _PPTX_SLIDE_TYPES, _PPTX_SLIDE_LAYOUTS,
    _desktop_workspace_root, _is_outside_workspace, _json,
    _power_user_reads_anywhere, _validate_read_path, _validate_write_path,
)
from tools.document.pptx_writer import pptx_write
from tools.document.reading import (
    warm_docling_converter, reset_docling_converter_cache,
    pdf_read_precise, document_read_precise,
    _persist_read_result, _load_read_result,
)
from tools.document.latex_render import (
    _LATEX_SYMBOLS, _latex_group, _latex_atom,
    _latex_command_html, _render_latex_html, _formula_to_html,
)
from tools.document.spec import (
    _normalize_pdf_template, _pdf_block, _pdf_section_blocks, _repair_jsonish,
    _coerce_json_container, _document_spec_error, _pdf_blocks, _build_pdf_spec,
    _block_to_html, _build_pdf_html, _build_standalone_html,
)
from tools.document.pdf_writer import (
    _count_pdf_pages, _render_pdf_from_html, render_pdf_from_html_source,
    _wrap_pdf_text, _render_pdf_with_reportlab, pdf_write, html_write,
)
from tools.document.docx_writer import _docx_add_block, _render_docx, docx_write

logger = logging.getLogger(__name__)



# Slide-object vocabulary is owned by tools/deliverable_contract.py — the single
# source of truth shared with the planner prompt (agent/prompt_builder.py) so the
# writer normalizes against the exact set the planner is told to emit.

# Optional per-slide layout hints the planner may set; the web renderer
# (renderDeck.ts) auto-selects by content when omitted. Keep in sync with
# SLIDE_LAYOUT_IDS in web/src/chat/pptx/renderDeck.ts.


from tools.document.schemas import (
    PDF_READ_PRECISE_SCHEMA,
    DOCUMENT_READ_PRECISE_SCHEMA,
    PDF_WRITE_SCHEMA,
    HTML_WRITE_SCHEMA,
    DOCX_WRITE_SCHEMA,
    PPTX_WRITE_SCHEMA,
)
registry.register(
    name="pdf_read_precise",
    toolset="documents",
    schema=PDF_READ_PRECISE_SCHEMA,
    handler=lambda args, **kw: pdf_read_precise(
        path=args.get("path", ""),
        mode=args.get("mode", "auto"),
        include_content=bool(args.get("include_content", True)),
        page_start=args.get("page_start"),
        page_end=args.get("page_end"),
    ),
    check_fn=lambda: True,
    emoji="📄",
)

registry.register(
    name="document_read_precise",
    toolset="documents",
    schema=DOCUMENT_READ_PRECISE_SCHEMA,
    handler=lambda args, **kw: document_read_precise(
        path=args.get("path", ""),
        mode=args.get("mode", "auto"),
        include_content=bool(args.get("include_content", True)),
        page_start=args.get("page_start"),
        page_end=args.get("page_end"),
    ),
    check_fn=lambda: True,
    emoji="📚",
)

registry.register(
    name="pdf_write",
    toolset="documents",
    schema=PDF_WRITE_SCHEMA,
    handler=lambda args, **kw: pdf_write(
        path=args.get("path", ""),
        title=args.get("title", ""),
        document=args.get("document") or {},
        template=args.get("template", "academic_report"),
        visual_master=args.get("visual_master", "default_print"),
    ),
    check_fn=lambda: True,
    emoji="📝",
)

registry.register(
    name="html_write",
    toolset="documents",
    schema=HTML_WRITE_SCHEMA,
    handler=lambda args, **kw: html_write(
        path=args.get("path", ""),
        title=args.get("title", ""),
        document=args.get("document") or {},
        template=args.get("template", "academic_report"),
        visual_master=args.get("visual_master", "default_web"),
    ),
    check_fn=lambda: True,
    emoji="🌐",
)

registry.register(
    name="docx_write",
    toolset="documents",
    schema=DOCX_WRITE_SCHEMA,
    handler=lambda args, **kw: docx_write(
        path=args.get("path", ""),
        title=args.get("title", ""),
        document=args.get("document") or {},
        template=args.get("template", "academic_report"),
        visual_master=args.get("visual_master", "default_docx"),
    ),
    check_fn=lambda: True,
    emoji="📄",
)

registry.register(
    name="pptx_write",
    toolset="documents",
    schema=PPTX_WRITE_SCHEMA,
    handler=lambda args, **kw: pptx_write(
        path=args.get("path", ""),
        title=args.get("title", ""),
        slides=args.get("slides") or [],
        template=args.get("template", "course_report"),
        visual_master=args.get("visual_master", "default_native"),
        meta=args.get("meta"),
        template_path=args.get("template_path", ""),
        callback=kw.get("callback"),
    ),
    check_fn=lambda: True,
    emoji="📊",
)
