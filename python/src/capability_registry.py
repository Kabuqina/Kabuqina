# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""First-party product capability definitions for Kabuqina Desktop."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

VALID_CAPABILITY_STATUSES = (
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
        "title": "Student report PPT workflow",
        "description": "Build structured course, paper, and code-defense PPT workflows from source material.",
        "category": "documents",
        "agent_hint": "Use for course reports, paper presentations, and code-defense slide generation.",
        "tools": ["material_index_build", "review_outline", "pptx_write"],
        "required_toolsets": ["documents", "clarify"],
        "required_load_packages": [],
        "optional_load_packages": ["docling-codeformula"],
        "roles": ["default", "advanced", "power"],
        "risk": "medium",
        "source": "builtin",
        "trust": "official",
        "pipelines": [
            {
                "id": "student-ppt-from-documents",
                "title": "Student PPT from source documents",
                "primary": True,
                "stages": ["reader", "material_index", "planner", "writer"],
                "inputs": ["document"],
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
                        "id": "write-student-ppt",
                        "stage": "writer",
                        "tool": "pptx_write",
                        "default_args": {"template": "course_report"},
                        "inputs": ["outline", "material_index"],
                        "outputs": ["pptx_path"],
                    },
                ],
            }
        ],
        "shortcuts": [
            {
                "id": "create-student-ppt",
                "surface": "wizard",
                "label": "Create PPT",
                "entry_pipeline": "student-ppt-from-documents",
                "requires_input": ["document"],
                "visible_when": "pipeline_ready_or_downloadable",
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
