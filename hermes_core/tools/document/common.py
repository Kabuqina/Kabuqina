# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Shared leaf helpers + spec/path/data primitives for the document tools."""

import json
import os
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from tools.deliverable_contract import slide_layout_set, slide_type_set
from tools.registry import tool_error


# Exact files that a trusted host UI has authorized for this read request.
# This is deliberately separate from power-user mode: it never grants access
# to a parent directory and ContextVar state follows asyncio.to_thread without
# becoming a process-wide permission.
_TEMPORARY_DOCUMENT_READ_PATHS: ContextVar[tuple[Path, ...]] = ContextVar(
    "kabuqina_temporary_document_read_paths",
    default=(),
)


def _normalized_read_path(path: str | os.PathLike) -> Path:
    try:
        return Path(path).expanduser().resolve()
    except OSError:
        return Path(os.path.realpath(os.path.abspath(os.fspath(path))))


@contextmanager
def temporary_document_read_access(path: str | os.PathLike) -> Iterator[Path]:
    """Authorize one exact host-selected file for the current read context."""
    selected = _normalized_read_path(path)
    token = _TEMPORARY_DOCUMENT_READ_PATHS.set(
        (*_TEMPORARY_DOCUMENT_READ_PATHS.get(), selected)
    )
    try:
        yield selected
    finally:
        _TEMPORARY_DOCUMENT_READ_PATHS.reset(token)


def _has_temporary_document_read_access(path: Path) -> bool:
    return _normalized_read_path(path) in _TEMPORARY_DOCUMENT_READ_PATHS.get()


def _text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return text or default


def _list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _string_list(value: Any, *, limit: int = 8) -> List[str]:
    return [_text(item) for item in _list(value) if _text(item)][:limit]


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


Rgb = Tuple[int, int, int]


_PPTX_SLIDE_TYPES = slide_type_set()


_PPTX_SLIDE_LAYOUTS = slide_layout_set()


_PDF_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "academic_report": {
        "title": "Academic report",
        "accent": (37, 99, 235),
        "subtitle": "print-friendly student report",
    },
    "code_report": {
        "title": "Code report",
        "accent": (79, 70, 229),
        "subtitle": "technical report with code and tables",
    },
    "math_report": {
        "title": "Math report",
        "accent": (22, 101, 52),
        "subtitle": "formula-oriented report",
    },
    "brief": {
        "title": "Brief",
        "accent": (71, 85, 105),
        "subtitle": "compact document",
    },
}


_PDF_BLOCK_TYPES = {
    "heading",
    "paragraph",
    "bullets",
    "table",
    "code",
    "formula",
    "image_placeholder",
    "page_break",
}


class DocumentSpecError(ValueError):
    """Raised when a writer document spec cannot be normalized safely."""


def _json(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


def _desktop_workspace_root() -> Optional[Path]:
    raw = (
        os.environ.get("HERMESDESK_WORKSPACE")
        or os.environ.get("HERMES_WORKSPACE")
        or ""
    ).strip()
    if not raw:
        return None
    try:
        return Path(raw).expanduser().resolve()
    except OSError:
        return None


def _is_outside_workspace(path: Path, workspace: Path) -> bool:
    try:
        path.resolve().relative_to(workspace.resolve())
        return False
    except ValueError:
        return True


def _power_user_reads_anywhere() -> bool:
    """Power-user mode lets *read* tools reach outside the workspace.

    Lets the agent read a project in place instead of copying the whole tree
    into the workspace first. Write targets stay workspace-confined regardless
    (see ``_validate_write_path``).
    """
    return os.environ.get("HERMESDESK_POWER_USER") == "1"


def _validate_read_path(document_path: Path, original_path: str, label: str) -> Optional[str]:
    if not document_path.exists():
        return tool_error(f"{label} not found: {original_path}")
    workspace = _desktop_workspace_root()
    if workspace is not None and not _power_user_reads_anywhere():
        try:
            resolved = document_path.resolve()
        except OSError:
            resolved = document_path
        if (
            _is_outside_workspace(resolved, workspace)
            and not _has_temporary_document_read_access(resolved)
        ):
            return tool_error(
                f"{label} path is outside the Kabuqina workspace ({workspace}): {original_path}",
                code="outside_workspace",
                workspace=str(workspace),
                hint=(
                    "Copy the file into the workspace first. If terminal is available, "
                    "run cp yourself (Git Bash: cp \"/d/.../file\" \"./file\") — "
                    "do not ask the user to copy manually."
                ),
            )
    return None


def _validate_write_path(out_path: Path, original_path: str) -> Optional[str]:
    """Workspace guard for *write* targets (the file need not exist yet)."""
    workspace = _desktop_workspace_root()
    if workspace is None:
        return None
    try:
        resolved = out_path.resolve()
    except OSError:
        resolved = out_path
    if _is_outside_workspace(resolved, workspace):
        return tool_error(
            f"Output path is outside the Kabuqina workspace ({workspace}): {original_path}",
            code="outside_workspace",
            workspace=str(workspace),
            hint="Write the output file into the workspace (or a subfolder of it).",
        )
    return None
