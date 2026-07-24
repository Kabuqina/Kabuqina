"""Parity tests: channel-related env keys used by Kabuqina Settings reach load_gateway_config()."""

from __future__ import annotations

import pytest

from gateway.config import Platform, load_gateway_config


@pytest.fixture
def hermes_home(tmp_path, monkeypatch):
    monkeypatch.setenv("KABUQINA_HOME", str(tmp_path))
    # Minimal layout some code paths may expect.
    (tmp_path / "sessions").mkdir(parents=True)


def test_qq_home_channel_from_env(hermes_home, monkeypatch):
    monkeypatch.setenv("QQ_APP_ID", "qid")
    monkeypatch.setenv("QQ_CLIENT_SECRET", "qsec")
    monkeypatch.setenv("QQBOT_HOME_CHANNEL", "open_123")
    monkeypatch.setenv("QQBOT_HOME_CHANNEL_NAME", "My Home")

    cfg = load_gateway_config()
    q = cfg.platforms.get(Platform.QQBOT)
    assert q is not None
    assert q.home_channel is not None
    assert q.home_channel.chat_id == "open_123"
    assert q.home_channel.name == "My Home"


def test_qq_group_policy_and_allowlist_from_env(hermes_home, monkeypatch):
    monkeypatch.setenv("QQ_APP_ID", "qid")
    monkeypatch.setenv("QQ_CLIENT_SECRET", "qsec")
    monkeypatch.setenv("QQ_GROUP_POLICY", "allowlist")
    monkeypatch.setenv("QQ_GROUP_ALLOWED_USERS", "grp_a,grp_b")

    cfg = load_gateway_config()
    q = cfg.platforms.get(Platform.QQBOT)
    assert q is not None
    assert q.extra.get("group_policy") == "allowlist"
    assert q.extra.get("group_allow_from") == "grp_a,grp_b"


def test_qq_advanced_flags_from_env(hermes_home, monkeypatch):
    monkeypatch.setenv("QQ_APP_ID", "qid")
    monkeypatch.setenv("QQ_CLIENT_SECRET", "qsec")
    monkeypatch.setenv("QQ_MARKDOWN_SUPPORT", "false")
    monkeypatch.setenv("QQ_SANDBOX", "true")

    cfg = load_gateway_config()
    q = cfg.platforms.get(Platform.QQBOT)
    assert q is not None
    assert q.extra.get("markdown_support") is False
    assert q.extra.get("sandbox") is True
