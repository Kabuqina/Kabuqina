"""
Configuration management for Hermes Agent.

Config files are stored in ~/.hermes/ for easy access:
- ~/.hermes/config.yaml  - All settings (model, toolsets, terminal, etc.)
- ~/.hermes/.env         - API keys and secrets

This module provides:
- hermes config          - Show current configuration
- hermes config edit     - Open config in editor
- hermes config set      - Set a specific value
- hermes config wizard   - Re-run setup wizard
"""

import copy
import logging
import os
import platform
import re
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)

# The ~/.hermes/.env read/write cluster (+ its env-only constants) now lives
# in hermes_cli.config_env; re-export every name so existing
# hermes_cli.config.* imports + test monkeypatches keep resolving the same.
from hermes_cli.config_env import (  # noqa: F401
    _check_non_ascii_credential,
    _ENV_VAR_NAME_RE,
    _EXTRA_ENV_KEYS,
    get_env_path,
    get_env_value,
    _IS_WINDOWS,
    load_env,
    redact_key,
    reload_env,
    remove_env_value,
    sanitize_env_file,
    _sanitize_env_lines,
    save_anthropic_api_key,
    save_anthropic_oauth_token,
    save_env_value,
    save_env_value_secure,
    use_anthropic_claude_code_credentials,
)
# The config loader core (read_raw_config/load_config/save_config + caches)
# now lives in hermes_cli.config_loader; re-export every name so existing
# hermes_cli.config.* imports + monkeypatches keep resolving the same.
from hermes_cli.config_loader import (  # noqa: F401
    _FALLBACK_COMMENT,
    _LAST_EXPANDED_CONFIG_BY_PATH,
    load_config,
    _LOAD_CONFIG_CACHE,
    _RAW_CONFIG_CACHE,
    read_raw_config,
    save_config,
    _SECURITY_COMMENT,
)

import yaml

from hermes_cli.colors import Colors, color
from hermes_cli.default_soul import DEFAULT_SOUL_MD


# =============================================================================
# Managed mode (NixOS declarative config)
# =============================================================================

_MANAGED_TRUE_VALUES = ("true", "1", "yes")
_MANAGED_SYSTEM_NAMES = {
    "brew": "Homebrew",
    "homebrew": "Homebrew",
    "nix": "NixOS",
    "nixos": "NixOS",
}


# Managed-install / container detection now lives in hermes_cli.config_managed
# (a leaf below config); re-export so existing hermes_cli.config.* imports work.
from hermes_cli.config_managed import (  # noqa: F401
    format_managed_message,
    get_container_exec_info,
    get_managed_system,
    get_managed_update_command,
    is_managed,
    managed_error,
    recommended_update_command,
)


# =============================================================================
# Container-aware CLI (NixOS container mode)
# =============================================================================


# =============================================================================
# Config paths
# =============================================================================

# Re-export from hermes_constants — canonical definition lives there.
from hermes_constants import get_hermes_home  # noqa: F811,E402
from utils import atomic_replace

# Config path resolvers now live in hermes_cli.config_paths (a leaf below
# the loader core); re-export so existing hermes_cli.config.* imports work.
from hermes_cli.config_paths import (  # noqa: F401
    get_config_path,
    get_project_root,
    save_config_value,
)


# Home-dir setup + file/dir security now live in hermes_cli.config_home
# (above config_managed, below the env/load layers); re-export so existing
# hermes_cli.config.* imports keep working.
from hermes_cli.config_home import (  # noqa: F401
    _ensure_default_soul_md,
    ensure_hermes_home,
    _ensure_hermes_home_managed,
    _is_container,
    _secure_dir,
    _secure_file,
)


# =============================================================================
# Config loading/saving
# =============================================================================

# DEFAULT_CONFIG now lives in hermes_cli.config_defaults (pure data);
# re-export it so existing hermes_cli.config.DEFAULT_CONFIG imports work.
from hermes_cli.config_defaults import DEFAULT_CONFIG  # noqa: F401

# =============================================================================
# Config Migration System
# =============================================================================

# Env-var schema data (ENV_VARS_BY_VERSION, REQUIRED_ENV_VARS, OPTIONAL_ENV_VARS)
# now lives in hermes_cli.config_env_schema (pure data); re-export so existing
# hermes_cli.config.* imports keep working.
from hermes_cli.config_env_schema import (  # noqa: F401
    ENV_VARS_BY_VERSION,
    OPTIONAL_ENV_VARS,
    REQUIRED_ENV_VARS,
)


def get_missing_env_vars(required_only: bool = False) -> List[Dict[str, Any]]:
    """
    Check which environment variables are missing.
    
    Returns list of dicts with var info for missing variables.
    """
    missing = []
    
    # Check required vars
    for var_name, info in REQUIRED_ENV_VARS.items():
        if not get_env_value(var_name):
            missing.append({"name": var_name, **info, "is_required": True})
    
    # Check optional vars (if not required_only)
    if not required_only:
        for var_name, info in OPTIONAL_ENV_VARS.items():
            if not get_env_value(var_name):
                missing.append({"name": var_name, **info, "is_required": False})
    
    return missing


def _set_nested(config, dotted_key: str, value):
    """Set a value at an arbitrarily nested dotted key path.

    Supports both dict and list navigation:
      _set_nested(c, "a.b.c", 1)     → c["a"]["b"]["c"] = 1
      _set_nested(c, "a.0.b", 1)     → c["a"][0]["b"] = 1
      _set_nested(c, "providers.1", "x") → c["providers"][1] = "x"

    Intermediate dicts are created on demand.  List indices are parsed
    from numeric path segments; the referenced index must already exist
    (we do not grow lists — the user is navigating into structure they
    wrote themselves).  If a segment targets a non-container leaf
    (scalar), the leaf is replaced with a fresh dict so the write can
    proceed — this preserves the pre-existing behavior for bare scalar
    overrides (e.g. setting ``a.b.c`` where ``a.b`` was previously a
    string).

    Guards against #17876: before this fix the code unconditionally
    replaced any non-dict value (including lists) with ``{}``, silently
    destroying list-typed config like ``custom_providers`` whenever a
    caller used an indexed path.
    """
    parts = dotted_key.split(".")
    current = config
    for part in parts[:-1]:
        if isinstance(current, list):
            try:
                idx = int(part)
            except (TypeError, ValueError):
                raise TypeError(
                    f"Cannot navigate into list at key {dotted_key!r}: "
                    f"segment {part!r} is not a numeric index"
                )
            current = current[idx]
        elif isinstance(current, dict):
            existing = current.get(part)
            # Preserve dicts and lists; replace missing/scalar with a fresh dict.
            if part not in current or not isinstance(existing, (dict, list)):
                current[part] = {}
            current = current[part]
        else:
            raise TypeError(
                f"Cannot navigate into {type(current).__name__} at key {dotted_key!r}"
            )
    last = parts[-1]
    if isinstance(current, list):
        current[int(last)] = value
    else:
        current[last] = value


def get_missing_config_fields() -> List[Dict[str, Any]]:
    """
    Check which config fields are missing or outdated (recursive).
    
    Walks the DEFAULT_CONFIG tree at arbitrary depth and reports any keys
    present in defaults but absent from the user's loaded config.
    """
    config = load_config()
    missing = []

    def _check(defaults: dict, current: dict, prefix: str = ""):
        for key, default_value in defaults.items():
            if key.startswith('_'):
                continue
            full_key = key if not prefix else f"{prefix}.{key}"
            if key not in current:
                missing.append({
                    "key": full_key,
                    "default": default_value,
                    "description": f"New config option: {full_key}",
                })
            elif isinstance(default_value, dict) and isinstance(current.get(key), dict):
                _check(default_value, current[key], full_key)

    _check(DEFAULT_CONFIG, config)
    return missing


def get_missing_skill_config_vars() -> List[Dict[str, Any]]:
    """Return skill-declared config vars that are missing or empty in config.yaml.

    Scans all enabled skills for ``metadata.hermes.config`` entries, then checks
    which ones are absent or empty under ``skills.config.<key>`` in the user's
    config.yaml.  Returns a list of dicts suitable for prompting.
    """
    try:
        from agent.skill_utils import discover_all_skill_config_vars, SKILL_CONFIG_PREFIX
    except Exception:
        return []

    all_vars = discover_all_skill_config_vars()
    if not all_vars:
        return []

    config = load_config()
    missing: List[Dict[str, Any]] = []
    for var in all_vars:
        # Skill config is stored under skills.config.<logical_key>
        storage_key = f"{SKILL_CONFIG_PREFIX}.{var['key']}"
        parts = storage_key.split(".")
        current = config
        value = None
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
                value = current
            else:
                value = None
                break
        # Missing = key doesn't exist or is empty string
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(var)
    return missing


def _normalize_custom_provider_entry(
    entry: Any,
    *,
    provider_key: str = "",
) -> Optional[Dict[str, Any]]:
    """Return a runtime-compatible custom provider entry or ``None``."""
    if not isinstance(entry, dict):
        return None

    # Accept camelCase aliases commonly used in hand-written configs.
    _CAMEL_ALIASES: Dict[str, str] = {
        "apiKey": "api_key",
        "baseUrl": "base_url",
        "apiMode": "api_mode",
        "keyEnv": "key_env",
        "apiKeyEnv": "key_env",  # alias — OpenClaw-compatible + docs variant
        "defaultModel": "default_model",
        "contextLength": "context_length",
        "rateLimitDelay": "rate_limit_delay",
    }
    # api_key_env is a documented snake_case alias for key_env. Normalize it
    # up front so the rest of the normalizer treats it as the canonical field.
    if "api_key_env" in entry and "key_env" not in entry:
        entry["key_env"] = entry["api_key_env"]
    _KNOWN_KEYS = {
        "name", "api", "url", "base_url", "api_key", "key_env", "api_key_env",
        "api_mode", "transport", "model", "default_model", "models",
        "context_length", "rate_limit_delay",
        "request_timeout_seconds", "stale_timeout_seconds",
    }
    for camel, snake in _CAMEL_ALIASES.items():
        if camel in entry and snake not in entry:
            logger.warning(
                "providers.%s: camelCase key '%s' auto-mapped to '%s' "
                "(use snake_case to avoid this warning)",
                provider_key or "?", camel, snake,
            )
            entry[snake] = entry[camel]
    unknown = set(entry.keys()) - _KNOWN_KEYS - set(_CAMEL_ALIASES.keys())
    if unknown:
        logger.warning(
            "providers.%s: unknown config keys ignored: %s",
            provider_key or "?", ", ".join(sorted(unknown)),
        )

    from urllib.parse import urlparse

    base_url = ""
    for url_key in ("base_url", "url", "api"):
        raw_url = entry.get(url_key)
        if isinstance(raw_url, str) and raw_url.strip():
            candidate = raw_url.strip()
            parsed = urlparse(candidate)
            if parsed.scheme and parsed.netloc:
                base_url = candidate
                break
            else:
                logger.warning(
                    "providers.%s: '%s' value '%s' is not a valid URL "
                    "(no scheme or host) — skipped",
                    provider_key or "?", url_key, candidate,
                )
    if not base_url:
        return None

    name = ""
    raw_name = entry.get("name")
    if isinstance(raw_name, str) and raw_name.strip():
        name = raw_name.strip()
    elif provider_key.strip():
        name = provider_key.strip()
    if not name:
        return None

    normalized: Dict[str, Any] = {
        "name": name,
        "base_url": base_url,
    }

    provider_key = provider_key.strip()
    if provider_key:
        normalized["provider_key"] = provider_key

    api_key = entry.get("api_key")
    if isinstance(api_key, str) and api_key.strip():
        normalized["api_key"] = api_key.strip()

    key_env = entry.get("key_env")
    if isinstance(key_env, str) and key_env.strip():
        normalized["key_env"] = key_env.strip()

    api_mode = entry.get("api_mode") or entry.get("transport")
    if isinstance(api_mode, str) and api_mode.strip():
        normalized["api_mode"] = api_mode.strip()

    model_name = entry.get("model") or entry.get("default_model")
    if isinstance(model_name, str) and model_name.strip():
        normalized["model"] = model_name.strip()

    models = entry.get("models")
    if isinstance(models, dict) and models:
        normalized["models"] = models
    elif isinstance(models, list) and models:
        # Hand-edited configs (and older Hermes versions) write ``models`` as
        # a plain list of model ids. Preserve them by converting to the dict
        # shape downstream code expects; otherwise normalize silently drops
        # the list and /model shows the provider with (0) models.
        normalized["models"] = {
            str(m): {} for m in models if isinstance(m, str) and m.strip()
        }

    context_length = entry.get("context_length")
    if isinstance(context_length, int) and context_length > 0:
        normalized["context_length"] = context_length

    rate_limit_delay = entry.get("rate_limit_delay")
    if isinstance(rate_limit_delay, (int, float)) and rate_limit_delay >= 0:
        normalized["rate_limit_delay"] = rate_limit_delay

    return normalized


def providers_dict_to_custom_providers(providers_dict: Any) -> List[Dict[str, Any]]:
    """Normalize ``providers`` config entries into the legacy custom-provider shape."""
    if not isinstance(providers_dict, dict):
        return []

    custom_providers: List[Dict[str, Any]] = []
    for key, entry in providers_dict.items():
        normalized = _normalize_custom_provider_entry(entry, provider_key=str(key))
        if normalized is not None:
            custom_providers.append(normalized)

    return custom_providers


def get_compatible_custom_providers(
    config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Return a deduplicated custom-provider view across legacy and v12+ config.

    ``custom_providers`` remains the on-disk legacy format, while ``providers``
    is the newer keyed schema.  Runtime and picker flows still need a single
    list-shaped view, but we should not materialise that compatibility layer
    back into config.yaml because it duplicates entries in UIs.
    """
    if config is None:
        config = load_config()

    compatible: List[Dict[str, Any]] = []
    seen_provider_keys: set = set()
    seen_name_url_pairs: set = set()

    def _append_if_new(entry: Optional[Dict[str, Any]]) -> None:
        if entry is None:
            return
        provider_key = str(entry.get("provider_key", "") or "").strip().lower()
        name = str(entry.get("name", "") or "").strip().lower()
        base_url = str(entry.get("base_url", "") or "").strip().rstrip("/").lower()
        model = str(entry.get("model", "") or "").strip().lower()
        pair = (name, base_url, model)

        if provider_key and provider_key in seen_provider_keys:
            return
        if name and base_url and pair in seen_name_url_pairs:
            return

        compatible.append(entry)
        if provider_key:
            seen_provider_keys.add(provider_key)
        if name and base_url:
            seen_name_url_pairs.add(pair)

    custom_providers = config.get("custom_providers")
    if custom_providers is not None:
        if not isinstance(custom_providers, list):
            return []
        for entry in custom_providers:
            _append_if_new(_normalize_custom_provider_entry(entry))

    for entry in providers_dict_to_custom_providers(config.get("providers")):
        _append_if_new(entry)

    return compatible


def get_custom_provider_context_length(
    model: str,
    base_url: str,
    custom_providers: Optional[List[Dict[str, Any]]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """Look up a per-model ``context_length`` override from ``custom_providers``.

    Matches any entry whose ``base_url`` equals ``base_url`` (trailing-slash
    insensitive) and returns ``custom_providers[i].models.<model>.context_length``
    if present and valid.  Returns ``None`` when no override applies.

    This is the single source of truth for custom-provider context overrides,
    used by:
      * ``AIAgent.__init__`` (startup resolution)
      * ``AIAgent.switch_model`` (mid-session ``/model`` switch)
      * ``hermes_cli.model_switch.resolve_display_context_length`` (``/model`` confirmation display)
      * ``gateway.run._format_session_info`` (``/info`` display)
      * ``agent.model_metadata.get_model_context_length`` (when custom_providers is threaded through)

    Before this helper existed, the lookup was duplicated in ``run_agent.py``'s
    startup path only; every other path (notably ``/model`` switch) fell back
    to the 128K default.  See #15779.
    """
    if not model or not base_url:
        return None
    if custom_providers is None:
        try:
            custom_providers = get_compatible_custom_providers(config)
        except Exception:
            if config is None:
                return None
            raw = config.get("custom_providers")
            custom_providers = raw if isinstance(raw, list) else []
    if not isinstance(custom_providers, list):
        return None

    target_url = (base_url or "").rstrip("/")
    if not target_url:
        return None

    for entry in custom_providers:
        if not isinstance(entry, dict):
            continue
        entry_url = (entry.get("base_url") or "").rstrip("/")
        if not entry_url or entry_url != target_url:
            continue
        models = entry.get("models")
        if not isinstance(models, dict):
            continue
        model_cfg = models.get(model)
        if not isinstance(model_cfg, dict):
            continue
        raw_ctx = model_cfg.get("context_length")
        if raw_ctx is None:
            continue
        try:
            ctx = int(raw_ctx)
        except (TypeError, ValueError):
            continue
        if ctx > 0:
            return ctx
    return None


def check_config_version() -> Tuple[int, int]:
    """
    Check config version.
    
    Returns (current_version, latest_version).
    """
    config = load_config()
    current = config.get("_config_version", 0)
    latest = DEFAULT_CONFIG.get("_config_version", 1)
    return current, latest


# =============================================================================
# Config structure validation
# =============================================================================

# Fields that are valid at root level of config.yaml
_KNOWN_ROOT_KEYS = {
    "_config_version", "model", "providers", "fallback_model",
    "fallback_providers", "credential_pool_strategies", "toolsets",
    "agent", "terminal", "display", "compression", "delegation",
    "auxiliary", "custom_providers", "context", "memory", "gateway",
    "sessions",
}

# Valid fields inside a custom_providers list entry
_VALID_CUSTOM_PROVIDER_FIELDS = {
    "name", "base_url", "api_key", "api_mode", "model", "models",
    "context_length", "rate_limit_delay",
    # key_env is read at runtime by runtime_provider.py and auxiliary_client.py
    # — include it here so the set accurately describes the supported schema.
    "key_env",
}

# Fields that look like they should be inside custom_providers, not at root
_CUSTOM_PROVIDER_LIKE_FIELDS = {"base_url", "api_key", "rate_limit_delay", "api_mode"}


@dataclass
class ConfigIssue:
    """A detected config structure problem."""

    severity: str  # "error", "warning"
    message: str
    hint: str


def validate_config_structure(config: Optional[Dict[str, Any]] = None) -> List["ConfigIssue"]:
    """Validate config.yaml structure and return a list of detected issues.

    Catches common YAML formatting mistakes that produce confusing runtime
    errors (like "Unknown provider") instead of clear diagnostics.

    Can be called with a pre-loaded config dict, or will load from disk.
    """
    if config is None:
        try:
            config = load_config()
        except Exception:
            return [ConfigIssue("error", "Could not load config.yaml", "Run 'hermes setup' to create a valid config")]

    issues: List[ConfigIssue] = []

    # ── custom_providers must be a list, not a dict ──────────────────────
    cp = config.get("custom_providers")
    if cp is not None:
        if isinstance(cp, dict):
            issues.append(ConfigIssue(
                "error",
                "custom_providers is a dict — it must be a YAML list (items prefixed with '-')",
                "Change to:\n"
                "  custom_providers:\n"
                "    - name: my-provider\n"
                "      base_url: https://...\n"
                "      api_key: ...",
            ))
            # Check if dict keys look like they should be list-entry fields
            cp_keys = set(cp.keys()) if isinstance(cp, dict) else set()
            suspicious = cp_keys & _CUSTOM_PROVIDER_LIKE_FIELDS
            if suspicious:
                issues.append(ConfigIssue(
                    "warning",
                    f"Root-level keys {sorted(suspicious)} look like custom_providers entry fields",
                    "These should be indented under a '- name: ...' list entry, not at root level",
                ))
        elif isinstance(cp, list):
            # Validate each entry in the list
            for i, entry in enumerate(cp):
                if not isinstance(entry, dict):
                    issues.append(ConfigIssue(
                        "warning",
                        f"custom_providers[{i}] is not a dict (got {type(entry).__name__})",
                        "Each entry should have at minimum: name, base_url",
                    ))
                    continue
                if not entry.get("name"):
                    issues.append(ConfigIssue(
                        "warning",
                        f"custom_providers[{i}] is missing 'name' field",
                        "Add a name, e.g.: name: my-provider",
                    ))
                if not entry.get("base_url"):
                    issues.append(ConfigIssue(
                        "warning",
                        f"custom_providers[{i}] is missing 'base_url' field",
                        "Add the API endpoint URL, e.g.: base_url: https://api.example.com/v1",
                    ))

    # ── fallback_model: single dict OR list of dicts (chain) ─────────────
    fb = config.get("fallback_model")
    if fb is not None:
        if isinstance(fb, list):
            # Chain fallback — validate each entry
            for i, entry in enumerate(fb):
                if not isinstance(entry, dict):
                    issues.append(ConfigIssue(
                        "error",
                        f"fallback_model[{i}] should be a dict, got {type(entry).__name__}",
                        "Each entry needs provider + model",
                    ))
                else:
                    if not entry.get("provider"):
                        issues.append(ConfigIssue(
                            "warning",
                            f"fallback_model[{i}] is missing 'provider' field",
                            "Add: provider: openrouter (or another provider)",
                        ))
                    if not entry.get("model"):
                        issues.append(ConfigIssue(
                            "warning",
                            f"fallback_model[{i}] is missing 'model' field",
                            "Add: model: <model-name>",
                        ))
        elif not isinstance(fb, dict):
            issues.append(ConfigIssue(
                "error",
                f"fallback_model should be a dict with 'provider' and 'model', got {type(fb).__name__}",
                "Change to:\n"
                "  fallback_model:\n"
                "    provider: openrouter\n"
                "    model: anthropic/claude-sonnet-4",
            ))
        elif fb:
            if not fb.get("provider"):
                issues.append(ConfigIssue(
                    "warning",
                    "fallback_model is missing 'provider' field — fallback will be disabled",
                    "Add: provider: openrouter (or another provider)",
                ))
            if not fb.get("model"):
                issues.append(ConfigIssue(
                    "warning",
                    "fallback_model is missing 'model' field — fallback will be disabled",
                    "Add: model: anthropic/claude-sonnet-4 (or another model)",
                ))

    # ── Check for fallback_model accidentally nested inside custom_providers ──
    if isinstance(cp, dict) and "fallback_model" not in config and "fallback_model" in (cp or {}):
        issues.append(ConfigIssue(
            "error",
            "fallback_model appears inside custom_providers instead of at root level",
            "Move fallback_model to the top level of config.yaml (no indentation)",
        ))

    # ── model section: should exist when custom_providers is configured ──
    model_cfg = config.get("model")
    if cp and not model_cfg:
        issues.append(ConfigIssue(
            "warning",
            "custom_providers defined but no 'model' section — Hermes won't know which provider to use",
            "Add a model section:\n"
            "  model:\n"
            "    provider: custom\n"
            "    default: your-model-name\n"
            "    base_url: https://...",
        ))

    # ── Root-level keys that look misplaced ──────────────────────────────
    for key in config:
        if key.startswith("_"):
            continue
        if key not in _KNOWN_ROOT_KEYS and key in _CUSTOM_PROVIDER_LIKE_FIELDS:
            issues.append(ConfigIssue(
                "warning",
                f"Root-level key '{key}' looks misplaced — should it be under 'model:' or inside a 'custom_providers' entry?",
                f"Move '{key}' under the appropriate section",
            ))

    return issues


def print_config_warnings(config: Optional[Dict[str, Any]] = None) -> None:
    """Print config structure warnings to stderr at startup.

    Called early in CLI and gateway init so users see problems before
    they hit cryptic "Unknown provider" errors.  Prints nothing if
    config is healthy.
    """
    try:
        issues = validate_config_structure(config)
    except Exception:
        return
    if not issues:
        return

    lines = ["\033[33m⚠ Config issues detected in config.yaml:\033[0m"]
    for ci in issues:
        marker = "\033[31m✗\033[0m" if ci.severity == "error" else "\033[33m⚠\033[0m"
        lines.append(f"  {marker} {ci.message}")
    lines.append("  \033[2mRun 'hermes doctor' for fix suggestions.\033[0m")
    sys.stderr.write("\n".join(lines) + "\n\n")


def warn_deprecated_cwd_env_vars(config: Optional[Dict[str, Any]] = None) -> None:
    """Warn if MESSAGING_CWD or TERMINAL_CWD is set in .env instead of config.yaml.

    These env vars are deprecated — the canonical setting is terminal.cwd
    in config.yaml.  Prints a migration hint to stderr.
    """
    messaging_cwd = os.environ.get("MESSAGING_CWD")
    terminal_cwd_env = os.environ.get("TERMINAL_CWD")

    if config is None:
        try:
            config = load_config()
        except Exception:
            return

    terminal_cfg = config.get("terminal", {})
    config_cwd = terminal_cfg.get("cwd", ".") if isinstance(terminal_cfg, dict) else "."
    # Only warn if config.yaml doesn't have an explicit path
    config_has_explicit_cwd = config_cwd not in (".", "auto", "cwd", "")

    lines: list[str] = []
    if messaging_cwd:
        lines.append(
            f"  \033[33m⚠\033[0m MESSAGING_CWD={messaging_cwd} found in .env — "
            f"this is deprecated."
        )
    if terminal_cwd_env and not config_has_explicit_cwd:
        # TERMINAL_CWD in env but not from config bridge — likely from .env
        lines.append(
            f"  \033[33m⚠\033[0m TERMINAL_CWD={terminal_cwd_env} found in .env — "
            f"this is deprecated."
        )
    if lines:
        hint_path = os.environ.get("HERMES_HOME", "~/.hermes")
        lines.insert(0, "\033[33m⚠ Deprecated .env settings detected:\033[0m")
        lines.append(
            f"  \033[2mMove to config.yaml instead:  "
            f"terminal:\\n    cwd: /your/project/path\033[0m"
        )
        lines.append(
            f"  \033[2mThen remove the old entries from {hint_path}/.env\033[0m"
        )
        sys.stderr.write("\n".join(lines) + "\n\n")


def migrate_config(interactive: bool = True, quiet: bool = False) -> Dict[str, Any]:
    """
    Migrate config to latest version, prompting for new required fields.
    
    Args:
        interactive: If True, prompt user for missing values
        quiet: If True, suppress output
        
    Returns:
        Dict with migration results: {"env_added": [...], "config_added": [...], "warnings": [...]}
    """
    results = {"env_added": [], "config_added": [], "warnings": []}

    # ── Always: sanitize .env (split concatenated keys) ──
    try:
        fixes = sanitize_env_file()
        if fixes and not quiet:
            print(f"  ✓ Repaired .env file ({fixes} corrupted entries fixed)")
    except Exception:
        pass  # best-effort; don't block migration on sanitize failure

    # Check config version
    current_ver, latest_ver = check_config_version()
    
    # ── Version 3 → 4: migrate tool progress from .env to config.yaml ──
    if current_ver < 4:
        config = load_config()
        display = config.get("display", {})
        if not isinstance(display, dict):
            display = {}
        if "tool_progress" not in display:
            old_enabled = get_env_value("HERMES_TOOL_PROGRESS")
            old_mode = get_env_value("HERMES_TOOL_PROGRESS_MODE")
            if old_enabled and old_enabled.lower() in ("false", "0", "no"):
                display["tool_progress"] = "off"
                results["config_added"].append("display.tool_progress=off (from HERMES_TOOL_PROGRESS=false)")
            elif old_mode and old_mode.lower() in ("new", "all"):
                display["tool_progress"] = old_mode.lower()
                results["config_added"].append(f"display.tool_progress={old_mode.lower()} (from HERMES_TOOL_PROGRESS_MODE)")
            else:
                display["tool_progress"] = "all"
                results["config_added"].append("display.tool_progress=all (default)")
            config["display"] = display
            save_config(config)
            if not quiet:
                print(f"  ✓ Migrated tool progress to config.yaml: {display['tool_progress']}")
    
    # ── Version 4 → 5: add timezone field ──
    if current_ver < 5:
        config = load_config()
        if "timezone" not in config:
            old_tz = os.getenv("HERMES_TIMEZONE", "")
            if old_tz and old_tz.strip():
                config["timezone"] = old_tz.strip()
                results["config_added"].append(f"timezone={old_tz.strip()} (from HERMES_TIMEZONE)")
            else:
                config["timezone"] = ""
                results["config_added"].append("timezone= (empty, uses server-local)")
            save_config(config)
            if not quiet:
                tz_display = config["timezone"] or "(server-local)"
                print(f"  ✓ Added timezone to config.yaml: {tz_display}")

    # ── Version 8 → 9: clear ANTHROPIC_TOKEN from .env ──
    # The new Anthropic auth flow no longer uses this env var.
    if current_ver < 9:
        try:
            old_token = get_env_value("ANTHROPIC_TOKEN")
            if old_token:
                save_env_value("ANTHROPIC_TOKEN", "")
                if not quiet:
                    print("  ✓ Cleared ANTHROPIC_TOKEN from .env (no longer used)")
        except Exception:
            pass

    # ── Version 11 → 12: migrate custom_providers list → providers dict ──
    if current_ver < 12:
        config = load_config()
        custom_list = config.get("custom_providers")
        if isinstance(custom_list, list) and custom_list:
            providers_dict = config.get("providers", {})
            if not isinstance(providers_dict, dict):
                providers_dict = {}
            migrated_count = 0
            for entry in custom_list:
                if not isinstance(entry, dict):
                    continue
                old_name = entry.get("name", "")
                old_url = entry.get("base_url", "") or entry.get("url", "") or ""
                old_key = entry.get("api_key", "")
                if not old_url:
                    continue  # skip entries with no URL

                # Generate a kebab-case key from the display name
                key = old_name.strip().lower().replace(" ", "-").replace("(", "").replace(")", "")
                # Remove consecutive hyphens and trailing hyphens
                while "--" in key:
                    key = key.replace("--", "-")
                key = key.strip("-")
                if not key:
                    # Fallback: derive from URL hostname
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(old_url)
                        key = (parsed.hostname or "endpoint").replace(".", "-")
                    except Exception:
                        key = f"endpoint-{migrated_count}"

                # Don't overwrite existing entries
                if key in providers_dict:
                    key = f"{key}-{migrated_count}"

                new_entry = {"api": old_url}
                if old_name:
                    new_entry["name"] = old_name
                if old_key and old_key not in ("no-key", "no-key-required", ""):
                    new_entry["api_key"] = old_key

                # Carry over model and api_mode if present
                if entry.get("model"):
                    new_entry["default_model"] = entry["model"]
                if entry.get("api_mode"):
                    new_entry["transport"] = entry["api_mode"]

                providers_dict[key] = new_entry
                migrated_count += 1

            if migrated_count > 0:
                config["providers"] = providers_dict
                # Remove the old list — runtime reads via get_compatible_custom_providers()
                config.pop("custom_providers", None)
                save_config(config)
                if not quiet:
                    print(f"  ✓ Migrated {migrated_count} custom provider(s) to providers: section")
                    for key in list(providers_dict.keys())[-migrated_count:]:
                        ep = providers_dict[key]
                        print(f"    → {key}: {ep.get('api', '')}")

    # ── Version 12 → 13: clear dead LLM_MODEL / OPENAI_MODEL from .env ──
    # These env vars were written by the old setup wizard but nothing reads
    # them anymore (config.yaml is the sole source of truth since March 2026).
    # Stale entries cause user confusion — see issue report.
    if current_ver < 13:
        for dead_var in ("LLM_MODEL", "OPENAI_MODEL"):
            try:
                old_val = get_env_value(dead_var)
                if old_val:
                    save_env_value(dead_var, "")
                    if not quiet:
                        print(f"  ✓ Cleared {dead_var} from .env (no longer used — config.yaml is source of truth)")
            except Exception:
                pass

    # ── Version 13 → 14: migrate legacy flat stt.model to provider section ──
    # Old configs (and cli-config.yaml.example) had a flat `stt.model` key
    # that was provider-agnostic.  When the provider was "local" this caused
    # OpenAI model names (e.g. "whisper-1") to be fed to faster-whisper,
    # crashing with "Invalid model size".  Move the value into the correct
    # provider-specific section and remove the flat key.
    if current_ver < 14:
        # Read raw config (no defaults merged) to check what the user actually
        # wrote, then apply changes to the merged config for saving.
        raw = read_raw_config()
        raw_stt = raw.get("stt", {})
        if isinstance(raw_stt, dict) and "model" in raw_stt:
            legacy_model = raw_stt["model"]
            provider = raw_stt.get("provider", "local")
            config = load_config()
            stt = config.get("stt", {})
            # Remove the legacy flat key
            stt.pop("model", None)
            # Place it in the appropriate provider section only if the
            # user didn't already set a model there
            if provider in ("local", "local_command"):
                # Don't migrate an OpenAI model name into the local section
                _local_models = {
                    "tiny.en", "tiny", "base.en", "base", "small.en", "small",
                    "medium.en", "medium", "large-v1", "large-v2", "large-v3",
                    "large", "distil-large-v2", "distil-medium.en",
                    "distil-small.en", "distil-large-v3", "distil-large-v3.5",
                    "large-v3-turbo", "turbo",
                }
                if legacy_model in _local_models:
                    # Check raw config — only set if user didn't already
                    # have a nested local.model
                    raw_local = raw_stt.get("local", {})
                    if not isinstance(raw_local, dict) or "model" not in raw_local:
                        local_cfg = stt.setdefault("local", {})
                        local_cfg["model"] = legacy_model
                # else: drop it — it was an OpenAI model name, local section
                # already defaults to "base" via DEFAULT_CONFIG
            else:
                # Cloud provider — put it in that provider's section only
                # if user didn't already set a nested model
                raw_provider = raw_stt.get(provider, {})
                if not isinstance(raw_provider, dict) or "model" not in raw_provider:
                    provider_cfg = stt.setdefault(provider, {})
                    provider_cfg["model"] = legacy_model
            config["stt"] = stt
            save_config(config)
            if not quiet:
                print(f"  ✓ Migrated legacy stt.model to provider-specific config")

    # ── Version 14 → 15: add explicit gateway interim-message gate ──
    if current_ver < 15:
        config = read_raw_config()
        display = config.get("display", {})
        if not isinstance(display, dict):
            display = {}
        if "interim_assistant_messages" not in display:
            display["interim_assistant_messages"] = True
            config["display"] = display
            results["config_added"].append("display.interim_assistant_messages=true (default)")
            save_config(config)
            if not quiet:
                print("  ✓ Added display.interim_assistant_messages=true")

    # ── Version 15 → 16: migrate tool_progress_overrides into display.platforms ──
    if current_ver < 16:
        config = read_raw_config()
        display = config.get("display", {})
        if not isinstance(display, dict):
            display = {}
        old_overrides = display.get("tool_progress_overrides")
        if isinstance(old_overrides, dict) and old_overrides:
            platforms = display.get("platforms", {})
            if not isinstance(platforms, dict):
                platforms = {}
            for plat, mode in old_overrides.items():
                if plat not in platforms:
                    platforms[plat] = {}
                if "tool_progress" not in platforms[plat]:
                    platforms[plat]["tool_progress"] = mode
            display["platforms"] = platforms
            config["display"] = display
            save_config(config)
            if not quiet:
                migrated = ", ".join(f"{p}={m}" for p, m in old_overrides.items())
                print(f"  ✓ Migrated tool_progress_overrides → display.platforms: {migrated}")
            results["config_added"].append("display.platforms (migrated from tool_progress_overrides)")

    # ── Version 16 → 17: remove legacy compression.summary_* keys ──
    if current_ver < 17:
        config = read_raw_config()
        comp = config.get("compression", {})
        if isinstance(comp, dict):
            s_model = comp.pop("summary_model", None)
            s_provider = comp.pop("summary_provider", None)
            s_base_url = comp.pop("summary_base_url", None)
            migrated_keys = []
            # Migrate non-empty, non-default values to auxiliary.compression
            if s_model and str(s_model).strip():
                aux = config.setdefault("auxiliary", {})
                aux_comp = aux.setdefault("compression", {})
                if not aux_comp.get("model"):
                    aux_comp["model"] = str(s_model).strip()
                    migrated_keys.append(f"model={s_model}")
            if s_provider and str(s_provider).strip() not in ("", "auto"):
                aux = config.setdefault("auxiliary", {})
                aux_comp = aux.setdefault("compression", {})
                if not aux_comp.get("provider") or aux_comp.get("provider") == "auto":
                    aux_comp["provider"] = str(s_provider).strip()
                    migrated_keys.append(f"provider={s_provider}")
            if s_base_url and str(s_base_url).strip():
                aux = config.setdefault("auxiliary", {})
                aux_comp = aux.setdefault("compression", {})
                if not aux_comp.get("base_url"):
                    aux_comp["base_url"] = str(s_base_url).strip()
                    migrated_keys.append(f"base_url={s_base_url}")
            if migrated_keys or s_model is not None or s_provider is not None or s_base_url is not None:
                config["compression"] = comp
                save_config(config)
                if not quiet:
                    if migrated_keys:
                        print(f"  ✓ Migrated compression.summary_* → auxiliary.compression: {', '.join(migrated_keys)}")
                    else:
                        print("  ✓ Removed unused compression.summary_* keys")

    # ── Version 20 → 21: plugins are now opt-in; grandfather existing user plugins ──
    # The loader now requires plugins to appear in ``plugins.enabled`` before
    # loading. Existing installs had all discovered plugins loading by default
    # (minus anything in ``plugins.disabled``). To avoid silently breaking
    # those setups on upgrade, populate ``plugins.enabled`` with the set of
    # currently-installed user plugins that aren't already disabled.
    #
    # Bundled plugins (shipped in the repo itself) are NOT grandfathered —
    # they ship off for everyone, including existing users, so any user who
    # wants one has to opt in explicitly.
    if current_ver < 21:
        config = read_raw_config()
        plugins_cfg = config.get("plugins")
        if not isinstance(plugins_cfg, dict):
            plugins_cfg = {}
        # Only migrate if the enabled allow-list hasn't been set yet.
        if "enabled" not in plugins_cfg:
            disabled = plugins_cfg.get("disabled", []) or []
            if not isinstance(disabled, list):
                disabled = []
            disabled_set = set(disabled)

            # Scan ``$HERMES_HOME/plugins/`` for currently installed user plugins.
            grandfathered: List[str] = []
            try:
                user_plugins_dir = get_hermes_home() / "plugins"
                if user_plugins_dir.is_dir():
                    for child in sorted(user_plugins_dir.iterdir()):
                        if not child.is_dir():
                            continue
                        manifest_file = child / "plugin.yaml"
                        if not manifest_file.exists():
                            manifest_file = child / "plugin.yml"
                        if not manifest_file.exists():
                            continue
                        try:
                            with open(manifest_file) as _mf:
                                manifest = yaml.safe_load(_mf) or {}
                        except Exception:
                            manifest = {}
                        name = manifest.get("name") or child.name
                        if name in disabled_set:
                            continue
                        grandfathered.append(name)
            except Exception:
                grandfathered = []

            plugins_cfg["enabled"] = grandfathered
            config["plugins"] = plugins_cfg
            save_config(config)
            results["config_added"].append(
                f"plugins.enabled (opt-in allow-list, {len(grandfathered)} grandfathered)"
            )
            if not quiet:
                if grandfathered:
                    print(
                        f"  ✓ Plugins now opt-in: grandfathered "
                        f"{len(grandfathered)} existing plugin(s) into plugins.enabled"
                    )
                else:
                    print(
                        "  ✓ Plugins now opt-in: no existing plugins to grandfather. "
                        "Use `hermes plugins enable <name>` to activate."
                    )

    # ── Version 22 → 23: seed curator defaults + create logs/curator/ ──
    # The curator (background skill maintenance) was added in PR #16049, but
    # existing configs from before that PR (or before the April 2026
    # unification under `auxiliary.curator`) never wrote the curator section
    # to disk. The runtime deep-merge in `load_config()` fills defaults at
    # read time, so the curator *functions*; but users can't see/edit the
    # settings in their `config.yaml`, and `hermes curator status` has no
    # stable logs dir to point at until the first run mkdir's it.
    #
    # This migration:
    #   1. Writes the `curator` top-level section to config.yaml (enabled,
    #      interval_hours, min_idle_hours, stale_after_days, archive_after_days)
    #      — only keys the user hasn't already overridden.
    #   2. Writes the `auxiliary.curator` aux-task slot (provider, model,
    #      base_url, api_key, timeout, extra_body) — canonical slot for
    #      routing the curator fork to a cheaper aux model.
    #   3. Creates `~/.hermes/logs/curator/` if missing (belt-and-suspenders
    #      on top of ensure_hermes_home() — old profiles that predate this
    #      migration still benefit).
    if current_ver < 23:
        try:
            curator_dir = get_hermes_home() / "logs" / "curator"
            curator_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            results["warnings"].append(f"Could not create {curator_dir}: {e}")

        config = read_raw_config()
        touched = False

        # (1) Top-level curator section — only add missing keys
        _curator_defaults = DEFAULT_CONFIG.get("curator", {})
        raw_curator = config.get("curator")
        if not isinstance(raw_curator, dict):
            raw_curator = {}
        added_curator: List[str] = []
        for k, v in _curator_defaults.items():
            if k not in raw_curator:
                raw_curator[k] = copy.deepcopy(v)
                added_curator.append(k)
        if added_curator:
            config["curator"] = raw_curator
            touched = True

        # (2) auxiliary.curator task slot
        _aux_curator_defaults = (
            DEFAULT_CONFIG.get("auxiliary", {}).get("curator", {})
        )
        raw_aux = config.get("auxiliary")
        if not isinstance(raw_aux, dict):
            raw_aux = {}
        raw_aux_curator = raw_aux.get("curator")
        if not isinstance(raw_aux_curator, dict):
            raw_aux_curator = {}
        added_aux: List[str] = []
        for k, v in _aux_curator_defaults.items():
            if k not in raw_aux_curator:
                raw_aux_curator[k] = copy.deepcopy(v)
                added_aux.append(k)
        if added_aux:
            raw_aux["curator"] = raw_aux_curator
            config["auxiliary"] = raw_aux
            touched = True

        if touched:
            save_config(config)
            if added_curator:
                results["config_added"].append(
                    f"curator ({len(added_curator)} default key(s))"
                )
                if not quiet:
                    print(
                        "  ✓ Seeded curator defaults in config.yaml: "
                        f"{', '.join(added_curator)}"
                    )
            if added_aux:
                results["config_added"].append(
                    f"auxiliary.curator ({len(added_aux)} default key(s))"
                )
                if not quiet:
                    print(
                        "  ✓ Seeded auxiliary.curator defaults in config.yaml: "
                        f"{', '.join(added_aux)}"
                    )

    if current_ver < latest_ver and not quiet:
        print(f"Config version: {current_ver} → {latest_ver}")
    
    # Check for missing required env vars
    missing_env = get_missing_env_vars(required_only=True)
    
    if missing_env and not quiet:
        print("\n⚠️  Missing required environment variables:")
        for var in missing_env:
            print(f"   • {var['name']}: {var['description']}")
    
    if interactive and missing_env:
        print("\nLet's configure them now:\n")
        for var in missing_env:
            if var.get("url"):
                print(f"  Get your key at: {var['url']}")
            
            if var.get("password"):
                import getpass
                value = getpass.getpass(f"  {var['prompt']}: ")
            else:
                value = input(f"  {var['prompt']}: ").strip()
            
            if value:
                save_env_value(var["name"], value)
                results["env_added"].append(var["name"])
                print(f"  ✓ Saved {var['name']}")
            else:
                results["warnings"].append(f"Skipped {var['name']} - some features may not work")
            print()
    
    # Check for missing optional env vars and offer to configure interactively
    # Skip "advanced" vars (like OPENAI_BASE_URL) -- those are for power users
    missing_optional = get_missing_env_vars(required_only=False)
    required_names = {v["name"] for v in missing_env} if missing_env else set()
    missing_optional = [
        v for v in missing_optional
        if v["name"] not in required_names and not v.get("advanced")
    ]
    
    # Only offer to configure env vars that are NEW since the user's previous version
    new_var_names = set()
    for ver in range(current_ver + 1, latest_ver + 1):
        new_var_names.update(ENV_VARS_BY_VERSION.get(ver, []))

    if new_var_names and interactive and not quiet:
        new_and_unset = [
            (name, OPTIONAL_ENV_VARS[name])
            for name in sorted(new_var_names)
            if not get_env_value(name) and name in OPTIONAL_ENV_VARS
        ]
        if new_and_unset:
            print(f"\n  {len(new_and_unset)} new optional key(s) in this update:")
            for name, info in new_and_unset:
                print(f"    • {name} — {info.get('description', '')}")
            print()
            try:
                answer = input("  Configure new keys? [y/N]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                answer = "n"

            if answer in ("y", "yes"):
                print()
                for name, info in new_and_unset:
                    if info.get("url"):
                        print(f"  {info.get('description', name)}")
                        print(f"  Get your key at: {info['url']}")
                    else:
                        print(f"  {info.get('description', name)}")
                    if info.get("password"):
                        import getpass
                        value = getpass.getpass(f"  {info.get('prompt', name)} (Enter to skip): ")
                    else:
                        value = input(f"  {info.get('prompt', name)} (Enter to skip): ").strip()
                    if value:
                        save_env_value(name, value)
                        results["env_added"].append(name)
                        print(f"  ✓ Saved {name}")
                    print()
            else:
                print("  Set later with: hermes config set <key> <value>")
    
    # Check for missing config fields
    missing_config = get_missing_config_fields()
    
    if missing_config:
        config = load_config()
        
        for field in missing_config:
            key = field["key"]
            default = field["default"]
            
            _set_nested(config, key, default)
            results["config_added"].append(key)
            if not quiet:
                print(f"  ✓ Added {key} = {default}")
        
        # Update version and save
        config["_config_version"] = latest_ver
        save_config(config)
    elif current_ver < latest_ver:
        # Just update version
        config = load_config()
        config["_config_version"] = latest_ver
        save_config(config)

    # ── Skill-declared config vars ──────────────────────────────────────
    # Skills can declare config.yaml settings they need via
    # metadata.hermes.config in their SKILL.md frontmatter.
    # Prompt for any that are missing/empty.
    missing_skill_config = get_missing_skill_config_vars()
    if missing_skill_config and interactive and not quiet:
        print(f"\n  {len(missing_skill_config)} skill setting(s) not configured:")
        for var in missing_skill_config:
            skill_name = var.get("skill", "unknown")
            print(f"    • {var['key']} — {var['description']} (from skill: {skill_name})")
        print()
        try:
            answer = input("  Configure skill settings? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"

        if answer in ("y", "yes"):
            print()
            config = load_config()
            try:
                from agent.skill_utils import SKILL_CONFIG_PREFIX
            except Exception:
                SKILL_CONFIG_PREFIX = "skills.config"
            for var in missing_skill_config:
                default = var.get("default", "")
                default_hint = f" (default: {default})" if default else ""
                value = input(f"  {var['prompt']}{default_hint}: ").strip()
                if not value and default:
                    value = str(default)
                if value:
                    storage_key = f"{SKILL_CONFIG_PREFIX}.{var['key']}"
                    _set_nested(config, storage_key, value)
                    results["config_added"].append(var["key"])
                    print(f"  ✓ Saved {var['key']} = {value}")
                else:
                    results["warnings"].append(
                        f"Skipped {var['key']} — skill '{var.get('skill', '?')}' may ask for it later"
                    )
                print()
            save_config(config)
        else:
            print("  Set later with: hermes config set <key> <value>")

    return results


# Config-tree merge/normalize helpers now live in hermes_cli.config_merge
# (below load_config); re-export so existing hermes_cli.config.* imports work.
from hermes_cli.config_merge import (  # noqa: F401
    cfg_get,
    _deep_merge,
    _expand_env_vars,
    _items_by_unique_name,
    _normalize_max_turns_config,
    _normalize_root_model_keys,
    _preserve_env_ref_templates,
)


_COMMENTED_SECTIONS = """
# ── Security ──────────────────────────────────────────────────────────
# Secret redaction is OFF by default. Set to true to mask strings that
# look like API keys, tokens, and passwords in tool output and logs.
#
# security:
#   redact_secrets: true

# ── Fallback Model ────────────────────────────────────────────────────
# Automatic provider failover when primary is unavailable.
# Uncomment and configure to enable. Triggers on rate limits (429),
# overload (529), service errors (503), or connection failures.
#
# Supported providers:
#   openrouter   (OPENROUTER_API_KEY)  — routes to any model
#   nous         (OAuth — hermes auth) — Nous Portal
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


# =============================================================================
# Config display
# =============================================================================


def show_config():
    """Display current configuration."""
    config = load_config()
    
    print()
    print(color("┌─────────────────────────────────────────────────────────┐", Colors.CYAN))
    print(color("│              ⚕ Hermes Configuration                    │", Colors.CYAN))
    print(color("└─────────────────────────────────────────────────────────┘", Colors.CYAN))
    
    # Paths
    print()
    print(color("◆ Paths", Colors.CYAN, Colors.BOLD))
    print(f"  Config:       {get_config_path()}")
    print(f"  Secrets:      {get_env_path()}")
    print(f"  Install:      {get_project_root()}")
    
    # API Keys
    print()
    print(color("◆ API Keys", Colors.CYAN, Colors.BOLD))
    
    keys = [
        ("OPENROUTER_API_KEY", "OpenRouter"),
        ("VOICE_TOOLS_OPENAI_KEY", "OpenAI (STT/TTS)"),
        ("EXA_API_KEY", "Exa"),
        ("PARALLEL_API_KEY", "Parallel"),
        ("FIRECRAWL_API_KEY", "Firecrawl"),
        ("TAVILY_API_KEY", "Tavily"),
        ("BROWSERBASE_API_KEY", "Browserbase"),
        ("BROWSER_USE_API_KEY", "Browser Use"),
        ("FAL_KEY", "FAL"),
    ]
    
    for env_key, name in keys:
        value = get_env_value(env_key)
        print(f"  {name:<14} {redact_key(value)}")
    from hermes_cli.auth import get_anthropic_key
    anthropic_value = get_anthropic_key()
    print(f"  {'Anthropic':<14} {redact_key(anthropic_value)}")
    
    # Model settings
    print()
    print(color("◆ Model", Colors.CYAN, Colors.BOLD))
    print(f"  Model:        {config.get('model', 'not set')}")
    print(f"  Max turns:    {config.get('agent', {}).get('max_turns', DEFAULT_CONFIG['agent']['max_turns'])}")
    
    # Display
    print()
    print(color("◆ Display", Colors.CYAN, Colors.BOLD))
    display = config.get('display', {})
    print(f"  Personality:  {display.get('personality', 'kawaii')}")
    print(f"  Reasoning:    {'on' if display.get('show_reasoning', False) else 'off'}")
    print(f"  Bell:         {'on' if display.get('bell_on_complete', False) else 'off'}")
    ump = display.get('user_message_preview', {}) if isinstance(display.get('user_message_preview', {}), dict) else {}
    ump_first = ump.get('first_lines', 2)
    ump_last = ump.get('last_lines', 2)
    print(f"  User preview: first {ump_first} line(s), last {ump_last} line(s)")

    # Terminal
    print()
    print(color("◆ Terminal", Colors.CYAN, Colors.BOLD))
    terminal = config.get('terminal', {})
    print(f"  Backend:      {terminal.get('backend', 'local')}")
    print(f"  Working dir:  {terminal.get('cwd', '.')}")
    print(f"  Timeout:      {terminal.get('timeout', 60)}s")
    
    if terminal.get('backend') == 'docker':
        print(f"  Docker image: {terminal.get('docker_image', 'nikolaik/python-nodejs:python3.11-nodejs20')}")
    elif terminal.get('backend') == 'singularity':
        print(f"  Image:        {terminal.get('singularity_image', 'docker://nikolaik/python-nodejs:python3.11-nodejs20')}")
    elif terminal.get('backend') == 'modal':
        print(f"  Modal image:  {terminal.get('modal_image', 'nikolaik/python-nodejs:python3.11-nodejs20')}")
        modal_token = get_env_value('MODAL_TOKEN_ID')
        print(f"  Modal token:  {'configured' if modal_token else '(not set)'}")
    elif terminal.get('backend') == 'daytona':
        print(f"  Daytona image: {terminal.get('daytona_image', 'nikolaik/python-nodejs:python3.11-nodejs20')}")
        daytona_key = get_env_value('DAYTONA_API_KEY')
        print(f"  API key:      {'configured' if daytona_key else '(not set)'}")
    elif terminal.get('backend') == 'vercel_sandbox':
        print(f"  Vercel runtime: {terminal.get('vercel_runtime', 'node24')}")
        print(f"  Vercel auth:    {'configured' if get_env_value('VERCEL_OIDC_TOKEN') or (get_env_value('VERCEL_TOKEN') and get_env_value('VERCEL_PROJECT_ID') and get_env_value('VERCEL_TEAM_ID')) else '(not set)'}")
    elif terminal.get('backend') == 'ssh':
        ssh_host = get_env_value('TERMINAL_SSH_HOST')
        ssh_user = get_env_value('TERMINAL_SSH_USER')
        print(f"  SSH host:     {ssh_host or '(not set)'}")
        print(f"  SSH user:     {ssh_user or '(not set)'}")
    
    # Timezone
    print()
    print(color("◆ Timezone", Colors.CYAN, Colors.BOLD))
    tz = config.get('timezone', '')
    if tz:
        print(f"  Timezone:     {tz}")
    else:
        print(f"  Timezone:     {color('(server-local)', Colors.DIM)}")

    # Compression
    print()
    print(color("◆ Context Compression", Colors.CYAN, Colors.BOLD))
    compression = config.get('compression', {})
    enabled = compression.get('enabled', True)
    print(f"  Enabled:      {'yes' if enabled else 'no'}")
    if enabled:
        print(f"  Threshold:    {compression.get('threshold', 0.50) * 100:.0f}%")
        print(f"  Target ratio: {compression.get('target_ratio', 0.20) * 100:.0f}% of threshold preserved")
        print(f"  Protect last: {compression.get('protect_last_n', 20)} messages")
        _aux_comp = config.get('auxiliary', {}).get('compression', {})
        _sm = _aux_comp.get('model', '') or '(auto)'
        print(f"  Model:        {_sm}")
        comp_provider = _aux_comp.get('provider', 'auto')
        if comp_provider and comp_provider != 'auto':
            print(f"  Provider:     {comp_provider}")
    
    # Auxiliary models
    auxiliary = config.get('auxiliary', {})
    aux_tasks = {
        "Vision":      auxiliary.get('vision', {}),
        "Web extract": auxiliary.get('web_extract', {}),
    }
    has_overrides = any(
        t.get('provider', 'auto') != 'auto' or t.get('model', '')
        for t in aux_tasks.values()
    )
    if has_overrides:
        print()
        print(color("◆ Auxiliary Models (overrides)", Colors.CYAN, Colors.BOLD))
        for label, task_cfg in aux_tasks.items():
            prov = task_cfg.get('provider', 'auto')
            mdl = task_cfg.get('model', '')
            if prov != 'auto' or mdl:
                parts = [f"provider={prov}"]
                if mdl:
                    parts.append(f"model={mdl}")
                print(f"  {label:12s}  {', '.join(parts)}")
    
    # Messaging
    print()
    print(color("◆ Messaging Platforms", Colors.CYAN, Colors.BOLD))
    
    telegram_token = get_env_value('TELEGRAM_BOT_TOKEN')
    discord_token = get_env_value('DISCORD_BOT_TOKEN')
    
    print(f"  Telegram:     {'configured' if telegram_token else color('not configured', Colors.DIM)}")
    print(f"  Discord:      {'configured' if discord_token else color('not configured', Colors.DIM)}")
    
    # Skill config
    try:
        from agent.skill_utils import discover_all_skill_config_vars, resolve_skill_config_values
        skill_vars = discover_all_skill_config_vars()
        if skill_vars:
            resolved = resolve_skill_config_values(skill_vars)
            print()
            print(color("◆ Skill Settings", Colors.CYAN, Colors.BOLD))
            for var in skill_vars:
                key = var["key"]
                value = resolved.get(key, "")
                skill_name = var.get("skill", "")
                display_val = str(value) if value else color("(not set)", Colors.DIM)
                print(f"  {key:<20s} {display_val}  {color(f'[{skill_name}]', Colors.DIM)}")
    except Exception:
        pass

    print()
    print(color("─" * 60, Colors.DIM))
    print(color("  hermes config edit     # Edit config file", Colors.DIM))
    print(color("  hermes config set <key> <value>", Colors.DIM))
    print(color("  hermes setup           # Run setup wizard", Colors.DIM))
    print()


def edit_config():
    """Open config file in user's editor."""
    if is_managed():
        managed_error("edit configuration")
        return
    config_path = get_config_path()
    
    # Ensure config exists
    if not config_path.exists():
        save_config(DEFAULT_CONFIG)
        print(f"Created {config_path}")
    
    # Find editor
    editor = os.getenv('EDITOR') or os.getenv('VISUAL')
    
    if not editor:
        # Try common editors
        for cmd in ['nano', 'vim', 'vi', 'code', 'notepad']:
            import shutil
            if shutil.which(cmd):
                editor = cmd
                break
    
    if not editor:
        print("No editor found. Config file is at:")
        print(f"  {config_path}")
        return
    
    print(f"Opening {config_path} in {editor}...")
    subprocess.run([editor, str(config_path)])


def set_config_value(key: str, value: str):
    """Set a configuration value."""
    if is_managed():
        managed_error("set configuration values")
        return
    # Check if it's an API key (goes to .env)
    api_keys = [
        'OPENROUTER_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'VOICE_TOOLS_OPENAI_KEY',
        'EXA_API_KEY', 'PARALLEL_API_KEY', 'FIRECRAWL_API_KEY', 'FIRECRAWL_API_URL',
        'FIRECRAWL_GATEWAY_URL', 'TOOL_GATEWAY_DOMAIN', 'TOOL_GATEWAY_SCHEME',
        'TOOL_GATEWAY_USER_TOKEN', 'TAVILY_API_KEY',
        'BROWSERBASE_API_KEY', 'BROWSERBASE_PROJECT_ID', 'BROWSER_USE_API_KEY',
        'FAL_KEY', 'TELEGRAM_BOT_TOKEN', 'DISCORD_BOT_TOKEN',
        'TERMINAL_SSH_HOST', 'TERMINAL_SSH_USER', 'TERMINAL_SSH_KEY',
        'SUDO_PASSWORD', 'SLACK_BOT_TOKEN', 'SLACK_APP_TOKEN',
        'GITHUB_TOKEN', 'HONCHO_API_KEY', 'WANDB_API_KEY',
        'TINKER_API_KEY',
    ]
    
    if key.upper() in api_keys or key.upper().endswith(('_API_KEY', '_TOKEN')) or key.upper().startswith('TERMINAL_SSH'):
        save_env_value(key.upper(), value)
        print(f"✓ Set {key} in {get_env_path()}")
        return
    
    # Otherwise it goes to config.yaml
    # Read the raw user config (not merged with defaults) to avoid
    # dumping all default values back to the file
    config_path = get_config_path()
    user_config = {}
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}
        except Exception:
            user_config = {}
    
    # Handle nested keys (e.g., "tts.provider") including numeric list
    # indices (e.g., "custom_providers.0.api_key").  Delegates to
    # _set_nested which preserves list-typed nodes; before #17876 the
    # inline navigation here silently overwrote lists with dicts.

    # Convert value to appropriate type
    if value.lower() in ('true', 'yes', 'on'):
        value = True
    elif value.lower() in ('false', 'no', 'off'):
        value = False
    elif value.isdigit():
        value = int(value)
    elif value.replace('.', '', 1).isdigit():
        value = float(value)

    _set_nested(user_config, key, value)
    
    # Write only user config back (not the full merged defaults)
    ensure_hermes_home()
    from utils import atomic_yaml_write
    atomic_yaml_write(config_path, user_config, sort_keys=False)
    
    # Keep .env in sync for keys that terminal_tool reads directly from env vars.
    # config.yaml is authoritative, but terminal_tool only reads TERMINAL_ENV etc.
    _config_to_env_sync = {
        "terminal.backend": "TERMINAL_ENV",
        "terminal.modal_mode": "TERMINAL_MODAL_MODE",
        "terminal.docker_image": "TERMINAL_DOCKER_IMAGE",
        "terminal.singularity_image": "TERMINAL_SINGULARITY_IMAGE",
        "terminal.modal_image": "TERMINAL_MODAL_IMAGE",
        "terminal.daytona_image": "TERMINAL_DAYTONA_IMAGE",
        "terminal.vercel_runtime": "TERMINAL_VERCEL_RUNTIME",
        "terminal.docker_mount_cwd_to_workspace": "TERMINAL_DOCKER_MOUNT_CWD_TO_WORKSPACE",
        "terminal.docker_run_as_host_user": "TERMINAL_DOCKER_RUN_AS_HOST_USER",
        "terminal.cwd": "TERMINAL_CWD",
        "terminal.timeout": "TERMINAL_TIMEOUT",
        "terminal.sandbox_dir": "TERMINAL_SANDBOX_DIR",
        "terminal.persistent_shell": "TERMINAL_PERSISTENT_SHELL",
        "terminal.container_cpu": "TERMINAL_CONTAINER_CPU",
        "terminal.container_memory": "TERMINAL_CONTAINER_MEMORY",
        "terminal.container_disk": "TERMINAL_CONTAINER_DISK",
        "terminal.container_persistent": "TERMINAL_CONTAINER_PERSISTENT",
    }
    if key in _config_to_env_sync:
        save_env_value(_config_to_env_sync[key], str(value))

    print(f"✓ Set {key} = {value} in {config_path}")


# =============================================================================
# Command handler
# =============================================================================

def config_command(args):
    """Handle config subcommands."""
    subcmd = getattr(args, 'config_command', None)
    
    if subcmd is None or subcmd == "show":
        show_config()
    
    elif subcmd == "edit":
        edit_config()
    
    elif subcmd == "set":
        key = getattr(args, 'key', None)
        value = getattr(args, 'value', None)
        if not key or value is None:
            print("Usage: hermes config set <key> <value>")
            print()
            print("Examples:")
            print("  hermes config set model anthropic/claude-sonnet-4")
            print("  hermes config set terminal.backend docker")
            print("  hermes config set OPENROUTER_API_KEY sk-or-...")
            sys.exit(1)
        set_config_value(key, value)
    
    elif subcmd == "path":
        print(get_config_path())
    
    elif subcmd == "env-path":
        print(get_env_path())
    
    elif subcmd == "migrate":
        print()
        print(color("🔄 Checking configuration for updates...", Colors.CYAN, Colors.BOLD))
        print()
        
        # Check what's missing
        missing_env = get_missing_env_vars(required_only=False)
        missing_config = get_missing_config_fields()
        current_ver, latest_ver = check_config_version()
        
        if not missing_env and not missing_config and current_ver >= latest_ver:
            print(color("✓ Configuration is up to date!", Colors.GREEN))
            print()
            return
        
        # Show what needs to be updated
        if current_ver < latest_ver:
            print(f"  Config version: {current_ver} → {latest_ver}")
        
        if missing_config:
            print(f"\n  {len(missing_config)} new config option(s) will be added with defaults")
        
        required_missing = [v for v in missing_env if v.get("is_required")]
        optional_missing = [
            v for v in missing_env
            if not v.get("is_required") and not v.get("advanced")
        ]
        
        if required_missing:
            print(f"\n  ⚠️  {len(required_missing)} required API key(s) missing:")
            for var in required_missing:
                print(f"     • {var['name']}")
        
        if optional_missing:
            print(f"\n  ℹ️  {len(optional_missing)} optional API key(s) not configured:")
            for var in optional_missing:
                tools = var.get("tools", [])
                tools_str = f" (enables: {', '.join(tools[:2])})" if tools else ""
                print(f"     • {var['name']}{tools_str}")
        
        print()
        
        # Run migration
        results = migrate_config(interactive=True, quiet=False)
        
        print()
        if results["env_added"] or results["config_added"]:
            print(color("✓ Configuration updated!", Colors.GREEN))
        
        if results["warnings"]:
            print()
            for warning in results["warnings"]:
                print(color(f"  ⚠️  {warning}", Colors.YELLOW))
        
        print()
    
    elif subcmd == "check":
        # Non-interactive check for what's missing
        print()
        print(color("📋 Configuration Status", Colors.CYAN, Colors.BOLD))
        print()
        
        current_ver, latest_ver = check_config_version()
        if current_ver >= latest_ver:
            print(f"  Config version: {current_ver} ✓")
        else:
            print(color(f"  Config version: {current_ver} → {latest_ver} (update available)", Colors.YELLOW))
        
        print()
        print(color("  Required:", Colors.BOLD))
        for var_name in REQUIRED_ENV_VARS:
            if get_env_value(var_name):
                print(f"    ✓ {var_name}")
            else:
                print(color(f"    ✗ {var_name} (missing)", Colors.RED))
        
        print()
        print(color("  Optional:", Colors.BOLD))
        for var_name, info in OPTIONAL_ENV_VARS.items():
            if get_env_value(var_name):
                print(f"    ✓ {var_name}")
            else:
                tools = info.get("tools", [])
                tools_str = f" → {', '.join(tools[:2])}" if tools else ""
                print(color(f"    ○ {var_name}{tools_str}", Colors.DIM))
        
        missing_config = get_missing_config_fields()
        if missing_config:
            print()
            print(color(f"  {len(missing_config)} new config option(s) available", Colors.YELLOW))
            print("    Run 'hermes config migrate' to add them")
        
        print()
    
    else:
        print(f"Unknown config command: {subcmd}")
        print()
        print("Available commands:")
        print("  hermes config           Show current configuration")
        print("  hermes config edit      Open config in editor")
        print("  hermes config set <key> <value>   Set a config value")
        print("  hermes config check     Check for missing/outdated config")
        print("  hermes config migrate   Update config with new options")
        print("  hermes config path      Show config file path")
        print("  hermes config env-path  Show .env file path")
        sys.exit(1)
