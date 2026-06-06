# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Tests for Docling bundle download helpers."""

from __future__ import annotations

import io
import os
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from bundle_docling_models import (  # noqa: E402
    _code_formula_models_present,
    _hf_models_present,
    github_download_candidates,
    robust_download_url,
)


class GitHubDownloadCandidatesTests(unittest.TestCase):
    def test_direct_github_url_only_when_mirrors_disabled(self):
        url = "https://github.com/JaidedAI/EasyOCR/releases/download/pre-v1.1.6/craft_mlt_25k.zip"
        with patch.dict(os.environ, {"DOCLING_TRY_GITHUB_MIRRORS": "0", "GITHUB_MIRROR": ""}, clear=False):
            self.assertEqual(github_download_candidates(url), [url])

    def test_adds_custom_github_mirror_first(self):
        url = "https://github.com/JaidedAI/EasyOCR/releases/download/pre-v1.1.6/craft_mlt_25k.zip"
        with patch.dict(
            os.environ,
            {"DOCLING_TRY_GITHUB_MIRRORS": "0", "GITHUB_MIRROR": "https://ghfast.top", "DOCLING_GITHUB_DIRECT_FALLBACK": "0"},
            clear=False,
        ):
            self.assertEqual(
                github_download_candidates(url),
                ["https://ghfast.top/" + url],
            )

    def test_custom_mirror_can_fallback_to_direct(self):
        url = "https://github.com/JaidedAI/EasyOCR/releases/download/pre-v1.1.6/craft_mlt_25k.zip"
        with patch.dict(
            os.environ,
            {"DOCLING_TRY_GITHUB_MIRRORS": "0", "GITHUB_MIRROR": "https://ghfast.top", "DOCLING_GITHUB_DIRECT_FALLBACK": "1"},
            clear=False,
        ):
            self.assertEqual(
                github_download_candidates(url),
                ["https://ghfast.top/" + url, url],
            )

    def test_builtin_mirrors_precede_direct_by_default(self):
        url = "https://github.com/JaidedAI/EasyOCR/releases/download/pre-v1.1.6/craft_mlt_25k.zip"
        with patch.dict(os.environ, {"DOCLING_TRY_GITHUB_MIRRORS": "1", "GITHUB_MIRROR": ""}, clear=False):
            candidates = github_download_candidates(url)
        self.assertEqual(candidates[-1], url)
        self.assertGreater(len(candidates), 1)
        self.assertTrue(all(candidate.endswith("craft_mlt_25k.zip") for candidate in candidates))

    def test_non_github_urls_are_not_mirrored(self):
        url = "https://hf-mirror.com/api/models"
        self.assertEqual(github_download_candidates(url), [url])


class BundlePresenceTests(unittest.TestCase):
    def test_bundle_script_copies_capability_modules(self):
        root = Path(__file__).resolve().parents[1]
        script = (root / "build_bundle.ps1").read_text(encoding="utf-8")
        sync_script = (root.parent / "scripts" / "sync-runtime-sources.ps1").read_text(encoding="utf-8")

        self.assertIn("src\\capability_registry.py", script)
        self.assertIn("src\\capability_status.py", script)
        self.assertIn("src\\capability_prompt.py", script)
        self.assertIn('"capability_registry.py"', sync_script)
        self.assertIn('"capability_status.py"', sync_script)
        self.assertIn('"capability_prompt.py"', sync_script)

    def test_hf_models_present_detects_layout_and_table(self):
        root = Path(self._get_temp_dir())
        layout = root / "ds4sd--docling-models/model_artifacts/layout/model.safetensors"
        table = root / "ds4sd--docling-models/model_artifacts/tableformer/fast/tableformer_fast.safetensors"
        layout.parent.mkdir(parents=True)
        table.parent.mkdir(parents=True)
        layout.write_bytes(b"x")
        self.assertFalse(_hf_models_present(root))
        table.write_bytes(b"y")
        self.assertTrue(_hf_models_present(root))

    def test_code_formula_models_present_detects_formula_weights(self):
        root = Path(self._get_temp_dir())
        formula = root / "ds4sd--CodeFormula"
        formula.mkdir(parents=True)
        self.assertFalse(_code_formula_models_present(root))
        (formula / "model.safetensors").write_bytes(b"x")
        self.assertTrue(_code_formula_models_present(root))

    def test_prune_removes_bundled_code_formula(self):
        from bundle_docling_models import _prune_bundled_code_formula

        root = Path(self._get_temp_dir())
        formula = root / "ds4sd--CodeFormula"
        formula.mkdir(parents=True)
        (formula / "model.safetensors").write_bytes(b"x")
        _prune_bundled_code_formula(root)
        self.assertFalse(formula.exists())

    def _get_temp_dir(self):
        import tempfile

        return tempfile.mkdtemp()


class RobustDownloadUrlTests(unittest.TestCase):
    def test_retries_then_succeeds(self):
        url = "https://github.com/example/model.zip"
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as archive:
            archive.writestr("model.pth", b"ok")
        payload = zip_buf.getvalue()

        class FakeResponse:
            def __init__(self, body: bytes):
                self.headers = {"content-length": str(len(body))}
                self._body = body

            def raise_for_status(self):
                return None

            def iter_content(self, _chunk_size):
                yield self._body

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        calls = {"count": 0}

        def fake_get(*_args, **_kwargs):
            calls["count"] += 1
            if calls["count"] < 2:
                raise ConnectionError("Remote end closed connection without response")
            return FakeResponse(payload)

        with patch("requests.get", fake_get):
            buf = robust_download_url(url, progress=False, retries_per_url=3)
        self.assertEqual(buf.getvalue(), payload)
        self.assertEqual(calls["count"], 2)


if __name__ == "__main__":
    unittest.main()
