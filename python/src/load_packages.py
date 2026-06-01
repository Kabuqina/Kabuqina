# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Generic optional load-package registry for large on-demand assets."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import docling_math_models as dmm

StatusFn = Callable[[], dict[str, Any]]
DownloadFn = Callable[[], dict[str, Any]]
DeleteFn = Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class LoadPackage:
    id: str
    title: str
    description: str
    model_id: str
    size_mb: int
    feature: str
    status_fn: StatusFn
    download_fn: DownloadFn
    delete_fn: DeleteFn

    def status(self) -> dict[str, Any]:
        raw = self.status_fn()
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "feature": self.feature,
            "modelId": self.model_id,
            "sizeMb": self.size_mb,
            "downloaded": bool(raw.get("downloaded")),
            "size": int(raw.get("size") or 0),
            "path": str(raw.get("path") or ""),
        }


def _file_size(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except OSError:
        return 0


def _voice_helpers():
    """Load desk_server/voice_helpers.py without importing desk_server.__init__."""
    name = "_kabuqina_desk_voice_helpers"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    path = Path(__file__).resolve().parent / "desk_server" / "voice_helpers.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load voice_helpers from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _stt_status() -> dict[str, Any]:
    voice_helpers = _voice_helpers()
    path, downloaded = voice_helpers.desk_stt_model_resolved()
    return {
        "downloaded": downloaded,
        "size": _file_size(path) if downloaded else 0,
        "path": str(path),
    }


def _stt_download() -> dict[str, Any]:
    voice_helpers = _voice_helpers()
    path, downloaded = voice_helpers.desk_stt_model_resolved()
    if downloaded:
        return {
            "ok": True,
            "already": True,
            "size": _file_size(path),
            "path": str(path),
        }

    dest = voice_helpers.desk_stt_model_path()
    ok, info = voice_helpers.download_stt_model_blocking(dest)
    if not ok:
        detail = info.get("detail") or info.get("error") or "unknown"
        raise RuntimeError(str(detail))
    return {"ok": True, **info}


def _stt_delete() -> dict[str, Any]:
    voice_helpers = _voice_helpers()
    path, downloaded = voice_helpers.desk_stt_model_resolved()
    removed = False
    if downloaded and path.is_file():
        path.unlink()
        removed = True
    else:
        canonical = voice_helpers.desk_stt_model_path()
        if canonical.is_file():
            canonical.unlink()
            path = canonical
            removed = True
    return {"ok": True, "removed": removed, "path": str(path)}


def _formula_status() -> dict[str, Any]:
    return dmm.code_formula_status()


def _formula_download() -> dict[str, Any]:
    return dmm.download_code_formula_blocking()


def _formula_delete() -> dict[str, Any]:
    return dmm.delete_code_formula()


def _packages() -> dict[str, LoadPackage]:
    return {
        "docling-codeformula": LoadPackage(
            id="docling-codeformula",
            title="Docling CodeFormula",
            description="Formula extraction model for document_read_precise / pdf_read_precise mode=math.",
            feature="document-math",
            model_id=dmm.CODE_FORMULA_REPO,
            size_mb=dmm.CODE_FORMULA_SIZE_MB,
            status_fn=_formula_status,
            download_fn=_formula_download,
            delete_fn=_formula_delete,
        ),
        "local-stt-base-q5_1": LoadPackage(
            id="local-stt-base-q5_1",
            title="Local speech recognition",
            description="Whisper.cpp GGML model used by local voice transcription.",
            feature="voice-stt",
            model_id="ggerganov/whisper.cpp/ggml-base-q5_1.bin",
            size_mb=57,
            status_fn=_stt_status,
            download_fn=_stt_download,
            delete_fn=_stt_delete,
        ),
    }


def _get_package(package_id: str) -> LoadPackage:
    packages = _packages()
    try:
        return packages[package_id]
    except KeyError as exc:
        raise ValueError(f"unknown load package: {package_id}") from exc


def list_load_packages() -> list[dict[str, Any]]:
    return [_packages()[package_id].status() for package_id in sorted(_packages())]


def package_status(package_id: str) -> dict[str, Any]:
    return _get_package(package_id).status()


def download_package(package_id: str) -> dict[str, Any]:
    return _get_package(package_id).download_fn()


def delete_package(package_id: str) -> dict[str, Any]:
    return _get_package(package_id).delete_fn()


def ensure_package_available_with_approval(package_id: str, *, reason: str = "") -> dict[str, Any]:
    package = _get_package(package_id)
    status = package.status()
    if status["downloaded"]:
        return {"ok": True, "already": True, **status}

    from approval_backend import ApprovalBackend

    result = ApprovalBackend().ask_model_download(
        model_id=package.model_id,
        size_mb=package.size_mb,
        reason=reason or package.description,
    )
    if result != "once":
        raise PermissionError(f"User declined the {package.title} download.")

    downloaded = package.download_fn()
    return {"ok": True, **downloaded}
