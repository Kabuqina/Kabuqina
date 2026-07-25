#!/usr/bin/env python3
"""Fail when active platform documentation advertises removed surfaces."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = (
    ROOT
    / "docs"
    / "superpowers"
    / "progress"
    / "2026-07-18-v0.5.0-c0-platform-surface-manifest.json"
)
MESSAGING_DOCS = (
    ROOT / "hermes_core" / "website" / "docs" / "user-guide" / "messaging"
)


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def audit() -> list[str]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    retained = set(manifest["platform_sets"]["retained_external"])
    removed = set(manifest["platform_sets"]["removed_builtin"])
    removed_plugins = set(manifest["platform_sets"]["removed_bundled_plugins"])
    errors: list[str] = []

    expected_pages = {f"{name}.md" for name in retained} | {
        "index.md",
        "_category_.json",
    }
    actual_pages = {path.name for path in MESSAGING_DOCS.iterdir() if path.is_file()}
    if actual_pages != expected_pages:
        errors.append(
            "messaging documentation set drift: "
            f"missing={sorted(expected_pages - actual_pages)} "
            f"extra={sorted(actual_pages - expected_pages)}"
        )

    index = (MESSAGING_DOCS / "index.md").read_text(encoding="utf-8")
    linked = set(re.findall(r"\]\(([a-z0-9_]+)\.md\)", index))
    if linked != retained:
        errors.append(
            "messaging index platform links drift: "
            f"expected={sorted(retained)} actual={sorted(linked)}"
        )

    removed_prefixes = sorted(
        {
            "DISCORD",
            "SLACK",
            "SIGNAL",
            "SMS",
            "BLUEBUBBLES",
            "MATTERMOST",
            "MATRIX",
            "HASS",
            "WEBHOOK",
            "API_SERVER",
            "FEISHU",
            "LARK",
            "WECOM",
            "YUANBAO",
            "TEAMS",
            "IRC",
        }
    )
    env_reference = _read(
        "hermes_core/website/docs/reference/environment-variables.md"
    )
    for prefix in removed_prefixes:
        if re.search(rf"\|\s*`{re.escape(prefix)}_[A-Z0-9_]+`", env_reference):
            errors.append(f"active environment reference advertises {prefix}_*")

    removed_names = removed | removed_plugins
    toolsets = _read("hermes_core/website/docs/reference/toolsets-reference.md")
    for name in sorted(removed_names):
        patterns = (
            rf"\|\s*`{re.escape(name)}`\s*\|",
            rf"`(?:hermes|kabuqina)-{re.escape(name)}`",
        )
        if any(re.search(pattern, toolsets, re.IGNORECASE) for pattern in patterns):
            errors.append(f"active toolset reference advertises {name}")

    cron = _read("hermes_core/website/docs/user-guide/features/cron.md")
    for name in sorted(removed_names):
        if re.search(rf'\|\s*`"{re.escape(name)}(?::[^"]*)?"`', cron):
            errors.append(f"active cron reference advertises delivery target {name}")

    cli = _read("hermes_core/website/docs/reference/cli-commands.md")
    for command in ("slack", "webhook"):
        if re.search(rf"`hermes {command}(?:\s|`)", cli, re.IGNORECASE):
            errors.append(f"active CLI reference advertises hermes {command}")

    active_product_docs = (
        "hermes_core/README.md",
        "hermes_core/website/docs/user-guide/profiles.md",
        "hermes_core/website/docs/user-guide/features/tools.md",
        "docs/safety.md",
        "docs/test-plan.md",
        "docs/test-cases/gateway-messaging.md",
    )
    display_names = (
        "Discord",
        "Slack",
        "Signal",
        "Matrix",
        "Mattermost",
        "Feishu",
        "Lark",
        "WeCom",
        "BlueBubbles",
        "Yuanbao",
        "Home Assistant",
    )
    for relative in active_product_docs:
        text = _read(relative)
        for display_name in display_names:
            if re.search(rf"\b{re.escape(display_name)}\b", text):
                errors.append(
                    f"active product doc advertises removed platform: "
                    f"{relative}: {display_name}"
                )
    return errors


def main() -> int:
    errors = audit()
    if errors:
        print(f"active platform documentation audit FAILED ({len(errors)} issue(s))")
        for error in errors:
            print(f"- {error}")
        return 1
    print("active platform documentation audit passed: retained=6 removed_advertisements=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
