# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""PPTX deck writer, split from document_tools.py."""

from __future__ import annotations

import base64
import html
import io
import json
import logging
import os
import re
import textwrap
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tools.registry import registry, tool_error
from tools.document.common import (
    DocumentSpecError, Rgb, _PDF_BLOCK_TYPES, _PDF_TEMPLATES,
    _PPTX_SLIDE_LAYOUTS, _PPTX_SLIDE_TYPES, _desktop_workspace_root,
    _is_outside_workspace, _json, _power_user_reads_anywhere,
    _validate_read_path, _validate_write_path,
    _text, _list, _string_list, _dict,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _PptxTheme:
    key: str
    subtitle: str
    badge: str
    bg: Rgb
    title: Rgb
    subtitle_color: Rgb
    body: Rgb
    accent: Rgb
    accent_light: Rgb
    title_band: Optional[Rgb] = None
    footer_band: Optional[Rgb] = None


_PPTX_THEMES: Dict[str, _PptxTheme] = {
    "course_report": _PptxTheme(
        key="course_report",
        subtitle="课程汇报",
        badge="课程报告",
        bg=(239, 246, 255),
        title=(30, 64, 175),
        subtitle_color=(37, 99, 235),
        body=(51, 65, 85),
        accent=(37, 99, 235),
        accent_light=(147, 197, 253),
        title_band=(37, 99, 235),
    ),
    "paper_report": _PptxTheme(
        key="paper_report",
        subtitle="论文 / 文献汇报",
        badge="论文报告",
        bg=(255, 251, 235),
        title=(20, 83, 45),
        subtitle_color=(22, 101, 52),
        body=(68, 64, 60),
        accent=(22, 101, 52),
        accent_light=(134, 239, 172),
    ),
    "code_defense": _PptxTheme(
        key="code_defense",
        subtitle="课程设计答辩",
        badge="项目答辩",
        bg=(241, 245, 249),
        title=(49, 46, 129),
        subtitle_color=(234, 88, 12),
        body=(71, 85, 105),
        accent=(99, 102, 241),
        accent_light=(249, 115, 22),
        footer_band=(30, 41, 59),
    ),
}


_PPTX_VISUAL_MASTERS: Dict[str, Dict[str, str]] = {
    "default_native": {"name": "Default native renderer", "dir": ""},
    "soft_editorial": {"name": "Soft Editorial", "dir": "soft-editorial"},
    "blue_professional": {"name": "Blue Professional", "dir": "blue-professional"},
    "signal": {"name": "Signal", "dir": "signal"},
    "neo_grid_bold": {"name": "Neo Grid Bold", "dir": "neo-grid-bold"},
    "editorial_forest": {"name": "Editorial Forest", "dir": "editorial-forest"},
}


def _normalize_pptx_template(template: str) -> str:
    key = (template or "course_report").strip().lower()
    return key if key in _PPTX_THEMES else "course_report"


def _normalize_pptx_visual_master(visual_master: str) -> str:
    key = (visual_master or "default_native").strip().lower().replace("-", "_")
    return key if key in _PPTX_VISUAL_MASTERS else "default_native"


def _pptx_visual_master_name(visual_master: str) -> str:
    return _PPTX_VISUAL_MASTERS[visual_master]["name"]


def _get_pptx_theme(template: str) -> _PptxTheme:
    return _PPTX_THEMES[_normalize_pptx_template(template)]


def _normalize_slide_type(raw: Any) -> str:
    key = str(raw or "claim_bullets").strip().lower()
    return key if key in _PPTX_SLIDE_TYPES else "claim_bullets"


def _deck_slide_spec(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize one planner slide into a renderer-friendly entry.

    The web layer (PptxGenJS) renders from this spec, so keep it structured and
    bounded — same field contract the old python-pptx renderer consumed.
    """
    raw = _dict(raw)
    slide_type = _normalize_slide_type(raw.get("slide_type"))
    entry: Dict[str, Any] = {
        "slide_type": slide_type,
        "title": _text(raw.get("title")),
        "subtitle": _text(raw.get("subtitle")),
        "bullets": _string_list(raw.get("bullets"), limit=8),
        "notes": _text(raw.get("notes")),
        "tags": _string_list(raw.get("tags"), limit=6),
    }
    # Optional per-slide layout hint; the web renderer auto-selects by content
    # when this is absent or unknown (see renderDeck.ts:chooseLayout).
    layout = _text(raw.get("layout"))
    if layout in _PPTX_SLIDE_LAYOUTS:
        entry["layout"] = layout
    diagram = _dict(raw.get("diagram"))
    if diagram:
        entry["diagram"] = {
            "nodes": _string_list(diagram.get("nodes") or diagram.get("steps"), limit=8),
        }
    table = _dict(raw.get("table"))
    if table:
        headers = _string_list(table.get("headers"), limit=6)
        entry["table"] = {
            "headers": headers,
            "rows": [
                _string_list(row, limit=len(headers) or 6)
                for row in _list(table.get("rows"))[:8]
            ],
        }
    placeholder = _dict(raw.get("placeholder"))
    if placeholder:
        entry["placeholder"] = {
            "label": _text(placeholder.get("label")),
            "caption": _text(placeholder.get("caption")),
            "source_hint": _text(placeholder.get("source_hint")),
        }
    # Track D design intent (model-provided): structured metrics for stat layouts
    # and a single spotlight emphasis. Bounded + sanitized like the blocks above.
    metrics = [
        {"value": _text(_dict(m).get("value")), "label": _text(_dict(m).get("label"))}
        for m in _list(raw.get("metrics"))[:4]
        if _text(_dict(m).get("value"))
    ]
    if metrics:
        entry["metrics"] = metrics
    emphasis = _dict(raw.get("emphasis"))
    kind = _text(emphasis.get("kind"))
    if kind in ("stat", "quote"):
        entry["emphasis"] = {
            "kind": kind,
            "value": _text(emphasis.get("value")),
            "label": _text(emphasis.get("label")),
        }
    return entry


def _slide_has_body(slide: Dict[str, Any]) -> bool:
    """A slide carries content if it has bullets, a table, a diagram, or a placeholder."""
    return bool(
        slide.get("bullets")
        or slide.get("table")
        or slide.get("diagram")
        or slide.get("placeholder")
    )


def _normalize_deck_slides(slides: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deterministic structural cleanup applied after per-slide normalization.

    Model-independent guardrails that guarantee a sound deck skeleton regardless
    of planner quality. We only *remove* clearly-broken structure — never rewrite
    or invent content, which stays the planner/model's job. This is the hard
    backstop paired with the soft guidance in
    ``prompt_builder.build_deliverable_planner_prompt`` ("Slide content quality"):
    the prompt aims the model high, this catches the misses for free.

    Three high-confidence rules, each only ever a deletion:

    1. Drop structurally-empty slides (no title and no body of any kind).
    2. Exactly one agenda — keep the richest (most bullets; ties → earliest) and
       drop the rest. Two agenda slides is never intended.
    3. Drop exact-duplicate *content* slides (same type + title + bullets),
       keeping the first. Placeholder slides are never deduped, since a repeated
       "insert screenshot here" cue can be legitimate in a defense deck.
    """
    cleaned = [s for s in slides if s.get("title") or _slide_has_body(s)]

    agenda_idx = [i for i, s in enumerate(cleaned) if s.get("slide_type") == "agenda"]
    if len(agenda_idx) > 1:
        keep = max(agenda_idx, key=lambda i: (len(cleaned[i].get("bullets") or []), -i))
        cleaned = [
            s for i, s in enumerate(cleaned)
            if s.get("slide_type") != "agenda" or i == keep
        ]

    seen: set = set()
    deduped: List[Dict[str, Any]] = []
    for s in cleaned:
        signature = (s.get("slide_type"), s.get("title"), tuple(s.get("bullets") or []))
        if s.get("bullets") and signature in seen:
            continue
        seen.add(signature)
        deduped.append(s)
    return deduped


def _deck_meta(raw: Any) -> Dict[str, str]:
    """Deck-level presentation metadata that belongs on the cover, not in slides.

    Giving author / affiliation / date / citation a structural home removes the
    reason a planner would otherwise cram author info into an agenda bullet.
    """
    raw = _dict(raw)
    meta: Dict[str, str] = {}
    for key in ("author", "affiliation", "date", "citation"):
        value = _text(raw.get(key))
        if value:
            meta[key] = value
    return meta


def _hex6(value: str) -> str:
    """Normalize a DrawingML colour to a 6-hex string, or '' if not parseable."""
    v = (value or "").strip().lstrip("#").upper()
    if len(v) == 6 and all(c in "0123456789ABCDEF" for c in v):
        return v
    return ""


def _theme_color(scheme_el: Any, tag: str, ns: Dict[str, str]) -> str:
    """Read one <a:clrScheme> entry (srgbClr val=... or sysClr lastClr=...)."""
    node = scheme_el.find(f"a:{tag}", ns)
    if node is None:
        return ""
    srgb = node.find("a:srgbClr", ns)
    if srgb is not None:
        return _hex6(srgb.get("val", ""))
    sysclr = node.find("a:sysClr", ns)
    if sysclr is not None:
        return _hex6(sysclr.get("lastClr", ""))
    return ""


def _extract_pptx_theme(template_path: Path) -> Optional[Dict[str, Any]]:
    """Derive an inline visual master (palette + fonts) from an uploaded .pptx.

    Route A of template support: rather than rendering *into* the school template
    (which PptxGenJS cannot do), we read its DrawingML theme and reuse its colours
    and fonts so the generated deck matches the school's look while keeping our
    own rich layouts. Pure stdlib (zip + XML), deterministic, no dependency on the
    python-pptx writer. Returns ``None`` if the theme cannot be parsed, so the
    caller falls back to the selected built-in master.
    """
    import xml.etree.ElementTree as ET
    import zipfile

    ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    try:
        with zipfile.ZipFile(template_path) as zf:
            with zf.open("ppt/theme/theme1.xml") as fh:
                root = ET.parse(fh).getroot()
    except (KeyError, OSError, zipfile.BadZipFile, ET.ParseError):
        return None

    elements = root.find("a:themeElements", ns)
    if elements is None:
        return None
    scheme = elements.find("a:clrScheme", ns)
    fonts_el = elements.find("a:fontScheme", ns)
    if scheme is None:
        return None

    # lt1/dk1 are usually window bg/text; dk2/accent1 carry the brand identity.
    background = _theme_color(scheme, "lt1", ns) or _theme_color(scheme, "lt2", ns)
    title = _theme_color(scheme, "dk2", ns) or _theme_color(scheme, "dk1", ns)
    body = _theme_color(scheme, "dk1", ns) or title
    accent = _theme_color(scheme, "accent1", ns)
    accent2 = _theme_color(scheme, "accent2", ns) or accent

    palette: Dict[str, Any] = {}
    if background:
        palette["background"] = background
    if title:
        palette["title"] = title
    if body and body != background:
        palette["body"] = body
    if accent:
        palette["accent"] = accent
    if accent2:
        palette["accent2"] = accent2

    if fonts_el is not None:
        def _typeface(role: str) -> str:
            font = fonts_el.find(f"a:{role}", ns)
            latin = font.find("a:latin", ns) if font is not None else None
            face = (latin.get("typeface", "") if latin is not None else "").strip()
            # "+mj-lt"/"+mn-lt" are theme self-references, not real font names.
            return face if face and not face.startswith("+") else ""
        major = _typeface("majorFont")
        minor = _typeface("minorFont")
        if major or minor:
            palette["fonts"] = {"major": major or minor, "minor": minor or major}

    # Require at least an accent or a usable background to consider it a theme.
    if not (palette.get("accent") or palette.get("background")):
        return None
    return palette


def _build_deck_spec(
    title: str,
    slides: List[Dict[str, Any]],
    theme: "_PptxTheme",
    visual_master: str,
    meta: Any = None,
    theme_override: Optional[Dict[str, Any]] = None,
    template_name: str = "",
) -> Dict[str, Any]:
    normalized = _normalize_deck_slides([_deck_slide_spec(raw) for raw in (slides or [])])
    spec: Dict[str, Any] = {
        "title": _text(title) or "学生汇报",
        "template": theme.key,
        "template_subtitle": theme.subtitle,
        "template_badge": theme.badge,
        "visual_master": visual_master,
        "visual_master_name": _pptx_visual_master_name(visual_master),
        "page_size": {"width": 13.333, "height": 7.5},
        "meta": _deck_meta(meta),
        "slides": normalized,
    }
    if theme_override:
        spec["visual_master_palette"] = theme_override
        if template_name:
            spec["visual_master_name"] = template_name
    return spec


def pptx_write(
    path: str,
    title: str,
    slides: List[Dict[str, Any]],
    template: str = "course_report",
    visual_master: str = "default_native",
    meta: Optional[Dict[str, Any]] = None,
    template_path: str = "",
    callback=None,
) -> str:
    """Render a student deck with PptxGenJS in the desktop web layer.

    The agent loop (run_agent._invoke_tool) routes this tool with
    ``callback=self.clarify_callback``. We emit the deck spec as a
    ``kind="pptx_render"`` interaction; the webview builds the .pptx with
    PptxGenJS and returns it base64-encoded in the interaction ``data``, which
    we decode and write to the (workspace-validated) output path. There is no
    python-pptx writer anymore — Python only persists the bytes.
    """
    logger.info(
        "pptx_write called: callback_present=%s slides=%d template=%s visual_master=%s",
        callback is not None,
        len(slides or []),
        template,
        visual_master,
    )
    theme = _get_pptx_theme(template)
    selected_visual_master = _normalize_pptx_visual_master(visual_master)
    out = Path(path).expanduser()
    if out.suffix.lower() != ".pptx":
        out = out.with_suffix(".pptx")

    # Route A: an uploaded school template contributes its colours/fonts as an
    # inline visual master. Bad/unreadable templates degrade silently to the
    # selected built-in master rather than failing the whole deck.
    theme_override: Optional[Dict[str, Any]] = None
    template_name = ""
    if _text(template_path):
        tpl = Path(template_path).expanduser()
        read_error = _validate_read_path(tpl, template_path, "PPT template")
        if read_error is not None:
            return read_error
        theme_override = _extract_pptx_theme(tpl)
        if theme_override is not None:
            template_name = tpl.stem
            logger.info("pptx_write: applied uploaded template theme from %s", tpl.name)
        else:
            logger.warning("pptx_write: could not parse theme from %s; using built-in master", tpl.name)

    deck_spec = _build_deck_spec(
        title, slides, theme, selected_visual_master, meta, theme_override, template_name
    )

    if callback is None:
        return tool_error(
            "PptxGenJS rendering requires the Kabuqina desktop UI; no interactive "
            "renderer is available in this context.",
            code="pptx_render_unavailable",
        )

    artifact = {"type": "pptx_deck", "filename": out.name, "deck": deck_spec}
    question = f"生成 PPT：{deck_spec['title']}（{len(deck_spec['slides'])} 页内容）"
    try:
        response = callback(question, [], kind="pptx_render", artifact=artifact)
    except TypeError:
        return tool_error(
            "The active interaction callback does not support PptxGenJS rendering.",
            code="pptx_render_unsupported",
        )

    data: Dict[str, Any] = {}
    if isinstance(response, dict):
        action = str(response.get("action") or "")
        data = response.get("data") if isinstance(response.get("data"), dict) else {}
        if action in {"cancel", "timeout"}:
            return tool_error(
                f"PPT rendering was not completed (action={action}).",
                code="pptx_render_cancelled",
            )
        if action == "error":
            return tool_error(
                str(response.get("text") or "PptxGenJS rendering failed in the web layer."),
                code="pptx_render_failed",
            )

    b64 = str(data.get("pptx_base64") or "")
    if not b64:
        return tool_error(
            "The web renderer did not return a .pptx payload.",
            code="pptx_render_empty",
        )

    import base64

    try:
        raw_bytes = base64.b64decode(b64)
    except Exception as exc:
        return tool_error(f"Could not decode rendered .pptx: {exc}", code="pptx_render_decode_error")

    validation_error = _validate_write_path(out, path)
    if validation_error is not None:
        return validation_error
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(raw_bytes)

    slide_count = int(data.get("slide_count") or (len(deck_spec["slides"]) + 1))
    return _json(
        {
            "ok": True,
            "path": str(out),
            "slide_count": slide_count,
            "template": theme.key,
            "theme": theme.badge,
            "visual_master": selected_visual_master,
            "visual_master_name": _pptx_visual_master_name(selected_visual_master),
            "visual_master_renderer": "pptxgenjs_v1",
            "bytes": len(raw_bytes),
        }
    )
