"""Tests for tools/send_message_tool.py."""

import asyncio
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _reset_signal_scheduler():
    """Drop the process-wide attachment scheduler so each test gets a
    fresh token bucket."""
    from gateway.platforms.signal_rate_limit import _reset_scheduler
    _reset_scheduler()
    yield
    _reset_scheduler()


class _FakeFormData:
    def __init__(self):
        self.fields = []

    def add_field(self, *args, **kwargs):
        self.fields.append((args, kwargs))


@pytest.fixture(autouse=True)
def _fake_aiohttp_module(monkeypatch):
    fake = SimpleNamespace(
        ClientSession=MagicMock(),
        ClientTimeout=lambda *args, **kwargs: SimpleNamespace(args=args, kwargs=kwargs),
        FormData=_FakeFormData,
    )
    monkeypatch.setitem(sys.modules, "aiohttp", fake)
    return fake


from gateway.config import Platform
from tools.send_message_tool import (
    _parse_target_ref,
    _send_matrix_via_adapter,
    _send_signal,
    _send_telegram,
    _send_to_platform,
    send_message_tool,
)


def _run_async_immediately(coro):
    return asyncio.run(coro)


def _make_config():
    telegram_cfg = SimpleNamespace(enabled=True, token="***", extra={})
    return SimpleNamespace(
        platforms={Platform.TELEGRAM: telegram_cfg},
        get_home_channel=lambda _platform: None,
    ), telegram_cfg


def _install_telegram_mock(monkeypatch, bot):
    parse_mode = SimpleNamespace(MARKDOWN_V2="MarkdownV2", HTML="HTML")
    constants_mod = SimpleNamespace(ParseMode=parse_mode)
    telegram_mod = SimpleNamespace(Bot=lambda token: bot, constants=constants_mod)
    monkeypatch.setitem(sys.modules, "telegram", telegram_mod)
    monkeypatch.setitem(sys.modules, "telegram.constants", constants_mod)


def _ensure_slack_mock(monkeypatch):
    if "slack_bolt" in sys.modules and hasattr(sys.modules["slack_bolt"], "__file__"):
        return

    slack_bolt = MagicMock()
    slack_bolt.async_app.AsyncApp = MagicMock
    slack_bolt.adapter.socket_mode.async_handler.AsyncSocketModeHandler = MagicMock

    slack_sdk = MagicMock()
    slack_sdk.web.async_client.AsyncWebClient = MagicMock

    for name, mod in [
        ("slack_bolt", slack_bolt),
        ("slack_bolt.async_app", slack_bolt.async_app),
        ("slack_bolt.adapter", slack_bolt.adapter),
        ("slack_bolt.adapter.socket_mode", slack_bolt.adapter.socket_mode),
        ("slack_bolt.adapter.socket_mode.async_handler", slack_bolt.adapter.socket_mode.async_handler),
        ("slack_sdk", slack_sdk),
        ("slack_sdk.web", slack_sdk.web),
        ("slack_sdk.web.async_client", slack_sdk.web.async_client),
    ]:
        monkeypatch.setitem(sys.modules, name, mod)


class TestSendMessageTool:
    def test_cron_duplicate_target_is_skipped_and_explained(self):
        home = SimpleNamespace(chat_id="-1001")
        config, _telegram_cfg = _make_config()
        config.get_home_channel = lambda _platform: home

        with patch.dict(
            os.environ,
            {
                "HERMES_CRON_AUTO_DELIVER_PLATFORM": "telegram",
                "HERMES_CRON_AUTO_DELIVER_CHAT_ID": "-1001",
            },
            clear=False,
        ), \
             patch("gateway.config.load_gateway_config", return_value=config), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch("model_tools._run_async", side_effect=_run_async_immediately), \
             patch("tools.send_message_tool._send_to_platform", new=AsyncMock(return_value={"success": True})) as send_mock, \
             patch("gateway.mirror.mirror_to_session", return_value=True) as mirror_mock:
            result = json.loads(
                send_message_tool(
                    {
                        "action": "send",
                        "target": "telegram",
                        "message": "hello",
                    }
                )
            )

        assert result["success"] is True
        assert result["skipped"] is True
        assert result["reason"] == "cron_auto_delivery_duplicate_target"
        assert "final response" in result["note"]
        send_mock.assert_not_awaited()
        mirror_mock.assert_not_called()

    def test_resolved_telegram_topic_name_preserves_thread_id(self):
        config, telegram_cfg = _make_config()

        with patch("gateway.config.load_gateway_config", return_value=config), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch("gateway.channel_directory.resolve_channel_name", return_value="-1001:17585"), \
             patch("model_tools._run_async", side_effect=_run_async_immediately), \
             patch("tools.send_message_tool._send_to_platform", new=AsyncMock(return_value={"success": True})) as send_mock, \
             patch("gateway.mirror.mirror_to_session", return_value=True):
            result = json.loads(
                send_message_tool(
                    {
                        "action": "send",
                        "target": "telegram:Coaching Chat / topic 17585",
                        "message": "hello",
                    }
                )
            )

        assert result["success"] is True
        send_mock.assert_awaited_once_with(
            Platform.TELEGRAM,
            telegram_cfg,
            "-1001",
            "hello",
            thread_id="17585",
            media_files=[],
        )

    def test_display_label_target_resolves_via_channel_directory(self, tmp_path):
        config, telegram_cfg = _make_config()
        cache_file = tmp_path / "channel_directory.json"
        cache_file.write_text(json.dumps({
            "updated_at": "2026-01-01T00:00:00",
            "platforms": {
                "telegram": [
                    {"id": "-1001:17585", "name": "Coaching Chat / topic 17585", "type": "group"}
                ]
            },
        }))

        with patch("gateway.channel_directory.DIRECTORY_PATH", cache_file), \
             patch("gateway.config.load_gateway_config", return_value=config), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch("model_tools._run_async", side_effect=_run_async_immediately), \
             patch("tools.send_message_tool._send_to_platform", new=AsyncMock(return_value={"success": True})) as send_mock, \
             patch("gateway.mirror.mirror_to_session", return_value=True):
            result = json.loads(
                send_message_tool(
                    {
                        "action": "send",
                        "target": "telegram:Coaching Chat / topic 17585 (group)",
                        "message": "hello",
                    }
                )
            )

        assert result["success"] is True
        send_mock.assert_awaited_once_with(
            Platform.TELEGRAM,
            telegram_cfg,
            "-1001",
            "hello",
            thread_id="17585",
            media_files=[],
        )

    def test_mirror_receives_current_session_user_id(self):
        config, _telegram_cfg = _make_config()

        with patch("gateway.config.load_gateway_config", return_value=config), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch("model_tools._run_async", side_effect=_run_async_immediately), \
             patch("tools.send_message_tool._send_to_platform", new=AsyncMock(return_value={"success": True})), \
             patch("gateway.session_context.get_session_env") as get_session_env_mock, \
             patch("gateway.mirror.mirror_to_session", return_value=True) as mirror_mock:
            get_session_env_mock.side_effect = lambda name, default="": {
                "HERMES_SESSION_PLATFORM": "telegram",
                "HERMES_SESSION_USER_ID": "user-123",
            }.get(name, default)
            result = json.loads(
                send_message_tool(
                    {
                        "action": "send",
                        "target": "telegram:12345",
                        "message": "hello",
                    }
                )
            )

        assert result["success"] is True
        mirror_mock.assert_called_once_with(
            "telegram",
            "12345",
            "hello",
            source_label="telegram",
            thread_id=None,
            user_id="user-123",
        )

    def test_top_level_send_failure_redacts_query_token(self):
        config, _telegram_cfg = _make_config()
        leaked = "very-secret-query-token-123456"

        def _raise_and_close(coro):
            coro.close()
            raise RuntimeError(
                f"transport error: https://api.example.com/send?access_token={leaked}"
            )

        with patch("gateway.config.load_gateway_config", return_value=config), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch("model_tools._run_async", side_effect=_raise_and_close):
            result = json.loads(
                send_message_tool(
                    {
                        "action": "send",
                        "target": "telegram:-1001",
                        "message": "hello",
                    }
                )
            )

        assert "error" in result
        assert leaked not in result["error"]
        assert "access_token=***" in result["error"]


class TestSendTelegramMediaDelivery:
    def test_sends_text_then_photo_for_media_tag(self, tmp_path, monkeypatch):
        image_path = tmp_path / "photo.png"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)

        bot = MagicMock()
        bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=1))
        bot.send_photo = AsyncMock(return_value=SimpleNamespace(message_id=2))
        bot.send_video = AsyncMock()
        bot.send_voice = AsyncMock()
        bot.send_audio = AsyncMock()
        bot.send_document = AsyncMock()
        _install_telegram_mock(monkeypatch, bot)

        result = asyncio.run(
            _send_telegram(
                "token",
                "12345",
                "Hello there",
                media_files=[(str(image_path), False)],
            )
        )

        assert result["success"] is True
        assert result["message_id"] == "2"
        bot.send_message.assert_awaited_once()
        bot.send_photo.assert_awaited_once()
        sent_text = bot.send_message.await_args.kwargs["text"]
        assert "MEDIA:" not in sent_text
        assert sent_text == "Hello there"

    def test_sends_voice_for_ogg_with_voice_directive(self, tmp_path, monkeypatch):
        voice_path = tmp_path / "voice.ogg"
        voice_path.write_bytes(b"OggS" + b"\x00" * 32)

        bot = MagicMock()
        bot.send_message = AsyncMock()
        bot.send_photo = AsyncMock()
        bot.send_video = AsyncMock()
        bot.send_voice = AsyncMock(return_value=SimpleNamespace(message_id=7))
        bot.send_audio = AsyncMock()
        bot.send_document = AsyncMock()
        _install_telegram_mock(monkeypatch, bot)

        result = asyncio.run(
            _send_telegram(
                "token",
                "12345",
                "",
                media_files=[(str(voice_path), True)],
            )
        )

        assert result["success"] is True
        bot.send_voice.assert_awaited_once()
        bot.send_audio.assert_not_awaited()
        bot.send_message.assert_not_awaited()

    def test_sends_audio_for_mp3(self, tmp_path, monkeypatch):
        audio_path = tmp_path / "clip.mp3"
        audio_path.write_bytes(b"ID3" + b"\x00" * 32)

        bot = MagicMock()
        bot.send_message = AsyncMock()
        bot.send_photo = AsyncMock()
        bot.send_video = AsyncMock()
        bot.send_voice = AsyncMock()
        bot.send_audio = AsyncMock(return_value=SimpleNamespace(message_id=8))
        bot.send_document = AsyncMock()
        _install_telegram_mock(monkeypatch, bot)

        result = asyncio.run(
            _send_telegram(
                "token",
                "12345",
                "",
                media_files=[(str(audio_path), False)],
            )
        )

        assert result["success"] is True
        bot.send_audio.assert_awaited_once()
        bot.send_voice.assert_not_awaited()

    def test_missing_media_returns_error_without_leaking_raw_tag(self, monkeypatch):
        bot = MagicMock()
        bot.send_message = AsyncMock()
        bot.send_photo = AsyncMock()
        bot.send_video = AsyncMock()
        bot.send_voice = AsyncMock()
        bot.send_audio = AsyncMock()
        bot.send_document = AsyncMock()
        _install_telegram_mock(monkeypatch, bot)

        result = asyncio.run(
            _send_telegram(
                "token",
                "12345",
                "",
                media_files=[("/tmp/does-not-exist.png", False)],
            )
        )

        assert "error" in result
        assert "No deliverable text or media remained" in result["error"]
        bot.send_message.assert_not_awaited()


# ---------------------------------------------------------------------------
# Regression: long messages are chunked before platform dispatch
# ---------------------------------------------------------------------------


class TestSendToPlatformChunking:
    def test_slack_messages_are_formatted_before_send(self, monkeypatch):
        _ensure_slack_mock(monkeypatch)

        import gateway.platforms.slack as slack_mod

        monkeypatch.setattr(slack_mod, "SLACK_AVAILABLE", True)
        send = AsyncMock(return_value={"success": True, "message_id": "1"})

        with patch("tools.send_message_tool._send_slack", send):
            result = asyncio.run(
                _send_to_platform(
                    Platform.SLACK,
                    SimpleNamespace(enabled=True, token="***", extra={}),
                    "C123",
                    "**hello** from [Hermes](<https://example.com>)",
                )
            )

        assert result["success"] is True
        send.assert_awaited_once_with(
            "***",
            "C123",
            "*hello* from <https://example.com|Hermes>",
        )

    def test_slack_bold_italic_formatted_before_send(self, monkeypatch):
        """Bold+italic ***text*** survives tool-layer formatting."""
        _ensure_slack_mock(monkeypatch)
        import gateway.platforms.slack as slack_mod

        monkeypatch.setattr(slack_mod, "SLACK_AVAILABLE", True)
        send = AsyncMock(return_value={"success": True, "message_id": "1"})
        with patch("tools.send_message_tool._send_slack", send):
            result = asyncio.run(
                _send_to_platform(
                    Platform.SLACK,
                    SimpleNamespace(enabled=True, token="***", extra={}),
                    "C123",
                    "***important*** update",
                )
            )
        assert result["success"] is True
        sent_text = send.await_args.args[2]
        assert "*_important_*" in sent_text

    def test_slack_blockquote_formatted_before_send(self, monkeypatch):
        """Blockquote '>' markers must survive formatting (not escaped to '&gt;')."""
        _ensure_slack_mock(monkeypatch)
        import gateway.platforms.slack as slack_mod

        monkeypatch.setattr(slack_mod, "SLACK_AVAILABLE", True)
        send = AsyncMock(return_value={"success": True, "message_id": "1"})
        with patch("tools.send_message_tool._send_slack", send):
            result = asyncio.run(
                _send_to_platform(
                    Platform.SLACK,
                    SimpleNamespace(enabled=True, token="***", extra={}),
                    "C123",
                    "> important quote\n\nnormal text & stuff",
                )
            )
        assert result["success"] is True
        sent_text = send.await_args.args[2]
        assert sent_text.startswith("> important quote")
        assert "&amp;" in sent_text  # & is escaped
        assert "&gt;" not in sent_text.split("\n")[0]  # > in blockquote is NOT escaped

    def test_slack_pre_escaped_entities_not_double_escaped(self, monkeypatch):
        """Pre-escaped HTML entities survive tool-layer formatting without double-escaping."""
        _ensure_slack_mock(monkeypatch)
        import gateway.platforms.slack as slack_mod
        monkeypatch.setattr(slack_mod, "SLACK_AVAILABLE", True)
        send = AsyncMock(return_value={"success": True, "message_id": "1"})
        with patch("tools.send_message_tool._send_slack", send):
            result = asyncio.run(
                _send_to_platform(
                    Platform.SLACK,
                    SimpleNamespace(enabled=True, token="***", extra={}),
                    "C123",
                    "AT&amp;T &lt;tag&gt; test",
                )
            )
        assert result["success"] is True
        sent_text = send.await_args.args[2]
        assert "&amp;amp;" not in sent_text
        assert "&amp;lt;" not in sent_text
        assert "AT&amp;T" in sent_text

    def test_slack_url_with_parens_formatted_before_send(self, monkeypatch):
        """Wikipedia-style URL with parens survives tool-layer formatting."""
        _ensure_slack_mock(monkeypatch)
        import gateway.platforms.slack as slack_mod
        monkeypatch.setattr(slack_mod, "SLACK_AVAILABLE", True)
        send = AsyncMock(return_value={"success": True, "message_id": "1"})
        with patch("tools.send_message_tool._send_slack", send):
            result = asyncio.run(
                _send_to_platform(
                    Platform.SLACK,
                    SimpleNamespace(enabled=True, token="***", extra={}),
                    "C123",
                    "See [Foo](https://en.wikipedia.org/wiki/Foo_(bar))",
                )
            )
        assert result["success"] is True
        sent_text = send.await_args.args[2]
        assert "<https://en.wikipedia.org/wiki/Foo_(bar)|Foo>" in sent_text

    def test_telegram_media_attaches_to_last_chunk(self):

        sent_calls = []

        async def fake_send(token, chat_id, message, media_files=None, thread_id=None, disable_link_previews=False):
            sent_calls.append(media_files or [])
            return {"success": True, "platform": "telegram", "chat_id": chat_id, "message_id": str(len(sent_calls))}

        long_msg = "word " * 2000  # ~10000 chars, well over 4096
        media = [("/tmp/photo.png", False)]
        with patch("tools.send_message_tool._send_telegram", fake_send):
            asyncio.run(
                _send_to_platform(
                    Platform.TELEGRAM,
                    SimpleNamespace(enabled=True, token="tok", extra={}),
                    "123", long_msg, media_files=media,
                )
            )
        assert len(sent_calls) >= 3
        assert all(call == [] for call in sent_calls[:-1])
        assert sent_calls[-1] == media

    def test_matrix_media_uses_native_adapter_helper(self, tmp_path):

        doc_path = tmp_path / "test-send-message-matrix.pdf"
        doc_path.write_bytes(b"%PDF-1.4 test")

        try:
            helper = AsyncMock(return_value={"success": True, "platform": "matrix", "chat_id": "!room:example.com", "message_id": "$evt"})
            with patch("tools.send_message_tool._send_matrix_via_adapter", helper):
                result = asyncio.run(
                    _send_to_platform(
                        Platform.MATRIX,
                        SimpleNamespace(enabled=True, token="tok", extra={"homeserver": "https://matrix.example.com"}),
                        "!room:example.com",
                        "here you go",
                        media_files=[(str(doc_path), False)],
                    )
                )

            assert result["success"] is True
            helper.assert_awaited_once()
            call = helper.await_args
            assert call.args[1] == "!room:example.com"
            assert call.args[2] == "here you go"
            assert call.kwargs["media_files"] == [(str(doc_path), False)]
        finally:
            doc_path.unlink(missing_ok=True)

    def test_matrix_text_only_uses_lightweight_path(self):
        """Text-only Matrix sends should NOT go through the heavy adapter path."""
        helper = AsyncMock()
        lightweight = AsyncMock(return_value={"success": True, "platform": "matrix", "chat_id": "!room:ex.com", "message_id": "$txt"})
        with patch("tools.send_message_tool._send_matrix_via_adapter", helper), \
             patch("tools.send_message_tool._send_matrix", lightweight):
            result = asyncio.run(
                _send_to_platform(
                    Platform.MATRIX,
                    SimpleNamespace(enabled=True, token="tok", extra={"homeserver": "https://matrix.example.com"}),
                    "!room:ex.com",
                    "just text, no files",
                )
            )

        assert result["success"] is True
        helper.assert_not_awaited()
        lightweight.assert_awaited_once()

    def test_send_matrix_via_adapter_sends_document(self, tmp_path):
        file_path = tmp_path / "report.pdf"
        file_path.write_bytes(b"%PDF-1.4 test")

        calls = []

        class FakeAdapter:
            def __init__(self, _config):
                self.connected = False

            async def connect(self):
                self.connected = True
                calls.append(("connect",))
                return True

            async def send(self, chat_id, message, metadata=None):
                calls.append(("send", chat_id, message, metadata))
                return SimpleNamespace(success=True, message_id="$text")

            async def send_document(self, chat_id, file_path, metadata=None):
                calls.append(("send_document", chat_id, file_path, metadata))
                return SimpleNamespace(success=True, message_id="$file")

            async def disconnect(self):
                calls.append(("disconnect",))

        fake_module = SimpleNamespace(MatrixAdapter=FakeAdapter)

        with patch.dict(sys.modules, {"gateway.platforms.matrix": fake_module}):
            result = asyncio.run(
                _send_matrix_via_adapter(
                    SimpleNamespace(enabled=True, token="tok", extra={"homeserver": "https://matrix.example.com"}),
                    "!room:example.com",
                    "report attached",
                    media_files=[(str(file_path), False)],
                )
            )

        assert result == {
            "success": True,
            "platform": "matrix",
            "chat_id": "!room:example.com",
            "message_id": "$file",
        }
        assert calls == [
            ("connect",),
            ("send", "!room:example.com", "report attached", None),
            ("send_document", "!room:example.com", str(file_path), None),
            ("disconnect",),
        ]


# ---------------------------------------------------------------------------
# HTML auto-detection in Telegram send
# ---------------------------------------------------------------------------


class TestSendToPlatformWhatsapp:
    def test_whatsapp_routes_via_local_bridge_sender(self):
        chat_id = "test-user@lid"
        async_mock = AsyncMock(return_value={"success": True, "platform": "whatsapp", "chat_id": chat_id, "message_id": "abc123"})

        with patch("tools.send_message_tool._send_whatsapp", async_mock):
            result = asyncio.run(
                _send_to_platform(
                    Platform.WHATSAPP,
                    SimpleNamespace(enabled=True, token=None, extra={"bridge_port": 3000}),
                    chat_id,
                    "hello from hermes",
                )
            )

        assert result["success"] is True
        async_mock.assert_awaited_once_with({"bridge_port": 3000}, chat_id, "hello from hermes")


class TestSendTelegramHtmlDetection:
    """Verify that messages containing HTML tags are sent with parse_mode=HTML
    and that plain / markdown messages use MarkdownV2."""

    def _make_bot(self):
        bot = MagicMock()
        bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=1))
        bot.send_photo = AsyncMock()
        bot.send_video = AsyncMock()
        bot.send_voice = AsyncMock()
        bot.send_audio = AsyncMock()
        bot.send_document = AsyncMock()
        return bot

    def test_html_message_uses_html_parse_mode(self, monkeypatch):
        bot = self._make_bot()
        _install_telegram_mock(monkeypatch, bot)

        asyncio.run(
            _send_telegram("tok", "123", "<b>Hello</b> world")
        )

        bot.send_message.assert_awaited_once()
        kwargs = bot.send_message.await_args.kwargs
        assert kwargs["parse_mode"] == "HTML"
        assert kwargs["text"] == "<b>Hello</b> world"

    def test_plain_text_uses_markdown_v2(self, monkeypatch):
        bot = self._make_bot()
        _install_telegram_mock(monkeypatch, bot)

        asyncio.run(
            _send_telegram("tok", "123", "Just plain text, no tags")
        )

        bot.send_message.assert_awaited_once()
        kwargs = bot.send_message.await_args.kwargs
        assert kwargs["parse_mode"] == "MarkdownV2"

    def test_disable_link_previews_sets_disable_web_page_preview(self, monkeypatch):
        bot = self._make_bot()
        _install_telegram_mock(monkeypatch, bot)

        asyncio.run(
            _send_telegram("tok", "123", "https://example.com", disable_link_previews=True)
        )

        kwargs = bot.send_message.await_args.kwargs
        assert kwargs["disable_web_page_preview"] is True

    def test_html_with_code_and_pre_tags(self, monkeypatch):
        bot = self._make_bot()
        _install_telegram_mock(monkeypatch, bot)

        html = "<pre>code block</pre> and <code>inline</code>"
        asyncio.run(_send_telegram("tok", "123", html))

        kwargs = bot.send_message.await_args.kwargs
        assert kwargs["parse_mode"] == "HTML"

    def test_closing_tag_detected(self, monkeypatch):
        bot = self._make_bot()
        _install_telegram_mock(monkeypatch, bot)

        asyncio.run(_send_telegram("tok", "123", "text </div> more"))

        kwargs = bot.send_message.await_args.kwargs
        assert kwargs["parse_mode"] == "HTML"

    def test_angle_brackets_in_math_not_detected(self, monkeypatch):
        """Expressions like 'x < 5' or '3 > 2' should not trigger HTML mode."""
        bot = self._make_bot()
        _install_telegram_mock(monkeypatch, bot)

        asyncio.run(_send_telegram("tok", "123", "if x < 5 then y > 2"))

        kwargs = bot.send_message.await_args.kwargs
        assert kwargs["parse_mode"] == "MarkdownV2"

    def test_html_parse_failure_falls_back_to_plain(self, monkeypatch):
        """If Telegram rejects the HTML, fall back to plain text."""
        bot = self._make_bot()
        bot.send_message = AsyncMock(
            side_effect=[
                Exception("Bad Request: can't parse entities: unsupported html tag"),
                SimpleNamespace(message_id=2),  # plain fallback succeeds
            ]
        )
        _install_telegram_mock(monkeypatch, bot)

        result = asyncio.run(
            _send_telegram("tok", "123", "<invalid>broken html</invalid>")
        )

        assert result["success"] is True
        assert bot.send_message.await_count == 2
        second_call = bot.send_message.await_args_list[1].kwargs
        assert second_call["parse_mode"] is None

    def test_transient_bad_gateway_retries_text_send(self, monkeypatch):
        bot = self._make_bot()
        bot.send_message = AsyncMock(
            side_effect=[
                Exception("502 Bad Gateway"),
                SimpleNamespace(message_id=2),
            ]
        )
        _install_telegram_mock(monkeypatch, bot)

        with patch("asyncio.sleep", new=AsyncMock()) as sleep_mock:
            result = asyncio.run(_send_telegram("tok", "123", "hello"))

        assert result["success"] is True
        assert bot.send_message.await_count == 2
        sleep_mock.assert_awaited_once()


class TestParseTargetRefMatrix:
    """_parse_target_ref correctly handles Matrix room IDs and user MXIDs."""

    def test_matrix_room_id_is_explicit(self):
        """Matrix room IDs (!) are recognized as explicit targets."""
        chat_id, thread_id, is_explicit = _parse_target_ref("matrix", "!HLOQwxYGgFPMPJUSNR:matrix.org")
        assert chat_id == "!HLOQwxYGgFPMPJUSNR:matrix.org"
        assert thread_id is None
        assert is_explicit is True

    def test_matrix_user_mxid_is_explicit(self):
        """Matrix user MXIDs (@) are recognized as explicit targets."""
        chat_id, thread_id, is_explicit = _parse_target_ref("matrix", "@hermes:matrix.org")
        assert chat_id == "@hermes:matrix.org"
        assert thread_id is None
        assert is_explicit is True

    def test_matrix_alias_is_not_explicit(self):
        """Matrix room aliases (#) are NOT explicit — they need resolution."""
        chat_id, thread_id, is_explicit = _parse_target_ref("matrix", "#general:matrix.org")
        assert chat_id is None
        assert is_explicit is False

    def test_matrix_prefix_only_matches_matrix_platform(self):
        """! and @ prefixes are only treated as explicit for the matrix platform."""
        chat_id, _, is_explicit = _parse_target_ref("telegram", "!something")
        assert is_explicit is False

        chat_id, _, is_explicit = _parse_target_ref("slack", "@someone")
        assert is_explicit is False


class TestParseTargetRefE164:
    """_parse_target_ref accepts E.164 phone numbers for phone-based platforms."""

    def test_signal_e164_preserves_plus_prefix(self):
        """signal:+E164 is explicit and preserves the leading '+' for signal-cli."""
        chat_id, thread_id, is_explicit = _parse_target_ref("signal", "+41791234567")
        assert chat_id == "+41791234567"
        assert thread_id is None
        assert is_explicit is True

    def test_sms_e164_is_explicit(self):
        chat_id, _, is_explicit = _parse_target_ref("sms", "+15551234567")
        assert chat_id == "+15551234567"
        assert is_explicit is True

    def test_whatsapp_e164_is_explicit(self):
        chat_id, _, is_explicit = _parse_target_ref("whatsapp", "+15551234567")
        assert chat_id == "+15551234567"
        assert is_explicit is True

    def test_signal_bare_digits_still_work(self):
        """Bare digit strings continue to match the generic numeric branch."""
        chat_id, _, is_explicit = _parse_target_ref("signal", "15551234567")
        assert chat_id == "15551234567"
        assert is_explicit is True

    def test_signal_invalid_e164_rejected(self):
        """Too-short, too-long, and non-numeric E.164 strings are not explicit."""
        assert _parse_target_ref("signal", "+123")[2] is False
        assert _parse_target_ref("signal", "+1234567890123456")[2] is False
        assert _parse_target_ref("signal", "+12abc4567890")[2] is False
        assert _parse_target_ref("signal", "+")[2] is False

    def test_e164_prefix_only_matches_phone_platforms(self):
        """'+' prefix must NOT be treated as explicit for non-phone platforms."""
        assert _parse_target_ref("telegram", "+15551234567")[2] is False
        assert _parse_target_ref("matrix", "+15551234567")[2] is False
        assert _parse_target_ref("matrix", "+15551234567")[2] is False


class TestParseTargetRefSlack:
    """_parse_target_ref recognizes Slack channel/user IDs as explicit."""

    def test_public_channel_id_is_explicit(self):
        chat_id, thread_id, is_explicit = _parse_target_ref("slack", "C0B0QV5434G")
        assert chat_id == "C0B0QV5434G"
        assert thread_id is None
        assert is_explicit is True

    def test_private_channel_id_is_explicit(self):
        assert _parse_target_ref("slack", "G123ABCDEF")[2] is True

    def test_dm_id_is_explicit(self):
        assert _parse_target_ref("slack", "D123ABCDEF")[2] is True

    def test_user_id_is_not_explicit(self):
        """Slack user IDs (U...) and workspace IDs (W...) are NOT explicit send
        targets. chat.postMessage rejects them — a DM must be opened first via
        conversations.open to obtain a D... conversation ID.
        """
        assert _parse_target_ref("slack", "U123ABCDEF")[2] is False
        assert _parse_target_ref("slack", "W123ABCDEF")[2] is False

    def test_whitespace_is_stripped(self):
        chat_id, _, is_explicit = _parse_target_ref("slack", "  C0B0QV5434G  ")
        assert chat_id == "C0B0QV5434G"
        assert is_explicit is True

    def test_lowercase_or_short_id_is_not_explicit(self):
        assert _parse_target_ref("slack", "c0b0qv5434g")[2] is False
        assert _parse_target_ref("slack", "C123")[2] is False
        assert _parse_target_ref("slack", "X0B0QV5434G")[2] is False

    def test_slack_id_not_explicit_for_other_platforms(self):
        assert _parse_target_ref("telegram", "C0B0QV5434G")[2] is False
        assert _parse_target_ref("telegram", "C0B0QV5434G")[2] is False


class TestSendMatrixUrlEncoding:
    """_send_matrix URL-encodes Matrix room IDs in the API path."""

    def test_room_id_is_percent_encoded_in_url(self):
        """Matrix room IDs with ! and : are percent-encoded in the PUT URL."""
        import aiohttp

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"event_id": "$evt123"})
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.put = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            from tools.send_message_tool import _send_matrix
            result = asyncio.get_event_loop().run_until_complete(
                _send_matrix(
                    "test_token",
                    {"homeserver": "https://matrix.example.org"},
                    "!HLOQwxYGgFPMPJUSNR:matrix.org",
                    "hello",
                )
            )

        assert result["success"] is True
        # Verify the URL was called with percent-encoded room ID
        put_url = mock_session.put.call_args[0][0]
        assert "%21HLOQwxYGgFPMPJUSNR%3Amatrix.org" in put_url
        assert "!HLOQwxYGgFPMPJUSNR:matrix.org" not in put_url


# ---------------------------------------------------------------------------
# Tests for _derive_forum_thread_name
# ---------------------------------------------------------------------------


class _FakeSignalHttp:
    """Stand-in for httpx.AsyncClient used as an async context manager.

    Pops a response from the queue per `post` call. Each entry is either
    a dict (returned from .json()) or an exception instance (raised).
    Captures (url, payload) per call.
    """

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, *_a, **_kw):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False

    async def post(self, url, json=None):
        self.calls.append({"url": url, "payload": json})
        if not self.responses:
            raise AssertionError("Unexpected extra POST")
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        resp = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda data=item: data,
        )
        return resp


def _install_signal_http(monkeypatch, fake):
    """Patch httpx.AsyncClient at the module level so the lazy import in
    _send_signal picks it up.
    """
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", fake)


def _patch_sendmsg_sleep_and_time(monkeypatch, capture: list):
    """Mock asyncio.sleep + time.monotonic in the signal_rate_limit
    module so the scheduler's acquire loop sees synthetic time advancing
    during sleep calls, and report_rpc_duration sees the same clock.

    Zero-second sleeps (event-loop yields from fake HTTP posts) are
    delegated to the real asyncio.sleep so they don't pollute the
    capture list.
    """
    import asyncio as _aio
    _real_sleep = _aio.sleep
    offset = [0.0]

    async def fake_sleep(seconds):
        if seconds > 0:
            capture.append(seconds)
            offset[0] += seconds
        else:
            await _real_sleep(0)

    monkeypatch.setattr(
        "gateway.platforms.signal_rate_limit.asyncio.sleep", fake_sleep
    )
    monkeypatch.setattr(
        "gateway.platforms.signal_rate_limit.time.monotonic", lambda: offset[0]
    )


class TestSendSignalChunking:
    def test_text_only_single_rpc(self, monkeypatch):
        fake = _FakeSignalHttp([{"result": {"timestamp": 1}}])
        _install_signal_http(monkeypatch, fake)

        result = asyncio.run(
            _send_signal(
                {"http_url": "http://localhost:8080", "account": "+15551234567"},
                "+15557654321",
                "hello",
            )
        )

        assert result == {"success": True, "platform": "signal", "chat_id": "+15557654321"}
        assert len(fake.calls) == 1
        params = fake.calls[0]["payload"]["params"]
        assert params["message"] == "hello"
        assert "attachments" not in params

    def test_chunks_attachments_above_max(self, tmp_path, monkeypatch):
        """33 attachments → 2 batches; text only on first batch. Batch 1
        only needs 1 token and 18 remain after batch 0, so no sleep."""
        from gateway.platforms.signal_rate_limit import (
            SIGNAL_MAX_ATTACHMENTS_PER_MSG,
        )

        paths = []
        for i in range(33):
            p = tmp_path / f"img_{i}.png"
            p.write_bytes(b"\x89PNG" + b"\x00" * 16)
            paths.append((str(p), False))

        fake = _FakeSignalHttp([
            {"result": {"timestamp": 1}},   # batch 0
            {"result": {"timestamp": 2}},   # batch 1
        ])
        _install_signal_http(monkeypatch, fake)

        sleep_calls = []
        _patch_sendmsg_sleep_and_time(monkeypatch, sleep_calls)

        result = asyncio.run(
            _send_signal(
                {"http_url": "http://localhost:8080", "account": "+15551234567"},
                "+15557654321",
                "Caption goes here",
                media_files=paths,
            )
        )

        assert result["success"] is True
        assert len(fake.calls) == 2
        assert len(sleep_calls) == 0

        first = fake.calls[0]["payload"]["params"]
        assert first["message"] == "Caption goes here"
        assert len(first["attachments"]) == SIGNAL_MAX_ATTACHMENTS_PER_MSG

        second = fake.calls[1]["payload"]["params"]
        assert second["message"] == ""  # caption only on batch 0
        assert len(second["attachments"]) == 33 - SIGNAL_MAX_ATTACHMENTS_PER_MSG

    def test_full_followup_batch_emits_pacing_notice(self, tmp_path, monkeypatch):
        """64 attachments → 2 full batches. Batch 1 needs 14 more tokens
        than the 18 remaining after batch 0 — 56s wait crossing the 10s
        notice threshold."""
        from gateway.platforms.signal_rate_limit import (
            SIGNAL_MAX_ATTACHMENTS_PER_MSG,
            SIGNAL_RATE_LIMIT_BUCKET_CAPACITY,
            SIGNAL_RATE_LIMIT_DEFAULT_RETRY_AFTER,
        )

        paths = []
        for i in range(64):
            p = tmp_path / f"img_{i}.png"
            p.write_bytes(b"\x89PNG" + b"\x00" * 16)
            paths.append((str(p), False))

        fake = _FakeSignalHttp([
            {"result": {"timestamp": 1}},   # batch 0
            {"result": {"timestamp": 99}},  # pacing notice
            {"result": {"timestamp": 2}},   # batch 1
        ])
        _install_signal_http(monkeypatch, fake)

        sleep_calls = []
        _patch_sendmsg_sleep_and_time(monkeypatch, sleep_calls)

        result = asyncio.run(
            _send_signal(
                {"http_url": "http://localhost:8080", "account": "+15551234567"},
                "+15557654321",
                "",
                media_files=paths,
            )
        )

        assert result["success"] is True
        assert len(fake.calls) == 3
        notice = fake.calls[1]["payload"]["params"]
        assert "More images coming" in notice["message"]
        assert "attachments" not in notice
        # Batch 1 deficit: 32 - (50 - 32) = 14 tokens × 4s = 56s
        expected = (
            SIGNAL_MAX_ATTACHMENTS_PER_MSG
            - (SIGNAL_RATE_LIMIT_BUCKET_CAPACITY - SIGNAL_MAX_ATTACHMENTS_PER_MSG)
        ) * SIGNAL_RATE_LIMIT_DEFAULT_RETRY_AFTER
        assert sleep_calls == [pytest.approx(expected, abs=1.0)]

    def test_429_with_retry_after_drives_exact_backoff(self, tmp_path, monkeypatch):
        """signal-cli ≥ v0.14.3 surfaces Retry-After under
        error.data.response.results[*].retryAfterSeconds. The scheduler
        calibrates its refill rate from that value; the retry of n=1
        sleeps the per-token interval."""
        from gateway.platforms.signal_rate_limit import SIGNAL_RPC_ERROR_RATELIMIT

        p = tmp_path / "img.png"
        p.write_bytes(b"\x89PNG" + b"\x00" * 16)

        fake = _FakeSignalHttp([
            {
                "error": {
                    "code": SIGNAL_RPC_ERROR_RATELIMIT,
                    "message": "Failed to send message due to rate limiting",
                    "data": {
                        "response": {
                            "timestamp": 0,
                            "results": [
                                {"type": "RATE_LIMIT_FAILURE", "retryAfterSeconds": 42},
                            ],
                        }
                    },
                }
            },
            {"result": {"timestamp": 7}},
        ])
        _install_signal_http(monkeypatch, fake)

        sleep_calls = []
        _patch_sendmsg_sleep_and_time(monkeypatch, sleep_calls)

        result = asyncio.run(
            _send_signal(
                {"http_url": "http://localhost:8080", "account": "+15551234567"},
                "+15557654321",
                "",
                media_files=[(str(p), False)],
            )
        )

        assert result["success"] is True
        assert len(fake.calls) == 2  # initial + retry
        assert sleep_calls == [pytest.approx(42.0, abs=1.0)]

    def test_429_without_retry_after_falls_back_to_default(self, tmp_path, monkeypatch):
        """Older signal-cli (< v0.14.3) doesn't surface Retry-After.
        The scheduler keeps its default rate (1 token / 4s)."""
        from gateway.platforms.signal_rate_limit import SIGNAL_RATE_LIMIT_DEFAULT_RETRY_AFTER

        p = tmp_path / "img.png"
        p.write_bytes(b"\x89PNG" + b"\x00" * 16)

        fake = _FakeSignalHttp([
            {"error": {"message": "Failed: [429] Rate Limited"}},
            {"result": {"timestamp": 7}},
        ])
        _install_signal_http(monkeypatch, fake)

        sleep_calls = []
        _patch_sendmsg_sleep_and_time(monkeypatch, sleep_calls)

        result = asyncio.run(
            _send_signal(
                {"http_url": "http://localhost:8080", "account": "+15551234567"},
                "+15557654321",
                "",
                media_files=[(str(p), False)],
            )
        )

        assert result["success"] is True
        assert sleep_calls == [pytest.approx(SIGNAL_RATE_LIMIT_DEFAULT_RETRY_AFTER, abs=1.0)]

    def test_429_retry_exhaust_continues_to_next_batch(self, tmp_path, monkeypatch):
        """Both attempts on batch 0 fail; batch 1 still gets a chance.
        The scheduler's natural pacing (no more cooldown gate) lets the
        second batch through after its acquire wait."""
        from gateway.platforms.signal_rate_limit import SIGNAL_RPC_ERROR_RATELIMIT

        paths = []
        for i in range(33):  # forces 2 batches
            p = tmp_path / f"img_{i}.png"
            p.write_bytes(b"\x89PNG" + b"\x00" * 16)
            paths.append((str(p), False))

        rate_limit_err = {
            "error": {
                "code": SIGNAL_RPC_ERROR_RATELIMIT,
                "message": "Failed to send message due to rate limiting",
                "data": {
                    "response": {
                        "timestamp": 0,
                        "results": [
                            {"type": "RATE_LIMIT_FAILURE", "retryAfterSeconds": 4},
                        ],
                    }
                },
            }
        }

        fake = _FakeSignalHttp([
            rate_limit_err,                  # batch 0, attempt 1
            rate_limit_err,                  # batch 0, attempt 2 (exhaust)
            {"result": {"timestamp": 9}},    # batch 1 succeeds
        ])
        _install_signal_http(monkeypatch, fake)

        sleep_calls = []
        _patch_sendmsg_sleep_and_time(monkeypatch, sleep_calls)

        result = asyncio.run(
            _send_signal(
                {"http_url": "http://localhost:8080", "account": "+15551234567"},
                "+15557654321",
                "many",
                media_files=paths,
            )
        )

        # Partial success: batch 0 lost but batch 1 went through.
        assert result["success"] is True
        assert "warnings" in result
        assert any("rate-limited" in w for w in result["warnings"])
        # 2 attempts on batch 0 + 1 successful batch 1 = 3 calls
        assert len(fake.calls) == 3

    def test_non_rate_limit_error_returns_immediately(self, tmp_path, monkeypatch):
        """A non-429 RPC error should not retry — it returns an error result."""
        p = tmp_path / "img.png"
        p.write_bytes(b"\x89PNG" + b"\x00" * 16)

        fake = _FakeSignalHttp([
            {"error": {"message": "UntrustedIdentityException"}},
        ])
        _install_signal_http(monkeypatch, fake)

        result = asyncio.run(
            _send_signal(
                {"http_url": "http://localhost:8080", "account": "+15551234567"},
                "+15557654321",
                "",
                media_files=[(str(p), False)],
            )
        )

        assert "error" in result
        assert "UntrustedIdentityException" in result["error"]
        assert len(fake.calls) == 1  # no retry on non-429

    def test_skipped_missing_files_reported_in_warnings(self, tmp_path, monkeypatch):
        good = tmp_path / "ok.png"
        good.write_bytes(b"\x89PNG" + b"\x00" * 16)

        fake = _FakeSignalHttp([{"result": {"timestamp": 1}}])
        _install_signal_http(monkeypatch, fake)

        result = asyncio.run(
            _send_signal(
                {"http_url": "http://localhost:8080", "account": "+15551234567"},
                "+15557654321",
                "msg",
                media_files=[(str(good), False), (str(tmp_path / "missing.png"), False)],
            )
        )

        assert result["success"] is True
        assert "warnings" in result
        # Only the existing file made it into the RPC
        params = fake.calls[0]["payload"]["params"]
        assert len(params["attachments"]) == 1
