# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Compatibility guardrails for the v0.3.0 slim & focus pass.

These pin the retained core surface so the bulk-deletion phases (removing
upstream gateways, tools, plugins, skills, and TUI/ACP/website subtrees)
cannot silently break the imports the desktop product depends on. A red test
here means a deletion went too far — catch it at the deletion commit, not in a
later runtime smoke.

See ``docs/superpowers/specs/2026-06-19-v0.3.0-slim-and-focus-plan.md``.
"""

import ast
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


def test_run_agent_still_exports_ai_agent():
    from run_agent import AIAgent

    assert AIAgent.__name__ == "AIAgent"


def test_legacy_core_modules_still_import():
    import kabuqina_constants
    import kabuqina_logging
    import kabuqina_state
    import kabuqina_time
    import hermes_constants
    import hermes_logging
    import hermes_state
    import hermes_time

    assert hermes_constants is kabuqina_constants
    assert hermes_logging is kabuqina_logging
    assert hermes_state is kabuqina_state
    assert hermes_time is kabuqina_time


def test_legacy_cli_package_aliases_canonical_package():
    import hermes_cli
    import kabuqina_cli

    assert hermes_cli is kabuqina_cli


@pytest.mark.parametrize("import_order", ["legacy-first", "canonical-first"])
def test_legacy_cli_stateful_submodules_share_canonical_runtime(import_order):
    """Normal imports must never execute a canonical submodule twice."""

    script = textwrap.dedent(
        f"""
        import importlib
        import sys

        order = {import_order!r}
        names = ("config", "config_home", "auth")
        if order == "legacy-first":
            legacy = {{
                name: importlib.import_module(f"hermes_cli.{{name}}")
                for name in names
            }}
            canonical = {{
                name: importlib.import_module(f"kabuqina_cli.{{name}}")
                for name in names
            }}
        else:
            canonical = {{
                name: importlib.import_module(f"kabuqina_cli.{{name}}")
                for name in names
            }}
            legacy = {{
                name: importlib.import_module(f"hermes_cli.{{name}}")
                for name in names
            }}

        import hermes_cli
        import kabuqina_cli

        assert hermes_cli is kabuqina_cli
        for name in names:
            assert legacy[name] is canonical[name], name
            assert sys.modules[f"hermes_cli.{{name}}"] is canonical[name]
            assert sys.modules[f"kabuqina_cli.{{name}}"] is canonical[name]

        assert legacy["config"].DEFAULT_CONFIG is canonical["config"].DEFAULT_CONFIG
        marker = object()
        canonical["auth"].PROVIDER_REGISTRY["__a_r3_alias_probe__"] = marker
        assert legacy["auth"].PROVIDER_REGISTRY["__a_r3_alias_probe__"] is marker
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, (
        f"{import_order} subprocess failed\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def test_owned_public_symbol_aliases_point_to_canonical_objects():
    from acp_adapter.server import HermesACPAgent, KabuqinaACPAgent
    from kabuqina_cli.providers import HermesOverlay, KabuqinaOverlay
    from tools.mcp_oauth import HermesTokenStorage, KabuqinaTokenStorage

    assert HermesACPAgent is KabuqinaACPAgent
    assert HermesOverlay is KabuqinaOverlay
    assert HermesTokenStorage is KabuqinaTokenStorage


def test_kabuqina_agent_facade_matches_run_agent():
    from kabuqina_core.agent import AIAgent
    from run_agent import AIAgent as LegacyAIAgent

    assert AIAgent is LegacyAIAgent


def test_kept_modules_do_not_depend_on_deleted_cli_gateway_bridge():
    core_root = Path(__file__).parents[2]

    for relative_path in (
        "kabuqina_cli/profiles.py",
        "kabuqina_cli/dump.py",
    ):
        tree = ast.parse((core_root / relative_path).read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module != "hermes_cli.gateway"
            elif isinstance(node, ast.Import):
                assert all(alias.name != "hermes_cli.gateway" for alias in node.names)
