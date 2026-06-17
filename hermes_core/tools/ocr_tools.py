"""Offline OCR tools backed by bundled EasyOCR models."""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from tools.registry import registry

logger = logging.getLogger(__name__)

_READER_LOCK = threading.Lock()
_READERS: Dict[Tuple[Tuple[str, ...], str, bool], Any] = {}


def _json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "tolist"):
        return _json_safe(value.tolist())
    if hasattr(value, "item"):
        return value.item()
    return value


def _detect_image_mime_type(image_path: Path) -> Optional[str]:
    with image_path.open("rb") as f:
        header = f.read(64)

    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if header.startswith(b"BM"):
        return "image/bmp"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    return None


def _normalize_languages(languages: Optional[Iterable[str]]) -> List[str]:
    normalized: List[str] = []
    for lang in languages or ["en"]:
        value = str(lang or "").strip().lower()
        if value and value not in normalized:
            normalized.append(value)
    return normalized or ["en"]


def _easyocr_dir_has_models(path: Path) -> bool:
    if not path.is_dir():
        return False
    return (path / "craft_mlt_25k.pth").is_file() and any(path.glob("*_g2.pth"))


def resolve_easyocr_model_dir() -> Optional[Path]:
    """Return the local EasyOCR model directory, never downloading models."""
    explicit = os.environ.get("HERMESDESK_EASYOCR_MODEL_DIR", "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        if _easyocr_dir_has_models(path):
            return path

    artifacts = os.environ.get("DOCLING_ARTIFACTS_PATH", "").strip()
    if artifacts:
        path = Path(artifacts).expanduser() / "EasyOcr"
        if _easyocr_dir_has_models(path):
            return path

    bundle_dir = os.environ.get("HERMESDESK_BUNDLE_DIR", "").strip()
    if bundle_dir:
        path = Path(bundle_dir).expanduser() / "docling-models" / "EasyOcr"
        if _easyocr_dir_has_models(path):
            return path

    try:
        from docling_math_models import resolve_docling_artifacts_path

        resolved = resolve_docling_artifacts_path(profile="fast")
        if resolved:
            path = Path(resolved) / "EasyOcr"
            if _easyocr_dir_has_models(path):
                return path
    except Exception:
        pass

    return None


def reset_easyocr_reader_cache() -> None:
    with _READER_LOCK:
        _READERS.clear()


def _get_easyocr_reader(languages: List[str], model_dir: Path, *, gpu: bool = False) -> Any:
    key = (tuple(languages), str(model_dir), bool(gpu))
    with _READER_LOCK:
        reader = _READERS.get(key)
        if reader is not None:
            return reader

        import easyocr  # type: ignore

        reader = easyocr.Reader(
            languages,
            gpu=gpu,
            model_storage_directory=str(model_dir),
            download_enabled=False,
        )
        _READERS[key] = reader
        return reader


def check_ocr_requirements() -> bool:
    return importlib.util.find_spec("easyocr") is not None and resolve_easyocr_model_dir() is not None


def ocr_image_tool(
    image_path: str,
    languages: Optional[Iterable[str]] = None,
    *,
    paragraph: bool = False,
) -> str:
    """Extract text from a local image using bundled EasyOCR models."""
    try:
        raw_path = str(image_path or "").strip()
        if raw_path.startswith("file://"):
            raw_path = raw_path[len("file://"):]
        path = Path(os.path.expanduser(raw_path))
        if not path.is_file():
            return _json({
                "success": False,
                "error_type": "file_not_found",
                "message": "Image file was not found.",
                "path": raw_path,
            })

        mime_type = _detect_image_mime_type(path)
        if not mime_type:
            return _json({
                "success": False,
                "error_type": "unsupported_image",
                "message": "Only real PNG, JPEG, GIF, BMP, or WebP image files are supported.",
                "path": str(path),
            })

        model_dir = resolve_easyocr_model_dir()
        if model_dir is None:
            return _json({
                "success": False,
                "error_type": "easyocr_models_missing",
                "message": (
                    "EasyOCR models were not found. Expected bundled models under "
                    "HERMESDESK_BUNDLE_DIR/docling-models/EasyOcr or set "
                    "HERMESDESK_EASYOCR_MODEL_DIR."
                ),
            })

        langs = _normalize_languages(languages)
        reader = _get_easyocr_reader(langs, model_dir, gpu=False)
        raw_lines = reader.readtext(str(path), detail=1, paragraph=bool(paragraph))

        lines = []
        text_parts = []
        for item in raw_lines or []:
            if len(item) < 2:
                continue
            bbox = item[0]
            text = str(item[1] or "")
            confidence = float(item[2]) if len(item) > 2 and item[2] is not None else None
            if text:
                text_parts.append(text)
            lines.append({
                "text": text,
                "confidence": confidence,
                "bbox": _json_safe(bbox),
            })

        return _json({
            "success": True,
            "engine": "easyocr",
            "languages": langs,
            "model_dir": str(model_dir),
            "path": str(path),
            "mime_type": mime_type,
            "text": "\n".join(text_parts),
            "lines": lines,
        })
    except Exception as exc:
        logger.error("OCR image failed: %s", exc, exc_info=True)
        return _json({
            "success": False,
            "error_type": "ocr_failed",
            "message": str(exc),
        })


OCR_IMAGE_SCHEMA = {
    "name": "ocr_image",
    "description": (
        "Extract visible text from a local image using offline EasyOCR. Use this "
        "for screenshots, scanned pages, error dialogs, labels, and other "
        "text-heavy images. Use vision_analyze instead when you need semantic "
        "image understanding beyond text extraction."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Local image file path or file:// URI to OCR.",
            },
            "languages": {
                "type": "array",
                "items": {"type": "string"},
                "description": "EasyOCR language codes. Default: ['en'].",
            },
            "paragraph": {
                "type": "boolean",
                "description": "Group nearby text into paragraphs. Default: false.",
            },
        },
        "required": ["image_path"],
    },
}


def _handle_ocr_image(args: Dict[str, Any], **kw: Any) -> str:
    return ocr_image_tool(
        args.get("image_path", ""),
        args.get("languages") or ["en"],
        paragraph=bool(args.get("paragraph", False)),
    )


registry.register(
    name="ocr_image",
    toolset="vision",
    schema=OCR_IMAGE_SCHEMA,
    handler=_handle_ocr_image,
    check_fn=check_ocr_requirements,
    emoji="OCR",
)
