"""
Verify that every retained gateway platform has a connection
checker so ``GatewayConfig.get_connected_platforms()`` doesn't silently drop
platforms with bespoke auth requirements.
"""

from unittest.mock import MagicMock

import pytest

from gateway.config import Platform, _PLATFORM_CONNECTED_CHECKERS, _BUILTIN_PLATFORM_VALUES


def test_all_builtins_have_checker_or_generic_token_path():
    """Every built-in Platform member must be reachable by either:

    1. The generic ``config.token or config.api_key`` check, OR
    2. A platform-specific entry in ``_PLATFORM_CONNECTED_CHECKERS``.

    This guarantees ``get_connected_platforms()`` doesn't silently ignore
    a built-in just because nobody added it to the checker dict.
    """
    generic_token_values = {Platform.TELEGRAM.value}
    compatibility_only_values = {
        Platform.DISCORD.value,
        Platform.FEISHU.value,
        Platform.WECOM.value,
        Platform.WECOM_CALLBACK.value,
        Platform.SLACK.value,
        Platform.SIGNAL.value,
        Platform.MATTERMOST.value,
        Platform.MATRIX.value,
        Platform.HOMEASSISTANT.value,
        Platform.SMS.value,
        Platform.API_SERVER.value,
        Platform.WEBHOOK.value,
        Platform.BLUEBUBBLES.value,
        Platform.YUANBAO.value,
    }

    # Platforms with a bespoke checker
    checker_values = {p.value for p in set(_PLATFORM_CONNECTED_CHECKERS.keys())}

    # Every built-in should be in one of the two sets
    all_builtins = set(_BUILTIN_PLATFORM_VALUES)
    missing = (
        all_builtins
        - generic_token_values
        - checker_values
        - compatibility_only_values
        - {"local"}
    )

    assert not missing, (
        f"Built-in platforms missing a connection checker: "
        f"{sorted(missing)}.  "
        f"Add them to _PLATFORM_CONNECTED_CHECKERS or generic_token_platforms."
    )


@pytest.mark.parametrize("platform, checker", list(_PLATFORM_CONNECTED_CHECKERS.items()))
def test_checker_handles_minimal_config(platform, checker):
    """Each bespoke checker must not crash on a minimal PlatformConfig."""
    mock_config = MagicMock()
    mock_config.extra = {}
    mock_config.token = None
    mock_config.api_key = None
    mock_config.enabled = True

    # Should return a bool without raising
    result = checker(mock_config)
    assert isinstance(result, bool)


@pytest.mark.parametrize("platform, checker", list(_PLATFORM_CONNECTED_CHECKERS.items()))
def test_checker_returns_true_when_configured(platform, checker, monkeypatch):
    """Each bespoke checker must return True when the config looks valid."""
    mock_config = MagicMock()
    mock_config.token = None
    mock_config.api_key = None
    mock_config.enabled = True

    # Set up platform-specific mock extra fields so the checker succeeds
    if platform == Platform.WEIXIN:
        mock_config.extra = {"account_id": "123", "token": "***"}
    elif platform == Platform.EMAIL:
        mock_config.extra = {"address": "hermes@example.com"}
    elif platform == Platform.WHATSAPP:
        mock_config.extra = {}
    elif platform == Platform.QQBOT:
        mock_config.extra = {"app_id": "app", "client_secret": "sec"}
    elif platform == Platform.DINGTALK:
        mock_config.extra = {"client_id": "id", "client_secret": "sec"}
    else:
        pytest.skip(f"No synthetic config defined for {platform.value}")

    result = checker(mock_config)
    assert result is True, f"{platform.value} checker should return True with valid-looking config"
