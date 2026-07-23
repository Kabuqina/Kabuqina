"""Fresh-install contracts for platforms removed from the gateway."""

from __future__ import annotations

import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent


def _extract_shell_function(path: Path, name: str) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(
        rf"^{re.escape(name)}\(\)\s*\{{\s*\n(?P<body>.*?)^\}}",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"{name}() not found in {path.name}"
    return match["body"]


def _extract_powershell_function(path: Path, name: str) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(
        rf"^function\s+{re.escape(name)}\s*\{{\s*\n(?P<body>.*?)^\}}",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"{name} not found in {path.name}"
    return match["body"]


def test_fresh_install_template_has_no_removed_platform_state() -> None:
    template_path = REPO_ROOT / "cli-config.yaml.example"
    text = template_path.read_text(encoding="utf-8")
    config = yaml.safe_load(text)

    assert "discord" not in (config.get("platform_toolsets") or {})
    assert "kabuqina-discord" not in text.casefold()


def test_active_readme_does_not_advertise_removed_platform() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "discord" not in readme.casefold()


def test_windows_gateway_start_ignores_removed_token() -> None:
    body = _extract_powershell_function(
        REPO_ROOT / "scripts" / "install.ps1",
        "Start-GatewayIfConfigured",
    )

    assert "DISCORD_BOT_TOKEN" not in body
    assert "TELEGRAM_BOT_TOKEN" in body


def test_posix_gateway_start_ignores_removed_token() -> None:
    body = _extract_shell_function(
        REPO_ROOT / "scripts" / "install.sh",
        "maybe_start_gateway",
    )

    assert "DISCORD_BOT_TOKEN" not in body
    assert "TELEGRAM_BOT_TOKEN" in body
