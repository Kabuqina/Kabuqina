"""Provider parity tests: verify that AIAgent builds correct API kwargs
and handles responses properly for all supported providers.

Ensures changes to one provider path don't silently break another.
"""

import json
import os
import sys
import types
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest
sys.modules.setdefault("fire", types.SimpleNamespace(Fire=lambda *a, **k: None))
sys.modules.setdefault("firecrawl", types.SimpleNamespace(Firecrawl=object))
sys.modules.setdefault("fal_client", types.SimpleNamespace())

from run_agent import AIAgent


# ── Helpers ──────────────────────────────────────────────────────────────────

def _tool_defs(*names):
    return [
        {
            "type": "function",
            "function": {
                "name": n,
                "description": f"{n} tool",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for n in names
    ]


class _FakeOpenAI:
    def __init__(self, **kw):
        self.api_key = kw.get("api_key", "test")
        self.base_url = kw.get("base_url", "http://test")
    def close(self):
        pass


def _make_agent(monkeypatch, provider, api_mode="chat_completions", base_url="https://openrouter.ai/api/v1", model=None):
    monkeypatch.setattr("run_agent.get_tool_definitions", lambda **kw: _tool_defs("web_search", "terminal"))
    monkeypatch.setattr("run_agent.check_toolset_requirements", lambda: {})
    monkeypatch.setattr("run_agent.OpenAI", _FakeOpenAI)
    kwargs = dict(
        api_key="test-key",
        base_url=base_url,
        provider=provider,
        api_mode=api_mode,
        max_iterations=4,
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
    )
    if model:
        kwargs["model"] = model
    return AIAgent(**kwargs)


# ── _build_api_kwargs tests ─────────────────────────────────────────────────

class TestBuildApiKwargsOpenRouter:
    def test_uses_chat_completions_format(self, monkeypatch):
        agent = _make_agent(monkeypatch, "openrouter")
        messages = [{"role": "user", "content": "hi"}]
        kwargs = agent._build_api_kwargs(messages)
        assert "messages" in kwargs
        assert "model" in kwargs
        assert kwargs["messages"][-1]["content"] == "hi"

    def test_includes_reasoning_in_extra_body(self, monkeypatch):
        agent = _make_agent(monkeypatch, "openrouter")
        agent.model = "anthropic/claude-sonnet-4-20250514"
        messages = [{"role": "user", "content": "hi"}]
        kwargs = agent._build_api_kwargs(messages)
        extra = kwargs.get("extra_body", {})
        assert "reasoning" in extra
        assert extra["reasoning"]["enabled"] is True

    def test_includes_tools(self, monkeypatch):
        agent = _make_agent(monkeypatch, "openrouter")
        messages = [{"role": "user", "content": "hi"}]
        kwargs = agent._build_api_kwargs(messages)
        assert "tools" in kwargs
        tool_names = [t["function"]["name"] for t in kwargs["tools"]]
        assert "web_search" in tool_names

    def test_no_responses_api_fields(self, monkeypatch):
        agent = _make_agent(monkeypatch, "openrouter")
        messages = [{"role": "user", "content": "hi"}]
        kwargs = agent._build_api_kwargs(messages)
        assert "input" not in kwargs
        assert "instructions" not in kwargs
        assert "store" not in kwargs

    def test_strips_internal_tool_call_fields_from_chat_messages(self, monkeypatch):
        agent = _make_agent(monkeypatch, "openrouter")
        messages = [
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": "Checking now.",
                "tool_calls": [
                    {
                        "id": "call_123",
                        "call_id": "call_123",
                        "response_item_id": "fc_123",
                        "type": "function",
                        "function": {"name": "terminal", "arguments": "{\"command\":\"pwd\"}"},
                        "extra_content": {"thought_signature": "opaque"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_123", "content": "/tmp"},
        ]

        kwargs = agent._build_api_kwargs(messages)

        assistant_msg = kwargs["messages"][1]
        tool_call = assistant_msg["tool_calls"][0]

        assert tool_call["id"] == "call_123"
        assert tool_call["function"]["name"] == "terminal"
        assert tool_call["extra_content"] == {"thought_signature": "opaque"}
        assert "call_id" not in tool_call
        assert "response_item_id" not in tool_call

        # Original stored history must remain unchanged.
        assert messages[1]["tool_calls"][0]["call_id"] == "call_123"
        assert messages[1]["tool_calls"][0]["response_item_id"] == "fc_123"

    def test_gemini_native_passes_base_url_for_top_level_thinking_config(self, monkeypatch):
        agent = _make_agent(
            monkeypatch,
            "gemini",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            model="gemini-3-flash-preview",
        )
        agent.reasoning_config = {"enabled": True, "effort": "high"}
        kwargs = agent._build_api_kwargs([{"role": "user", "content": "hi"}])
        assert kwargs["extra_body"]["thinking_config"] == {
            "includeThoughts": True,
            "thinkingLevel": "high",
        }
        assert "extra_body" not in kwargs["extra_body"]

    def test_gemini_openai_compat_passes_base_url_for_nested_google_thinking_config(self, monkeypatch):
        agent = _make_agent(
            monkeypatch,
            "gemini",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            model="gemini-3.1-pro-preview",
        )
        agent.reasoning_config = {"enabled": True, "effort": "high"}
        kwargs = agent._build_api_kwargs([{"role": "user", "content": "hi"}])
        assert "thinking_config" not in kwargs["extra_body"]
        assert kwargs["extra_body"]["extra_body"]["google"]["thinking_config"] == {
            "include_thoughts": True,
            "thinking_level": "high",
        }


class TestDeveloperRoleSwap:
    """GPT-5 models should get 'developer' instead of 'system' role."""

    @pytest.mark.parametrize("model", [
        "openai/gpt-5",
        "openai/gpt-5-turbo",
        "openai/gpt-5.4",
        "gpt-5-mini",
    ])
    def test_gpt5_get_developer_role(self, monkeypatch, model):
        agent = _make_agent(monkeypatch, "openrouter")
        agent.model = model
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hi"},
        ]
        kwargs = agent._build_api_kwargs(messages)
        assert kwargs["messages"][0]["role"] == "developer"
        assert kwargs["messages"][0]["content"] == "You are helpful."
        assert kwargs["messages"][1]["role"] == "user"

    @pytest.mark.parametrize("model", [
        "anthropic/claude-opus-4.6",
        "openai/gpt-4o",
        "google/gemini-2.5-pro",
        "deepseek/deepseek-chat",
        "openai/o3-mini",
    ])
    def test_non_matching_models_keep_system_role(self, monkeypatch, model):
        agent = _make_agent(monkeypatch, "openrouter")
        agent.model = model
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hi"},
        ]
        kwargs = agent._build_api_kwargs(messages)
        assert kwargs["messages"][0]["role"] == "system"

    def test_no_system_message_no_crash(self, monkeypatch):
        agent = _make_agent(monkeypatch, "openrouter")
        agent.model = "openai/gpt-5"
        messages = [{"role": "user", "content": "hi"}]
        kwargs = agent._build_api_kwargs(messages)
        assert kwargs["messages"][0]["role"] == "user"

    def test_original_messages_not_mutated(self, monkeypatch):
        agent = _make_agent(monkeypatch, "openrouter")
        agent.model = "openai/gpt-5"
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hi"},
        ]
        agent._build_api_kwargs(messages)
        # Original messages must be untouched (internal representation stays "system")
        assert messages[0]["role"] == "system"

    def test_developer_role_via_nous_portal(self, monkeypatch):
        agent = _make_agent(monkeypatch, "nous", base_url="https://inference-api.nousresearch.com/v1")
        agent.model = "gpt-5"
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hi"},
        ]
        kwargs = agent._build_api_kwargs(messages)
        assert kwargs["messages"][0]["role"] == "developer"


class TestBuildApiKwargsChatCompletionsServiceTier:
    """service_tier via request_overrides works on the chat_completions path."""

    def test_includes_service_tier_via_request_overrides(self, monkeypatch):
        agent = _make_agent(monkeypatch, "openrouter")
        agent.model = "gpt-4.1"
        agent.request_overrides = {"service_tier": "priority"}
        messages = [{"role": "user", "content": "hi"}]
        kwargs = agent._build_api_kwargs(messages)
        assert kwargs["service_tier"] == "priority"

    def test_no_service_tier_when_overrides_empty(self, monkeypatch):
        agent = _make_agent(monkeypatch, "openrouter")
        agent.model = "gpt-4.1"
        agent.request_overrides = {}
        messages = [{"role": "user", "content": "hi"}]
        kwargs = agent._build_api_kwargs(messages)
        assert "service_tier" not in kwargs

    def test_no_crash_when_request_overrides_is_none(self, monkeypatch):
        agent = _make_agent(monkeypatch, "openrouter")
        agent.model = "gpt-4.1"
        agent.request_overrides = None
        messages = [{"role": "user", "content": "hi"}]
        kwargs = agent._build_api_kwargs(messages)
        assert "service_tier" not in kwargs


class TestBuildApiKwargsKimiNoTemperatureOverride:
    def test_kimi_for_coding_omits_temperature(self, monkeypatch):
        """Temperature should NOT be set client-side for Kimi models.

        The Kimi gateway selects the correct temperature server-side.
        """
        agent = _make_agent(
            monkeypatch,
            "kimi-coding",
            base_url="https://api.kimi.com/coding/v1",
            model="kimi-for-coding",
        )
        messages = [{"role": "user", "content": "hi"}]
        kwargs = agent._build_api_kwargs(messages)
        assert "temperature" not in kwargs


class TestBuildApiKwargsNousPortal:
    def test_includes_nous_product_tags(self, monkeypatch):
        agent = _make_agent(monkeypatch, "nous", base_url="https://inference-api.nousresearch.com/v1")
        messages = [{"role": "user", "content": "hi"}]
        kwargs = agent._build_api_kwargs(messages)
        extra = kwargs.get("extra_body", {})
        assert extra.get("tags") == ["product=hermes-agent"]

    def test_uses_chat_completions_format(self, monkeypatch):
        agent = _make_agent(monkeypatch, "nous", base_url="https://inference-api.nousresearch.com/v1")
        messages = [{"role": "user", "content": "hi"}]
        kwargs = agent._build_api_kwargs(messages)
        assert "messages" in kwargs
        assert "input" not in kwargs


class TestBuildApiKwargsCustomEndpoint:
    def test_uses_chat_completions_format(self, monkeypatch):
        agent = _make_agent(monkeypatch, "custom", base_url="http://localhost:1234/v1")
        messages = [{"role": "user", "content": "hi"}]
        kwargs = agent._build_api_kwargs(messages)
        assert "messages" in kwargs
        assert "input" not in kwargs

    def test_no_openrouter_extra_body(self, monkeypatch):
        agent = _make_agent(monkeypatch, "custom", base_url="http://localhost:1234/v1")
        messages = [{"role": "user", "content": "hi"}]
        kwargs = agent._build_api_kwargs(messages)
        extra = kwargs.get("extra_body", {})
        assert "reasoning" not in extra

    def test_fireworks_tool_call_payload_strips_internal_fields(self, monkeypatch):
        agent = _make_agent(
            monkeypatch,
            "custom",
            base_url="https://api.fireworks.ai/inference/v1",
        )
        messages = [
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": "Checking now.",
                "tool_calls": [
                    {
                        "id": "call_fw_123",
                        "call_id": "call_fw_123",
                        "response_item_id": "fc_fw_123",
                        "type": "function",
                        "function": {
                            "name": "terminal",
                            "arguments": "{\"command\":\"pwd\"}",
                        },
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_fw_123", "content": "/tmp"},
        ]

        kwargs = agent._build_api_kwargs(messages)

        assert kwargs["tools"][0]["function"]["name"] == "web_search"
        assert "input" not in kwargs
        assert kwargs.get("extra_body", {}) == {}

        assistant_msg = kwargs["messages"][1]
        tool_call = assistant_msg["tool_calls"][0]

        assert tool_call["id"] == "call_fw_123"
        assert tool_call["type"] == "function"
        assert tool_call["function"]["name"] == "terminal"
        assert "call_id" not in tool_call
        assert "response_item_id" not in tool_call


# ── Chat completions response handling (OpenRouter/Nous) ─────────────────────

class TestBuildAssistantMessage:
    """Verify _build_assistant_message works for all provider response formats."""

    def test_openrouter_reasoning_fields(self, monkeypatch):
        agent = _make_agent(monkeypatch, "openrouter")
        msg = SimpleNamespace(
            content="answer",
            tool_calls=None,
            reasoning="I thought about it",
            reasoning_content=None,
            reasoning_details=None,
        )
        result = agent._build_assistant_message(msg, "stop")
        assert result["content"] == "answer"
        assert result["reasoning"] == "I thought about it"

    def test_openrouter_reasoning_details_preserved_unmodified(self, monkeypatch):
        """reasoning_details must be passed back exactly as received for
        multi-turn continuity (OpenRouter, Anthropic, OpenAI all need this)."""
        agent = _make_agent(monkeypatch, "openrouter")
        original_detail = {
            "type": "thinking",
            "thinking": "deep thoughts here",
            "signature": "sig123_opaque_blob",
            "encrypted_content": "some_provider_blob",
            "extra_field": "should_not_be_dropped",
        }
        msg = SimpleNamespace(
            content="answer",
            tool_calls=None,
            reasoning=None,
            reasoning_content=None,
            reasoning_details=[original_detail],
        )
        result = agent._build_assistant_message(msg, "stop")
        stored = result["reasoning_details"][0]
        # ALL fields must survive, not just type/text/signature
        assert stored["signature"] == "sig123_opaque_blob"
        assert stored["encrypted_content"] == "some_provider_blob"
        assert stored["extra_field"] == "should_not_be_dropped"
        assert stored["thinking"] == "deep thoughts here"

# ── Auxiliary client provider resolution ─────────────────────────────────────

class TestAuxiliaryClientProviderPriority:
    """Verify auxiliary client resolution doesn't break for any provider."""

    def test_openrouter_always_wins(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        from providers.chat_completions import get_text_auxiliary_client
        with patch("providers.chat_completions.OpenAI") as mock:
            client, model = get_text_auxiliary_client()
        assert model == "google/gemini-3-flash-preview"
        assert "openrouter" in str(mock.call_args.kwargs["base_url"]).lower()

    def test_nous_when_no_openrouter(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        from providers.chat_completions import get_text_auxiliary_client
        with patch("providers.chat_completions._read_nous_auth", return_value={"access_token": "nous-tok"}), \
             patch("hermes_cli.models.get_nous_recommended_aux_model", return_value=None), \
             patch("providers.chat_completions.OpenAI") as mock:
            client, model = get_text_auxiliary_client()
        assert model == "google/gemini-3-flash-preview"

    def test_custom_endpoint_when_no_nous(self, monkeypatch):
        """Custom endpoint is used when no OpenRouter/Nous keys are available.

        Since the March 2026 config refactor, OPENAI_BASE_URL env var is no
        longer consulted — base_url comes from config.yaml via
        resolve_runtime_provider.  Mock _resolve_custom_runtime directly.
        """
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "local-key")
        from providers.chat_completions import get_text_auxiliary_client
        with patch("providers.chat_completions._read_nous_auth", return_value=None), \
             patch("providers.chat_completions._resolve_custom_runtime",
                   return_value=("http://localhost:1234/v1", "local-key")), \
             patch("providers.chat_completions.OpenAI") as mock:
            client, model = get_text_auxiliary_client()
        assert mock.call_args.kwargs["base_url"] == "http://localhost:1234/v1"

# ── Provider routing tests ───────────────────────────────────────────────────

class TestProviderRouting:
    """Verify provider_routing config flows into extra_body.provider."""

    def test_sort_throughput(self, monkeypatch):
        agent = _make_agent(monkeypatch, "openrouter")
        agent.provider_sort = "throughput"
        kwargs = agent._build_api_kwargs([{"role": "user", "content": "hi"}])
        assert kwargs["extra_body"]["provider"]["sort"] == "throughput"

    def test_only_providers(self, monkeypatch):
        agent = _make_agent(monkeypatch, "openrouter")
        agent.providers_allowed = ["anthropic", "google"]
        kwargs = agent._build_api_kwargs([{"role": "user", "content": "hi"}])
        assert kwargs["extra_body"]["provider"]["only"] == ["anthropic", "google"]

    def test_ignore_providers(self, monkeypatch):
        agent = _make_agent(monkeypatch, "openrouter")
        agent.providers_ignored = ["deepinfra"]
        kwargs = agent._build_api_kwargs([{"role": "user", "content": "hi"}])
        assert kwargs["extra_body"]["provider"]["ignore"] == ["deepinfra"]

    def test_order_providers(self, monkeypatch):
        agent = _make_agent(monkeypatch, "openrouter")
        agent.providers_order = ["anthropic", "together"]
        kwargs = agent._build_api_kwargs([{"role": "user", "content": "hi"}])
        assert kwargs["extra_body"]["provider"]["order"] == ["anthropic", "together"]

    def test_require_parameters(self, monkeypatch):
        agent = _make_agent(monkeypatch, "openrouter")
        agent.provider_require_parameters = True
        kwargs = agent._build_api_kwargs([{"role": "user", "content": "hi"}])
        assert kwargs["extra_body"]["provider"]["require_parameters"] is True

    def test_data_collection_deny(self, monkeypatch):
        agent = _make_agent(monkeypatch, "openrouter")
        agent.provider_data_collection = "deny"
        kwargs = agent._build_api_kwargs([{"role": "user", "content": "hi"}])
        assert kwargs["extra_body"]["provider"]["data_collection"] == "deny"

    def test_no_routing_when_unset(self, monkeypatch):
        agent = _make_agent(monkeypatch, "openrouter")
        kwargs = agent._build_api_kwargs([{"role": "user", "content": "hi"}])
        assert "provider" not in kwargs.get("extra_body", {}).get("provider", {}) or \
               kwargs.get("extra_body", {}).get("provider") is None or \
               "only" not in kwargs.get("extra_body", {}).get("provider", {})

    def test_combined_routing(self, monkeypatch):
        agent = _make_agent(monkeypatch, "openrouter")
        agent.provider_sort = "latency"
        agent.providers_ignored = ["deepinfra"]
        agent.provider_data_collection = "deny"
        kwargs = agent._build_api_kwargs([{"role": "user", "content": "hi"}])
        prov = kwargs["extra_body"]["provider"]
        assert prov["sort"] == "latency"
        assert prov["ignore"] == ["deepinfra"]
        assert prov["data_collection"] == "deny"


# ── Reasoning effort consistency tests ───────────────────────────────────────

class TestReasoningEffortDefaults:
    """Verify reasoning effort defaults to medium across all provider paths."""

    def test_openrouter_default_medium(self, monkeypatch):
        agent = _make_agent(monkeypatch, "openrouter")
        agent.model = "anthropic/claude-sonnet-4-20250514"
        kwargs = agent._build_api_kwargs([{"role": "user", "content": "hi"}])
        reasoning = kwargs["extra_body"]["reasoning"]
        assert reasoning["effort"] == "medium"

    def test_openrouter_reasoning_config_override(self, monkeypatch):
        agent = _make_agent(monkeypatch, "openrouter")
        agent.model = "anthropic/claude-sonnet-4-20250514"
        agent.reasoning_config = {"enabled": True, "effort": "medium"}
        kwargs = agent._build_api_kwargs([{"role": "user", "content": "hi"}])
        assert kwargs["extra_body"]["reasoning"]["effort"] == "medium"
