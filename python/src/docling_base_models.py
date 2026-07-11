# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""On-demand Docling base layout/table weights.

The base Docling package contains ``ds4sd--docling-models`` with layout and
TableFormer weights. It is not shipped in the installer by default; onboarding
starts a background load-package download, and Settings can retry/delete it.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen

log = logging.getLogger("kabuqina.docling_base")

ProgressFn = Callable[[dict[str, Any]], None]

DOCLING_BASE_PACKAGE_ID = "docling-base"
DOCLING_BASE_REPO = "ds4sd/docling-models"
DOCLING_BASE_FOLDER = "ds4sd--docling-models"
DOCLING_BASE_SIZE_MB = 506
DOCLING_BASE_ARCHIVE_URLS = (
    "https://nanapackages-1428509047.cos.ap-guangzhou.myqcloud.com/ds4sd--docling-models.zip",
)

DOCLING_BASE_SETTINGS_HINT = (
    "Download the Docling base pack (~506 MB) in Kabuqina Settings "
    "(Settings -> Load packages), then retry precise document reading."
)

_DOWNLOAD_CHUNK = 1024 * 1024


class DoclingBaseMissingError(RuntimeError):
    """Raised when Docling layout/table weights are not available locally."""


def _data_dir() -> Path:
    raw = os.environ.get("HERMESDESK_DATA_DIR", "").strip()
    if raw:
        return Path(raw).expanduser()
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if local:
        return Path(local) / "com.kabuqina.app"
    return Path.home() / ".kabuqina"


def _bundle_dir() -> Optional[Path]:
    raw = os.environ.get("HERMESDESK_BUNDLE_DIR", "").strip()
    return Path(raw).expanduser() if raw else None


def user_docling_base_root() -> Path:
    return _data_dir() / "load-packages" / DOCLING_BASE_PACKAGE_ID


def user_docling_base_dir() -> Path:
    return user_docling_base_root() / DOCLING_BASE_FOLDER


def bundled_docling_base_artifacts_dir() -> Optional[Path]:
    bundle = _bundle_dir()
    if bundle is None:
        return None
    return bundle / "docling-models"


def bundled_docling_base_dir() -> Optional[Path]:
    artifacts = bundled_docling_base_artifacts_dir()
    if artifacts is None:
        return None
    return artifacts / DOCLING_BASE_FOLDER


def _has_base_models(path: Optional[Path]) -> bool:
    if path is None or not path.is_dir():
        return False
    layout = path / "model_artifacts" / "layout" / "model.safetensors"
    table_fast = path / "model_artifacts" / "tableformer" / "fast" / "tableformer_fast.safetensors"
    return layout.is_file() and table_fast.is_file()


def docling_base_downloaded() -> bool:
    return _has_base_models(user_docling_base_dir())


def resolve_docling_base_dir() -> Optional[Path]:
    user = user_docling_base_dir()
    if _has_base_models(user):
        return user
    bundled = bundled_docling_base_dir()
    if _has_base_models(bundled):
        return bundled
    return None


def resolve_docling_base_artifacts_dir() -> Optional[Path]:
    user = user_docling_base_dir()
    if _has_base_models(user):
        return user_docling_base_root()
    bundled = bundled_docling_base_dir()
    if _has_base_models(bundled):
        return bundled_docling_base_artifacts_dir()
    return None


def docling_base_present() -> bool:
    return resolve_docling_base_dir() is not None


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


def docling_base_status() -> dict[str, Any]:
    path = resolve_docling_base_dir()
    downloaded = path is not None
    source = "missing"
    if path is not None:
        try:
            if path.resolve() == user_docling_base_dir().resolve():
                source = "downloaded"
            else:
                source = "bundled"
        except OSError:
            source = "downloaded" if str(path) == str(user_docling_base_dir()) else "bundled"
    return {
        "downloaded": downloaded,
        "size": _dir_size_bytes(path) if path else 0,
        "path": str(path or user_docling_base_dir()),
        "source": source,
        "sizeMb": DOCLING_BASE_SIZE_MB,
        "modelId": DOCLING_BASE_REPO,
    }


def require_docling_base() -> None:
    if docling_base_present():
        return
    raise DoclingBaseMissingError(
        "docling_base_model_missing: precise document reading requires "
        f"{DOCLING_BASE_REPO} (~{DOCLING_BASE_SIZE_MB} MB). {DOCLING_BASE_SETTINGS_HINT}"
    )


def _http_total_size(url: str) -> int:
    try:
        req = Request(url, method="HEAD", headers={"User-Agent": "Kabuqina/1.0"})
        with urlopen(req, timeout=60) as response:
            return int(response.headers.get("Content-Length") or 0)
    except Exception:
        return 0


def _download_archive(
    url: str,
    dest: Path,
    *,
    progress_cb: Optional[ProgressFn],
    max_attempts: int = 6,
) -> None:
    source = urlparse(url).netloc or url
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    total = _http_total_size(url)
    last_err: Optional[BaseException] = None

    for attempt in range(1, max_attempts + 1):
        have = part.stat().st_size if part.exists() else 0
        if total and have == total:
            break
        if total and have > total:
            part.unlink(missing_ok=True)
            have = 0

        headers = {"User-Agent": "Kabuqina/1.0"}
        if have:
            headers["Range"] = f"bytes={have}-"
        try:
            with urlopen(Request(url, headers=headers), timeout=900) as response:
                status = getattr(response, "status", 200) or 200
                mode = "ab"
                if have and status != 206:
                    have, mode = 0, "wb"
                if not total:
                    if status == 206:
                        content_range = response.headers.get("Content-Range") or ""
                        if "/" in content_range:
                            try:
                                total = int(content_range.rsplit("/", 1)[1])
                            except ValueError:
                                pass
                    else:
                        total = int(response.headers.get("Content-Length") or 0)
                with open(part, mode) as handle:
                    while True:
                        chunk = response.read(_DOWNLOAD_CHUNK)
                        if not chunk:
                            break
                        handle.write(chunk)
                        if progress_cb:
                            progress_cb({
                                "phase": "downloading",
                                "source": source,
                                "totalBytes": total or (DOCLING_BASE_SIZE_MB * 1024 * 1024),
                                "downloadedBytes": handle.tell(),
                            })
        except Exception as exc:
            last_err = exc
            log.warning("Docling base download attempt %d/%d failed (%s); resuming", attempt, max_attempts, exc)
            time.sleep(min(2.0 * attempt, 10.0))

    final_size = part.stat().st_size if part.exists() else 0
    if final_size == 0:
        raise last_err or RuntimeError("Docling base download produced an empty file")
    if total and final_size != total:
        raise last_err or RuntimeError(f"incomplete Docling base download: {final_size}/{total} bytes")
    os.replace(part, dest)


def _extract_archive(archive: Path, root: Path) -> None:
    extract_root = root / f"{DOCLING_BASE_FOLDER}.extracting"
    if extract_root.exists():
        shutil.rmtree(extract_root, ignore_errors=True)
    extract_root.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive) as zf:
            root_resolved = extract_root.resolve()
            for member in zf.infolist():
                target = (extract_root / member.filename).resolve()
                if root_resolved != target and root_resolved not in target.parents:
                    raise RuntimeError(f"unsafe archive member path: {member.filename}")
            zf.extractall(extract_root)

        payload = extract_root / DOCLING_BASE_FOLDER
        if not _has_base_models(payload):
            if _has_base_models(extract_root):
                payload = extract_root
            else:
                raise RuntimeError(f"archive extracted but Docling base weights missing under {extract_root}")

        final = root / DOCLING_BASE_FOLDER
        if final.exists():
            shutil.rmtree(final, ignore_errors=True)
        if payload == extract_root:
            final.mkdir(parents=True, exist_ok=True)
            for item in extract_root.iterdir():
                if item == final:
                    continue
                shutil.move(str(item), str(final / item.name))
        else:
            shutil.move(str(payload), str(final))
    finally:
        shutil.rmtree(extract_root, ignore_errors=True)


def invalidate_docling_converter_cache() -> None:
    try:
        from tools.document_tools import reset_docling_converter_cache

        reset_docling_converter_cache()
    except Exception:
        pass


def download_docling_base_blocking(progress: Optional[ProgressFn] = None) -> dict[str, Any]:
    if docling_base_downloaded():
        path = user_docling_base_dir()
        return {"ok": True, "already": True, "size": _dir_size_bytes(path), "path": str(path)}

    root = user_docling_base_root()
    root.mkdir(parents=True, exist_ok=True)
    archive = root / f"{DOCLING_BASE_FOLDER}.zip.tmp"

    last_err: Optional[BaseException] = None
    for url in DOCLING_BASE_ARCHIVE_URLS:
        try:
            log.info("Docling base download via %s", urlparse(url).netloc)
            _download_archive(url, archive, progress_cb=progress)
            if progress:
                progress({"phase": "installing", "downloadedBytes": archive.stat().st_size})
            _extract_archive(archive, root)
            if not _has_base_models(user_docling_base_dir()):
                raise RuntimeError(f"Docling base extracted but weights missing under {user_docling_base_dir()}")
            invalidate_docling_converter_cache()
            path = user_docling_base_dir()
            return {"ok": True, "size": _dir_size_bytes(path), "path": str(path)}
        except Exception as exc:
            last_err = exc
            log.warning("Docling base source %s failed: %s", urlparse(url).netloc, exc)
        finally:
            try:
                archive.unlink()
            except OSError:
                pass

    assert last_err is not None
    raise last_err


def delete_docling_base() -> dict[str, Any]:
    target = user_docling_base_dir()
    removed = False
    if target.is_dir():
        shutil.rmtree(target, ignore_errors=False)
        removed = True
    invalidate_docling_converter_cache()
    return {"ok": True, "removed": removed, "path": str(target)}
