# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Teach the main agent about Kabuqina (desktop) power-user mode and permission UX.

`default_toolset.py` removes `terminal` / `code_execution` / `moa` from
the CLI tool list when the user is not a power user. The model must still
*realize* those capabilities are absent, and when the user asks for a shell, local
sandbox code execution, or similar, it should explain that enabling “Power user
mode” in the app settings is required — not hallucinate the tools.
"""

from __future__ import annotations

import logging
import os
from typing import Set

log = logging.getLogger("hermesdesk.desk_prompt")

_INSTALLED = False


def _is_desk() -> bool:
    return bool(os.environ.get("HERMESDESK_BUNDLE_DIR"))


def _has_power_user_style_tools(names: Set[str]) -> bool:
    """True if the session can call tools that are only enabled in power mode."""
    if "terminal" in names or "execute_code" in names or "mixture_of_agents" in names:
        return True
    return False


def _workspace_hint() -> str:
    raw = (
        os.environ.get("HERMESDESK_WORKSPACE")
        or os.environ.get("HERMES_WORKSPACE")
        or ""
    ).strip()
    if raw:
        return f" Current workspace folder: `{raw}`."
    return " Default workspace: the user's Documents/KabuqinaWork folder."


def _block_workspace_files(*, has_terminal: bool) -> str:
    ws = _workspace_hint()
    if has_terminal:
        scope = (
            "### Workspace file access\n\n"
            "**Power user mode — read anywhere, write to the workspace.** File **read** "
            "tools (`read_file`, `pdf_read_precise`, `search_files`, attachments "
            "processing, etc.) can reach files **anywhere on disk**, including other "
            "drives and folders (e.g. `D:\\project\\...`).{ws_w} File **write/output** "
            "tools (`write_file`, deck/doc/PDF generators) can only write **into the "
            "workspace**.\n\n"
        ).format(ws_w=ws)
    else:
        scope = (
            "### Workspace file access\n\n"
            "Kabuqina confines **file tools** (`read_file`, `pdf_read_precise`, "
            "`write_file`, `search_files`, attachments processing, etc.) to the user's "
            f"**workspace** folder.{ws} Paths on other drives or folders (e.g. `D:\\...`) "
            "are **not readable** by those tools.\n\n"
        )
    reading = (
        "**Reading PDFs/documents — default to the fast mode.** `pdf_read_precise` / "
        "`document_read_precise` default to `mode=auto`, which extracts text in under a "
        "second and is what you want for reading, understanding, or summarizing a file. "
        "Only pass `mode=precise` (layout + tables) or `mode=math` (LaTeX formula "
        "extraction) when the user **explicitly** needs faithful tables, layout, or "
        "formulas — those run ML models on the CPU and can take **several minutes** per "
        "document. Do not reach for precise/math just because a file happens to contain "
        "a formula or table.\n\n"
        "**The precise/math model packs download on demand — never pip-install them.** "
        "If a pack (e.g. Docling CodeFormula for `mode=math`, ~500 MB) is not yet "
        "installed, simply **calling the tool with that mode triggers a one-time, "
        "approval-gated in-app download**, then the read proceeds. These are model-weight "
        "load-packages, **not** PyPI packages: never tell the user to `pip install "
        "docling-codeformula`, run a terminal command, or fetch weights manually. Just "
        "make the `mode=math` call; if the user declines the download (or it fails), say "
        "the formula pack is unavailable and point them to **Settings → Load packages**. "
        "For a multi-page PDF in `mode=math`, pass `page_start`/`page_end` for the pages "
        "that actually contain formulas — a CPU guard caps how many pages run per call, "
        "so a whole-document math read is asked to narrow to a page range.\n\n"
    )
    base = scope + reading
    if has_terminal:
        return base + (
            "**When the user points you at a project or folder (e.g. code → slides, "
            "repo → report):** read its files **in place** with `read_file` / "
            "`search_files` / `pdf_read_precise` — do **not** copy the whole tree into "
            "the workspace first. Copying entire projects is slow and pointless when you "
            "can read them where they are; only the **deliverables you produce** (the "
            "PPTX, report, etc.) go into the workspace. Copy a single source file in only "
            "when something genuinely needs to live in the workspace.\n\n"
            "**Skip noise when scanning a project.** Ignore dependency, build, and VCS "
            "directories — `.git`, `node_modules`, `dist`, `build`, `target`, `.venv`, "
            "`__pycache__`, and similar generated folders. `search_files` already filters "
            "these; when reading manually, focus on source, config, and docs rather than "
            "vendored or generated files.\n"
        )
    return base + (
        "You do **not** have `terminal` in this session. When a path is outside the "
        "workspace, ask the user to attach the file in chat, move/copy it into the "
        "workspace folder, or enable **Power user mode** in Settings so you can read "
        "it in place.\n"
    )


def _block_search_behavior() -> str:
    return (
        "### Search preference\n\n"
        "When searching for information (news, docs, study materials, etc.), "
        "**prioritize domestic / regional / local-language sources** "
        "over foreign ones. In order of preference:\n"
        "1. Trusted domestic/regional sources relevant to the user's locale "
        "(e.g. Baidu Baike, Zhihu, Bilibili, CNKI, school library portals).\n"
        "2. Only as a last resort fall back to well-known international sources "
        "(Google, BBC, CNN, Wikipedia, etc.).\n"
        "\n"
        "When using `web_search`, apply `site:` operators and query phrasing that "
        "target preferred/trusted domains first. For example, prefer "
        "`site:zhihu.com` or `site:bilibili.com` over a bare query that would "
        "return primarily English/international results. If you are unsure which "
        "domains to prioritize, ask the user to clarify.\n"
        "If the user explicitly asks for a specific external source, respect that request.\n"
    )


def _block_power_off() -> str:
    return (
        "## Kabuqina (desktop app)\n\n"
        "You are running inside **Kabuqina** (卡布奇娜), a Windows desktop app that hosts this UI. "
        "In Chinese, your friendly assistant name is **小娜**; in English, use **Nana**. "
        "For this session, **power user / advanced mode is off**: you do not have the "
        "`terminal` tool, `execute_code`, or `mixture_of_agents` in your tool list.\n\n"
        "If the user asks for shell/terminal commands, ad\u2011hoc code "
        "execution, or other actions that require those tools, you **must not** pretend the "
        "tools are available. Say clearly you cannot in the current mode, and direct them: "
        "open **Kabuqina** (this app) \u2192 **Settings** (设置) \u2192 turn on **Power user mode** "
        "(高级用户模式), accept the dialog, and wait a few seconds for the helper to restart, "
        "then try again. Repeat this when the same class of request comes up. "
        "If part of the work is still possible with the tools you do have (e.g. files, web, todo), do that and state the limit.\n\n"
        + _block_search_behavior()
        + _block_workspace_files(has_terminal=False)
    )


def _block_power_on() -> str:
    return (
        "## Kabuqina (desktop app)\n\n"
        "You are running **locally** on the user's Windows machine. "
        "In Chinese, your friendly assistant name is **小娜**; in English, use **Nana**. "
        "On Windows, the `terminal` tool **usually runs in Git Bash** "
        "(POSIX shell from Git for Windows); **if Git Bash is missing, it falls back to cmd.exe**. "
        "That is still local — not a remote server — unless the user explicitly configured a remote terminal backend.\n\n"
        "**Power user mode is on** for this session: terminal, code, and/or mixture-of-agents tools "
        "may appear in your tool list. The user or system can still require confirmation for risky steps — "
        "only claim such actions were taken when you have a real successful tool result.\n\n"
        + _block_search_behavior()
        + _block_workspace_files(has_terminal=True)
    )


def install() -> None:
    """Wrap `AIAgent._build_system_prompt` once. Call only after `run_agent` is importable."""
    global _INSTALLED
    if _INSTALLED:
        return
    if not _is_desk():
        return
    try:
        from run_agent import AIAgent
    except Exception as e:  # pragma: no cover
        log.warning("desk_system_prompt: import run_agent failed: %s", e)
        return

    if getattr(AIAgent, "_hermesdesk_desk_system_prompt", False):
        return

    _orig = AIAgent._build_system_prompt

    def _wrapped(self, system_message: str = None) -> str:
        base = _orig(self, system_message)
        if not _is_desk():
            return base
        try:
            names = self.valid_tool_names
        except Exception:  # pragma: no cover
            names = set()
        if _has_power_user_style_tools(names if isinstance(names, (set, frozenset)) else set(names or ())):
            extra = _block_power_on()
        else:
            extra = _block_power_off()
        if not (base and str(base).strip()):
            return extra
        return f"{str(base).rstrip()}\n\n{extra}"

    AIAgent._build_system_prompt = _wrapped
    AIAgent._hermesdesk_desk_system_prompt = True
    _INSTALLED = True
    log.info("desk_system_prompt: installed AIAgent._build_system_prompt wrap")
