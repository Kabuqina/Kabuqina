# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Phase 3.5 Task 3: enforce LangGraph/LangChain/LangSmith import isolation.

Only ``agent/graph_engine/builder.py`` may import from ``langgraph``.
No production file may import from ``langchain`` or ``langsmith``.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # hermes_core/
PRODUCTION_ROOT = ROOT
EXCLUDED_DIR_NAMES = {
    "tests",
    "__pycache__",
    ".venv",
    "venv",
    "build",
    "dist",
}


def _walk_production_py_files(directory: Path) -> list[Path]:
    """Return all .py files under *directory*, excluding __pycache__ and tests."""
    files: list[Path] = []
    for py_file in directory.rglob("*.py"):
        relative_parts = py_file.relative_to(ROOT).parts[:-1]
        if any(part in EXCLUDED_DIR_NAMES for part in relative_parts):
            continue
        files.append(py_file)
    return sorted(files)


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


def test_configured_import_scan_covers_entire_core():
    """The configured gate must include production modules outside agent/."""
    scanned = {
        _relative(path) for path in _walk_production_py_files(PRODUCTION_ROOT)
    }
    assert {
        "run_agent.py",
        "gateway/run.py",
        "cron/scheduler.py",
        "tools/cronjob_tools.py",
        "agent/graph_engine/builder.py",
    } <= scanned


# ── langgraph-only gate ──────────────────────────────────────────────────

LANGRAPH_ALLOWED = {"agent/graph_engine/builder.py"}
FORBIDDEN_PREFIXES = ("langchain", "langsmith")


def test_langgraph_imports_only_in_builder():
    """langgraph imports are allowed ONLY in agent/graph_engine/builder.py."""
    violations: list[str] = []
    for py_file in _walk_production_py_files(PRODUCTION_ROOT):
        rel = _relative(py_file)
        for module, symbol, lineno in _extract_imports(py_file):
            if module == "langgraph" or module.startswith("langgraph."):
                if rel not in LANGRAPH_ALLOWED:
                    violations.append(
                        f"{rel}:{lineno}: import {module}"
                        + (f" as {symbol}" if symbol else "")
                    )
    assert not violations, (
        "only agent/graph_engine/builder.py may import langgraph:\n"
        + "\n".join(violations)
    )


def test_no_langchain_or_langsmith_imports():
    """No production file may import from langchain or langsmith."""
    violations: list[str] = []
    for py_file in _walk_production_py_files(PRODUCTION_ROOT):
        rel = _relative(py_file)
        for module, symbol, lineno in _extract_imports(py_file):
            for prefix in FORBIDDEN_PREFIXES:
                if module == prefix or module.startswith(f"{prefix}."):
                    violations.append(
                        f"{rel}:{lineno}: import {module}"
                        + (f" as {symbol}" if symbol else "")
                    )
    assert not violations, (
        "langchain/langsmith imports are forbidden in production code:\n"
        + "\n".join(violations)
    )


def test_langgraph_import_present_in_builder():
    """builder.py must keep the graph package's sole langgraph import."""
    py_file = ROOT / "agent" / "graph_engine" / "builder.py"
    found = False
    for module, _symbol, _lineno in _extract_imports(py_file):
        if module == "langgraph" or (module is not None and module.startswith("langgraph.")):
            found = True
            break
    assert found, "agent/graph_engine/builder.py must import langgraph"
