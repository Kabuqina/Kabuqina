"""Retained, platform-neutral tests for gateway voice mode commands."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

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
