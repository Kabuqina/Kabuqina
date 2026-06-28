# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Phase 3.5 Task 3: enforce LangGraph/LangChain/LangSmith import isolation.

Only ``agent/graph_engine/builder.py`` may import from ``langgraph``.
No production file may import from ``langchain`` or ``langsmith``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]  # hermes_core/
AGENT_DIR = ROOT / "agent"


def _walk_production_py_files(directory: Path) -> list[Path]:
    """Return all .py files under *directory*, excluding __pycache__ and tests."""
    files: list[Path] = []
    for py_file in directory.rglob("*.py"):
        parts = py_file.parts
        if "__pycache__" in parts:
            continue
        if "tests" in parts:
            continue
        files.append(py_file)
    return files


def _extract_imports(file_path: Path) -> list[tuple[str, str | None, int]]:
    """Return (module, symbol, lineno) for every import in *file_path*."""
    tree = ast.parse(file_path.read_text("utf-8"), filename=str(file_path))
    imports: list[tuple[str, str | None, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, None, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                for alias in node.names:
                    imports.append((node.module, alias.name, node.lineno))
    return imports


def _relative(path: Path) -> str:
    """Return path relative to hermes_core/ for readable test output."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


# ── langgraph-only gate ──────────────────────────────────────────────────

LANGRAPH_ALLOWED = {"agent/graph_engine/builder.py"}
FORBIDDEN_PREFIXES = ("langchain", "langsmith")


@pytest.mark.parametrize("py_file", _walk_production_py_files(AGENT_DIR))
def test_langgraph_imports_only_in_builder(py_file: Path):
    """langgraph imports are allowed ONLY in agent/graph_engine/builder.py."""
    rel = _relative(py_file)
    for module, symbol, lineno in _extract_imports(py_file):
        if module == "langgraph" or (module is not None and module.startswith("langgraph.")):
            if rel not in LANGRAPH_ALLOWED:
                msg = (
                    f"{rel}:{lineno}: import langgraph"
                    + (f".{module.split('.', 1)[1]}" if "." in (module or "") else "")
                    + (f" as {symbol}" if symbol else "")
                    + " — only agent/graph_engine/builder.py may import langgraph"
                )
                pytest.fail(msg)


@pytest.mark.parametrize("py_file", _walk_production_py_files(AGENT_DIR))
def test_no_langchain_or_langsmith_imports(py_file: Path):
    """No production file may import from langchain or langsmith."""
    rel = _relative(py_file)
    for module, symbol, lineno in _extract_imports(py_file):
        if module is not None:
            for prefix in FORBIDDEN_PREFIXES:
                if module == prefix or module.startswith(f"{prefix}."):
                    msg = (
                        f"{rel}:{lineno}: import {module}"
                        + (f" as {symbol}" if symbol else "")
                        + f" — {prefix} imports are forbidden in production code"
                    )
                    pytest.fail(msg)


@pytest.mark.parametrize("py_file", _walk_production_py_files(AGENT_DIR))
def test_langgraph_import_present_in_builder(py_file: Path):
    """If this is builder.py, at least one langgraph import must exist."""
    rel = _relative(py_file)
    if rel != "agent/graph_engine/builder.py":
        pytest.skip("only applies to builder.py")
    found = False
    for module, _symbol, _lineno in _extract_imports(py_file):
        if module == "langgraph" or (module is not None and module.startswith("langgraph.")):
            found = True
            break
    if not found:
        pytest.fail("agent/graph_engine/builder.py must import langgraph")
