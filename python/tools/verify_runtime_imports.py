# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Verify that desktop runtime entry imports resolve from a bundled runtime."""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path


REQUIRED_IMPORTS = (
    "kabuqina_constants",
    "kabuqina_state",
    "kabuqina_logging",
    "kabuqina_time",
    "kabuqina_cli.config",
    "desk_server",
    "desk_server.routes.study_routes",
    "desk_server.routes.knowledge_core_compilation_routes",
    "desk_server.knowledge_core_compile_runner",
    "desk_server.routes.study_activity_routes",
    "desk_server.routes.study_whiteboard_routes",
    "desk_server.routes.studio_routes",
    "desk_server.capabilities",  # internal runtime facts; no user-facing catalog
    "product_profile_policy",
    "learning.flashcards",
    "learning.learning_map",
    "learning.learning_plans",
    "learning.material_reader_port",
    "learning.knowledge_core_compilation_store",
    "learning.knowledge_core_compiler",
    "learning_owner",
    "learning_recovery",
    "activity_projection",
    "studio_store",
    "study_semantic_reviewer",
    "agent.graph_engine.tutor_contracts",
    "agent.graph_engine.tutor_branch_policy",
    "agent.graph_engine.tutor_retention",
    "agent.knowledge_post_node",
    "learning.tutor_practice",
    "agent.graph_engine.tutor_ports",
    "agent.graph_engine.tutor_nodes",
    "agent.graph_engine.tutor_builder",
    "agent.graph_engine.tutor_engine",
    "learning.practice_contract",
    "learning.practice_hints",
    "learning.practice_evaluation",
    "learning.whiteboard_contract",
    "learning.whiteboard",
    "learning.tutor_whiteboard",
)


def _add_runtime_paths(root: Path) -> None:
    for path in (
        root,
        root / "kabuqina",
        root / "site-packages",
        root / "site-packages" / "win32",
        root / "site-packages" / "win32" / "lib",
        root / "site-packages" / "pythonwin",
    ):
        if path.exists():
            sys.path.insert(0, str(path))


def _seed_import_environment(root: Path) -> None:
    smoke_root = Path(tempfile.gettempdir()) / "kabuqina-runtime-import-smoke"
    os.environ.setdefault("KABUQINA_BUNDLE_DIR", str(root))
    os.environ.setdefault("KABUQINA_DATA_DIR", str(smoke_root / "data"))
    os.environ.setdefault("KABUQINA_WORKSPACE", str(smoke_root / "workspace"))
    os.environ.setdefault("KABUQINA_HOME", str(smoke_root / "kabuqina-home"))
    os.environ.setdefault("KABUQINA_OVERLAY_LENIENT", "1")
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")


def verify_runtime_imports(root: Path) -> list[tuple[str, BaseException]]:
    _add_runtime_paths(root)
    _seed_import_environment(root)
    failures: list[tuple[str, BaseException]] = []
    for module in REQUIRED_IMPORTS:
        try:
            importlib.import_module(module)
        except Exception as exc:  # pragma: no cover - exercised by subprocess tests
            failures.append((module, exc))
    return failures


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: verify_runtime_imports.py <runtime-root>", file=sys.stderr)
        return 2
    root = Path(argv[1]).resolve()
    if not root.is_dir():
        print(f"runtime root not found: {root}", file=sys.stderr)
        return 2
    failures = verify_runtime_imports(root)
    if failures:
        for module, exc in failures:
            print(
                f"runtime import failed: {module}: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
        return 1
    print("runtime imports ok: " + ", ".join(REQUIRED_IMPORTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
