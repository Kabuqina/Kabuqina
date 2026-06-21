# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""PDF and standalone HTML document writers."""

from __future__ import annotations

import io
import logging
import os
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Tuple

from tools.registry import tool_error
from tools.document.common import (
    DocumentSpecError,
    _PDF_TEMPLATES,
    _json,
    _text,
    _validate_write_path,
)
from tools.document.spec import (
    _build_pdf_html,
    _build_pdf_spec,
    _build_standalone_html,
    _document_spec_error,
)

logger = logging.getLogger(__name__)


def _count_pdf_pages(pdf_bytes: bytes) -> int:
    try:
        from pypdf import PdfReader

        return len(PdfReader(io.BytesIO(pdf_bytes)).pages)
    except Exception:
        return 0


def _render_pdf_from_html(html_source: str) -> Tuple[bytes, int, str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ImportError(
            "HTML print PDF rendering requires the Python Playwright package."
        ) from exc

    launch_attempts: List[str] = []
    with sync_playwright() as pw:
        launch_options: List[Dict[str, Any]] = []
        browser_path = _text(os.getenv("HERMESDESK_PDF_BROWSER_PATH"))
        if browser_path:
            launch_options.append({"executable_path": browser_path, "headless": True})

        channel = _text(os.getenv("HERMESDESK_PDF_BROWSER_CHANNEL"))
        if channel:
            launch_options.append({"channel": channel, "headless": True})
        elif sys.platform.startswith("win"):
            launch_options.append({"channel": "msedge", "headless": True})

        launch_options.append({"headless": True})

        browser = None
        for options in launch_options:
            try:
                browser = pw.chromium.launch(**options)
                break
            except Exception as exc:
                launch_attempts.append(f"{options}: {exc}")
        if browser is None:
            detail = "; ".join(launch_attempts) or "no launch attempts"
            raise RuntimeError(f"Could not launch Chromium for PDF printing: {detail}")

        try:
            page = browser.new_page(viewport={"width": 794, "height": 1123})
            page.set_content(html_source, wait_until="load")
            page.emulate_media(media="print")
            pdf_bytes = page.pdf(
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
            )
        finally:
            browser.close()

    return pdf_bytes, _count_pdf_pages(pdf_bytes), "chromium_print_v1"


def render_pdf_from_html_source(html_source: str) -> Tuple[bytes, int, str]:
    """Render an arbitrary trusted HTML print source using the core PDF renderer."""
    return _render_pdf_from_html(html_source)


def _wrap_pdf_text(text: str, *, width: int = 78) -> List[str]:
    lines: List[str] = []
    for raw_line in _text(text).splitlines() or [""]:
        if not raw_line:
            lines.append("")
            continue
        lines.extend(textwrap.wrap(raw_line, width=width, break_long_words=True, replace_whitespace=False) or [""])
    return lines


def _render_pdf_with_reportlab(spec: Dict[str, Any]) -> Tuple[bytes, int, str]:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfgen import canvas

    font_name = "STSong-Light"
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(font_name))
    except Exception:
        font_name = "Helvetica"

    template = _PDF_TEMPLATES.get(spec["template"], _PDF_TEMPLATES["academic_report"])
    accent = template["accent"]
    buffer = io.BytesIO()
    page_width, page_height = A4
    margin = 1.8 * cm
    line_height = 14
    page_count = 1
    y = page_height - margin
    c = canvas.Canvas(buffer, pagesize=A4)

    def new_page() -> None:
        nonlocal y, page_count
        c.showPage()
        page_count += 1
        y = page_height - margin

    def ensure(space: float = line_height) -> None:
        if y - space < margin:
            new_page()

    def draw_text(text: str, *, size: int = 10, leading: int = line_height, indent: float = 0, font: str = font_name) -> None:
        nonlocal y
        for line in _wrap_pdf_text(text, width=88 if size <= 10 else 64):
            ensure(leading)
            c.setFont(font, size)
            c.drawString(margin + indent, y, line)
            y -= leading

    c.setTitle(_text(spec.get("title")))
    c.setAuthor("Kabuqina")
    c.setFillColorRGB(accent[0] / 255, accent[1] / 255, accent[2] / 255)
    draw_text(_text(spec.get("title")), size=18, leading=24)
    c.setFillColorRGB(0.39, 0.45, 0.55)
    draw_text(f"{spec.get('template_name')} · {spec.get('template_subtitle')}", size=9, leading=16)
    c.setStrokeColorRGB(accent[0] / 255, accent[1] / 255, accent[2] / 255)
    c.line(margin, y, page_width - margin, y)
    y -= 18
    c.setFillColorRGB(0.07, 0.09, 0.15)

    for block in spec.get("blocks") or []:
        block_type = block.get("type")
        if block_type == "page_break":
            new_page()
            continue
        if block_type == "heading":
            level = int(block.get("level") or 2)
            y -= 4
            c.setFillColorRGB(0.07, 0.09, 0.15)
            draw_text(_text(block.get("text")), size=15 if level <= 2 else 12, leading=20 if level <= 2 else 16)
            continue
        if block_type == "bullets":
            for item in block.get("items") or []:
                draw_text(f"• {item}", indent=10)
            y -= 4
            continue
        if block_type == "table":
            headers = block.get("headers") or []
            rows = block.get("rows") or []
            if headers:
                draw_text(" | ".join(headers), size=9, leading=13)
            for row in rows:
                draw_text(" | ".join(row), size=9, leading=13)
            y -= 6
            continue
        if block_type == "code":
            language = _text(block.get("language"))
            if language:
                draw_text(language, size=8, leading=12)
            for line in _wrap_pdf_text(_text(block.get("text")), width=90):
                draw_text(line, size=8, leading=11, font="Courier")
            y -= 6
            continue
        if block_type == "formula":
            draw_text(_text(block.get("text")), size=11, leading=15)
            y -= 6
            continue
        if block_type == "image_placeholder":
            ensure(54)
            c.setStrokeColorRGB(0.58, 0.64, 0.72)
            c.rect(margin, y - 46, page_width - 2 * margin, 42, stroke=1, fill=0)
            c.setFillColorRGB(0.29, 0.33, 0.41)
            c.setFont(font_name, 9)
            c.drawString(margin + 10, y - 20, _text(block.get("label")))
            c.drawString(margin + 10, y - 34, _text(block.get("caption") or block.get("source_hint")))
            y -= 58
            c.setFillColorRGB(0.07, 0.09, 0.15)
            continue
        draw_text(_text(block.get("text")), size=10, leading=14)
        y -= 4

    c.save()
    return buffer.getvalue(), page_count, "reportlab_pdf_v1"


def pdf_write(
    path: str,
    title: str,
    document: Any,
    template: str = "academic_report",
    visual_master: str = "default_print",
) -> str:
    """Create a PDF and adjacent HTML source from a structured document spec."""
    if not _text(path):
        return tool_error("pdf_write requires an output path.", code="missing_path")
    out = Path(path).expanduser()
    if out.suffix.lower() != ".pdf":
        out = out.with_suffix(".pdf")

    validation_error = _validate_write_path(out, path)
    if validation_error is not None:
        return validation_error

    try:
        spec = _build_pdf_spec(title, document, template, visual_master)
    except DocumentSpecError as exc:
        return _document_spec_error(exc)
    html_source = _build_pdf_html(spec)
    warnings: List[str] = []
    try:
        pdf_bytes, page_count, renderer = _render_pdf_from_html(html_source)
    except Exception as html_exc:
        warnings.append(f"HTML print renderer unavailable; fell back to ReportLab: {html_exc}")
        try:
            pdf_bytes, page_count, renderer = _render_pdf_with_reportlab(spec)
        except ImportError as exc:
            return tool_error(
                (
                    "PDF rendering requires either Chromium/Playwright or ReportLab "
                    f"in the desktop Python bundle. HTML print error: {html_exc}; "
                    f"ReportLab error: {exc}"
                ),
                code="pdf_render_unavailable",
            )
        except Exception as exc:
            return tool_error(
                f"PDF rendering failed. HTML print error: {html_exc}; ReportLab error: {exc}",
                code="pdf_render_failed",
            )

    out.parent.mkdir(parents=True, exist_ok=True)
    html_path = out.with_suffix(".html")
    out.write_bytes(pdf_bytes)
    html_path.write_text(html_source, encoding="utf-8")
    payload = {
        "ok": True,
        "path": str(out),
        "html_path": str(html_path),
        "page_count": int(page_count),
        "template": spec["template"],
        "visual_master": spec["visual_master"],
        "renderer": renderer,
        "bytes": len(pdf_bytes),
    }
    if warnings:
        payload["warnings"] = warnings
    return _json(payload)


def html_write(
    path: str,
    title: str,
    document: Any,
    template: str = "academic_report",
    visual_master: str = "default_web",
) -> str:
    """Create a standalone .html deliverable from a structured document spec.

    This is the first-class HTML writer (not the print sidecar that pdf_write
    emits). It consumes the same structured document/blocks contract as pdf_write
    so the reader -> material_index -> planner layers can target either format,
    then renders a responsive, self-contained HTML page.
    """
    if not _text(path):
        return tool_error("html_write requires an output path.", code="missing_path")
    out = Path(path).expanduser()
    if out.suffix.lower() not in (".html", ".htm"):
        out = out.with_suffix(".html")

    validation_error = _validate_write_path(out, path)
    if validation_error is not None:
        return validation_error

    try:
        spec = _build_pdf_spec(title, document, template, visual_master)
    except DocumentSpecError as exc:
        return _document_spec_error(exc)
    html_source = _build_standalone_html(spec)

    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html_source, encoding="utf-8")
    except OSError as exc:
        return tool_error(f"HTML write failed: {exc}", code="html_write_failed")

    return _json(
        {
            "ok": True,
            "path": str(out),
            "template": spec["template"],
            "visual_master": spec["visual_master"],
            "renderer": "standalone_html_v1",
            "block_count": len(spec.get("blocks") or []),
            "bytes": len(html_source.encode("utf-8")),
        }
    )
