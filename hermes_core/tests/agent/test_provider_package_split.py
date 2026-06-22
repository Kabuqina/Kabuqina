from __future__ import annotations


def test_provider_package_modules_alias_legacy_agent_paths():
    import agent.anthropic_adapter as legacy_anthropic
    import agent.auxiliary_client as legacy_chat
    import agent.credential_pool as legacy_pool
    import agent.credential_sources as legacy_sources
    import agent.error_classifier as legacy_errors
    import agent.gemini_native_adapter as legacy_gemini
    import agent.image_gen_provider as legacy_image_gen_provider
    import agent.image_gen_registry as legacy_image_gen_registry
    import agent.image_routing as legacy_image_routing
    import agent.model_metadata as legacy_metadata
    import agent.nous_rate_guard as legacy_nous_guard
    import agent.rate_limit_tracker as legacy_rate_limits
    import agent.retry_utils as legacy_retry
    import providers.anthropic as provider_anthropic
    import providers.chat_completions as provider_chat
    import providers.credential_pool as provider_pool
    import providers.credential_sources as provider_sources
    import providers.error_classifier as provider_errors
    import providers.gemini as provider_gemini
    import providers.image_gen_provider as provider_image_gen_provider
    import providers.image_gen_registry as provider_image_gen_registry
    import providers.image_routing as provider_image_routing
    import providers.model_metadata as provider_metadata
    import providers.nous_rate_guard as provider_nous_guard
    import providers.rate_limit_tracker as provider_rate_limits
    import providers.retry as provider_retry

    assert legacy_anthropic is provider_anthropic
    assert legacy_chat is provider_chat
    assert legacy_pool is provider_pool
    assert legacy_sources is provider_sources
    assert legacy_errors is provider_errors
    assert legacy_gemini is provider_gemini
    assert legacy_image_gen_provider is provider_image_gen_provider
    assert legacy_image_gen_registry is provider_image_gen_registry
    assert legacy_image_routing is provider_image_routing
    assert legacy_metadata is provider_metadata
    assert legacy_nous_guard is provider_nous_guard
    assert legacy_rate_limits is provider_rate_limits
    assert legacy_retry is provider_retry


def test_provider_transports_package_aliases_legacy_agent_paths():
    import agent.transports as legacy_transports
    import agent.transports.anthropic as legacy_anthropic
    import agent.transports.base as legacy_base
    import agent.transports.chat_completions as legacy_chat
    import agent.transports.types as legacy_types
    import providers.transports as provider_transports
    import providers.transports.anthropic as provider_anthropic
    import providers.transports.base as provider_base
    import providers.transports.chat_completions as provider_chat
    import providers.transports.types as provider_types

    assert legacy_transports is provider_transports
    assert legacy_anthropic is provider_anthropic
    assert legacy_base is provider_base
    assert legacy_chat is provider_chat
    assert legacy_types is provider_types


# Auth-store persistence primitives moved from hermes_cli.auth into
# providers.auth_store. hermes_cli.auth must re-export every name so existing
# imports and monkeypatches of hermes_cli.auth.* keep hitting the same object.
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


def test_hermes_cli_auth_reexports_auth_store_primitives():
    import hermes_cli.auth as auth
    import providers.auth_store as auth_store

    for name in _AUTH_STORE_PRIMITIVES:
        assert getattr(auth, name) is getattr(auth_store, name), (
            f"hermes_cli.auth.{name} must re-export providers.auth_store.{name}"
        )


# API-key secret / base-URL resolution helpers moved from hermes_cli.auth into
# providers.api_key_auth. The registry-coupled callers (get_anthropic_key,
# resolve_api_key_provider_credentials, resolve_external_process_provider_credentials)
# stay in hermes_cli.auth and reach these via re-export.
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


def test_hermes_cli_auth_reexports_api_key_auth_helpers():
    import hermes_cli.auth as auth
    import providers.api_key_auth as api_key_auth

    for name in _API_KEY_AUTH_PRIMITIVES:
        assert getattr(auth, name) is getattr(api_key_auth, name), (
            f"hermes_cli.auth.{name} must re-export providers.api_key_auth.{name}"
        )


# Shared OAuth / JWT / timestamp leaf helpers moved from hermes_cli.auth into
# providers.oauth_helpers (stdlib-only; importable by any provider module
# without a cycle). hermes_cli.auth re-exports them for existing call sites.
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


def test_hermes_cli_auth_reexports_oauth_helpers():
    import hermes_cli.auth as auth
    import providers.oauth_helpers as oauth_helpers

    for name in _OAUTH_HELPERS:
        assert getattr(auth, name) is getattr(oauth_helpers, name), (
            f"hermes_cli.auth.{name} must re-export providers.oauth_helpers.{name}"
        )


# AuthError + format_auth_error moved to providers.auth_errors (a zero-dep leaf
# so provider resolver modules can raise AuthError without an import cycle).
_AUTH_ERROR_NAMES = ("AuthError", "format_auth_error")


def test_auth_errors_live_in_providers_package():
    import providers.auth_errors as auth_errors

    for name in _AUTH_ERROR_NAMES:
        assert hasattr(auth_errors, name), f"providers.auth_errors missing {name}"


def test_hermes_cli_auth_reexports_auth_errors():
    import hermes_cli.auth as auth
    import providers.auth_errors as auth_errors

    for name in _AUTH_ERROR_NAMES:
        assert getattr(auth, name) is getattr(auth_errors, name), (
            f"hermes_cli.auth.{name} must re-export providers.auth_errors.{name}"
        )

