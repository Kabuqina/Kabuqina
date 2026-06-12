from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _build(profile: str = "paper_report", materials=None):
    from tools.material_index_tools import material_index_build

    return json.loads(material_index_build(profile=profile, materials=materials or []))


def test_material_index_builds_minimal_general_shape():
    result = _build(
        materials=[
            {
                "name": "paper.md",
                "kind": "text",
                "content": "# 校园节能系统\n\n系统用于集中展示校园能耗数据。",
                "metadata": {"engine": "fixture"},
            }
        ]
    )

    assert result["ok"] is True
    assert result["version"] == 1
    assert result["profile"] == "paper_report"
    assert result["source_files"][0]["id"] == "src_1"
    assert result["source_files"][0]["name"] == "paper.md"
    assert result["sections"]
    assert result["key_points"]
    assert "generation_hints" in result
    assert "ppt" in result["generation_hints"]
    assert "report" in result["generation_hints"]


def test_material_index_tool_is_in_documents_toolset():
    from toolsets import TOOLSETS

    assert "material_index_build" in TOOLSETS["documents"]["tools"]
    assert "pdf_write" in TOOLSETS["documents"]["tools"]


def test_material_index_extracts_markdown_sections_with_source_refs():
    result = _build(
        materials=[
            {
                "name": "course.md",
                "content": "# 第一章 绪论\n\n绿色校园建设背景。\n\n## 关键概念\n\n能耗统计、用能分析。",
            }
        ]
    )

    titles = [section["title"] for section in result["sections"]]
    assert "第一章 绪论" in titles
    assert "关键概念" in titles
    assert all(section["source_id"] == "src_1" for section in result["sections"])
    assert any("绿色校园建设背景" in section["text"] for section in result["sections"])


def test_material_index_extracts_markdown_tables():
    result = _build(
        materials=[
            {
                "name": "tests.md",
                "content": """
## 测试结果

| 模块 | 用例 | 结果 |
| --- | --- | --- |
| 仪表盘 | 时间筛选 | 通过 |
| 预警 | 阈值触发 | 通过 |
""",
            }
        ]
    )

    table = result["tables"][0]
    assert table["source_id"] == "src_1"
    assert table["headers"] == ["模块", "用例", "结果"]
    assert table["rows"][0] == ["仪表盘", "时间筛选", "通过"]
    assert "测试结果" in table["title"]


def test_material_index_extracts_figures_and_screenshot_cues():
    result = _build(
        materials=[
            {
                "name": "paper.md",
                "content": """
![系统截图](dashboard.png)

图 2 系统架构展示了前端、后端和数据库之间的关系。

运行结果界面显示能耗趋势。
""",
            }
        ]
    )

    assert any("系统截图" in item["title"] for item in result["screenshots"])
    assert any("系统架构" in item["text"] for item in result["figures"])
    assert result["generation_hints"]["missing_assets"] == []


def test_material_index_extracts_code_profile_cues():
    result = _build(
        profile="code_defense",
        materials=[
            {"name": "README.md", "kind": "text", "content": "# 项目说明\n\nSpring Boot 校园节能系统。"},
            {"name": "src/main/java/App.java", "kind": "code", "content": "public class App {}"},
            {"name": "pom.xml", "kind": "code", "content": "<project></project>"},
        ],
    )

    names = [item["name"] for item in result["code_files"]]
    assert "src/main/java/App.java" in names
    assert "pom.xml" in names
    assert any("README" in item["title"] for item in result["evidence"])
    assert "screenshot_placeholder" in result["generation_hints"]["ppt"]["recommended_slide_types"]


def test_material_index_bounds_snippets_and_records_uncertainty():
    long_text = "识别不清：" + ("校园能耗数据" * 200)
    result = _build(
        materials=[
            {
                "name": "ocr.md",
                "content": f"# OCR 材料\n\n{long_text}\n\nOCR uncertain near table 2.",
            }
        ]
    )

    assert result["uncertain_parts"]
    assert any("识别不清" in item["text"] for item in result["uncertain_parts"])
    assert all(len(item.get("text", "")) <= 360 for item in result["key_points"])


def test_material_index_can_load_material_content_from_read_cache(tmp_path, monkeypatch):
    from tools.document_tools import _persist_read_result

    monkeypatch.setenv("HERMESDESK_DATA_DIR", str(tmp_path / "data"))
    read_id, _cache_path = _persist_read_result(
        {
            "ok": True,
            "path": str(tmp_path / "paper.md"),
            "engine": "fixture",
            "content": "# 缓存材料\n\nMaterial Index 可以按 read_id 读取内容。",
            "metadata": {"kind": "markdown"},
        }
    )

    result = _build(
        materials=[
            {
                "name": "paper.md",
                "read_id": read_id,
                "metadata": {"engine": "fixture"},
            }
        ]
    )

    assert result["ok"] is True
    assert result["source_files"][0]["metadata"]["read_id"] == read_id
    assert any("缓存材料" in section["title"] for section in result["sections"])
