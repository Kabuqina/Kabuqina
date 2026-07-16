"""Shared comprehensive discord.py stub for gateway and e2e collection.

The helper mutates an existing partial stub in place.  That matters because a
production gateway module may already hold a reference to the object installed
by another subtree's conftest; replacing only ``sys.modules['discord']`` would
leave that captured reference incomplete.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


def _is_real_module(module: object | None) -> bool:
    return isinstance(getattr(module, "__file__", None), (str, bytes, Path))


def ensure_comprehensive_discord_stub() -> None:
    existing = sys.modules.get("discord")
    if _is_real_module(existing):
        return

    # Conftests from different test subtrees can be loaded in either order.
    # Once production code has imported this object, replacing attributes such
    # as ``Thread`` or ``File`` would split class/patch identity between the
    # captured module reference and ``sys.modules``.  Keep the first complete
    # stub stable for the lifetime of the worker.
    if existing is not None and vars(existing).get("_kabuqina_complete_stub") is True:
        return

    discord_mod = existing if existing is not None else MagicMock()
    discord_mod.Intents.default.return_value = MagicMock()
    discord_mod.Client = MagicMock
    discord_mod.File = MagicMock
    discord_mod.DMChannel = type("DMChannel", (), {})
    discord_mod.Thread = type("Thread", (), {})
    discord_mod.ForumChannel = type("ForumChannel", (), {})
    discord_mod.Interaction = object
    discord_mod.Message = type("Message", (), {})

    class _FakeAllowedMentions:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class _FakeEmbed:
        def __init__(self, *, title=None, description=None, color=None, **_):
            self.title = title
            self.description = description
            self.color = color

    class _FakeView:
        def __init__(self, timeout=None):
            self.timeout = timeout
            self.children = []

        def add_item(self, item):
            self.children.append(item)

        def clear_items(self):
            self.children.clear()

    class _FakeSelect:
        def __init__(self, *, placeholder=None, options=None, custom_id=None, **_):
            self.placeholder = placeholder
            self.options = options or []
            self.custom_id = custom_id
            self.callback = None
            self.disabled = False

    class _FakeButton:
        def __init__(self, *, label=None, style=None, custom_id=None, emoji=None,
                     url=None, disabled=False, row=None, sku_id=None, **_):
            self.label = label
            self.style = style
            self.custom_id = custom_id
            self.emoji = emoji
            self.url = url
            self.disabled = disabled
            self.row = row
            self.sku_id = sku_id
            self.callback = None

    class _FakeSelectOption:
        def __init__(self, *, label=None, value=None, description=None, **_):
            self.label = label
            self.value = value
            self.description = description

    class _FakeGroup:
        def __init__(self, *, name, description, parent=None):
            self.name = name
            self.description = description
            self.parent = parent
            self._children = {}
            if parent is not None:
                parent.add_command(self)

        def add_command(self, command):
            self._children[command.name] = command

    class _FakeCommand:
        def __init__(self, *, name, description, callback, parent=None):
            self.name = name
            self.description = description
            self.callback = callback
            self.parent = parent

    discord_mod.AllowedMentions = _FakeAllowedMentions
    discord_mod.Embed = _FakeEmbed
    discord_mod.SelectOption = _FakeSelectOption
    discord_mod.ui = SimpleNamespace(
        View=_FakeView,
        Select=_FakeSelect,
        Button=_FakeButton,
        button=lambda *args, **kwargs: (lambda fn: fn),
    )
    discord_mod.ButtonStyle = SimpleNamespace(
        success=1, primary=2, secondary=2, danger=3,
        green=1, grey=2, blurple=2, red=3,
    )
    discord_mod.Color = SimpleNamespace(
        orange=lambda: 1,
        green=lambda: 2,
        blue=lambda: 3,
        red=lambda: 4,
        purple=lambda: 5,
        greyple=lambda: 6,
    )
    discord_mod.app_commands = SimpleNamespace(
        describe=lambda **kwargs: (lambda fn: fn),
        choices=lambda **kwargs: (lambda fn: fn),
        autocomplete=lambda **kwargs: (lambda fn: fn),
        Choice=lambda **kwargs: SimpleNamespace(**kwargs),
        Group=_FakeGroup,
        Command=_FakeCommand,
    )
    discord_mod.opus = SimpleNamespace(
        is_loaded=lambda: True,
        load_opus=lambda *_args, **_kwargs: None,
    )
    discord_mod.FFmpegPCMAudio = MagicMock
    discord_mod.PCMVolumeTransformer = MagicMock
    discord_mod.http = SimpleNamespace(Route=MagicMock)

    ext_mod = MagicMock()
    commands_mod = MagicMock()
    commands_mod.Bot = MagicMock
    ext_mod.commands = commands_mod

    sys.modules["discord"] = discord_mod
    sys.modules["discord.ext"] = ext_mod
    sys.modules["discord.ext.commands"] = commands_mod
    sys.modules["discord.opus"] = discord_mod.opus
    discord_mod._kabuqina_complete_stub = True
