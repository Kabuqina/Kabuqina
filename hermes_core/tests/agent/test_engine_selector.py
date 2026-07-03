# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Phase 3.5 Task 10: agent engine selector precedence and validation.

Covers all four precedence levels (explicit arg > HERMES_AGENT_ENGINE > profile
config > default ``graph``), invalid-value handling for each source, blank-value
coercion, profile-aware ``HERMES_HOME`` resolution through the real config
loader, and the separate-process environment model (injected ``env`` mapping).
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest
import yaml

from agent.engine_selector import (
    DEFAULT_ENGINE,
    ENGINE_ENV_VAR,
    VALID_ENGINES,
    resolve_agent_engine,
)


# ── Level 4: default ──────────────────────────────────────────────────────

def test_default_is_graph_when_nothing_set():
    assert resolve_agent_engine(None, env={}, config={}) == "graph"
    assert DEFAULT_ENGINE == "graph"


def test_serialized_config_default_is_graph():
    from hermes_cli.config import DEFAULT_CONFIG

    assert DEFAULT_CONFIG["agent"]["engine"] == "graph"


def test_default_engine_is_a_valid_engine():
    assert DEFAULT_ENGINE in VALID_ENGINES


# ── Level 3: profile config ───────────────────────────────────────────────

def test_config_value_selects_engine():
    assert (
        resolve_agent_engine(None, env={}, config={"agent": {"engine": "graph"}})
        == "graph"
    )


def test_config_loop_rolls_back_graph_default():
    assert (
        resolve_agent_engine(None, env={}, config={"agent": {"engine": "loop"}})
        == "loop"
    )


def test_config_value_is_normalized():
    assert (
        resolve_agent_engine(None, env={}, config={"agent": {"engine": "  GRAPH "}})
        == "graph"
    )


def test_missing_agent_section_falls_back_to_default():
    assert resolve_agent_engine(None, env={}, config={"model": "x"}) == "graph"


def test_invalid_config_value_warns_and_falls_back(caplog):
    with caplog.at_level(logging.WARNING):
        result = resolve_agent_engine(
            None, env={}, config={"agent": {"engine": "banana"}}
        )
    assert result == "graph"
    assert any("banana" in rec.message for rec in caplog.records)


# ── Level 2: HERMES_AGENT_ENGINE environment override ─────────────────────

def test_env_overrides_config():
    assert (
        resolve_agent_engine(
            None,
            env={ENGINE_ENV_VAR: "graph"},
            config={"agent": {"engine": "loop"}},
        )
        == "graph"
    )


def test_env_loop_rolls_back_graph_config():
    assert (
        resolve_agent_engine(
            None,
            env={ENGINE_ENV_VAR: "loop"},
            config={"agent": {"engine": "graph"}},
        )
        == "loop"
    )


def test_blank_env_is_ignored():
    # Empty/whitespace HERMES_AGENT_ENGINE reads as unset, not invalid.
    assert (
        resolve_agent_engine(
            None, env={ENGINE_ENV_VAR: "   "}, config={"agent": {"engine": "graph"}}
        )
        == "graph"
    )


def test_invalid_env_raises():
    with pytest.raises(ValueError, match=ENGINE_ENV_VAR):
        resolve_agent_engine(None, env={ENGINE_ENV_VAR: "banana"}, config={})


def test_env_default_reads_os_environ(monkeypatch):
    monkeypatch.setenv(ENGINE_ENV_VAR, "graph")
    # No explicit env mapping → falls back to os.environ.
    assert resolve_agent_engine(None, config={}) == "graph"


# ── Level 1: explicit constructor argument ────────────────────────────────

def test_explicit_overrides_env_and_config():
    assert (
        resolve_agent_engine(
            "loop",
            env={ENGINE_ENV_VAR: "graph"},
            config={"agent": {"engine": "graph"}},
        )
        == "loop"
    )


def test_explicit_is_normalized():
    assert resolve_agent_engine("GRAPH", env={}, config={}) == "graph"


def test_blank_explicit_falls_through():
    # An empty explicit argument is "not provided", not invalid.
    assert (
        resolve_agent_engine("", env={ENGINE_ENV_VAR: "graph"}, config={}) == "graph"
    )


def test_invalid_explicit_raises():
    with pytest.raises(ValueError, match="agent_engine argument"):
        resolve_agent_engine("banana", env={}, config={})


# ── Profile-aware HERMES_HOME (real config loader) ────────────────────────

def _write_config(home, mapping):
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text(yaml.safe_dump(mapping), encoding="utf-8")


def test_profile_aware_home_reads_config(monkeypatch, tmp_path):
    home = tmp_path / "hermes"
    _write_config(home, {"agent": {"engine": "graph"}})
    monkeypatch.setenv("HERMES_HOME", str(home))
    # No injected config → loads the active profile's config.yaml under HERMES_HOME.
    assert resolve_agent_engine(None, env={}) == "graph"


def test_profile_aware_home_default_when_unset(monkeypatch, tmp_path):
    home = tmp_path / "hermes"
    _write_config(home, {"model": "x"})  # no agent.engine override
    monkeypatch.setenv("HERMES_HOME", str(home))
    # DEFAULT_CONFIG supplies agent.engine == "graph" via deep merge.
    assert resolve_agent_engine(None, env={}) == "graph"


def test_separate_process_environments_are_independent():
    # The web and gateway children read their own process env; the selector
    # honours whichever env mapping it is handed, modelling that isolation.
    web_env = {ENGINE_ENV_VAR: "graph"}
    gateway_env: dict[str, str] = {}
    cfg = {"agent": {"engine": "loop"}}
    assert resolve_agent_engine(None, env=web_env, config=cfg) == "graph"
    assert resolve_agent_engine(None, env=gateway_env, config=cfg) == "loop"


# ── Public dispatcher: AIAgent.run_conversation routes by self.agent_engine ──
# These exercise the actual seam (not just the resolver): a real AIAgent.method
# is invoked on a bare instance whose two engine bodies are stubbed, so the
# dispatch decision — and the "graph error must not fall back to loop" rule — are
# verified without running a full conversation. (Review P2-6.)


def _bare_agent(engine: str):
    """An AIAgent instance with only ``agent_engine`` set, bypassing __init__."""
    import run_agent

    agent = object.__new__(run_agent.AIAgent)
    agent.agent_engine = engine
    return agent


def test_run_conversation_dispatches_to_graph_when_selected():
    import run_agent

    agent = _bare_agent("graph")
    agent._run_conversation_graph = MagicMock(return_value={"final_response": "graph"})
    agent._run_conversation_loop = MagicMock(return_value={"final_response": "loop"})

    out = run_agent.AIAgent.run_conversation(agent, "hello", task_id="t1")

    assert out == {"final_response": "graph"}
    agent._run_conversation_graph.assert_called_once()
    agent._run_conversation_loop.assert_not_called()
    _, kwargs = agent._run_conversation_graph.call_args
    assert kwargs["user_message"] == "hello"
    assert kwargs["task_id"] == "t1"


def test_run_conversation_dispatches_to_loop_by_default():
    import run_agent

    agent = _bare_agent("loop")
    agent._run_conversation_graph = MagicMock()
    agent._run_conversation_loop = MagicMock(return_value={"final_response": "loop"})

    out = run_agent.AIAgent.run_conversation(agent, "hello")

    assert out == {"final_response": "loop"}
    agent._run_conversation_loop.assert_called_once()
    agent._run_conversation_graph.assert_not_called()


def test_graph_failure_does_not_fall_back_to_loop():
    """A graph exception must propagate, never re-run the loop for the same turn
    (a tool may already have mutated external state — see run_conversation)."""
    import run_agent

    agent = _bare_agent("graph")
    agent._run_conversation_graph = MagicMock(side_effect=RuntimeError("graph boom"))
    agent._run_conversation_loop = MagicMock()

    with pytest.raises(RuntimeError, match="graph boom"):
        run_agent.AIAgent.run_conversation(agent, "hello")

    agent._run_conversation_loop.assert_not_called()
