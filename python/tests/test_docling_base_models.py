# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Docling base model load-package: resolve/status/extract/download helpers."""

from __future__ import annotations

import io
import os
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import docling_base_models as dbm  # noqa: E402


def _make_base_payload(root: Path) -> None:
    layout = root / "model_artifacts" / "layout"
    table = root / "model_artifacts" / "tableformer" / "fast"
    layout.mkdir(parents=True, exist_ok=True)
    table.mkdir(parents=True, exist_ok=True)
    (layout / "model.safetensors").write_bytes(b"layout")
    (table / "tableformer_fast.safetensors").write_bytes(b"table")


def _make_base_zip(top_folder: bool = True) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        prefix = f"{dbm.DOCLING_BASE_FOLDER}/" if top_folder else ""
        zf.writestr(f"{prefix}model_artifacts/layout/model.safetensors", b"layout")
        zf.writestr(
            f"{prefix}model_artifacts/tableformer/fast/tableformer_fast.safetensors",
            b"table",
        )
    return buf.getvalue()


class _Headers(dict):
    def get(self, key, default=None):
        for k, value in self.items():
            if k.lower() == key.lower():
                return value
        return default


class _Resp:
    def __init__(self, body=b"", status=200, headers=None):
        self._body = io.BytesIO(body)
        self.status = status
        self.headers = _Headers(headers or {})

    def read(self, n=-1):
        return self._body.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _FakeOpener:
    def __init__(self, data: bytes, truncate_first: bool = True):
        self.data = data
        self.truncate_first = truncate_first
        self.get_calls = 0

    def __call__(self, req, timeout=None):
        if req.get_method() == "HEAD":
            return _Resp(b"", 200, {"Content-Length": str(len(self.data))})
        rng = req.get_header("Range")
        start = 0
        if rng:
            start = int(re.match(r"bytes=(\d+)-", rng).group(1))
        body = self.data[start:]
        status = 206 if rng else 200
        headers = {"Content-Length": str(len(body))}
        if rng:
            headers["Content-Range"] = f"bytes {start}-{len(self.data) - 1}/{len(self.data)}"
        self.get_calls += 1
        if self.truncate_first and self.get_calls == 1:
            body = body[: max(1, len(body) // 2)]
        return _Resp(body, status, headers)


class DoclingBaseResolveTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.root = Path(self._tmpdir.name)
        self.data_dir = self.root / "data"
        self.bundle_dir = self.root / "bundle"
        self.data_dir.mkdir()
        self.bundle_dir.mkdir()
        self._env = patch.dict(
            os.environ,
            {
                "HERMESDESK_DATA_DIR": str(self.data_dir),
                "HERMESDESK_BUNDLE_DIR": str(self.bundle_dir),
            },
            clear=False,
        )
        self._env.start()
        self.addCleanup(self._env.stop)

    def test_missing_when_no_payload_exists(self):
        self.assertFalse(dbm.docling_base_present())
        self.assertFalse(dbm.docling_base_downloaded())
        self.assertIsNone(dbm.resolve_docling_base_dir())
        self.assertIsNone(dbm.resolve_docling_base_artifacts_dir())
        self.assertFalse(dbm.docling_base_status()["downloaded"])

    def test_user_download_preferred_over_legacy_bundle(self):
        bundled = self.bundle_dir / "docling-models" / dbm.DOCLING_BASE_FOLDER
        user = dbm.user_docling_base_dir()
        _make_base_payload(bundled)
        _make_base_payload(user)

        self.assertTrue(dbm.docling_base_present())
        self.assertTrue(dbm.docling_base_downloaded())
        self.assertEqual(dbm.resolve_docling_base_dir(), user)
        self.assertEqual(dbm.resolve_docling_base_artifacts_dir(), dbm.user_docling_base_root())
        status = dbm.docling_base_status()
        self.assertEqual(status["path"], str(user))
        self.assertEqual(status["source"], "downloaded")

    def test_legacy_bundle_is_still_resolved_for_upgraded_installs(self):
        bundled = self.bundle_dir / "docling-models" / dbm.DOCLING_BASE_FOLDER
        _make_base_payload(bundled)

        self.assertTrue(dbm.docling_base_present())
        self.assertFalse(dbm.docling_base_downloaded())
        self.assertEqual(dbm.resolve_docling_base_dir(), bundled)
        self.assertEqual(dbm.resolve_docling_base_artifacts_dir(), self.bundle_dir / "docling-models")
        self.assertEqual(dbm.docling_base_status()["source"], "bundled")


class DoclingBaseArchiveTests(unittest.TestCase):
    def test_extracts_top_folder_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "base.zip"
            archive.write_bytes(_make_base_zip(top_folder=True))

            dbm._extract_archive(archive, root)

            self.assertTrue(dbm._has_base_models(root / dbm.DOCLING_BASE_FOLDER))

    def test_extracts_flat_layout_into_canonical_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "base.zip"
            archive.write_bytes(_make_base_zip(top_folder=False))

            dbm._extract_archive(archive, root)

            self.assertTrue(dbm._has_base_models(root / dbm.DOCLING_BASE_FOLDER))

    def test_archive_rejects_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("../escape.safetensors", b"bad")

            with self.assertRaisesRegex(RuntimeError, "unsafe archive member path"):
                dbm._extract_archive(archive, root)

            self.assertFalse((root.parent / "escape.safetensors").exists())

    def test_resumable_download_recovers_from_truncation(self):
        payload = _make_base_zip(top_folder=True)
        opener = _FakeOpener(payload, truncate_first=True)
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "base.zip.tmp"
            with patch.object(dbm, "urlopen", opener):
                dbm._download_archive(dbm.DOCLING_BASE_ARCHIVE_URLS[0], dest, progress_cb=None)
            self.assertEqual(dest.read_bytes(), payload)
            self.assertGreaterEqual(opener.get_calls, 2)

    def test_blocking_download_extracts_base_package(self):
        data = Path(tempfile.mkdtemp(prefix="kbq-dbm-data-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(data, ignore_errors=True))
        opener = _FakeOpener(_make_base_zip(top_folder=True), truncate_first=True)
        with patch.dict(os.environ, {"HERMESDESK_DATA_DIR": str(data)}, clear=False):
            os.environ.pop("HERMESDESK_BUNDLE_DIR", None)
            with patch.object(dbm, "urlopen", opener):
                result = dbm.download_docling_base_blocking()

        self.assertTrue(result["ok"])
        self.assertTrue(dbm._has_base_models(data / "load-packages" / "docling-base" / dbm.DOCLING_BASE_FOLDER))


if __name__ == "__main__":
    unittest.main()
