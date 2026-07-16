from __future__ import annotations

import importlib

import pytest

# Phase 3a removed the legacy ``agent.*`` alias shims (the provider extraction's
# migration scaffolding); ``providers.*`` is now the single import surface. These
# tests guard that the legacy paths stay gone, and that the canonical modules
# still import.
_REMOVED_AGENT_MODULES = (
    "agent.anthropic_adapter",
    "agent.auxiliary_client",
    "agent.credential_pool",
    "agent.credential_sources",
    "agent.error_classifier",
    "agent.gemini_native_adapter",
    "agent.image_gen_provider",
    "agent.image_gen_registry",
    "agent.image_routing",
    "agent.model_metadata",
    "agent.nous_rate_guard",
    "agent.rate_limit_tracker",
    "agent.retry_utils",
    "agent.transports",
    "agent.transports.anthropic",
    "agent.transports.base",
    "agent.transports.chat_completions",
    "agent.transports.types",
)

_CANONICAL_PROVIDER_MODULES = (
    "providers.anthropic",
    "providers.chat_completions",
    "providers.credential_pool",
    "providers.credential_sources",
    "providers.error_classifier",
    "providers.gemini",
    "providers.image_gen_provider",
    "providers.image_gen_registry",
    "providers.image_routing",
    "providers.model_metadata",
    "providers.nous_rate_guard",
    "providers.rate_limit_tracker",
    "providers.retry",
    "providers.transports",
    "providers.transports.anthropic",
    "providers.transports.base",
    "providers.transports.chat_completions",
    "providers.transports.types",
)


@pytest.mark.parametrize("module_name", _REMOVED_AGENT_MODULES)
def test_legacy_agent_alias_modules_are_removed(module_name):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)


@pytest.mark.parametrize("module_name", _CANONICAL_PROVIDER_MODULES)
def test_canonical_provider_modules_import(module_name):
    assert importlib.import_module(module_name) is not None


# Auth-store persistence primitives moved from kabuqina_cli.auth into
# providers.auth_store. kabuqina_cli.auth must re-export every name so existing
# imports and monkeypatches of kabuqina_cli.auth.* keep hitting the same object.
_AUTH_STORE_PRIMITIVES = (
    "AUTH_STORE_VERSION",
    "AUTH_LOCK_TIMEOUT_SECONDS",
    "_auth_file_path",
    "_auth_lock_path",
    "_auth_lock_holder",
    "_auth_store_lock",
    "_load_auth_store",
    "_save_auth_store",
    "_load_provider_state",
    "_save_provider_state",
    "_store_provider_state",
    "read_credential_pool",
    "write_credential_pool",
    "suppress_credential_source",
    "is_source_suppressed",
    "unsuppress_credential_source",
    "get_provider_auth_state",
    "get_active_provider",
    "clear_provider_auth",
    "deactivate_provider",
)


def test_auth_store_primitives_live_in_providers_package():
    import providers.auth_store as auth_store

    for name in _AUTH_STORE_PRIMITIVES:
        assert hasattr(auth_store, name), f"providers.auth_store missing {name}"


def test_kabuqina_cli_auth_reexports_auth_store_primitives():
    import kabuqina_cli.auth as auth
    import providers.auth_store as auth_store

    for name in _AUTH_STORE_PRIMITIVES:
        assert getattr(auth, name) is getattr(auth_store, name), (
            f"kabuqina_cli.auth.{name} must re-export providers.auth_store.{name}"
        )


# API-key secret / base-URL resolution helpers moved from kabuqina_cli.auth into
# providers.api_key_auth. The registry-coupled callers (get_anthropic_key,
# resolve_api_key_provider_credentials, resolve_external_process_provider_credentials)
# stay in kabuqina_cli.auth and reach these via re-export.
_API_KEY_AUTH_PRIMITIVES = (
    "KIMI_CODE_BASE_URL",
    "ZAI_ENDPOINTS",
    "_PLACEHOLDER_SECRET_VALUES",
    "has_usable_secret",
    "_resolve_kimi_base_url",
    "_resolve_api_key_provider_secret",
    "detect_zai_endpoint",
    "_resolve_zai_base_url",
)


def test_api_key_auth_helpers_live_in_providers_package():
    import providers.api_key_auth as api_key_auth

    for name in _API_KEY_AUTH_PRIMITIVES:
        assert hasattr(api_key_auth, name), f"providers.api_key_auth missing {name}"


def test_kabuqina_cli_auth_reexports_api_key_auth_helpers():
    import kabuqina_cli.auth as auth
    import providers.api_key_auth as api_key_auth

    for name in _API_KEY_AUTH_PRIMITIVES:
        assert getattr(auth, name) is getattr(api_key_auth, name), (
            f"kabuqina_cli.auth.{name} must re-export providers.api_key_auth.{name}"
        )


# Shared OAuth / JWT / timestamp leaf helpers moved from kabuqina_cli.auth into
# providers.oauth_helpers (stdlib-only; importable by any provider module
# without a cycle). kabuqina_cli.auth re-exports them for existing call sites.
_OAUTH_HELPERS = (
    "_token_fingerprint",
    "_oauth_trace_enabled",
    "_oauth_trace",
    "_parse_iso_timestamp",
    "_is_expiring",
    "_coerce_ttl_seconds",
    "_optional_base_url",
    "_decode_jwt_claims",
)


def test_oauth_helpers_live_in_providers_package():
    import providers.oauth_helpers as oauth_helpers

    for name in _OAUTH_HELPERS:
        assert hasattr(oauth_helpers, name), f"providers.oauth_helpers missing {name}"


def test_kabuqina_cli_auth_reexports_oauth_helpers():
    import kabuqina_cli.auth as auth
    import providers.oauth_helpers as oauth_helpers

    for name in _OAUTH_HELPERS:
        assert getattr(auth, name) is getattr(oauth_helpers, name), (
            f"kabuqina_cli.auth.{name} must re-export providers.oauth_helpers.{name}"
        )


# AuthError + format_auth_error moved to providers.auth_errors (a zero-dep leaf
# so provider resolver modules can raise AuthError without an import cycle).
_AUTH_ERROR_NAMES = ("AuthError", "format_auth_error")


def test_auth_errors_live_in_providers_package():
    import providers.auth_errors as auth_errors

    for name in _AUTH_ERROR_NAMES:
        assert hasattr(auth_errors, name), f"providers.auth_errors missing {name}"


def test_kabuqina_cli_auth_reexports_auth_errors():
    import kabuqina_cli.auth as auth
    import providers.auth_errors as auth_errors

    for name in _AUTH_ERROR_NAMES:
        assert getattr(auth, name) is getattr(auth_errors, name), (
            f"kabuqina_cli.auth.{name} must re-export providers.auth_errors.{name}"
        )


# Nous Portal runtime auth (device-code, refresh, mint, status) moved from
# kabuqina_cli.auth into providers.nous_auth.  kabuqina_cli.auth re-exports every
# name so existing imports and monkeypatches keep hitting the same objects.
_NOUS_AUTH_PRIMITIVES = (
    "_default_verify",
    "_resolve_verify",
    "_request_device_code",
    "_poll_for_token",
    "_refresh_access_token",
    "_mint_agent_key",
    "fetch_nous_models",
    "_agent_key_is_usable",
    "resolve_nous_access_token",
    "refresh_nous_oauth_pure",
    "refresh_nous_oauth_from_state",
    "NOUS_DEVICE_CODE_SOURCE",
    "persist_nous_credentials",
    "resolve_nous_runtime_credentials",
    "_empty_nous_auth_status",
    "_snapshot_nous_pool_status",
    "get_nous_auth_status",
)


def test_nous_auth_primitives_live_in_providers_package():
    import providers.nous_auth as nous_auth

    for name in _NOUS_AUTH_PRIMITIVES:
        assert hasattr(nous_auth, name), f"providers.nous_auth missing {name}"


def test_kabuqina_cli_auth_reexports_nous_auth_primitives():
    import kabuqina_cli.auth as auth
    import providers.nous_auth as nous_auth

    for name in _NOUS_AUTH_PRIMITIVES:
        assert getattr(auth, name) is getattr(nous_auth, name), (
            f"kabuqina_cli.auth.{name} must re-export providers.nous_auth.{name}"
        )


# MiniMax OAuth runtime helpers moved from kabuqina_cli.auth into
# providers.minimax_auth.  kabuqina_cli.auth re-exports every name so existing
# imports and monkeypatches keep hitting the same objects.
_MINIMAX_AUTH_PRIMITIVES = (
    "_minimax_pkce_pair",
    "_minimax_request_user_code",
    "_minimax_poll_token",
    "_minimax_save_auth_state",
    "_refresh_minimax_oauth_state",
    "resolve_minimax_oauth_runtime_credentials",
    "get_minimax_oauth_auth_status",
)


def test_minimax_auth_primitives_live_in_providers_package():
    import providers.minimax_auth as minimax_auth

    for name in _MINIMAX_AUTH_PRIMITIVES:
        assert hasattr(minimax_auth, name), f"providers.minimax_auth missing {name}"


def test_kabuqina_cli_auth_reexports_minimax_auth_primitives():
    import kabuqina_cli.auth as auth
    import providers.minimax_auth as minimax_auth

    for name in _MINIMAX_AUTH_PRIMITIVES:
        assert getattr(auth, name) is getattr(minimax_auth, name), (
            f"kabuqina_cli.auth.{name} must re-export providers.minimax_auth.{name}"
        )
