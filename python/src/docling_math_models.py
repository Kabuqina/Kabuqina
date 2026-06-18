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
import threading
import time
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen

log = logging.getLogger("hermesdesk.docling_math")

ProgressFn = Callable[[dict[str, Any]], None]

CODE_FORMULA_REPO = "ds4sd/CodeFormula"
CODE_FORMULA_FOLDER = "ds4sd--CodeFormula"
CODE_FORMULA_REVISION = "v1.0.2"
CODE_FORMULA_SIZE_MB = 500
KABUQINA_CODE_FORMULA_BASE_URL = "https://kabuqina.com/packages/codeformula/"
KABUQINA_CODE_FORMULA_URL = urljoin(KABUQINA_CODE_FORMULA_BASE_URL, f"{CODE_FORMULA_FOLDER}/")
KABUQINA_CODE_FORMULA_ARCHIVE_URLS = (
    "https://nanapackages-1428509047.cos.ap-guangzhou.myqcloud.com/ds4sd--CodeFormula.zip",
)

CODE_FORMULA_SETTINGS_HINT = (
    "Download the optional CodeFormula pack (~500 MB) in Kabuqina Settings "
    "(Settings → Load packages), then retry mode=math."
)

DEFAULT_HF_ENDPOINTS = (
    "https://hf-mirror.com",
    "https://huggingface.co",
)

STATIC_DOWNLOAD_CHUNK_SIZE = 1024 * 1024


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
    try:
        from load_packages import user_package_root

        return user_package_root("docling-codeformula") / CODE_FORMULA_FOLDER
    except Exception:
        return desktop_data_dir() / "load-packages" / "docling-codeformula" / CODE_FORMULA_FOLDER


def _legacy_formula_dir() -> Path:
    return desktop_data_dir() / "docling-models" / CODE_FORMULA_FOLDER


def huggingface_cache_dir() -> Path:
    return desktop_data_dir() / "huggingface-cache"


def merged_artifacts_dir() -> Path:
    return desktop_data_dir() / "docling-artifacts"


def code_formula_present(formula_dir: Optional[Path] = None) -> bool:
    if formula_dir is None:
        return _code_formula_present_at(user_formula_dir()) or _code_formula_present_at(_legacy_formula_dir())
    return _code_formula_present_at(formula_dir)


def _code_formula_present_at(formula_dir: Path) -> bool:
    target = formula_dir or user_formula_dir()
    if not target.is_dir():
        return False
    return any(target.rglob("*.safetensors")) or any(target.rglob("*.bin"))


def _active_formula_dir() -> Path:
    primary = user_formula_dir()
    if _code_formula_present_at(primary):
        return primary
    legacy = _legacy_formula_dir()
    if _code_formula_present_at(legacy):
        return legacy
    return primary


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
    path = _active_formula_dir()
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

    # EasyOCR may be bundled (offline build) or downloaded as a load-package.
    easyocr_src: Optional[Path] = None
    try:
        from easyocr_models import resolve_easyocr_dir

        easyocr_src = resolve_easyocr_dir()
    except Exception:
        easyocr_src = None
    if easyocr_src is None:
        fallback = bundle / "EasyOcr"
        easyocr_src = fallback if fallback.is_dir() else None
    if easyocr_src is not None and easyocr_src.is_dir():
        _ensure_dir_junction(merged / "EasyOcr", easyocr_src)

    formula_src = user_formula_dir()
    if code_formula_present(formula_src):
        _ensure_dir_junction(merged / CODE_FORMULA_FOLDER, formula_src)
    else:
        legacy_formula = _legacy_formula_dir()
        if code_formula_present(legacy_formula):
            _ensure_dir_junction(merged / CODE_FORMULA_FOLDER, legacy_formula)
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

    # fast / default
    bundle = bundle_docling_models_dir()
    if bundle is not None and (bundle / "EasyOcr").is_dir():
        # Fully bundled (EasyOCR present): unchanged behavior.
        return bundle
    # EasyOCR was unbundled but the user downloaded it -> expose a merged dir so
    # ocr_image / docling OCR find layout/table (bundle) + EasyOcr (download).
    try:
        from easyocr_models import easyocr_downloaded

        if easyocr_downloaded():
            merged = _materialize_merged_artifacts()
            if merged is not None:
                return merged
    except Exception:
        pass
    return bundle


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


class _HrefParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.hrefs.append(value)


def _static_directory_entries(index_url: str) -> list[tuple[str, str, bool]]:
    request = Request(index_url, headers={"User-Agent": "Kabuqina/1.0"})
    with urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")

    parser = _HrefParser()
    parser.feed(html)
    base = urlparse(index_url)
    entries: list[tuple[str, str, bool]] = []
    seen: set[tuple[str, str]] = set()

    for href in parser.hrefs:
        href = href.strip()
        if not href or href.startswith("#") or href.startswith("?"):
            continue
        full_url = urljoin(index_url, href)
        parsed = urlparse(full_url)
        if parsed.scheme != base.scheme or parsed.netloc != base.netloc:
            continue
        if not parsed.path.startswith(base.path):
            continue
        if parsed.query or parsed.fragment:
            continue
        is_dir = parsed.path.endswith("/")
        name = unquote(parsed.path.rstrip("/").rsplit("/", 1)[-1])
        if name in ("", ".", ".."):
            continue
        key = (full_url, name)
        if key in seen:
            continue
        seen.add(key)
        entries.append((name, full_url, is_dir))
    return entries


def _download_static_file(url: str, dest: Path, *, root: Path, progress_cb: Optional[ProgressFn], source: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    request = Request(url, headers={"User-Agent": "Kabuqina/1.0"})
    try:
        with urlopen(request, timeout=600) as response:
            with open(tmp, "wb") as handle:
                while True:
                    chunk = response.read(STATIC_DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    handle.write(chunk)
                    if progress_cb:
                        progress_cb({
                            "phase": "downloading",
                            "source": source,
                            "totalBytes": CODE_FORMULA_SIZE_MB * 1024 * 1024,
                            "downloadedBytes": _dir_size_bytes(root),
                        })
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass
        os.replace(tmp, dest)
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def _download_static_tree(index_url: str, local_dir: Path, *, root: Path, progress_cb: Optional[ProgressFn], source: str) -> None:
    local_dir.mkdir(parents=True, exist_ok=True)
    entries = _static_directory_entries(index_url)
    if not entries:
        raise RuntimeError(f"no downloadable entries found at {index_url}")

    for name, full_url, is_dir in entries:
        target = local_dir / name
        if is_dir:
            _download_static_tree(full_url, target, root=root, progress_cb=progress_cb, source=source)
        else:
            _download_static_file(full_url, target, root=root, progress_cb=progress_cb, source=source)


def _download_static_code_formula(local_dir: Path, *, progress_cb: Optional[ProgressFn] = None) -> None:
    source = urlparse(KABUQINA_CODE_FORMULA_BASE_URL).netloc or "kabuqina.com"
    if progress_cb:
        progress_cb({
            "phase": "downloading",
            "source": source,
            "totalBytes": CODE_FORMULA_SIZE_MB * 1024 * 1024,
            "downloadedBytes": _dir_size_bytes(local_dir),
        })
    _download_static_tree(KABUQINA_CODE_FORMULA_URL, local_dir, root=local_dir, progress_cb=progress_cb, source=source)
    if not code_formula_present(local_dir):
        raise RuntimeError(f"download finished but weights missing under {local_dir}")


def _download_code_formula_archive(url: str, local_dir: Path, *, progress_cb: Optional[ProgressFn] = None) -> None:
    source = urlparse(url).netloc or url
    local_dir.mkdir(parents=True, exist_ok=True)
    archive = local_dir.parent / f"{CODE_FORMULA_FOLDER}.zip.tmp"
    request = Request(url, headers={"User-Agent": "Kabuqina/1.0"})
    downloaded = 0
    try:
        if progress_cb:
            progress_cb({
                "phase": "downloading",
                "source": source,
                "totalBytes": CODE_FORMULA_SIZE_MB * 1024 * 1024,
                "downloadedBytes": _dir_size_bytes(local_dir),
            })
        with urlopen(request, timeout=600) as response:
            with open(archive, "wb") as handle:
                while True:
                    chunk = response.read(STATIC_DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb:
                        progress_cb({
                            "phase": "downloading",
                            "source": source,
                            "totalBytes": CODE_FORMULA_SIZE_MB * 1024 * 1024,
                            "downloadedBytes": downloaded,
                        })
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass

        extract_root = local_dir.parent / f"{CODE_FORMULA_FOLDER}.extracting"
        if extract_root.exists():
            shutil.rmtree(extract_root, ignore_errors=True)
        extract_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as zf:
            root_resolved = extract_root.resolve()
            for member in zf.infolist():
                target = (extract_root / member.filename).resolve()
                if root_resolved != target and root_resolved not in target.parents:
                    raise RuntimeError(f"unsafe archive member path: {member.filename}")
                zf.extract(member, extract_root)

        payload = extract_root / CODE_FORMULA_FOLDER
        if not payload.is_dir():
            payload = extract_root
        if local_dir.exists():
            shutil.rmtree(local_dir, ignore_errors=True)
        shutil.move(str(payload), str(local_dir))
        if extract_root.exists():
            shutil.rmtree(extract_root, ignore_errors=True)

        if not code_formula_present(local_dir):
            raise RuntimeError(f"archive download finished but weights missing under {local_dir}")
    finally:
        try:
            archive.unlink()
        except OSError:
            pass
        try:
            shutil.rmtree(local_dir.parent / f"{CODE_FORMULA_FOLDER}.extracting", ignore_errors=True)
        except OSError:
            pass


def _download_code_formula(local_dir: Path, *, progress: bool = True, progress_cb: Optional[ProgressFn] = None) -> None:
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
        if _truthy("DOCLING_CODEFORMULA_OFFICIAL_FIRST", "1"):
            for archive_url in KABUQINA_CODE_FORMULA_ARCHIVE_URLS:
                try:
                    log.info("CodeFormula download via %s", urlparse(archive_url).netloc)
                    _download_code_formula_archive(archive_url, local_dir, progress_cb=progress_cb)
                    if code_formula_present(local_dir):
                        if progress_cb:
                            progress_cb({
                                "phase": "checking",
                                "source": urlparse(archive_url).netloc,
                                "downloadedBytes": _dir_size_bytes(local_dir),
                            })
                        return
                except Exception as exc:
                    last_err = exc
                    log.warning("CodeFormula archive source failed, falling back: %s", exc)

            try:
                log.info("CodeFormula download via %s", urlparse(KABUQINA_CODE_FORMULA_BASE_URL).netloc)
                _download_static_code_formula(local_dir, progress_cb=progress_cb)
                if code_formula_present(local_dir):
                    if progress_cb:
                        progress_cb({
                            "phase": "checking",
                            "source": urlparse(KABUQINA_CODE_FORMULA_BASE_URL).netloc,
                            "downloadedBytes": _dir_size_bytes(local_dir),
                        })
                    return
            except Exception as exc:
                last_err = exc
                log.warning("CodeFormula official source failed, falling back to HF: %s", exc)

        for endpoint in _hf_endpoint_candidates():
            os.environ["HF_ENDPOINT"] = endpoint
            host = urlparse(endpoint).netloc or endpoint
            log.info("CodeFormula download via %s", host)
            if progress_cb:
                progress_cb({
                    "phase": "downloading",
                    "source": host,
                    "totalBytes": CODE_FORMULA_SIZE_MB * 1024 * 1024,
                    "downloadedBytes": _dir_size_bytes(local_dir),
                })
            for attempt in range(1, retries + 1):
                try:
                    stop_monitor = threading.Event()
                    monitor: Optional[threading.Thread] = None
                    if progress_cb:
                        def _monitor_download_dir() -> None:
                            while not stop_monitor.wait(1.0):
                                progress_cb({
                                    "phase": "downloading",
                                    "source": host,
                                    "totalBytes": CODE_FORMULA_SIZE_MB * 1024 * 1024,
                                    "downloadedBytes": _dir_size_bytes(local_dir),
                                })

                        monitor = threading.Thread(target=_monitor_download_dir, daemon=True)
                        monitor.start()
                    try:
                        snapshot_download(
                            repo_id=CODE_FORMULA_REPO,
                            revision=CODE_FORMULA_REVISION,
                            local_dir=str(local_dir),
                            cache_dir=str(cache_dir),
                            resume_download=True,
                            max_workers=max_workers,
                        )
                    finally:
                        stop_monitor.set()
                        if monitor is not None:
                            monitor.join(timeout=1.0)
                    if code_formula_present(local_dir):
                        if progress_cb:
                            progress_cb({
                                "phase": "checking",
                                "source": host,
                                "downloadedBytes": _dir_size_bytes(local_dir),
                            })
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


def download_code_formula_blocking(progress: Optional[ProgressFn] = None) -> dict[str, Any]:
    """Download CodeFormula to the user profile (Settings action)."""
    dest = user_formula_dir()
    active = _active_formula_dir()
    if code_formula_present(active):
        return {
            "ok": True,
            "already": True,
            "size": _dir_size_bytes(active),
            "path": str(active),
        }

    log.info("Downloading CodeFormula to %s", dest)
    _download_code_formula(dest, progress=True, progress_cb=progress)
    if not code_formula_present(dest):
        raise RuntimeError(f"CodeFormula download finished but weights are missing under {dest}")

    if progress:
        progress({"phase": "installing", "downloadedBytes": _dir_size_bytes(dest)})
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
    for target in {dest, _legacy_formula_dir()}:
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=False)
            removed = True

    formula_link = merged_artifacts_dir() / CODE_FORMULA_FOLDER
    _remove_junction(formula_link)
    _materialize_merged_artifacts()
    invalidate_docling_converter_cache()
    return {"ok": True, "removed": removed, "path": str(dest)}
