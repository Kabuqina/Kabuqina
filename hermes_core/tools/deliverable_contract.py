# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Canonical, dependency-free contract for student-deliverable generation.

This is the single source of truth for the **planner <-> writer vocabulary**.
Both the writer (``tools/document_tools.py``) and the shared planner prompt
(``agent/prompt_builder.py``) import from here, so:

- the web child and the gateway child plan against identical rules, and
- the writer normalizes slide objects against the exact same sets the planner
  is told to emit.

Keep this module import-cheap and dependency-free — it is pulled into the agent
system-prompt build path, which runs early and must not drag in heavy deps.
"""

from __future__ import annotations

# Slide-object vocabulary the PPT writer (``pptx_write``) accepts. Unknown
# values normalize to "claim_bullets" in ``document_tools._normalize_slide_type``.
PPTX_SLIDE_TYPES: tuple[str, ...] = (
    "agenda",
    "claim_bullets",
    "diagram",
    "table",
    "chart_placeholder",
    "screenshot_placeholder",
    "qa_backup",
    "closing",
)

# Optional per-slide layout hints the planner may set; the web renderer
# auto-selects by content when omitted.
PPTX_SLIDE_LAYOUTS: tuple[str, ...] = (
    "hero_statement",
    "standard_bullets",
    "two_column_bullets",
    "comparison_cards",
    "process_flow_horizontal",
    "process_flow_vertical",
    "data_table",
    "media_placeholder",
    "section_divider",
    "stat_callout",
    "pull_quote",
    "image_text_split",
    "big_number_grid",
    "icon_grid",
    "timeline",
)

# Per-structure "must cover" outline for PPT decks. Keyed by the capability
# structure_template id (see ``student-ppt`` in capability_registry).
PPTX_STRUCTURES: dict[str, dict[str, object]] = {
    "course_report": {
        "title": "课程学习汇报",
        "must_cover": [
            "知识结构图 diagram",
            "关键概念解释",
            "案例 / 例题 / 应用场景",
            "对比 table 或流程 diagram",
            "学习总结 / 个人收获",
            "难点或易错点 qa_backup",
        ],
    },
    "paper_report": {
        "title": "论文 / 文献汇报",
        "must_cover": [
            "研究背景 / 问题",
            "研究方法或系统框架 diagram",
            "关键实现或分析证据",
            "结果 / 测试 / 实验汇总",
            "创新点或贡献",
            "局限与展望",
            "老师可能追问 qa_backup",
        ],
    },
    "code_defense": {
        "title": "课设 / 项目答辩",
        "must_cover": [
            "项目背景与目标",
            "总体架构 diagram",
            "模块调用 / 数据流 / 核心实现流程 diagram",
            "运行结果 screenshot_placeholder 或真实截图",
            "测试结果 table",
            "问题与解决方案",
            "部署运行说明或核心代码说明 qa_backup",
        ],
    },
}

# Writer tools whose presence should trigger the planner guidance, mapped to the
# output they produce. Used by the shared planner prompt to self-gate.
DELIVERABLE_WRITER_TOOLS: dict[str, str] = {
    "pptx_write": "PPTX",
    "pdf_write": "PDF",
    "html_write": "HTML",
    "docx_write": "DOCX",
}


def slide_type_set() -> set[str]:
    return set(PPTX_SLIDE_TYPES)


def slide_layout_set() -> set[str]:
    return set(PPTX_SLIDE_LAYOUTS)
