# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""On-demand Docling CodeFormula weights for ``mode=math`` (not shipped in MSI).

Layout/table stay in the runtime bundle; formula enrichment (~500 MB) is managed
from Kabuqina Settings (manual download/delete). Agent reads fail fast with a
clear ``docling_error`` when the pack is missing — no silent pypdf fallback.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

log = logging.getLogger("hermesdesk.docling_math")

CODE_FORMULA_REPO = "ds4sd/CodeFormula"
CODE_FORMULA_FOLDER = "ds4sd--CodeFormula"
CODE_FORMULA_REVISION = "v1.0.2"
CODE_FORMULA_SIZE_MB = 500

CODE_FORMULA_SETTINGS_HINT = (
    "Download the optional CodeFormula pack (~500 MB) in Kabuqina Settings "
    "(Settings → Load packages), then retry mode=math."
)

DEFAULT_HF_ENDPOINTS = (
    "https://hf-mirror.com",
    "https://huggingface.co",
)


class CodeFormulaMissingError(RuntimeError):
    """Raised when ``mode=math`` is requested without CodeFormula on disk."""


def _truthy(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).strip().lower() not in ("0", "false", "no", "off")


def desktop_data_dir() -> Path:
    raw = os.environ.get("HERMESDESK_DATA_DIR", "").strip()
    if raw:
        return Path(raw).expanduser()
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if local:
        return Path(local) / "com.kabuqina.app"
    return Path.home() / ".kabuqina"


def bundle_docling_models_dir() -> Optional[Path]:
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


def user_formula_dir() -> Path:
    return desktop_data_dir() / "docling-models" / CODE_FORMULA_FOLDER


def huggingface_cache_dir() -> Path:
    return desktop_data_dir() / "huggingface-cache"


def merged_artifacts_dir() -> Path:
    return desktop_data_dir() / "docling-artifacts"


def code_formula_present(formula_dir: Optional[Path] = None) -> bool:
    target = formula_dir or user_formula_dir()
    if not target.is_dir():
        return False
    return any(target.rglob("*.safetensors")) or any(target.rglob("*.bin"))


def _dir_size_bytes(path: Path) -> int:
    if not path.is_dir():
        return 0
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                pass
    return total


def code_formula_status() -> dict[str, Any]:
    path = user_formula_dir()
    downloaded = code_formula_present(path)
    return {
        "downloaded": downloaded,
        "size": _dir_size_bytes(path) if downloaded else 0,
        "path": str(path),
        "sizeMb": CODE_FORMULA_SIZE_MB,
        "modelId": CODE_FORMULA_REPO,
    }


def require_code_formula() -> None:
    """Fail fast when CodeFormula is missing; agent should surface settings hint."""
    if code_formula_present():
        return
    raise CodeFormulaMissingError(
        "code_formula_model_missing: mode=math requires ds4sd/CodeFormula "
        f"(~{CODE_FORMULA_SIZE_MB} MB). {CODE_FORMULA_SETTINGS_HINT}"
    )


def ensure_code_formula_available_for_math() -> None:
    """Ask once, then download CodeFormula when ``mode=math`` first needs it."""
    if code_formula_present():
        return

    try:
        from load_packages import ensure_package_available_with_approval
    except ImportError as exc:
        raise CodeFormulaMissingError(
            "code_formula_model_missing: mode=math requires ds4sd/CodeFormula "
            f"(~{CODE_FORMULA_SIZE_MB} MB). {CODE_FORMULA_SETTINGS_HINT}"
        ) from exc

    ensure_package_available_with_approval(
        "docling-codeformula",
        reason=(
            "Kabuqina needs the optional Docling CodeFormula pack to extract "
            "formulas from this document with mode=math."
        ),
    )
    if not code_formula_present():
        raise CodeFormulaMissingError(
            "code_formula_model_missing: CodeFormula download completed but "
            f"weights were not found. {CODE_FORMULA_SETTINGS_HINT}"
        )


def invalidate_docling_converter_cache() -> None:
    try:
        from tools.document_tools import reset_docling_converter_cache

        reset_docling_converter_cache()
    except ImportError:
        pass


def _ensure_dir_junction(link: Path, target: Path) -> None:
    if link.exists():
        return
    if not target.is_dir():
        raise FileNotFoundError(f"junction target missing: {target}")
    link.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target.resolve())],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"failed to link {link.name} -> {target}: "
                f"{(result.stderr or result.stdout or '').strip()}"
            )
    else:
        os.symlink(target.resolve(), link, target_is_directory=True)


def _remove_junction(link: Path) -> None:
    if not link.exists():
        return
    try:
        if sys.platform == "win32":
            subprocess.run(["cmd", "/c", "rmdir", str(link)], check=False)
        else:
            link.unlink()
    except OSError:
        pass


def _materialize_merged_artifacts() -> Optional[Path]:
    bundle = bundle_docling_models_dir()
    if bundle is None:
        return None
    merged = merged_artifacts_dir()
    merged.mkdir(parents=True, exist_ok=True)

    layout_src = bundle / "ds4sd--docling-models"
    if layout_src.is_dir():
        _ensure_dir_junction(merged / "ds4sd--docling-models", layout_src)

    easyocr_src = bundle / "EasyOcr"
    if easyocr_src.is_dir():
        _ensure_dir_junction(merged / "EasyOcr", easyocr_src)

    formula_src = user_formula_dir()
    if code_formula_present(formula_src):
        _ensure_dir_junction(merged / CODE_FORMULA_FOLDER, formula_src)
    else:
        bundled_formula = bundle / CODE_FORMULA_FOLDER
        if code_formula_present(bundled_formula):
            _ensure_dir_junction(merged / CODE_FORMULA_FOLDER, bundled_formula)

    return merged


def _refresh_formula_junction() -> None:
    formula_link = merged_artifacts_dir() / CODE_FORMULA_FOLDER
    _remove_junction(formula_link)
    _materialize_merged_artifacts()


def resolve_docling_artifacts_path(*, profile: str = "fast") -> Optional[Path]:
    """Return Docling ``artifacts_path`` for the given converter profile."""
    if profile == "math":
        merged = _materialize_merged_artifacts()
        if merged is not None and code_formula_present(merged / CODE_FORMULA_FOLDER):
            return merged
        return None
    return bundle_docling_models_dir()


def _hf_endpoint_candidates() -> list[str]:
    ordered: list[str] = []
    custom = os.environ.get("HF_ENDPOINT", "").strip().rstrip("/")
    if custom:
        ordered.append(custom)
    for endpoint in DEFAULT_HF_ENDPOINTS:
        if endpoint not in ordered:
            ordered.append(endpoint)
    if not _truthy("DOCLING_HF_DIRECT_FALLBACK", "1"):
        direct = "https://huggingface.co"
        if direct in ordered and (not custom or custom != direct):
            ordered = [e for e in ordered if e != direct]
    return ordered


def _download_code_formula(local_dir: Path, *, progress: bool = True) -> None:
    from huggingface_hub import snapshot_download
    from huggingface_hub.utils import disable_progress_bars

    if not progress:
        disable_progress_bars()

    retries = max(1, int(os.environ.get("DOCLING_HF_RETRIES", "5")))
    max_workers = max(1, int(os.environ.get("DOCLING_HF_MAX_WORKERS", "1")))
    local_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = huggingface_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    last_err: Optional[BaseException] = None
    prev_endpoint = os.environ.get("HF_ENDPOINT")

    try:
        for endpoint in _hf_endpoint_candidates():
            os.environ["HF_ENDPOINT"] = endpoint
            host = urlparse(endpoint).netloc or endpoint
            log.info("CodeFormula download via %s", host)
            for attempt in range(1, retries + 1):
                try:
                    snapshot_download(
                        repo_id=CODE_FORMULA_REPO,
                        revision=CODE_FORMULA_REVISION,
                        local_dir=str(local_dir),
                        cache_dir=str(cache_dir),
                        resume_download=True,
                        max_workers=max_workers,
                    )
                    if code_formula_present(local_dir):
                        return
                    raise RuntimeError(f"download finished but weights missing under {local_dir}")
                except Exception as exc:
                    last_err = exc
                    if attempt < retries:
                        delay = min(2.0 * attempt, 30.0)
                        log.warning(
                            "CodeFormula download failed (%s), retry in %.0fs: %s",
                            type(exc).__name__,
                            delay,
                            exc,
                        )
                        time.sleep(delay)
    finally:
        if prev_endpoint is not None:
            os.environ["HF_ENDPOINT"] = prev_endpoint
        else:
            os.environ.pop("HF_ENDPOINT", None)

    assert last_err is not None
    raise last_err


def download_code_formula_blocking() -> dict[str, Any]:
    """Download CodeFormula to the user profile (Settings action)."""
    dest = user_formula_dir()
    if code_formula_present(dest):
        return {
            "ok": True,
            "already": True,
            "size": _dir_size_bytes(dest),
            "path": str(dest),
        }

    log.info("Downloading CodeFormula to %s", dest)
    _download_code_formula(dest, progress=True)
    if not code_formula_present(dest):
        raise RuntimeError(f"CodeFormula download finished but weights are missing under {dest}")

    _refresh_formula_junction()
    invalidate_docling_converter_cache()
    return {
        "ok": True,
        "size": _dir_size_bytes(dest),
        "path": str(dest),
    }


def delete_code_formula() -> dict[str, Any]:
    """Remove downloaded CodeFormula weights and refresh Docling junctions."""
    dest = user_formula_dir()
    removed = False
    if dest.is_dir():
        shutil.rmtree(dest, ignore_errors=False)
        removed = True

    formula_link = merged_artifacts_dir() / CODE_FORMULA_FOLDER
    _remove_junction(formula_link)
    _materialize_merged_artifacts()
    invalidate_docling_converter_cache()
    return {"ok": True, "removed": removed, "path": str(dest)}
