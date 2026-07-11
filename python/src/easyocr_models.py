# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""On-demand EasyOCR weights for scanned-image / scanned-PDF OCR.

Mirrors the CodeFormula pattern (docling_math_models.py): the ~108 MB EasyOCR
weights are NOT shipped in the installer; they are downloaded from the Kabuqina
COS bucket via Settings -> Load packages, or auto-downloaded (with approval) the
first time OCR is used. When the weights ARE bundled (dev/offline builds), the
bundled copy is used and nothing is downloaded.

Layout matches what hermes ``tools/ocr_tools.py`` and ``tools/document_tools.py``
expect: a directory named ``EasyOcr`` containing ``craft_mlt_25k.pth`` plus the
``*_g2.pth`` recognizer weights.
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

log = logging.getLogger("kabuqina.easyocr")

ProgressFn = Callable[[dict[str, Any]], None]

EASYOCR_PACKAGE_ID = "easyocr"
EASYOCR_FOLDER = "EasyOcr"
EASYOCR_SIZE_MB = 108
EASYOCR_MODEL_ID = "JaidedAI/EasyOCR (craft + latin/english g2)"

# Single zip hosted on Tencent COS (same bucket as CodeFormula / STT). The zip
# contains a top-level ``EasyOcr/`` folder with the three weight files.
EASYOCR_ARCHIVE_URLS = (
    "https://nanapackages-1428509047.cos.ap-guangzhou.myqcloud.com/EasyOcr.zip",
)

EASYOCR_EXPECTED_FILES = ("craft_mlt_25k.pth", "english_g2.pth", "latin_g2.pth")

_DOWNLOAD_CHUNK = 1024 * 1024
EASYOCR_SETTINGS_HINT = (
    "Download the EasyOCR pack (~108 MB) in Kabuqina Settings "
    "(Settings -> Load packages), then retry OCR."
)


class EasyOcrMissingError(RuntimeError):
    """Raised when OCR is requested without EasyOCR weights on disk."""


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


def user_easyocr_root() -> Path:
    """Parent dir the archive extracts into (yields ``<root>/EasyOcr/``)."""
    try:
        from load_packages import user_package_root

        return user_package_root(EASYOCR_PACKAGE_ID)
    except Exception:
        return _data_dir() / "load-packages" / EASYOCR_PACKAGE_ID


def user_easyocr_dir() -> Path:
    return user_easyocr_root() / EASYOCR_FOLDER


def bundled_easyocr_dir() -> Optional[Path]:
    bundle = _bundle_dir()
    if bundle is None:
        return None
    return bundle / "docling-models" / EASYOCR_FOLDER


def _has_models(path: Optional[Path]) -> bool:
    if path is None or not path.is_dir():
        return False
    if not (path / "craft_mlt_25k.pth").is_file():
        return False
    return any(path.glob("*_g2.pth"))


def easyocr_downloaded() -> bool:
    """True when a user-downloaded copy exists (ignores the bundle)."""
    return _has_models(user_easyocr_dir())


def resolve_easyocr_dir() -> Optional[Path]:
    """Return the active EasyOCR dir: user download first, then bundle."""
    downloaded = user_easyocr_dir()
    if _has_models(downloaded):
        return downloaded
    bundled = bundled_easyocr_dir()
    if _has_models(bundled):
        return bundled
    return None


def easyocr_present() -> bool:
    return resolve_easyocr_dir() is not None


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


def easyocr_status() -> dict[str, Any]:
    path = resolve_easyocr_dir()
    downloaded = path is not None
    return {
        "downloaded": downloaded,
        "size": _dir_size_bytes(path) if path else 0,
        "path": str(path or user_easyocr_dir()),
        "sizeMb": EASYOCR_SIZE_MB,
        "modelId": EASYOCR_MODEL_ID,
    }


def _http_total_size(url: str) -> int:
    """Best-effort total size via HEAD; 0 when the server doesn't say."""
    try:
        req = Request(url, method="HEAD", headers={"User-Agent": "Kabuqina/1.0"})
        with urlopen(req, timeout=60) as r:
            return int(r.headers.get("Content-Length") or 0)
    except Exception:
        return 0


def _download_archive(
    url: str,
    dest: Path,
    *,
    progress_cb: Optional[ProgressFn],
    max_attempts: int = 6,
) -> None:
    """Download to ``dest`` with HTTP Range resume + retry.

    COS large transfers occasionally drop ~1 MB short of Content-Length
    (IncompleteRead) or truncate silently. We keep a ``.part`` file and resume
    from the current offset on each attempt, and only succeed when the byte
    count matches the server-reported total.
    """
    source = urlparse(url).netloc or url
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    total = _http_total_size(url)
    last_err: Optional[BaseException] = None

    for attempt in range(1, max_attempts + 1):
        have = part.stat().st_size if part.exists() else 0
        if total and have == total:
            break
        if total and have > total:  # corrupt partial — restart
            part.unlink(missing_ok=True)
            have = 0

        headers = {"User-Agent": "Kabuqina/1.0"}
        if have:
            headers["Range"] = f"bytes={have}-"
        try:
            with urlopen(Request(url, headers=headers), timeout=600) as r:
                status = getattr(r, "status", 200) or 200
                mode = "ab"
                if have and status != 206:  # server ignored Range — start over
                    have, mode = 0, "wb"
                if not total:
                    if status == 206:
                        cr = r.headers.get("Content-Range") or ""
                        if "/" in cr:
                            try:
                                total = int(cr.rsplit("/", 1)[1])
                            except ValueError:
                                pass
                    else:
                        total = int(r.headers.get("Content-Length") or 0)
                with open(part, mode) as fh:
                    while True:
                        chunk = r.read(_DOWNLOAD_CHUNK)
                        if not chunk:
                            break
                        fh.write(chunk)
                        if progress_cb:
                            progress_cb({
                                "phase": "downloading",
                                "source": source,
                                "totalBytes": total or (EASYOCR_SIZE_MB * 1024 * 1024),
                                "downloadedBytes": fh.tell(),
                            })
        except Exception as exc:  # noqa: BLE001 - keep partial, resume next loop
            last_err = exc
            log.warning("EasyOCR download attempt %d/%d failed (%s); resuming…", attempt, max_attempts, exc)
            time.sleep(min(2.0 * attempt, 10.0))

    final = part.stat().st_size if part.exists() else 0
    if final == 0:
        raise last_err or RuntimeError("EasyOCR download produced an empty file")
    if total and final != total:
        raise last_err or RuntimeError(f"incomplete EasyOCR download: {final}/{total} bytes")
    os.replace(part, dest)


def _extract_archive(archive: Path, root: Path) -> None:
    """Safely extract the COS zip so weights land at ``root/EasyOcr/``."""
    extract_root = root / f"{EASYOCR_FOLDER}.extracting"
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

        payload = extract_root / EASYOCR_FOLDER
        if not _has_models(payload):
            # Archive may have the weights at its root instead of under EasyOcr/.
            if _has_models(extract_root):
                payload = extract_root
            else:
                raise RuntimeError(f"archive extracted but EasyOCR weights missing under {extract_root}")

        final = root / EASYOCR_FOLDER
        if final.exists():
            shutil.rmtree(final, ignore_errors=True)
        if payload == extract_root:
            final.mkdir(parents=True, exist_ok=True)
            for name in EASYOCR_EXPECTED_FILES:
                src = extract_root / name
                if src.is_file():
                    shutil.move(str(src), str(final / name))
        else:
            shutil.move(str(payload), str(final))
    finally:
        shutil.rmtree(extract_root, ignore_errors=True)


def download_easyocr_blocking(progress: Optional[ProgressFn] = None) -> dict[str, Any]:
    """Download + verify + extract EasyOCR into the user package dir."""
    if easyocr_downloaded():
        path = user_easyocr_dir()
        return {"ok": True, "already": True, "size": _dir_size_bytes(path), "path": str(path)}

    root = user_easyocr_root()
    root.mkdir(parents=True, exist_ok=True)
    archive = root / f"{EASYOCR_FOLDER}.zip.tmp"

    last_err: Optional[BaseException] = None
    for url in EASYOCR_ARCHIVE_URLS:
        try:
            log.info("EasyOCR download via %s", urlparse(url).netloc)
            _download_archive(url, archive, progress_cb=progress)
            if progress:
                progress({"phase": "installing", "downloadedBytes": archive.stat().st_size})
            _extract_archive(archive, root)
            if not _has_models(user_easyocr_dir()):
                raise RuntimeError(f"EasyOCR extracted but weights missing under {user_easyocr_dir()}")
            _invalidate_caches()
            path = user_easyocr_dir()
            return {"ok": True, "size": _dir_size_bytes(path), "path": str(path)}
        except Exception as exc:  # noqa: BLE001 - try next mirror
            last_err = exc
            log.warning("EasyOCR source %s failed: %s", urlparse(url).netloc, exc)
        finally:
            try:
                archive.unlink()
            except OSError:
                pass

    assert last_err is not None
    raise last_err


def delete_easyocr() -> dict[str, Any]:
    target = user_easyocr_dir()
    removed = False
    if target.is_dir():
        shutil.rmtree(target, ignore_errors=False)
        removed = True
    _invalidate_caches()
    return {"ok": True, "removed": removed, "path": str(target)}


def _invalidate_caches() -> None:
    # Drop cached docling converter + EasyOCR readers so the new weights are seen.
    try:
        from docling_math_models import invalidate_docling_converter_cache

        invalidate_docling_converter_cache()
    except Exception:
        pass
    try:
        from tools.ocr_tools import reset_easyocr_reader_cache

        reset_easyocr_reader_cache()
    except Exception:
        pass


def ensure_easyocr_available(*, reason: str = "") -> dict[str, Any]:
    """Start the EasyOCR background download when OCR first needs it."""
    if easyocr_present():
        return {"ok": True, "already": True, **easyocr_status()}

    try:
        from load_packages import start_package_download_if_missing
    except ImportError as exc:
        raise EasyOcrMissingError(
            f"easyocr_models_missing: OCR requires the EasyOCR pack "
            f"(~{EASYOCR_SIZE_MB} MB). {EASYOCR_SETTINGS_HINT}"
        ) from exc

    try:
        start_package_download_if_missing(EASYOCR_PACKAGE_ID)
    except Exception as exc:
        raise EasyOcrMissingError(
            f"easyocr_models_missing: OCR requires the EasyOCR pack (~{EASYOCR_SIZE_MB} MB), "
            f"but the background download could not start: {exc}. {EASYOCR_SETTINGS_HINT}"
        ) from exc

    raise EasyOcrMissingError(
        f"easyocr_models_missing: OCR requires the EasyOCR pack (~{EASYOCR_SIZE_MB} MB). "
        f"The pack is downloading in the background; retry after it finishes, "
        f"or check {EASYOCR_SETTINGS_HINT}"
        )
