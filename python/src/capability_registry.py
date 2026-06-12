# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""First-party product capability definitions for Kabuqina Desktop."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

VALID_CAPABILITY_STATUSES = (
    "candidate",
    "available",
    "missing_package",
    "downloading",
    "package_error",
    "disabled_toolset",
    "requires_power_user",
    "unsupported_platform",
    "error",
)

VALID_FRAMEWORK_STAGES = ("reader", "material_index", "planner", "writer")


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _derive_fields(capability: dict[str, Any]) -> dict[str, Any]:
    pipelines = list(capability.get("pipelines") or [])
    stages: list[str] = []
    tools: list[str] = []
    required_packages: list[str] = []
    optional_packages: list[str] = []
    for pipeline in pipelines:
        stages.extend([str(stage) for stage in pipeline.get("stages") or []])
        for step in pipeline.get("steps") or []:
            stage = str(step.get("stage") or "")
            if stage:
                stages.append(stage)
            tool = str(step.get("tool") or "")
            if tool:
                tools.append(tool)
            tools.extend([str(tool) for tool in step.get("tools") or []])
            required_packages.extend([str(pkg) for pkg in step.get("required_load_packages") or []])
            optional_packages.extend([str(pkg) for pkg in step.get("optional_load_packages") or []])
    merged = dict(capability)
    merged["stages"] = _unique(stages)
    merged["tools"] = _unique(list(capability.get("tools") or []) + tools)
    merged["required_load_packages"] = _unique(
        list(capability.get("required_load_packages") or []) + required_packages
    )
    merged["optional_load_packages"] = _unique(
        list(capability.get("optional_load_packages") or []) + optional_packages
    )
    return merged


_CAPABILITIES: tuple[dict[str, Any], ...] = (
    {
        "id": "document-precise-read",
        "title": "Precise document reading",
        "description": "Read PDFs and documents with layout, tables, OCR hints, and structured extraction.",
        "category": "documents",
        "agent_hint": "Use for PDF, Word, and document understanding tasks that need structure beyond plain text.",
        "tools": ["pdf_read_precise", "document_read_precise"],
        "required_toolsets": ["documents"],
        "required_load_packages": [],
        "optional_load_packages": ["docling-codeformula"],
        "roles": ["default", "advanced", "power"],
        "risk": "low",
        "source": "builtin",
        "trust": "official",
        "pipelines": [
            {
                "id": "docling-precise-document-read",
                "title": "Docling precise document read",
                "primary": True,
                "stages": ["reader"],
                "inputs": ["pdf", "docx", "pptx", "xlsx", "html", "markdown", "csv", "image", "text"],
                "steps": [
                    {
                        "id": "read-document-precise",
                        "stage": "reader",
                        "tool": "document_read_precise",
                        "default_args": {"mode": "auto"},
                        "optional_load_packages": ["docling-codeformula"],
                        "outputs": ["read_id", "markdown", "metadata"],
                    }
                ],
            },
            {
                "id": "docling-precise-pdf-read",
                "title": "Docling precise PDF read",
                "primary": False,
                "stages": ["reader"],
                "inputs": ["pdf"],
                "steps": [
                    {
                        "id": "read-pdf-precise",
                        "stage": "reader",
                        "tool": "pdf_read_precise",
                        "default_args": {"mode": "auto"},
                        "optional_load_packages": ["docling-codeformula"],
                        "outputs": ["read_id", "markdown", "metadata"],
                    }
                ],
            },
        ],
    },
    {
        "id": "document-math",
        "title": "Formula extraction and LaTeX",
        "description": "Extract formulas and math notation from supported documents and images.",
        "category": "documents",
        "agent_hint": "Use when the user asks for formula recognition, math extraction, or LaTeX cleanup.",
        "tools": ["pdf_read_precise", "document_read_precise"],
        "required_toolsets": ["documents"],
        "required_load_packages": ["docling-codeformula"],
        "optional_load_packages": [],
        "roles": ["default", "advanced", "power"],
        "risk": "low",
        "source": "builtin",
        "trust": "official",
        "pipelines": [
            {
                "id": "docling-math-document-read",
                "title": "Docling math document read",
                "primary": True,
                "stages": ["reader"],
                "inputs": ["pdf", "docx", "pptx", "xlsx", "html", "markdown", "image"],
                "steps": [
                    {
                        "id": "read-document-math",
                        "stage": "reader",
                        "tool": "document_read_precise",
                        "default_args": {"mode": "math"},
                        "required_load_packages": ["docling-codeformula"],
                        "outputs": ["read_id", "markdown", "formulas"],
                    }
                ],
            },
            {
                "id": "docling-math-pdf-read",
                "title": "Docling math PDF read",
                "primary": False,
                "stages": ["reader"],
                "inputs": ["pdf"],
                "steps": [
                    {
                        "id": "read-pdf-math",
                        "stage": "reader",
                        "tool": "pdf_read_precise",
                        "default_args": {"mode": "math"},
                        "required_load_packages": ["docling-codeformula"],
                        "outputs": ["read_id", "markdown", "formulas"],
                    }
                ],
            },
        ],
        "shortcuts": [
            {
                "id": "extract-formulas",
                "surface": "chat_quick_action",
                "label": "Extract formulas",
                "entry_pipeline": "docling-math-document-read",
                "requires_input": ["document"],
                "visible_when": "pipeline_ready_or_downloadable",
            }
        ],
    },
    {
        "id": "voice-local-stt",
        "title": "Local speech recognition",
        "description": "Transcribe microphone input locally with whisper.cpp.",
        "category": "voice",
        "agent_hint": "Use for local voice input when the user has downloaded the STT model.",
        "tools": ["transcribe_audio"],
        "required_toolsets": [],
        "required_load_packages": ["local-stt-base-q5_1"],
        "optional_load_packages": [],
        "roles": ["default", "advanced", "power"],
        "risk": "low",
        "source": "builtin",
        "trust": "official",
        "pipelines": [
            {
                "id": "local-stt-audio-read",
                "title": "Local STT audio read",
                "primary": True,
                "stages": ["reader"],
                "inputs": ["audio"],
                "steps": [
                    {
                        "id": "transcribe-local-audio",
                        "stage": "reader",
                        "kind": "desktop_voice_input",
                        "required_load_packages": ["local-stt-base-q5_1"],
                        "outputs": ["transcript", "metadata"],
                    }
                ],
            }
        ],
        "shortcuts": [
            {
                "id": "voice-input",
                "surface": "settings_action",
                "label": "Enable local voice",
                "entry_pipeline": "local-stt-audio-read",
                "requires_input": ["audio"],
                "visible_when": "pipeline_ready_or_downloadable",
            }
        ],
    },
    {
        "id": "desktop-organizer",
        "title": "Desktop organization",
        "description": "Organize desktop files through the built-in desktop organizer workflow.",
        "category": "workspace",
        "agent_hint": "Use when the user asks Nana to clean or organize desktop files.",
        "tools": ["run_builtin_helper"],
        "required_toolsets": ["file"],
        "required_load_packages": [],
        "optional_load_packages": [],
        "roles": ["default", "advanced", "power"],
        "risk": "medium",
        "source": "builtin",
        "trust": "official",
        "pipelines": [
            {
                "id": "desktop-organizer-helper",
                "title": "Desktop organizer helper",
                "primary": True,
                "stages": ["reader", "planner", "writer"],
                "inputs": ["workspace"],
                "steps": [
                    {
                        "id": "inspect-desktop-files",
                        "stage": "reader",
                        "tool": "search_files",
                        "outputs": ["file_inventory"],
                    },
                    {
                        "id": "plan-file-organization",
                        "stage": "planner",
                        "kind": "agent_plan",
                        "inputs": ["file_inventory"],
                        "outputs": ["organization_plan"],
                    },
                    {
                        "id": "apply-file-organization",
                        "stage": "writer",
                        "tool": "run_builtin_helper",
                        "default_args": {"helper_id": "folder_organize"},
                        "inputs": ["organization_plan"],
                        "outputs": ["workspace_changes"],
                    },
                ],
            }
        ],
        "shortcuts": [
            {
                "id": "organize-desktop",
                "surface": "chat_quick_action",
                "label": "Organize files",
                "entry_pipeline": "desktop-organizer-helper",
                "requires_input": ["workspace"],
                "visible_when": "pipeline_ready",
            }
        ],
    },
    {
        "id": "student-ppt",
        "title": "Generate report (PPT)",
        "description": "Generate student-facing course, paper, and code-defense PPT reports with reviewed outlines and selectable visual masters.",
        "category": "documents",
        "family": "student-report-generation",
        "agent_hint": (
            "Use for student PPT report generation. First pick the report structure "
            "(course_report, paper_report, or code_defense), build/review the outline, "
            "then call pptx_write with the selected visual_master."
        ),
        "tools": ["material_index_build", "review_outline", "pptx_write"],
        "required_toolsets": ["documents", "clarify"],
        "required_load_packages": [],
        "optional_load_packages": ["docling-codeformula"],
        "structure_templates": [
            {
                "id": "course_report",
                "title": "Course report",
                "description": "课程学习汇报：知识结构、关键概念、案例/例题、对比流程、学习总结、难点备用问答。",
                "default_slide_types": [
                    "agenda",
                    "diagram",
                    "claim_bullets",
                    "table",
                    "chart_placeholder",
                    "qa_backup",
                    "closing",
                ],
            },
            {
                "id": "paper_report",
                "title": "Paper report",
                "description": "论文/文献汇报：背景问题、方法框架、关键证据、实验结果、贡献局限、展望与备用问答。",
                "default_slide_types": [
                    "agenda",
                    "claim_bullets",
                    "diagram",
                    "table",
                    "chart_placeholder",
                    "qa_backup",
                    "closing",
                ],
            },
            {
                "id": "code_defense",
                "title": "Code defense",
                "description": "课设/项目答辩：背景目标、总体架构、模块流程、运行截图、测试结果、问题改进、备用问答。",
                "default_slide_types": [
                    "agenda",
                    "diagram",
                    "screenshot_placeholder",
                    "table",
                    "chart_placeholder",
                    "qa_backup",
                    "closing",
                ],
            },
        ],
        "visual_masters": [
            {
                "id": "soft_editorial",
                "title": "Soft Editorial",
                "dir": "soft-editorial",
                "status": "available",
                "best_for": ["course_report", "paper_report"],
            },
            {
                "id": "blue_professional",
                "title": "Blue Professional",
                "dir": "blue-professional",
                "status": "available",
                "best_for": ["paper_report", "course_report", "code_defense"],
            },
            {
                "id": "signal",
                "title": "Signal",
                "dir": "signal",
                "status": "available",
                "best_for": ["paper_report", "course_report"],
            },
            {
                "id": "neo_grid_bold",
                "title": "Neo Grid Bold",
                "dir": "neo-grid-bold",
                "status": "available",
                "best_for": ["code_defense", "course_report"],
            },
            {
                "id": "editorial_forest",
                "title": "Editorial Forest",
                "dir": "editorial-forest",
                "status": "available",
                "best_for": ["paper_report", "course_report"],
            },
        ],
        "roles": ["default", "advanced", "power"],
        "risk": "medium",
        "source": "builtin",
        "trust": "official",
        "pipelines": [
            {
                "id": "student-course-report-ppt",
                "title": "Generate course report PPT",
                "primary": True,
                "stages": ["reader", "material_index", "planner", "writer"],
                "inputs": ["document"],
                "structure_template": "course_report",
                "visual_master_required": True,
                "steps": [
                    {
                        "id": "read-student-material",
                        "stage": "reader",
                        "tools": ["pdf_read_precise", "document_read_precise"],
                        "default_args": {"mode": "auto", "include_content": False},
                        "optional_load_packages": ["docling-codeformula"],
                        "outputs": ["read_id", "markdown", "metadata"],
                    },
                    {
                        "id": "build-material-index",
                        "stage": "material_index",
                        "tool": "material_index_build",
                        "default_args": {"profile": "course_report"},
                        "inputs": ["read_id"],
                        "outputs": ["material_index"],
                    },
                    {
                        "id": "review-ppt-outline",
                        "stage": "planner",
                        "kind": "agent_review",
                        "requires_user_review": True,
                        "inputs": ["material_index"],
                        "outputs": ["outline"],
                    },
                    {
                        "id": "select-ppt-visual-master",
                        "stage": "planner",
                        "kind": "user_select_visual_master",
                        "requires_user_review": True,
                        "inputs": ["outline"],
                        "outputs": ["visual_master"],
                    },
                    {
                        "id": "write-student-ppt",
                        "stage": "writer",
                        "tool": "pptx_write",
                        "default_args": {"template": "course_report", "visual_master": "soft_editorial"},
                        "inputs": ["outline", "material_index", "visual_master"],
                        "outputs": ["pptx_path", "visual_master"],
                    },
                ],
            },
            {
                "id": "student-paper-report-ppt",
                "title": "Generate paper report PPT",
                "primary": False,
                "stages": ["reader", "material_index", "planner", "writer"],
                "inputs": ["document", "pdf", "markdown"],
                "structure_template": "paper_report",
                "visual_master_required": True,
                "steps": [
                    {
                        "id": "read-paper-material",
                        "stage": "reader",
                        "tools": ["pdf_read_precise", "document_read_precise"],
                        "default_args": {"mode": "auto", "include_content": False},
                        "optional_load_packages": ["docling-codeformula"],
                        "outputs": ["read_id", "markdown", "metadata"],
                    },
                    {
                        "id": "build-paper-material-index",
                        "stage": "material_index",
                        "tool": "material_index_build",
                        "default_args": {"profile": "paper_report"},
                        "inputs": ["read_id"],
                        "outputs": ["material_index"],
                    },
                    {
                        "id": "review-paper-ppt-outline",
                        "stage": "planner",
                        "kind": "agent_review",
                        "requires_user_review": True,
                        "inputs": ["material_index"],
                        "outputs": ["outline"],
                    },
                    {
                        "id": "select-ppt-visual-master",
                        "stage": "planner",
                        "kind": "user_select_visual_master",
                        "requires_user_review": True,
                        "inputs": ["outline"],
                        "outputs": ["visual_master"],
                    },
                    {
                        "id": "write-paper-ppt",
                        "stage": "writer",
                        "tool": "pptx_write",
                        "default_args": {"template": "paper_report", "visual_master": "blue_professional"},
                        "inputs": ["outline", "material_index", "visual_master"],
                        "outputs": ["pptx_path", "visual_master"],
                    },
                ],
            },
            {
                "id": "student-code-defense-ppt",
                "title": "Generate code-defense PPT",
                "primary": False,
                "stages": ["reader", "material_index", "planner", "writer"],
                "inputs": ["workspace", "code", "document"],
                "structure_template": "code_defense",
                "visual_master_required": True,
                "steps": [
                    {
                        "id": "inspect-code-defense-material",
                        "stage": "reader",
                        "tools": ["document_read_precise"],
                        "default_args": {"mode": "auto", "include_content": False},
                        "outputs": ["read_id", "markdown", "metadata"],
                    },
                    {
                        "id": "build-code-defense-material-index",
                        "stage": "material_index",
                        "tool": "material_index_build",
                        "default_args": {"profile": "code_defense"},
                        "inputs": ["read_id"],
                        "outputs": ["material_index"],
                    },
                    {
                        "id": "review-code-defense-ppt-outline",
                        "stage": "planner",
                        "kind": "agent_review",
                        "requires_user_review": True,
                        "inputs": ["material_index"],
                        "outputs": ["outline"],
                    },
                    {
                        "id": "select-ppt-visual-master",
                        "stage": "planner",
                        "kind": "user_select_visual_master",
                        "requires_user_review": True,
                        "inputs": ["outline"],
                        "outputs": ["visual_master"],
                    },
                    {
                        "id": "write-code-defense-ppt",
                        "stage": "writer",
                        "tool": "pptx_write",
                        "default_args": {"template": "code_defense", "visual_master": "neo_grid_bold"},
                        "inputs": ["outline", "material_index", "visual_master"],
                        "outputs": ["pptx_path", "visual_master"],
                    },
                ],
            }
        ],
        "shortcuts": [
            {
                "id": "create-course-report-ppt",
                "surface": "wizard",
                "label": "Course report PPT",
                "entry_pipeline": "student-course-report-ppt",
                "requires_input": ["document"],
                "visible_when": "pipeline_ready_or_downloadable",
            },
            {
                "id": "create-paper-report-ppt",
                "surface": "wizard",
                "label": "Paper report PPT",
                "entry_pipeline": "student-paper-report-ppt",
                "requires_input": ["document"],
                "visible_when": "pipeline_ready_or_downloadable",
            },
            {
                "id": "create-code-defense-ppt",
                "surface": "wizard",
                "label": "Code-defense PPT",
                "entry_pipeline": "student-code-defense-ppt",
                "requires_input": ["document"],
                "visible_when": "pipeline_ready_or_downloadable",
            }
        ],
    },
    {
        "id": "document-pdf-generation",
        "title": "Generate document (PDF)",
        "description": "Generate print-ready PDF documents from structured writer-layer content with an HTML source sidecar.",
        "category": "documents",
        "family": "document-generation",
        "agent_hint": (
            "Use when the user asks for a PDF deliverable. Build a structured document "
            "with sections or blocks, then call pdf_write. It saves both the PDF and "
            "an inspectable HTML source file."
        ),
        "tools": ["pdf_write"],
        "required_toolsets": ["documents"],
        "required_load_packages": [],
        "optional_load_packages": [],
        "roles": ["default", "advanced", "power"],
        "risk": "medium",
        "source": "builtin",
        "trust": "official",
        "pipelines": [
            {
                "id": "document-pdf-writer-v1",
                "title": "Generate PDF document",
                "primary": True,
                "stages": ["writer"],
                "inputs": ["outline", "markdown", "material_index", "report_blocks", "html"],
                "steps": [
                    {
                        "id": "write-pdf-document",
                        "stage": "writer",
                        "tool": "pdf_write",
                        "default_args": {"template": "academic_report", "visual_master": "default_print"},
                        "outputs": ["pdf_path", "html_path", "page_count", "renderer"],
                    },
                ],
            }
        ],
        "shortcuts": [
            {
                "id": "create-pdf-document",
                "surface": "wizard",
                "label": "PDF document",
                "entry_pipeline": "document-pdf-writer-v1",
                "requires_input": ["outline"],
                "visible_when": "pipeline_ready",
            }
        ],
    },
    {
        "id": "math-expression-cleanup",
        "title": "Math expression cleanup",
        "description": "Normalize messy OCR, document, LaTeX, and code math into clean LaTeX/Markdown via the SymPy core (regex fallback).",
        "category": "math",
        "family": "math-expression-engineering",
        "agent_hint": (
            "Use for normalizing messy OCR, LaTeX, document math, or code-like math expressions. "
            "This is cleanup/normalization, not document extraction or proof checking."
        ),
        "tools": ["math_expression_cleanup"],
        "required_toolsets": ["math"],
        "required_load_packages": [],
        "optional_load_packages": [],
        "roles": ["default", "advanced", "power"],
        "risk": "low",
        "source": "builtin",
        "trust": "official",
        "pipelines": [
            {
                "id": "math-expression-cleanup-v1",
                "title": "Math expression cleanup V1",
                "primary": True,
                "stages": ["reader", "material_index", "writer"],
                "inputs": ["ocr_formula", "latex", "document_math", "code_expression"],
                "steps": [
                    {
                        "id": "cleanup-math-expression",
                        "stage": "writer",
                        "tool": "math_expression_cleanup",
                        "outputs": ["clean_latex", "markdown", "variable_table", "warnings"],
                    },
                ],
            }
        ],
        "shortcuts": [
            {
                "id": "cleanup-math-expression",
                "surface": "context_menu",
                "label": "Clean formula",
                "entry_pipeline": "math-expression-cleanup-v1",
                "requires_input": ["formula"],
                "visible_when": "pipeline_ready",
            }
        ],
    },
    {
        "id": "math-formula-to-code",
        "title": "Formula to code",
        "description": (
            "Convert formulas, LaTeX, and document math into code for a user-selected target "
            "language (Python, NumPy, JavaScript, MATLAB/Octave, or Fortran) via a canonical "
            "SymPy core with NumPy numeric self-validation."
        ),
        "category": "math",
        "family": "math-expression-engineering",
        "agent_hint": (
            "Use for converting a formula or LaTeX expression into code. Pass the user's chosen "
            "language (python, numpy, javascript, octave, fortran). The tool parses into a canonical "
            "SymPy expression, transpiles with SymPy's code printers, and reports a NumPy lambdify "
            "vs evalf numeric check. Still extract a semantic_contract (variables, dimensions, domains, "
            "boundary/open-closed intervals, invariants, expected outputs) and run executable tests "
            "covering both numeric error and every clause before claiming success."
        ),
        "tools": ["math_formula_to_code"],
        "required_toolsets": ["math"],
        "required_load_packages": [],
        "optional_load_packages": [],
        "roles": ["default", "advanced", "power"],
        "risk": "low",
        "source": "builtin",
        "trust": "official",
        "pipelines": [
            {
                "id": "math-formula-to-code-v1",
                "title": "Formula to code V1",
                "primary": True,
                "stages": ["reader", "material_index", "planner", "writer"],
                "inputs": ["latex", "markdown_formula", "document_math", "extracted_formula"],
                "writer_targets": ["python", "numpy", "javascript", "octave", "fortran"],
                "steps": [
                    {
                        "id": "convert-formula-to-code",
                        "stage": "writer",
                        "tool": "math_formula_to_code",
                        "outputs": [
                            "code",
                            "language",
                            "variable_table",
                            "assumptions",
                            "example_inputs",
                            "semantic_validation",
                        ],
                    },
                ],
            }
        ],
        "shortcuts": [
            {
                "id": "formula-to-code",
                "surface": "context_menu",
                "label": "Formula to code",
                "entry_pipeline": "math-formula-to-code-v1",
                "requires_input": ["formula"],
                "visible_when": "pipeline_ready",
            }
        ],
    },
    {
        "id": "code-to-math-formula",
        "title": "Code to math formula",
        "description": "Convert Python or NumPy code into formulas, LaTeX, Markdown, and HTML reports via the SymPy core.",
        "category": "math",
        "family": "math-expression-engineering",
        "agent_hint": (
            "Use for converting simple Python or NumPy expressions into LaTeX, Markdown, and an HTML "
            "report (sympy.latex over the canonical expression). Other source languages are a future "
            "follow-up. For a PDF deliverable, pass the structured report content to pdf_write through "
            "the document-pdf-generation capability."
        ),
        "tools": ["code_to_math_formula"],
        "required_toolsets": ["math"],
        "required_load_packages": [],
        "optional_load_packages": [],
        "roles": ["default", "advanced", "power"],
        "risk": "low",
        "source": "builtin",
        "trust": "official",
        "pipelines": [
            {
                "id": "code-to-math-formula-v1",
                "title": "Code to math formula V1",
                "primary": True,
                "stages": ["reader", "material_index", "planner", "writer"],
                "inputs": ["python", "numpy"],
                "steps": [
                    {
                        "id": "convert-code-to-math-report",
                        "stage": "writer",
                        "tool": "code_to_math_formula",
                        "outputs": ["formulas", "latex", "markdown", "html_path", "pdf_path", "variable_table"],
                    },
                ],
            }
        ],
        "shortcuts": [
            {
                "id": "code-to-formula-report",
                "surface": "context_menu",
                "label": "Code to formula",
                "entry_pipeline": "code-to-math-formula-v1",
                "requires_input": ["code"],
                "visible_when": "pipeline_ready",
            }
        ],
    },
)


def list_capability_defs() -> list[dict[str, Any]]:
    return [_derive_fields(deepcopy(item)) for item in _CAPABILITIES]


def get_capability_def(capability_id: str) -> dict[str, Any]:
    for item in _CAPABILITIES:
        if item["id"] == capability_id:
            return _derive_fields(deepcopy(item))
    raise KeyError(capability_id)
