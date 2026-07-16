"""Shared comprehensive python-telegram-bot stub for gateway/e2e tests.

The object is completed in place and then kept stable.  Pytest may load the
gateway and e2e conftests in either order, while the production adapter keeps
objects imported from ``telegram.constants`` at module import time.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


def _is_real_module(module: object | None) -> bool:
    return isinstance(getattr(module, "__file__", None), (str, bytes, Path))


def ensure_comprehensive_telegram_stub() -> None:
    existing = sys.modules.get("telegram")
    if _is_real_module(existing):
        return
    if existing is not None and vars(existing).get("_kabuqina_complete_stub") is True:
        return

    telegram_mod = existing if existing is not None else MagicMock()

    parse_mode = SimpleNamespace(
        MARKDOWN="Markdown",
        MARKDOWN_V2="MarkdownV2",
        HTML="HTML",
    )
    chat_type = SimpleNamespace(
        PRIVATE="private",
        GROUP="group",
        SUPERGROUP="supergroup",
        CHANNEL="channel",
    )

    # ``telegram.constants`` is intentionally the same object as the package,
    # so set both the root exports and the conventional ``constants`` view to
    # the exact same identity.
    telegram_mod.ParseMode = parse_mode
    telegram_mod.ChatType = chat_type
    telegram_mod.constants = SimpleNamespace(ParseMode=parse_mode, ChatType=chat_type)

    class _FakeInlineKeyboardButton:
        def __init__(self, text, callback_data=None, **kwargs):
            self.text = text
            self.callback_data = callback_data
            for key, value in kwargs.items():
                setattr(self, key, value)

    class _FakeInlineKeyboardMarkup:
        def __init__(self, inline_keyboard, **kwargs):
            self.inline_keyboard = inline_keyboard
            for key, value in kwargs.items():
                setattr(self, key, value)

    class _FakeLinkPreviewOptions:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class _FakeHandler:
        """Accept PTB handler arguments without treating arg 0 as a mock spec."""

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.callback = args[-1] if args else kwargs.get("callback")

    telegram_mod.Update = MagicMock
    telegram_mod.Update.ALL_TYPES = []
    telegram_mod.Bot = MagicMock
    telegram_mod.Message = MagicMock
    telegram_mod.InlineKeyboardButton = _FakeInlineKeyboardButton
    telegram_mod.InlineKeyboardMarkup = _FakeInlineKeyboardMarkup
    telegram_mod.LinkPreviewOptions = _FakeLinkPreviewOptions
    telegram_mod.BotCommand = MagicMock
    telegram_mod.InputMediaPhoto = MagicMock

    telegram_mod.Application = MagicMock
    telegram_mod.Application.builder = MagicMock
    telegram_mod.CommandHandler = _FakeHandler
    telegram_mod.CallbackQueryHandler = _FakeHandler
    telegram_mod.MessageHandler = _FakeHandler
    telegram_mod.ContextTypes = SimpleNamespace(DEFAULT_TYPE=type(None))
    telegram_mod.filters = MagicMock()
    telegram_mod.HTTPXRequest = MagicMock

    errors = SimpleNamespace(
        NetworkError=type("NetworkError", (OSError,), {}),
        TimedOut=type("TimedOut", (OSError,), {}),
        BadRequest=type("BadRequest", (Exception,), {}),
        Forbidden=type("Forbidden", (Exception,), {}),
        InvalidToken=type("InvalidToken", (Exception,), {}),
        RetryAfter=type("RetryAfter", (Exception,), {"retry_after": 1}),
        Conflict=type("Conflict", (Exception,), {}),
    )
    telegram_mod.error = errors
    telegram_mod.ext = telegram_mod
    telegram_mod.request = telegram_mod

    for name in (
        "telegram",
        "telegram.constants",
        "telegram.ext",
        "telegram.request",
    ):
        sys.modules[name] = telegram_mod
    sys.modules["telegram.ext.filters"] = telegram_mod.filters
    sys.modules["telegram.error"] = errors
    telegram_mod._kabuqina_complete_stub = True
