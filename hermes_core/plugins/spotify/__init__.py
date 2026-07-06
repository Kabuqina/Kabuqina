"""Bundled Spotify tool plugin."""

from __future__ import annotations

from . import tools as spotify_tools


def register(ctx) -> None:
    spotify_tools.register(ctx)
