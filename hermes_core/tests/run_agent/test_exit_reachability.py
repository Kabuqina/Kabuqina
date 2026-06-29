# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Runtime reachability proofs for the legacy ``run_conversation`` exits."""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest

from tests.run_agent.golden_harness import (
    _CompressStub,
    _ScriptedClock,
    _ScriptedTransport,
    _chat_response,
    _validate_retry_assumptions,
    replay_transcript,
)

GOLDEN_DIR = Path(__file__).parent / "golden"

# Return line numbers rebased 2026-06-29 after Tasks 5-7 added graph-engine code
# above and inside the adapter (the returns themselves are unchanged; only their
# absolute positions shifted).  Kept in sync with EXIT_INVENTORY in
# test_exit_contract.py.
RUNTIME_EXITS = {
    "nous_rate_guard_without_fallback": (10111, "exit_nous_rate_guard.json"),
    "invalid_response_retries_exhausted": (10336, "exit_invalid_response.json"),
    "interrupt_during_invalid_response_wait": (10357, "exit_interrupt_invalid_wait.json"),
    "thinking_budget_exhausted": (10470, "exit_thinking_budget.json"),
    "text_continuation_exhausted": (10510, "exit_text_continuation.json"),
    "truncated_tool_call_repeated": (10538, "exit_truncated_tool_call.json"),
    "interrupt_during_api_error_handling": (11122, "exit_interrupt_api_error.json"),
    "payload_compression_attempts_exhausted": (11292, "exit_payload_compression.json"),
    "payload_cannot_compress": (11323, "exit_payload_no_compression.json"),
    "safe_output_context_attempts_exhausted": (11376, "exit_safe_output_context.json"),
    "context_stepdown_attempts_exhausted": (11449, "exit_context_stepdown.json"),
    "context_cannot_compress": (11482, "exit_context_no_compression.json"),
    "nonretryable_client_error": (11577, "exit_nonretryable_client.json"),
    "api_retries_exhausted": (11660, "exit_api_retries.json"),
    "interrupt_during_generic_retry_wait": (11702, "exit_interrupt_retry_wait.json"),
    "incomplete_scratchpad_exhausted": (11856, "exit_incomplete_scratchpad.json"),
    "unknown_tool_retries_exhausted": (11903, "unknown_tool.json"),
    "truncated_json_tool_arguments": (11969, "exit_truncated_json_args.json"),
    "normal_final_result": (12689, "plain_text.json"),
}


def _replay_with_line_trace(spec):
    visited: set[int] = set()

    def trace(frame, event, arg):
        if (
            event == "line"
            and frame.f_code.co_name == "run_conversation"
            and Path(frame.f_code.co_filename).name == "run_agent.py"
        ):
            visited.add(frame.f_lineno)
        return trace

    sys.settrace(trace)
    try:
        snapshot = replay_transcript(spec)
    finally:
        sys.settrace(None)
    return snapshot, visited


def test_scripted_transport_raises_declared_error_with_metadata() -> None:
    transport = _ScriptedTransport(
        [
            {
                "raise": {
                    "type": "api_error",
                    "status_code": 413,
                    "message": "request payload too large",
                }
            }
        ],
        _chat_response,
        "golden/test-model",
    )

    with pytest.raises(Exception, match="request payload too large") as caught:
        transport()

    assert caught.value.status_code == 413
    assert transport.calls == 1


def test_compress_stub_replays_declared_sequence() -> None:
    stub = _CompressStub(
        sequence=[
            [{"role": "user", "content": "first"}],
            [{"role": "user", "content": "second"}],
        ]
    )

    assert stub([]) == [{"role": "user", "content": "first"}]
    assert stub([]) == [{"role": "user", "content": "second"}]
    with pytest.raises(AssertionError, match="only declares 2 output"):
        stub([])


def test_retry_assumptions_reject_contract_drift() -> None:
    with pytest.raises(AssertionError, match="api_max_retries"):
        _validate_retry_assumptions({"api_max_retries": 99})


def test_replay_validates_retry_assumptions_before_transport() -> None:
    spec = {
        "agent": {},
        "user_message": "hello",
        "model_turns": [],
        "assumed_retry_counts": {"api_max_retries": 99},
    }

    with pytest.raises(AssertionError, match="api_max_retries"):
        replay_transcript(spec)


def test_scripted_clock_advances_and_interrupts_on_declared_sleep() -> None:
    interrupts: list[str] = []
    clock = _ScriptedClock(
        interrupt_on_sleep=2,
        interrupt=lambda: interrupts.append("interrupt"),
    )

    before = clock.time()
    clock.sleep(0.2)
    clock.sleep(0.2)

    assert clock.time() == pytest.approx(before + 0.4)
    assert interrupts == ["interrupt"]


def test_nous_rate_guard_precondition_reaches_guard_exit() -> None:
    snapshot = replay_transcript(
        {
            "agent": {"provider": "nous"},
            "user_message": "hello",
            "model_turns": [],
            "preconditions": {"nous_rate_guard_seconds": 60},
        }
    )

    assert snapshot["result"]["completed"] is False
    assert "Nous Portal rate limit active" in snapshot["result"]["final_response"]
    assert snapshot["model_turns_consumed"] == 0


@pytest.mark.parametrize(
    ("scenario_id", "return_line", "fixture_name"),
    [(scenario, *contract) for scenario, contract in RUNTIME_EXITS.items()],
    ids=list(RUNTIME_EXITS),
)
def test_runtime_exit_is_reachable(
    scenario_id: str, return_line: int, fixture_name: str
) -> None:
    spec = json.loads((GOLDEN_DIR / fixture_name).read_text(encoding="utf-8"))

    _snapshot, visited = _replay_with_line_trace(spec)

    assert return_line in visited, (
        f"{scenario_id} did not execute source return at run_agent.py:{return_line}; "
        f"fixture={fixture_name}"
    )


def test_truncation_fallthroughs_are_structurally_unreachable() -> None:
    from providers.transports.anthropic import AnthropicTransport
    from providers.transports.base import NormalizedResponse
    from providers.transports.chat_completions import ChatCompletionsTransport
    from run_agent import AIAgent

    for transport in (ChatCompletionsTransport, AnthropicTransport):
        annotation = inspect.signature(transport.normalize_response).return_annotation
        assert annotation in (NormalizedResponse, "NormalizedResponse")

    source = inspect.getsource(AIAgent.run_conversation)
    assert "_trunc_msg = _trunc_result" in source
    assert not (GOLDEN_DIR / "exit_truncation_rolls_back_history.json").exists()
    assert not (GOLDEN_DIR / "exit_first_response_truncated.json").exists()


def test_snapshot_observes_trajectory_writes_and_callback_event_order() -> None:
    plain = json.loads((GOLDEN_DIR / "plain_text.json").read_text(encoding="utf-8"))
    max_iterations = json.loads(
        (GOLDEN_DIR / "max_iterations.json").read_text(encoding="utf-8")
    )

    plain_snapshot = replay_transcript(plain)
    max_snapshot = replay_transcript(max_iterations)

    assert len(plain_snapshot["trajectory_writes"]) == 1
    assert plain_snapshot["trajectory_writes"][0]["completed"] is True
    assert plain_snapshot["callback_events"]
    assert all(
        event["channel"] == "status" for event in plain_snapshot["callback_events"]
    )
    assert any(
        event["channel"] == "status" for event in max_snapshot["callback_events"]
    )
