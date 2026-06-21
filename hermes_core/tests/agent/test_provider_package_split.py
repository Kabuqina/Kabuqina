from __future__ import annotations


def test_provider_package_modules_alias_legacy_agent_paths():
    import agent.anthropic_adapter as legacy_anthropic
    import agent.auxiliary_client as legacy_chat
    import agent.credential_pool as legacy_pool
    import agent.error_classifier as legacy_errors
    import agent.gemini_native_adapter as legacy_gemini
    import agent.image_routing as legacy_image_routing
    import agent.model_metadata as legacy_metadata
    import agent.retry_utils as legacy_retry
    import providers.anthropic as provider_anthropic
    import providers.chat_completions as provider_chat
    import providers.credential_pool as provider_pool
    import providers.error_classifier as provider_errors
    import providers.gemini as provider_gemini
    import providers.image_routing as provider_image_routing
    import providers.model_metadata as provider_metadata
    import providers.retry as provider_retry

    assert legacy_anthropic is provider_anthropic
    assert legacy_chat is provider_chat
    assert legacy_pool is provider_pool
    assert legacy_errors is provider_errors
    assert legacy_gemini is provider_gemini
    assert legacy_image_routing is provider_image_routing
    assert legacy_metadata is provider_metadata
    assert legacy_retry is provider_retry

