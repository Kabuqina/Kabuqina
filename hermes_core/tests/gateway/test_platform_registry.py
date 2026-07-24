"""Negative contracts for the fixed product platform registry."""

from unittest.mock import MagicMock

import pytest

from gateway.config import GatewayConfig, Platform
from gateway.platform_registry import PlatformEntry, PlatformRegistry


def _entry(name: str, *, source: str = "plugin") -> PlatformEntry:
    return PlatformEntry(
        name=name,
        label=name.title(),
        adapter_factory=lambda _cfg: MagicMock(),
        check_fn=lambda: True,
        source=source,
    )


def test_unknown_platform_enum_is_rejected():
    with pytest.raises(ValueError):
        Platform("third-party-chat")


def test_platform_registry_rejects_plugin_entries():
    registry = PlatformRegistry()
    with pytest.raises(ValueError, match="platform plugins are not supported"):
        registry.register(_entry("irc"))
    assert registry.all_entries() == []


def test_product_entry_cannot_be_overridden():
    registry = PlatformRegistry()
    registry.register(_entry("telegram", source="builtin"))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(_entry("telegram", source="builtin"))


def test_gateway_config_ignores_unknown_plugin_platform():
    config = GatewayConfig.from_dict(
        {
            "platforms": {
                "telegram": {"enabled": True, "token": "test-token"},
                "third-party-chat": {"enabled": True, "token": "plugin-token"},
            }
        }
    )
    assert Platform.TELEGRAM in config.platforms
    assert all(p.value != "third-party-chat" for p in config.platforms)


@pytest.mark.parametrize(
    "removed",
    [
        "slack",
        "signal",
        "mattermost",
        "matrix",
        "homeassistant",
        "sms",
        "api_server",
        "webhook",
        "bluebubbles",
        "yuanbao",
        "irc",
        "teams",
    ],
)
def test_removed_platform_config_never_connects(removed):
    config = GatewayConfig.from_dict(
        {"platforms": {removed: {"enabled": True, "token": "still-present"}}}
    )
    assert all(p.value != removed for p in config.get_connected_platforms())
