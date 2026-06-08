"""Document read/write tools for student deliverables."""

from __future__ import annotations

import json
import os
import sys
import hashlib
import tempfile
import threading
from copy import deepcopy
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


def _set_notes(slide, raw: Dict[str, Any], extra: str = "") -> None:
    notes = _text(raw.get("notes"))
    if extra:
        notes = f"{notes}\n{extra}".strip()
    if notes:
        slide.notes_slide.notes_text_frame.text = notes


def _set_slide_background(slide, rgb: Rgb) -> None:
    from pptx.dml.color import RGBColor

    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(*rgb)


def _add_bar(slide, *, left, top, width, height, rgb: Rgb):
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE

    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor(*rgb)
    shape.line.fill.background()
    return shape


def _style_paragraph(paragraph, *, text: str, size: int, rgb: Rgb, bold: bool = False) -> None:
    from pptx.dml.color import RGBColor
    from pptx.util import Pt

    paragraph.text = text
    paragraph.font.size = Pt(size)
    paragraph.font.bold = bold
    paragraph.font.color.rgb = RGBColor(*rgb)


def _style_title_shape(shape, text: str, theme: _PptxTheme, *, size: int) -> None:
    if shape is None or not getattr(shape, "has_text_frame", False):
        return
    _style_paragraph(shape.text_frame.paragraphs[0], text=text, size=size, rgb=theme.title, bold=True)


def _hide_body_placeholder(slide) -> None:
    if len(slide.placeholders) <= 1:
        return
    body = slide.placeholders[1]
    if getattr(body, "has_text_frame", False):
        body.text_frame.clear()


def _add_textbox(slide, *, left, top, width, height, text: str, size: int, rgb: Rgb, bold: bool = False):
    from pptx.dml.color import RGBColor
    from pptx.util import Pt

    box = slide.shapes.add_textbox(left, top, width, height)
    frame = box.text_frame
    frame.word_wrap = True
    frame.margin_left = 0
    frame.margin_right = 0
    paragraph = frame.paragraphs[0]
    paragraph.text = text
    paragraph.font.size = Pt(size)
    paragraph.font.bold = bold
    paragraph.font.color.rgb = RGBColor(*rgb)
    return box


def _add_subtitle(slide, raw: Dict[str, Any], theme: _PptxTheme) -> None:
    from pptx.util import Inches

    subtitle = _text(raw.get("subtitle"))
    if subtitle:
        _add_textbox(
            slide,
            left=Inches(0.7),
            top=Inches(1.08),
            width=Inches(10.8),
            height=Inches(0.35),
            text=subtitle,
            size=15,
            rgb=theme.subtitle_color,
            bold=True,
        )


def _render_bullets(slide, raw: Dict[str, Any], theme: _PptxTheme, *, numbered: bool = False, limit: int = 7) -> None:
    from pptx.dml.color import RGBColor
    from pptx.util import Pt

    _add_subtitle(slide, raw, theme)
    body = slide.placeholders[1].text_frame
    body.clear()
    bullets = _string_list(raw.get("bullets"), limit=limit)
    if not bullets:
        bullets = ["请补充本页要点"]
    for i, bullet in enumerate(bullets):
        p = body.paragraphs[0] if i == 0 else body.add_paragraph()
        p.text = f"{i + 1}. {bullet}" if numbered else bullet
        p.level = 0
        p.font.size = Pt(19 if not numbered else 20)
        p.font.color.rgb = RGBColor(*theme.body)


def _render_diagram(slide, raw: Dict[str, Any], theme: _PptxTheme) -> None:
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Inches, Pt

    _hide_body_placeholder(slide)
    _add_subtitle(slide, raw, theme)
    payload = _dict(raw.get("diagram"))
    nodes = _string_list(payload.get("nodes") or payload.get("steps") or raw.get("bullets"), limit=6)
    if len(nodes) < 2:
        _render_bullets(slide, {**raw, "bullets": nodes or raw.get("bullets")}, theme)
        return

    horizontal = len(nodes) <= 4
    if horizontal:
        box_w = Inches(2.35)
        box_h = Inches(1.0)
        gap = Inches(0.45)
        left = Inches(0.75)
        top = Inches(3.0)
        for i, node in enumerate(nodes):
            x = left + i * (box_w + gap)
            shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, top, box_w, box_h)
            shape.fill.solid()
            shape.fill.fore_color.rgb = RGBColor(255, 255, 255)
            shape.line.color.rgb = RGBColor(*theme.accent)
            paragraph = shape.text_frame.paragraphs[0]
            paragraph.text = node
            paragraph.font.size = Pt(15)
            paragraph.font.bold = True
            paragraph.font.color.rgb = RGBColor(*theme.title)
            if i < len(nodes) - 1:
                _add_textbox(
                    slide,
                    left=x + box_w,
                    top=top + Inches(0.32),
                    width=gap,
                    height=Inches(0.3),
                    text="→",
                    size=20,
                    rgb=theme.accent,
                    bold=True,
                )
    else:
        left = Inches(1.0)
        top = Inches(1.75)
        box_w = Inches(5.8)
        box_h = Inches(0.55)
        step_gap = Inches(0.68)
        for i, node in enumerate(nodes):
            y = top + i * step_gap
            shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, y, box_w, box_h)
            shape.fill.solid()
            shape.fill.fore_color.rgb = RGBColor(255, 255, 255)
            shape.line.color.rgb = RGBColor(*theme.accent)
            paragraph = shape.text_frame.paragraphs[0]
            paragraph.text = node
            paragraph.font.size = Pt(14)
            paragraph.font.color.rgb = RGBColor(*theme.title)
            if i < len(nodes) - 1:
                _add_textbox(
                    slide,
                    left=left + Inches(6.05),
                    top=y + Inches(0.08),
                    width=Inches(0.35),
                    height=Inches(0.35),
                    text="↓",
                    size=16,
                    rgb=theme.accent,
                    bold=True,
                )


def _render_table(slide, raw: Dict[str, Any], theme: _PptxTheme) -> None:
    from pptx.dml.color import RGBColor
    from pptx.util import Inches, Pt

    _hide_body_placeholder(slide)
    _add_subtitle(slide, raw, theme)
    payload = _dict(raw.get("table"))
    headers = _string_list(payload.get("headers"), limit=5)
    rows = [_string_list(row, limit=len(headers) or 5) for row in _list(payload.get("rows"))[:6]]
    rows = [row for row in rows if row]
    if not headers or not rows:
        _render_bullets(slide, raw, theme)
        return

    row_count = len(rows) + 1
    col_count = len(headers)
    table_shape = slide.shapes.add_table(
        row_count,
        col_count,
        Inches(0.75),
        Inches(1.7),
        Inches(11.6),
        Inches(4.45),
    )
    table = table_shape.table
    for col, header in enumerate(headers):
        cell = table.cell(0, col)
        cell.text = header
        cell.fill.solid()
        cell.fill.fore_color.rgb = RGBColor(*theme.accent)
        for paragraph in cell.text_frame.paragraphs:
            paragraph.font.size = Pt(13)
            paragraph.font.bold = True
            paragraph.font.color.rgb = RGBColor(255, 255, 255)

    for r_idx, row in enumerate(rows, 1):
        for c_idx, header in enumerate(headers):
            cell = table.cell(r_idx, c_idx)
            cell.text = row[c_idx] if c_idx < len(row) else ""
            for paragraph in cell.text_frame.paragraphs:
                paragraph.font.size = Pt(12)
                paragraph.font.color.rgb = RGBColor(*theme.body)


def _render_placeholder(slide, raw: Dict[str, Any], theme: _PptxTheme, *, chart: bool) -> None:
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Inches, Pt

    _hide_body_placeholder(slide)
    _add_subtitle(slide, raw, theme)
    payload = _dict(raw.get("placeholder"))
    label = _text(payload.get("label"), "待补充图表" if chart else "待补充截图")
    caption = _text(payload.get("caption"), "请替换为真实材料后再提交。")
    source_hint = _text(payload.get("source_hint"))

    frame = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(1.15),
        Inches(1.85),
        Inches(10.7),
        Inches(3.65),
    )
    frame.fill.solid()
    frame.fill.fore_color.rgb = RGBColor(255, 255, 255)
    frame.line.color.rgb = RGBColor(*theme.accent)

    icon = "CHART PLACEHOLDER" if chart else "SCREENSHOT PLACEHOLDER"
    _add_textbox(
        slide,
        left=Inches(1.65),
        top=Inches(2.45),
        width=Inches(9.7),
        height=Inches(0.35),
        text=icon,
        size=11,
        rgb=theme.subtitle_color,
        bold=True,
    )
    _add_textbox(
        slide,
        left=Inches(1.65),
        top=Inches(3.0),
        width=Inches(9.7),
        height=Inches(0.55),
        text=label,
        size=24,
        rgb=theme.title,
        bold=True,
    )
    _add_textbox(
        slide,
        left=Inches(1.65),
        top=Inches(3.85),
        width=Inches(9.7),
        height=Inches(0.6),
        text=caption,
        size=15,
        rgb=theme.body,
    )
    if source_hint:
        _set_notes(slide, raw, f"素材提示：{source_hint}")


def _render_backup(slide, raw: Dict[str, Any], theme: _PptxTheme) -> None:
    from pptx.util import Inches

    _add_bar(slide, left=Inches(10.65), top=Inches(0.45), width=Inches(1.5), height=Inches(0.32), rgb=theme.accent_light)
    _add_textbox(
        slide,
        left=Inches(10.75),
        top=Inches(0.47),
        width=Inches(1.3),
        height=Inches(0.25),
        text="BACKUP",
        size=10,
        rgb=theme.title,
        bold=True,
    )
    _render_bullets(slide, raw, theme, limit=6)


def _apply_title_slide(slide, prs, theme: _PptxTheme, title: str) -> None:
    from pptx.dml.color import RGBColor
    from pptx.util import Inches, Pt

    _set_slide_background(slide, theme.bg)
    width = prs.slide_width
    height = prs.slide_height

    if theme.title_band is not None:
        band_h = Inches(1.05)
        _add_bar(slide, left=0, top=0, width=width, height=band_h, rgb=theme.title_band)
        badge = slide.shapes.add_textbox(Inches(0.55), Inches(0.28), Inches(2.4), Inches(0.45))
        _style_paragraph(
            badge.text_frame.paragraphs[0],
            text=theme.badge,
            size=16,
            rgb=(255, 255, 255),
            bold=True,
        )

    if theme.footer_band is not None:
        band_h = Inches(0.95)
        _add_bar(
            slide,
            left=0,
            top=height - band_h,
            width=width,
            height=band_h,
            rgb=theme.footer_band,
        )
        accent_h = Inches(0.07)
        _add_bar(
            slide,
            left=0,
            top=height - band_h - accent_h,
            width=width,
            height=accent_h,
            rgb=theme.accent_light,
        )

    if theme.key == "paper_report":
        _add_bar(slide, left=0, top=0, width=Inches(0.22), height=height, rgb=theme.accent)
        _add_bar(
            slide,
            left=Inches(0.95),
            top=Inches(4.85),
            width=Inches(4.5),
            height=Inches(0.05),
            rgb=theme.accent_light,
        )

    title_shape = slide.shapes.title
    _style_title_shape(title_shape, title or "学生汇报", theme, size=40)

    subtitle_shape = slide.placeholders[1]
    subtitle_shape.text = theme.subtitle
    sub_p = subtitle_shape.text_frame.paragraphs[0]
    sub_p.font.size = Pt(22)
    sub_p.font.color.rgb = RGBColor(*theme.subtitle_color)


def _apply_content_slide(slide, prs, theme: _PptxTheme, raw: Dict[str, Any]) -> None:
    from pptx.util import Inches

    _set_slide_background(slide, theme.bg)
    width = prs.slide_width
    height = prs.slide_height

    _add_bar(slide, left=0, top=0, width=Inches(0.16), height=height, rgb=theme.accent)

    if theme.key == "course_report":
        _add_bar(slide, left=0, top=0, width=width, height=Inches(0.08), rgb=theme.accent_light)
    elif theme.key == "paper_report":
        _add_bar(
            slide,
            left=Inches(0.55),
            top=Inches(1.35),
            width=Inches(2.8),
            height=Inches(0.05),
            rgb=theme.accent_light,
        )
    elif theme.key == "code_defense":
        accent_h = Inches(0.06)
        _add_bar(
            slide,
            left=0,
            top=height - accent_h,
            width=width,
            height=accent_h,
            rgb=theme.accent_light,
        )

    title_shape = slide.shapes.title
    _style_title_shape(title_shape, str(raw.get("title") or "未命名页"), theme, size=30)

    slide_type = _normalize_slide_type(raw.get("slide_type"))
    if slide_type == "agenda":
        _render_bullets(slide, raw, theme, numbered=True, limit=8)
        _set_notes(slide, raw)
    elif slide_type == "diagram":
        _render_diagram(slide, raw, theme)
        _set_notes(slide, raw)
    elif slide_type == "table":
        _render_table(slide, raw, theme)
        _set_notes(slide, raw)
    elif slide_type == "screenshot_placeholder":
        _render_placeholder(slide, raw, theme, chart=False)
        if not _text(_dict(raw.get("placeholder")).get("source_hint")):
            _set_notes(slide, raw)
    elif slide_type == "chart_placeholder":
        _render_placeholder(slide, raw, theme, chart=True)
        if not _text(_dict(raw.get("placeholder")).get("source_hint")):
            _set_notes(slide, raw)
    elif slide_type == "qa_backup":
        _render_backup(slide, raw, theme)
        _set_notes(slide, raw)
    elif slide_type == "closing":
        _render_bullets(slide, raw, theme, limit=5)
        _set_notes(slide, raw)
    else:
        _render_bullets(slide, raw, theme)
        _set_notes(slide, raw)


def _repo_visual_master_root() -> Optional[Path]:
    candidates = [Path.cwd(), Path(__file__).resolve()]
    for start in candidates:
        for parent in [start, *start.parents]:
            root = parent / "assets" / "ppt" / "visual-masters"
            if root.exists():
                return root
    return None


def _visual_master_asset_dir(visual_master: str) -> Optional[Path]:
    master_dir = _PPTX_VISUAL_MASTERS[visual_master].get("dir")
    if not master_dir:
        return None
    root = _repo_visual_master_root()
    if root is None:
        return None
    asset_dir = root / master_dir
    return asset_dir if (asset_dir / "template.pptx").exists() else None


def _parse_hex_rgb(value: Any, fallback: Rgb) -> Rgb:
    text = str(value or "").strip()
    if not text.startswith("#") or len(text) != 7:
        return fallback
    try:
        return (int(text[1:3], 16), int(text[3:5], 16), int(text[5:7], 16))
    except ValueError:
        return fallback


def _visual_master_tokens(asset_dir: Path, theme: _PptxTheme) -> Dict[str, Rgb]:
    metadata_path = asset_dir / "metadata.json"
    raw_tokens: Dict[str, Any] = {}
    if metadata_path.exists():
        try:
            raw_tokens = json.loads(metadata_path.read_text(encoding="utf-8")).get("tokens") or {}
        except Exception:
            raw_tokens = {}
    bg = _parse_hex_rgb(
        raw_tokens.get("background")
        or raw_tokens.get("paper")
        or raw_tokens.get("cream")
        or raw_tokens.get("forest_green")
        or raw_tokens.get("background_light"),
        theme.bg,
    )
    luminance = 0.2126 * bg[0] + 0.7152 * bg[1] + 0.0722 * bg[2]
    default_text = (245, 245, 245) if luminance < 110 else theme.title
    default_body = (225, 225, 225) if luminance < 110 else theme.body
    return {
        "background": bg,
        "title": _parse_hex_rgb(
            raw_tokens.get("text")
            or raw_tokens.get("ink")
            or raw_tokens.get("text_on_dark")
            or raw_tokens.get("text_on_light"),
            default_text,
        ),
        "body": _parse_hex_rgb(
            raw_tokens.get("text_muted")
            or raw_tokens.get("ink_soft")
            or raw_tokens.get("muted")
            or raw_tokens.get("text_on_dark_muted")
            or raw_tokens.get("text_on_light_muted"),
            default_body,
        ),
        "accent": _parse_hex_rgb(raw_tokens.get("accent") or raw_tokens.get("pink"), theme.accent),
    }


def _load_visual_master_slide_map(asset_dir: Path, slide_count: int) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    frame_map_path = asset_dir / "frame-map.json"
    if frame_map_path.exists():
        try:
            frames = json.loads(frame_map_path.read_text(encoding="utf-8")).get("frames") or []
            for frame in frames:
                slide_no = int(frame.get("current_slide") or 0) - 1
                if slide_no < 0 or slide_no >= slide_count:
                    continue
                role = str(frame.get("role") or "").strip().lower()
                if role:
                    mapping.setdefault(role, slide_no)
                for slide_type in frame.get("writer_slide_types") or []:
                    mapping.setdefault(str(slide_type).strip().lower(), slide_no)
        except Exception:
            mapping = {}
    mapping.setdefault("cover", 0)
    mapping.setdefault("title", 0)
    mapping.setdefault("agenda", min(1, slide_count - 1))
    mapping.setdefault("claim_bullets", min(2, slide_count - 1))
    mapping.setdefault("diagram", min(4, slide_count - 1))
    mapping.setdefault("table", min(3, slide_count - 1))
    mapping.setdefault("screenshot_placeholder", min(4, slide_count - 1))
    mapping.setdefault("chart_placeholder", min(5, slide_count - 1))
    mapping.setdefault("qa_backup", min(max(slide_count - 2, 1), slide_count - 1))
    mapping.setdefault("closing", max(slide_count - 1, 0))
    return mapping


def _clone_slide_from_master(prs, source_slide):
    blank_index = min(6, len(prs.slide_layouts) - 1)
    blank_layout = prs.slide_layouts[blank_index]
    dest = prs.slides.add_slide(blank_layout)
    for shape in source_slide.shapes:
        dest.shapes._spTree.insert_element_before(deepcopy(shape.element), "p:extLst")
    for rel in source_slide.part.rels.values():
        if rel.reltype.endswith("/slideLayout") or rel.reltype.endswith("/notesSlide"):
            continue
        if getattr(rel, "is_external", False):
            dest.part.rels._add_relationship(rel.reltype, rel.target_ref, is_external=True)
        else:
            dest.part.rels._add_relationship(rel.reltype, rel.target_part)
    return dest


def _delete_slide(prs, slide) -> None:
    slide_id = slide.slide_id
    slides = prs.slides
    for sld_id in list(slides._sldIdLst):
        if int(sld_id.id) == slide_id:
            rel_id = sld_id.rId
            slides._sldIdLst.remove(sld_id)
            prs.part.drop_rel(rel_id)
            return


def _fill_shape(slide, *, left, top, width, height, rgb: Rgb):
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE

    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor(*rgb)
    shape.line.fill.background()
    return shape


def _blank_master_baked_text(slide, bg: Rgb) -> None:
    for shape in list(slide.shapes):
        if getattr(shape, "has_text_frame", False) and _text(getattr(shape, "text", "")):
            _fill_shape(slide, left=shape.left, top=shape.top, width=shape.width, height=shape.height, rgb=bg)
            shape.text_frame.clear()


def _content_lines(raw: Dict[str, Any], *, limit: int = 7) -> List[str]:
    slide_type = _normalize_slide_type(raw.get("slide_type"))
    if slide_type in {"diagram", "chart_placeholder", "screenshot_placeholder"}:
        payload = _dict(raw.get("diagram")) or _dict(raw.get("placeholder"))
        lines = _string_list(payload.get("nodes") or payload.get("steps") or raw.get("bullets"), limit=limit)
        label = _text(payload.get("label"))
        caption = _text(payload.get("caption"))
        if label:
            lines.insert(0, label)
        if caption:
            lines.append(caption)
        return lines[:limit]
    if slide_type == "table":
        payload = _dict(raw.get("table"))
        headers = _string_list(payload.get("headers"), limit=5)
        rows = [_string_list(row, limit=len(headers) or 5) for row in _list(payload.get("rows"))[:4]]
        if headers and rows:
            return [" | ".join(headers), *[" | ".join(row) for row in rows if row]][:limit]
    return _string_list(raw.get("bullets"), limit=limit) or ["请补充本页要点"]


def _apply_visual_master_slide_text(slide, prs, title: str, lines: List[str], tokens: Dict[str, Rgb], *, cover: bool) -> None:
    from pptx.util import Inches

    _blank_master_baked_text(slide, tokens["background"])
    width = prs.slide_width
    if cover:
        _fill_shape(slide, left=Inches(0.7), top=Inches(1.1), width=Inches(11.9), height=Inches(2.2), rgb=tokens["background"])
        _add_textbox(
            slide,
            left=Inches(0.82),
            top=Inches(1.25),
            width=Inches(11.3),
            height=Inches(1.0),
            text=title or "学生汇报",
            size=38,
            rgb=tokens["title"],
            bold=True,
        )
        _add_textbox(
            slide,
            left=Inches(0.86),
            top=Inches(2.45),
            width=Inches(10.5),
            height=Inches(0.45),
            text=lines[0] if lines else "课程 / 论文 / 项目答辩",
            size=18,
            rgb=tokens["body"],
        )
        return

    _fill_shape(slide, left=Inches(0.55), top=Inches(0.42), width=width - Inches(1.1), height=Inches(0.82), rgb=tokens["background"])
    _add_textbox(
        slide,
        left=Inches(0.7),
        top=Inches(0.52),
        width=Inches(11.9),
        height=Inches(0.48),
        text=title or "未命名页",
        size=26,
        rgb=tokens["title"],
        bold=True,
    )
    body_text = "\n".join(f"{idx + 1}. {line}" for idx, line in enumerate(lines[:7]))
    _fill_shape(slide, left=Inches(0.78), top=Inches(1.52), width=Inches(11.8), height=Inches(4.95), rgb=tokens["background"])
    _add_textbox(
        slide,
        left=Inches(0.95),
        top=Inches(1.72),
        width=Inches(11.2),
        height=Inches(4.45),
        text=body_text,
        size=20,
        rgb=tokens["body"],
    )


def _try_write_visual_master_pptx(
    *,
    out: Path,
    title: str,
    slides: List[Dict[str, Any]],
    theme: _PptxTheme,
    visual_master: str,
) -> Optional[Dict[str, Any]]:
    asset_dir = _visual_master_asset_dir(visual_master)
    if asset_dir is None:
        return None
    try:
        from pptx import Presentation
    except Exception:
        return None

    source_prs = Presentation(str(asset_dir / "template.pptx"))
    original_slides = list(source_prs.slides)
    if not original_slides:
        return None
    prs = Presentation()
    prs.slide_width = source_prs.slide_width
    prs.slide_height = source_prs.slide_height

    tokens = _visual_master_tokens(asset_dir, theme)
    slide_map = _load_visual_master_slide_map(asset_dir, len(original_slides))
    generated_slides = []

    cover_source = original_slides[slide_map.get("cover", 0)]
    cover = _clone_slide_from_master(prs, cover_source)
    _apply_visual_master_slide_text(cover, prs, title, [theme.subtitle], tokens, cover=True)
    generated_slides.append(cover)

    for index, raw in enumerate(slides):
        slide_type = _normalize_slide_type(raw.get("slide_type"))
        source_index = slide_map.get(slide_type)
        if source_index is None:
            source_index = slide_map.get("claim_bullets", min((index % len(original_slides)), len(original_slides) - 1))
        cloned = _clone_slide_from_master(prs, original_slides[source_index])
        _apply_visual_master_slide_text(
            cloned,
            prs,
            _text(raw.get("title"), "未命名页"),
            _content_lines(raw),
            tokens,
            cover=False,
        )
        _set_notes(cloned, raw)
        generated_slides.append(cloned)

    prs.save(str(out))
    return {
        "ok": True,
        "path": str(out),
        "slide_count": len(generated_slides),
        "template": theme.key,
        "theme": theme.badge,
        "visual_master": visual_master,
        "visual_master_name": _pptx_visual_master_name(visual_master),
        "visual_master_renderer": "html_background_master_v1",
        "visual_master_template": str(asset_dir / "template.pptx"),
    }


def pptx_write(
    path: str,
    title: str,
    slides: List[Dict[str, Any]],
    template: str = "course_report",
    visual_master: str = "default_native",
) -> str:
    try:
        from pptx import Presentation
        from pptx.util import Inches
    except Exception as exc:
        return tool_error(f"python-pptx is not available: {exc}")

    theme = _get_pptx_theme(template)
    selected_visual_master = _normalize_pptx_visual_master(visual_master)
    out = Path(path).expanduser()
    if out.suffix.lower() != ".pptx":
        out = out.with_suffix(".pptx")
    out.parent.mkdir(parents=True, exist_ok=True)

    visual_result = None
    if selected_visual_master != "default_native":
        visual_result = _try_write_visual_master_pptx(
            out=out,
            title=title,
            slides=slides,
            theme=theme,
            visual_master=selected_visual_master,
        )
    if visual_result is not None:
        return _json(visual_result)

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    title_slide = prs.slides.add_slide(prs.slide_layouts[0])
    _apply_title_slide(title_slide, prs, theme, title)

    for raw in slides:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        _apply_content_slide(slide, prs, theme, raw)

    prs.save(str(out))
    return _json({
        "ok": True,
        "path": str(out),
        "slide_count": len(prs.slides),
        "template": theme.key,
        "theme": theme.badge,
        "visual_master": selected_visual_master,
        "visual_master_name": _pptx_visual_master_name(selected_visual_master),
        "visual_master_renderer": "native_v1",
    })


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

PPTX_WRITE_SCHEMA = {
    "name": "pptx_write",
    "description": (
        "Create a high-quality student-facing .pptx deck from structured slide content. "
        "Slides can use editable structured types such as agenda, claim_bullets, "
        "diagram, table, screenshot_placeholder, chart_placeholder, qa_backup, and closing. "
        "Templates apply distinct visual themes: course_report (blue classroom), "
        "paper_report (green academic), code_defense (indigo/orange tech defense). "
        "visual_master selects the prepared visual master when assets are available; "
        "otherwise pptx_write falls back to the editable native renderer."
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
    name="pptx_write",
    toolset="documents",
    schema=PPTX_WRITE_SCHEMA,
    handler=lambda args, **kw: pptx_write(
        path=args.get("path", ""),
        title=args.get("title", ""),
        slides=args.get("slides") or [],
        template=args.get("template", "course_report"),
        visual_master=args.get("visual_master", "default_native"),
    ),
    check_fn=lambda: True,
    emoji="📊",
)
