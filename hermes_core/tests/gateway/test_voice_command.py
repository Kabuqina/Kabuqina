"""Retained, platform-neutral tests for gateway voice mode commands."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import Platform
from gateway.platforms.base import MessageEvent, MessageType, SessionSource


def _make_event(text: str = "", message_type=MessageType.TEXT, chat_id="123") -> MessageEvent:
    source = SessionSource(
        chat_id=chat_id,
        user_id="user1",
        platform=Platform.TELEGRAM,
    )
    source.thread_id = None
    event = MessageEvent(text=text, message_type=message_type, source=source)
    event.message_id = "msg42"
    return event


def _make_runner(tmp_path):
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.adapters = {}
    runner._voice_mode = {}
    runner._VOICE_MODE_PATH = tmp_path / "gateway_voice_mode.json"
    runner._session_db = None
    runner.session_store = MagicMock()
    runner._is_user_authorized = lambda source: True
    return runner


class TestHandleVoiceCommand:
    @pytest.fixture
    def runner(self, tmp_path):
        return _make_runner(tmp_path)

    @pytest.mark.asyncio
    async def test_voice_on(self, runner):
        result = await runner._handle_voice_command(_make_event("/voice on"))
        assert "enabled" in result.lower()
        assert runner._voice_mode["telegram:123"] == "voice_only"

    @pytest.mark.asyncio
    async def test_voice_off(self, runner):
        runner._voice_mode["telegram:123"] = "voice_only"
        result = await runner._handle_voice_command(_make_event("/voice off"))
        assert "disabled" in result.lower()
        assert runner._voice_mode["telegram:123"] == "off"

    @pytest.mark.asyncio
    async def test_voice_tts(self, runner):
        result = await runner._handle_voice_command(_make_event("/voice tts"))
        assert "tts" in result.lower()
        assert runner._voice_mode["telegram:123"] == "all"

    @pytest.mark.asyncio
    async def test_voice_status_reports_current_mode(self, runner):
        runner._voice_mode["telegram:123"] = "voice_only"
        result = await runner._handle_voice_command(_make_event("/voice status"))
        assert "voice reply" in result.lower()

    @pytest.mark.asyncio
    async def test_toggle_round_trip(self, runner):
        enabled = await runner._handle_voice_command(_make_event("/voice"))
        disabled = await runner._handle_voice_command(_make_event("/voice"))
        assert "enabled" in enabled.lower()
        assert "disabled" in disabled.lower()
        assert runner._voice_mode["telegram:123"] == "off"

    @pytest.mark.asyncio
    async def test_persistence_round_trip(self, runner):
        await runner._handle_voice_command(_make_event("/voice tts", chat_id="456"))
        persisted = json.loads(runner._VOICE_MODE_PATH.read_text())
        assert persisted == {"telegram:456": "all"}
        assert runner._load_voice_modes() == persisted


class TestRetainedVoiceState:
    def test_sync_restores_disabled_chats_for_retained_adapter(self, tmp_path):
        runner = _make_runner(tmp_path)
        runner._voice_mode = {"telegram:123": "off", "telegram:456": "all"}
        adapter = SimpleNamespace(
            _auto_tts_disabled_chats=set(),
            platform=Platform.TELEGRAM,
        )

        runner._sync_voice_mode_state_to_adapter(adapter)

        assert adapter._auto_tts_disabled_chats == {"123"}

    def test_sync_does_not_cross_platform_boundary(self, tmp_path):
        runner = _make_runner(tmp_path)
        runner._voice_mode = {"weixin:123": "off", "telegram:123": "all"}
        adapter = SimpleNamespace(
            _auto_tts_disabled_chats=set(),
            platform=Platform.TELEGRAM,
        )

        runner._sync_voice_mode_state_to_adapter(adapter)

        assert adapter._auto_tts_disabled_chats == set()

    def test_sync_restores_enabled_chats_for_retained_adapter(self, tmp_path):
        runner = _make_runner(tmp_path)
        runner._voice_mode = {
            "telegram:off-chat": "off",
            "telegram:on-chat": "voice_only",
            "telegram:tts-chat": "all",
            "slack:other-chat": "all",
        }
        adapter = SimpleNamespace(
            _auto_tts_default=False,
            _auto_tts_disabled_chats=set(),
            _auto_tts_enabled_chats=set(),
            platform=Platform.TELEGRAM,
        )

        runner._sync_voice_mode_state_to_adapter(adapter)

        assert adapter._auto_tts_disabled_chats == {"off-chat"}
        assert adapter._auto_tts_enabled_chats == {"on-chat", "tts-chat"}

    def test_sync_pushes_voice_auto_tts_default(self, tmp_path, monkeypatch):
        runner = _make_runner(tmp_path)
        adapter = SimpleNamespace(
            _auto_tts_default=False,
            _auto_tts_disabled_chats=set(),
            _auto_tts_enabled_chats=set(),
            platform=Platform.TELEGRAM,
        )
        monkeypatch.setattr(
            "kabuqina_cli.config.load_config",
            lambda: {"voice": {"auto_tts": True}},
        )

        runner._sync_voice_mode_state_to_adapter(adapter)

        assert adapter._auto_tts_default is True


class TestShouldAutoTtsForChat:
    @staticmethod
    def _call(chat_id, *, default=False, enabled=(), disabled=()):
        from gateway.platforms.base import BasePlatformAdapter

        adapter = SimpleNamespace(
            _auto_tts_default=default,
            _auto_tts_enabled_chats=set(enabled),
            _auto_tts_disabled_chats=set(disabled),
        )
        return BasePlatformAdapter._should_auto_tts_for_chat(adapter, chat_id)

    def test_falls_back_to_config_default(self):
        assert self._call("chat", default=False) is False
        assert self._call("chat", default=True) is True

    def test_explicit_enable_overrides_disabled_default(self):
        assert self._call("chat", default=False, enabled={"chat"}) is True

    def test_explicit_disable_overrides_enabled_default(self):
        assert self._call("chat", default=True, disabled={"chat"}) is False

    def test_explicit_enable_has_precedence_over_stale_disable(self):
        assert self._call(
            "chat",
            default=False,
            enabled={"chat"},
            disabled={"chat"},
        ) is True

    def test_override_is_isolated_per_chat(self):
        assert self._call("enabled", enabled={"enabled"}) is True
        assert self._call("other", enabled={"enabled"}) is False


class TestShouldSendVoiceReply:
    @staticmethod
    def _call(
        runner,
        *,
        mode,
        message_type,
        response="Hello",
        agent_messages=None,
        already_sent=False,
    ):
        event = _make_event(message_type=message_type)
        runner._voice_mode["telegram:123"] = mode
        return runner._should_send_voice_reply(
            event,
            response,
            agent_messages or [],
            already_sent=already_sent,
        )

    def test_streaming_voice_input_is_sent_by_runner(self, tmp_path):
        runner = _make_runner(tmp_path)

        assert self._call(
            runner,
            mode="voice_only",
            message_type=MessageType.VOICE,
            already_sent=True,
        ) is True

    def test_non_streaming_voice_input_is_left_to_base_adapter(self, tmp_path):
        runner = _make_runner(tmp_path)

        assert self._call(
            runner,
            mode="voice_only",
            message_type=MessageType.VOICE,
        ) is False

    def test_all_mode_sends_for_text_input(self, tmp_path):
        runner = _make_runner(tmp_path)

        assert self._call(
            runner,
            mode="all",
            message_type=MessageType.TEXT,
        ) is True

    def test_agent_tts_tool_call_deduplicates_reply(self, tmp_path):
        runner = _make_runner(tmp_path)
        agent_messages = [{
            "role": "assistant",
            "tool_calls": [{
                "function": {
                    "name": "text_to_speech",
                    "arguments": "{}",
                },
            }],
        }]

        assert self._call(
            runner,
            mode="all",
            message_type=MessageType.TEXT,
            agent_messages=agent_messages,
        ) is False


class TestSendVoiceReply:
    @pytest.mark.asyncio
    async def test_routes_voice_with_thread_metadata_and_unique_filename(
        self,
        tmp_path,
    ):
        runner = _make_runner(tmp_path)
        adapter = SimpleNamespace(send_voice=AsyncMock())
        event = _make_event()
        event.source.thread_id = "thread-7"
        runner.adapters[Platform.TELEGRAM] = adapter
        actual_audio = tmp_path / "rendered.ogg"
        actual_audio.write_bytes(b"audio")
        tts_result = json.dumps({
            "success": True,
            "file_path": str(actual_audio),
        })

        with (
            patch(
                "tools.tts_tool._strip_markdown_for_tts",
                side_effect=lambda text: text,
            ),
            patch(
                "gateway.run.asyncio.to_thread",
                new_callable=AsyncMock,
                return_value=tts_result,
            ) as to_thread,
            patch(
                "gateway.run.tempfile.gettempdir",
                return_value=str(tmp_path),
            ),
            patch(
                "uuid.uuid4",
                return_value=SimpleNamespace(hex="0123456789abcdef"),
            ),
        ):
            await runner._send_voice_reply(event, "Hello world")

        requested_path = to_thread.await_args.kwargs["output_path"]
        assert requested_path.endswith("tts_reply_0123456789ab.mp3")
        adapter.send_voice.assert_awaited_once_with(
            chat_id="123",
            audio_path=str(actual_audio),
            reply_to="msg42",
            metadata={"thread_id": "thread-7"},
        )
        assert not actual_audio.exists()

    @pytest.mark.asyncio
    async def test_cleans_rendered_file_when_adapter_send_fails(self, tmp_path):
        runner = _make_runner(tmp_path)
        adapter = SimpleNamespace(
            send_voice=AsyncMock(side_effect=RuntimeError("send failed")),
        )
        event = _make_event(message_type=MessageType.VOICE)
        runner.adapters[Platform.TELEGRAM] = adapter
        actual_audio = tmp_path / "failed-send.ogg"
        actual_audio.write_bytes(b"audio")
        tts_result = json.dumps({
            "success": True,
            "file_path": str(actual_audio),
        })

        with (
            patch(
                "tools.tts_tool._strip_markdown_for_tts",
                return_value="Hello",
            ),
            patch(
                "gateway.run.asyncio.to_thread",
                new_callable=AsyncMock,
                return_value=tts_result,
            ),
            patch(
                "gateway.run.tempfile.gettempdir",
                return_value=str(tmp_path),
            ),
        ):
            await runner._send_voice_reply(event, "Hello")

        adapter.send_voice.assert_awaited_once()
        assert not actual_audio.exists()
