import json

import pytest

from gateway.delivery_contract import (
    CONTRACT_VERSION,
    unsupported_delivery_reason,
    validate_new_delivery,
)
from tools.send_message_tool import send_message_tool


@pytest.mark.parametrize(
    ("profile", "allowed", "blocked"),
    [
        ("mainland_cn", ("desktop", "weixin:wxid", "qqbot:group", "dingtalk:cid"), "feishu:oc_old"),
        ("sea", ("desktop", "telegram:1", "whatsapp:2", "email:a@example.com"), "discord:3"),
    ],
)
def test_profile_delivery_contract_is_exact(monkeypatch, profile, allowed, blocked):
    monkeypatch.setenv("KABUQINA_PRODUCT_PROFILE", profile)
    for target in allowed:
        validate_new_delivery(target)
    with pytest.raises(ValueError, match="unsupported_delivery") as exc:
        validate_new_delivery(blocked)
    assert CONTRACT_VERSION in str(exc.value)


def test_unknown_profile_fails_closed(monkeypatch):
    monkeypatch.setenv("KABUQINA_PRODUCT_PROFILE", "antarctica")
    assert "unknown product profile" in unsupported_delivery_reason("telegram:1")


def test_send_rejects_before_gateway_config_import(monkeypatch):
    monkeypatch.setenv("KABUQINA_PRODUCT_PROFILE", "mainland_cn")
    result = json.loads(send_message_tool({
        "action": "send",
        "target": "discord:123",
        "message": "must not send",
    }))
    assert "unsupported_delivery" in result["error"]
    assert CONTRACT_VERSION in result["error"]


def test_standalone_core_without_desktop_profile_keeps_legacy_scope(monkeypatch):
    monkeypatch.delenv("KABUQINA_PRODUCT_PROFILE", raising=False)
    assert unsupported_delivery_reason("discord:123") is None
