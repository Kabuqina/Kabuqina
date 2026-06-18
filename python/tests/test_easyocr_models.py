# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""EasyOCR on-demand load-package: resolve/status/extract + resumable download."""

import io
import os
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

_root = Path(__file__).resolve().parent.parent
_src = _root / "src"
for p in (_src, _root):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

import easyocr_models as eom  # noqa: E402

_FILES = ("craft_mlt_25k.pth", "english_g2.pth", "latin_g2.pth")


def _make_zip(top_folder: bool = True) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in _FILES:
            arc = f"EasyOcr/{name}" if top_folder else name
            zf.writestr(arc, b"weights-" + name.encode())
    return buf.getvalue()


class _Headers(dict):
    def get(self, key, default=None):
        for k, v in self.items():
            if k.lower() == key.lower():
                return v
        return default


class _Resp:
    def __init__(self, body=b"", status=200, headers=None):
        self._b = io.BytesIO(body)
        self.status = status
        self.headers = _Headers(headers or {})

    def read(self, n=-1):
        return self._b.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeOpener:
    """HEAD reports full size; the first GET truncates (simulates COS drop)."""

    def __init__(self, data, truncate_first=True):
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
            body = body[: max(1, len(body) // 2)]  # drop the tail silently
        return _Resp(body, status, headers)


class TestEasyOcrResolve(unittest.TestCase):
    def setUp(self):
        self.data = Path(tempfile.mkdtemp(prefix="kbq-eom-data-"))
        self.bundle = Path(tempfile.mkdtemp(prefix="kbq-eom-bundle-"))
        self._env = patch.dict(os.environ, {
            "HERMESDESK_DATA_DIR": str(self.data),
            "HERMESDESK_BUNDLE_DIR": str(self.bundle),
        })
        self._env.start()
        self.addCleanup(self._env.stop)
        import shutil
        self.addCleanup(lambda: shutil.rmtree(self.data, ignore_errors=True))
        self.addCleanup(lambda: shutil.rmtree(self.bundle, ignore_errors=True))

    def _make_models(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        for name in _FILES:
            (root / name).write_bytes(b"x")

    def test_missing_when_nothing_present(self):
        self.assertFalse(eom.easyocr_present())
        self.assertFalse(eom.easyocr_downloaded())
        self.assertIsNone(eom.resolve_easyocr_dir())
        self.assertFalse(eom.easyocr_status()["downloaded"])

    def test_bundled_only(self):
        self._make_models(self.bundle / "docling-models" / "EasyOcr")
        self.assertTrue(eom.easyocr_present())
        self.assertFalse(eom.easyocr_downloaded())  # bundle != user download
        self.assertEqual(Path(eom.resolve_easyocr_dir()), self.bundle / "docling-models" / "EasyOcr")

    def test_user_download_preferred_over_bundle(self):
        self._make_models(self.bundle / "docling-models" / "EasyOcr")
        self._make_models(eom.user_easyocr_dir())
        self.assertTrue(eom.easyocr_downloaded())
        self.assertEqual(Path(eom.resolve_easyocr_dir()), eom.user_easyocr_dir())

    def test_delete_removes_user_copy(self):
        self._make_models(eom.user_easyocr_dir())
        self.assertTrue(eom.easyocr_downloaded())
        out = eom.delete_easyocr()
        self.assertTrue(out["removed"])
        self.assertFalse(eom.easyocr_downloaded())


class TestEasyOcrExtract(unittest.TestCase):
    def test_extract_top_folder_layout(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            archive = root / "EasyOcr.zip"
            archive.write_bytes(_make_zip(top_folder=True))
            eom._extract_archive(archive, root)
            for name in _FILES:
                self.assertTrue((root / "EasyOcr" / name).is_file())

    def test_extract_flat_layout(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            archive = root / "EasyOcr.zip"
            archive.write_bytes(_make_zip(top_folder=False))
            eom._extract_archive(archive, root)
            for name in _FILES:
                self.assertTrue((root / "EasyOcr" / name).is_file())


class TestEasyOcrDownload(unittest.TestCase):
    def test_resumable_download_recovers_from_truncation(self):
        payload = b"0123456789" * 5000  # 50 KB
        opener = _FakeOpener(payload, truncate_first=True)
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "EasyOcr.zip.tmp"
            with patch.object(eom, "urlopen", opener):
                eom._download_archive("http://x/EasyOcr.zip", dest, progress_cb=None)
            self.assertEqual(dest.read_bytes(), payload)
            self.assertGreaterEqual(opener.get_calls, 2)  # resumed at least once

    def test_blocking_download_extracts(self):
        data = Path(tempfile.mkdtemp(prefix="kbq-eom-dl-"))
        env = patch.dict(os.environ, {"HERMESDESK_DATA_DIR": str(data)})
        env.start()
        self.addCleanup(env.stop)
        import shutil
        self.addCleanup(lambda: shutil.rmtree(data, ignore_errors=True))
        os.environ.pop("HERMESDESK_BUNDLE_DIR", None)

        opener = _FakeOpener(_make_zip(top_folder=True), truncate_first=True)
        with patch.object(eom, "urlopen", opener):
            res = eom.download_easyocr_blocking()
        self.assertTrue(res["ok"])
        self.assertTrue(eom.easyocr_downloaded())
        for name in _FILES:
            self.assertTrue((eom.user_easyocr_dir() / name).is_file())


if __name__ == "__main__":
    unittest.main()
