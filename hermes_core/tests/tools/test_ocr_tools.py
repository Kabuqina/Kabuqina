import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image


def _write_png(path):
    Image.new("RGB", (8, 8), color="white").save(path, format="PNG")


def test_ocr_image_uses_bundled_easyocr_models(tmp_path, monkeypatch):
    model_dir = tmp_path / "runtime" / "docling-models" / "EasyOcr"
    model_dir.mkdir(parents=True)
    (model_dir / "craft_mlt_25k.pth").write_bytes(b"detector")
    (model_dir / "english_g2.pth").write_bytes(b"recognizer")
    monkeypatch.setenv("HERMESDESK_BUNDLE_DIR", str(tmp_path / "runtime"))

    img = tmp_path / "sample.png"
    _write_png(img)

    fake_reader = MagicMock()
    fake_reader.readtext.return_value = [
        ([[np.int32(0), np.int32(0)], [4, 0], [4, 4], [0, 4]], "Hello", np.float32(0.98)),
        ([[0, 5], [4, 5], [4, 7], [0, 7]], "World", 0.87),
    ]

    fake_easyocr = SimpleNamespace(Reader=MagicMock(return_value=fake_reader))
    monkeypatch.setitem(sys.modules, "easyocr", fake_easyocr)

    from tools.ocr_tools import ocr_image_tool, reset_easyocr_reader_cache

    reset_easyocr_reader_cache()
    result = json.loads(ocr_image_tool(str(img)))

    assert result["success"] is True
    assert result["engine"] == "easyocr"
    assert result["model_dir"] == str(model_dir)
    assert result["text"] == "Hello\nWorld"
    assert result["lines"][0]["confidence"] == pytest.approx(0.98)
    assert result["lines"][0]["bbox"] == [[0, 0], [4, 0], [4, 4], [0, 4]]
    fake_easyocr.Reader.assert_called_once_with(
        ["en"],
        gpu=False,
        model_storage_directory=str(model_dir),
        download_enabled=False,
    )
    fake_reader.readtext.assert_called_once_with(str(img), detail=1, paragraph=False)


def test_ocr_image_rejects_non_image_file(tmp_path):
    text_file = tmp_path / "note.txt"
    text_file.write_text("not an image", encoding="utf-8")

    from tools.ocr_tools import ocr_image_tool

    result = json.loads(ocr_image_tool(str(text_file)))

    assert result["success"] is False
    assert result["error_type"] == "unsupported_image"


def test_ocr_image_reports_missing_model_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMESDESK_BUNDLE_DIR", str(tmp_path / "runtime"))
    img = tmp_path / "sample.png"
    _write_png(img)

    from tools.ocr_tools import ocr_image_tool, reset_easyocr_reader_cache

    reset_easyocr_reader_cache()
    result = json.loads(ocr_image_tool(str(img)))

    assert result["success"] is False
    assert result["error_type"] == "easyocr_models_missing"
    assert "EasyOcr" in result["message"]


def test_ocr_image_registered_and_in_vision_toolset():
    import tools.ocr_tools  # noqa: F401
    from tools.registry import registry
    from toolsets import TOOLSETS, _KABUQINA_CORE_TOOLS

    entry = registry._tools.get("ocr_image")

    assert entry is not None
    assert entry.toolset == "vision"
    assert entry.schema["name"] == "ocr_image"
    assert "ocr_image" in TOOLSETS["vision"]["tools"]
    assert "ocr_image" in _KABUQINA_CORE_TOOLS
