# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Tests for the EasyOCR resolver auto-download overlay."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
OVERLAYS_DIR = Path(__file__).resolve().parents[1] / "overlays"
CORE_DIR = Path(__file__).resolve().parents[2] / "hermes_core"
for path in (SRC_DIR, OVERLAYS_DIR, CORE_DIR):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)


class EasyOcrAutoDownloadOverlayTests(unittest.TestCase):
    def test_missing_resolver_starts_background_download_without_blocking(self):
        import easyocr_autodownload
        from tools import ocr_tools

        original = ocr_tools.resolve_easyocr_model_dir
        self.addCleanup(setattr, ocr_tools, "resolve_easyocr_model_dir", original)
        self.addCleanup(setattr, easyocr_autodownload, "_INSTALLED", False)

        def missing():
            return None

        ocr_tools.resolve_easyocr_model_dir = missing
        easyocr_autodownload._INSTALLED = False

        with patch("load_packages.package_status", return_value={"downloaded": False}):
            with patch("load_packages.start_download_package", return_value={"job": {"status": "running"}}) as start:
                easyocr_autodownload.install()
                result = ocr_tools.resolve_easyocr_model_dir()

        self.assertIsNone(result)
        start.assert_called_once_with("easyocr")


if __name__ == "__main__":
    unittest.main()
