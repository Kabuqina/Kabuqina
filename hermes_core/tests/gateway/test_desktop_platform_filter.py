import pytest

from gateway.config import (
    GatewayConfig,
    Platform,
    PlatformConfig,
    _enforce_desktop_single_platform,
)


def _config_with(*platforms):
    return GatewayConfig(platforms={platform: PlatformConfig(enabled=True) for platform in platforms})


def test_desktop_gateway_child_keeps_only_selected_adapter(monkeypatch):
    monkeypatch.setenv("KABUQINA_PRODUCT_PROFILE", "mainland_cn")
    monkeypatch.setenv("KABUQINA_GATEWAY_PLATFORM", "weixin")
    config = _config_with(Platform.WEIXIN, Platform.FEISHU, Platform.DISCORD)

    _enforce_desktop_single_platform(config)

    assert list(config.platforms) == [Platform.WEIXIN]


def test_desktop_gateway_child_rejects_wrong_profile_platform(monkeypatch):
    monkeypatch.setenv("KABUQINA_PRODUCT_PROFILE", "mainland_cn")
    monkeypatch.setenv("KABUQINA_GATEWAY_PLATFORM", "telegram")
    with pytest.raises(RuntimeError, match="platform_unavailable"):
        _enforce_desktop_single_platform(_config_with(Platform.TELEGRAM))


def test_desktop_gateway_child_rejects_missing_profile(monkeypatch):
    monkeypatch.delenv("KABUQINA_PRODUCT_PROFILE", raising=False)
    monkeypatch.delenv("HERMESDESK_PRODUCT_PROFILE", raising=False)
    monkeypatch.setenv("KABUQINA_GATEWAY_PLATFORM", "weixin")
    with pytest.raises(RuntimeError, match="unknown product profile"):
        _enforce_desktop_single_platform(_config_with(Platform.WEIXIN))


def test_standalone_gateway_without_child_identity_is_unchanged(monkeypatch):
    monkeypatch.delenv("KABUQINA_GATEWAY_PLATFORM", raising=False)
    monkeypatch.delenv("HERMESDESK_GATEWAY_PLATFORM", raising=False)
    config = _config_with(Platform.TELEGRAM, Platform.DISCORD)
    _enforce_desktop_single_platform(config)
    assert set(config.platforms) == {Platform.TELEGRAM, Platform.DISCORD}
