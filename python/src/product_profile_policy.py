# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""ProductProfilePolicy — resolve the active region product profile.

v0.3.0 "slim & focus" introduces region product profiles so one codebase can
expose a focused ``mainland_cn`` student surface while keeping source for a
future ``sea`` (Singapore / Malaysia) branch.

Phase A scope: profile *resolution* only. The profile-aware visibility lists
(providers, gateways, toolsets, skills, network hosts, bundle/deletion targets)
are added in Phase B, where the existing policy modules
(``capability_policy`` / ``tool_policy`` / ``network_policy`` /
``gateway_policy`` / ``desk_server.capabilities``) consume this object instead
of repeating region checks.

The profile is selected in settings and injected by the Rust shell into the
Python child as ``KABUQINA_PRODUCT_PROFILE`` (with ``HERMESDESK_PRODUCT_PROFILE``
accepted as a fallback during the v0.4.0 rename window). Missing or unknown
values resolve to ``mainland_cn``.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger("kabuqina.product_profile")

MAINLAND_CN = "mainland_cn"
SEA = "sea"

DEFAULT_PROFILE = MAINLAND_CN
KNOWN_PROFILES = frozenset({MAINLAND_CN, SEA})

_ENV_PRIMARY = "KABUQINA_PRODUCT_PROFILE"
_ENV_FALLBACK = "HERMESDESK_PRODUCT_PROFILE"


# ── Profile-aware visibility contract (Phase B) ────────────────────────────
#
# Single runtime source of truth for region cuts. Policy consumers read these
# instead of hardcoding their own region checks. The authoritative human lists
# live in docs/superpowers/specs/2026-06-19-mainland-profile-code-pruning-design.md;
# keep the two in sync. Gateway visibility/autostart is the CTL-C01 manifest
# contract and never falls back across regions.

_VISIBLE_PROVIDERS: dict[str, tuple[str, ...]] = {
    MAINLAND_CN: (
        "deepseek", "zai", "kimi-coding", "kimi-coding-cn",
        "stepfun", "minimax-cn", "alibaba", "custom",
    ),
}

_VISIBLE_GATEWAYS: dict[str, tuple[str, ...]] = {
    # ``desktop`` is the Tauri shell, not a gateway platform — excluded here.
    MAINLAND_CN: ("weixin", "qqbot", "dingtalk"),
    SEA: ("telegram", "whatsapp", "email"),
}

# Gateways whose stale ``.env`` keys are allowed to auto-start the gateway
# child. Mirrors ``_VISIBLE_GATEWAYS`` for ``mainland_cn`` but kept separate so
# a profile can show a platform without making it auto-start.
_AUTOSTART_GATEWAYS: dict[str, tuple[str, ...]] = {
    MAINLAND_CN: ("weixin", "qqbot", "dingtalk"),
    SEA: ("telegram", "whatsapp", "email"),
}

# Toolsets hidden from the desktop capability catalog for the profile, and also
# subtracted from the default active toolset by ToolPolicy. Catalog visibility
# only — hermes_core CONFIGURABLE_TOOLSETS (CLI/TUI/tests) is intact.
# ``image_gen`` is hidden for mainland_cn: its only backend is FAL.ai (a US
# service, not on the mainland egress allowlist) with no China backend wired in,
# so it is non-functional by default here. Source is kept for the sea profile.
_HIDDEN_TOOLSETS: dict[str, tuple[str, ...]] = {
    MAINLAND_CN: (
        "moa", "rl", "homeassistant", "discord", "discord_admin",
        "spotify", "feishu_doc", "feishu_drive", "yuanbao", "delegation",
        "image_gen",
    ),
}

_HIDDEN_SKILL_CATEGORIES: dict[str, tuple[str, ...]] = {
    MAINLAND_CN: (
        "apple", "autonomous-ai-agents", "devops", "dogfood", "gaming",
        "gifs", "github", "inference-sh", "mcp", "mlops", "red-teaming",
        "smart-home", "social-media", "yuanbao",
    ),
}

# Plugins not surfaced as student product features in the profile. Includes the
# global-cut plugins (also deleted in Phase D) plus retained-but-not-surfaced
# ones (observability, context_engine).
_HIDDEN_PLUGINS: dict[str, tuple[str, ...]] = {
    MAINLAND_CN: (
        "spotify", "google_meet", "example-dashboard", "hermes-achievements",
        "strike-freedom-cockpit", "observability", "context_engine",
    ),
}

# China provider API hosts added to the egress allowlist by default. Hostnames
# verified against web/src/lib/providers.ts. Messaging-platform hosts continue
# to be added dynamically via NetworkPolicy.extend_hosts.
_DEFAULT_NETWORK_HOSTS: dict[str, tuple[str, ...]] = {
    MAINLAND_CN: (
        "api.deepseek.com", "api.z.ai", "api.kimi.com", "api.stepfun.ai",
        "api.minimaxi.com", "dashscope-intl.aliyuncs.com",
        "dashscope.aliyuncs.com",
    ),
}

# Items deleted for EVERY profile (global student cut) — not a region decision.
# Provider deletion is deferred to v0.3.x; this constant is the target list and
# the contract the "absent from both profiles" tests assert against. Must NOT
# contain openai/google/gemini/anthropic/openrouter/telegram/whatsapp/email —
# those are sea-profile decisions, not global cuts.
GLOBAL_STUDENT_CUT: frozenset[str] = frozenset({
    # provider first-party surfaces
    "openai-codex", "copilot-acp", "github-copilot", "google-gemini-cli",
    "qwen-oauth", "bedrock", "azure-foundry", "vercel", "opencode",
    "opencode-go", "kilo", "nvidia", "arcee", "gmi", "ollama-cloud",
    # gateway/platform surfaces
    "homeassistant", "slack", "signal", "matrix", "mattermost",
    "bluebubbles", "webhook", "api_server", "yuanbao",
    # toolsets/tools
    "rl", "discord_admin", "spotify", "moa",
})


def _for_profile(mapping: dict[str, tuple[str, ...]], profile: str) -> tuple[str, ...]:
    """Return the profile's tuple, falling back to the default profile."""
    return mapping.get(profile) or mapping[DEFAULT_PROFILE]


def _exact_for_profile(mapping: dict[str, tuple[str, ...]], profile: str | None) -> tuple[str, ...]:
    """Return an exact profile value; unknown/missing profiles fail closed."""
    if profile not in KNOWN_PROFILES:
        return ()
    return mapping.get(profile, ())


class ProductProfilePolicy:
    """Resolve the active product profile from the runtime environment."""

    @staticmethod
    def resolve_profile() -> str:
        """Return the active profile id, always one of ``KNOWN_PROFILES``.

        Precedence: ``KABUQINA_PRODUCT_PROFILE`` then
        ``HERMESDESK_PRODUCT_PROFILE``. An unset or empty value resolves to the
        default *without* a warning; a set-but-unknown value logs a warning and
        falls back to the default.
        """
        raw = (
            os.environ.get(_ENV_PRIMARY)
            or os.environ.get(_ENV_FALLBACK)
            or ""
        ).strip().lower()
        if not raw:
            return DEFAULT_PROFILE
        if raw not in KNOWN_PROFILES:
            log.warning(
                "Unknown product profile %r; falling back to %s",
                raw,
                DEFAULT_PROFILE,
            )
            return DEFAULT_PROFILE
        return raw

    @staticmethod
    def resolve_gateway_profile() -> str | None:
        """Resolve a profile for gateway-producing boundaries.

        Missing values keep the installed default. A set-but-unknown value is
        not allowed to inherit another region's gateway surface.
        """
        raw = (os.environ.get(_ENV_PRIMARY) or os.environ.get(_ENV_FALLBACK) or "").strip().lower()
        if not raw:
            return DEFAULT_PROFILE
        if raw not in KNOWN_PROFILES:
            log.error("Unknown gateway product profile %r; gateway surface disabled", raw)
            return None
        return raw

    @staticmethod
    def is_mainland_cn() -> bool:
        return ProductProfilePolicy.resolve_profile() == MAINLAND_CN

    # ── Visibility accessors ──────────────────────────────────────────────
    # Each takes an optional explicit profile; when omitted it resolves the
    # active one. Set-returning accessors return frozensets for cheap
    # membership checks by consumers.

    @classmethod
    def _profile(cls, profile: str | None) -> str:
        return profile or cls.resolve_profile()

    @classmethod
    def visible_providers(cls, profile: str | None = None) -> tuple[str, ...]:
        return _for_profile(_VISIBLE_PROVIDERS, cls._profile(profile))

    @classmethod
    def visible_gateways(cls, profile: str | None = None) -> tuple[str, ...]:
        resolved = cls.resolve_gateway_profile() if profile is None else profile
        return _exact_for_profile(_VISIBLE_GATEWAYS, resolved)

    @classmethod
    def autostart_gateways(cls, profile: str | None = None) -> frozenset[str]:
        resolved = cls.resolve_gateway_profile() if profile is None else profile
        return frozenset(_exact_for_profile(_AUTOSTART_GATEWAYS, resolved))

    @classmethod
    def hidden_toolsets(cls, profile: str | None = None) -> frozenset[str]:
        return frozenset(_for_profile(_HIDDEN_TOOLSETS, cls._profile(profile)))

    @classmethod
    def hidden_skill_categories(cls, profile: str | None = None) -> frozenset[str]:
        return frozenset(_for_profile(_HIDDEN_SKILL_CATEGORIES, cls._profile(profile)))

    @classmethod
    def hidden_plugins(cls, profile: str | None = None) -> frozenset[str]:
        return frozenset(_for_profile(_HIDDEN_PLUGINS, cls._profile(profile)))

    @classmethod
    def default_network_hosts(cls, profile: str | None = None) -> tuple[str, ...]:
        return _for_profile(_DEFAULT_NETWORK_HOSTS, cls._profile(profile))

    @classmethod
    def is_toolset_hidden(cls, name: str, profile: str | None = None) -> bool:
        return name in cls.hidden_toolsets(profile)

    @classmethod
    def is_skill_category_hidden(cls, category: str | None, profile: str | None = None) -> bool:
        if not category:
            return False
        return str(category).strip().lower() in cls.hidden_skill_categories(profile)

    @classmethod
    def is_plugin_hidden(cls, name: str | None, profile: str | None = None) -> bool:
        if not name:
            return False
        return str(name).strip().lower() in cls.hidden_plugins(profile)
