"""Tests for context token tracking in run_agent.py's usage extraction.

The context counter (status bar) must show the TOTAL prompt tokens including
Anthropic's cached portions. This is an integration test for the token
extraction in run_conversation(), not the ContextCompressor itself (which
is tested in tests/agent/test_context_compressor.py).
"""

import sys
import types
from types import SimpleNamespace

sys.modules.setdefault("fire", types.SimpleNamespace(Fire=lambda *a, **k: None))
sys.modules.setdefault("firecrawl", types.SimpleNamespace(Firecrawl=object))
sys.modules.setdefault("fal_client", types.SimpleNamespace())

import run_agent


def _patch_bootstrap(monkeypatch):
    monkeypatch.setattr(run_agent, "get_tool_definitions", lambda **kwargs: [{
        "type": "function",
        "function": {"name": "t", "description": "t", "parameters": {"type": "object", "properties": {}}},
    }])
    monkeypatch.setattr(run_agent, "check_toolset_requirements", lambda: {})


class _FakeAnthropicClient:
    def close(self):
        pass


class _FakeOpenAIClient:
    """Fake OpenAI client returned by mocked resolve_provider_client."""
    api_key = "fake-openai-key"
    base_url = "https://api.openai.com/v1"
    _default_headers = None


def _make_agent(monkeypatch, api_mode, provider, response_fn):
    _patch_bootstrap(monkeypatch)
    monkeypatch.setattr(run_agent, "OpenAI", lambda **kwargs: _FakeOpenAIClient())
    import providers.anthropic as anthropic_provider

    monkeypatch.setattr(
        anthropic_provider,
        "build_anthropic_client",
        lambda *args, **kwargs: _FakeAnthropicClient(),
    )
    agent = run_agent.AIAgent(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        provider=provider,
        api_mode=api_mode,
        model="claude-sonnet-4-6" if api_mode == "anthropic_messages" else "gpt-4o",
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
    )
    agent.api_mode = api_mode
    agent.provider = provider
    agent._disable_streaming = True
    if api_mode == "anthropic_messages":
        monkeypatch.setattr(agent, "_anthropic_messages_create", lambda api_kwargs: response_fn())
    else:
        monkeypatch.setattr(agent, "_interruptible_api_call", lambda api_kwargs: response_fn())
    return agent



def _anthropic_resp(input_tok, output_tok, cache_read=0, cache_creation=0):
    usage_fields = {"input_tokens": input_tok, "output_tokens": output_tok}
    if cache_read:
        usage_fields["cache_read_input_tokens"] = cache_read
    if cache_creation:
        usage_fields["cache_creation_input_tokens"] = cache_creation
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text="ok")],
        stop_reason="end_turn",
        usage=SimpleNamespace(**usage_fields),
        model="claude-sonnet-4-6",
    )


# -- Anthropic: cached tokens must be included --

def test_anthropic_cache_read_and_creation_added(monkeypatch):
    agent = _make_agent(monkeypatch, "anthropic_messages", "anthropic",
                        lambda: _anthropic_resp(3, 10, cache_read=15000, cache_creation=2000))
    agent.run_conversation("hi")
    assert agent.context_compressor.last_prompt_tokens == 17003  # 3+15000+2000
    assert agent.session_prompt_tokens == 17003


def test_anthropic_no_cache_fields(monkeypatch):
    agent = _make_agent(monkeypatch, "anthropic_messages", "anthropic",
                        lambda: _anthropic_resp(500, 20))
    agent.run_conversation("hi")
    assert agent.context_compressor.last_prompt_tokens == 500


def test_anthropic_cache_read_only(monkeypatch):
    agent = _make_agent(monkeypatch, "anthropic_messages", "anthropic",
                        lambda: _anthropic_resp(5, 15, cache_read=17666, cache_creation=15))
    agent.run_conversation("hi")
    assert agent.context_compressor.last_prompt_tokens == 17686  # 5+17666+15


# -- OpenAI: prompt_tokens already total --

def test_openai_prompt_tokens_unchanged(monkeypatch):
    resp = lambda: SimpleNamespace(
        choices=[SimpleNamespace(index=0, message=SimpleNamespace(
            role="assistant", content="ok", tool_calls=None, reasoning_content=None,
        ), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=5000, completion_tokens=100, total_tokens=5100),
        model="gpt-4o",
    )
    agent = _make_agent(monkeypatch, "chat_completions", "openrouter", resp)
    agent.run_conversation("hi")
    assert agent.context_compressor.last_prompt_tokens == 5000


# -- Missing cache fields default to 0 --
