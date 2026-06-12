# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Compact agent-facing summary of Nana's current product capabilities."""

from __future__ import annotations

from typing import Any


def build_capability_prompt_summary(capabilities: list[dict[str, Any]]) -> str:
    lines = ["Current Kabuqina product capabilities:"]
    for item in capabilities:
        status = str(item.get("status") or "error")
        title = str(item.get("title") or item.get("id") or "unknown")
        hint = str(item.get("agentHint") or "").strip()
        missing_packages = [
            _format_package_ref(pkg)
            for pkg in item.get("requiredLoadPackages") or []
            if not bool(pkg.get("downloaded", status == "available"))
        ]
        missing_packages = [pkg for pkg in missing_packages if pkg]
        suffix = f" Missing package(s): {', '.join(missing_packages)}." if missing_packages else ""
        if status == "candidate":
            suffix += " Candidate only; not yet executable."
        hint_suffix = f" {hint}" if hint else ""
        pipeline_suffix = _format_ready_pipelines(item)
        visual_master_suffix = _format_visual_masters(item)
        ppt_rule_suffix = _format_ppt_visual_master_rule(item)
        pdf_rule_suffix = _format_pdf_writer_rule(item)
        lines.append(
            f"- {title}: {status}.{suffix}{hint_suffix}"
            f"{pipeline_suffix}{visual_master_suffix}{ppt_rule_suffix}{pdf_rule_suffix}"
        )
    return "\n".join(lines)


def _format_package_ref(package: dict[str, Any]) -> str:
    package_id = str(package.get("id") or "").strip()
    title = str(package.get("title") or "").strip()
    if package_id and title and title != package_id:
        return f"{package_id} ({title})"
    return package_id or title


def _format_ready_pipelines(capability: dict[str, Any]) -> str:
    formatted = [
        _format_pipeline(pipeline)
        for pipeline in capability.get("pipelines") or []
        if bool(pipeline.get("ready"))
    ]
    formatted = [item for item in formatted if item]
    if not formatted:
        return ""
    return f" Ready pipeline(s): {'; '.join(formatted)}."


def _format_visual_masters(capability: dict[str, Any]) -> str:
    masters = []
    for item in capability.get("visualMasters") or capability.get("visual_masters") or []:
        master_id = str(item.get("id") or "").strip()
        title = str(item.get("title") or item.get("name") or "").strip()
        if master_id and title:
            masters.append(f"{master_id}={title}")
        elif master_id:
            masters.append(master_id)
    if not masters:
        return ""
    return f" Available visual masters: {', '.join(masters)}."


def _format_ppt_visual_master_rule(capability: dict[str, Any]) -> str:
    tools = {str(item) for item in capability.get("tools") or []}
    pipeline_tools = {
        str(step.get("tool") or "")
        for pipeline in capability.get("pipelines") or []
        for step in pipeline.get("steps") or []
        if isinstance(step, dict)
    }
    if "pptx_write" not in tools and "pptx_write" not in pipeline_tools:
        return ""
    return (
        " For PPT generation, pass template and visual_master to pptx_write from the "
        "user's selection or the ready pipeline default. The deck is rendered by "
        "PptxGenJS in the Kabuqina desktop UI; on success visual_master_renderer is "
        "pptxgenjs_v1 and path points at the saved .pptx. If pptx_write returns an "
        "error (e.g. code pptx_render_unavailable), tell the user PPT generation "
        "requires the Kabuqina app window instead of claiming a file was created."
    )


def _format_pdf_writer_rule(capability: dict[str, Any]) -> str:
    tools = {str(item) for item in capability.get("tools") or []}
    pipeline_tools = {
        str(step.get("tool") or "")
        for pipeline in capability.get("pipelines") or []
        for step in pipeline.get("steps") or []
        if isinstance(step, dict)
    }
    if "pdf_write" not in tools and "pdf_write" not in pipeline_tools:
        return ""
    return (
        " For PDF generation, call pdf_write with a structured document containing "
        "sections or blocks. The normal path writes a PDF plus an HTML source sidecar; "
        "on success renderer is reportlab_pdf_v1 and html_path points at the source. "
        "If pdf_write returns an error such as pdf_render_unavailable, say the PDF "
        "backend is unavailable instead of claiming a file was created."
    )


def _format_pipeline(pipeline: dict[str, Any]) -> str:
    pipeline_id = str(pipeline.get("id") or "").strip()
    steps = [_format_step(step) for step in pipeline.get("steps") or []]
    steps = [step for step in steps if step]
    if not pipeline_id or not steps:
        return pipeline_id
    return f"{pipeline_id}: {' | '.join(steps)}"


def _format_step(step: dict[str, Any]) -> str:
    call = _format_step_call(step)
    outputs = [str(item) for item in step.get("outputs") or [] if str(item)]
    if call and outputs:
        return f"{call} -> outputs: {', '.join(outputs)}"
    if outputs:
        return f"outputs: {', '.join(outputs)}"
    return call


def _format_step_call(step: dict[str, Any]) -> str:
    tool = str(step.get("tool") or "").strip()
    tools = [str(item) for item in step.get("tools") or [] if str(item)]
    kind = str(step.get("kind") or "").strip()
    name = tool or "/".join(tools) or kind
    if not name:
        return ""

    args = step.get("default_args") or step.get("defaultArgs") or {}
    if not isinstance(args, dict) or not args:
        return name
    arg_text = ", ".join(f"{key}={args[key]}" for key in sorted(args))
    return f"{name}({arg_text})"
