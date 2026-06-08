from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _require_pptx() -> None:
    try:
        from pptx import Presentation  # noqa: F401
    except Exception as exc:
        pytest.skip(f"python-pptx unavailable: {exc}")


def _slide_text(slide) -> str:
    parts = []
    for shape in slide.shapes:
        if getattr(shape, "has_text_frame", False):
            parts.append(shape.text)
        if getattr(shape, "has_table", False):
            for row in shape.table.rows:
                for cell in row.cells:
                    parts.append(cell.text)
    return "\n".join(part for part in parts if part)


def test_pdf_read_precise_rejects_paths_outside_workspace(tmp_path, monkeypatch):
    from tools.document_tools import pdf_read_precise

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setenv("HERMESDESK_WORKSPACE", str(workspace))
    result = json.loads(pdf_read_precise(path=str(outside)))

    assert result.get("code") == "outside_workspace"
    assert "workspace" in result
    assert "terminal" in result.get("hint", "").lower()


def test_pptx_write_creates_openable_deck(tmp_path):
    _require_pptx()
    from tools.document_tools import pptx_write

    out = tmp_path / "student-report.pptx"
    result = json.loads(
        pptx_write(
            path=str(out),
            title="课设答辩",
            slides=[
                {"title": "项目目标", "bullets": ["完成 PDF 精确识别", "生成可提交 PPT"]},
                {"title": "实现方案", "bullets": ["Docling 解析", "大纲确认后生成"]},
            ],
            template="code_defense",
            visual_master="neo_grid_bold",
        )
    )

    assert result["ok"] is True
    assert result["slide_count"] == 3
    assert result["template"] == "code_defense"
    assert result["theme"] == "项目答辩"
    assert result["visual_master"] == "neo_grid_bold"
    assert result["visual_master_renderer"] in {"html_background_master_v1", "native_v1"}
    assert out.exists()

    from pptx import Presentation

    prs = Presentation(str(out))
    assert len(prs.slides) == 3
    assert "课设答辩" in prs.slides[0].shapes.title.text
    assert len(prs.slides[0].shapes) >= 4


def test_pptx_write_preserves_simple_slide_schema_with_notes(tmp_path):
    _require_pptx()
    from tools.document_tools import pptx_write

    out = tmp_path / "simple-schema.pptx"
    result = json.loads(
        pptx_write(
            path=str(out),
            title="简单格式",
            slides=[
                {
                    "title": "研究背景",
                    "bullets": ["校园能耗管理需要集中展示", "传统表格统计滞后"],
                    "notes": "讲稿：解释为什么需要系统。",
                }
            ],
            template="paper_report",
        )
    )

    assert result["ok"] is True
    assert out.exists()

    from pptx import Presentation

    prs = Presentation(str(out))
    assert len(prs.slides) == 2
    assert "研究背景" in _slide_text(prs.slides[1])
    assert "校园能耗管理需要集中展示" in _slide_text(prs.slides[1])
    assert "讲稿：解释为什么需要系统。" in prs.slides[1].notes_slide.notes_text_frame.text


def test_pptx_write_renders_structured_student_slide_types(tmp_path):
    _require_pptx()
    from tools.document_tools import pptx_write

    out = tmp_path / "structured-student.pptx"
    result = json.loads(
        pptx_write(
            path=str(out),
            title="高质量可交付 PPT",
            slides=[
                {
                    "slide_type": "agenda",
                    "title": "汇报提纲",
                    "bullets": ["研究背景", "系统设计", "测试结果"],
                },
                {
                    "slide_type": "claim_bullets",
                    "title": "系统解决能耗数据分散问题",
                    "subtitle": "核心价值",
                    "bullets": ["统一采集口径", "可视化分析", "异常阈值预警"],
                },
                {
                    "slide_type": "diagram",
                    "title": "系统架构",
                    "diagram": {
                        "nodes": ["Vue 前端", "Spring Boot API", "MySQL 数据库"],
                    },
                },
                {
                    "slide_type": "table",
                    "title": "测试用例汇总",
                    "table": {
                        "headers": ["模块", "用例", "结果"],
                        "rows": [["仪表盘", "时间筛选", "通过"], ["预警", "阈值触发", "通过"]],
                    },
                },
                {
                    "slide_type": "screenshot_placeholder",
                    "title": "系统运行截图",
                    "placeholder": {
                        "label": "待放入仪表盘截图",
                        "caption": "展示电、水、气总览与趋势图",
                        "source_hint": "从系统首页截取真实运行画面。",
                    },
                },
                {
                    "slide_type": "chart_placeholder",
                    "title": "能耗趋势图",
                    "placeholder": {
                        "label": "待放入 ECharts 趋势图",
                        "caption": "对比不同建筑的月度电耗变化",
                    },
                },
                {
                    "slide_type": "qa_backup",
                    "title": "备用：老师可能追问",
                    "bullets": ["为什么使用规则阈值", "如何保证权限边界"],
                    "notes": "备用讲稿。",
                },
                {
                    "slide_type": "closing",
                    "title": "总结",
                    "bullets": ["系统流程完整", "后续可接入真实采集设备"],
                },
            ],
            template="paper_report",
        )
    )

    assert result["ok"] is True

    from pptx import Presentation

    prs = Presentation(str(out))
    assert len(prs.slides) == 9
    deck_text = "\n".join(_slide_text(slide) for slide in prs.slides)
    for expected in [
        "1. 研究背景",
        "核心价值",
        "Vue 前端",
        "Spring Boot API",
        "测试用例汇总",
        "待放入仪表盘截图",
        "展示电、水、气总览与趋势图",
        "待放入 ECharts 趋势图",
        "备用",
        "系统流程完整",
    ]:
        assert expected in deck_text
    assert "从系统首页截取真实运行画面。" in prs.slides[5].notes_slide.notes_text_frame.text


def test_pptx_write_unknown_slide_type_falls_back_to_bullets(tmp_path):
    _require_pptx()
    from tools.document_tools import pptx_write

    out = tmp_path / "unknown-slide-type.pptx"
    result = json.loads(
        pptx_write(
            path=str(out),
            title="未知类型",
            slides=[
                {
                    "slide_type": "mystery",
                    "title": "仍然生成",
                    "bullets": ["未知类型应回退到普通要点页"],
                }
            ],
            template="course_report",
        )
    )

    assert result["ok"] is True

    from pptx import Presentation

    prs = Presentation(str(out))
    assert "未知类型应回退到普通要点页" in _slide_text(prs.slides[1])


def test_pptx_write_templates_apply_distinct_backgrounds(tmp_path):
    _require_pptx()
    from tools.document_tools import _PPTX_THEMES, pptx_write

    slides = [{"title": "章节", "bullets": ["要点 A"]}]
    backgrounds = {}
    for key, theme in _PPTX_THEMES.items():
        out = tmp_path / f"{key}.pptx"
        result = json.loads(
            pptx_write(path=str(out), title="演示标题", slides=slides, template=key)
        )
        assert result["template"] == key
        assert result["theme"] == theme.badge

        from pptx import Presentation

        prs = Presentation(str(out))
        fill = prs.slides[1].background.fill
        assert fill.type is not None
        rgb = fill.fore_color.rgb
        backgrounds[key] = tuple(rgb)
        assert backgrounds[key] == theme.bg

    assert len(set(backgrounds.values())) == 3


def test_pptx_write_unknown_template_falls_back_to_course_report(tmp_path):
    _require_pptx()
    from tools.document_tools import pptx_write

    out = tmp_path / "fallback.pptx"
    result = json.loads(
        pptx_write(
            path=str(out),
            title="测试",
            slides=[{"title": "页", "bullets": ["内容"]}],
            template="unknown_style",
        )
    )
    assert result["template"] == "course_report"


def test_pptx_write_unknown_visual_master_falls_back_to_default_native(tmp_path):
    _require_pptx()
    from tools.document_tools import pptx_write

    out = tmp_path / "fallback-visual-master.pptx"
    result = json.loads(
        pptx_write(
            path=str(out),
            title="测试",
            slides=[{"title": "页", "bullets": ["内容"]}],
            template="course_report",
            visual_master="unknown-master",
        )
    )

    assert result["ok"] is True
    assert result["visual_master"] == "default_native"
    assert result["visual_master_name"] == "Default native renderer"


def test_pdf_read_precise_falls_back_to_pypdf(tmp_path):
    from pypdf import PdfWriter
    from tools.document_tools import pdf_read_precise

    pdf = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with pdf.open("wb") as f:
        writer.write(f)

    result = json.loads(pdf_read_precise(path=str(pdf)))

    assert result["ok"] is True
    assert result["engine"] in {"docling", "pypdf"}
    assert result["pages"] == 1
    if result["engine"] == "pypdf":
        assert "Docling" in result["warning"]
        assert "docling_error" in result


def test_docling_converter_is_cached(monkeypatch):
    import tools.document_tools as document_tools

    calls = []

    class FakeConverter:
        pass

    def fake_create(profile="fast"):
        calls.append("create")
        return FakeConverter()

    document_tools.reset_docling_converter_cache()
    monkeypatch.setattr(document_tools, "_create_docling_converter", fake_create)

    first = document_tools._get_docling_converter()
    second = document_tools._get_docling_converter()

    assert first is second
    assert calls == ["create"]
    document_tools.reset_docling_converter_cache()


def test_docling_profile_for_mode_defaults_to_fast():
    from tools.document_tools import _docling_profile_for_mode

    assert _docling_profile_for_mode("auto") == "fast"
    assert _docling_profile_for_mode("") == "fast"
    assert _docling_profile_for_mode("precise") == "precise"


def test_docling_profile_for_mode_supports_math():
    from tools.document_tools import _docling_profile_for_mode

    assert _docling_profile_for_mode("math") == "math"
    assert _docling_profile_for_mode("MATH") == "math"


def test_configure_pdf_pipeline_options_enables_formula_for_math():
    import tools.document_tools as document_tools

    class Options:
        do_ocr = True
        do_table_structure = True
        do_code_enrichment = False
        do_formula_enrichment = False

    fast = Options()
    document_tools._configure_pdf_pipeline_options(fast, "fast")
    assert fast.do_formula_enrichment is False
    assert fast.do_code_enrichment is False

    math = Options()
    document_tools._configure_pdf_pipeline_options(math, "math")
    assert math.do_formula_enrichment is True
    assert math.do_code_enrichment is False


def test_require_math_artifacts_raises_without_codeformula(tmp_path, monkeypatch):
    import tools.document_tools as document_tools

    bundle = tmp_path / "bundle"
    (bundle / "docling-models").mkdir(parents=True)
    monkeypatch.setenv("HERMESDESK_BUNDLE_DIR", str(bundle))
    monkeypatch.delenv("DOCLING_ARTIFACTS_PATH", raising=False)

    with pytest.raises(ValueError, match="mode=math requires offline CodeFormula"):
        document_tools._require_math_artifacts_bundled()


def test_ensure_math_artifacts_uses_desktop_first_use_download(monkeypatch):
    import docling_math_models
    import tools.document_tools as document_tools

    calls = []

    def fake_ensure():
        calls.append("ensure")

    monkeypatch.setattr(docling_math_models, "ensure_code_formula_available_for_math", fake_ensure)

    document_tools._ensure_math_artifacts()

    assert calls == ["ensure"]


def test_format_docling_error_surfaces_settings_hint_for_missing_model():
    from tools.document_tools import _format_docling_error

    try:
        from docling_math_models import CodeFormulaMissingError
    except ImportError:
        pytest.skip("docling_math_models not on path")

    msg = _format_docling_error(
        CodeFormulaMissingError(
            "code_formula_model_missing: mode=math requires ds4sd/CodeFormula (~500 MB). "
            "Download in Settings."
        )
    )
    assert "code_formula_model_missing" in msg
    assert "Settings" in msg


def test_read_document_precise_math_mode_does_not_fallback_on_missing_model(tmp_path, monkeypatch):
    import tools.document_tools as document_tools

    source = tmp_path / "formula.pdf"
    source.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setenv("HERMESDESK_WORKSPACE", str(tmp_path))

    try:
        from docling_math_models import CodeFormulaMissingError
    except ImportError:
        pytest.skip("docling_math_models not on path")

    def fake_read(_path: Path, _mode: str):
        raise CodeFormulaMissingError(
            "code_formula_model_missing: mode=math requires ds4sd/CodeFormula (~500 MB). "
            "Download in Settings."
        )

    monkeypatch.setattr(document_tools, "_read_with_docling", fake_read)

    result = json.loads(document_tools.document_read_precise(path=str(source), mode="math"))

    assert result["ok"] is False
    assert result["code"] == "docling_math_unavailable"
    assert "code_formula_model_missing" in result["docling_error"]
    assert "Settings" in result["docling_error"]


def test_prime_torch_keeps_existing_modules_on_failure(monkeypatch):
    import sys
    import types
    import tools.document_tools as document_tools

    fake_torch = types.ModuleType("torch")
    fake_child = types.ModuleType("torch.partial")
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "torch.partial", fake_child)

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "torch":
            return fake_torch
        if name == "torch.library":
            raise AttributeError("partially initialized module 'torch' has no attribute 'library'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(AttributeError):
        document_tools._prime_torch_for_docling()

    assert sys.modules["torch"] is fake_torch
    assert sys.modules["torch.partial"] is fake_child


def test_document_read_precise_routes_docx_through_docling(tmp_path, monkeypatch):
    import tools.document_tools as document_tools

    docx = tmp_path / "brief.docx"
    docx.write_bytes(b"fake docx")

    def fake_read(path: Path, mode: str):
        return {
            "ok": True,
            "engine": "docling",
            "mode": mode,
            "path": str(path),
            "pages": 0,
            "content": "Docling DOCX content",
        }

    monkeypatch.setattr(document_tools, "_read_with_docling", fake_read)

    result = json.loads(document_tools.document_read_precise(path=str(docx), mode="precise"))

    assert result["ok"] is True
    assert result["engine"] == "docling"
    assert result["mode"] == "precise"
    assert result["content"] == "Docling DOCX content"


def test_document_read_precise_math_mode_uses_docling_even_for_lightweight_suffix(tmp_path, monkeypatch):
    import tools.document_tools as document_tools

    source = tmp_path / "formula.md"
    source.write_text("Euler: $e^{i\\pi}+1=0$", encoding="utf-8")
    bundle = tmp_path / "bundle"
    formula = bundle / "docling-models" / "ds4sd--CodeFormula"
    formula.mkdir(parents=True)
    (formula / "model.safetensors").write_bytes(b"x")
    monkeypatch.setenv("HERMESDESK_BUNDLE_DIR", str(bundle))
    monkeypatch.setenv("HERMESDESK_WORKSPACE", str(tmp_path))
    monkeypatch.delenv("DOCLING_ARTIFACTS_PATH", raising=False)

    def fake_read(path: Path, mode: str):
        return {
            "ok": True,
            "engine": "docling",
            "mode": mode,
            "profile": "math",
            "path": str(path),
            "content": "$$e^{i\\pi}+1=0$$",
        }

    monkeypatch.setattr(document_tools, "_read_with_docling", fake_read)

    result = json.loads(document_tools.document_read_precise(path=str(source), mode="math"))

    assert result["ok"] is True
    assert result["engine"] == "docling"
    assert result["profile"] == "math"
    assert result["metadata"]["kind"] == "markdown"
    assert "$$e^{i\\pi}+1=0$$" in result["content"]


def test_document_read_precise_rejects_legacy_doc_with_hint(tmp_path):
    from tools.document_tools import document_read_precise

    doc = tmp_path / "legacy.doc"
    doc.write_bytes(b"not really a Word binary")

    result = json.loads(document_read_precise(path=str(doc)))

    assert result["ok"] is False
    assert result["code"] == "unsupported_legacy_doc"
    assert "LibreOffice" in result["hint"]


def test_run_on_docling_thread_serializes_calls():
    from tools import document_tools

    seen: list[int] = []

    def _record(value: int) -> int:
        seen.append(value)
        return value

    assert document_tools._run_on_docling_thread(_record, 1) == 1
    assert document_tools._run_on_docling_thread(_record, 2) == 2
    assert seen == [1, 2]


def test_format_docling_error_surfaces_network_failures():
    from tools.document_tools import _format_docling_error

    msg = _format_docling_error(
        ConnectionError("Connection to huggingface.co timed out.")
    )
    assert "Docling model load failed" in msg
    assert "huggingface.co" in msg


def test_format_docling_error_flags_unsupported_torch_runtime():
    from tools.document_tools import _format_docling_error

    msg = _format_docling_error(
        AttributeError(
            "partially initialized module 'torch' has no attribute 'library' "
            "(most likely due to a circular import)"
        )
    )
    assert "environment problem" in msg
    assert "3.11" in msg


def test_format_docling_error_flags_pdfium_page_count_failure():
    from tools.document_tools import _format_docling_error

    msg = _format_docling_error(ValueError("Inconsistent number of pages: 73!=-1"))
    assert "environment problem" in msg
    assert "3.11" in msg


def test_format_docling_error_flags_duplicate_torch_kernel_registration():
    from tools.document_tools import _format_docling_error

    msg = _format_docling_error(
        RuntimeError(
            "This is not allowed since there's already a kernel registered from python "
            "overriding wait_tensor's behavior for Autograd dispatch key and "
            "_c10d_functional namespace."
        )
    )
    assert "environment problem" in msg
    assert "restart" in msg.lower()


def test_format_docling_error_surfaces_path_policy_blocks():
    from tools.document_tools import _format_docling_error

    msg = _format_docling_error(
        PermissionError(
            "Kabuqina path policy blocked read to \\\\.\\nul\\ "
            "(allowed root: C:\\\\Users\\\\X13\\\\Documents\\\\KabuqinaWork)"
        )
    )
    assert "path policy" in msg.lower() or "PathPolicy" in msg or "blocked read" in msg


def test_resolve_docling_artifacts_path_from_bundle_env(tmp_path, monkeypatch):
    from tools.document_tools import _resolve_docling_artifacts_path

    models = tmp_path / "docling-models"
    models.mkdir()
    monkeypatch.setenv("HERMESDESK_BUNDLE_DIR", str(tmp_path))
    monkeypatch.delenv("DOCLING_ARTIFACTS_PATH", raising=False)

    assert _resolve_docling_artifacts_path() == models


def test_document_read_precise_fast_text_skips_docling_and_writes_read_cache(tmp_path, monkeypatch):
    import tools.document_tools as document_tools

    data_dir = tmp_path / "data"
    source = tmp_path / "notes.md"
    source.write_text("# 标题\n\nRead 层应该快速读取 markdown。", encoding="utf-8")

    monkeypatch.setenv("HERMESDESK_DATA_DIR", str(data_dir))

    def fail_docling(path: Path, mode: str):
        raise AssertionError("fast markdown reads should not initialize Docling")

    monkeypatch.setattr(document_tools, "_read_with_docling", fail_docling)

    result = json.loads(document_tools.document_read_precise(path=str(source), mode="auto"))

    assert result["ok"] is True
    assert result["engine"] == "text"
    assert result["read_id"]
    assert result["cache_path"].startswith(str(data_dir))
    assert result["metadata"]["kind"] == "markdown"
    assert result["content"].startswith("# 标题")


def test_document_read_precise_include_content_false_returns_cache_handle(tmp_path, monkeypatch):
    import tools.document_tools as document_tools

    monkeypatch.setenv("HERMESDESK_DATA_DIR", str(tmp_path / "data"))
    source = tmp_path / "brief.txt"
    source.write_text("这是一份较长材料的正文。", encoding="utf-8")

    result = json.loads(
        document_tools.document_read_precise(path=str(source), mode="fast", include_content=False)
    )

    assert result["ok"] is True
    assert result["read_id"]
    assert result["content"] == ""
    assert result["content_omitted"] is True
    assert Path(result["cache_path"]).exists()


def test_document_read_precise_large_output_surfaces_cache_hint_before_content(tmp_path, monkeypatch):
    import tools.document_tools as document_tools

    monkeypatch.setenv("HERMESDESK_DATA_DIR", str(tmp_path / "data"))
    source = tmp_path / "formula.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    payload = {
        "ok": True,
        "engine": "docling",
        "mode": "math",
        "content": "x" * 120_000,
    }

    result = document_tools._finalize_read_payload(payload, source, include_content=True)
    serialized = document_tools._json(result)

    assert result["content_hint"]
    assert "read_file" in result["content_hint"]
    assert "vision_analyze" in result["content_hint"]
    assert serialized.index('"content_hint"') < serialized.index('"content"')


def test_pdf_read_precise_uses_common_read_pipeline_for_pdf(tmp_path, monkeypatch):
    import tools.document_tools as document_tools

    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    calls = []

    def fake_read(path: Path, *, mode: str, include_content: bool):
        calls.append((path, mode, include_content))
        return {"ok": True, "path": str(path), "engine": "fixture", "content": "PDF text"}

    monkeypatch.setattr(document_tools, "_read_document_precise_payload", fake_read)

    result = json.loads(document_tools.pdf_read_precise(path=str(pdf), mode="precise", include_content=False))

    assert result["ok"] is True
    assert result["content"] == "PDF text"
    assert calls == [(pdf, "precise", False)]


def test_read_tool_schemas_advertise_math_mode():
    from tools.document_tools import DOCUMENT_READ_PRECISE_SCHEMA, PDF_READ_PRECISE_SCHEMA

    assert "math" in PDF_READ_PRECISE_SCHEMA["parameters"]["properties"]["mode"]["description"]
    assert "math" in DOCUMENT_READ_PRECISE_SCHEMA["parameters"]["properties"]["mode"]["description"]
