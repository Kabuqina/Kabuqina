# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Verify that v0.3.0 release runtime does not ship cut surfaces."""

from __future__ import annotations

import sys
from pathlib import Path


FORBIDDEN_RUNTIME_PATHS = (
    # v0.3.0 global-cut gateway adapters.
    "hermes/gateway/platforms/api_server.py",
    "hermes/gateway/platforms/bluebubbles.py",
    "hermes/gateway/platforms/homeassistant.py",
    "hermes/gateway/platforms/matrix.py",
    "hermes/gateway/platforms/mattermost.py",
    "hermes/gateway/platforms/signal.py",
    "hermes/gateway/platforms/signal_rate_limit.py",
    "hermes/gateway/platforms/slack.py",
    "hermes/gateway/platforms/sms.py",
    "hermes/gateway/platforms/webhook.py",
    "hermes/gateway/platforms/yuanbao.py",
    "hermes/gateway/platforms/yuanbao_media.py",
    "hermes/gateway/platforms/yuanbao_proto.py",
    "hermes/gateway/platforms/yuanbao_sticker.py",
    # v0.3.0 global-cut bundled plugins and late-discovered platform plugins.
    "hermes/plugins/disk-cleanup",
    "hermes/plugins/platforms",
    "hermes/plugins/spotify",
    # v0.3.0 global-cut or non-product skills.
    "hermes/skills/creative/popular-web-designs/templates/spotify.md",
    "hermes/skills/dogfood",
    "hermes/skills/media/spotify",
)

FORBIDDEN_RUNTIME_CONTENT = (
    ("hermes/hermes_cli/auth.py", "spotify"),
    ("hermes/toolsets.py", "spotify"),
    ("hermes/hermes_cli/tools_config.py", "spotify"),
)


def find_forbidden_runtime_paths(root: Path) -> list[str]:
    found: list[str] = []
    for rel in FORBIDDEN_RUNTIME_PATHS:
        if (root / Path(rel)).exists():
            found.append(rel)
    return found


def find_forbidden_runtime_content(root: Path) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for rel, needle in FORBIDDEN_RUNTIME_CONTENT:
        path = root / Path(rel)
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if needle.lower() in text.lower():
            found.append((rel, needle))
    return found


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: verify_runtime_pruned.py <runtime-root>", file=sys.stderr)
        return 2
    root = Path(argv[1]).resolve()
    if not root.is_dir():
        print(f"runtime root not found: {root}", file=sys.stderr)
        return 2

    path_residuals = find_forbidden_runtime_paths(root)
    content_residuals = find_forbidden_runtime_content(root)
    if path_residuals or content_residuals:
        for rel in path_residuals:
            print(f"forbidden runtime residual: {rel}", file=sys.stderr)
        for rel, needle in content_residuals:
            print(
                f"forbidden runtime content: {rel} contains {needle!r}",
                file=sys.stderr,
            )
        return 1

    print("runtime pruning ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
