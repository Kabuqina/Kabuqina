"""
Shared platform registry for Kabuqina.

Single source of truth for platform metadata consumed by both
skills_config (label display) and tools_config (default toolset
resolution).  Import ``PLATFORMS`` from here instead of maintaining
duplicate dicts in each module.
"""

from collections import OrderedDict
from typing import NamedTuple


class PlatformInfo(NamedTuple):
    """Metadata for a single platform entry."""
    label: str
    default_toolset: str


# Ordered so that TUI menus are deterministic.
PLATFORMS: OrderedDict[str, PlatformInfo] = OrderedDict([
    ("cli",            PlatformInfo(label="🖥️  CLI",            default_toolset="kabuqina-cli")),
    ("telegram",       PlatformInfo(label="📱 Telegram",        default_toolset="kabuqina-telegram")),
    ("whatsapp",       PlatformInfo(label="📱 WhatsApp",        default_toolset="kabuqina-whatsapp")),
    ("email",          PlatformInfo(label="📧 Email",           default_toolset="kabuqina-email")),
    ("dingtalk",       PlatformInfo(label="💬 DingTalk",        default_toolset="kabuqina-dingtalk")),
    ("weixin",         PlatformInfo(label="💬 Weixin",          default_toolset="kabuqina-weixin")),
    ("qqbot",          PlatformInfo(label="💬 QQBot",           default_toolset="kabuqina-qqbot")),
    ("cron",           PlatformInfo(label="⏰ Cron",            default_toolset="kabuqina-cron")),
])


def platform_label(key: str, default: str = "") -> str:
    """Return the display label for a platform key, or *default*.

    Platform metadata is a fixed product registry.
    """
    info = PLATFORMS.get(key)
    if info is not None:
        return info.label
    return default


def get_all_platforms() -> "OrderedDict[str, PlatformInfo]":
    """Return a copy of the fixed product platform registry."""
    return OrderedDict(PLATFORMS)
