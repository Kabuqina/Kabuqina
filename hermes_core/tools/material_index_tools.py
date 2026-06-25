"""Material Index builder for downstream document generation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tools.registry import registry, tool_error

_MAX_SECTIONS = 24
_MAX_KEY_POINTS = 36
_MAX_TABLES = 12
_MAX_TABLE_ROWS = 8
_MAX_FIGURES = 18
_MAX_CODE_FILES = 40
_MAX_EVIDENCE = 36
_MAX_CITATIONS = 24
_MAX_UNCERTAIN = 16
_SNIPPET_LIMIT = 320

_PROFILES = {"paper_report", "course_report", "code_defense", "sandtable_review", "auto"}
_CODE_SUFFIXES = {
    ".java",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".rs",
    ".go",
    ".cs",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".xml",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".gradle",
}


def _json(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


def _safe_text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return text or default


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _truncate(text: Any, limit: int = _SNIPPET_LIMIT) -> str:
    value = re.sub(r"\s+", " ", _safe_text(text)).strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def _make_id(prefix: str, index: int) -> str:
    return f"{prefix}_{index}"


def _normalize_profile(profile: Any) -> str:
    key = _safe_text(profile, "auto").lower()
    return key if key in _PROFILES else "auto"


def _material_kind(name: str, explicit: str) -> str:
    if explicit:
        return explicit.lower()
    suffix = Path(name).suffix.lower()
    if suffix in _CODE_SUFFIXES:
        return "code"
    if suffix:
        return suffix.lstrip(".")
    return "unknown"


def _normalize_materials(materials: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    source_files: List[Dict[str, Any]] = []
    normalized: List[Dict[str, Any]] = []
    for idx, raw in enumerate(_safe_list(materials), 1):
        if not isinstance(raw, dict):
            continue
        name = _safe_text(raw.get("name"), f"material-{idx}")
        metadata = dict(_safe_dict(raw.get("metadata")))
        content = _safe_text(raw.get("content"))
        read_id = _safe_text(raw.get("read_id") or metadata.get("read_id"))
        if not content and read_id:
            try:
                from tools.document_tools import _load_read_result

                cached = _load_read_result(read_id)
                content = _safe_text(cached.get("content"))
                if not name or name == f"material-{idx}":
                    name = _safe_text(Path(_safe_text(cached.get("path"))).name, name)
                cached_metadata = _safe_dict(cached.get("metadata"))
                metadata = {**cached_metadata, **metadata, "read_id": read_id}
            except Exception as exc:
                metadata = {**metadata, "read_id": read_id, "read_cache_error": str(exc)}
        source_id = _make_id("src", len(source_files) + 1)
        source = {
            "id": source_id,
            "name": name,
            "path": _safe_text(raw.get("path")),
            "mime": _safe_text(raw.get("mime")),
            "kind": _material_kind(name, _safe_text(raw.get("kind"))),
            "metadata": metadata,
        }
        source_files.append(source)
        normalized.append({
            "source": source,
            "content": content,
        })
    return source_files, normalized


def _paragraphs(content: str) -> List[str]:
    return [
        block.strip()
        for block in re.split(r"\n\s*\n", content)
        if block.strip() and not block.strip().startswith("|")
    ]


def _extract_sections(materials: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sections: List[Dict[str, Any]] = []
    for material in materials:
        source_id = material["source"]["id"]
        content = material["content"]
        lines = content.splitlines()
        heading_positions: List[Tuple[int, str]] = []
        for idx, line in enumerate(lines):
            match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            if match:
                heading_positions.append((idx, match.group(2).strip()))
        for pos, (line_idx, title) in enumerate(heading_positions):
            next_idx = heading_positions[pos + 1][0] if pos + 1 < len(heading_positions) else len(lines)
            body = "\n".join(lines[line_idx + 1:next_idx])
            snippet = ""
            for paragraph in _paragraphs(body):
                snippet = _truncate(paragraph)
                if snippet:
                    break
            sections.append({
                "id": _make_id("sec", len(sections) + 1),
                "source_id": source_id,
                "title": _truncate(title, 120),
                "text": snippet,
            })
            if len(sections) >= _MAX_SECTIONS:
                return sections
        if not heading_positions:
            for paragraph in _paragraphs(content)[:2]:
                sections.append({
                    "id": _make_id("sec", len(sections) + 1),
                    "source_id": source_id,
                    "title": _truncate(material["source"]["name"], 120),
                    "text": _truncate(paragraph),
                })
                if len(sections) >= _MAX_SECTIONS:
                    return sections
    return sections


def _extract_key_points(materials: List[Dict[str, Any]], sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    points: List[Dict[str, Any]] = []
    for section in sections:
        if section.get("text"):
            points.append({
                "id": _make_id("kp", len(points) + 1),
                "source_id": section["source_id"],
                "section_id": section["id"],
                "text": _truncate(section["text"]),
            })
            if len(points) >= _MAX_KEY_POINTS:
                return points

    bullet_re = re.compile(r"^\s*(?:[-*+]|\d+[.)]|[·•])\s+(.+?)\s*$")
    for material in materials:
        source_id = material["source"]["id"]
        for line in material["content"].splitlines():
            match = bullet_re.match(line)
            if not match:
                continue
            text = _truncate(match.group(1))
            if not text:
                continue
            points.append({
                "id": _make_id("kp", len(points) + 1),
                "source_id": source_id,
                "text": text,
            })
            if len(points) >= _MAX_KEY_POINTS:
                return points
    return points


def _is_separator_row(cells: List[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def _split_table_row(line: str) -> List[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _nearest_heading(lines: List[str], start: int, fallback: str) -> str:
    for idx in range(min(start, len(lines) - 1), -1, -1):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", lines[idx])
        if match:
            return match.group(2).strip()
    return fallback


def _extract_tables(materials: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    tables: List[Dict[str, Any]] = []
    for material in materials:
        source_id = material["source"]["id"]
        lines = material["content"].splitlines()
        idx = 0
        while idx < len(lines):
            line = lines[idx]
            if "|" not in line or idx + 1 >= len(lines):
                idx += 1
                continue
            headers = _split_table_row(line)
            separator = _split_table_row(lines[idx + 1])
            if not headers or not _is_separator_row(separator):
                idx += 1
                continue
            rows: List[List[str]] = []
            idx += 2
            while idx < len(lines) and "|" in lines[idx] and len(rows) < _MAX_TABLE_ROWS:
                row = _split_table_row(lines[idx])
                if row and not _is_separator_row(row):
                    rows.append(row[:len(headers)])
                idx += 1
            if rows:
                tables.append({
                    "id": _make_id("tbl", len(tables) + 1),
                    "source_id": source_id,
                    "title": _truncate(_nearest_heading(lines, idx, material["source"]["name"]), 120),
                    "headers": headers,
                    "rows": rows,
                })
                if len(tables) >= _MAX_TABLES:
                    return tables
            continue
    return tables


def _extract_visuals(materials: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    figures: List[Dict[str, Any]] = []
    screenshots: List[Dict[str, Any]] = []
    image_re = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    cue_re = re.compile(r"(图\s*\d+|Figure\s*\d+|截图|界面|dashboard|运行结果|系统架构)", re.IGNORECASE)
    screenshot_words = ("截图", "界面", "dashboard", "运行结果", "screenshot")
    for material in materials:
        source_id = material["source"]["id"]
        for match in image_re.finditer(material["content"]):
            alt = _safe_text(match.group(1), "图片")
            path = _safe_text(match.group(2))
            item = {
                "id": _make_id("shot" if any(word.lower() in alt.lower() for word in screenshot_words) else "fig",
                               len(screenshots if any(word.lower() in alt.lower() for word in screenshot_words) else figures) + 1),
                "source_id": source_id,
                "title": _truncate(alt, 120),
                "text": _truncate(alt),
                "path": path,
            }
            if any(word.lower() in alt.lower() or word.lower() in path.lower() for word in screenshot_words):
                screenshots.append(item)
            else:
                figures.append(item)

        for line in material["content"].splitlines():
            text = line.strip()
            if not text or image_re.search(text) or not cue_re.search(text):
                continue
            target = screenshots if any(word.lower() in text.lower() for word in screenshot_words) else figures
            prefix = "shot" if target is screenshots else "fig"
            target.append({
                "id": _make_id(prefix, len(target) + 1),
                "source_id": source_id,
                "title": _truncate(text, 120),
                "text": _truncate(text),
            })
            if len(figures) >= _MAX_FIGURES and len(screenshots) >= _MAX_FIGURES:
                return figures[:_MAX_FIGURES], screenshots[:_MAX_FIGURES]
    return figures[:_MAX_FIGURES], screenshots[:_MAX_FIGURES]


def _is_code_file(source: Dict[str, Any]) -> bool:
    name = source["name"]
    suffix = Path(name).suffix.lower()
    return source["kind"] == "code" or suffix in _CODE_SUFFIXES or "/" in name or "\\" in name


def _extract_code_files(materials: List[Dict[str, Any]], profile: str) -> List[Dict[str, Any]]:
    if profile != "code_defense":
        return []
    code_files: List[Dict[str, Any]] = []
    for material in materials:
        source = material["source"]
        if not _is_code_file(source):
            continue
        code_files.append({
            "id": _make_id("code", len(code_files) + 1),
            "source_id": source["id"],
            "name": source["name"],
            "kind": source["kind"],
            "text": _truncate(material["content"], 220),
        })
        if len(code_files) >= _MAX_CODE_FILES:
            break
    return code_files


def _extract_evidence(materials: List[Dict[str, Any]], tables, figures, screenshots, code_files) -> List[Dict[str, Any]]:
    evidence: List[Dict[str, Any]] = []
    for material in materials:
        name = material["source"]["name"]
        lower = name.lower()
        if lower in {"readme.md", "readme"} or "readme" in lower:
            evidence.append({
                "id": _make_id("ev", len(evidence) + 1),
                "source_id": material["source"]["id"],
                "title": "README 项目说明",
                "text": _truncate(material["content"]),
            })
    for kind, items in (("table", tables), ("figure", figures), ("screenshot", screenshots), ("code", code_files)):
        for item in items:
            evidence.append({
                "id": _make_id("ev", len(evidence) + 1),
                "source_id": item["source_id"],
                "title": _truncate(item.get("title") or item.get("name") or kind, 120),
                "text": _truncate(item.get("text") or item.get("name") or ""),
                "kind": kind,
            })
            if len(evidence) >= _MAX_EVIDENCE:
                return evidence
    return evidence


def _extract_citations(materials: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    citations: List[Dict[str, Any]] = []
    patterns = [
        re.compile(r"<!--\s*page:(\d+)\s*-->"),
        re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE),
        re.compile(r"^\s*\[(\d+)\]\s+(.+)$"),
        re.compile(r"^\s*(参考文献|References)\s*$", re.IGNORECASE),
    ]
    for material in materials:
        for line in material["content"].splitlines():
            for pattern in patterns:
                if pattern.search(line):
                    citations.append({
                        "id": _make_id("cite", len(citations) + 1),
                        "source_id": material["source"]["id"],
                        "text": _truncate(line, 180),
                    })
                    break
            if len(citations) >= _MAX_CITATIONS:
                return citations
    return citations


def _extract_uncertainty(materials: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    uncertain: List[Dict[str, Any]] = []
    pattern = re.compile(r"(识别不清|不确定|uncertain|ocr|fallback|无法识别|模糊)", re.IGNORECASE)
    for material in materials:
        for paragraph in _paragraphs(material["content"]):
            if not pattern.search(paragraph):
                continue
            uncertain.append({
                "id": _make_id("unc", len(uncertain) + 1),
                "source_id": material["source"]["id"],
                "text": _truncate(paragraph),
            })
            if len(uncertain) >= _MAX_UNCERTAIN:
                return uncertain
    return uncertain


def _generation_hints(profile: str, *, tables, figures, screenshots, code_files, uncertain_parts) -> Dict[str, Any]:
    missing_assets: List[Dict[str, Any]] = []
    quality_warnings: List[str] = []
    if uncertain_parts:
        quality_warnings.append("Some source material contains OCR/read uncertainty; verify before final delivery.")

    if profile == "code_defense":
        ppt_types = ["diagram", "screenshot_placeholder", "table", "qa_backup"]
        report_sections = ["项目背景", "系统架构", "关键实现", "测试结果", "问题与改进"]
        if not screenshots:
            missing_assets.append({
                "kind": "screenshot",
                "reason": "Code defense usually needs real running screenshots.",
            })
    elif profile == "course_report":
        ppt_types = ["diagram", "table", "claim_bullets", "qa_backup"]
        report_sections = ["知识结构", "关键概念", "案例应用", "学习总结"]
    elif profile == "sandtable_review":
        ppt_types = ["timeline", "table", "chart_placeholder", "claim_bullets", "qa_backup"]
        report_sections = ["沙盘背景与规则", "团队战略", "各周期决策", "经营结果", "复盘改进"]
        if not tables:
            missing_assets.append({
                "kind": "table_or_metrics",
                "reason": "Sandtable review is stronger with per-round financial tables/metrics (营收/利润/份额).",
            })
    else:
        ppt_types = ["diagram", "table", "chart_placeholder", "qa_backup"]
        report_sections = ["研究背景", "方法框架", "关键证据", "结果分析", "局限与展望"]
        if not figures and not tables:
            missing_assets.append({
                "kind": "figure_or_table",
                "reason": "Paper reports are stronger with figures, tables, or result evidence.",
            })

    return {
        "missing_assets": missing_assets,
        "quality_warnings": quality_warnings,
        "ppt": {"recommended_slide_types": ppt_types},
        "report": {"recommended_sections": report_sections},
    }


def material_index_build(profile: str = "auto", materials: Optional[List[Dict[str, Any]]] = None) -> str:
    if materials is None:
        materials = []
    if not isinstance(materials, list):
        return tool_error("materials must be an array of already-read material objects")

    normalized_profile = _normalize_profile(profile)
    source_files, normalized_materials = _normalize_materials(materials)
    sections = _extract_sections(normalized_materials)
    key_points = _extract_key_points(normalized_materials, sections)
    tables = _extract_tables(normalized_materials)
    figures, screenshots = _extract_visuals(normalized_materials)
    code_files = _extract_code_files(normalized_materials, normalized_profile)
    evidence = _extract_evidence(normalized_materials, tables, figures, screenshots, code_files)
    citations = _extract_citations(normalized_materials)
    uncertain_parts = _extract_uncertainty(normalized_materials)

    return _json({
        "ok": True,
        "version": 1,
        "profile": normalized_profile,
        "source_files": source_files,
        "sections": sections,
        "key_points": key_points,
        "tables": tables,
        "figures": figures,
        "screenshots": screenshots,
        "code_files": code_files,
        "evidence": evidence,
        "citations": citations,
        "uncertain_parts": uncertain_parts,
        "generation_hints": _generation_hints(
            normalized_profile,
            tables=tables,
            figures=figures,
            screenshots=screenshots,
            code_files=code_files,
            uncertain_parts=uncertain_parts,
        ),
    })


MATERIAL_INDEX_BUILD_SCHEMA = {
    "name": "material_index_build",
    "description": (
        "Build a format-agnostic Material Index from already-read student materials. "
        "Use after document_read_precise/pdf_read_precise/file reads and before planning generated files. "
        "Does not read paths, OCR files, or call an LLM."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "profile": {
                "type": "string",
                "description": "paper_report, course_report, code_defense, or auto",
            },
            "materials": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "path": {"type": "string"},
                        "mime": {"type": "string"},
                        "kind": {"type": "string"},
                        "content": {"type": "string"},
                        "read_id": {"type": "string", "description": "Optional Read-layer cache handle returned by document_read_precise/pdf_read_precise."},
                        "metadata": {"type": "object"},
                    },
                    "required": ["name"],
                },
            },
        },
        "required": ["materials"],
    },
}


registry.register(
    name="material_index_build",
    toolset="documents",
    schema=MATERIAL_INDEX_BUILD_SCHEMA,
    handler=lambda args, **kw: material_index_build(
        profile=args.get("profile", "auto"),
        materials=args.get("materials") or [],
    ),
    check_fn=lambda: True,
    emoji="🗂️",
)
