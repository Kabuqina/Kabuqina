# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Shared structured document spec normalization and HTML rendering."""

from __future__ import annotations

import html
import json
from typing import Any, Dict, List

from tools.registry import tool_error
from tools.document.common import (
    DocumentSpecError,
    _PDF_BLOCK_TYPES,
    _PDF_TEMPLATES,
    _dict,
    _list,
    _string_list,
    _text,
)
from tools.document.latex_render import _formula_to_html


def _normalize_pdf_template(template: str) -> str:
    key = _text(template).lower()
    return key if key in _PDF_TEMPLATES else "academic_report"


def _pdf_block(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, str):
        return {"type": "paragraph", "text": raw}
    raw = _dict(raw)
    block_type = _text(raw.get("type") or raw.get("block_type")).lower()
    if block_type not in _PDF_BLOCK_TYPES:
        block_type = "paragraph"
    if block_type == "heading":
        level = raw.get("level", 2)
        try:
            level = max(1, min(4, int(level)))
        except (TypeError, ValueError):
            level = 2
        return {"type": "heading", "level": level, "text": _text(raw.get("text") or raw.get("title"))}
    if block_type == "bullets":
        return {"type": "bullets", "items": _string_list(raw.get("items") or raw.get("bullets"), limit=24)}
    if block_type == "table":
        table = _dict(raw.get("table")) or raw
        headers = _string_list(table.get("headers"), limit=8)
        rows = [_string_list(row, limit=len(headers) or 8) for row in _list(table.get("rows"))[:40]]
        return {"type": "table", "headers": headers, "rows": rows}
    if block_type == "code":
        return {
            "type": "code",
            "language": _text(raw.get("language")),
            "text": _text(raw.get("text") or raw.get("code")),
        }
    if block_type == "formula":
        return {"type": "formula", "text": _text(raw.get("text") or raw.get("latex") or raw.get("formula"))}
    if block_type == "image_placeholder":
        return {
            "type": "image_placeholder",
            "label": _text(raw.get("label") or raw.get("title") or "Image placeholder"),
            "caption": _text(raw.get("caption")),
            "source_hint": _text(raw.get("source_hint")),
        }
    if block_type == "page_break":
        return {"type": "page_break"}
    return {"type": "paragraph", "text": _text(raw.get("text") or raw.get("content") or raw.get("body"))}


def _pdf_section_blocks(section: Dict[str, Any]) -> List[Dict[str, Any]]:
    section = _dict(section)
    blocks: List[Dict[str, Any]] = []
    title = _text(section.get("title") or section.get("heading"))
    if title:
        blocks.append({"type": "heading", "level": 2, "text": title})
    for paragraph in _list(section.get("paragraphs")):
        if _text(paragraph):
            blocks.append({"type": "paragraph", "text": _text(paragraph)})
    content = section.get("content")
    if isinstance(content, list):
        blocks.extend(_pdf_block(item) for item in content)
    elif _text(content):
        blocks.append({"type": "paragraph", "text": _text(content)})
    bullets = _string_list(section.get("bullets"), limit=24)
    if bullets:
        blocks.append({"type": "bullets", "items": bullets})
    if _dict(section.get("table")):
        blocks.append(_pdf_block({"type": "table", "table": section.get("table")}))
    if _text(section.get("code")):
        blocks.append(_pdf_block({"type": "code", "code": section.get("code"), "language": section.get("language")}))
    if _text(section.get("formula") or section.get("latex")):
        blocks.append(_pdf_block({"type": "formula", "text": section.get("formula") or section.get("latex")}))
    placeholder = _dict(section.get("image_placeholder") or section.get("placeholder"))
    if placeholder:
        blocks.append(_pdf_block({"type": "image_placeholder", **placeholder}))
    return blocks


def _repair_jsonish(text: str) -> str:
    """Best-effort repair of the JSON mistakes LLMs make when stringifying args.

    Single left-to-right pass that tracks whether we are inside a string literal:

    * Unescaped ``"`` inside a value — the dominant failure mode. Source text
      lifted from a PDF often contains content quotes (e.g. 信息"大爆炸"时代);
      when the model hand-builds the ``document`` JSON it forgets to escape them,
      so strict ``json.loads`` aborts at the first one. A ``"`` is treated as the
      string terminator only when the next significant char is structural
      (``:`` ``,`` ``}`` ``]`` or end-of-input); otherwise it is content and gets
      escaped to ``\\"``.
    * Trailing commas before ``}`` / ``]`` are dropped.

    Escape sequences are passed through verbatim so already-valid input is left
    unchanged. This is a heuristic, not a parser: the caller still runs
    ``json.loads`` on the result and falls back to the raw string if it fails.
    """
    out: List[str] = []
    i = 0
    n = len(text)
    in_str = False
    while i < n:
        c = text[i]
        if not in_str:
            if c == ",":
                j = i + 1
                while j < n and text[j] in " \t\r\n":
                    j += 1
                if j < n and text[j] in "}]":
                    i += 1  # drop trailing comma
                    continue
            out.append(c)
            if c == '"':
                in_str = True
            i += 1
            continue
        if c == "\\":
            out.append(text[i:i + 2])
            i += 2
            continue
        if c == '"':
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            nxt = text[j] if j < n else ""
            if nxt in (":", ",", "}", "]", ""):
                out.append('"')
                in_str = False
            else:
                out.append('\\"')
            i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _coerce_json_container(value: Any) -> Any:
    """Decode a JSON-string into the dict/list it encodes; pass anything else through.

    LLM tool-calls routinely stringify nested object/array arguments, so the
    ``document`` (or its ``blocks`` / ``sections``) can arrive as a JSON string
    even though the schema declares an object. Without this, ``_pdf_blocks``
    treated the whole JSON string as a single paragraph (dumping raw JSON onto
    the page) or fell through to an empty document. Genuine prose stays a string:
    only text that starts with ``[``/``{`` is treated as a container candidate.

    When strict parsing fails (commonly unescaped content quotes from PDF text),
    one repair pass via ``_repair_jsonish`` is attempted before giving up.
    """
    if isinstance(value, str):
        text = value.strip()
        if text[:1] in ("[", "{"):
            for candidate in (text, _repair_jsonish(text)):
                try:
                    parsed = json.loads(candidate)
                except (ValueError, TypeError):
                    continue
                if isinstance(parsed, (dict, list)):
                    return parsed
            raise DocumentSpecError(
                "document looks like JSON but could not be parsed. Pass document as a real "
                "object, or fix the malformed JSON string before calling the writer."
            )
    return value


def _document_spec_error(exc: DocumentSpecError) -> str:
    return tool_error(str(exc), ok=False, code="invalid_document_json")


def _pdf_blocks(document: Any) -> List[Dict[str, Any]]:
    document = _coerce_json_container(document)
    if isinstance(document, str):
        return [{"type": "paragraph", "text": document}]
    if isinstance(document, list):
        return [_pdf_block(item) for item in document]
    document = _dict(document)
    blocks_value = _coerce_json_container(document.get("blocks"))
    if isinstance(blocks_value, list):
        return [_pdf_block(item) for item in blocks_value]
    blocks: List[Dict[str, Any]] = []
    for section in _list(_coerce_json_container(document.get("sections"))):
        blocks.extend(_pdf_section_blocks(_dict(section)))
    if blocks:
        return blocks
    for key in ("summary", "abstract", "content", "body", "text"):
        value = document.get(key)
        if _text(value):
            blocks.append({"type": "paragraph", "text": _text(value)})
    return blocks or [{"type": "paragraph", "text": ""}]


def _build_pdf_spec(
    title: str,
    document: Any,
    template: str,
    visual_master: str,
) -> Dict[str, Any]:
    template_key = _normalize_pdf_template(template)
    return {
        "title": _text(title) or "Kabuqina PDF",
        "template": template_key,
        "template_name": _PDF_TEMPLATES[template_key]["title"],
        "template_subtitle": _PDF_TEMPLATES[template_key]["subtitle"],
        "visual_master": _text(visual_master) or "default_print",
        "page_size": "A4",
        "blocks": _pdf_blocks(document),
    }


def _block_to_html(block: Dict[str, Any]) -> str:
    block_type = block.get("type")
    if block_type == "heading":
        level = max(1, min(4, int(block.get("level") or 2)))
        return f"<h{level}>{html.escape(_text(block.get('text')))}</h{level}>"
    if block_type == "bullets":
        items = "".join(f"<li>{html.escape(item)}</li>" for item in block.get("items") or [])
        return f"<ul>{items}</ul>"
    if block_type == "table":
        headers = "".join(f"<th>{html.escape(item)}</th>" for item in block.get("headers") or [])
        rows = []
        for row in block.get("rows") or []:
            rows.append("<tr>" + "".join(f"<td>{html.escape(item)}</td>" for item in row) + "</tr>")
        head = f"<thead><tr>{headers}</tr></thead>" if headers else ""
        return f"<table>{head}<tbody>{''.join(rows)}</tbody></table>"
    if block_type == "code":
        language = html.escape(_text(block.get("language")))
        label = f"<figcaption>{language}</figcaption>" if language else ""
        return f"<figure class=\"code\">{label}<pre>{html.escape(_text(block.get('text')))}</pre></figure>"
    if block_type == "formula":
        return f"<div class=\"formula\">{_formula_to_html(_text(block.get('text')))}</div>"
    if block_type == "image_placeholder":
        label = html.escape(_text(block.get("label")))
        caption = html.escape(_text(block.get("caption")))
        source_hint = html.escape(_text(block.get("source_hint")))
        return (
            "<figure class=\"image-placeholder\">"
            f"<div>{label}</div><figcaption>{caption}</figcaption><small>{source_hint}</small>"
            "</figure>"
        )
    if block_type == "page_break":
        return "<div class=\"page-break\"></div>"
    return f"<p>{html.escape(_text(block.get('text')))}</p>"


def _build_pdf_html(spec: Dict[str, Any]) -> str:
    accent = _PDF_TEMPLATES.get(spec["template"], _PDF_TEMPLATES["academic_report"])["accent"]
    accent_css = f"rgb({accent[0]}, {accent[1]}, {accent[2]})"
    body = "\n".join(_block_to_html(block) for block in spec.get("blocks") or [])
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{html.escape(_text(spec.get("title")))}</title>
  <style>
    @page {{ size: A4; margin: 18mm; }}
    body {{ color: #111827; font-family: "Microsoft YaHei", "Noto Sans CJK SC", Arial, sans-serif; line-height: 1.55; }}
    h1 {{ color: {accent_css}; font-size: 26px; margin: 0 0 6px; }}
    .subtitle {{ color: #64748b; margin: 0 0 22px; }}
    h2, h3, h4 {{ color: #111827; margin: 22px 0 8px; }}
    p {{ margin: 8px 0; }}
    ul {{ margin: 8px 0 12px 22px; }}
    table {{ border-collapse: collapse; margin: 12px 0; width: 100%; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 7px 9px; text-align: left; vertical-align: top; }}
    th {{ background: #f1f5f9; }}
    pre {{ background: #0f172a; color: #e2e8f0; border-radius: 6px; padding: 12px; white-space: pre-wrap; }}
    figure {{ margin: 12px 0; }}
    .formula {{ background: #f8fafc; border-left: 4px solid {accent_css}; padding: 10px 12px; font-family: Cambria Math, serif; }}
    .formula-math {{ font-size: 1.05em; word-spacing: 0.08em; }}
    .frac {{ display: inline-flex; flex-direction: column; align-items: center; vertical-align: middle; line-height: 1.05; margin: 0 0.12em; }}
    .frac .num {{ border-bottom: 1px solid currentColor; padding: 0 0.18em 1px; }}
    .frac .den {{ padding: 1px 0.18em 0; }}
    .sqrt::before {{ content: "√"; font-size: 1.12em; }}
    .sqrt .radicand {{ border-top: 1px solid currentColor; padding: 0 0.12em; }}
    .overline {{ text-decoration: overline; text-decoration-thickness: 1px; }}
    .vec-mark {{ display: inline-block; margin-left: -0.1em; transform: translateY(-0.18em); }}
    .image-placeholder {{ border: 1px dashed #94a3b8; border-radius: 6px; padding: 18px; color: #475569; }}
    .page-break {{ break-after: page; page-break-after: always; }}
  </style>
</head>
<body>
  <h1>{html.escape(_text(spec.get("title")))}</h1>
  <p class="subtitle">{html.escape(_text(spec.get("template_name")))} · {html.escape(_text(spec.get("template_subtitle")))}</p>
  {body}
</body>
</html>
"""


def _build_standalone_html(spec: Dict[str, Any]) -> str:
    """Screen-first standalone HTML deliverable.

    Reuses the same normalized blocks and per-block rendering as the PDF sidecar
    (``_block_to_html``), but wraps them in a responsive, centered container with
    both screen and print styling so the .html is a first-class output, not just
    a print source.
    """
    accent = _PDF_TEMPLATES.get(spec["template"], _PDF_TEMPLATES["academic_report"])["accent"]
    accent_css = f"rgb({accent[0]}, {accent[1]}, {accent[2]})"
    body = "\n".join(_block_to_html(block) for block in spec.get("blocks") or [])
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(_text(spec.get("title")))}</title>
  <style>
    :root {{ --accent: {accent_css}; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #f1f5f9; color: #111827;
      font-family: "Microsoft YaHei", "Noto Sans CJK SC", Arial, sans-serif; line-height: 1.6; }}
    main.container {{ max-width: 820px; margin: 0 auto; padding: 40px 28px 64px;
      background: #ffffff; min-height: 100vh; box-shadow: 0 1px 24px rgba(15, 23, 42, 0.08); }}
    h1 {{ color: var(--accent); font-size: 28px; margin: 0 0 6px; }}
    .subtitle {{ color: #64748b; margin: 0 0 26px; border-bottom: 1px solid #e2e8f0; padding-bottom: 16px; }}
    h2, h3, h4 {{ color: #0f172a; margin: 26px 0 8px; }}
    p {{ margin: 10px 0; }}
    ul {{ margin: 10px 0 14px 22px; }}
    table {{ border-collapse: collapse; margin: 14px 0; width: 100%; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 8px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #f1f5f9; }}
    figure {{ margin: 14px 0; }}
    figure.code figcaption {{ color: #64748b; font-size: 13px; margin-bottom: 4px; }}
    pre {{ background: #0f172a; color: #e2e8f0; border-radius: 8px; padding: 14px; overflow-x: auto; white-space: pre-wrap; }}
    .formula {{ background: #f8fafc; border-left: 4px solid var(--accent); padding: 12px 14px; font-family: Cambria Math, serif; }}
    .formula-math {{ font-size: 1.05em; word-spacing: 0.08em; }}
    .frac {{ display: inline-flex; flex-direction: column; align-items: center; vertical-align: middle; line-height: 1.05; margin: 0 0.12em; }}
    .frac .num {{ border-bottom: 1px solid currentColor; padding: 0 0.18em 1px; }}
    .frac .den {{ padding: 1px 0.18em 0; }}
    .sqrt::before {{ content: "√"; font-size: 1.12em; }}
    .sqrt .radicand {{ border-top: 1px solid currentColor; padding: 0 0.12em; }}
    .overline {{ text-decoration: overline; text-decoration-thickness: 1px; }}
    .vec-mark {{ display: inline-block; margin-left: -0.1em; transform: translateY(-0.18em); }}
    .image-placeholder {{ border: 1px dashed #94a3b8; border-radius: 8px; padding: 20px; color: #475569; text-align: center; }}
    .page-break {{ break-after: page; page-break-after: always; }}
    @media (max-width: 640px) {{ main.container {{ padding: 24px 16px 48px; }} }}
    @media print {{ body {{ background: #fff; }} main.container {{ box-shadow: none; max-width: none; }} }}
  </style>
</head>
<body>
  <main class="container">
    <h1>{html.escape(_text(spec.get("title")))}</h1>
    <p class="subtitle">{html.escape(_text(spec.get("template_name")))} · {html.escape(_text(spec.get("template_subtitle")))}</p>
    {body}
  </main>
</body>
</html>
"""
