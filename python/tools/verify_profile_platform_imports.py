"""Verify retained platform imports do not pull removed adapters into runtime."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

from verify_runtime_imports import _add_runtime_paths, _seed_import_environment

PROFILE_IMPORTS = {
    "mainland_cn": (
        "gateway.platforms.weixin",
        "gateway.platforms.qqbot.adapter",
        "gateway.platforms.dingtalk",
    ),
    "sea": (
        "gateway.platforms.telegram",
        "gateway.platforms.whatsapp",
        "gateway.platforms.email",
    ),
}

REMOVED_MODULES = frozenset({
    "feishu", "wecom", "wecom_callback", "discord", "slack", "signal",
    "matrix", "mattermost", "sms", "bluebubbles", "homeassistant",
    "yuanbao", "webhook", "api_server",
})


def _verify_desktop_child_filter() -> None:
    from gateway.config import (
        GatewayConfig,
        Platform,
        PlatformConfig,
        _enforce_desktop_single_platform,
    )

    keys = (
        "KABUQINA_PRODUCT_PROFILE",
        "HERMESDESK_PRODUCT_PROFILE",
        "KABUQINA_GATEWAY_PLATFORM",
        "HERMESDESK_GATEWAY_PLATFORM",
    )
    previous = {key: os.environ.get(key) for key in keys}
    try:
        os.environ["KABUQINA_PRODUCT_PROFILE"] = "mainland_cn"
        os.environ["KABUQINA_GATEWAY_PLATFORM"] = "weixin"
        os.environ.pop("HERMESDESK_PRODUCT_PROFILE", None)
        os.environ.pop("HERMESDESK_GATEWAY_PLATFORM", None)
        config = GatewayConfig(platforms={
            Platform.WEIXIN: PlatformConfig(enabled=True),
            Platform.FEISHU: PlatformConfig(enabled=True),
            Platform.DISCORD: PlatformConfig(enabled=True),
            Platform.WECOM: PlatformConfig(enabled=True),
            Platform.WECOM_CALLBACK: PlatformConfig(enabled=True),
        })
        _enforce_desktop_single_platform(config)
        if list(config.platforms) != [Platform.WEIXIN]:
            raise RuntimeError(f"desktop child filter kept unexpected adapters: {list(config.platforms)}")
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: verify_profile_platform_imports.py <runtime-root>", file=sys.stderr)
        return 2
    root = Path(argv[1]).resolve()
    if not root.is_dir():
        print(f"runtime root not found: {root}", file=sys.stderr)
        return 2
    _add_runtime_paths(root)
    _seed_import_environment(root)
    try:
        for modules in PROFILE_IMPORTS.values():
            for module in modules:
                importlib.import_module(module)
        _verify_desktop_child_filter()
    except Exception as exc:
        print(f"retained platform import failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    imported_removed = sorted(
        name for name in sys.modules
        if any(
            name == f"gateway.platforms.{platform}"
            or name.startswith(f"gateway.platforms.{platform}.")
            for platform in REMOVED_MODULES
        )
    )
    if imported_removed:
        print("retained platforms imported removed modules: " + ", ".join(imported_removed), file=sys.stderr)
        return 1
    print("profile platform imports ok: retained imports clean; desktop child kept one profile adapter")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
