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
        "required_load_packages": ["docling-base"],
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
                        "required_load_packages": ["docling-base"],
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
                        "required_load_packages": ["docling-base"],
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
        "required_load_packages": ["docling-base", "docling-codeformula"],
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
                        "required_load_packages": ["docling-base", "docling-codeformula"],
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
                        "required_load_packages": ["docling-base", "docling-codeformula"],
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
        "description": "Generate student-facing course, paper, code-defense, and sandtable-review PPT reports with reviewed outlines and selectable visual masters.",
        "category": "documents",
        "family": "student-report-generation",
        "agent_hint": (
            "Use for student PPT report generation. First pick the report structure "
            "(course_report, paper_report, code_defense, or sandtable_review), build/review "
            "the outline, then call pptx_write with the selected visual_master. "
            "sandtable_review (经营沙盘复盘) and code_defense usually read a project/material "
            "directory in place, not a single file."
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
            {
                "id": "sandtable_review",
                "title": "Sandtable review",
                "description": "经营沙盘模拟复盘：背景规则、团队战略、各周期决策、经营财务结果、得失分析、复盘改进、备用问答。",
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
            },
            {
                "id": "student-sandtable-review-ppt",
                "title": "Generate sandtable-review PPT",
                "primary": False,
                "stages": ["reader", "material_index", "planner", "writer"],
                "inputs": ["workspace", "document"],
                "structure_template": "sandtable_review",
                "visual_master_required": True,
                "steps": [
                    {
                        "id": "inspect-sandtable-material",
                        "stage": "reader",
                        "tools": ["document_read_precise"],
                        "default_args": {"mode": "auto", "include_content": False},
                        "outputs": ["read_id", "markdown", "metadata"],
                    },
                    {
                        "id": "build-sandtable-material-index",
                        "stage": "material_index",
                        "tool": "material_index_build",
                        "default_args": {"profile": "sandtable_review"},
                        "inputs": ["read_id"],
                        "outputs": ["material_index"],
                    },
                    {
                        "id": "review-sandtable-ppt-outline",
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
                        "id": "write-sandtable-ppt",
                        "stage": "writer",
                        "tool": "pptx_write",
                        "default_args": {"template": "sandtable_review", "visual_master": "signal"},
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
            },
            {
                "id": "create-sandtable-review-ppt",
                "surface": "wizard",
                "label": "Sandtable review PPT",
                "entry_pipeline": "student-sandtable-review-ppt",
                "requires_input": ["workspace", "document"],
                "visible_when": "pipeline_ready_or_downloadable",
            }
        ],
    },
    {
        "id": "document-pdf-generation",
        "title": "Generate document (PDF)",
        "description": "Generate print-ready PDF reports through the full reader -> material index -> planner -> writer pipeline, or write a PDF directly from prepared blocks. Both paths emit and print from an HTML source sidecar.",
        "category": "documents",
        "family": "document-generation",
        "agent_hint": (
            "Use when the user asks for a PDF deliverable. Preferred path for source "
            "material: read it (pdf_read_precise / document_read_precise), build a "
            "material index (material_index_build), draft a structured outline with "
            "sections/blocks from that index, have the user review it (review_outline), "
            "then call pdf_write. If you already hold structured content (e.g. from "
            "another tool), call pdf_write directly. pdf_write saves both the PDF and "
            "an inspectable HTML print source file."
        ),
        "tools": ["material_index_build", "review_outline", "pdf_write"],
        "required_toolsets": ["documents", "clarify"],
        "required_load_packages": [],
        "optional_load_packages": [],
        "structure_templates": [
            {
                "id": "academic_report",
                "title": "Academic report",
                "description": "论文/课程报告：研究背景、方法框架、关键证据、结果分析、局限与展望。",
                "pdf_template": "academic_report",
                "material_index_profile": "paper_report",
                "default_sections": ["研究背景", "方法框架", "关键证据", "结果分析", "局限与展望"],
            },
            {
                "id": "code_report",
                "title": "Code report",
                "description": "项目/课设报告：项目背景、系统架构、关键实现、测试结果、问题与改进。",
                "pdf_template": "code_report",
                "material_index_profile": "code_defense",
                "default_sections": ["项目背景", "系统架构", "关键实现", "测试结果", "问题与改进"],
            },
            {
                "id": "math_report",
                "title": "Math report",
                "description": "公式/推导报告：问题定义、公式与推导、变量说明、数值验证、结论。",
                "pdf_template": "math_report",
                "material_index_profile": "course_report",
                "default_sections": ["问题定义", "公式与推导", "变量说明", "数值验证", "结论"],
            },
        ],
        "roles": ["default", "advanced", "power"],
        "risk": "medium",
        "source": "builtin",
        "trust": "official",
        "pipelines": [
            {
                "id": "document-report-pdf",
                "title": "Generate PDF report from source material",
                "primary": True,
                "stages": ["reader", "material_index", "planner", "writer"],
                "inputs": ["document"],
                "structure_template": "academic_report",
                "steps": [
                    {
                        "id": "read-report-source",
                        "stage": "reader",
                        "tools": ["pdf_read_precise", "document_read_precise"],
                        "default_args": {"mode": "auto", "include_content": False},
                        "optional_load_packages": ["docling-codeformula"],
                        "outputs": ["read_id", "markdown", "metadata"],
                    },
                    {
                        "id": "build-report-material-index",
                        "stage": "material_index",
                        "tool": "material_index_build",
                        "default_args": {"profile": "paper_report"},
                        "inputs": ["read_id"],
                        "outputs": ["material_index"],
                    },
                    {
                        "id": "review-report-outline",
                        "stage": "planner",
                        "kind": "agent_review",
                        "requires_user_review": True,
                        "inputs": ["material_index"],
                        "outputs": ["report_blocks"],
                    },
                    {
                        "id": "write-report-pdf",
                        "stage": "writer",
                        "tool": "pdf_write",
                        "default_args": {"template": "academic_report", "visual_master": "default_print"},
                        "inputs": ["report_blocks"],
                        "outputs": ["pdf_path", "html_path", "page_count", "renderer"],
                    },
                ],
            },
            {
                "id": "document-pdf-writer-v1",
                "title": "Write PDF directly from prepared blocks",
                "primary": False,
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
            },
        ],
        "shortcuts": [
            {
                "id": "create-pdf-report",
                "surface": "wizard",
                "label": "PDF report",
                "entry_pipeline": "document-report-pdf",
                "requires_input": ["document"],
                "visible_when": "pipeline_ready",
            },
            {
                "id": "create-pdf-document",
                "surface": "wizard",
                "label": "PDF from blocks",
                "entry_pipeline": "document-pdf-writer-v1",
                "requires_input": ["outline"],
                "visible_when": "pipeline_ready",
            },
        ],
    },
    {
        "id": "document-html-generation",
        "title": "Generate document (HTML)",
        "description": "Generate standalone, responsive HTML reports through the full reader -> material index -> planner -> writer pipeline, or write HTML directly from prepared blocks.",
        "category": "documents",
        "family": "document-generation",
        "agent_hint": (
            "Use when the user asks for an HTML deliverable, web report, or shareable "
            "study notes. Preferred path for source material: read it (pdf_read_precise "
            "/ document_read_precise), build a material index (material_index_build), "
            "draft a structured outline with sections/blocks from that index, have the "
            "user review it (review_outline), then call html_write. If you already hold "
            "structured content, call html_write directly. html_write produces one "
            "self-contained .html file (renderer standalone_html_v1)."
        ),
        "tools": ["material_index_build", "review_outline", "html_write"],
        "required_toolsets": ["documents", "clarify"],
        "required_load_packages": [],
        "optional_load_packages": [],
        "structure_templates": [
            {
                "id": "web_report",
                "title": "Web report",
                "description": "通用网页报告：背景、要点、证据、结论。",
                "html_template": "academic_report",
                "material_index_profile": "paper_report",
                "default_sections": ["背景", "关键要点", "证据与数据", "结论"],
            },
            {
                "id": "study_notes",
                "title": "Study notes",
                "description": "学习笔记：知识结构、关键概念、案例应用、复习要点。",
                "html_template": "academic_report",
                "material_index_profile": "course_report",
                "default_sections": ["知识结构", "关键概念", "案例应用", "复习要点"],
            },
            {
                "id": "code_walkthrough",
                "title": "Code walkthrough",
                "description": "代码讲解：项目概览、关键模块、核心代码、运行说明。",
                "html_template": "code_report",
                "material_index_profile": "code_defense",
                "default_sections": ["项目概览", "关键模块", "核心代码", "运行说明"],
            },
        ],
        "roles": ["default", "advanced", "power"],
        "risk": "medium",
        "source": "builtin",
        "trust": "official",
        "pipelines": [
            {
                "id": "document-report-html",
                "title": "Generate HTML report from source material",
                "primary": True,
                "stages": ["reader", "material_index", "planner", "writer"],
                "inputs": ["document"],
                "structure_template": "web_report",
                "steps": [
                    {
                        "id": "read-html-source",
                        "stage": "reader",
                        "tools": ["pdf_read_precise", "document_read_precise"],
                        "default_args": {"mode": "auto", "include_content": False},
                        "optional_load_packages": ["docling-codeformula"],
                        "outputs": ["read_id", "markdown", "metadata"],
                    },
                    {
                        "id": "build-html-material-index",
                        "stage": "material_index",
                        "tool": "material_index_build",
                        "default_args": {"profile": "paper_report"},
                        "inputs": ["read_id"],
                        "outputs": ["material_index"],
                    },
                    {
                        "id": "review-html-outline",
                        "stage": "planner",
                        "kind": "agent_review",
                        "requires_user_review": True,
                        "inputs": ["material_index"],
                        "outputs": ["report_blocks"],
                    },
                    {
                        "id": "write-report-html",
                        "stage": "writer",
                        "tool": "html_write",
                        "default_args": {"template": "academic_report", "visual_master": "default_web"},
                        "inputs": ["report_blocks"],
                        "outputs": ["path", "renderer", "block_count"],
                    },
                ],
            },
            {
                "id": "document-html-writer-v1",
                "title": "Write HTML directly from prepared blocks",
                "primary": False,
                "stages": ["writer"],
                "inputs": ["outline", "markdown", "material_index", "report_blocks"],
                "steps": [
                    {
                        "id": "write-html-document",
                        "stage": "writer",
                        "tool": "html_write",
                        "default_args": {"template": "academic_report", "visual_master": "default_web"},
                        "outputs": ["path", "renderer", "block_count"],
                    },
                ],
            },
        ],
        "shortcuts": [
            {
                "id": "create-html-report",
                "surface": "wizard",
                "label": "HTML report",
                "entry_pipeline": "document-report-html",
                "requires_input": ["document"],
                "visible_when": "pipeline_ready",
            },
            {
                "id": "create-html-document",
                "surface": "wizard",
                "label": "HTML from blocks",
                "entry_pipeline": "document-html-writer-v1",
                "requires_input": ["outline"],
                "visible_when": "pipeline_ready",
            },
        ],
    },
    {
        "id": "document-docx-generation",
        "title": "Generate document (Word)",
        "description": "Generate editable Word (.docx) reports through the full reader -> material index -> planner -> writer pipeline, or write a Word file directly from prepared blocks.",
        "category": "documents",
        "family": "document-generation",
        "agent_hint": (
            "Use when the user asks for a Word / .docx deliverable they will keep "
            "editing. Preferred path for source material: read it (pdf_read_precise / "
            "document_read_precise), build a material index (material_index_build), "
            "draft a structured outline with sections/blocks from that index, have the "
            "user review it (review_outline), then call docx_write. If you already hold "
            "structured content, call docx_write directly. docx_write produces an "
            "editable .docx (renderer python_docx_v1)."
        ),
        "tools": ["material_index_build", "review_outline", "docx_write"],
        "required_toolsets": ["documents", "clarify"],
        "required_load_packages": [],
        "optional_load_packages": [],
        "structure_templates": [
            {
                "id": "word_report",
                "title": "Word report",
                "description": "通用 Word 报告：背景、要点、证据、结论。",
                "docx_template": "academic_report",
                "material_index_profile": "paper_report",
                "default_sections": ["背景", "关键要点", "证据与数据", "结论"],
            },
            {
                "id": "study_notes",
                "title": "Study notes",
                "description": "学习笔记：知识结构、关键概念、案例应用、复习要点。",
                "docx_template": "academic_report",
                "material_index_profile": "course_report",
                "default_sections": ["知识结构", "关键概念", "案例应用", "复习要点"],
            },
            {
                "id": "project_report",
                "title": "Project report",
                "description": "项目/课设报告：项目背景、系统设计、关键实现、测试结果、问题与改进。",
                "docx_template": "code_report",
                "material_index_profile": "code_defense",
                "default_sections": ["项目背景", "系统设计", "关键实现", "测试结果", "问题与改进"],
            },
        ],
        "roles": ["default", "advanced", "power"],
        "risk": "medium",
        "source": "builtin",
        "trust": "official",
        "pipelines": [
            {
                "id": "document-report-docx",
                "title": "Generate Word report from source material",
                "primary": True,
                "stages": ["reader", "material_index", "planner", "writer"],
                "inputs": ["document"],
                "structure_template": "word_report",
                "steps": [
                    {
                        "id": "read-docx-source",
                        "stage": "reader",
                        "tools": ["pdf_read_precise", "document_read_precise"],
                        "default_args": {"mode": "auto", "include_content": False},
                        "optional_load_packages": ["docling-codeformula"],
                        "outputs": ["read_id", "markdown", "metadata"],
                    },
                    {
                        "id": "build-docx-material-index",
                        "stage": "material_index",
                        "tool": "material_index_build",
                        "default_args": {"profile": "paper_report"},
                        "inputs": ["read_id"],
                        "outputs": ["material_index"],
                    },
                    {
                        "id": "review-docx-outline",
                        "stage": "planner",
                        "kind": "agent_review",
                        "requires_user_review": True,
                        "inputs": ["material_index"],
                        "outputs": ["report_blocks"],
                    },
                    {
                        "id": "write-report-docx",
                        "stage": "writer",
                        "tool": "docx_write",
                        "default_args": {"template": "academic_report", "visual_master": "default_docx"},
                        "inputs": ["report_blocks"],
                        "outputs": ["path", "renderer", "block_count"],
                    },
                ],
            },
            {
                "id": "document-docx-writer-v1",
                "title": "Write Word directly from prepared blocks",
                "primary": False,
                "stages": ["writer"],
                "inputs": ["outline", "markdown", "material_index", "report_blocks"],
                "steps": [
                    {
                        "id": "write-docx-document",
                        "stage": "writer",
                        "tool": "docx_write",
                        "default_args": {"template": "academic_report", "visual_master": "default_docx"},
                        "outputs": ["path", "renderer", "block_count"],
                    },
                ],
            },
        ],
        "shortcuts": [
            {
                "id": "create-docx-report",
                "surface": "wizard",
                "label": "Word report",
                "entry_pipeline": "document-report-docx",
                "requires_input": ["document"],
                "visible_when": "pipeline_ready",
            },
            {
                "id": "create-docx-document",
                "surface": "wizard",
                "label": "Word from blocks",
                "entry_pipeline": "document-docx-writer-v1",
                "requires_input": ["outline"],
                "visible_when": "pipeline_ready",
            },
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
                # Writer-only by design: the tool consumes a raw formula directly.
                # Reader / material_index inputs come from *other* capabilities
                # (e.g. document-math), not from steps owned by this pipeline.
                "stages": ["writer"],
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
            "language (Python, JavaScript, MATLAB/Octave, or C++17) via a canonical "
            "SymPy core with NumPy numeric self-validation."
        ),
        "category": "math",
        "family": "math-expression-engineering",
        "agent_hint": (
            "Use for converting a formula or LaTeX expression into code. Pass the user's chosen "
            "language (python, javascript, octave, cpp17). The tool parses into a canonical "
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
                # Writer-only by design: the tool transpiles a formula directly.
                # Upstream reader / material_index inputs are produced by other
                # capabilities, not by steps owned by this pipeline.
                "stages": ["writer"],
                "inputs": ["latex", "markdown_formula", "document_math", "extracted_formula"],
                "writer_targets": ["python", "javascript", "octave", "cpp17"],
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
            "Use ONLY for closed-form numeric/mathematical expressions — scientific formulas or the "
            "analytic body of an algorithm (arithmetic plus whitelisted math functions like sin/exp/"
            "sqrt). Do NOT use for business logic, I/O, string processing, or data-structure "
            "manipulation; first confirm the selected code is an actual mathematical computation. The "
            "tool rejects non-mathematical code with a clear error rather than emitting nonsense LaTeX. "
            "Converts simple Python or NumPy expressions into LaTeX, Markdown, and an HTML report "
            "(sympy.latex over the canonical expression). Other source languages are a future follow-up. "
            "For a PDF deliverable, pass the structured report content to pdf_write through the "
            "document-pdf-generation capability."
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
                # Writer-only by design: the tool reduces code to a formula report
                # directly. Upstream reader / material_index inputs are produced by
                # other capabilities, not by steps owned by this pipeline.
                "stages": ["writer"],
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
    {
        "id": "student-tutor-runtime",
        "title": "Resumable Tutor runtime",
        "description": (
            "Executable L-2 Tutor activities with persisted learner checkpoints, "
            "single-attempt provider budgets, recovery, one bounded remediation, "
            "and deterministic participation-only terminal summaries."
        ),
        "category": "learning",
        "family": "student-learning",
        "lifecycle": "available",
        "agent_hint": (
            "Tutor runs are explicit trusted-desktop activities. Do not infer Tutor "
            "intent or emulate Tutor runs with ordinary chat; the host creates and "
            "resumes the persisted activity through the Study activity API."
        ),
        "tools": [],
        "required_toolsets": [],
        "pipelines": [
            {
                "id": "tutor-lifecycle-v1",
                "primary": True,
                "stages": ["reader", "planner", "writer"],
                "steps": [
                    {
                        "id": "load-tutor-checkpoint",
                        "stage": "reader",
                        "outputs": ["tutor_checkpoint"],
                    },
                    {
                        "id": "advance-deterministic-tutor-graph",
                        "stage": "planner",
                        "inputs": ["tutor_checkpoint"],
                        "outputs": ["tutor_transition"],
                    },
                    {
                        "id": "commit-tutor-transition",
                        "stage": "writer",
                        "inputs": ["tutor_transition"],
                        "outputs": ["tutor_activity_snapshot"],
                    },
                ],
            }
        ],
    },
    {
        # STUDY learning foundation (M1). References the learning Planner id and
        # learning artifact kinds by STABLE ID only — no prompt/schema is
        # duplicated here; the drift test in tests/test_capability_registry_learning.py
        # binds these ids back to hermes_core (learning_contract / planner_registry).
        "id": "student-learning-foundation",
        "title": "Learning foundation (course spaces & artifacts)",
        "description": (
            "Course-space learning spine: build the Learning Index and produce "
            "typed learning artifacts (flashcards, quizzes, plans, etc.) as drafts "
            "for review. Data/contract only in M1; the STUDY UI arrives later."
        ),
        "category": "learning",
        "family": "student-learning",
        "lifecycle": "candidate",
        "agent_hint": (
            "Use the 'learning' toolset for course-space learning artifacts. Select "
            "or create a course space, call learning_index_build, then plan via the "
            "learning Planner and save typed drafts with learning_draft_create. "
            "Owner/space are injected by the runtime — never pass them as arguments."
        ),
        "tools": [
            "learning_space_list",
            "learning_space_create",
            "learning_space_select",
            "learning_index_build",
            "learning_draft_create",
            "learning_artifact_list",
        ],
        "required_toolsets": ["learning"],
        # Stable-id references (drift-tested against hermes_core):
        "learning_planner_id": "learning",
        "learning_output_kinds": [
            "student_state",
            "knowledge_base",
            "learning_plan",
            "resource_pack",
            "flashcard_deck",
            "quiz",
            "tutoring_note",
            "evaluation",
        ],
        "pipelines": [
            {
                "id": "learning-foundation-pipeline",
                "primary": True,
                "stages": ["reader", "material_index", "planner", "writer"],
                "steps": [
                    {
                        "id": "read-learning-context",
                        "stage": "reader",
                        "outputs": ["learning_context"],
                    },
                    {
                        "id": "build-learning-index",
                        "stage": "material_index",
                        "tool": "learning_index_build",
                        "inputs": ["learning_context"],
                        "outputs": ["learning_index"],
                    },
                    {
                        "id": "plan-learning-output",
                        "stage": "planner",
                        "kind": "agent_plan",
                        "planner_id": "learning",
                        "inputs": ["learning_index"],
                        "outputs": ["learning_output_plan"],
                    },
                    {
                        "id": "write-learning-draft",
                        "stage": "writer",
                        "tool": "learning_draft_create",
                        "inputs": ["learning_output_plan"],
                        "outputs": ["learning_artifact_draft"],
                    },
                ],
            }
        ],
    },
)


def _pipeline_step_stages(pipeline: dict[str, Any]) -> list[str]:
    """Stages that have at least one real step in the pipeline (source of truth)."""
    return [str(step.get("stage") or "") for step in pipeline.get("steps") or [] if step.get("stage")]


def validate_capability_definitions() -> list[str]:
    """Check the four-layer framework contract and return human-readable errors.

    The invariant: a pipeline's declared ``stages`` must be exactly the set of
    stages that have a real step. This forbids "phantom" stages — a layer
    labelled on a pipeline that no step actually implements — so the registry
    can never claim a capability covers Material Index / Planner / Writer
    without a tool or agent step backing it. Run from a test so any future
    edit that re-introduces a phantom stage fails CI.
    """
    errors: list[str] = []
    for capability in _CAPABILITIES:
        cap_id = capability.get("id", "<unknown>")
        for pipeline in capability.get("pipelines") or []:
            pid = pipeline.get("id", "<unknown>")
            declared = list(pipeline.get("stages") or [])
            for stage in declared:
                if stage not in VALID_FRAMEWORK_STAGES:
                    errors.append(f"{cap_id}/{pid}: declared stage '{stage}' is not a framework stage")
            step_stages = _pipeline_step_stages(pipeline)
            for stage in step_stages:
                if stage not in VALID_FRAMEWORK_STAGES:
                    errors.append(f"{cap_id}/{pid}: step stage '{stage}' is not a framework stage")
            declared_set = {s for s in declared if s in VALID_FRAMEWORK_STAGES}
            step_set = set(step_stages)
            phantom = declared_set - step_set
            undeclared = step_set - declared_set
            if phantom:
                errors.append(
                    f"{cap_id}/{pid}: declared stage(s) {sorted(phantom)} have no backing step "
                    f"(phantom stage — add a real step or drop the stage)"
                )
            if undeclared:
                errors.append(
                    f"{cap_id}/{pid}: step stage(s) {sorted(undeclared)} are not declared in pipeline 'stages'"
                )
    return errors


def _step_actors(step: dict[str, Any]) -> list[str]:
    """What actually performs a step: tool name(s), or an agent/<kind> marker."""
    actors: list[str] = []
    if step.get("tool"):
        actors.append(str(step["tool"]))
    actors.extend([str(tool) for tool in step.get("tools") or []])
    if not actors and step.get("kind"):
        actors.append(f"<{step['kind']}>")
    return actors


def build_framework_coverage() -> dict[str, Any]:
    """Auto-generated four-layer coverage matrix, derived only from real steps.

    Truthful by construction: a stage shows up for a pipeline only when a step
    with that stage exists, so this replaces any hand-maintained "layer x output"
    table. Each cell lists the tool(s) / agent step(s) that implement the layer.
    """
    pipelines: list[dict[str, Any]] = []
    for capability in _CAPABILITIES:
        for pipeline in capability.get("pipelines") or []:
            coverage: dict[str, list[str]] = {stage: [] for stage in VALID_FRAMEWORK_STAGES}
            for step in pipeline.get("steps") or []:
                stage = str(step.get("stage") or "")
                if stage in coverage:
                    coverage[stage].extend(_step_actors(step))
            pipelines.append(
                {
                    "capability": capability.get("id"),
                    "pipeline": pipeline.get("id"),
                    "primary": bool(pipeline.get("primary")),
                    "category": capability.get("category"),
                    "coverage": {stage: _unique(actors) for stage, actors in coverage.items()},
                    "covered_stages": [stage for stage in VALID_FRAMEWORK_STAGES if coverage[stage]],
                }
            )
    return {"stages": list(VALID_FRAMEWORK_STAGES), "pipelines": pipelines}


def render_framework_coverage_table() -> str:
    """Render build_framework_coverage() as a Markdown matrix for docs / CLI."""
    data = build_framework_coverage()
    stages = data["stages"]
    header = "| capability | pipeline | " + " | ".join(stages) + " |"
    divider = "| --- | --- | " + " | ".join("---" for _ in stages) + " |"
    lines = [header, divider]
    for row in data["pipelines"]:
        cells = []
        for stage in stages:
            actors = row["coverage"][stage]
            cells.append(", ".join(actors) if actors else "—")
        star = " *" if row["primary"] else ""
        lines.append(f"| {row['capability']}{star} | {row['pipeline']} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def list_capability_defs() -> list[dict[str, Any]]:
    return [_derive_fields(deepcopy(item)) for item in _CAPABILITIES]


def get_capability_def(capability_id: str) -> dict[str, Any]:
    for item in _CAPABILITIES:
        if item["id"] == capability_id:
            return _derive_fields(deepcopy(item))
    raise KeyError(capability_id)
