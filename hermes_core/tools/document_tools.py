"""Document read/write tools for student deliverables."""

from __future__ import annotations

import json
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

from tools.registry import registry, tool_error

Rgb = Tuple[int, int, int]

_DOCLING_CONVERTERS: Dict[str, Any] = {}
_DOCLING_CONVERTER_LOCK = threading.Lock()
_DOCLING_IO_POOL: Optional["ThreadPoolExecutor"] = None
_DOCLING_IO_POOL_LOCK = threading.Lock()
_TORCH_PRIME_LOCK = threading.Lock()


def _get_docling_io_pool() -> "ThreadPoolExecutor":
    """Single-worker pool: all Docling/torch init and convert on one thread."""
    global _DOCLING_IO_POOL
    with _DOCLING_IO_POOL_LOCK:
        if _DOCLING_IO_POOL is None:
            from concurrent.futures import ThreadPoolExecutor

            _DOCLING_IO_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="docling-io")
        return _DOCLING_IO_POOL


def _run_on_docling_thread(fn, /, *args, **kwargs):
    return _get_docling_io_pool().submit(lambda: fn(*args, **kwargs)).result()

_DOCLING_SUFFIXES = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".html",
    ".htm",
    ".md",
    ".markdown",
    ".adoc",
    ".asciidoc",
    ".csv",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".bmp",
    ".webp",
    ".xml",
    ".wav",
    ".mp3",
    ".vtt",
}

_FALLBACK_SUFFIXES = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".html",
    ".htm",
    ".md",
    ".markdown",
    ".csv",
    ".txt",
}

_PPTX_SLIDE_TYPES = {
    "agenda",
    "claim_bullets",
    "diagram",
    "table",
    "chart_placeholder",
    "screenshot_placeholder",
    "qa_backup",
    "closing",
}

# Optional per-slide layout hints the planner may set; the web renderer
# (renderDeck.ts) auto-selects by content when omitted. Keep in sync with
# SLIDE_LAYOUT_IDS in web/src/chat/pptx/renderDeck.ts.
_PPTX_SLIDE_LAYOUTS = {
    "hero_statement",
    "standard_bullets",
    "two_column_bullets",
    "comparison_cards",
    "process_flow_horizontal",
    "process_flow_vertical",
    "data_table",
    "media_placeholder",
    "section_divider",
}

_PDF_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "academic_report": {
        "title": "Academic report",
        "accent": (37, 99, 235),
        "subtitle": "print-friendly student report",
    },
    "code_report": {
        "title": "Code report",
        "accent": (79, 70, 229),
        "subtitle": "technical report with code and tables",
    },
    "math_report": {
        "title": "Math report",
        "accent": (22, 101, 52),
        "subtitle": "formula-oriented report",
    },
    "brief": {
        "title": "Brief",
        "accent": (71, 85, 105),
        "subtitle": "compact document",
    },
}

_PDF_BLOCK_TYPES = {
    "heading",
    "paragraph",
    "bullets",
    "table",
    "code",
    "formula",
    "image_placeholder",
    "page_break",
}

_LIGHTWEIGHT_FIRST_SUFFIXES = {
    ".docx",
    ".pptx",
    ".xlsx",
    ".html",
    ".htm",
    ".md",
    ".markdown",
    ".csv",
    ".txt",
}

_KIND_BY_SUFFIX = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".pptx": "pptx",
    ".xlsx": "xlsx",
    ".html": "html",
    ".htm": "html",
    ".md": "markdown",
    ".markdown": "markdown",
    ".csv": "csv",
    ".txt": "text",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".tif": "image",
    ".tiff": "image",
    ".bmp": "image",
    ".webp": "image",
}


def _json(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


def _error_payload(message: str, **extra) -> Dict[str, Any]:
    return json.loads(tool_error(message, **extra))


def _document_kind(path: Path) -> str:
    return _KIND_BY_SUFFIX.get(path.suffix.lower(), path.suffix.lower().lstrip(".") or "unknown")


def _read_cache_root() -> Path:
    raw = (
        os.environ.get("HERMESDESK_DATA_DIR")
        or os.environ.get("HERMES_HOME")
        or os.environ.get("LOCALAPPDATA")
        or tempfile.gettempdir()
    )
    root = Path(raw).expanduser()
    if root.name != "read-cache":
        root = root / "read-cache"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _read_id_for_payload(payload: Dict[str, Any]) -> str:
    content = str(payload.get("content") or "")
    path = str(payload.get("path") or "")
    engine = str(payload.get("engine") or "")
    digest = hashlib.sha256()
    digest.update(path.encode("utf-8", errors="replace"))
    digest.update(b"\0")
    digest.update(engine.encode("utf-8", errors="replace"))
    digest.update(b"\0")
    digest.update(content.encode("utf-8", errors="replace"))
    return digest.hexdigest()[:24]


def _persist_read_result(payload: Dict[str, Any]) -> Tuple[str, str]:
    """Persist a Read-layer payload so downstream tools can consume it by reference."""
    read_id = str(payload.get("read_id") or _read_id_for_payload(payload))
    cache_path = _read_cache_root() / f"{read_id}.json"
    stored = dict(payload)
    stored["read_id"] = read_id
    stored["cache_path"] = str(cache_path)
    cache_path.write_text(_json(stored), encoding="utf-8")
    return read_id, str(cache_path)


def _load_read_result(read_id: str) -> Dict[str, Any]:
    safe_id = "".join(ch for ch in str(read_id or "") if ch.isalnum() or ch in {"-", "_"})
    if not safe_id or safe_id != str(read_id):
        raise ValueError("invalid read_id")
    cache_path = _read_cache_root() / f"{safe_id}.json"
    if not cache_path.exists():
        raise FileNotFoundError(f"read cache entry not found: {safe_id}")
    return json.loads(cache_path.read_text(encoding="utf-8"))


def _with_read_metadata(payload: Dict[str, Any], document_path: Path) -> Dict[str, Any]:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    suffix = document_path.suffix.lower()
    enriched = {
        **payload,
        "path": str(document_path),
        "metadata": {
            **metadata,
            "kind": metadata.get("kind") or _document_kind(document_path),
            "suffix": suffix,
            "source_name": document_path.name,
            "parser_engine": payload.get("engine", ""),
        },
    }
    return enriched


def _finalize_read_payload(payload: Dict[str, Any], document_path: Path, *, include_content: bool) -> Dict[str, Any]:
    enriched = _with_read_metadata(payload, document_path)
    content = str(enriched.get("content") or "")
    read_id, cache_path = _persist_read_result(enriched)
    content_value = enriched.pop("content", "")
    enriched["read_id"] = read_id
    enriched["cache_path"] = cache_path
    enriched["content_chars"] = len(content)
    enriched["metadata"]["read_id"] = read_id
    enriched["content_hint"] = (
        "Full extracted content is stored in read-cache. Use read_file on cache_path "
        "with offset/limit to inspect the cached JSON content, or pass read_id to "
        "material_index_build. For extracting formulas from PDFs, use pdf_read_precise "
        "or document_read_precise with mode=math and read the extracted Markdown; do "
        "not use vision_analyze unless the PDF reader failed or the user explicitly "
        "asked for visual image description."
    )
    if not include_content:
        enriched["content"] = ""
        enriched["content_omitted"] = True
    else:
        enriched["content"] = content_value
    return enriched


def _resolve_docling_artifacts_path(profile: str = "fast") -> Optional[Path]:
    """Return bundled/offline Docling model dir when present."""
    try:
        from docling_math_models import resolve_docling_artifacts_path

        resolved = resolve_docling_artifacts_path(profile=profile)
        if resolved is not None:
            return resolved
        if profile == "math":
            return None
    except ImportError:
        pass

    explicit = os.environ.get("DOCLING_ARTIFACTS_PATH", "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        if path.is_dir():
            return path

    bundle_dir = os.environ.get("HERMESDESK_BUNDLE_DIR", "").strip()
    if bundle_dir:
        path = Path(bundle_dir) / "docling-models"
        if path.is_dir():
            return path
    return None


def _code_formula_bundle_present(artifacts_path: Optional[Path]) -> bool:
    if artifacts_path is None:
        return False
    formula_dir = artifacts_path / "ds4sd--CodeFormula"
    if not formula_dir.is_dir():
        return False
    return any(formula_dir.rglob("*.safetensors")) or any(formula_dir.rglob("*.bin"))


def _require_math_artifacts_bundled() -> None:
    """Non-desktop fallback when docling_math_models is unavailable."""
    artifacts_path = _resolve_docling_artifacts_path("fast")
    if not _code_formula_bundle_present(artifacts_path):
        target = (
            str(artifacts_path / "ds4sd--CodeFormula")
            if artifacts_path is not None
            else "<bundle>/docling-models/ds4sd--CodeFormula"
        )
        raise ValueError(
            "mode=math requires offline CodeFormula weights at "
            f"{target}. Re-run .\\python\\build_bundle.ps1 to bundle ds4sd/CodeFormula, "
            "or set DOCLING_ARTIFACTS_PATH to a directory that contains ds4sd--CodeFormula/."
        )


def _ensure_math_artifacts() -> None:
    """Ensure CodeFormula weights exist; fail with settings hint when missing."""
    try:
        from docling_math_models import ensure_code_formula_available_for_math

        ensure_code_formula_available_for_math()
        return
    except ImportError:
        pass
    _require_math_artifacts_bundled()


def _docling_profile_for_mode(mode: str) -> str:
    key = (mode or "").strip().lower()
    if key in {"precise", "math"}:
        return key
    return "fast"


def _prime_torch_for_docling() -> None:
    with _TORCH_PRIME_LOCK:
        import torch
        import torch.library  # noqa: F401
        if not hasattr(torch, "library"):
            raise AttributeError("torch imported without torch.library")


def _configure_pdf_pipeline_options(pipeline_options: Any, profile: str) -> None:
    if profile == "fast":
        pipeline_options.do_ocr = False
        pipeline_options.do_table_structure = False
        if hasattr(pipeline_options, "force_backend_text"):
            pipeline_options.force_backend_text = True
        if hasattr(pipeline_options, "do_formula_enrichment"):
            pipeline_options.do_formula_enrichment = False
        if hasattr(pipeline_options, "do_code_enrichment"):
            pipeline_options.do_code_enrichment = False
        return

    if profile == "precise":
        if hasattr(pipeline_options, "do_formula_enrichment"):
            pipeline_options.do_formula_enrichment = False
        if hasattr(pipeline_options, "do_code_enrichment"):
            pipeline_options.do_code_enrichment = False
        return

    if profile == "math":
        if not hasattr(pipeline_options, "do_formula_enrichment"):
            raise ValueError("Docling PdfPipelineOptions does not support formula enrichment")
        pipeline_options.do_formula_enrichment = True
        if hasattr(pipeline_options, "do_code_enrichment"):
            pipeline_options.do_code_enrichment = False
        if hasattr(pipeline_options, "code_formula_options"):
            pipeline_options.code_formula_options.extract_formulas = True
            pipeline_options.code_formula_options.extract_code = False
        return

    raise ValueError(f"unknown Docling profile: {profile}")


def _create_docling_converter(profile: str = "fast"):
    if profile == "math":
        _ensure_math_artifacts()
    _prime_torch_for_docling()

    from docling.datamodel.base_models import InputFormat  # type: ignore
    from docling.datamodel.pipeline_options import PdfPipelineOptions  # type: ignore
    from docling.document_converter import DocumentConverter, PdfFormatOption  # type: ignore

    pipeline_options = PdfPipelineOptions()
    artifacts_path = _resolve_docling_artifacts_path(profile)
    if artifacts_path is not None:
        pipeline_options.artifacts_path = artifacts_path
        easyocr_dir = artifacts_path / "EasyOcr"
        if easyocr_dir.is_dir() and hasattr(pipeline_options, "ocr_options"):
            pipeline_options.ocr_options.model_storage_directory = str(easyocr_dir)
            pipeline_options.ocr_options.download_enabled = False

    _configure_pdf_pipeline_options(pipeline_options, profile)

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )


def _get_docling_converter(profile: str = "fast"):
    profile = _docling_profile_for_mode(profile)
    if profile not in _DOCLING_CONVERTERS:
        with _DOCLING_CONVERTER_LOCK:
            if profile not in _DOCLING_CONVERTERS:
                _DOCLING_CONVERTERS[profile] = _create_docling_converter(profile)
    return _DOCLING_CONVERTERS[profile]


def reset_docling_converter_cache() -> None:
    with _DOCLING_CONVERTER_LOCK:
        _DOCLING_CONVERTERS.clear()


def warm_docling_converter(mode: str = "auto") -> Dict[str, Any]:
    """Eagerly initialize Docling so the first user document read is faster."""
    return _run_on_docling_thread(_warm_docling_converter_impl, mode)


def _warm_docling_converter_impl(mode: str = "auto") -> Dict[str, Any]:
    profile = _docling_profile_for_mode(mode)
    converter = _get_docling_converter(profile)
    return {
        "ok": True,
        "engine": "docling",
        "profile": profile,
        "converter": type(converter).__name__,
        "artifacts_path": str(_resolve_docling_artifacts_path() or ""),
    }


def _build_docling_converter():
    """Compatibility wrapper for older call sites/tests."""
    return _get_docling_converter("fast")


def _desktop_workspace_root() -> Optional[Path]:
    raw = (
        os.environ.get("HERMESDESK_WORKSPACE")
        or os.environ.get("HERMES_WORKSPACE")
        or ""
    ).strip()
    if not raw:
        return None
    try:
        return Path(raw).expanduser().resolve()
    except OSError:
        return None


def _is_outside_workspace(path: Path, workspace: Path) -> bool:
    try:
        path.resolve().relative_to(workspace.resolve())
        return False
    except ValueError:
        return True


def _is_unsupported_runtime_error(lowered: str) -> bool:
    """Detect Docling failures caused by an unsupported Python/ML runtime.

    Symptoms seen on unsupported interpreters (e.g. Python 3.14 with a torch
    build that has not caught up): torch import is "partially initialized" /
    missing attributes, or the pdfium backend cannot agree on a page count.
    These are environment problems, not bad input, so the hint must point at
    the supported runtime rather than at the document.
    """
    torch_broken = "torch" in lowered and any(
        token in lowered
        for token in ("partially initialized", "has no attribute", "no attribute 'library'")
    )
    pdfium_broken = "inconsistent number of pages" in lowered or "pdfium" in lowered
    torch_dispatcher_broken = (
        "already a kernel registered" in lowered
        and ("wait_tensor" in lowered or "_c10d_functional" in lowered)
    )
    return torch_broken or pdfium_broken or torch_dispatcher_broken


def _is_torch_dispatcher_registration_error(lowered: str) -> bool:
    return (
        "already a kernel registered" in lowered
        and ("wait_tensor" in lowered or "_c10d_functional" in lowered)
    )


def _format_docling_error(exc: BaseException) -> str:
    msg = str(exc).strip() or type(exc).__name__
    lowered = msg.lower()
    if _is_unsupported_runtime_error(lowered):
        runtime = f"CPython {sys.version_info.major}.{sys.version_info.minor} ({sys.executable})"
        if _is_torch_dispatcher_registration_error(lowered):
            hint = (
                "This points to duplicate PyTorch dispatcher registration in the current "
                "process, usually after a failed Docling/PyTorch warmup or re-import. Fully "
                "restart Kabuqina once; the background Docling warmup is disabled by default "
                "to avoid poisoning the main agent process."
            )
        elif sys.version_info[:2] == (3, 11):
            hint = (
                "The bundled 3.11 runtime is active, so this is most likely torch/Docling "
                "initialization state left behind in the current process. Fully restart "
                "Kabuqina once; if it repeats, keep the text fallback and report this "
                "docling_error."
            )
        else:
            hint = (
                "Kabuqina's supported runtime is the bundled CPython 3.11 from "
                "python/build_bundle.ps1; torch/pdfium may fail on newer interpreters "
                "such as 3.14. Run on the bundled 3.11 runtime to restore precise reads."
            )
        return (
            f"Docling backend failed on this Python/ML runtime ({type(exc).__name__}): {msg}. "
            f"This is an environment problem, not a bad document. Runtime: {runtime}. "
            f"{hint} A text-only fallback was used so this read could still succeed."
        )
    if any(token in lowered for token in ("huggingface", "timed out", "timeout", "connection")):
        return (
            f"Docling model load failed ({type(exc).__name__}): {msg}. "
            "Offline models may be missing from the app bundle, or HuggingFace is unreachable."
        )
    if isinstance(exc, ImportError):
        return f"Docling is not installed: {msg}"
    try:
        from docling_math_models import CodeFormulaMissingError

        if isinstance(exc, CodeFormulaMissingError):
            return msg
    except ImportError:
        pass
    if "code_formula_model_missing" in lowered:
        return msg
    if isinstance(exc, PermissionError) or "declined the formula model download" in lowered:
        return (
            f"Docling formula model unavailable ({type(exc).__name__}): {msg}. "
            "Open Kabuqina Settings → Load packages to download (~500 MB), then retry mode=math."
        )
    if "codeformula" in lowered and ("mode=math requires" in lowered or "hfvalidationerror" in lowered):
        return (
            f"Docling formula model unavailable ({type(exc).__name__}): {msg}. "
            "Open Kabuqina Settings → Load packages to download ds4sd/CodeFormula (~500 MB), "
            "then retry mode=math."
        )
    return f"Docling failed ({type(exc).__name__}): {msg}"


def _validate_read_path(document_path: Path, original_path: str, label: str) -> Optional[str]:
    if not document_path.exists():
        return tool_error(f"{label} not found: {original_path}")
    workspace = _desktop_workspace_root()
    if workspace is not None:
        try:
            resolved = document_path.resolve()
        except OSError:
            resolved = document_path
        if _is_outside_workspace(resolved, workspace):
            return tool_error(
                f"{label} path is outside the Kabuqina workspace ({workspace}): {original_path}",
                code="outside_workspace",
                workspace=str(workspace),
                hint=(
                    "Copy the file into the workspace first. If terminal is available, "
                    "run cp yourself (Git Bash: cp \"/d/.../file\" \"./file\") — "
                    "do not ask the user to copy manually."
                ),
            )
    return None


def _read_with_docling(document_path: Path, mode: str) -> Dict[str, Any]:
    return _run_on_docling_thread(_read_with_docling_impl, document_path, mode)


def _read_with_docling_impl(document_path: Path, mode: str) -> Dict[str, Any]:
    profile = _docling_profile_for_mode(mode)
    converter = _get_docling_converter(profile)
    result = converter.convert(str(document_path))
    document = result.document
    markdown = document.export_to_markdown()
    return {
        "ok": True,
        "engine": "docling",
        "mode": mode,
        "profile": profile,
        "path": str(document_path),
        "pages": len(getattr(document, "pages", []) or []),
        "content": markdown,
    }


def _read_pdf_with_pypdf(pdf_path: Path) -> Dict[str, Any]:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    chunks: List[str] = []
    for idx, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        chunks.append(f"<!-- page:{idx} -->\n{text}".strip())
    return {
        "ok": True,
        "engine": "pypdf",
        "mode": "fallback",
        "path": str(pdf_path),
        "pages": len(reader.pages),
        "content": "\n\n".join(chunks).strip(),
        "warning": "Used text-only pypdf fallback because Docling could not parse this PDF.",
    }


def _read_docx_with_python_docx(docx_path: Path) -> Dict[str, Any]:
    from docx import Document

    doc = Document(str(docx_path))
    chunks: List[str] = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            if any(cells):
                chunks.append(" | ".join(cells))
    return {
        "ok": True,
        "engine": "python-docx",
        "mode": "fallback",
        "path": str(docx_path),
        "pages": 0,
        "content": "\n\n".join(chunks).strip(),
        "warning": "Used text-only python-docx fallback because Docling could not parse this document.",
    }


def _read_pptx_with_python_pptx(pptx_path: Path) -> Dict[str, Any]:
    from pptx import Presentation

    prs = Presentation(str(pptx_path))
    slides: List[str] = []
    for idx, slide in enumerate(prs.slides, 1):
        parts: List[str] = []
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False) and shape.text.strip():
                parts.append(shape.text.strip())
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                    if any(cells):
                        parts.append(" | ".join(cells))
        slides.append(f"<!-- slide:{idx} -->\n" + "\n\n".join(parts).strip())
    return {
        "ok": True,
        "engine": "python-pptx",
        "mode": "fallback",
        "path": str(pptx_path),
        "slides": len(prs.slides),
        "content": "\n\n".join(slides).strip(),
        "warning": "Used text-only python-pptx fallback because Docling could not parse this document.",
    }


def _read_xlsx_with_openpyxl(xlsx_path: Path) -> Dict[str, Any]:
    from openpyxl import load_workbook

    wb = load_workbook(str(xlsx_path), read_only=True, data_only=True)
    chunks: List[str] = []
    for ws in wb.worksheets:
        chunks.append(f"## {ws.title}")
        for row in ws.iter_rows(values_only=True):
            values = ["" if cell is None else str(cell) for cell in row]
            if any(value.strip() for value in values):
                chunks.append(" | ".join(values))
    return {
        "ok": True,
        "engine": "openpyxl",
        "mode": "fallback",
        "path": str(xlsx_path),
        "sheets": len(wb.worksheets),
        "content": "\n".join(chunks).strip(),
        "warning": "Used text-only openpyxl fallback because Docling could not parse this document.",
    }


def _read_plain_text(document_path: Path) -> Dict[str, Any]:
    content = document_path.read_text(encoding="utf-8", errors="replace")
    return {
        "ok": True,
        "engine": "text",
        "mode": "fallback",
        "path": str(document_path),
        "content": content,
        "warning": "Used plain-text fallback because Docling could not parse this document.",
    }


def _read_with_fallback(document_path: Path) -> Optional[Dict[str, Any]]:
    suffix = document_path.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf_with_pypdf(document_path)
    if suffix == ".docx":
        return _read_docx_with_python_docx(document_path)
    if suffix == ".pptx":
        return _read_pptx_with_python_pptx(document_path)
    if suffix == ".xlsx":
        return _read_xlsx_with_openpyxl(document_path)
    if suffix in {".html", ".htm", ".md", ".markdown", ".csv", ".txt"}:
        return _read_plain_text(document_path)
    return None


def _should_try_lightweight_first(suffix: str, mode: str) -> bool:
    return _docling_profile_for_mode(mode) == "fast" and suffix in _LIGHTWEIGHT_FIRST_SUFFIXES


def _pdf_fast_text_is_sufficient(payload: Dict[str, Any]) -> bool:
    """Is the pypdf text good enough to skip Docling? Guards against scanned PDFs.

    A text-based PDF (most papers/reports) extracts plenty of characters; a
    scanned/image PDF yields almost nothing, in which case we fall through to
    Docling so layout/OCR still has a chance.
    """
    content = str(payload.get("content") or "").strip()
    if len(content) < 200:
        return False
    pages = int(payload.get("pages") or 0)
    if pages > 0 and (len(content) / pages) < 40:
        return False
    return True


def _attach_docling_error(payload: Dict[str, Any], docling_error: Optional[str]) -> Dict[str, Any]:
    if docling_error:
        payload["docling_error"] = docling_error
    return payload


def _should_avoid_docling_fallback(mode: str, exc: Optional[BaseException] = None) -> bool:
    if _docling_profile_for_mode(mode) == "math":
        return True
    if exc is not None:
        lowered = str(exc).lower()
        if "code_formula_model_missing" in lowered:
            return True
    try:
        from docling_math_models import CodeFormulaMissingError

        if isinstance(exc, CodeFormulaMissingError):
            return True
    except ImportError:
        pass
    if isinstance(exc, PermissionError):
        return True
    if exc is not None and "declined the formula model download" in str(exc).lower():
        return True
    return False


def _read_document_precise_payload(document_path: Path, *, mode: str, include_content: bool = True) -> Dict[str, Any]:
    suffix = document_path.suffix.lower()
    docling_error: Optional[str] = None

    if suffix == ".doc":
        return _error_payload(
            "Legacy .doc files are not directly supported by Docling.",
            ok=False,
            code="unsupported_legacy_doc",
            hint="Convert the file with LibreOffice headless to .docx or .pdf, then read it again.",
        )
    if suffix not in _DOCLING_SUFFIXES and suffix not in _FALLBACK_SUFFIXES:
        return _error_payload(
            f"Unsupported document type: {suffix or '(no extension)'}",
            ok=False,
            code="unsupported_document_type",
            supported=sorted(_DOCLING_SUFFIXES | _FALLBACK_SUFFIXES),
        )

    # Fast text-first for PDFs in auto/fast mode: a text-based paper/report
    # extracts in well under a second with pypdf, versus minutes of Docling
    # layout inference on CPU. Scanned/sparse PDFs fail the sufficiency guard
    # and fall through to Docling. precise/math modes always use Docling.
    if suffix == ".pdf" and _docling_profile_for_mode(mode) == "fast":
        try:
            fast = _read_pdf_with_pypdf(document_path)
        except Exception:
            fast = None
        if fast is not None and _pdf_fast_text_is_sufficient(fast):
            fast["mode"] = mode
            fast["engine"] = "pypdf"
            fast["warning"] = (
                "Fast text-only PDF read (pypdf) — chosen for speed, not a Docling "
                "failure. For layout, tables, or formula extraction, re-read with "
                "mode=precise or mode=math."
            )
            return _finalize_read_payload(fast, document_path, include_content=include_content)

    if _should_try_lightweight_first(suffix, mode):
        try:
            fallback = _read_with_fallback(document_path)
            if fallback is not None:
                fallback["mode"] = mode
                return _finalize_read_payload(fallback, document_path, include_content=include_content)
        except Exception:
            pass

    if suffix in _DOCLING_SUFFIXES:
        try:
            return _finalize_read_payload(_read_with_docling(document_path, mode), document_path, include_content=include_content)
        except Exception as exc:
            docling_error = _format_docling_error(exc)
            if _should_avoid_docling_fallback(mode, exc):
                return _error_payload(
                    docling_error or "Docling read failed.",
                    ok=False,
                    code="docling_math_unavailable",
                    docling_error=docling_error,
                )

    try:
        fallback = _read_with_fallback(document_path)
        if fallback is not None:
            return _finalize_read_payload(
                _attach_docling_error(fallback, docling_error),
                document_path,
                include_content=include_content,
            )
    except Exception as exc:
        return _error_payload(
            f"Document fallback read failed: {exc}",
            ok=False,
            docling_error=docling_error,
        )

    return _error_payload(
        "Docling could not parse this document and no local fallback is available.",
        ok=False,
        code="docling_failed_no_fallback",
        docling_error=docling_error,
    )


def pdf_read_precise(path: str, mode: str = "auto", include_content: bool = True) -> str:
    pdf_path = Path(path).expanduser()
    validation_error = _validate_read_path(pdf_path, path, "PDF")
    if validation_error is not None:
        return validation_error
    if pdf_path.suffix.lower() != ".pdf":
        return tool_error("pdf_read_precise only accepts .pdf files")
    return _json(_read_document_precise_payload(pdf_path, mode=mode, include_content=include_content))


def document_read_precise(path: str, mode: str = "auto", include_content: bool = True) -> str:
    document_path = Path(path).expanduser()
    validation_error = _validate_read_path(document_path, path, "Document")
    if validation_error is not None:
        return validation_error
    return _json(_read_document_precise_payload(document_path, mode=mode, include_content=include_content))


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


def _text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return text or default


def _list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _string_list(value: Any, *, limit: int = 8) -> List[str]:
    return [_text(item) for item in _list(value) if _text(item)][:limit]


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _validate_write_path(out_path: Path, original_path: str) -> Optional[str]:
    """Workspace guard for *write* targets (the file need not exist yet)."""
    workspace = _desktop_workspace_root()
    if workspace is None:
        return None
    try:
        resolved = out_path.resolve()
    except OSError:
        resolved = out_path
    if _is_outside_workspace(resolved, workspace):
        return tool_error(
            f"Output path is outside the Kabuqina workspace ({workspace}): {original_path}",
            code="outside_workspace",
            workspace=str(workspace),
            hint="Write the output file into the workspace (or a subfolder of it).",
        )
    return None


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
    return entry


def _build_deck_spec(
    title: str,
    slides: List[Dict[str, Any]],
    theme: "_PptxTheme",
    visual_master: str,
) -> Dict[str, Any]:
    return {
        "title": _text(title) or "学生汇报",
        "template": theme.key,
        "template_subtitle": theme.subtitle,
        "template_badge": theme.badge,
        "visual_master": visual_master,
        "visual_master_name": _pptx_visual_master_name(visual_master),
        "page_size": {"width": 13.333, "height": 7.5},
        "slides": [_deck_slide_spec(raw) for raw in (slides or [])],
    }


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


def _pdf_blocks(document: Any) -> List[Dict[str, Any]]:
    if isinstance(document, str):
        return [{"type": "paragraph", "text": document}]
    if isinstance(document, list):
        return [_pdf_block(item) for item in document]
    document = _dict(document)
    if isinstance(document.get("blocks"), list):
        return [_pdf_block(item) for item in document.get("blocks") or []]
    blocks: List[Dict[str, Any]] = []
    for section in _list(document.get("sections")):
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
        return f"<div class=\"formula\">{html.escape(_text(block.get('text')))}</div>"
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

    spec = _build_pdf_spec(title, document, template, visual_master)
    html_source = _build_pdf_html(spec)
    try:
        pdf_bytes, page_count, renderer = _render_pdf_with_reportlab(spec)
    except ImportError as exc:
        return tool_error(
            f"PDF rendering requires ReportLab in the desktop Python bundle: {exc}",
            code="pdf_render_unavailable",
        )
    except Exception as exc:
        return tool_error(f"PDF rendering failed: {exc}", code="pdf_render_failed")

    out.parent.mkdir(parents=True, exist_ok=True)
    html_path = out.with_suffix(".html")
    out.write_bytes(pdf_bytes)
    html_path.write_text(html_source, encoding="utf-8")
    return _json(
        {
            "ok": True,
            "path": str(out),
            "html_path": str(html_path),
            "page_count": int(page_count),
            "template": spec["template"],
            "visual_master": spec["visual_master"],
            "renderer": renderer,
            "bytes": len(pdf_bytes),
        }
    )


def pptx_write(
    path: str,
    title: str,
    slides: List[Dict[str, Any]],
    template: str = "course_report",
    visual_master: str = "default_native",
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
    theme = _get_pptx_theme(template)
    selected_visual_master = _normalize_pptx_visual_master(visual_master)
    out = Path(path).expanduser()
    if out.suffix.lower() != ".pptx":
        out = out.with_suffix(".pptx")

    deck_spec = _build_deck_spec(title, slides, theme, selected_visual_master)

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


PDF_READ_PRECISE_SCHEMA = {
    "name": "pdf_read_precise",
    "description": (
        "Precisely read a PDF for student work. Path must be inside the Kabuqina "
        "workspace (file tools cannot read D: or other folders directly). "
        "If the PDF is elsewhere, copy it into the workspace with terminal first. "
        "Uses Docling when available, with pypdf fallback. For math/formula "
        "extraction, call with mode=math and inspect the extracted Markdown/read-cache; "
        "do not use vision_analyze for a normal PDF unless this reader fails or the "
        "user explicitly asks for visual image description."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "mode": {"type": "string", "description": "auto, precise, or math. math enables Docling formula enrichment for LaTeX-oriented extraction."},
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
        "Precisely read student documents using Docling as the primary engine. "
        "Supports PDF, DOCX, PPTX, XLSX, HTML, Markdown, CSV, common images, and text. "
        "Legacy .doc must be converted to .docx or .pdf first. Uses format-specific "
        "text fallbacks when Docling fails and reports the real Docling error."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "mode": {"type": "string", "description": "auto, precise, or math. math enables Docling formula enrichment for LaTeX-oriented extraction."},
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
        "and visual placeholders. The v1 renderer builds normalized blocks, writes "
        "HTML source, then renders the PDF with ReportLab in the desktop Python bundle."
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
                    "Structured document spec. Prefer sections or blocks. Supported block "
                    "types: heading, paragraph, bullets, table, code, formula, "
                    "image_placeholder, page_break."
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
        "paper_report (green academic), code_defense (indigo/orange tech defense). "
        "The deck is rendered by PptxGenJS in the Kabuqina desktop UI using the selected "
        "visual_master palette; this tool requires the interactive app (it is not available "
        "in headless/CLI contexts)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "title": {"type": "string"},
            "template": {"type": "string", "description": "course_report, paper_report, or code_defense"},
            "visual_master": {
                "type": "string",
                "description": (
                    "default_native, soft_editorial, blue_professional, signal, "
                    "neo_grid_bold, or editorial_forest. Use the visual master selected by the user."
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
                                "process_flow_vertical, data_table, media_placeholder, section_divider. "
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
                            "description": "For table slides. Use headers and rows arrays.",
                        },
                        "placeholder": {
                            "type": "object",
                            "description": (
                                "For screenshot/chart placeholders. Use label, caption, and optional source_hint. "
                                "Do not claim a real asset was inserted when using a placeholder."
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


registry.register(
    name="pdf_read_precise",
    toolset="documents",
    schema=PDF_READ_PRECISE_SCHEMA,
    handler=lambda args, **kw: pdf_read_precise(
        path=args.get("path", ""),
        mode=args.get("mode", "auto"),
        include_content=bool(args.get("include_content", True)),
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
    name="pptx_write",
    toolset="documents",
    schema=PPTX_WRITE_SCHEMA,
    handler=lambda args, **kw: pptx_write(
        path=args.get("path", ""),
        title=args.get("title", ""),
        slides=args.get("slides") or [],
        template=args.get("template", "course_report"),
        visual_master=args.get("visual_master", "default_native"),
        callback=kw.get("callback"),
    ),
    check_fn=lambda: True,
    emoji="📊",
)
