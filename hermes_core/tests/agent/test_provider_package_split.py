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

