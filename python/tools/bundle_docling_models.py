"""Download Docling ML artifacts into the HermesDesk runtime bundle.

Called from ``build_bundle.ps1`` after pip installs docling. Uses
``HF_ENDPOINT`` when set; otherwise defaults to ``https://hf-mirror.com`` so
layout/table weights can be fetched on networks that cannot reach huggingface.co.

EasyOCR weights come from GitHub Releases (not HuggingFace). This script retries
those downloads and can fall back to ``GITHUB_MIRROR`` / built-in GitHub mirrors.

Incremental builds skip work when ``runtime/docling-models/`` already contains
the bundled layout/table/OCR files.
"""

from __future__ import annotations

import os
import sys
import time
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

DEFAULT_GITHUB_MIRRORS = (
    "https://ghfast.top",
    "https://mirror.ghproxy.com",
)


def _truthy(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).strip().lower() not in ("0", "false", "no", "off")


def github_download_candidates(url: str) -> list[str]:
    """Return download URLs to try, preferring mirrors on slow/blocked GitHub networks."""
    if "github.com/" not in url:
        return [url]

    direct = url
    ordered: list[str] = []
    custom = os.environ.get("GITHUB_MIRROR", "").strip().rstrip("/")
    if custom:
        mirror_url = direct if direct.startswith(custom + "/") else f"{custom}/{direct}"
        ordered.append(mirror_url)
        if _truthy("DOCLING_GITHUB_DIRECT_FALLBACK", "0"):
            ordered.append(direct)
    elif _truthy("DOCLING_TRY_GITHUB_MIRRORS", "1"):
        for prefix in DEFAULT_GITHUB_MIRRORS:
            ordered.append(f"{prefix.rstrip('/')}/{direct}")
        ordered.append(direct)
    else:
        ordered.append(direct)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in ordered:
        if candidate not in seen:
            seen.add(candidate)
            deduped.append(candidate)
    return deduped


def _download_once(url: str, *, progress: bool, timeout: tuple[float, float]) -> BytesIO:
    import requests

    headers = {
        "User-Agent": "Kabuqina-docling-bundle/1.0 (+https://github.com/kabuqina)",
    }
    buf = BytesIO()
    with requests.get(
        url,
        stream=True,
        allow_redirects=True,
        timeout=timeout,
        headers=headers,
    ) as response:
        response.raise_for_status()
        total_size = int(response.headers.get("content-length", 0) or 0)
        progress_bar = None
        if progress:
            from tqdm import tqdm

            progress_bar = tqdm(
                total=total_size or None,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
            )
        for chunk in response.iter_content(256 * 1024):
            if not chunk:
                continue
            buf.write(chunk)
            if progress_bar is not None:
                progress_bar.update(len(chunk))
        if progress_bar is not None:
            progress_bar.close()

    if buf.tell() == 0:
        raise RuntimeError(f"empty response body from {url}")

    if url.lower().endswith(".zip"):
        with zipfile.ZipFile(buf, "r") as archive:
            corrupt = archive.testzip()
            if corrupt is not None:
                raise RuntimeError(f"corrupt zip member {corrupt!r} from {url}")
        buf.seek(0)

    buf.seek(0)
    return buf


def robust_download_url(
    url: str,
    *,
    progress: bool = False,
    retries_per_url: int = 2,
    timeout: tuple[float, float] = (15.0, 300.0),
) -> BytesIO:
    last_err: Optional[BaseException] = None
    candidates = github_download_candidates(url)
    for candidate in candidates:
        for attempt in range(1, max(1, retries_per_url) + 1):
            try:
                if len(candidates) > 1 or attempt > 1:
                    host = urlparse(candidate).netloc or candidate
                    print(f"  downloading from {host} (attempt {attempt}/{retries_per_url})")
                return _download_once(candidate, progress=progress, timeout=timeout)
            except Exception as exc:
                last_err = exc
                if attempt < retries_per_url:
                    time.sleep(min(1.5 * attempt, 4.0))
    assert last_err is not None
    raise last_err


def _patch_docling_downloader() -> None:
    import docling.utils.utils as docling_utils

    docling_utils.download_url_with_progress = robust_download_url  # type: ignore[assignment]


def _hf_models_present(out: Path) -> bool:
    base = out / "ds4sd--docling-models" / "model_artifacts"
    layout = base / "layout" / "model.safetensors"
    table_fast = base / "tableformer" / "fast" / "tableformer_fast.safetensors"
    return layout.is_file() and table_fast.is_file()


def _easyocr_models_present(local_dir: Path) -> bool:
    expected = (
        "craft_mlt_25k.pth",
        "english_g2.pth",
        "latin_g2.pth",
    )
    return all((local_dir / name).is_file() for name in expected)


def _download_hf_models(out: Path, *, progress: bool) -> None:
    from docling.utils.model_downloader import download_models

    download_models(
        output_dir=out,
        progress=progress,
        with_layout=True,
        with_tableformer=True,
        with_code_formula=False,
        with_picture_classifier=False,
        with_easyocr=False,
        with_smolvlm=False,
        with_granite_vision=False,
    )

    layout_marker = out / "ds4sd--docling-models" / "model_artifacts" / "layout"
    if not layout_marker.is_dir():
        raise RuntimeError(f"layout model missing after download: {layout_marker}")


def _download_easyocr_models(local_dir: Path, *, progress: bool) -> None:
    from docling.models.easyocr_model import EasyOcrModel

    local_dir.mkdir(parents=True, exist_ok=True)
    EasyOcrModel.download_models(local_dir=local_dir, force=False, progress=progress)
    if not _easyocr_models_present(local_dir):
        missing = [
            name
            for name in ("craft_mlt_25k.pth", "english_g2.pth", "latin_g2.pth")
            if not (local_dir / name).is_file()
        ]
        raise RuntimeError(f"EasyOCR download finished but files are missing: {', '.join(missing)}")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: bundle_docling_models.py <runtime-root>", file=sys.stderr)
        return 2

    runtime = Path(sys.argv[1]).resolve()
    site_packages = runtime / "site-packages"
    if not site_packages.is_dir():
        print(f"missing site-packages: {site_packages}", file=sys.stderr)
        return 1

    sys.path.insert(0, str(site_packages))
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

    out = runtime / "docling-models"
    progress = _truthy("DOCLING_BUNDLE_PROGRESS", "1")
    skip_easyocr = not _truthy("DOCLING_BUNDLE_EASYOCR", "1")
    easyocr_dir = out / "EasyOcr"

    need_hf = not _hf_models_present(out)
    need_easyocr = (not skip_easyocr) and not _easyocr_models_present(easyocr_dir)

    if not need_hf and not need_easyocr:
        print(f"docling models already bundled — skipping download ({out})")
        return 0

    _patch_docling_downloader()

    if need_hf:
        print("Downloading Docling layout + table models (HuggingFace)...")
        try:
            _download_hf_models(out, progress=progress)
        except Exception as exc:
            print(f"Docling HF bundling failed: {exc}", file=sys.stderr)
            return 1
    else:
        print("layout/table models already present — skipping HuggingFace download")

    if skip_easyocr:
        print("Skipping EasyOCR bundle (DOCLING_BUNDLE_EASYOCR=0).")
    elif need_easyocr:
        print("Downloading EasyOCR models (GitHub Releases)...")
        try:
            _download_easyocr_models(easyocr_dir, progress=progress)
        except Exception as exc:
            print(f"EasyOCR bundling failed: {exc}", file=sys.stderr)
            print(
                "Retry with a GitHub mirror, e.g.\n"
                "  $env:GITHUB_MIRROR='https://ghfast.top'\n"
                "  .\\python\\build_bundle.ps1\n"
                "Or skip OCR bundle (scanned PDF OCR may fail offline):\n"
                "  $env:DOCLING_BUNDLE_EASYOCR='0'",
                file=sys.stderr,
            )
            return 1
    else:
        print(f"EasyOCR models already present — skipping ({easyocr_dir})")

    print(f"docling models ok: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
