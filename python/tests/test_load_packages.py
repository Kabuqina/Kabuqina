# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Tests for the generic optional load-package registry."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
CORE_DIR = Path(__file__).resolve().parents[2] / "hermes_core"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(CORE_DIR))


class LoadPackageRegistryTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.data_dir = Path(self._tmpdir.name) / "appdata"
        self.workspace = Path(self._tmpdir.name) / "workspace"
        self.data_dir.mkdir()
        self.workspace.mkdir()

    def test_registry_lists_docling_formula_and_local_stt_packages(self):
        import load_packages

        with patch.dict(
            os.environ,
            {
                "HERMESDESK_DATA_DIR": str(self.data_dir),
                "HERMESDESK_WORKSPACE": str(self.workspace),
            },
            clear=False,
        ):
            packages = load_packages.list_load_packages()

        ids = {item["id"] for item in packages}
        self.assertIn("docling-codeformula", ids)
        self.assertIn("local-stt-base-q5_1", ids)
        formula = next(item for item in packages if item["id"] == "docling-codeformula")
        self.assertEqual(formula["modelId"], "ds4sd/CodeFormula")
        self.assertEqual(formula["sizeMb"], 500)

    def test_stt_package_delete_removes_downloaded_model(self):
        import load_packages

        with patch.dict(
            os.environ,
            {
                "HERMESDESK_DATA_DIR": str(self.data_dir),
                "HERMESDESK_WORKSPACE": str(self.workspace),
            },
            clear=False,
        ):
            voice_helpers = load_packages._voice_helpers()
            path = voice_helpers.desk_stt_model_path()
            path.parent.mkdir(parents=True)
            path.write_bytes(b"model")
            self.assertTrue(load_packages.package_status("local-stt-base-q5_1")["downloaded"])

            result = load_packages.delete_package("local-stt-base-q5_1")

            self.assertTrue(result["ok"])
            self.assertTrue(result["removed"])
            self.assertFalse(path.exists())
            self.assertFalse(load_packages.package_status("local-stt-base-q5_1")["downloaded"])

    def test_desk_route_lists_load_packages_and_formula_route_is_not_registered(self):
        from desk_server.auth import SESSION_HEADER_NAME, SESSION_TOKEN
        from desk_server.app import create_app
        from fastapi.testclient import TestClient

        with patch.dict(
            os.environ,
            {
                "HERMESDESK_DATA_DIR": str(self.data_dir),
                "HERMESDESK_WORKSPACE": str(self.workspace),
            },
            clear=False,
        ):
            client = TestClient(create_app())
            headers = {SESSION_HEADER_NAME: SESSION_TOKEN}
            resp = client.get("/api/desk/load-packages", headers=headers)
            old_resp = client.get("/api/desk/formula-model/status", headers=headers)

        self.assertEqual(resp.status_code, 200)
        ids = {item["id"] for item in resp.json()["packages"]}
        self.assertIn("docling-codeformula", ids)
        self.assertIn("local-stt-base-q5_1", ids)
        self.assertEqual(old_resp.status_code, 404)


class CodeFormulaFirstUseTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.data_dir = Path(self._tmpdir.name) / "appdata"
        self.data_dir.mkdir()

    def test_ensure_code_formula_prompts_then_downloads_when_missing(self):
        import docling_math_models as dmm

        with patch.dict(os.environ, {"HERMESDESK_DATA_DIR": str(self.data_dir)}, clear=False):
            with patch("approval_backend.ApprovalBackend.ask_model_download", return_value="once") as ask:
                with patch.object(dmm, "download_code_formula_blocking", return_value={"ok": True}) as download:
                    with patch.object(dmm, "code_formula_present", side_effect=[False, False, True]):
                        dmm.ensure_code_formula_available_for_math()

        ask.assert_called_once()
        kwargs = ask.call_args.kwargs
        self.assertEqual(kwargs["model_id"], "ds4sd/CodeFormula")
        self.assertEqual(kwargs["size_mb"], 500)
        download.assert_called_once()

    def test_ensure_code_formula_raises_when_user_declines(self):
        import docling_math_models as dmm

        with patch.dict(os.environ, {"HERMESDESK_DATA_DIR": str(self.data_dir)}, clear=False):
            with patch("approval_backend.ApprovalBackend.ask_model_download", return_value="deny"):
                with self.assertRaises(PermissionError):
                    dmm.ensure_code_formula_available_for_math()

    def test_download_restores_hf_endpoint_after_success(self):
        import docling_math_models as dmm

        calls = []

        def fake_snapshot_download(**_kwargs):
            calls.append(os.environ.get("HF_ENDPOINT"))

        with patch.dict(os.environ, {"HF_ENDPOINT": "https://original.example"}, clear=False):
            with patch("huggingface_hub.snapshot_download", side_effect=fake_snapshot_download):
                with patch.object(dmm, "code_formula_present", return_value=True):
                    dmm._download_code_formula(self.data_dir / "formula", progress=True)

            self.assertEqual(os.environ.get("HF_ENDPOINT"), "https://original.example")

        self.assertEqual(calls, ["https://original.example"])

    def test_download_removes_temporary_hf_endpoint_after_failure_without_previous_value(self):
        import docling_math_models as dmm

        with patch.dict(
            os.environ,
            {
                "DOCLING_HF_RETRIES": "1",
                "DOCLING_HF_DIRECT_FALLBACK": "0",
            },
            clear=False,
        ):
            os.environ.pop("HF_ENDPOINT", None)
            with patch("huggingface_hub.snapshot_download", side_effect=RuntimeError("offline")):
                with self.assertRaises(RuntimeError):
                    dmm._download_code_formula(self.data_dir / "formula", progress=True)

            self.assertNotIn("HF_ENDPOINT", os.environ)


if __name__ == "__main__":
    unittest.main()
