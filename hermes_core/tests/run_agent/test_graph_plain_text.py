# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Phase 3.5 Task 4: plain-text vertical slice — loop ≡ graph for a text reply.

Reuses the ``golden/plain_text.json`` fixture and the same hermetic setup
as ``test_golden_transcripts.py``.  The test replays the transcript through
the **graph engine** path (``AIAgent._run_conversation_graph``) instead of
the legacy loop (``AIAgent.run_conversation``) and asserts that the result
is byte-identical.

This is the behavioural gate for ``initialize_turn → prepare_request →
call_transport → process_response → finish``.
"""

from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

sys.modules.setdefault("fire", types.SimpleNamespace(Fire=lambda *a, **k: None))
sys.modules.setdefault("firecrawl", types.SimpleNamespace(Firecrawl=object))
sys.modules.setdefault("fal_client", types.SimpleNamespace())

from tests.run_agent.golden_harness import (
    GOLDEN_SESSION_ID,
    GOLDEN_TASK_ID,
    _CompressStub,
    _FakeChatClient,
    _ScriptedClock,
    _ScriptedTransport,
    _ToolStub,
    _chat_response,
    _fallback_patch,
    _normalize_messages,
    _patches,
    _snapshot,
    _validate_retry_assumptions,
    _anthropic_response,
)


GOLDEN_DIR = Path(__file__).parent / "golden"


def _replay_graph(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Replay one transcript through ``AIAgent._run_conversation_graph``."""
    import run_agent

    _validate_retry_assumptions(spec.get("assumed_retry_counts", {}))

    cfg = spec.get("agent", {})
    preconditions = spec.get("preconditions", {})
    api_mode = cfg.get("api_mode", "chat_completions")
    provider = cfg.get("provider", "openrouter")
    model = cfg.get("model", "golden/test-model")
    base_url = cfg.get("base_url", "https://api.openai.com/v1")

    tool_names = spec.get("tools", [])
    tool_stub = _ToolStub(spec.get("tool_results", {}))
    builder = _anthropic_response if api_mode == "anthropic_messages" else _chat_response
    transport = _ScriptedTransport(spec.get("model_turns", []), builder, model)
    stream_log: List[str] = []
    callback_events: List[Dict[str, Any]] = []
    trajectory_writes: List[Dict[str, Any]] = []

    summary_spec = spec.get("summary_response")
    summary_response = _chat_response(summary_spec, model) if summary_spec else None

    compression = spec.get("compression")
    compressed_sequence = preconditions.get("compressed_history_sequence")
    if compressed_sequence is not None:
        compress_stub = _CompressStub(sequence=compressed_sequence)
    elif compression:
        compress_stub = _CompressStub(compression.get("compressed_history", []))
    else:
        compress_stub = None
    conversation_history = spec.get("conversation_history")

    extra_kwargs = {}
    if "max_iterations" in cfg:
        extra_kwargs["max_iterations"] = cfg["max_iterations"]
    if cfg.get("fallback_model"):
        extra_kwargs["fallback_model"] = cfg["fallback_model"]

    with _patches(
        tool_names, tool_stub, api_mode, preconditions
    ) as hook_recorder, _fallback_patch(cfg.get("fallback_model")):
        agent = run_agent.AIAgent(
            api_key="golden-key",
            base_url=base_url,
            provider=provider,
            api_mode=api_mode,
            model=model,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            status_callback=lambda kind, message: callback_events.append(
                {"channel": "status", "kind": kind, "message": message}
            ),
            interim_assistant_callback=lambda text, **kwargs: callback_events.append(
                {
                    "channel": "interim",
                    "text": text,
                    "already_streamed": bool(kwargs.get("already_streamed")),
                }
            ),
            **extra_kwargs,
        )
        agent.session_id = GOLDEN_SESSION_ID
        agent.api_mode = api_mode
        agent.provider = provider
        agent._disable_streaming = True
        agent._session_db = MagicMock()
        agent._last_flushed_db_idx = 0
        agent._save_session_log = lambda *a, **k: None

        def _record_trajectory(messages, user_query, completed):
            trajectory_writes.append(
                {
                    "messages": _normalize_messages(messages),
                    "user_query": user_query,
                    "completed": completed,
                }
            )

        agent._save_trajectory = _record_trajectory
        if summary_response is not None:
            agent.client = _FakeChatClient(summary_response)

        if compression is not None:
            agent.compression_enabled = True
            cc = agent.context_compressor
            cc.protect_first_n = compression.get("protect_first_n", 1)
            cc.protect_last_n = compression.get("protect_last_n", 1)
            cc.threshold_tokens = compression.get("threshold_tokens", 5)
            cc.compress = compress_stub
        elif compress_stub is not None:
            agent.context_compressor.compress = compress_stub

        if "context_length" in preconditions:
            agent.context_compressor.context_length = preconditions["context_length"]

        cleanup_task_ids: List[str] = []
        clear_interrupt_calls = [0]
        _real_cleanup = agent._cleanup_task_resources
        _real_clear = agent.clear_interrupt

        def _observed_cleanup(task_id, _real=_real_cleanup, _ids=cleanup_task_ids):
            _ids.append(task_id)
            return _real(task_id)

        def _observed_clear(_real=_real_clear, _box=clear_interrupt_calls):
            _box[0] += 1
            return _real()

        agent._cleanup_task_resources = _observed_cleanup
        agent.clear_interrupt = _observed_clear

        transport.agent = agent
        if api_mode == "anthropic_messages":
            agent._anthropic_messages_create = transport
        else:
            agent._interruptible_api_call = transport

        clock = _ScriptedClock(
            interrupt_on_sleep=preconditions.get("interrupt_on_sleep"),
            interrupt=lambda: agent.interrupt(
                preconditions.get("interrupt_text", "scripted sleep interrupt")
            ),
        )
        with (
            patch.object(run_agent.time, "time", clock.time),
            patch.object(run_agent.time, "sleep", clock.sleep),
            patch.object(
                run_agent,
                "jittered_backoff",
                lambda *a, **k: preconditions.get("backoff_seconds", 0.2),
            ),
        ):

            def _record_stream(text):
                stream_log.append(text)
                callback_events.append({"channel": "stream", "text": text})

            # ── GRAPH PATH ────────────────────────────────────────
            result = agent._run_conversation_graph(
                spec["user_message"],
                conversation_history=conversation_history,
                task_id=GOLDEN_TASK_ID,
                stream_callback=_record_stream,
            )

    if compress_stub is not None:
        assert compress_stub.calls > 0, (
            "compression transcript did not trip the preflight compressor"
        )

    return _snapshot(
        result,
        agent,
        tool_stub,
        transport,
        stream_log,
        hook_recorder,
        cleanup_task_ids,
        clear_interrupt_calls[0],
        callback_events,
        trajectory_writes,
    )


# ── Tests ────────────────────────────────────────────────────────────────────


def test_graph_plain_text_matches_loop():
    """The graph engine produces the same essential output as the legacy loop.

    Task 4 only requires the plain-text route (no tools, no hooks, no full
    side-effect parity).  We compare the core result fields — final_response,
    api_calls, completed, messages — not the full snapshot which includes
    hook calls, trajectory writes, and usage accounting that will be wired
    in later tasks.
    """
    fixture_path = GOLDEN_DIR / "plain_text.json"
    spec = json.loads(fixture_path.read_text(encoding="utf-8"))
    snapshot = _replay_graph(spec)

    expected = spec.get("expected")
    assert expected is not None, "plain_text.json has no 'expected' snapshot"

    # ── Core result fields must match ────────────────────────────────
    assert snapshot["result"]["final_response"] == expected["result"]["final_response"]
    assert snapshot["result"]["completed"] == expected["result"]["completed"]
    assert snapshot["result"]["api_calls"] == expected["result"]["api_calls"]
    assert snapshot["result"]["interrupted"] == expected["result"]["interrupted"]
    assert snapshot["result"]["partial"] == expected["result"]["partial"]

    # ── Messages must contain the assistant response ─────────────────
    assert len(snapshot["messages"]) > 0, "No messages in graph output"
    # At minimum, the assistant message must be present
    assistant_msgs = [m for m in snapshot["messages"] if m.get("role") == "assistant"]
    assert len(assistant_msgs) == 1, f"Expected 1 assistant message, got {len(assistant_msgs)}"
    assert assistant_msgs[0]["content"] == expected["result"]["final_response"]

    # ── Model turns consumed must match ──────────────────────────────
    assert snapshot["model_turns_consumed"] == expected["model_turns_consumed"]

    # ── Tool invocations must be empty (plain text) ──────────────────
    assert snapshot["tool_invocations"] == []
