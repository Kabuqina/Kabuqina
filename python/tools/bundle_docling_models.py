# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Download Docling ML artifacts into the HermesDesk runtime bundle.

Called from ``build_bundle.ps1`` after pip installs docling. Uses
``HF_ENDPOINT`` when set; otherwise defaults to ``https://hf-mirror.com`` so
layout/table weights can be fetched on networks that cannot reach huggingface.co.

EasyOCR weights come from GitHub Releases (not HuggingFace). This script retries
those downloads and can fall back to ``GITHUB_MIRROR`` / built-in GitHub mirrors.

Incremental builds skip work when ``runtime/docling-models/`` already contains
the bundled layout/table/OCR files.

CodeFormula (``mode=math``) is **not** bundled by default (~500 MB). Users
download it from Kabuqina Settings; set ``DOCLING_BUNDLE_CODE_FORMULA=1`` only
for dev/offline experiments.
"""

from __future__ import annotations

import os
import shutil
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

DEFAULT_HF_ENDPOINTS = (
    "https://hf-mirror.com",
    "https://huggingface.co",
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


def _hf_endpoint_candidates() -> list[str]:
    """HF mirrors first; optional direct huggingface.co when mirrors reset connections."""
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


def _robust_hf_snapshot_download(
    *,
    repo_id: str,
    local_dir: Path,
    revision: str,
    progress: bool,
) -> Path:
    """Resume-capable snapshot_download with endpoint rotation and retries."""
    from huggingface_hub import snapshot_download
    from huggingface_hub.utils import disable_progress_bars

    if not progress:
        disable_progress_bars()

    retries = max(1, int(os.environ.get("DOCLING_HF_RETRIES", "5")))
    max_workers = max(1, int(os.environ.get("DOCLING_HF_MAX_WORKERS", "1")))
    local_dir.mkdir(parents=True, exist_ok=True)

    last_err: Optional[BaseException] = None
    prev_endpoint = os.environ.get("HF_ENDPOINT")
    endpoints = _hf_endpoint_candidates()

    for endpoint in endpoints:
        os.environ["HF_ENDPOINT"] = endpoint
        host = urlparse(endpoint).netloc or endpoint
        print(f"Trying HuggingFace endpoint: {host}")
        for attempt in range(1, retries + 1):
            try:
                if attempt > 1:
                    print(f"  snapshot_download {repo_id} attempt {attempt}/{retries} (resume enabled)")
                path = snapshot_download(
                    repo_id=repo_id,
                    local_dir=str(local_dir),
                    revision=revision,
                    resume_download=True,
                    max_workers=max_workers,
                )
                return Path(path)
            except Exception as exc:
                last_err = exc
                if attempt < retries:
                    delay = min(2.0 * attempt, 30.0)
                    print(f"  failed ({type(exc).__name__}): {exc}")
                    print(f"  retrying in {delay:.0f}s...")
                    time.sleep(delay)
        print(f"  exhausted {retries} attempts on {host}")

    if prev_endpoint is not None:
        os.environ["HF_ENDPOINT"] = prev_endpoint
    elif "HF_ENDPOINT" in os.environ and not prev_endpoint:
        pass

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


def _code_formula_models_present(out: Path) -> bool:
    """``mode=math`` needs ds4sd/CodeFormula under the bundled artifacts root."""
    formula_dir = out / "ds4sd--CodeFormula"
    if not formula_dir.is_dir():
        return False
    return any(formula_dir.rglob("*.safetensors")) or any(formula_dir.rglob("*.bin"))


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


def _download_code_formula_models(out: Path, *, progress: bool) -> None:
    from docling.models.code_formula_model import CodeFormulaModel

    formula_dir = out / CodeFormulaModel._model_repo_folder
    formula_dir.mkdir(parents=True, exist_ok=True)
    CodeFormulaModel.download_models(local_dir=formula_dir, force=False, progress=progress)
    if not _code_formula_models_present(out):
        raise RuntimeError(f"CodeFormula model missing after download: {formula_dir}")


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


def _prune_bundled_code_formula(out: Path) -> None:
    """Remove CodeFormula from the MSI bundle unless explicitly opted in."""
    formula_dir = out / "ds4sd--CodeFormula"
    if formula_dir.is_dir():
        shutil.rmtree(formula_dir)
        print(
            f"Removed bundled CodeFormula from {formula_dir} "
            "(on-demand via Settings; set DOCLING_BUNDLE_CODE_FORMULA=1 to keep)."
        )


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
    bundle_formula = _truthy("DOCLING_BUNDLE_CODE_FORMULA", "0")
    need_formula = bundle_formula and not _code_formula_models_present(out)
    need_easyocr = (not skip_easyocr) and not _easyocr_models_present(easyocr_dir)

    if not bundle_formula:
        _prune_bundled_code_formula(out)

    if not need_hf and not need_formula and not need_easyocr:
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

    if need_formula:
        print("Downloading Docling CodeFormula model (DOCLING_BUNDLE_CODE_FORMULA=1)...")
        try:
            _download_code_formula_models(out, progress=progress)
        except Exception as exc:
            print(f"Docling CodeFormula bundling failed: {exc}", file=sys.stderr)
            return 1
    elif bundle_formula:
        print("CodeFormula model already present — skipping")
    else:
        print("CodeFormula not bundled (mode=math uses Settings on-demand download).")

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
