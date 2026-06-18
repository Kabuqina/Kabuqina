# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Tests for the generic optional load-package registry."""

from __future__ import annotations

import os
import json
import sys
import tempfile
import time
import unittest
import zipfile
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
        self.assertIn("docling-base", ids)
        self.assertIn("docling-codeformula", ids)
        self.assertIn("local-stt-base-q5_1", ids)
        base = next(item for item in packages if item["id"] == "docling-base")
        self.assertEqual(base["modelId"], "ds4sd/docling-models")
        self.assertEqual(base["sizeMb"], 506)
        self.assertEqual(
            base["sources"][0]["url"],
            "https://nanapackages-1428509047.cos.ap-guangzhou.myqcloud.com/ds4sd--docling-models.zip",
        )
        formula = next(item for item in packages if item["id"] == "docling-codeformula")
        self.assertEqual(formula["modelId"], "ds4sd/CodeFormula")
        self.assertEqual(formula["sizeMb"], 500)
        self.assertEqual(
            formula["sources"][0]["url"],
            "https://nanapackages-1428509047.cos.ap-guangzhou.myqcloud.com/ds4sd--CodeFormula.zip",
        )
        self.assertEqual(formula["sources"][1]["url"], "https://kabuqina.com/packages/codeformula/")

        stt = next(item for item in packages if item["id"] == "local-stt-base-q5_1")
        self.assertEqual(
            stt["sources"][0]["url"],
            "https://nanapackages-1428509047.cos.ap-guangzhou.myqcloud.com/ggml-base-q5_1.bin",
        )
        self.assertEqual(stt["sources"][1]["url"], "https://kabuqina.com/packages/stt/ggml-base-q5_1.bin")

    def test_download_implementations_try_cos_before_legacy_sources(self):
        import docling_math_models as dmm
        import load_packages

        voice_helpers = load_packages._voice_helpers()

        self.assertEqual(
            dmm.KABUQINA_CODE_FORMULA_ARCHIVE_URLS[0],
            "https://nanapackages-1428509047.cos.ap-guangzhou.myqcloud.com/ds4sd--CodeFormula.zip",
        )
        self.assertEqual(
            voice_helpers.DESK_STT_MODEL_URLS[0],
            "https://nanapackages-1428509047.cos.ap-guangzhou.myqcloud.com/ggml-base-q5_1.bin",
        )

    def test_load_packages_report_product_capability_usage(self):
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

        formula = next(item for item in packages if item["id"] == "docling-codeformula")
        stt = next(item for item in packages if item["id"] == "local-stt-base-q5_1")
        formula_usage = {item["id"] for item in formula["usedByCapabilities"]}
        stt_usage = {item["id"] for item in stt["usedByCapabilities"]}

        self.assertIn("document-math", formula_usage)
        self.assertIn("document-precise-read", formula_usage)
        self.assertIn("voice-local-stt", stt_usage)

    def test_package_status_prefers_user_path_over_bundled_path(self):
        import load_packages

        user_payload = self.data_dir / "load-packages" / "docling-base" / "ds4sd--docling-models"
        bundled_payload = self.data_dir / "runtime" / "load-packages" / "docling-base" / "ds4sd--docling-models"
        user_payload.mkdir(parents=True)
        bundled_payload.mkdir(parents=True)
        (user_payload / "model_artifacts" / "layout").mkdir(parents=True)
        (user_payload / "model_artifacts" / "tableformer" / "fast").mkdir(parents=True)
        (bundled_payload / "model_artifacts" / "layout").mkdir(parents=True)
        (bundled_payload / "model_artifacts" / "tableformer" / "fast").mkdir(parents=True)
        (user_payload / "model_artifacts" / "layout" / "model.safetensors").write_bytes(b"user")
        (user_payload / "model_artifacts" / "tableformer" / "fast" / "tableformer_fast.safetensors").write_bytes(b"user")
        (bundled_payload / "model_artifacts" / "layout" / "model.safetensors").write_bytes(b"bundle")
        (bundled_payload / "model_artifacts" / "tableformer" / "fast" / "tableformer_fast.safetensors").write_bytes(b"bundle")

        with patch.dict(
            os.environ,
            {
                "HERMESDESK_DATA_DIR": str(self.data_dir),
                "HERMESDESK_BUNDLE_DIR": str(self.data_dir / "runtime"),
                "HERMESDESK_WORKSPACE": str(self.workspace),
            },
            clear=False,
        ):
            status = load_packages.package_status("docling-base")

        self.assertEqual(status["realPath"], str(user_payload))
        self.assertEqual(status["source"], "downloaded")
        self.assertEqual(status["path"], status["realPath"])
        self.assertEqual(status["agentPath"], ".hermesdesk/load-packages/docling-base")

    def test_workspace_index_writes_manifests(self):
        import load_packages

        payload = self.data_dir / "load-packages" / "docling-base" / "ds4sd--docling-models"
        (payload / "model_artifacts" / "layout").mkdir(parents=True)
        (payload / "model_artifacts" / "tableformer" / "fast").mkdir(parents=True)
        (payload / "model_artifacts" / "layout" / "model.safetensors").write_bytes(b"x")
        (payload / "model_artifacts" / "tableformer" / "fast" / "tableformer_fast.safetensors").write_bytes(b"x")

        with patch.dict(
            os.environ,
            {
                "HERMESDESK_DATA_DIR": str(self.data_dir),
                "HERMESDESK_WORKSPACE": str(self.workspace),
            },
            clear=False,
        ):
            result = load_packages.refresh_workspace_package_index()

        root = self.workspace / ".hermesdesk" / "load-packages"
        index = root / "packages.json"
        per_package = root / "docling-base.json"
        real_path = root / "docling-base" / "real-path.txt"

        self.assertTrue(result["ok"])
        self.assertTrue(index.exists())
        self.assertTrue(per_package.exists())
        self.assertEqual(real_path.read_text(encoding="utf-8"), str(payload))
        data = json.loads(index.read_text(encoding="utf-8"))
        self.assertEqual(data["version"], 1)
        base = next(item for item in data["packages"] if item["id"] == "docling-base")
        self.assertEqual(base["agentPath"], ".hermesdesk/load-packages/docling-base")

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

    def test_download_route_starts_background_job_with_progress(self):
        import load_packages

        calls = []

        def fake_download(progress=None):
            calls.append("started")
            if progress:
                progress({"phase": "downloading", "downloadedBytes": 10, "totalBytes": 100})
            time.sleep(0.05)
            if progress:
                progress({"phase": "installing", "downloadedBytes": 100, "totalBytes": 100})
            return {"ok": True, "size": 100, "path": str(self.data_dir / "pkg")}

        with patch.dict(
            os.environ,
            {
                "HERMESDESK_DATA_DIR": str(self.data_dir),
                "HERMESDESK_WORKSPACE": str(self.workspace),
            },
            clear=False,
        ):
            with patch.object(load_packages, "_formula_download", side_effect=fake_download):
                started = load_packages.start_download_package("docling-codeformula")
                self.assertEqual(started["job"]["status"], "running")
                self.assertIn(started["job"]["phase"], {"queued", "downloading", "installing"})

                deadline = time.time() + 2
                final = started
                while time.time() < deadline:
                    final = load_packages.package_status("docling-codeformula")
                    if final["job"] and final["job"]["status"] == "done":
                        break
                    time.sleep(0.02)

        self.assertEqual(calls, ["started"])
        self.assertEqual(final["job"]["status"], "done")
        self.assertEqual(final["job"]["phase"], "done")
        self.assertEqual(final["job"]["downloadedBytes"], 100)
        self.assertEqual(final["job"]["totalBytes"], 100)
        self.assertEqual(final["job"]["percent"], 100)

    def test_installed_package_reconciles_stale_installing_job(self):
        import load_packages

        payload = self.data_dir / "load-packages" / "docling-codeformula" / "ds4sd--CodeFormula"
        payload.mkdir(parents=True)
        (payload / "model.safetensors").write_bytes(b"weights")

        with patch.dict(
            os.environ,
            {
                "HERMESDESK_DATA_DIR": str(self.data_dir),
                "HERMESDESK_WORKSPACE": str(self.workspace),
            },
            clear=False,
        ):
            load_packages._update_job(
                "docling-codeformula",
                {
                    "status": "running",
                    "phase": "installing",
                    "downloadedBytes": 7,
                    "totalBytes": 7,
                },
            )

            status = load_packages.package_status("docling-codeformula")

        self.assertTrue(status["downloaded"])
        self.assertEqual(status["job"]["status"], "done")
        self.assertEqual(status["job"]["phase"], "done")
        self.assertEqual(status["job"]["downloadedBytes"], status["size"])
        self.assertEqual(status["job"]["totalBytes"], status["size"])


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

        with patch.dict(
            os.environ,
            {"HF_ENDPOINT": "https://original.example", "DOCLING_CODEFORMULA_OFFICIAL_FIRST": "0"},
            clear=False,
        ):
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
                "DOCLING_CODEFORMULA_OFFICIAL_FIRST": "0",
            },
            clear=False,
        ):
            os.environ.pop("HF_ENDPOINT", None)
            with patch("huggingface_hub.snapshot_download", side_effect=RuntimeError("offline")):
                with self.assertRaises(RuntimeError):
                    dmm._download_code_formula(self.data_dir / "formula", progress=True)

            self.assertNotIn("HF_ENDPOINT", os.environ)

    def test_code_formula_archive_download_extracts_payload(self):
        import docling_math_models as dmm

        source_zip = self.data_dir / "source.zip"
        with zipfile.ZipFile(source_zip, "w") as zf:
            zf.writestr("ds4sd--CodeFormula/model.safetensors", b"weights")

        dest = self.data_dir / "load-packages" / "docling-codeformula" / "ds4sd--CodeFormula"
        progress_events = []

        dmm._download_code_formula_archive(
            source_zip.as_uri(),
            dest,
            progress_cb=progress_events.append,
        )

        self.assertTrue((dest / "model.safetensors").is_file())
        self.assertTrue(dmm.code_formula_present(dest))
        self.assertTrue(any(event.get("source") == "" or event.get("source") for event in progress_events))

    def test_code_formula_archive_rejects_unsafe_paths(self):
        import docling_math_models as dmm

        source_zip = self.data_dir / "unsafe.zip"
        with zipfile.ZipFile(source_zip, "w") as zf:
            zf.writestr("../escape.safetensors", b"bad")

        dest = self.data_dir / "load-packages" / "docling-codeformula" / "ds4sd--CodeFormula"

        with self.assertRaisesRegex(RuntimeError, "unsafe archive member path"):
            dmm._download_code_formula_archive(source_zip.as_uri(), dest)

        self.assertFalse((self.data_dir / "load-packages" / "docling-codeformula" / "escape.safetensors").exists())


if __name__ == "__main__":
    unittest.main()
