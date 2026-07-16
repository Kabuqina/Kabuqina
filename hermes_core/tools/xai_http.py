"""Shared helpers for direct xAI HTTP integrations."""

from __future__ import annotations


def kabuqina_xai_user_agent() -> str:
    """Return a stable Kabuqina-specific User-Agent for xAI HTTP calls."""
    try:
        from kabuqina_cli import __version__
    except Exception:
        __version__ = "unknown"
    return f"Kabuqina-Agent/{__version__}"


# One-release import compatibility.
hermes_xai_user_agent = kabuqina_xai_user_agent
