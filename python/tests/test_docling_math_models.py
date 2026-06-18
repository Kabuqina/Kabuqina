# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Tests for on-demand CodeFormula download helpers."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

import docling_math_models as dmm  # noqa: E402


class CodeFormulaPresenceTests(unittest.TestCase):
    def test_code_formula_present_detects_safetensors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ds4sd--CodeFormula"
            root.mkdir()
            self.assertFalse(dmm.code_formula_present(root))
            (root / "model.safetensors").write_bytes(b"x")
            self.assertTrue(dmm.code_formula_present(root))

    def test_user_formula_dir_uses_load_package_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data"
            expected = data / "load-packages" / "docling-codeformula" / dmm.CODE_FORMULA_FOLDER

            with patch.dict(os.environ, {"HERMESDESK_DATA_DIR": str(data)}, clear=False):
                self.assertEqual(dmm.user_formula_dir(), expected)


class RequireCodeFormulaTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.data_dir = Path(self._tmpdir.name) / "appdata"
        self.data_dir.mkdir()

    def test_passes_when_weights_exist(self):
        formula = self.data_dir / "docling-models" / dmm.CODE_FORMULA_FOLDER
        formula.mkdir(parents=True)
        (formula / "model.safetensors").write_bytes(b"x")

        with patch.dict(os.environ, {"HERMESDESK_DATA_DIR": str(self.data_dir)}, clear=False):
            dmm.require_code_formula()

    def test_raises_with_settings_hint_when_missing(self):
        with patch.dict(os.environ, {"HERMESDESK_DATA_DIR": str(self.data_dir)}, clear=False):
            with self.assertRaises(dmm.CodeFormulaMissingError) as ctx:
                dmm.require_code_formula()
        self.assertIn("code_formula_model_missing", str(ctx.exception))
        self.assertIn("Settings", str(ctx.exception))


class DownloadDeleteTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.data_dir = Path(self._tmpdir.name) / "appdata"
        self.data_dir.mkdir()

    def test_download_skips_when_already_present(self):
        formula = self.data_dir / "docling-models" / dmm.CODE_FORMULA_FOLDER
        formula.mkdir(parents=True)
        (formula / "model.safetensors").write_bytes(b"abc")

        with patch.dict(os.environ, {"HERMESDESK_DATA_DIR": str(self.data_dir)}, clear=False):
            with patch.object(dmm, "_download_code_formula") as mock_download:
                result = dmm.download_code_formula_blocking()
        mock_download.assert_not_called()
        self.assertTrue(result["already"])

    def test_delete_removes_weights(self):
        formula = self.data_dir / "docling-models" / dmm.CODE_FORMULA_FOLDER
        formula.mkdir(parents=True)
        (formula / "model.safetensors").write_bytes(b"x")

        with patch.dict(os.environ, {"HERMESDESK_DATA_DIR": str(self.data_dir)}, clear=False):
            with patch.object(dmm, "invalidate_docling_converter_cache") as mock_cache:
                result = dmm.delete_code_formula()
            self.assertFalse(dmm.code_formula_present())
        self.assertTrue(result["removed"])
        mock_cache.assert_called_once()

    def test_download_uses_app_data_huggingface_cache(self):
        calls = []

        def fake_snapshot_download(**kwargs):
            calls.append(kwargs)

        with patch.dict(
            os.environ,
            {
                "HERMESDESK_DATA_DIR": str(self.data_dir),
                "DOCLING_HF_RETRIES": "1",
                "DOCLING_HF_DIRECT_FALLBACK": "0",
                "DOCLING_CODEFORMULA_OFFICIAL_FIRST": "0",
            },
            clear=False,
        ):
            with patch("huggingface_hub.snapshot_download", side_effect=fake_snapshot_download):
                with patch.object(dmm, "code_formula_present", return_value=True):
                    dmm._download_code_formula(self.data_dir / "formula", progress=False)

        self.assertEqual(len(calls), 1)
        self.assertIn("cache_dir", calls[0])
        self.assertEqual(
            Path(calls[0]["cache_dir"]),
            self.data_dir / "huggingface-cache",
        )

    def test_download_tries_kabuqina_static_source_before_hf(self):
        calls = []

        def fake_official(local_dir, *, progress_cb=None):
            calls.append(("official", local_dir))

        def fake_snapshot_download(**kwargs):
            calls.append(("hf", kwargs))

        with patch.dict(
            os.environ,
            {
                "HERMESDESK_DATA_DIR": str(self.data_dir),
                "DOCLING_HF_RETRIES": "1",
            },
            clear=False,
        ):
            with patch.object(dmm, "_download_static_code_formula", side_effect=fake_official):
                with patch("huggingface_hub.snapshot_download", side_effect=fake_snapshot_download):
                    with patch.object(dmm, "code_formula_present", return_value=True):
                        dmm._download_code_formula(self.data_dir / "formula", progress=False)

        self.assertEqual(calls, [("official", self.data_dir / "formula")])

    def test_static_directory_entries_ignore_parent_links(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'<a href="../">Parent</a><a href="config.json">config</a>'

        with patch.object(dmm, "urlopen", return_value=FakeResponse()):
            entries = dmm._static_directory_entries(
                "https://kabuqina.com/packages/codeformula/ds4sd--CodeFormula/"
            )

        self.assertEqual(
            entries,
            [("config.json", "https://kabuqina.com/packages/codeformula/ds4sd--CodeFormula/config.json", False)],
        )


class ResolveArtifactsPathTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.root = Path(self._tmpdir.name)

    def test_fast_profile_uses_bundle_dir(self):
        bundle = self.root / "bundle"
        models = bundle / "docling-models" / "ds4sd--docling-models" / "model_artifacts" / "layout"
        models.mkdir(parents=True)
        (models / "model.safetensors").write_bytes(b"x")

        with patch.dict(
            os.environ,
            {"HERMESDESK_BUNDLE_DIR": str(bundle), "HERMESDESK_DATA_DIR": str(self.root / "data")},
            clear=False,
        ):
            resolved = dmm.resolve_docling_artifacts_path(profile="fast")
        self.assertEqual(resolved, bundle / "docling-models")

    def test_fast_profile_prefers_downloaded_docling_base_package(self):
        data = self.root / "data"
        payload = data / "load-packages" / "docling-base" / "ds4sd--docling-models"
        layout = payload / "model_artifacts" / "layout"
        table = payload / "model_artifacts" / "tableformer" / "fast"
        layout.mkdir(parents=True)
        table.mkdir(parents=True)
        (layout / "model.safetensors").write_bytes(b"x")
        (table / "tableformer_fast.safetensors").write_bytes(b"x")

        with patch.dict(
            os.environ,
            {"HERMESDESK_BUNDLE_DIR": str(self.root / "bundle"), "HERMESDESK_DATA_DIR": str(data)},
            clear=False,
        ):
            resolved = dmm.resolve_docling_artifacts_path(profile="fast")

        self.assertEqual(resolved, data / "load-packages" / "docling-base")

    def test_math_profile_returns_none_without_formula(self):
        bundle = self.root / "bundle"
        layout = bundle / "docling-models" / "ds4sd--docling-models" / "model_artifacts" / "layout"
        layout.mkdir(parents=True)
        (layout / "model.safetensors").write_bytes(b"x")

        with patch.dict(
            os.environ,
            {"HERMESDESK_BUNDLE_DIR": str(bundle), "HERMESDESK_DATA_DIR": str(self.root / "data")},
            clear=False,
        ):
            resolved = dmm.resolve_docling_artifacts_path(profile="math")
        self.assertIsNone(resolved)


if __name__ == "__main__":
    unittest.main()
