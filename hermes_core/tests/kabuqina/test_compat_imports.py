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


def test_run_agent_still_exports_ai_agent():
    from run_agent import AIAgent

    assert AIAgent.__name__ == "AIAgent"


def test_legacy_core_modules_still_import():
    import hermes_constants
    import hermes_logging
    import hermes_state
    import hermes_time

    assert hermes_constants is not None
    assert hermes_logging is not None
    assert hermes_state is not None
    assert hermes_time is not None


def test_kabuqina_agent_facade_matches_run_agent():
    from kabuqina_core.agent import AIAgent
    from run_agent import AIAgent as LegacyAIAgent

    assert AIAgent is LegacyAIAgent
