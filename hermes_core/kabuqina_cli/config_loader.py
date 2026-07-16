# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""The config loader core: read/merge/expand/save ``config.yaml`` for kabuqina_cli.

Extracted from ``kabuqina_cli/config.py`` — the top of the config dependency stack:
``read_raw_config`` -> ``load_config`` (deep-merge over DEFAULT_CONFIG + env
expansion + normalization, with mtime caches) -> ``save_config``. Builds on the
extracted leaves (defaults/merge/home/paths/managed). ``kabuqina_cli.config``
re-exports every name (and its consumers — validation, migration, the CLI
commands — stay in the facade and reach ``load_config`` via that re-export).
"""

from __future__ import annotations

import copy
import logging

import yaml

from typing import Any, Dict, Optional, Tuple

from kabuqina_cli.config_defaults import DEFAULT_CONFIG
from kabuqina_cli.config_merge import (
    _deep_merge,
    _expand_env_vars,
    _normalize_max_turns_config,
    _normalize_root_model_keys,
    _preserve_env_ref_templates,
)
from kabuqina_cli.config_home import ensure_kabuqina_home, _secure_file
from kabuqina_cli.config_paths import get_config_path
from kabuqina_cli.config_managed import is_managed, managed_error

logger = logging.getLogger(__name__)


_LAST_EXPANDED_CONFIG_BY_PATH: Dict[str, Any] = {}


_LOAD_CONFIG_CACHE: Dict[str, Tuple[int, int, Dict[str, Any]]] = {}


_RAW_CONFIG_CACHE: Dict[str, Tuple[int, int, Dict[str, Any]]] = {}


_SECURITY_COMMENT = """
# ── Security ──────────────────────────────────────────────────────────
# Secret redaction is OFF by default — tool output (terminal stdout,
# read_file results, web content) passes through unmodified. Set
# redact_secrets to true to mask strings that look like API keys, tokens,
# and passwords before they enter the model context and logs.
# tirith pre-exec scanning is enabled by default when the tirith binary
# is available. Configure via security.tirith_* keys or env vars
# (TIRITH_ENABLED, TIRITH_BIN, TIRITH_TIMEOUT, TIRITH_FAIL_OPEN).
#
# security:
#   redact_secrets: true
#   tirith_enabled: true
#   tirith_path: "tirith"
#   tirith_timeout: 5
#   tirith_fail_open: true
"""


_FALLBACK_COMMENT = """
# ── Fallback Model ────────────────────────────────────────────────────
# Automatic provider failover when primary is unavailable.
# Uncomment and configure to enable. Triggers on rate limits (429),
# overload (529), service errors (503), or connection failures.
#
# Supported providers:
#   openrouter   (OPENROUTER_API_KEY)  — routes to any model
#   nous         (OAuth — kabuqina auth) — Nous Portal
#   zai          (ZAI_API_KEY)         — Z.AI / GLM
#   kimi-coding  (KIMI_API_KEY)        — Kimi / Moonshot
#   kimi-coding-cn (KIMI_CN_API_KEY)   — Kimi / Moonshot (China)
#   minimax      (MINIMAX_API_KEY)     — MiniMax
#   minimax-cn   (MINIMAX_CN_API_KEY)  — MiniMax (China)
#
# For custom OpenAI-compatible endpoints, add base_url and key_env.
#
# fallback_model:
#   provider: openrouter
#   model: anthropic/claude-sonnet-4
"""


def read_raw_config() -> Dict[str, Any]:
    """Read ~/.kabuqina/config.yaml as-is, without merging defaults or migrating.

    Returns the raw YAML dict, or ``{}`` if the file doesn't exist or can't
    be parsed.  Use this for lightweight config reads where you just need a
    single value and don't want the overhead of ``load_config()``'s deep-merge
    + migration pipeline.

    Cached on the config file's (mtime_ns, size) — same strategy as
    ``load_config()``. Returns a deepcopy on every call since some callers
    mutate the result before passing to ``save_config()``.
    """
    try:
        config_path = get_config_path()
        st = config_path.stat()
        cache_key = (st.st_mtime_ns, st.st_size)
    except (FileNotFoundError, OSError):
        return {}

    path_key = str(config_path)
    cached = _RAW_CONFIG_CACHE.get(path_key)
    if cached is not None and cached[:2] == cache_key:
        return copy.deepcopy(cached[2])

    try:
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return {}

    if not isinstance(data, dict):
        data = {}
    _RAW_CONFIG_CACHE[path_key] = (cache_key[0], cache_key[1], copy.deepcopy(data))
    return data


def load_config() -> Dict[str, Any]:
    """Load configuration from ~/.kabuqina/config.yaml.

    Cached on the config file's (mtime_ns, size). Returns a deepcopy of
    the cached value when unchanged, since most call sites mutate the
    result (e.g. ``cfg["model"]["default"] = ...`` before ``save_config``).
    The cache is keyed on ``str(config_path)`` so profile switches
    (which change ``HERMES_HOME`` and therefore ``get_config_path()``)
    don't collide.
    """
    ensure_kabuqina_home()
    config_path = get_config_path()
    path_key = str(config_path)

    try:
        st = config_path.stat()
        cache_key: Optional[Tuple[int, int]] = (st.st_mtime_ns, st.st_size)
    except FileNotFoundError:
        cache_key = None

    cached = _LOAD_CONFIG_CACHE.get(path_key)
    if cached is not None and cache_key is not None and cached[:2] == cache_key:
        return copy.deepcopy(cached[2])

    config = copy.deepcopy(DEFAULT_CONFIG)

    if cache_key is not None:
        try:
            with open(config_path, encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}

            if "max_turns" in user_config:
                agent_user_config = dict(user_config.get("agent") or {})
                if agent_user_config.get("max_turns") is None:
                    agent_user_config["max_turns"] = user_config["max_turns"]
                user_config["agent"] = agent_user_config
                user_config.pop("max_turns", None)

            config = _deep_merge(config, user_config)
        except Exception as e:
            print(f"Warning: Failed to load config: {e}")

    normalized = _normalize_root_model_keys(_normalize_max_turns_config(config))
    expanded = _expand_env_vars(normalized)
    _LAST_EXPANDED_CONFIG_BY_PATH[path_key] = copy.deepcopy(expanded)
    if cache_key is not None:
        _LOAD_CONFIG_CACHE[path_key] = (cache_key[0], cache_key[1], copy.deepcopy(expanded))
    else:
        _LOAD_CONFIG_CACHE.pop(path_key, None)
    return expanded


def save_config(config: Dict[str, Any]):
    """Save configuration to ~/.kabuqina/config.yaml."""
    if is_managed():
        managed_error("save configuration")
        return
    from utils import atomic_yaml_write

    ensure_kabuqina_home()
    config_path = get_config_path()
    current_normalized = _normalize_root_model_keys(_normalize_max_turns_config(config))
    normalized = current_normalized
    raw_existing = _normalize_root_model_keys(_normalize_max_turns_config(read_raw_config()))
    if raw_existing:
        normalized = _preserve_env_ref_templates(
            normalized,
            raw_existing,
            _LAST_EXPANDED_CONFIG_BY_PATH.get(str(config_path)),
        )

    # Build optional commented-out sections for features that are off by
    # default or only relevant when explicitly configured.
    parts = []
    sec = normalized.get("security", {})
    if not sec or sec.get("redact_secrets") is None:
        parts.append(_SECURITY_COMMENT)
    fb = normalized.get("fallback_model", {})
    fb_is_valid = False
    if isinstance(fb, list):
        fb_is_valid = any(isinstance(e, dict) and e.get("provider") and e.get("model") for e in fb)
    elif isinstance(fb, dict):
        fb_is_valid = bool(fb.get("provider") and fb.get("model"))
    if not fb_is_valid:
        parts.append(_FALLBACK_COMMENT)

    atomic_yaml_write(
        config_path,
        normalized,
        extra_content="".join(parts) if parts else None,
    )
    _secure_file(config_path)
    _LAST_EXPANDED_CONFIG_BY_PATH[str(config_path)] = copy.deepcopy(current_normalized)
