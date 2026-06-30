# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Phase 3.5 Task 10: agent engine selector precedence and validation.

Covers all four precedence levels (explicit arg > HERMES_AGENT_ENGINE > profile
config > default ``loop``), invalid-value handling for each source, blank-value
coercion, profile-aware ``HERMES_HOME`` resolution through the real config
loader, and the separate-process environment model (injected ``env`` mapping).
"""

from __future__ import annotations

import logging

import pytest
import yaml

from agent.engine_selector import (
    DEFAULT_ENGINE,
    ENGINE_ENV_VAR,
    VALID_ENGINES,
    resolve_agent_engine,
)


# ── Level 4: default ──────────────────────────────────────────────────────

def test_default_is_loop_when_nothing_set():
    assert resolve_agent_engine(None, env={}, config={}) == "loop"
    assert DEFAULT_ENGINE == "loop"


def test_default_engine_is_a_valid_engine():
    assert DEFAULT_ENGINE in VALID_ENGINES


# ── Level 3: profile config ───────────────────────────────────────────────

def test_config_value_selects_engine():
    assert (
        resolve_agent_engine(None, env={}, config={"agent": {"engine": "graph"}})
        == "graph"
    )


def test_config_value_is_normalized():
    assert (
        resolve_agent_engine(None, env={}, config={"agent": {"engine": "  GRAPH "}})
        == "graph"
    )


def test_missing_agent_section_falls_back_to_default():
    assert resolve_agent_engine(None, env={}, config={"model": "x"}) == "loop"


def test_invalid_config_value_warns_and_falls_back(caplog):
    with caplog.at_level(logging.WARNING):
        result = resolve_agent_engine(
            None, env={}, config={"agent": {"engine": "banana"}}
        )
    assert result == "loop"
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
    # DEFAULT_CONFIG supplies agent.engine == "loop" via deep merge.
    assert resolve_agent_engine(None, env={}) == "loop"


def test_separate_process_environments_are_independent():
    # The web and gateway children read their own process env; the selector
    # honours whichever env mapping it is handed, modelling that isolation.
    web_env = {ENGINE_ENV_VAR: "graph"}
    gateway_env: dict[str, str] = {}
    cfg = {"agent": {"engine": "loop"}}
    assert resolve_agent_engine(None, env=web_env, config=cfg) == "graph"
    assert resolve_agent_engine(None, env=gateway_env, config=cfg) == "loop"
