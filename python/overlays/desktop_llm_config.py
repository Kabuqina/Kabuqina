# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Pin default model / provider for HermesDesk from Tauri-provided env.

Hermes reads ``config.yaml`` ``model`` (string or dict). The shell passes:

    HERMESDESK_MODEL               optional default model id
    HERMESDESK_INFERENCE_PROVIDER  optional, e.g. ``custom`` for OpenAI-compatible URLs
    HERMESDESK_API_BASE_URL        custom chat/completions base (typically ends with /v1)
    HERMESDESK_API_MODE            optional concrete wire protocol; empty means automatic
    HERMESDESK_PROVIDER            when ``deepseek``, seeds ``model.provider`` + ``reasoning_config``

If ``model.base_url`` is never written, ``provider: custom`` with an empty ``providers:`` block
can break or confuse resolution for code paths that only read YAML. The API key still comes from
the Tauri bridge; this overlay syncs non-secret routing fields on every Python boot.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger("hermesdesk.model")

_DEEPSEEK_DEFAULT_MODEL = "deepseek-v4-flash"

# Default max output tokens.  Providers often default to 4096 which causes
# "finish_reason='length'" truncation on complex tool-calling turns.
# 16384 is a safe floor that stays well within any modern model's context window.
_DEFAULT_MAX_TOKENS = 16384
_VALID_API_MODES = {"chat_completions", "anthropic_messages"}


def _apply_api_mode(model_block: dict, raw_mode: str) -> str | None:
    normalized = raw_mode.strip().lower()
    if not normalized:
        model_block.pop("api_mode", None)
        return None
    if normalized not in _VALID_API_MODES:
        log.warning(
            "invalid HERMESDESK_API_MODE=%r; using automatic detection",
            raw_mode,
        )
        model_block.pop("api_mode", None)
        return None
    model_block["api_mode"] = normalized
    return normalized


def _apply_deepseek_desk_seed(model: str, api_base: str, api_mode: str) -> None:
    """Write DeepSeek-oriented ``model`` block including default reasoning (high)."""
    try:
        from hermes_cli.config import load_config, save_config  # type: ignore
    except Exception as e:
        log.warning("hermes_cli.config not importable; skipping deepseek seed (%s)", e)
        return

    try:
        cfg = load_config() or {}
    except Exception as e:
        log.warning("could not load config for deepseek seed (%s)", e)
        cfg = {}

    prev = cfg.get("model")
    default_model = model
    if not default_model:
        if isinstance(prev, dict):
            d = prev.get("default")
            if isinstance(d, str) and d.strip():
                default_model = d.strip()
        elif isinstance(prev, str) and prev.strip():
            default_model = prev.strip()
    if not default_model:
        default_model = _DEEPSEEK_DEFAULT_MODEL

    if isinstance(prev, dict) and isinstance(prev.get("reasoning_config"), dict):
        reasoning_cfg = dict(prev["reasoning_config"])
    else:
        reasoning_cfg = {"enabled": True, "effort": "high"}

    new_block: dict = {
        "provider": "deepseek",
        "default": default_model,
        "reasoning_config": reasoning_cfg,
    }
    # Seed max_tokens only when the user hasn't set one yet.
    if isinstance(prev, dict) and prev.get("max_tokens") is not None:
        try:
            new_block["max_tokens"] = int(prev["max_tokens"])
        except (TypeError, ValueError):
            new_block["max_tokens"] = _DEFAULT_MAX_TOKENS
    else:
        new_block["max_tokens"] = _DEFAULT_MAX_TOKENS
    if api_base:
        new_block["base_url"] = api_base
    elif isinstance(prev, dict):
        prev_base = str(prev.get("base_url") or "").strip()
        if prev_base:
            new_block["base_url"] = prev_base

    if isinstance(prev, dict):
        model_block = {**prev, **new_block}
    else:
        model_block = new_block
    resolved_mode = _apply_api_mode(model_block, api_mode)
    cfg["model"] = model_block

    try:
        save_config(cfg)
        log.info(
            "HermesDesk DeepSeek model seed applied (model=%r base_url_set=%s api_mode=%r)",
            default_model,
            bool(str(new_block.get("base_url") or "").strip()),
            resolved_mode or "auto",
        )
    except Exception:
        log.exception("failed to save Hermes DeepSeek model seed")


def install() -> None:
    model = os.environ.get("HERMESDESK_MODEL", "").strip()
    inf = os.environ.get("HERMESDESK_INFERENCE_PROVIDER", "").strip()
    api_base = os.environ.get("HERMESDESK_API_BASE_URL", "").strip()
    api_mode = os.environ.get("HERMESDESK_API_MODE", "")
    desk_provider = os.environ.get("HERMESDESK_PROVIDER", "").strip().lower()

    if desk_provider == "deepseek":
        _apply_deepseek_desk_seed(model, api_base, api_mode)
        return

    if not model and not inf and not api_base:
        return

    try:
        from hermes_cli.config import load_config, save_config  # type: ignore
    except Exception as e:
        log.warning("hermes_cli.config not importable; skipping model seed (%s)", e)
        return

    try:
        cfg = load_config() or {}
    except Exception as e:
        log.warning("could not load config for model seed (%s)", e)
        cfg = {}

    provider_for_model = desk_provider or ("custom" if inf == "custom" else "")

    if inf == "custom" or (api_base and provider_for_model):
        prev = cfg.get("model")
        default_model = model
        prev_base = ""
        if isinstance(prev, dict):
            if not default_model:
                d = prev.get("default")
                if isinstance(d, str) and d.strip():
                    default_model = d.strip()
            prev_base = (str(prev.get("base_url") or prev.get("baseurl") or "")).strip()
        elif isinstance(prev, str) and prev.strip():
            if not default_model:
                default_model = prev.strip()
        if not default_model:
            default_model = "gpt-4o-mini"

        new_block: dict = {
            "default": default_model,
            "provider": provider_for_model or "custom",
        }
        # Seed max_tokens only when the user hasn't set one yet.
        if isinstance(prev, dict) and prev.get("max_tokens") is not None:
            try:
                new_block["max_tokens"] = int(prev["max_tokens"])
            except (TypeError, ValueError):
                new_block["max_tokens"] = _DEFAULT_MAX_TOKENS
        else:
            new_block["max_tokens"] = _DEFAULT_MAX_TOKENS
        if api_base:
            new_block["base_url"] = api_base
        elif prev_base:
            new_block["base_url"] = prev_base

        if isinstance(prev, dict):
            model_block = {**prev, **new_block}
        else:
            model_block = new_block
        _apply_api_mode(model_block, api_mode)
        cfg["model"] = model_block
    elif model:
        prev = cfg.get("model")
        if isinstance(prev, dict):
            merged = {**prev, "default": model}
            if prev.get("max_tokens") is None:
                merged["max_tokens"] = _DEFAULT_MAX_TOKENS
            _apply_api_mode(merged, api_mode)
            cfg["model"] = merged
        else:
            model_block = {"default": model, "max_tokens": _DEFAULT_MAX_TOKENS}
            _apply_api_mode(model_block, api_mode)
            cfg["model"] = model_block

    try:
        save_config(cfg)
        m = cfg.get("model")
        has_bu = bool(
            api_base
            or (isinstance(m, dict) and str(m.get("base_url") or "").strip())
        )
        log.info(
            "HermesDesk model seed applied (inference=%r model=%r base_url_set=%s api_mode=%r)",
            inf,
            model,
            has_bu,
            (
                m.get("api_mode", "auto")
                if isinstance(m, dict)
                else "auto"
            ),
        )
    except Exception:
        log.exception("failed to save Hermes model seed")
