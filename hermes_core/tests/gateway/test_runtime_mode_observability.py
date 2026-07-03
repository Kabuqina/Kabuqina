"""Safe logging contract for the gateway's resolved LLM transport."""

from __future__ import annotations

import logging

from gateway import run as gateway_run
from hermes_cli import runtime_provider


def test_gateway_logs_resolved_mode_without_secret(monkeypatch, caplog):
    monkeypatch.setattr(
        runtime_provider,
        "resolve_runtime_provider",
        lambda **_: {
            "provider": "custom",
            "api_mode": "anthropic_messages",
            "base_url": "https://example.com/anthropic",
            "api_key": "never-log-me",
        },
    )

    with caplog.at_level(logging.INFO, logger="gateway.run"):
        result = gateway_run._resolve_runtime_agent_kwargs()

    assert result["api_mode"] == "anthropic_messages"
    assert "provider=custom" in caplog.text
    assert "api_mode=anthropic_messages" in caplog.text
    assert "never-log-me" not in caplog.text
