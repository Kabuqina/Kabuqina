# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Phase 3.5 graph engine: pure node functions.

Each function corresponds to exactly one ``GraphServices`` method and
delegates everything through the LangGraph ``config`` (``RunnableConfig``).
Services and per-turn parameters travel via ``config["configurable"]``.

No LangGraph imports.
"""

from typing import Any

from agent.graph_engine.ports import GraphServices


def _services(config: Any) -> GraphServices:
    """Extract the service adapter from the LangGraph configurable dict."""
    if config is None:
        raise RuntimeError("GraphServices not available in node config")
    return config["configurable"]["services"]


def _get_configurable(config: Any, key: str, default: Any = None) -> Any:
    """Safely read a configurable value."""
    if config is None:
        return default
    return config.get("configurable", {}).get(key, default)


# ── Initialisation ───────────────────────────────────────────────────────

def initialize_turn(state: dict[str, Any], *, config = None) -> dict[str, Any]:
    """Bootstrap a fresh agent turn."""
    svc = _services(config)
    return svc.initialize_turn(
        state,
        user_message=state.get("user_message"),
        system_message=state.get("system_message"),
        conversation_history=state.get("conversation_history"),
        task_id=state.get("effective_task_id"),
        stream_callback=_get_configurable(config, "stream_callback"),
        persist_user_message=_get_configurable(config, "persist_user_message"),
    )


# ── Request / response ───────────────────────────────────────────────────

def prepare_request(state: dict[str, Any], *, config = None) -> dict[str, Any]:
    return _services(config).prepare_request(state)


def call_transport(state: dict[str, Any], *, config = None) -> dict[str, Any]:
    return _services(config).call_transport(state)


def process_response(state: dict[str, Any], *, config = None) -> dict[str, Any]:
    return _services(config).process_response(state)


def handle_transport_error(state: dict[str, Any], *, config = None) -> dict[str, Any]:
    return _services(config).handle_transport_error(state)


# ── Tool / steer ─────────────────────────────────────────────────────────

def dispatch_tools(state: dict[str, Any], *, config = None) -> dict[str, Any]:
    return _services(config).dispatch_tools(state)


def apply_steer(state: dict[str, Any], *, config = None) -> dict[str, Any]:
    return _services(config).apply_steer(state)


# ── Budget ───────────────────────────────────────────────────────────────

def summarize_on_budget(state: dict[str, Any], *, config = None) -> dict[str, Any]:
    return _services(config).summarize_on_budget(state)


# ── Finalisation ─────────────────────────────────────────────────────────

def finish(state: dict[str, Any], *, config = None) -> dict[str, Any]:
    return _services(config).apply_exit_policy(state)
