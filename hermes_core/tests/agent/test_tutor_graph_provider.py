from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from agent.graph_engine.tutor_contracts import (
    TutorProviderPlanV1,
    TutorProviderRequestV1,
)
from agent.graph_engine.tutor_ports import (
    SingleAttemptTutorProvider,
    TutorProviderBinding,
    TutorProviderOutputError,
    TutorProviderResolver,
    TutorProviderTimeoutError,
    TutorProviderUnavailableError,
    estimate_tutor_input_tokens,
)
from learning.tutor_runtime_store import ProviderAttemptReservationV1


def _plan(api_mode: str = "chat_completions") -> TutorProviderPlanV1:
    return TutorProviderPlanV1(
        provider_id="custom",
        model_id="model-1",
        api_mode=api_mode,
        endpoint_identity="https://example.invalid/v1",
    )


def _binding(api_mode: str = "chat_completions") -> TutorProviderBinding:
    return TutorProviderBinding(plan=_plan(api_mode), api_key="secret-not-persisted")


def _reservation(api_mode: str = "chat_completions") -> ProviderAttemptReservationV1:
    return ProviderAttemptReservationV1(
        attempt_id="attempt-1",
        segment_id="segment-1",
        ordinal=1,
        provider_id="custom",
        model_id="model-1",
        api_mode=api_mode,
        reserved_input_tokens=16_384,
        reserved_output_tokens=2_048,
        reserved_wall_ms=35_000,
    )


def _request(purpose: str = "explain") -> TutorProviderRequestV1:
    return TutorProviderRequestV1(
        purpose=purpose,
        goal="Explain fractions",
        input_refs=({"kind": "source", "id": "source-1"},),
        previous_output="first explanation" if purpose == "remediate" else None,
    )


class _ChatClient:
    def __init__(self, content: str, *, error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))],
            usage=SimpleNamespace(prompt_tokens=21, completion_tokens=8),
        )


def test_chat_execute_once_uses_one_physical_request_and_no_sdk_retry() -> None:
    client = _ChatClient(json.dumps({"schema_version": 1, "markdown": "Clear."}))
    factory_calls: list[dict] = []

    def factory(binding, *, timeout_s, max_retries):
        factory_calls.append(
            {"binding": binding, "timeout_s": timeout_s, "max_retries": max_retries}
        )
        return client

    port = SingleAttemptTutorProvider(_binding(), client_factory=factory)
    result = port.execute_once(_reservation(), _request(), timeout_s=12.5)

    assert result.markdown == "Clear."
    assert result.actual_input_tokens == 21
    assert result.actual_output_tokens == 8
    assert len(client.calls) == 1
    assert factory_calls[0]["max_retries"] == 0
    assert factory_calls[0]["timeout_s"] == 12.5
    assert client.calls[0]["timeout"] == 12.5
    assert client.calls[0]["max_tokens"] == 2_048


def test_invalid_output_fails_after_exactly_one_request() -> None:
    client = _ChatClient("not-json")
    port = SingleAttemptTutorProvider(
        _binding(), client_factory=lambda *_args, **_kwargs: client
    )

    with pytest.raises(TutorProviderOutputError):
        port.execute_once(_reservation(), _request(), timeout_s=10)

    assert len(client.calls) == 1


def test_client_construction_failure_is_typed_before_any_request() -> None:
    port = SingleAttemptTutorProvider(
        _binding(),
        client_factory=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ImportError("missing SDK")
        ),
    )

    with pytest.raises(TutorProviderUnavailableError):
        port.execute_once(_reservation(), _request(), timeout_s=10)


def test_timeout_fails_after_exactly_one_request() -> None:
    client = _ChatClient("", error=TimeoutError("must not be persisted"))
    port = SingleAttemptTutorProvider(
        _binding(), client_factory=lambda *_args, **_kwargs: client
    )

    with pytest.raises(TutorProviderTimeoutError):
        port.execute_once(_reservation(), _request(), timeout_s=10)

    assert len(client.calls) == 1


def test_reservation_candidate_mismatch_fails_before_client_creation() -> None:
    calls = []
    bad = ProviderAttemptReservationV1(
        **{**_reservation().__dict__, "model_id": "forged-model"}
    )
    port = SingleAttemptTutorProvider(
        _binding(), client_factory=lambda *_args, **_kwargs: calls.append(1)
    )

    with pytest.raises(TutorProviderUnavailableError):
        port.execute_once(bad, _request(), timeout_s=10)

    assert calls == []


def test_anthropic_execute_once_uses_one_messages_request() -> None:
    calls: list[dict] = []

    class Client:
        def __init__(self):
            self.messages = SimpleNamespace(create=self.create)

        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="text",
                        text=json.dumps(
                            {"schema_version": 1, "markdown": "Anthropic output"}
                        ),
                    )
                ],
                usage=SimpleNamespace(input_tokens=18, output_tokens=7),
            )

    port = SingleAttemptTutorProvider(
        _binding("anthropic_messages"),
        client_factory=lambda *_args, **_kwargs: Client(),
    )
    result = port.execute_once(
        _reservation("anthropic_messages"), _request(), timeout_s=8
    )

    assert result.markdown == "Anthropic output"
    assert result.actual_input_tokens == 18
    assert result.actual_output_tokens == 7
    assert len(calls) == 1
    assert calls[0]["max_tokens"] == 2_048


def test_resolver_freezes_current_candidate_and_rebinds_only_exact_saved_plan() -> None:
    runtime = {
        "provider": "custom",
        "api_mode": "chat_completions",
        "base_url": "https://example.invalid/v1/",
        "api_key": "secret",
    }
    requested: list[str | None] = []

    def load_runtime(provider):
        requested.append(provider)
        return dict(runtime)

    resolver = TutorProviderResolver(
        runtime_loader=load_runtime,
        config_loader=lambda: {
            "model": {"provider": "custom", "default": "model-1"}
        },
    )

    binding = resolver.resolve_current()
    rebound = resolver.bind_saved(binding.plan)

    assert binding.plan == _plan()
    assert rebound.plan.plan_hash == binding.plan.plan_hash
    assert requested == ["custom", "custom"]
    assert "secret" not in str(binding.plan.to_checkpoint_dict())


def test_saved_plan_drift_fails_closed_without_switching_candidate() -> None:
    resolver = TutorProviderResolver(
        runtime_loader=lambda _provider: {
            "provider": "custom",
            "api_mode": "chat_completions",
            "base_url": "https://different.invalid/v1",
            "api_key": "secret",
        },
        config_loader=lambda: {"model": {"default": "ignored"}},
    )

    with pytest.raises(TutorProviderUnavailableError):
        resolver.bind_saved(_plan())


def test_native_gemini_candidate_fails_closed_before_execution() -> None:
    resolver = TutorProviderResolver(
        runtime_loader=lambda _provider: {
            "provider": "gemini",
            "api_mode": "chat_completions",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "api_key": "secret",
        },
        config_loader=lambda: {
            "model": {"provider": "gemini", "default": "gemini-test"}
        },
    )

    with pytest.raises(TutorProviderUnavailableError):
        resolver.resolve_current()


def test_unknown_tokenizer_reservation_is_utf8_byte_conservative() -> None:
    request = TutorProviderRequestV1(
        purpose="explain", goal="分数", input_refs=()
    )
    estimate = estimate_tutor_input_tokens(request)
    assert estimate >= len("分数".encode("utf-8"))
    assert estimate > len(
        json.dumps(
            {"goal": "分数", "input_refs": []},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )
