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

REQUIRED_RUNTIME_FILES = (
    "site-packages/aiohttp/__init__.py",
    "site-packages/certifi/__init__.py",
    "site-packages/cryptography/__init__.py",
    "site-packages/qrcode/__init__.py",
    "site-packages/telegram/__init__.py",
    "kabuqina/scripts/whatsapp-bridge/bridge.js",
    "kabuqina/scripts/whatsapp-bridge/package.json",
    "kabuqina/scripts/whatsapp-bridge/package-lock.json",
    "kabuqina/scripts/whatsapp-bridge/node_modules/@whiskeysockets/baileys/package.json",
    "kabuqina/scripts/whatsapp-bridge/node_modules/express/package.json",
    "kabuqina/scripts/whatsapp-bridge/node_modules/pino/package.json",
    "kabuqina/scripts/whatsapp-bridge/node_modules/qrcode-terminal/package.json",
)

REQUIRED_DISTRIBUTION_GLOBS = (
    "site-packages/aiohttp-*.dist-info",
    "site-packages/certifi-*.dist-info",
    "site-packages/cryptography-*.dist-info",
    "site-packages/qrcode-*.dist-info",
    "site-packages/python_telegram_bot-*.dist-info",
)


def _missing_retained_runtime_inputs(root: Path) -> list[str]:
    missing = [
        rel for rel in REQUIRED_RUNTIME_FILES
        if not (root / Path(rel)).is_file()
    ]
    missing.extend(
        pattern for pattern in REQUIRED_DISTRIBUTION_GLOBS
        if not any(root.glob(pattern))
    )
    return missing


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
    missing_inputs = _missing_retained_runtime_inputs(root)
    if missing_inputs:
        for item in missing_inputs:
            print(f"missing retained runtime input: {item}", file=sys.stderr)
        return 1
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
