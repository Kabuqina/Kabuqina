# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Phase 3.5 strangler selector: choose the agent conversation engine.

Resolves which execution engine ``AIAgent.run_conversation`` dispatches to.
Precedence, highest first:

1. an explicit ``AIAgent(agent_engine=...)`` constructor argument;
2. the ``HERMES_AGENT_ENGINE`` environment variable;
3. ``agent.engine`` from the active profile's ``config.yaml``;
4. the migration default, ``loop``.

Only ``loop`` and ``graph`` are valid.  An invalid *explicit* or *environment*
value raises ``ValueError`` — those are operator intent and a typo must fail
loud.  An invalid *config* value logs a warning and falls back to ``loop`` so a
bad user file never bricks startup.

This module performs no LangGraph imports and is import-cheap: the profile
config is read lazily through :func:`hermes_cli.config_loader.load_config`,
which is ``HERMES_HOME``-aware, so each process (CLI, web, gateway child) reads
its own environment and profile without extra plumbing.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Mapping, Optional

logger = logging.getLogger(__name__)

#: The two engines the selector understands.
VALID_ENGINES = ("loop", "graph")

#: Migration default — the legacy loop stays the default until Task 11 flips it.
DEFAULT_ENGINE = "loop"

#: Per-process override environment variable.
ENGINE_ENV_VAR = "HERMES_AGENT_ENGINE"


def _coerce(value: Any) -> Optional[str]:
    """Normalise a candidate to a lowercased, stripped string, or ``None``.

    ``None`` and blank/whitespace-only values are treated as "not provided" so
    an empty constructor argument or ``HERMES_AGENT_ENGINE=`` reads as unset
    rather than as an invalid engine.
    """
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def _validate_strict(value: str, *, source: str) -> str:
    """Return a validated engine name or raise ``ValueError`` (operator intent)."""
    if value not in VALID_ENGINES:
        raise ValueError(
            f"Invalid agent engine {value!r} from {source}; "
            f"valid values are {', '.join(VALID_ENGINES)}"
        )
    return value


def _config_engine(config: Optional[Mapping[str, Any]]) -> Optional[str]:
    """Read ``agent.engine`` from the given config, or load the active profile's."""
    if config is None:
        try:
            from hermes_cli.config_loader import load_config

            config = load_config()
        except Exception:  # pragma: no cover - defensive; never block startup
            logger.warning(
                "Could not load config to resolve agent engine; using default %r",
                DEFAULT_ENGINE,
            )
            return None
    try:
        return config.get("agent", {}).get("engine")  # type: ignore[union-attr]
    except AttributeError:
        return None


def resolve_agent_engine(
    explicit: Any = None,
    *,
    env: Optional[Mapping[str, str]] = None,
    config: Optional[Mapping[str, Any]] = None,
) -> str:
    """Resolve the agent engine name (``"loop"`` or ``"graph"``).

    Args:
        explicit: the ``agent_engine`` constructor argument, if any.
        env: environment mapping to read ``HERMES_AGENT_ENGINE`` from
            (defaults to ``os.environ`` — injectable for tests and to model
            separate web/gateway process environments).
        config: an already-loaded config mapping (defaults to the active
            profile via ``load_config``).

    Raises:
        ValueError: if an explicit argument or environment value is non-blank
            but not one of :data:`VALID_ENGINES`.
    """
    # 1. explicit constructor argument
    explicit_value = _coerce(explicit)
    if explicit_value is not None:
        return _validate_strict(explicit_value, source="agent_engine argument")

    # 2. HERMES_AGENT_ENGINE environment override
    env_map = env if env is not None else os.environ
    env_value = _coerce(env_map.get(ENGINE_ENV_VAR))
    if env_value is not None:
        return _validate_strict(
            env_value, source=f"{ENGINE_ENV_VAR} environment variable"
        )

    # 3. agent.engine from the active profile's config.yaml
    config_value = _coerce(_config_engine(config))
    if config_value is not None:
        if config_value in VALID_ENGINES:
            return config_value
        logger.warning(
            "Invalid agent.engine %r in config; falling back to %r",
            config_value,
            DEFAULT_ENGINE,
        )

    # 4. migration default
    return DEFAULT_ENGINE
