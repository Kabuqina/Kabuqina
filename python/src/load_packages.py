# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Generic optional load-package registry for large on-demand assets."""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import docling_base_models as dbm
import docling_math_models as dmm

log = logging.getLogger("kabuqina.load_packages")

StatusFn = Callable[[], dict[str, Any]]
ProgressFn = Callable[[dict[str, Any]], None]
DownloadFn = Callable[[Optional[ProgressFn]], dict[str, Any]]
DeleteFn = Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class LoadPackageSource:
    id: str
    label: str
    url: str


@dataclass(frozen=True)
class LoadPackage:
    id: str
    title: str
    description: str
    model_id: str
    size_mb: int
    feature: str
    sources: tuple[LoadPackageSource, ...]
    status_fn: StatusFn
    download_fn: DownloadFn
    delete_fn: DeleteFn
    payload_folder: str = ""

    def status(self) -> dict[str, Any]:
        raw = self.status_fn()
        path_info = _status_path_info(self.id, raw, self.payload_folder)
        downloaded = bool(path_info["downloaded"])
        size = int(path_info.get("size") or raw.get("size") or 0)
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "feature": self.feature,
            "modelId": self.model_id,
            "sizeMb": self.size_mb,
            "downloaded": downloaded,
            "size": size,
            "path": str(path_info.get("realPath") or ""),
            "realPath": str(path_info.get("realPath") or ""),
            "agentPath": str(path_info.get("agentPath") or ""),
            "workspaceIndexPath": str(path_info.get("workspaceIndexPath") or ""),
            "source": str(path_info.get("source") or "missing"),
            "sources": [
                {"id": source.id, "label": source.label, "url": source.url}
                for source in self.sources
            ],
            "usedByCapabilities": _package_capability_usage().get(self.id, []),
            "job": _job_for_status(self.id, downloaded=downloaded, size=size),
        }


_JOB_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}

# Single serial download worker. All package downloads — onboarding self-heal,
# on-demand feature triggers, and manual Settings actions — flow through this one
# queue so at most one large asset downloads at a time (no bandwidth contention
# with chat or with each other). Historically each package spawned its own thread
# (parallel) and EasyOCR had a private resolver trigger; both are gone now.
_QUEUE_LOCK = threading.Lock()
_QUEUE_COND = threading.Condition(_QUEUE_LOCK)
_QUEUE: list["LoadPackage"] = []
_QUEUED_IDS: set[str] = set()
_ACTIVE_ID: Optional[str] = None
_WORKER: Optional[threading.Thread] = None


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _suppress_file() -> Path:
    return _data_dir() / "load-packages" / ".auto-skip.json"


def _load_suppressed() -> set[str]:
    try:
        data = json.loads(_suppress_file().read_text(encoding="utf-8"))
    except Exception:
        return set()
    return {str(item) for item in data} if isinstance(data, list) else set()


def _save_suppressed(ids: set[str]) -> None:
    path = _suppress_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sorted(ids)), encoding="utf-8")
    except OSError as exc:
        log.warning("failed to persist load-package auto-skip list: %s", exc)


def _add_suppressed(package_id: str) -> None:
    ids = _load_suppressed()
    if package_id not in ids:
        ids.add(package_id)
        _save_suppressed(ids)


def _clear_suppressed(package_id: str) -> None:
    ids = _load_suppressed()
    if package_id in ids:
        ids.discard(package_id)
        _save_suppressed(ids)


def _ensure_worker() -> None:
    global _WORKER
    if _WORKER is not None and _WORKER.is_alive():
        return
    _WORKER = threading.Thread(target=_download_worker, name="load-package-downloader", daemon=True)
    _WORKER.start()


def _download_worker() -> None:
    global _ACTIVE_ID
    while True:
        with _QUEUE_COND:
            while not _QUEUE:
                _QUEUE_COND.wait()
            package = _QUEUE.pop(0)
            _QUEUED_IDS.discard(package.id)
            _ACTIVE_ID = package.id
        try:
            status = package.status()
            if status["downloaded"]:
                size = int(status.get("size") or 0)
                _update_job(
                    package.id,
                    {"status": "done", "phase": "done", "downloadedBytes": size, "totalBytes": size, "error": ""},
                )
            else:
                _run_download(package)
        except Exception:
            log.exception("load-package download failed: %s", package.id)
        finally:
            with _QUEUE_COND:
                _ACTIVE_ID = None


def _enqueue(package: "LoadPackage") -> None:
    _ensure_worker()
    with _QUEUE_COND:
        if package.id == _ACTIVE_ID or package.id in _QUEUED_IDS:
            return
        _QUEUE.append(package)
        _QUEUED_IDS.add(package.id)
        _QUEUE_COND.notify()


def _data_dir() -> Path:
    raw = os.environ.get("HERMESDESK_DATA_DIR", "").strip()
    if raw:
        return Path(raw).expanduser()
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if local:
        return Path(local) / "com.kabuqina.app"
    return Path.home() / ".kabuqina"


def _bundle_dir() -> Path | None:
    raw = os.environ.get("HERMESDESK_BUNDLE_DIR", "").strip()
    return Path(raw).expanduser() if raw else None


def _workspace_root() -> Path | None:
    raw = (os.environ.get("HERMESDESK_WORKSPACE") or os.environ.get("HERMES_WORKSPACE") or "").strip()
    return Path(raw).expanduser() if raw else None


def _workspace_index_root() -> Path | None:
    workspace = _workspace_root()
    if workspace is None:
        return None
    return workspace / ".hermesdesk" / "load-packages"


def _agent_package_path(package_id: str) -> str:
    if _workspace_root() is None:
        return ""
    return f".hermesdesk/load-packages/{package_id}"


def user_package_root(package_id: str) -> Path:
    return _data_dir() / "load-packages" / package_id


def bundled_package_root(package_id: str) -> Path | None:
    bundle = _bundle_dir()
    if bundle is None:
        return None
    return bundle / "load-packages" / package_id


def _payload_present(path: Path) -> bool:
    if path.is_file():
        return True
    if not path.is_dir():
        return False
    return any(item.is_file() for item in path.rglob("*"))


def _path_size(path: Path) -> int:
    if path.is_file():
        return _file_size(path)
    if not path.is_dir():
        return 0
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += _file_size(item)
    return total


def resolve_package_payload(
    package_id: str,
    payload_folder: str,
    *,
    fallback: Path | None = None,
) -> dict[str, Any]:
    candidates: list[tuple[str, Path]] = [
        ("downloaded", user_package_root(package_id) / payload_folder),
    ]
    bundled = bundled_package_root(package_id)
    if bundled is not None:
        candidates.append(("bundled", bundled / payload_folder))
    if fallback is not None:
        candidates.append(("fallback", fallback))

    for source, path in candidates:
        if _payload_present(path):
            return {
                "source": source,
                "realPath": str(path),
                "downloaded": True,
                "size": _path_size(path),
            }

    missing = user_package_root(package_id) / payload_folder
    return {
        "source": "missing",
        "realPath": str(missing),
        "downloaded": False,
        "size": 0,
    }


def _status_path_info(
    package_id: str,
    raw: dict[str, Any],
    payload_folder: str,
) -> dict[str, Any]:
    raw_path = str(raw.get("path") or "").strip()
    if payload_folder:
        fallback = Path(raw_path) if raw_path else None
        resolved = resolve_package_payload(package_id, payload_folder, fallback=fallback)
    else:
        downloaded = bool(raw.get("downloaded"))
        resolved = {
            "downloaded": downloaded,
            "realPath": raw_path,
            "source": "downloaded" if downloaded else "missing",
            "size": int(raw.get("size") or 0),
        }

    index_root = _workspace_index_root()
    resolved["agentPath"] = _agent_package_path(package_id)
    resolved["workspaceIndexPath"] = str(index_root / package_id) if index_root is not None else ""
    return resolved


def _package_capability_usage() -> dict[str, list[dict[str, str]]]:
    try:
        from capability_registry import list_capability_defs
    except Exception:
        return {}

    usage: dict[str, list[dict[str, str]]] = {}
    for capability in list_capability_defs():
        refs = list(capability.get("required_load_packages") or [])
        refs.extend(list(capability.get("optional_load_packages") or []))
        for package_id in refs:
            usage.setdefault(str(package_id), []).append({
                "id": str(capability["id"]),
                "title": str(capability["title"]),
            })
    return {
        package_id: sorted(items, key=lambda item: item["title"])
        for package_id, items in usage.items()
    }


def _now() -> float:
    return time.time()


def _percent(downloaded: int, total: int) -> int | None:
    if total <= 0:
        return None
    return max(0, min(100, int(downloaded * 100 / total)))


def _base_job(package_id: str, *, status: str, phase: str) -> dict[str, Any]:
    ts = _now()
    return {
        "packageId": package_id,
        "status": status,
        "phase": phase,
        "downloadedBytes": 0,
        "totalBytes": 0,
        "percent": None,
        "source": "",
        "error": "",
        "startedAt": ts,
        "updatedAt": ts,
    }


def _update_job(package_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    with _JOB_LOCK:
        job = dict(_JOBS.get(package_id) or _base_job(package_id, status="running", phase="queued"))
        job.update(patch)
        downloaded = int(job.get("downloadedBytes") or 0)
        total = int(job.get("totalBytes") or 0)
        job["downloadedBytes"] = downloaded
        job["totalBytes"] = total
        job["percent"] = _percent(downloaded, total)
        job["updatedAt"] = _now()
        _JOBS[package_id] = job
        return dict(job)


def package_job_status(package_id: str) -> dict[str, Any] | None:
    with _JOB_LOCK:
        job = _JOBS.get(package_id)
        return dict(job) if job else None


def _job_for_status(package_id: str, *, downloaded: bool, size: int) -> dict[str, Any] | None:
    job = package_job_status(package_id)
    if (
        job
        and job.get("status") == "running"
        and downloaded
        and str(job.get("phase") or "") in {"checking", "installing", "done"}
    ):
        final_size = max(size, int(job.get("downloadedBytes") or 0), int(job.get("totalBytes") or 0))
        return _update_job(
            package_id,
            {
                "status": "done",
                "phase": "done",
                "downloadedBytes": final_size,
                "totalBytes": final_size,
                "error": "",
            },
        )
    return job


def _run_download(package: LoadPackage) -> dict[str, Any]:
    expected_total = int(package.size_mb) * 1024 * 1024
    _update_job(
        package.id,
        {
            "status": "running",
            "phase": "downloading",
            "totalBytes": expected_total,
            "error": "",
        },
    )

    def progress(patch: dict[str, Any]) -> None:
        _update_job(package.id, patch)

    try:
        result = package.download_fn(progress)
        final_size = int(result.get("size") or expected_total)
        _refresh_workspace_package_index_best_effort()
        _update_job(
            package.id,
            {
                "status": "done",
                "phase": "done",
                "downloadedBytes": final_size,
                "totalBytes": final_size,
                "error": "",
            },
        )
        return result
    except Exception as exc:
        _update_job(
            package.id,
            {
                "status": "error",
                "phase": "error",
                "error": str(exc),
            },
        )
        raise


def start_download_package(package_id: str) -> dict[str, Any]:
    # Resolve the package synchronously so any test/patched download_fn is
    # captured before the worker runs it on another thread.
    package = _get_package(package_id)
    # Any explicit intent to download clears a prior "user deleted this" mark.
    _clear_suppressed(package_id)
    status = package.status()
    if status["downloaded"]:
        _update_job(
            package.id,
            {
                "status": "done",
                "phase": "done",
                "downloadedBytes": int(status.get("size") or 0),
                "totalBytes": int(status.get("size") or 0),
                "error": "",
            },
        )
        return package.status()

    with _JOB_LOCK:
        current = _JOBS.get(package.id)
        if current and current.get("status") == "running":
            return package.status()
        _JOBS[package.id] = _base_job(package.id, status="running", phase="queued")

    # Serial: hand the package to the single background worker instead of
    # spawning a per-package thread. It stays "running/queued" until its turn.
    _enqueue(package)
    return package.status()


def start_auto_downloads() -> dict[str, Any]:
    """Enqueue every missing, non-suppressed package for background download.

    Called once at desk-server boot. Idempotent (already-present and
    already-running packages are skipped) so an interrupted download resumes on
    the next launch — this is what makes optional packages self-heal instead of
    being stranded when the one-shot onboarding batch was interrupted.
    """
    if _truthy_env("HERMESDESK_DISABLE_AUTO_LOAD_PACKAGES"):
        return {"ok": True, "disabled": True, "queued": []}

    suppressed = _load_suppressed()
    queued: list[str] = []
    for package_id in sorted(_packages()):
        if package_id in suppressed:
            continue
        try:
            if package_status(package_id)["downloaded"]:
                continue
            start_download_package(package_id)
        except Exception:
            log.exception("auto load-package download failed to start: %s", package_id)
            continue
        queued.append(package_id)
    if queued:
        log.info("auto load-package downloads queued (serial): %s", ", ".join(queued))
    return {"ok": True, "queued": queued}


def start_package_download_if_missing(package_id: str) -> dict[str, Any]:
    """Start a package download in the background unless it is already present."""
    status = package_status(package_id)
    if status["downloaded"]:
        return {"ok": True, "already": True, **status}
    started = start_download_package(package_id)
    return {"ok": True, "started": True, **started}


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


def _stt_download(progress: Optional[ProgressFn] = None) -> dict[str, Any]:
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
    if progress:
        progress({"phase": "downloading", "source": "kabuqina.com"})
    ok, info = voice_helpers.download_stt_model_blocking(dest)
    if not ok:
        detail = info.get("detail") or info.get("error") or "unknown"
        raise RuntimeError(str(detail))
    if progress:
        progress({"phase": "installing", "downloadedBytes": int(info.get("size") or 0)})
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


def _formula_download(progress: Optional[ProgressFn] = None) -> dict[str, Any]:
    return dmm.download_code_formula_blocking(progress=progress)


def _formula_delete() -> dict[str, Any]:
    return dmm.delete_code_formula()


def _docling_base_status() -> dict[str, Any]:
    return dbm.docling_base_status()


def _docling_base_download(progress: Optional[ProgressFn] = None) -> dict[str, Any]:
    return dbm.download_docling_base_blocking(progress=progress)


def _docling_base_delete() -> dict[str, Any]:
    return dbm.delete_docling_base()


def _eom():
    import easyocr_models as eom

    return eom


def _easyocr_status() -> dict[str, Any]:
    return _eom().easyocr_status()


def _easyocr_download(progress: Optional[ProgressFn] = None) -> dict[str, Any]:
    import easyocr_models as eom

    return eom.download_easyocr_blocking(progress=progress)


def _easyocr_delete() -> dict[str, Any]:
    import easyocr_models as eom

    return eom.delete_easyocr()


def _packages() -> dict[str, LoadPackage]:
    return {
        "docling-base": LoadPackage(
            id="docling-base",
            title="Docling base",
            description="Layout and table-recognition weights for precise document reading.",
            feature="document-precise-read",
            model_id=dbm.DOCLING_BASE_REPO,
            size_mb=dbm.DOCLING_BASE_SIZE_MB,
            sources=(
                LoadPackageSource(
                    id="tencent-cos",
                    label="Tencent COS",
                    url=dbm.DOCLING_BASE_ARCHIVE_URLS[0],
                ),
            ),
            status_fn=_docling_base_status,
            download_fn=_docling_base_download,
            delete_fn=_docling_base_delete,
            payload_folder=dbm.DOCLING_BASE_FOLDER,
        ),
        "docling-codeformula": LoadPackage(
            id="docling-codeformula",
            title="Docling CodeFormula",
            description="Formula extraction model for document_read_precise / pdf_read_precise mode=math.",
            feature="document-math",
            model_id=dmm.CODE_FORMULA_REPO,
            size_mb=dmm.CODE_FORMULA_SIZE_MB,
            sources=(
                LoadPackageSource(
                    id="tencent-cos",
                    label="Tencent COS",
                    url=dmm.KABUQINA_CODE_FORMULA_ARCHIVE_URLS[0],
                ),
                LoadPackageSource(
                    id="kabuqina-official",
                    label="Kabuqina official",
                    url=dmm.KABUQINA_CODE_FORMULA_BASE_URL,
                ),
                LoadPackageSource(id="hf-mirror", label="HF mirror", url="https://hf-mirror.com/ds4sd/CodeFormula"),
                LoadPackageSource(id="huggingface", label="HuggingFace", url="https://huggingface.co/ds4sd/CodeFormula"),
            ),
            status_fn=_formula_status,
            download_fn=_formula_download,
            delete_fn=_formula_delete,
            payload_folder=dmm.CODE_FORMULA_FOLDER,
        ),
        "easyocr": LoadPackage(
            id="easyocr",
            title="EasyOCR",
            description="Offline OCR weights for ocr_image and scanned-PDF text extraction.",
            feature="document-ocr",
            model_id=_eom().EASYOCR_MODEL_ID,
            size_mb=_eom().EASYOCR_SIZE_MB,
            sources=(
                LoadPackageSource(
                    id="tencent-cos",
                    label="Tencent COS",
                    url=_eom().EASYOCR_ARCHIVE_URLS[0],
                ),
            ),
            status_fn=_easyocr_status,
            download_fn=_easyocr_download,
            delete_fn=_easyocr_delete,
            payload_folder=_eom().EASYOCR_FOLDER,
        ),
        "local-stt-base-q5_1": LoadPackage(
            id="local-stt-base-q5_1",
            title="Local speech recognition",
            description="Whisper.cpp GGML model used by local voice transcription.",
            feature="voice-stt",
            model_id="ggerganov/whisper.cpp/ggml-base-q5_1.bin",
            size_mb=57,
            sources=(
                LoadPackageSource(
                    id="tencent-cos",
                    label="Tencent COS",
                    url="https://nanapackages-1428509047.cos.ap-guangzhou.myqcloud.com/ggml-base-q5_1.bin",
                ),
                LoadPackageSource(
                    id="kabuqina-official",
                    label="Kabuqina official",
                    url="https://kabuqina.com/packages/stt/ggml-base-q5_1.bin",
                ),
                LoadPackageSource(
                    id="hf-mirror",
                    label="HF mirror",
                    url="https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-base-q5_1.bin",
                ),
                LoadPackageSource(
                    id="huggingface",
                    label="HuggingFace",
                    url="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base-q5_1.bin",
                ),
            ),
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
    return _run_download(_get_package(package_id))


def delete_package(package_id: str) -> dict[str, Any]:
    result = _get_package(package_id).delete_fn()
    # Remember the explicit delete so boot self-heal does not silently
    # re-download it; a manual/Settings download later clears this.
    _add_suppressed(package_id)
    _refresh_workspace_package_index_best_effort()
    return result


def refresh_workspace_package_index() -> dict[str, Any]:
    root = _workspace_index_root()
    if root is None:
        return {"ok": False, "reason": "workspace_unavailable"}

    root.mkdir(parents=True, exist_ok=True)
    packages = list_load_packages()
    for package in packages:
        package_id = str(package["id"])
        package_dir = root / package_id
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "real-path.txt").write_text(
            str(package.get("realPath") or package.get("path") or ""),
            encoding="utf-8",
        )
        (root / f"{package_id}.json").write_text(
            json.dumps(package, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    (root / "packages.json").write_text(
        json.dumps({"version": 1, "packages": packages}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"ok": True, "path": str(root)}


def _refresh_workspace_package_index_best_effort() -> None:
    try:
        refresh_workspace_package_index()
    except Exception as exc:
        log.warning("Failed to refresh workspace load-package index: %s", exc)
