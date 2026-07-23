# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Verify that v0.3.0 release runtime does not ship cut surfaces."""

from __future__ import annotations

import sys
from pathlib import Path


FORBIDDEN_RUNTIME_PATHS = (
    # v0.3.0 global-cut gateway adapters.
    "kabuqina/gateway/platforms/api_server.py",
    "kabuqina/gateway/platforms/bluebubbles.py",
    "kabuqina/gateway/platforms/homeassistant.py",
    "kabuqina/gateway/platforms/matrix.py",
    "kabuqina/gateway/platforms/mattermost.py",
    "kabuqina/gateway/platforms/signal.py",
    "kabuqina/gateway/platforms/signal_rate_limit.py",
    "kabuqina/gateway/platforms/slack.py",
    "kabuqina/gateway/platforms/sms.py",
    "kabuqina/gateway/platforms/webhook.py",
    "kabuqina/gateway/platforms/yuanbao.py",
    "kabuqina/gateway/platforms/yuanbao_media.py",
    "kabuqina/gateway/platforms/yuanbao_proto.py",
    "kabuqina/gateway/platforms/yuanbao_sticker.py",
    # v0.5.0 CTL-C03a removed owned Discord surfaces.
    "kabuqina/gateway/platforms/discord.py",
    "kabuqina/tools/discord_tool.py",
    "kabuqina/scripts/discord-voice-doctor.py",
    # v0.5.0 CTL-C03b removed owned Feishu/Lark surfaces.
    "feishu_qr_worker.py",
    "kabuqina/gateway/platforms/feishu.py",
    "kabuqina/gateway/platforms/feishu_comment.py",
    "kabuqina/gateway/platforms/feishu_comment_rules.py",
    "kabuqina/tools/feishu_doc_tool.py",
    "kabuqina/tools/feishu_drive_tool.py",
    # v0.5.0 CTL-C03c removed owned WeCom bot/callback surfaces.
    "wecom_qr_worker.py",
    "kabuqina/gateway/platforms/wecom.py",
    "kabuqina/gateway/platforms/wecom_callback.py",
    "kabuqina/gateway/platforms/wecom_crypto.py",
    # v0.3.0 global-cut bundled plugins and late-discovered platform plugins.
    "kabuqina/plugins/disk-cleanup",
    "kabuqina/plugins/platforms",
    "kabuqina/plugins/spotify",
    # v0.3.0 global-cut or non-product skills.
    "kabuqina/skills/creative/popular-web-designs/templates/spotify.md",
    "kabuqina/skills/dogfood",
    "kabuqina/skills/media/spotify",
)

FORBIDDEN_RUNTIME_GLOBS = (
    # CTL-C03a direct dependency and its voice-only orphan.
    "site-packages/discord",
    "site-packages/discord_py-*.dist-info",
    "site-packages/nacl",
    "site-packages/PyNaCl-*.dist-info",
    # CTL-C03b direct dependency.
    "site-packages/lark_oapi",
    "site-packages/lark_oapi-*.dist-info",
)

FORBIDDEN_RUNTIME_CONTENT = (
    ("kabuqina/kabuqina_cli/auth.py", "spotify"),
    ("kabuqina/toolsets.py", "spotify"),
    ("kabuqina/kabuqina_cli/tools_config.py", "spotify"),
)


def find_forbidden_runtime_paths(root: Path) -> list[str]:
    found: list[str] = []
    for rel in FORBIDDEN_RUNTIME_PATHS:
        if (root / Path(rel)).exists():
            found.append(rel)
    return found


def find_forbidden_runtime_globs(root: Path) -> list[str]:
    found: set[str] = set()
    for pattern in FORBIDDEN_RUNTIME_GLOBS:
        for path in root.glob(pattern):
            found.add(path.relative_to(root).as_posix())
    return sorted(found)


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
    path_residuals.extend(find_forbidden_runtime_globs(root))
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
