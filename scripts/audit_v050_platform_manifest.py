"""Validate the v0.5.0 C-0 platform-surface manifest.

The contract checks are intentionally fail-closed: a new core enum member,
bundled platform plugin, adapter module, QR worker, Rust platform module, or
Web platform registry entry must first be classified in the manifest.

``--check-observed`` additionally verifies the mutable C-0 source snapshot.
``--verify-local-artifacts`` verifies the recorded local runtime and installer;
those artifacts are not expected to exist in every source checkout.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    ROOT
    / "docs"
    / "superpowers"
    / "progress"
    / "2026-07-18-v0.5.0-c0-platform-surface-manifest.json"
)

TARGET_PROFILES = {
    "mainland_cn": {
        "product_shells": ["desktop"],
        "gateway_platforms": ["weixin", "qqbot", "dingtalk"],
    },
    "sea": {
        "product_shells": ["desktop"],
        "gateway_platforms": ["telegram", "whatsapp", "email"],
    },
}
RETAINED_EXTERNAL = {
    "weixin",
    "qqbot",
    "dingtalk",
    "telegram",
    "whatsapp",
    "email",
}
RETAINED_BY_PROFILE = {
    "weixin": ["mainland_cn"],
    "qqbot": ["mainland_cn"],
    "dingtalk": ["mainland_cn"],
    "telegram": ["sea"],
    "whatsapp": ["sea"],
    "email": ["sea"],
}
INTERNAL_PLATFORMS = {"local"}
REMOVED_BUILTINS = {
    "discord",
    "feishu",
    "wecom",
    "wecom_callback",
    "sms",
    "slack",
    "signal",
    "matrix",
    "mattermost",
    "bluebubbles",
    "homeassistant",
    "yuanbao",
    "webhook",
    "api_server",
}
REMOVED_BUNDLED_PLUGINS = {"irc", "teams"}
EXPECTED_BUILTINS = RETAINED_EXTERNAL | INTERNAL_PLATFORMS | REMOVED_BUILTINS
EXPECTED_CLASSIFIED = EXPECTED_BUILTINS | REMOVED_BUNDLED_PLUGINS

REQUIRED_SURFACE_FIELDS = {
    "surface",
    "product_shells",
    "gateway_platforms",
    "profiles",
    "decision",
    "reason",
    "owner",
    "source_paths",
    "runtime_dependencies",
    "persisted_data",
    "network_hosts",
    "credential_keys",
    "jobs/home_channel",
    "removal_slice",
    "verification",
}
ALLOWED_DECISIONS = {
    "retain",
    "remove",
    "retain_product_shell",
    "retain_shared_kernel",
    "retain_internal_sentinel",
}
REQUIRED_SIGNOFF_ROLES = {
    "Gateway/core",
    "Python policy",
    "Rust shell",
    "Web Settings",
    "Bundle/release",
}
ALLOWED_SIGNOFF_STATUSES = {"pending", "approved", "changes_requested"}
ALLOWED_WORK_PACKAGE_STATUSES = {
    "review_evidence_complete_independent_signoff_pending",
    "done",
}

# C-0 is an inventory gate, so a merely non-empty curated ledger is not enough.
# These IDs are the reviewed closed sets. Adding or removing an inventory record
# requires an intentional contract change here as well as in the manifest.
EXPECTED_DEPENDENCY_IDS = {
    "node-whatsapp-bridge",
    "py-aiohttp-shared",
    "py-certifi-weixin",
    "py-croniter",
    "py-cryptography-shared",
    "py-dingtalk-openapi",
    "py-dingtalk-stream",
    "py-discord-voice",
    "py-httpx-socks-shared",
    "py-lark-oapi",
    "py-mautrix-stack",
    "py-microsoft-teams-apps",
    "py-pillow-shared",
    "py-qrcode-shared",
    "py-slack-sdk",
    "py-telegram-sdk",
    "py-websockets-shared-conflict",
    "qq-audio-external-tools",
    "rust-reqwest-shared",
    "py-fastapi-uvicorn",
}
EXPECTED_PERSISTED_RECORD_IDS = {
    "channel-directory",
    "cron-jobs-delivery-targets",
    "desktop-state-databases",
    "feishu-runtime-files",
    "gateway-config-primary-legacy",
    "gateway-runtime-state",
    "gateway-session-origin",
    "host-gateway-env",
    "pairing-stores",
    "platform-thread-maps",
    "profile-config-and-host-prefs",
    "profile-env",
    "removed-qr-state",
    "retained-qr-state",
    "shared-media-caches",
    "telegram-sticker-cache",
    "weixin-account-state",
    "whatsapp-auth-session",
    "whatsapp-bridge-log-cache",
    "windows-credential-manager",
}

REMOVED_SURFACE_NAMES = {
    "discord",
    "feishu_lark",
    "wecom_family",
    "sms_twilio",
    "slack",
    "signal",
    "matrix",
    "mattermost",
    "bluebubbles",
    "home_assistant",
    "yuanbao",
    "webhook",
    "api_server",
    "irc_plugin",
    "teams_plugin",
}

ENV_PREFIX_TO_SURFACE = {
    "API_SERVER": "api_server",
    "BLUEBUBBLES": "bluebubbles",
    "DINGTALK": "dingtalk",
    "DISCORD": "discord",
    "EMAIL": "email",
    "FEISHU": "feishu_lark",
    "LARK": "feishu_lark",
    "HOMEASSISTANT": "home_assistant",
    "HOME_ASSISTANT": "home_assistant",
    "HASS": "home_assistant",
    "IRC": "irc_plugin",
    "LOCAL": "local_delivery",
    "MATRIX": "matrix",
    "MATTERMOST": "mattermost",
    "QQBOT": "qqbot",
    "QQ": "qqbot",
    "SIGNAL": "signal",
    "SLACK": "slack",
    "SMS": "sms_twilio",
    "TEAMS": "teams_plugin",
    "TELEGRAM": "telegram",
    "TWILIO": "sms_twilio",
    "WEBHOOK": "webhook",
    "WECOM": "wecom_family",
    "WEIXIN": "weixin",
    "WHATSAPP": "whatsapp",
    "YUANBAO": "yuanbao",
}

# Non-platform environment namespaces are still part of the exact C-0 surface.
# Discovery happens before this mapping is applied; a new namespace therefore
# fails closed instead of being silently omitted from the ledger.
NON_PLATFORM_ENV_PREFIX_TO_SURFACE = {
    "AGENT_BROWSER": "gateway_kernel",
    "AIRTABLE": "gateway_kernel",
    "ALIBABA": "gateway_kernel",
    "ANTHROPIC": "gateway_kernel",
    "API": "gateway_kernel",
    "APPTAINER": "gateway_kernel",
    "AUXILIARY": "gateway_kernel",
    "AZURE": "gateway_kernel",
    "BASE": "gateway_kernel",
    "BLAND": "gateway_kernel",
    "BROWSER": "gateway_kernel",
    "BROWSERBASE": "gateway_kernel",
    "CAMOFOX": "gateway_kernel",
    "CANVAS": "gateway_kernel",
    "CLAUDE": "gateway_kernel",
    "COMFY": "gateway_kernel",
    "CUSTOM": "gateway_kernel",
    "DAYTONA": "gateway_kernel",
    "DASHSCOPE": "gateway_kernel",
    "DEEPSEEK": "gateway_kernel",
    "DELEGATION": "gateway_kernel",
    "DOCLING": "gateway_kernel",
    "EDITOR": "gateway_kernel",
    "ELEVENLABS": "gateway_kernel",
    "EXA": "gateway_kernel",
    "FAL": "gateway_kernel",
    "FIRECRAWL": "gateway_kernel",
    "FIREWORKS": "gateway_kernel",
    "GATEWAY": "gateway_kernel",
    "GEMINI": "gateway_kernel",
    "GIT": "gateway_kernel",
    "GITHUB": "gateway_kernel",
    "GOOGLE": "gateway_kernel",
    "GROQ": "gateway_kernel",
    "GLM": "gateway_kernel",
    "HERMES": "gateway_kernel",
    "HF": "gateway_kernel",
    "HINDSIGHT": "gateway_kernel",
    "HONCHO": "gateway_kernel",
    "KABUQINA": "desktop",
    "HERMESDESK": "desktop",
    "KIMI": "gateway_kernel",
    "IMAGE": "gateway_kernel",
    "LANGSMITH": "gateway_kernel",
    "LANGFUSE": "gateway_kernel",
    "LINEAR": "gateway_kernel",
    "MESSAGING": "gateway_kernel",
    "MEM0": "gateway_kernel",
    "MINIMAX": "gateway_kernel",
    "MISTRAL": "gateway_kernel",
    "MSTEAMS": "teams_plugin",
    "MODAL": "gateway_kernel",
    "MOA": "gateway_kernel",
    "NOUS": "gateway_kernel",
    "NOSTR": "gateway_kernel",
    "NOTION": "gateway_kernel",
    "OPENAI": "gateway_kernel",
    "OPENROUTER": "gateway_kernel",
    "OPENVIKING": "gateway_kernel",
    "OAUTHLIB": "gateway_kernel",
    "OSV": "gateway_kernel",
    "PARALLEL": "gateway_kernel",
    "PHONE": "gateway_kernel",
    "RETAINDB": "gateway_kernel",
    "SESSION": "gateway_kernel",
    "SOLANA": "gateway_kernel",
    "SSH": "gateway_kernel",
    "SSL": "gateway_kernel",
    "SQLITE": "gateway_kernel",
    "STT": "gateway_kernel",
    "STEPFUN": "gateway_kernel",
    "SUPERMEMORY": "gateway_kernel",
    "TAVILY": "gateway_kernel",
    "TENOR": "gateway_kernel",
    "TERMINAL": "gateway_kernel",
    "TINKER": "gateway_kernel",
    "TIRITH": "gateway_kernel",
    "TOOL": "gateway_kernel",
    "TOGETHER": "gateway_kernel",
    "TOKENHUB": "gateway_kernel",
    "TWITCH": "gateway_kernel",
    "USER": "gateway_kernel",
    "USDA": "gateway_kernel",
    "VERCEL": "gateway_kernel",
    "VAPI": "gateway_kernel",
    "VISUAL": "gateway_kernel",
    "VOICE": "gateway_kernel",
    "VISION": "gateway_kernel",
    "WANDB": "gateway_kernel",
    "WEB": "gateway_kernel",
    "XAI": "gateway_kernel",
    "XIAOMI": "gateway_kernel",
    "XDG": "gateway_kernel",
    "YC": "gateway_kernel",
    "YOLO": "gateway_kernel",
    "ZAI": "gateway_kernel",
    "Z_AI": "gateway_kernel",
}

EXACT_ENV_KEY_TO_SURFACE = {
    "BROWSER_CDP_URL": "desktop",
    "ALL_PROXY": "gateway_kernel",
    "DEV": "desktop",
    "DATABASE_URL": "gateway_kernel",
    "COLUMNS": "gateway_kernel",
    "COMSPEC": "desktop",
    "CONDA_PREFIX": "gateway_kernel",
    "DISPLAY": "gateway_kernel",
    "DOCLING_ARTIFACTS_PATH": "gateway_kernel",
    "DOCLING_HF_MAX_WORKERS": "desktop",
    "DOCLING_HF_RETRIES": "desktop",
    "GH_TOKEN": "gateway_kernel",
    "HOME": "gateway_kernel",
    "HTTP_PROXY": "gateway_kernel",
    "HTTPS_PROXY": "gateway_kernel",
    "HERMES_HOME": "desktop",
    "INVOCATION_ID": "gateway_kernel",
    "KABUQINA_MICROSOFT_OAUTH_CLIENT_ID": "email",
    "LM_API_KEY": "gateway_kernel",
    "LM_BASE_URL": "gateway_kernel",
    "LLM_MODEL": "gateway_kernel",
    "LANG": "gateway_kernel",
    "LC_ALL": "gateway_kernel",
    "LOCALAPPDATA": "desktop",
    "MIGRATION_JSON_OUTPUT": "gateway_kernel",
    "NO_COLOR": "gateway_kernel",
    "NO_PROXY": "desktop",
    "PATH": "desktop",
    "PATHEXT": "gateway_kernel",
    "PLAYWRIGHT_BROWSERS_PATH": "gateway_kernel",
    "PREFIX": "gateway_kernel",
    "PULSE_SERVER": "gateway_kernel",
    "PYTHONIOENCODING": "desktop",
    "PYTHONDONTWRITEBYTECODE": "gateway_kernel",
    "PYTHONPATH": "desktop",
    "PYTHONUNBUFFERED": "desktop",
    "PYTHONUTF8": "desktop",
    "PYTEST_CURRENT_TEST": "gateway_kernel",
    "REQUESTS_CA_BUNDLE": "gateway_kernel",
    "SHELL": "gateway_kernel",
    "SUDO_PASSWORD": "gateway_kernel",
    "SYSTEMROOT": "desktop",
    "TEMP": "desktop",
    "TERM": "gateway_kernel",
    "TERMUX_VERSION": "gateway_kernel",
    "TMP": "desktop",
    "TMPDIR": "gateway_kernel",
    "USERPROFILE": "desktop",
    "TZ": "gateway_kernel",
    "VIRTUAL_ENV": "gateway_kernel",
    "WINDIR": "desktop",
    "LINES": "gateway_kernel",
    "WAYLAND_DISPLAY": "gateway_kernel",
}

ENVIRONMENT_SCAN_ROOTS = (
    "hermes_core/",
    "python/src/",
    "python/overlays/",
    "tauri/src/",
    "web/src/",
)
ENVIRONMENT_SCAN_EXCLUDED_PREFIXES = (
    "hermes_core/.github/",
    "hermes_core/.plans/",
    "hermes_core/assets/",
    "hermes_core/datagen-config-examples/",
    "hermes_core/plans/",
    "hermes_core/web/",
    "hermes_core/website/",
)
ENVIRONMENT_NAMESPACE_SURFACE_OVERRIDES = {
    "_HERMES_FORCE_": "gateway_kernel",
    "CONDA": "gateway_kernel",
    "LANG": "gateway_kernel",
    "LC_": "gateway_kernel",
    "LOGNAME": "gateway_kernel",
    "SYSTEMROOT": "desktop",
    "TMPDIR": "gateway_kernel",
    "VIRTUAL_ENV": "gateway_kernel",
    "WINDIR": "desktop",
}
ENVIRONMENT_DISCOVERY_CONTRACT = {
    "mode": "discovery_first_fail_closed",
    "runtime_roots": list(ENVIRONMENT_SCAN_ROOTS),
    "excluded_source_classes": [
        "tests directories",
        *ENVIRONMENT_SCAN_EXCLUDED_PREFIXES,
    ],
    "python_accesses": [
        "os.getenv/putenv/unsetenv",
        "os.environ get/setdefault/pop/subscript",
        "literal wrapper calls and os.environ.get aliases",
    ],
    "rust_accesses": [
        "std::env/env var/var_os/set_var/remove_var",
        "Command.env",
        "option_env!/env!",
    ],
    "web_accesses": ["import.meta.env", "process.env"],
    "unknown_mapping": "validation_error",
    "dynamic_exact_declarations": "uppercase keys are extracted only from environment/credential registration structures, envKey properties and computed environment-key templates with a finite built-in/bundled-plugin expansion; mapping happens after discovery",
    "namespace_declarations": "wildcard prefixes are recorded in environment_namespace_edges and never inserted into the exact-key ledger",
    "computed_template_declarations": "computed keys such as {PLATFORM}_HOME_CHANNEL and its _NAME companion are recorded in environment_dynamic_key_templates; every statically known built-in/bundled plugin expansion must also exist as an exact edge, while unclassified runtime plugins remain prohibited",
    "ordinary_uppercase_literals": "ignored unless they occur in a real access or declaration structure",
}

REFERENCE_ALIASES = {
    "api_server": ("api_server", "api server"),
    "bluebubbles": ("bluebubbles",),
    "dingtalk": ("dingtalk",),
    "discord": ("discord",),
    "email": ("email",),
    "feishu_lark": ("feishu", "lark"),
    "home_assistant": ("homeassistant", "home_assistant", "home assistant"),
    "irc_plugin": ("irc",),
    "local_delivery": ("local", "desktop"),
    "matrix": ("matrix",),
    "mattermost": ("mattermost",),
    "qqbot": ("qqbot", "qq bot"),
    "signal": ("signal",),
    "slack": ("slack",),
    "sms_twilio": ("sms", "twilio"),
    "teams_plugin": ("teams",),
    "telegram": ("telegram",),
    "webhook": ("webhook",),
    "wecom_family": ("wecom", "wecom_callback", "wecom callback"),
    "weixin": ("weixin",),
    "whatsapp": ("whatsapp",),
    "yuanbao": ("yuanbao",),
}

REFERENCE_SCAN_ROOTS = (
    "hermes_core/gateway/",
    "hermes_core/cron/",
    "hermes_core/tools/",
    "hermes_core/kabuqina_cli/",
    "hermes_core/plugins/platforms/",
    "hermes_core/tests/",
    "python/src/",
    "python/overlays/",
    "python/tests/",
    "tauri/src/",
    "tauri/tests/",
    "web/src/",
    "web/tests/",
    "hermes_core/website/docs/",
    "docs/test-cases/",
)

REFERENCE_EXACT_FILES = {
    "AGENTS.md",
    "DECISIONS.md",
    "LICENSE",
    "NOTICE",
    "README.md",
    "docs/README.md",
    "docs/ROADMAP.md",
    "docs/architecture.md",
    "docs/embedded-python-bundled.md",
    "docs/onboarding.md",
    "docs/qa-checklist.md",
    "docs/safety.md",
    "docs/test-plan.md",
    "docs/troubleshooting.md",
    "hermes_core/LICENSE",
    "hermes_core/README.md",
    "hermes_core/pyproject.toml",
    "hermes_core/uv.lock",
    "hermes_core/scripts/whatsapp-bridge/package.json",
    "hermes_core/scripts/whatsapp-bridge/package-lock.json",
    "python/build_bundle.ps1",
    "python/requirements-desktop.txt",
    "python/tools/verify_bundle_site_packages.py",
    "python/tools/verify_runtime_imports.py",
    "python/tools/verify_runtime_pruned.py",
    "tauri/Cargo.lock",
    "tauri/Cargo.toml",
    "web/package-lock.json",
    "web/package.json",
}

ACTIVATION_ALLOWED_PATHS = {
    "docs/superpowers/plans/2026-07-18-v0.5.0-execution-control-board.md",
    "docs/superpowers/progress/2026-07-18-v0.5.0-c0-platform-audit.md",
    "docs/superpowers/progress/2026-07-18-v0.5.0-c0-platform-surface-manifest.json",
    "python/tests/test_v050_platform_manifest.py",
    "scripts/audit_v050_platform_manifest.py",
}

REQUIRED_TYPED_REFERENCE_FIELDS = {
    "path",
    "layer",
    "edge_types",
    "platform_surfaces",
    "observed_current",
    "target_contract",
    "known_gaps",
}
REQUIRED_DEPENDENCY_FIELDS = {
    "id",
    "package",
    "ecosystem",
    "declaration_paths",
    "version_constraint",
    "platform_surfaces",
    "users",
    "usage_class",
    "bundle_presence",
    "target_action",
    "license_status",
    "advisory_status",
    "known_gaps",
}
REQUIRED_CREDENTIAL_EDGE_FIELDS = {
    "key",
    "surface",
    "primary_role",
    "source_paths",
    "observed_current",
    "target_contract",
    "known_gaps",
}
REQUIRED_ENVIRONMENT_NAMESPACE_EDGE_FIELDS = {
    "prefix",
    "pattern",
    "surface",
    "source_paths",
    "observed_current",
    "target_contract",
    "known_gaps",
}
REQUIRED_ENVIRONMENT_DYNAMIC_TEMPLATE_FIELDS = {
    "template",
    "pattern",
    "known_platforms",
    "exact_expansion",
    "source_paths",
    "observed_current",
    "target_contract",
    "dynamic_namespace_contract",
    "known_gaps",
}
REQUIRED_PERSISTED_RECORD_FIELDS = {
    "id",
    "surface",
    "path_or_record",
    "record_kind",
    "sensitivity",
    "observed_current",
    "target_contract",
    "cleanup_mode",
    "known_gaps",
}
REQUIRED_VERIFICATION_FIELDS = {
    "id",
    "owner",
    "owner_status",
    "command",
    "expected",
    "evidence",
    "status",
}
REQUIRED_SURFACE_DEPENDENCY_COVERAGE_FIELDS = {
    "surface",
    "runtime_dependency",
    "dependency_ids",
    "exemption",
}
REQUIRED_PLUGIN_IMPORT_COVERAGE_FIELDS = {
    "surface",
    "import_root",
    "dependency_id",
}
ALLOWED_DEPENDENCY_EXEMPTION_KINDS = {
    "behavioral_observation",
    "bundled_runtime",
    "external_service",
    "host_framework",
    "stdlib",
    "system_component",
}
BUNDLED_PLUGIN_SURFACES = {
    "irc": "irc_plugin",
    "teams": "teams_plugin",
}
LOCAL_IMPORT_ROOTS = {"gateway", "hermes_core", "kabuqina_cli", "tools"}


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@lru_cache(maxsize=None)
def _tracked_files(root: Path = ROOT) -> list[str]:
    result = _run_git(root, "ls-files")
    if result.returncode != 0:
        raise RuntimeError(f"git ls-files failed: {result.stderr.strip()}")
    return sorted(line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip())


def _is_reference_scan_file(relative: str) -> bool:
    if relative in ACTIVATION_ALLOWED_PATHS:
        return False
    return relative in REFERENCE_EXACT_FILES or relative.startswith(REFERENCE_SCAN_ROOTS)


def _reference_layer_and_edges(relative: str) -> tuple[str, list[str]]:
    name = Path(relative).name.lower()
    if "/tests/" in relative or name.startswith("test_") or name.endswith(".test.mjs"):
        return "tests", ["verification_consumer"]
    if relative in {"LICENSE", "NOTICE", "hermes_core/LICENSE"}:
        return "license", ["license_reference"]
    if relative in {
        "hermes_core/pyproject.toml",
        "hermes_core/uv.lock",
        "hermes_core/scripts/whatsapp-bridge/package.json",
        "hermes_core/scripts/whatsapp-bridge/package-lock.json",
        "python/requirements-desktop.txt",
        "tauri/Cargo.lock",
        "tauri/Cargo.toml",
        "web/package-lock.json",
        "web/package.json",
    }:
        return "dependency_declaration", ["dependency_producer", "license_reference"]
    if relative == "python/build_bundle.ps1" or relative.startswith("python/tools/verify_"):
        return "bundle_build", ["bundle_producer", "verification_consumer"]
    if relative.startswith("hermes_core/gateway/platforms/") or relative.startswith(
        "hermes_core/plugins/platforms/"
    ):
        return "core_adapter", ["runtime_producer", "runtime_consumer"]
    if relative.startswith(("hermes_core/gateway/", "hermes_core/cron/", "hermes_core/tools/")):
        return "core_runtime", ["contract_producer", "runtime_consumer"]
    if relative.startswith("hermes_core/kabuqina_cli/"):
        return "core_cli", ["config_producer", "config_consumer"]
    if relative.startswith(("python/src/", "python/overlays/")):
        return "python_policy", ["policy_producer", "runtime_consumer"]
    if relative.startswith("tauri/src/"):
        return "rust_shell", ["credential_producer", "process_consumer"]
    if relative == "web/src/locales/strings.ts":
        return "web_i18n", ["copy_producer", "ui_consumer"]
    if relative.startswith("web/src/"):
        return "web_shell", ["settings_producer", "command_consumer"]
    return "active_docs", ["documentation_consumer"]


def _platform_surfaces_in_reference(relative: str, text: str, layer: str) -> list[str]:
    lower_path = relative.lower().replace("-", "_")
    lower_text = text.lower()
    found: set[str] = set()

    env_pattern = re.compile(
        r"[\"']((?:"
        + "|".join(sorted((re.escape(prefix) for prefix in ENV_PREFIX_TO_SURFACE), key=len, reverse=True))
        + r")_[A-Z0-9_]+)[\"']"
    )
    for key in env_pattern.findall(text):
        for prefix in sorted(ENV_PREFIX_TO_SURFACE, key=len, reverse=True):
            if key.startswith(f"{prefix}_"):
                found.add(ENV_PREFIX_TO_SURFACE[prefix])
                break

    is_documentation = layer in {"active_docs", "license"}
    for surface, aliases in REFERENCE_ALIASES.items():
        for alias in aliases:
            normalized = alias.replace(" ", "_")
            path_match = re.search(rf"(?:^|[/_.-]){re.escape(normalized)}(?:[/_.-]|$)", lower_path)
            if path_match:
                found.add(surface)
                break
            if is_documentation and re.search(rf"(?<![a-z0-9_]){re.escape(alias)}(?![a-z0-9_])", lower_text):
                found.add(surface)
                break
            literal_patterns = (
                rf"[\"']{re.escape(alias)}[\"']",
                rf"platform\.{re.escape(normalized)}\b",
                rf"gateway\.platforms\.{re.escape(normalized)}\b",
            )
            if any(re.search(pattern, lower_text) for pattern in literal_patterns):
                found.add(surface)
                break
    return sorted(found)


def collect_typed_reference_ledger(root: Path = ROOT) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for relative in _tracked_files(root):
        if not _is_reference_scan_file(relative):
            continue
        path = root / relative
        if not path.is_file():
            continue
        layer, edge_types = _reference_layer_and_edges(relative)
        text = path.read_text(encoding="utf-8", errors="ignore")
        surfaces = _platform_surfaces_in_reference(relative, text, layer)
        if not surfaces and layer != "license":
            continue
        if not surfaces:
            surfaces = ["all_classified"]
        records.append(
            {
                "path": relative,
                "layer": layer,
                "edge_types": edge_types,
                "platform_surfaces": surfaces,
                "observed_current": "Tracked source/reference contains a literal platform id, exact platform-prefixed key, adapter path, dependency declaration, test, active documentation, or license edge.",
                "target_contract": "Retained references must be reachable only from their exact profile; removed references leave live runtime/build/UI at their removal slice, while historical superpowers records remain outside this active-doc ledger.",
                "known_gaps": [f"surface_known_gaps.{surface}" for surface in surfaces if surface != "all_classified"],
            }
        )
    return records


def _credential_key_role(key: str) -> str:
    if "_HOME_" in key:
        return "home_target"
    if any(
        marker in key
        for marker in (
            "TOKEN",
            "SECRET",
            "PASSWORD",
            "ACCESS_KEY",
            "API_KEY",
            "APP_KEY",
            "RECOVERY_KEY",
            "ENCRYPT_KEY",
        )
    ) or key.endswith("_KEY"):
        return "secret"
    if any(
        marker in key
        for marker in (
            "_URL",
            "_HOST",
            "_DOMAIN",
            "_PROXY",
            "_HOMESERVER",
            "_API_BASE",
            "_WS_URL",
            "_CORS_ORIGINS",
        )
    ):
        return "network_host_expander"
    if any(marker in key for marker in ("_ID", "_ADDRESS", "_ACCOUNT", "_PHONE_NUMBER")):
        return "identifier"
    return "non_secret_config"


def _try_credential_surface(key: str) -> str | None:
    if key in EXACT_ENV_KEY_TO_SURFACE:
        return EXACT_ENV_KEY_TO_SURFACE[key]
    prefixes = {**ENV_PREFIX_TO_SURFACE, **NON_PLATFORM_ENV_PREFIX_TO_SURFACE}
    for prefix in sorted(prefixes, key=len, reverse=True):
        if key == prefix or key.startswith(f"{prefix}_"):
            return prefixes[prefix]
    return None


def _credential_surface(key: str) -> str:
    surface = _try_credential_surface(key)
    if surface is None:
        raise ValueError(f"unmapped discovered environment key: {key}")
    return surface


def _is_os_environ(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
        and node.attr == "environ"
    ) or (isinstance(node, ast.Name) and node.id == "environ")


def _python_environment_accesses(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
    environment_functions = {
        "getenv",
        "get_env_value",
        "save_env_value",
        "remove_env_value",
        "putenv",
        "unsetenv",
        "get_session_env",
        "lookup",
        "_opt_str",
    }
    name_values: dict[str, set[str]] = {}

    def literal_upper_values(node: ast.AST) -> set[str]:
        if isinstance(node, ast.Constant):
            return (
                {node.value}
                if isinstance(node.value, str)
                and re.fullmatch(r"[A-Z][A-Z0-9_]+", node.value)
                else set()
            )
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return {
                value
                for element in node.elts
                for value in literal_upper_values(element)
            }
        if isinstance(node, ast.Dict):
            return {
                value
                for element in [*node.keys, *node.values]
                if element is not None
                for value in literal_upper_values(element)
            }
        return set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            values = literal_upper_values(node.value)
            for target in targets:
                if isinstance(target, ast.Name) and values:
                    name_values.setdefault(target.id, set()).update(values)
        elif isinstance(node, ast.For) and isinstance(node.target, ast.Name):
            values = literal_upper_values(node.iter)
            if values:
                name_values.setdefault(node.target.id, set()).update(values)
        elif isinstance(node, ast.comprehension) and isinstance(node.target, ast.Name):
            values = literal_upper_values(node.iter)
            if values:
                name_values.setdefault(node.target.id, set()).update(values)

    def is_environment_call(node: ast.Call, names: set[str]) -> bool:
        if isinstance(node.func, ast.Name):
            return node.func.id in names or bool(
                re.match(r"^_?env_", node.func.id, re.IGNORECASE)
            )
        if not isinstance(node.func, ast.Attribute):
            return False
        return (
            node.func.attr in {"get", "setdefault", "pop"}
            and (
                _is_os_environ(node.func.value)
                or (
                    isinstance(node.func.value, ast.Name)
                    and (
                        node.func.value.id == "env"
                        or node.func.value.id.endswith("_env")
                    )
                )
            )
        ) or (
            node.func.attr in {"getenv", "putenv", "unsetenv"}
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "os"
        )

    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            parameters = {argument.arg for argument in node.args.args}
            if not parameters or node.name in environment_functions:
                continue
            if any(
                isinstance(child, ast.Call)
                and child.args
                and isinstance(child.args[0], ast.Name)
                and child.args[0].id in parameters
                and is_environment_call(child, environment_functions)
                for child in ast.walk(node)
            ):
                environment_functions.add(node.name)
                changed = True

    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for imported in node.names:
                if imported.name in environment_functions or node.module == "kabuqina_env":
                    aliases.add(imported.asname or imported.name)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        is_alias = (
            isinstance(value, ast.Attribute)
            and value.attr in {"get", "getenv"}
            and _is_os_environ(value.value)
        ) or (isinstance(value, ast.Name) and value.id in environment_functions)
        if is_alias:
            aliases.update(target.id for target in targets if isinstance(target, ast.Name))
    environment_functions.update(aliases)

    keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Constant):
            if (
                isinstance(node.left.value, str)
                and any(_is_os_environ(comparator) for comparator in node.comparators)
            ):
                keys.add(node.left.value)
                continue
        if (
            isinstance(node, ast.Subscript)
            and (
                _is_os_environ(node.value)
                or (
                    isinstance(node.value, ast.Name)
                    and (
                        node.value.id == "env"
                        or node.value.id.endswith("_env")
                    )
                )
            )
        ):
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                keys.add(node.slice.value)
                continue
            if isinstance(node.slice, ast.Name) and node.slice.id in name_values:
                keys.update(name_values[node.slice.id])
                continue
        if not isinstance(node, ast.Call) or not node.args:
            continue
        first = node.args[0]
        if is_environment_call(node, environment_functions):
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                keys.add(first.value)
            elif isinstance(first, ast.Name) and first.id in name_values:
                keys.update(name_values[first.id])
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if "os.environ" not in node.value and "os.getenv" not in node.value:
            continue
        keys.update(
            re.findall(
                r"(?:os\.getenv|os\.environ\.get|os\.environ\[)"
                r"\s*[\"']([A-Z][A-Z0-9_]+)[\"']",
                node.value,
            )
        )
    return {key for key in keys if re.fullmatch(r"[A-Z][A-Z0-9_]+", key)}


def _rust_environment_accesses(text: str) -> set[str]:
    patterns = (
        r"\.env\(\s*\"([A-Z][A-Z0-9_]+)\"",
        r"(?:(?:std::)?env::(?:var|var_os|set_var|remove_var)|option_env!|env!)"
        r"\(\s*\"([A-Z][A-Z0-9_]+)\"",
    )
    return {key for pattern in patterns for key in re.findall(pattern, text)}


def _web_environment_accesses(text: str) -> set[str]:
    dotted = re.findall(
        r"(?:import\.meta\.env|process\.env)\.([A-Z][A-Z0-9_]+)", text
    )
    bracketed = re.findall(
        r"(?:import\.meta\.env|process\.env)\[[\"']([A-Z][A-Z0-9_]+)[\"']\]",
        text,
    )
    return set(dotted) | set(bracketed)


def _is_environment_declaration_name(name: str) -> bool:
    upper = name.upper()
    normalized = name.lstrip("_")
    is_constant_name = bool(normalized) and normalized == normalized.upper()
    is_structured_local = bool(
        re.search(
            r"(?:^|_)env(?:_(?:map|names|keys|vars|requirements))?$",
            normalized,
            re.IGNORECASE,
        )
        or re.fullmatch(r"platform_.+_map", normalized, re.IGNORECASE)
        or re.fullmatch(r"(?:api|credential)_keys", normalized, re.IGNORECASE)
        or bool(re.search(r"env_.+(?:blocklist|allowlist)$", normalized, re.IGNORECASE))
    )
    if not (is_constant_name or is_structured_local):
        return False
    if any(marker in upper for marker in ("SUFFIX", "REGEX")) or upper.endswith("_RE"):
        return False
    if is_structured_local:
        return True
    return bool(re.search(r"(?:^|_)ENV(?:IRONMENT)?(?:_|$)", upper)) or any(
        marker in upper
        for marker in (
            "CREDENTIAL",
            "PLATFORM_EXTRA_KEYS",
            "TOOLSET_ENV_REQUIREMENTS",
        )
    )


def _classify_environment_declaration_tokens(
    tokens: Iterable[str], *, force_namespace: bool = False
) -> tuple[set[str], set[str]]:
    exact: set[str] = set()
    namespaces: set[str] = set()
    for raw in tokens:
        if not isinstance(raw, str):
            continue
        delimiter_form = raw.endswith("=") or raw.endswith(" ")
        token = raw.rstrip("= ")
        if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", token):
            continue
        if not delimiter_form and (force_namespace or token.endswith("_")):
            namespaces.add(token)
        else:
            exact.add(token)
    return exact, namespaces


def _python_environment_declarations(path: Path) -> tuple[set[str], set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
    exact: set[str] = set()
    namespaces: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue
        environment_items = node.iter
        if (
            isinstance(environment_items, ast.Call)
            and isinstance(environment_items.func, ast.Name)
            and environment_items.func.id in {"list", "tuple"}
            and environment_items.args
        ):
            environment_items = environment_items.args[0]
        if not (
            isinstance(environment_items, ast.Call)
            and isinstance(environment_items.func, ast.Attribute)
            and environment_items.func.attr == "items"
            and _is_os_environ(environment_items.func.value)
        ):
            continue
        if not isinstance(node.target, (ast.Tuple, ast.List)) or not node.target.elts:
            continue
        key_target = node.target.elts[0]
        if not isinstance(key_target, ast.Name):
            continue
        for child in ast.walk(node):
            if not (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr == "startswith"
                and isinstance(child.func.value, ast.Name)
                and child.func.value.id == key_target.id
                and child.args
                and isinstance(child.args[0], ast.Constant)
                and isinstance(child.args[0].value, str)
            ):
                continue
            _, discovered_namespaces = _classify_environment_declaration_tokens(
                [child.args[0].value], force_namespace=True
            )
            namespaces.update(discovered_namespaces)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not _is_environment_declaration_name(node.name):
            continue
        tokens = [
            child.value
            for child in ast.walk(node)
            if isinstance(child, ast.Constant) and isinstance(child.value, str)
        ]
        declared_exact, declared_namespaces = _classify_environment_declaration_tokens(
            tokens,
            force_namespace="PREFIX" in node.name.upper(),
        )
        exact.update(declared_exact)
        namespaces.update(declared_namespaces)
    for node in ast.walk(tree):
        if not isinstance(node, ast.keyword) or not node.arg:
            continue
        keyword_name = node.arg.lower()
        if "env" not in keyword_name or "suffix" in keyword_name:
            continue
        tokens = [
            child.value
            for child in ast.walk(node.value)
            if isinstance(child, ast.Constant) and isinstance(child.value, str)
        ]
        declared_exact, declared_namespaces = _classify_environment_declaration_tokens(
            tokens,
            force_namespace="prefix" in keyword_name,
        )
        exact.update(declared_exact)
        namespaces.update(declared_namespaces)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        names = [target.id for target in targets if isinstance(target, ast.Name)]
        declaration_names = [name for name in names if _is_environment_declaration_name(name)]
        if not declaration_names or node.value is None:
            continue
        tokens = [
            child.value
            for child in ast.walk(node.value)
            if isinstance(child, ast.Constant) and isinstance(child.value, str)
        ]
        declared_exact, declared_namespaces = _classify_environment_declaration_tokens(
            tokens,
            force_namespace=any("PREFIX" in name.upper() for name in declaration_names),
        )
        exact.update(declared_exact)
        namespaces.update(declared_namespaces)
    return exact, namespaces


def _rust_environment_declarations(text: str) -> tuple[set[str], set[str]]:
    exact: set[str] = set()
    namespaces: set[str] = set()
    declaration_blocks: list[tuple[str, str]] = []
    for match in re.finditer(
        r"\bconst\s+([A-Z][A-Z0-9_]*)\b[^=]*=\s*&?\[(.*?)\];",
        text,
        re.DOTALL,
    ):
        name, body = match.groups()
        if _is_environment_declaration_name(name):
            declaration_blocks.append((name, body))
    for match in re.finditer(
        r"\bfn\s+(platform_env_prefixes)\b.*?^\}",
        text,
        re.DOTALL | re.MULTILINE,
    ):
        declaration_blocks.append((match.group(1), match.group(0)))
    for name, body in declaration_blocks:
        tokens = re.findall(r'"([A-Z_][A-Z0-9_]*(?:[= ])?)"', body)
        declared_exact, declared_namespaces = _classify_environment_declaration_tokens(
            tokens,
            force_namespace="PREFIX" in name.upper(),
        )
        exact.update(declared_exact)
        namespaces.update(declared_namespaces)
    return exact, namespaces


def _web_environment_declarations(text: str) -> tuple[set[str], set[str]]:
    exact = set(
        re.findall(r"\benvKey\s*:\s*[\"']([A-Z][A-Z0-9_]*)[\"']", text)
    )
    namespaces: set[str] = set()
    for match in re.finditer(
        r"\b(?:const|let|var)\s+([A-Z][A-Z0-9_]*)\b[^=]*=\s*(.*?);",
        text,
        re.DOTALL,
    ):
        name, body = match.groups()
        if not _is_environment_declaration_name(name):
            continue
        tokens = re.findall(r"[\"']([A-Z_][A-Z0-9_]*)[\"']", body)
        declared_exact, declared_namespaces = _classify_environment_declaration_tokens(
            tokens,
            force_namespace="PREFIX" in name,
        )
        exact.update(declared_exact)
        namespaces.update(declared_namespaces)
    return exact, namespaces


def _joined_string_suffix(node: ast.JoinedStr) -> tuple[ast.FormattedValue | None, str]:
    """Return the last formatted value and the literal suffix following it."""

    suffix = ""
    for value in reversed(node.values):
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            suffix = value.value + suffix
            continue
        if isinstance(value, ast.FormattedValue):
            return value, suffix
        break
    return None, suffix


def _python_computed_environment_templates(path: Path) -> set[str]:
    """Discover computed keys only when an f-string is in an env-key context."""

    tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }

    def formatted_names(formatted: ast.FormattedValue) -> set[str]:
        return {
            child.id
            for child in ast.walk(formatted.value)
            if isinstance(child, ast.Name)
        }

    def has_env_key_context(node: ast.JoinedStr) -> bool:
        current: ast.AST | None = node
        while current is not None:
            parent = parents.get(current)
            if isinstance(parent, (ast.Assign, ast.AnnAssign)):
                targets = parent.targets if isinstance(parent, ast.Assign) else [parent.target]
                if any(
                    isinstance(target, ast.Name)
                    and "env_key" in target.id.lower()
                    for target in targets
                ):
                    return True
            if isinstance(parent, ast.Call):
                function_name = ""
                if isinstance(parent.func, ast.Name):
                    function_name = parent.func.id
                elif isinstance(parent.func, ast.Attribute):
                    function_name = parent.func.attr
                if function_name in {
                    "getenv",
                    "putenv",
                    "unsetenv",
                    "save_env_value",
                    "get_env_value",
                    "remove_env_value",
                }:
                    return True
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return "env_key" in parent.name.lower()
            current = parent
        return False

    templates: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr) or not has_env_key_context(node):
            continue
        formatted, suffix = _joined_string_suffix(node)
        if formatted is None:
            continue
        names = formatted_names(formatted)
        if suffix == "_HOME_CHANNEL" and any("platform" in name.lower() for name in names):
            templates.add("{PLATFORM}_HOME_CHANNEL")
        elif suffix == "_NAME" and any("env_key" in name.lower() for name in names):
            templates.add("{PLATFORM}_HOME_CHANNEL_NAME")
    return templates


@lru_cache(maxsize=None)
def discover_environment_dynamic_key_templates(
    root: Path = ROOT,
) -> dict[str, list[str]]:
    """Find computed environment-key templates before expanding their domain."""

    sources: dict[str, set[str]] = {}
    for relative in _tracked_files(root):
        if not _is_environment_scan_path(relative):
            continue
        path = root / relative
        if path.suffix != ".py" or not path.is_file():
            continue
        for template in _python_computed_environment_templates(path):
            sources.setdefault(template, set()).add(relative)
    return {template: sorted(paths) for template, paths in sorted(sources.items())}


def _environment_platform_domain(root: Path) -> list[str]:
    return sorted(
        set(discover_core_platforms(root)) | set(discover_bundled_platform_plugins(root))
    )


def _platform_environment_name(platform: str) -> str:
    return platform.upper().replace("-", "_").replace(" ", "_")


def _expand_environment_template(template: str, platform: str) -> str:
    return template.replace("{PLATFORM}", _platform_environment_name(platform))


@lru_cache(maxsize=None)
def collect_environment_dynamic_template_edges(
    root: Path = ROOT,
) -> list[dict[str, Any]]:
    templates = discover_environment_dynamic_key_templates(root)
    if not templates:
        return []
    platforms = _environment_platform_domain(root)
    records: list[dict[str, Any]] = []
    for template, source_paths in templates.items():
        suffix = re.escape(template.removeprefix("{PLATFORM}"))
        exact_expansion = [
            _expand_environment_template(template, platform) for platform in platforms
        ]
        records.append(
            {
                "template": template,
                "pattern": rf"^[A-Z][A-Z0-9_]*{suffix}$",
                "known_platforms": platforms,
                "exact_expansion": exact_expansion,
                "source_paths": source_paths,
                "observed_current": "A computed environment key is produced or consumed by the tracked runtime paths; all statically known platform values are expanded into the exact ledger.",
                "target_contract": "Every built-in or bundled plugin expansion must map to a classified surface and appear as an exact edge; any new bundled plugin fails closed until classified.",
                "dynamic_namespace_contract": "Runtime-registered plugin names are not a wildcard retention allowlist. unknown_platform_policy.runtime_plugin_platforms_allowed=false requires classification before this template may be instantiated.",
                "known_gaps": [
                    "User/project/pip runtime plugin names are not statically enumerable; the current target contract prohibits them until an explicit manifest classification is reviewed."
                ],
            }
        )
    return records


def _is_environment_scan_path(relative: str) -> bool:
    if not relative.startswith(ENVIRONMENT_SCAN_ROOTS):
        return False
    if relative.startswith(ENVIRONMENT_SCAN_EXCLUDED_PREFIXES):
        return False
    return "tests" not in PurePosixPath(relative).parts


@lru_cache(maxsize=None)
def discover_environment_key_accesses(root: Path = ROOT) -> dict[str, list[str]]:
    """Discover literal environment access before applying any surface map."""

    sources: dict[str, set[str]] = {}
    for relative in _tracked_files(root):
        if not _is_environment_scan_path(relative):
            continue
        path = root / relative
        if not path.is_file():
            continue
        keys: set[str] = set()
        if path.suffix == ".py":
            keys = _python_environment_accesses(path)
        elif path.suffix == ".rs":
            keys = _rust_environment_accesses(
                path.read_text(encoding="utf-8", errors="ignore")
            )
        elif path.suffix in {".ts", ".tsx", ".js", ".mjs"}:
            keys = _web_environment_accesses(
                path.read_text(encoding="utf-8", errors="ignore")
            )
        for key in keys:
            sources.setdefault(key, set()).add(relative)
    return {key: sorted(paths) for key, paths in sorted(sources.items())}


@lru_cache(maxsize=None)
def discover_environment_declarations(
    root: Path = ROOT,
) -> dict[str, dict[str, list[str]]]:
    """Discover exact keys and wildcard namespaces from real registration structures."""

    exact_sources: dict[str, set[str]] = {}
    namespace_sources: dict[str, set[str]] = {}
    for relative in _tracked_files(root):
        if not _is_environment_scan_path(relative):
            continue
        path = root / relative
        if not path.is_file():
            continue
        if path.suffix == ".py":
            exact, namespaces = _python_environment_declarations(path)
        elif path.suffix == ".rs":
            exact, namespaces = _rust_environment_declarations(
                path.read_text(encoding="utf-8", errors="ignore")
            )
        elif path.suffix in {".ts", ".tsx", ".js", ".mjs"}:
            exact, namespaces = _web_environment_declarations(
                path.read_text(encoding="utf-8", errors="ignore")
            )
        else:
            continue
        for key in exact:
            exact_sources.setdefault(key, set()).add(relative)
        for prefix in namespaces:
            namespace_sources.setdefault(prefix, set()).add(relative)
    return {
        "exact_keys": {
            key: sorted(paths) for key, paths in sorted(exact_sources.items())
        },
        "namespace_prefixes": {
            prefix: sorted(paths)
            for prefix, paths in sorted(namespace_sources.items())
        },
    }


@lru_cache(maxsize=None)
def collect_environment_key_sources(root: Path = ROOT) -> dict[str, list[str]]:
    """Collect literal accesses plus structured exact-key declarations."""

    discovered = discover_environment_key_accesses(root)
    sources = {key: set(paths) for key, paths in discovered.items()}
    declarations = discover_environment_declarations(root)["exact_keys"]
    for key, paths in declarations.items():
        sources.setdefault(key, set()).update(paths)
    for record in collect_environment_dynamic_template_edges(root):
        for key in record["exact_expansion"]:
            sources.setdefault(key, set()).update(record["source_paths"])
    return {key: sorted(paths) for key, paths in sorted(sources.items())}


@lru_cache(maxsize=None)
def collect_environment_namespace_sources(
    root: Path = ROOT,
) -> dict[str, list[str]]:
    return discover_environment_declarations(root)["namespace_prefixes"]


def _try_environment_namespace_surface(prefix: str) -> str | None:
    if prefix in ENVIRONMENT_NAMESPACE_SURFACE_OVERRIDES:
        return ENVIRONMENT_NAMESPACE_SURFACE_OVERRIDES[prefix]
    return _try_credential_surface(prefix.rstrip("_"))


@lru_cache(maxsize=None)
def collect_credential_key_edges(root: Path = ROOT) -> list[dict[str, Any]]:
    sources = collect_environment_key_sources(root)
    unmapped = [key for key in sources if _try_credential_surface(key) is None]
    if unmapped:
        raise ValueError(f"unmapped discovered environment keys: {sorted(unmapped)}")

    special_actions = {
        "QQBOT_APP_ID": "remove_stale_alias",
        "QQBOT_CLIENT_SECRET": "remove_stale_alias",
        "QQ_HOME_CHANNEL": "retain_legacy_reader_no_new_write",
        "QQ_HOME_CHANNEL_NAME": "retain_legacy_reader_no_new_write",
        "WEIXIN_APP_ID": "remove_stale_alias",
        "WEIXIN_APP_SECRET": "remove_stale_alias",
    }
    records: list[dict[str, Any]] = []
    for key in sorted(sources):
        surface = _credential_surface(key)
        role = _credential_key_role(key)
        if key in special_actions:
            action = special_actions[key]
        elif surface in REMOVED_SURFACE_NAMES:
            action = "stop_producing_then_explicit_cleanup"
        else:
            action = "retain_profile_scoped"
        gaps: list[str] = []
        if surface in REMOVED_SURFACE_NAMES:
            gaps.append("Removed-surface producers/consumers remain live until CTL-C02/removal; stored values require explicit CTL-C07 cleanup.")
        if role == "network_host_expander":
            gaps.append("Configured URL/host values require fail-closed network-policy validation; key presence is not an allowlist.")
        if role == "secret":
            if surface == "desktop":
                gaps.append("Desktop bridge/runtime secrets must remain ephemeral process inputs and must not be exported or persisted by cleanup flows.")
            else:
                gaps.append("Gateway secrets currently traverse host/profile .env files; CTL-C07 owns explicit cleanup/export and upgrade safety.")
        if key in special_actions:
            gaps.append("This is an observed stale/legacy alias and must not become a target allowlist entry.")
        records.append(
            {
                "key": key,
                "surface": surface,
                "primary_role": role,
                "source_paths": sources[key],
                "observed_current": "Literal environment access or structured exact-key declaration discovered in the listed tracked runtime paths.",
                "target_contract": action,
                "known_gaps": gaps,
            }
        )
    return records


@lru_cache(maxsize=None)
def collect_environment_namespace_edges(root: Path = ROOT) -> list[dict[str, Any]]:
    sources = collect_environment_namespace_sources(root)
    unmapped = [
        prefix
        for prefix in sources
        if _try_environment_namespace_surface(prefix) is None
    ]
    if unmapped:
        raise ValueError(
            f"unmapped discovered environment namespaces: {sorted(unmapped)}"
        )
    records: list[dict[str, Any]] = []
    for prefix in sorted(sources):
        surface = _try_environment_namespace_surface(prefix)
        if surface is None:
            raise AssertionError(f"validated namespace became unmapped: {prefix}")
        action = (
            "stop_producing_then_explicit_cleanup"
            if surface in REMOVED_SURFACE_NAMES
            else "retain_declared_namespace_boundary"
        )
        gaps = [
            "Wildcard namespace membership does not prove that any particular exact key exists; consumers must continue to validate exact keys."
        ]
        if surface in REMOVED_SURFACE_NAMES:
            gaps.append(
                "Removed-surface namespace consumers remain live until the owning removal slice and explicit CTL-C07 cleanup."
            )
        records.append(
            {
                "prefix": prefix,
                "pattern": f"{prefix}*",
                "surface": surface,
                "source_paths": sources[prefix],
                "observed_current": "Structured wildcard environment namespace declaration discovered in the listed tracked runtime paths.",
                "target_contract": action,
                "known_gaps": gaps,
            }
        )
    return records


def credential_environment_ledger_issues(
    manifest: dict[str, Any], root: Path = ROOT
) -> list[str]:
    try:
        actual_keys = collect_credential_key_edges(root)
        actual_namespaces = collect_environment_namespace_edges(root)
        actual_templates = collect_environment_dynamic_template_edges(root)
    except ValueError as exc:
        return [
            f"{exc}; add an explicit exact key or namespace-to-surface mapping"
        ]
    credential_graph = manifest.get("credential_data_graph", {})
    tracked_keys = credential_graph.get("environment_key_edges", [])
    errors: list[str] = []
    if tracked_keys != actual_keys:
        tracked_by_key = {
            record.get("key"): record
            for record in tracked_keys
            if isinstance(record, dict)
        }
        actual_by_key = {record["key"]: record for record in actual_keys}
        errors.append(
            "credential environment-key ledger drift: "
            f"missing={sorted(set(actual_by_key) - set(tracked_by_key))}, "
            f"extra={sorted(set(tracked_by_key) - set(actual_by_key))}; run "
            "scripts/audit_v050_platform_manifest.py --refresh-generated-ledgers"
        )
    tracked_namespaces = credential_graph.get("environment_namespace_edges", [])
    if tracked_namespaces != actual_namespaces:
        tracked_by_prefix = {
            record.get("prefix"): record
            for record in tracked_namespaces
            if isinstance(record, dict)
        }
        actual_by_prefix = {
            record["prefix"]: record for record in actual_namespaces
        }
        errors.append(
            "credential environment-namespace ledger drift: "
            f"missing={sorted(set(actual_by_prefix) - set(tracked_by_prefix))}, "
            f"extra={sorted(set(tracked_by_prefix) - set(actual_by_prefix))}; run "
            "scripts/audit_v050_platform_manifest.py --refresh-generated-ledgers"
        )
    tracked_templates = credential_graph.get("environment_dynamic_key_templates", [])
    if tracked_templates != actual_templates:
        tracked_by_template = {
            record.get("template"): record
            for record in tracked_templates
            if isinstance(record, dict)
        }
        actual_by_template = {
            record["template"]: record for record in actual_templates
        }
        errors.append(
            "credential dynamic environment-template ledger drift: "
            f"missing={sorted(set(actual_by_template) - set(tracked_by_template))}, "
            f"extra={sorted(set(tracked_by_template) - set(actual_by_template))}; run "
            "scripts/audit_v050_platform_manifest.py --refresh-generated-ledgers"
        )
    return errors


def refresh_generated_ledgers(manifest: dict[str, Any], root: Path = ROOT) -> None:
    references = collect_typed_reference_ledger(root)
    literal_environment_keys = discover_environment_key_accesses(root)
    dynamic_declarations = discover_environment_declarations(root)
    credential_edges = collect_credential_key_edges(root)
    namespace_edges = collect_environment_namespace_edges(root)
    dynamic_template_edges = collect_environment_dynamic_template_edges(root)
    manifest["typed_reference_ledger"] = references
    credential_graph = manifest.setdefault("credential_data_graph", {})
    credential_graph["environment_discovery"] = ENVIRONMENT_DISCOVERY_CONTRACT
    credential_graph["environment_key_edges"] = credential_edges
    credential_graph["environment_namespace_edges"] = namespace_edges
    credential_graph["environment_dynamic_key_templates"] = dynamic_template_edges
    manifest["generated_ledger_metadata"] = {
        "generator": "scripts/audit_v050_platform_manifest.py --refresh-generated-ledgers",
        "reference_path_count": len(references),
        "literal_environment_key_count": len(literal_environment_keys),
        "dynamic_environment_key_declaration_count": len(
            dynamic_declarations["exact_keys"]
        ),
        "environment_key_count": len(credential_edges),
        "environment_namespace_count": len(namespace_edges),
        "environment_dynamic_template_count": len(dynamic_template_edges),
        "historical_docs_policy": "docs/superpowers history is excluded from the active-doc reference scan; the three authority plans are hash-pinned separately.",
    }


def _ordered_unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _git_state(root: Path, relative_path: str) -> str:
    tracked = _run_git(root, "ls-files", "--error-unmatch", "--", relative_path)
    if tracked.returncode != 0:
        return "untracked"
    unstaged = _run_git(root, "diff", "--quiet", "--", relative_path)
    staged = _run_git(root, "diff", "--cached", "--quiet", "--", relative_path)
    return "modified" if unstaged.returncode or staged.returncode else "clean"


def discover_core_platforms(root: Path = ROOT) -> list[str]:
    config_path = root / "hermes_core" / "gateway" / "config.py"
    tree = ast.parse(config_path.read_text(encoding="utf-8"), filename=str(config_path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Platform":
            values: list[str] = []
            for child in node.body:
                if not isinstance(child, ast.Assign) or len(child.targets) != 1:
                    continue
                target = child.targets[0]
                if not isinstance(target, ast.Name) or target.id.startswith("_"):
                    continue
                if isinstance(child.value, ast.Constant) and isinstance(child.value.value, str):
                    values.append(child.value.value)
            return values
    raise RuntimeError(f"Platform enum not found in {config_path}")


def discover_bundled_platform_plugins(root: Path = ROOT) -> list[str]:
    base = root / "hermes_core" / "plugins" / "platforms"
    if not base.is_dir():
        return []
    names = {
        path.parent.name
        for pattern in ("*/plugin.yaml", "*/plugin.yml")
        for path in base.glob(pattern)
    }
    return sorted(names)


def collect_bundled_plugin_external_imports(
    root: Path = ROOT,
) -> list[dict[str, str]]:
    """Return third-party import roots observed in bundled platform plugins."""

    records: set[tuple[str, str]] = set()
    base = root / "hermes_core" / "plugins" / "platforms"
    for plugin in discover_bundled_platform_plugins(root):
        surface = BUNDLED_PLUGIN_SURFACES.get(plugin)
        if surface is None:
            raise ValueError(f"bundled plugin has no surface mapping: {plugin}")
        for path in sorted((base / plugin).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                import_root: str | None = None
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        candidate = alias.name.split(".", 1)[0]
                        if (
                            candidate not in sys.stdlib_module_names
                            and candidate not in LOCAL_IMPORT_ROOTS
                        ):
                            records.add((surface, candidate))
                    continue
                if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    import_root = node.module.split(".", 1)[0]
                if (
                    import_root
                    and import_root not in sys.stdlib_module_names
                    and import_root not in LOCAL_IMPORT_ROOTS
                ):
                    records.add((surface, import_root))
    return [
        {"surface": surface, "import_root": import_root}
        for surface, import_root in sorted(records)
    ]


def _source_claim_matches(claim: str, relative_path: str) -> bool:
    claim = claim.replace("\\", "/").rstrip("/")
    relative_path = relative_path.replace("\\", "/")
    if any(char in claim for char in "*?["):
        return fnmatch.fnmatchcase(relative_path, claim)
    return relative_path == claim or relative_path.startswith(f"{claim}/")


def _all_source_claims(manifest: dict[str, Any]) -> list[tuple[str, str]]:
    claims: list[tuple[str, str]] = []
    for surface in manifest.get("surfaces", []):
        for claim in surface.get("source_paths", []):
            if isinstance(claim, str):
                claims.append((surface.get("surface", "<unnamed>"), claim))
    return claims


def _shared_inventory_claims(manifest: dict[str, Any]) -> list[tuple[str, str]]:
    claims: list[tuple[str, str]] = []
    for item in manifest.get("shared_cross_layer_inventory", []):
        for claim in item.get("paths", []):
            if isinstance(claim, str):
                claims.append((f"shared:{item.get('id', '<unnamed>')}", claim))
    return claims


def _source_ownership_issues(
    manifest: dict[str, Any], root: Path = ROOT
) -> list[str]:
    candidates: set[Path] = set()
    candidates.update((root / "hermes_core" / "gateway" / "platforms").rglob("*"))
    candidates.update((root / "hermes_core" / "plugins" / "platforms").rglob("*"))
    candidates.update((root / "python" / "src").glob("*_qr_worker.py"))
    candidates.update((root / "tauri" / "src").glob("*_env.rs"))
    candidates.update((root / "tauri" / "src").glob("*_qr.rs"))
    candidates.update((root / "tauri" / "src").glob("*_oauth.rs"))

    claims = _all_source_claims(manifest)
    issues: list[str] = []
    for path in sorted(
        candidate
        for candidate in candidates
        if candidate.is_file()
        and "__pycache__" not in candidate.parts
        and candidate.suffix.lower() not in {".pyc", ".pyo"}
    ):
        relative = path.relative_to(root).as_posix()
        owners = sorted(
            {owner for owner, claim in claims if _source_claim_matches(claim, relative)}
        )
        if not owners:
            issues.append(f"unclassified platform source file: {relative}")
        elif len(owners) > 1:
            issues.append(f"multiply-owned platform source file: {relative} owners={owners}")
    return issues


def _path_owners(
    relative_path: str, claims: list[tuple[str, str]]
) -> set[str]:
    return {
        owner
        for owner, claim in claims
        if _source_claim_matches(claim, relative_path)
    }


def _core_reference_issues(
    manifest: dict[str, Any], root: Path = ROOT
) -> list[str]:
    issues: list[str] = []
    claims = _all_source_claims(manifest)
    enum_values = discover_core_platforms(root)
    enum_path = root / "hermes_core" / "gateway" / "config.py"
    enum_tree = ast.parse(enum_path.read_text(encoding="utf-8"), filename=str(enum_path))
    member_values: dict[str, str] = {}
    for node in enum_tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Platform":
            for child in node.body:
                if (
                    isinstance(child, ast.Assign)
                    and len(child.targets) == 1
                    and isinstance(child.targets[0], ast.Name)
                    and isinstance(child.value, ast.Constant)
                    and isinstance(child.value.value, str)
                ):
                    member_values[child.targets[0].id] = child.value.value

    scan_roots = [
        root / "hermes_core" / "gateway",
        root / "hermes_core" / "cron",
        root / "hermes_core" / "kabuqina_cli",
        root / "hermes_core" / "tools",
    ]
    for path in sorted(
        file
        for scan_root in scan_roots
        for file in scan_root.rglob("*.py")
        if "__pycache__" not in file.parts
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(root).as_posix()
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "Platform"
            ):
                if not node.attr.startswith("_") and node.attr not in member_values:
                    issues.append(
                        f"unknown Platform member reference: {relative}:{node.lineno} "
                        f"Platform.{node.attr}"
                    )
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Platform"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and node.args[0].value not in enum_values
                and node.args[0].value not in REMOVED_BUNDLED_PLUGINS
            ):
                issues.append(
                    f"unknown Platform literal reference: {relative}:{node.lineno} "
                    f"{node.args[0].value!r}"
                )

            module: str | None = None
            if isinstance(node, ast.ImportFrom):
                module = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("gateway.platforms"):
                        module = alias.name
                        break
            if not module or not module.startswith("gateway.platforms"):
                continue
            suffix = module.removeprefix("gateway.platforms").lstrip(".")
            if not suffix:
                target = "hermes_core/gateway/platforms/__init__.py"
            else:
                stem = suffix.replace(".", "/")
                file_target = root / "hermes_core" / "gateway" / "platforms" / f"{stem}.py"
                package_target = (
                    root / "hermes_core" / "gateway" / "platforms" / stem / "__init__.py"
                )
                if file_target.is_file():
                    target = file_target.relative_to(root).as_posix()
                elif package_target.is_file():
                    target = package_target.relative_to(root).as_posix()
                else:
                    issues.append(
                        f"unresolved gateway platform import: {relative}:{node.lineno} {module}"
                    )
                    continue
            owners = _path_owners(target, claims)
            if not owners:
                issues.append(
                    f"unclassified gateway platform import target: {relative}:{node.lineno} "
                    f"{target}"
                )
            elif len(owners) > 1:
                issues.append(
                    f"multiply-owned gateway platform import target: {relative}:{node.lineno} "
                    f"{target} owners={sorted(owners)}"
                )
    return _ordered_unique(issues)


def _bundle_reference_issues(
    manifest: dict[str, Any], root: Path = ROOT
) -> list[str]:
    issues: list[str] = []
    claims = _all_source_claims(manifest)
    build_path = root / "python" / "build_bundle.ps1"
    text = build_path.read_text(encoding="utf-8")

    drop_match = re.search(r"\$drop\s*=\s*@\((.*?)\n\)", text, flags=re.DOTALL)
    if not drop_match:
        return ["python/build_bundle.ps1: $drop block not found"]
    drop_paths = re.findall(r'"((?:gateway\\platforms|plugins\\platforms)[^\"]*)"', drop_match.group(1))
    for raw in drop_paths:
        normalized = raw.replace("\\", "/")
        if normalized == "plugins/platforms":
            for plugin in discover_bundled_platform_plugins(root):
                target = f"hermes_core/plugins/platforms/{plugin}"
                owners = _path_owners(target, claims)
                if len(owners) != 1:
                    issues.append(
                        f"bundle drop target ownership error: {target} owners={sorted(owners)}"
                    )
            continue
        target = f"hermes_core/{normalized}"
        owners = _path_owners(target, claims)
        if len(owners) != 1:
            issues.append(f"bundle drop target ownership error: {target} owners={sorted(owners)}")

    qr_workers = re.findall(r'"src\\([a-z0-9_]+_qr_worker\.py)"', text)
    for worker in qr_workers:
        target = f"python/src/{worker}"
        owners = _path_owners(target, claims)
        if len(owners) != 1:
            issues.append(f"bundle QR worker ownership error: {target} owners={sorted(owners)}")
    return issues


def validate_contract(
    manifest: dict[str, Any], root: Path = ROOT, *, scan_repository: bool = True
) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if manifest.get("work_package") != "CTL-C01" or manifest.get("slice") != "C-0":
        errors.append("manifest must identify work_package=CTL-C01 and slice=C-0")
    work_package_status = manifest.get("status")
    if work_package_status not in ALLOWED_WORK_PACKAGE_STATUSES:
        errors.append(
            "status must be one of "
            f"{sorted(ALLOWED_WORK_PACKAGE_STATUSES)}, got {work_package_status!r}"
        )
    if manifest.get("profiles") != TARGET_PROFILES:
        errors.append("profiles do not match the exact mainland_cn/sea product contract")
    if not isinstance(manifest.get("gate_ready"), bool):
        errors.append("gate_ready must be an explicit boolean")
    coverage = manifest.get("coverage_status")
    if not isinstance(coverage, dict):
        errors.append("coverage_status must be an object")
    elif manifest.get("gate_ready") is False and not coverage.get(
        "pending_before_ctl_c01_review"
    ):
        errors.append("gate_ready=false requires explicit pending_before_ctl_c01_review items")
    elif manifest.get("gate_ready") is True and coverage.get("pending_before_ctl_c01_review"):
        errors.append("gate_ready=true requires pending_before_ctl_c01_review to be empty")

    unknown_policy = manifest.get("unknown_platform_policy", {})
    required_unknown_policy = {
        "mode": "fail_closed",
        "wildcard_retention": False,
        "runtime_plugin_platforms_allowed": False,
        "bundled_platform_plugins_allowed": False,
        "plugin_override_of_retained_builtin_allowed": False,
    }
    for key, expected in required_unknown_policy.items():
        if unknown_policy.get(key) != expected:
            errors.append(f"unknown_platform_policy.{key} must be {expected!r}")

    surfaces = manifest.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        return errors + ["surfaces must be a non-empty list"]

    names: set[str] = set()
    classified: dict[str, str] = {}
    product_shells: set[str] = set()
    declared_runtime_dependency_pairs: set[tuple[str, str]] = set()
    for index, surface in enumerate(surfaces):
        if not isinstance(surface, dict):
            errors.append(f"surfaces[{index}] must be an object")
            continue
        name = surface.get("surface")
        if not isinstance(name, str) or not name:
            errors.append(f"surfaces[{index}].surface must be a non-empty string")
            name = f"<surface-{index}>"
        elif name in names:
            errors.append(f"duplicate surface name: {name}")
        names.add(name)

        missing = REQUIRED_SURFACE_FIELDS - set(surface)
        if missing:
            errors.append(f"{name}: missing fields {sorted(missing)}")
        for field in (
            "product_shells",
            "gateway_platforms",
            "profiles",
            "source_paths",
            "runtime_dependencies",
            "persisted_data",
            "network_hosts",
            "credential_keys",
            "verification",
        ):
            if not isinstance(surface.get(field), list):
                errors.append(f"{name}.{field} must be a list")
        for runtime_dependency in surface.get("runtime_dependencies", []):
            if not isinstance(runtime_dependency, str) or not runtime_dependency:
                errors.append(
                    f"{name}.runtime_dependencies entries must be non-empty strings"
                )
                continue
            declared_runtime_dependency_pairs.add((name, runtime_dependency))
        if not isinstance(surface.get("jobs/home_channel"), dict):
            errors.append(f"{name}.jobs/home_channel must be an object")
        if surface.get("decision") not in ALLOWED_DECISIONS:
            errors.append(f"{name}: unsupported decision {surface.get('decision')!r}")
        if not isinstance(surface.get("reason"), str) or not surface.get("reason"):
            errors.append(f"{name}.reason must be non-empty")
        if not isinstance(surface.get("owner"), str) or not surface.get("owner"):
            errors.append(f"{name}.owner must be non-empty")

        for profile in surface.get("profiles", []):
            if profile not in TARGET_PROFILES:
                errors.append(f"{name}: unknown profile {profile!r}")
        for shell in surface.get("product_shells", []):
            if not isinstance(shell, str):
                errors.append(f"{name}: product shell names must be strings")
            else:
                product_shells.add(shell)
        for platform in surface.get("gateway_platforms", []):
            if not isinstance(platform, str):
                errors.append(f"{name}: gateway platform names must be strings")
                continue
            if platform in classified:
                errors.append(
                    f"gateway platform {platform!r} is classified by both "
                    f"{classified[platform]!r} and {name!r}"
                )
            classified[platform] = name
        for claim in surface.get("source_paths", []):
            if not isinstance(claim, str) or not claim:
                errors.append(f"{name}: source path claims must be non-empty strings")
                continue
            path = Path(claim)
            if path.is_absolute() or ".." in path.parts:
                errors.append(f"{name}: source path must be repository-relative: {claim}")

    if product_shells != {"desktop"}:
        errors.append(f"product shells must be exactly ['desktop'], got {sorted(product_shells)}")
    classified_names = set(classified)
    if classified_names != EXPECTED_CLASSIFIED:
        errors.append(
            "classified gateway set differs from the C contract: "
            f"missing={sorted(EXPECTED_CLASSIFIED - classified_names)}, "
            f"extra={sorted(classified_names - EXPECTED_CLASSIFIED)}"
        )

    for platform in RETAINED_EXTERNAL:
        surface = next(
            (item for item in surfaces if platform in item.get("gateway_platforms", [])),
            None,
        )
        if surface is None:
            continue
        if surface.get("decision") != "retain":
            errors.append(f"retained platform {platform} must have decision=retain")
        if surface.get("profiles") != RETAINED_BY_PROFILE[platform]:
            errors.append(
                f"retained platform {platform} must belong to "
                f"{RETAINED_BY_PROFILE[platform]}"
            )
    for platform in REMOVED_BUILTINS | REMOVED_BUNDLED_PLUGINS:
        surface = next(
            (item for item in surfaces if platform in item.get("gateway_platforms", [])),
            None,
        )
        if surface is None:
            continue
        if surface.get("decision") != "remove" or surface.get("profiles") != []:
            errors.append(f"removed platform {platform} must be decision=remove with no profile")
    local_surface = next(
        (item for item in surfaces if "local" in item.get("gateway_platforms", [])),
        None,
    )
    if local_surface and local_surface.get("decision") != "retain_internal_sentinel":
        errors.append("Platform.LOCAL must remain an internal sentinel")

    platform_sets = manifest.get("platform_sets", {})
    expected_platform_sets = {
        "product_shells": ["desktop"],
        "retained_external": [
            "weixin",
            "qqbot",
            "dingtalk",
            "telegram",
            "whatsapp",
            "email",
        ],
        "internal_sentinels": ["local"],
        "removed_builtin": [
            "discord",
            "feishu",
            "wecom",
            "wecom_callback",
            "sms",
            "slack",
            "signal",
            "matrix",
            "mattermost",
            "bluebubbles",
            "homeassistant",
            "yuanbao",
            "webhook",
            "api_server",
        ],
        "removed_bundled_plugins": ["irc", "teams"],
    }
    if platform_sets != expected_platform_sets:
        errors.append("platform_sets do not match the exact C-track contract")

    known_gaps = manifest.get("surface_known_gaps", {})
    if not isinstance(known_gaps, dict):
        errors.append("surface_known_gaps must be an object")
    else:
        unknown_gap_surfaces = set(known_gaps) - names
        if unknown_gap_surfaces:
            errors.append(
                f"surface_known_gaps has unknown surfaces {sorted(unknown_gap_surfaces)}"
            )
        for surface_name, gaps in known_gaps.items():
            if not isinstance(gaps, list) or not gaps or not all(
                isinstance(gap, str) and gap for gap in gaps
            ):
                errors.append(f"surface_known_gaps.{surface_name} must be non-empty strings")

    field_semantics = manifest.get("field_semantics", {})
    mixed_fields = field_semantics.get("mixed_fields") if isinstance(field_semantics, dict) else None
    required_mixed_fields = {
        "source_paths",
        "runtime_dependencies",
        "persisted_data",
        "network_hosts",
        "credential_keys",
        "jobs/home_channel",
        "verification",
    }
    if not isinstance(mixed_fields, dict) or set(mixed_fields) != required_mixed_fields:
        errors.append("field_semantics.mixed_fields must classify every mixed C-0 field")
    else:
        for field, semantics in mixed_fields.items():
            if not isinstance(semantics, dict) or set(semantics) != {
                "observed_current",
                "target_contract",
                "known_gaps",
            }:
                errors.append(
                    f"field_semantics.mixed_fields.{field} must separate "
                    "observed_current/target_contract/known_gaps"
                )

    references = manifest.get("typed_reference_ledger")
    if not isinstance(references, list) or not references:
        errors.append("typed_reference_ledger must be a non-empty list")
        references = []
    reference_paths: set[str] = set()
    for index, record in enumerate(references):
        if not isinstance(record, dict):
            errors.append(f"typed_reference_ledger[{index}] must be an object")
            continue
        missing = REQUIRED_TYPED_REFERENCE_FIELDS - set(record)
        if missing:
            errors.append(f"typed_reference_ledger[{index}] missing fields {sorted(missing)}")
        path = record.get("path")
        if not isinstance(path, str) or not path:
            errors.append(f"typed_reference_ledger[{index}].path must be non-empty")
        elif path in reference_paths:
            errors.append(f"duplicate typed reference path: {path}")
        else:
            reference_paths.add(path)
        if not isinstance(record.get("edge_types"), list) or not record.get("edge_types"):
            errors.append(f"typed reference {path}.edge_types must be non-empty")
        if not isinstance(record.get("platform_surfaces"), list) or not record.get(
            "platform_surfaces"
        ):
            errors.append(f"typed reference {path}.platform_surfaces must be non-empty")
        if not isinstance(record.get("known_gaps"), list):
            errors.append(f"typed reference {path}.known_gaps must be a list")

    dependencies = manifest.get("dependency_graph")
    if not isinstance(dependencies, list) or not dependencies:
        errors.append("dependency_graph must be a non-empty list")
        dependencies = []
    dependency_ids: set[str] = set()
    dependency_by_id: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(dependencies):
        if not isinstance(record, dict):
            errors.append(f"dependency_graph[{index}] must be an object")
            continue
        missing = REQUIRED_DEPENDENCY_FIELDS - set(record)
        if missing:
            errors.append(f"dependency_graph[{index}] missing fields {sorted(missing)}")
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id:
            errors.append(f"dependency_graph[{index}].id must be non-empty")
        elif record_id in dependency_ids:
            errors.append(f"duplicate dependency id: {record_id}")
        else:
            dependency_ids.add(record_id)
            dependency_by_id[record_id] = record
        if not isinstance(record.get("declaration_paths"), list) or not record.get(
            "declaration_paths"
        ):
            errors.append(f"dependency {record_id}.declaration_paths must be non-empty")
        if not isinstance(record.get("platform_surfaces"), list) or not record.get(
            "platform_surfaces"
        ):
            errors.append(f"dependency {record_id}.platform_surfaces must be non-empty")
        if not isinstance(record.get("users"), list) or not record.get("users"):
            errors.append(f"dependency {record_id}.users must be non-empty")
        if not isinstance(record.get("known_gaps"), list):
            errors.append(f"dependency {record_id}.known_gaps must be a list")
        unknown_surfaces = set(record.get("platform_surfaces", [])) - names
        if unknown_surfaces:
            errors.append(
                f"dependency {record_id}.platform_surfaces has unknown surfaces "
                f"{sorted(unknown_surfaces)}"
            )
        for claim in record.get("declaration_paths", []):
            if not isinstance(claim, str) or not _claim_has_match(root, claim):
                errors.append(f"dependency {record_id}: declaration path has no match: {claim}")
        for claim in record.get("users", []):
            if not isinstance(claim, str) or not _claim_has_match(root, claim):
                errors.append(f"dependency {record_id}: user path has no match: {claim}")
    if dependency_ids != EXPECTED_DEPENDENCY_IDS:
        errors.append(
            "dependency_graph ids differ from the reviewed C-0 closed set: "
            f"missing={sorted(EXPECTED_DEPENDENCY_IDS - dependency_ids)}, "
            f"extra={sorted(dependency_ids - EXPECTED_DEPENDENCY_IDS)}"
        )

    dependency_coverage = manifest.get("surface_dependency_coverage")
    if not isinstance(dependency_coverage, list):
        errors.append("surface_dependency_coverage must be a list")
        dependency_coverage = []
    covered_runtime_dependency_pairs: set[tuple[str, str]] = set()
    for index, record in enumerate(dependency_coverage):
        if not isinstance(record, dict):
            errors.append(f"surface_dependency_coverage[{index}] must be an object")
            continue
        missing = REQUIRED_SURFACE_DEPENDENCY_COVERAGE_FIELDS - set(record)
        if missing:
            errors.append(
                f"surface_dependency_coverage[{index}] missing fields {sorted(missing)}"
            )
        surface_name = record.get("surface")
        runtime_dependency = record.get("runtime_dependency")
        pair = (surface_name, runtime_dependency)
        if surface_name not in names:
            errors.append(
                f"surface_dependency_coverage[{index}].surface is unknown: {surface_name!r}"
            )
        if not isinstance(runtime_dependency, str) or not runtime_dependency:
            errors.append(
                f"surface_dependency_coverage[{index}].runtime_dependency must be non-empty"
            )
        elif pair in covered_runtime_dependency_pairs:
            errors.append(f"duplicate surface dependency coverage: {pair!r}")
        else:
            covered_runtime_dependency_pairs.add(pair)

        dependency_refs = record.get("dependency_ids")
        exemption = record.get("exemption")
        if not isinstance(dependency_refs, list):
            errors.append(
                f"surface_dependency_coverage[{index}].dependency_ids must be a list"
            )
            dependency_refs = []
        if bool(dependency_refs) == (exemption is not None):
            errors.append(
                f"surface dependency {pair!r} must use exactly one of dependency_ids or exemption"
            )
        for dependency_id in dependency_refs:
            dependency_record = dependency_by_id.get(dependency_id)
            if dependency_record is None:
                errors.append(
                    f"surface dependency {pair!r} references unknown dependency {dependency_id!r}"
                )
            elif surface_name not in dependency_record.get("platform_surfaces", []):
                errors.append(
                    f"surface dependency {pair!r} references {dependency_id!r}, but the "
                    "dependency graph does not include that surface"
                )
        if exemption is not None:
            if not isinstance(exemption, dict) or set(exemption) != {"kind", "reason"}:
                errors.append(
                    f"surface dependency {pair!r}.exemption must contain kind/reason"
                )
            else:
                if exemption.get("kind") not in ALLOWED_DEPENDENCY_EXEMPTION_KINDS:
                    errors.append(
                        f"surface dependency {pair!r} has unsupported exemption kind "
                        f"{exemption.get('kind')!r}"
                    )
                if not isinstance(exemption.get("reason"), str) or not exemption.get("reason"):
                    errors.append(
                        f"surface dependency {pair!r}.exemption.reason must be non-empty"
                    )
    if covered_runtime_dependency_pairs != declared_runtime_dependency_pairs:
        errors.append(
            "surface_dependency_coverage differs from surfaces[*].runtime_dependencies: "
            f"missing={sorted(declared_runtime_dependency_pairs - covered_runtime_dependency_pairs)}, "
            f"extra={sorted(covered_runtime_dependency_pairs - declared_runtime_dependency_pairs)}"
        )

    plugin_import_coverage = manifest.get("bundled_plugin_dependency_imports")
    if not isinstance(plugin_import_coverage, list):
        errors.append("bundled_plugin_dependency_imports must be a list")
        plugin_import_coverage = []
    covered_plugin_imports: set[tuple[str, str]] = set()
    for index, record in enumerate(plugin_import_coverage):
        if not isinstance(record, dict):
            errors.append(f"bundled_plugin_dependency_imports[{index}] must be an object")
            continue
        missing = REQUIRED_PLUGIN_IMPORT_COVERAGE_FIELDS - set(record)
        if missing:
            errors.append(
                f"bundled_plugin_dependency_imports[{index}] missing fields {sorted(missing)}"
            )
        pair = (record.get("surface"), record.get("import_root"))
        if pair in covered_plugin_imports:
            errors.append(f"duplicate bundled plugin import coverage: {pair!r}")
        else:
            covered_plugin_imports.add(pair)
        dependency_id = record.get("dependency_id")
        dependency_record = dependency_by_id.get(dependency_id)
        if dependency_record is None:
            errors.append(
                f"bundled plugin import {pair!r} references unknown dependency {dependency_id!r}"
            )
        elif pair[0] not in dependency_record.get("platform_surfaces", []):
            errors.append(
                f"bundled plugin import {pair!r} references {dependency_id!r}, but the "
                "dependency graph does not include that surface"
            )
    if scan_repository:
        observed_plugin_imports = {
            (record["surface"], record["import_root"])
            for record in collect_bundled_plugin_external_imports(root)
        }
        if covered_plugin_imports != observed_plugin_imports:
            errors.append(
                "bundled plugin dependency imports differ from observed source: "
                f"missing={sorted(observed_plugin_imports - covered_plugin_imports)}, "
                f"extra={sorted(covered_plugin_imports - observed_plugin_imports)}"
            )

    credential_graph = manifest.get("credential_data_graph")
    if not isinstance(credential_graph, dict):
        errors.append("credential_data_graph must be an object")
        credential_graph = {}
    if credential_graph.get("environment_discovery") != ENVIRONMENT_DISCOVERY_CONTRACT:
        errors.append(
            "credential_data_graph.environment_discovery must match the exact "
            "discovery-first fail-closed contract"
        )
    credential_edges = credential_graph.get("environment_key_edges")
    if not isinstance(credential_edges, list) or not credential_edges:
        errors.append("credential_data_graph.environment_key_edges must be non-empty")
        credential_edges = []
    credential_keys: set[str] = set()
    for index, record in enumerate(credential_edges):
        if not isinstance(record, dict):
            errors.append(f"environment_key_edges[{index}] must be an object")
            continue
        missing = REQUIRED_CREDENTIAL_EDGE_FIELDS - set(record)
        if missing:
            errors.append(f"environment_key_edges[{index}] missing fields {sorted(missing)}")
        key = record.get("key")
        if not isinstance(key, str) or not key:
            errors.append(f"environment_key_edges[{index}].key must be non-empty")
        elif key in credential_keys:
            errors.append(f"duplicate environment key edge: {key}")
        else:
            credential_keys.add(key)
        if not isinstance(record.get("source_paths"), list) or not record.get("source_paths"):
            errors.append(f"environment key {key}.source_paths must be non-empty")
        if not isinstance(record.get("known_gaps"), list):
            errors.append(f"environment key {key}.known_gaps must be a list")

    namespace_edges = credential_graph.get("environment_namespace_edges")
    if not isinstance(namespace_edges, list) or not namespace_edges:
        errors.append(
            "credential_data_graph.environment_namespace_edges must be non-empty"
        )
        namespace_edges = []
    environment_prefixes: set[str] = set()
    for index, record in enumerate(namespace_edges):
        if not isinstance(record, dict):
            errors.append(f"environment_namespace_edges[{index}] must be an object")
            continue
        missing = REQUIRED_ENVIRONMENT_NAMESPACE_EDGE_FIELDS - set(record)
        if missing:
            errors.append(
                f"environment_namespace_edges[{index}] missing fields {sorted(missing)}"
            )
        prefix = record.get("prefix")
        if not isinstance(prefix, str) or not prefix:
            errors.append(
                f"environment_namespace_edges[{index}].prefix must be non-empty"
            )
        elif prefix in environment_prefixes:
            errors.append(f"duplicate environment namespace edge: {prefix}")
        else:
            environment_prefixes.add(prefix)
        if record.get("pattern") != f"{prefix}*":
            errors.append(
                f"environment namespace {prefix}.pattern must be the exact prefix plus '*'"
            )
        if not isinstance(record.get("source_paths"), list) or not record.get(
            "source_paths"
        ):
            errors.append(
                f"environment namespace {prefix}.source_paths must be non-empty"
            )
        if not isinstance(record.get("known_gaps"), list):
            errors.append(f"environment namespace {prefix}.known_gaps must be a list")

    dynamic_templates = credential_graph.get("environment_dynamic_key_templates")
    if not isinstance(dynamic_templates, list) or not dynamic_templates:
        errors.append(
            "credential_data_graph.environment_dynamic_key_templates must be non-empty"
        )
        dynamic_templates = []
    environment_templates: set[str] = set()
    for index, record in enumerate(dynamic_templates):
        if not isinstance(record, dict):
            errors.append(f"environment_dynamic_key_templates[{index}] must be an object")
            continue
        missing = REQUIRED_ENVIRONMENT_DYNAMIC_TEMPLATE_FIELDS - set(record)
        if missing:
            errors.append(
                f"environment_dynamic_key_templates[{index}] missing fields {sorted(missing)}"
            )
        template = record.get("template")
        if not isinstance(template, str) or "{PLATFORM}" not in template:
            errors.append(
                f"environment_dynamic_key_templates[{index}].template must contain {{PLATFORM}}"
            )
        elif template in environment_templates:
            errors.append(f"duplicate dynamic environment template: {template}")
        else:
            environment_templates.add(template)
        known_platforms = record.get("known_platforms")
        exact_expansion = record.get("exact_expansion")
        if not isinstance(known_platforms, list) or not known_platforms:
            errors.append(f"dynamic environment template {template}.known_platforms must be non-empty")
        if not isinstance(exact_expansion, list) or not exact_expansion:
            errors.append(f"dynamic environment template {template}.exact_expansion must be non-empty")
        elif set(exact_expansion) - credential_keys:
            errors.append(
                f"dynamic environment template {template} has expansions missing from exact ledger: "
                f"{sorted(set(exact_expansion) - credential_keys)}"
            )
        if not isinstance(record.get("source_paths"), list) or not record.get("source_paths"):
            errors.append(f"dynamic environment template {template}.source_paths must be non-empty")
        if not isinstance(record.get("known_gaps"), list):
            errors.append(f"dynamic environment template {template}.known_gaps must be a list")

    generated_metadata = manifest.get("generated_ledger_metadata")
    if not isinstance(generated_metadata, dict):
        errors.append("generated_ledger_metadata must be an object")
        generated_metadata = {}
    if generated_metadata.get("reference_path_count") != len(references):
        errors.append(
            "generated_ledger_metadata.reference_path_count must equal the typed "
            "reference ledger length"
        )
    if generated_metadata.get("environment_key_count") != len(credential_edges):
        errors.append(
            "generated_ledger_metadata.environment_key_count must equal the exact "
            "environment-key ledger length"
        )
    if generated_metadata.get("environment_namespace_count") != len(namespace_edges):
        errors.append(
            "generated_ledger_metadata.environment_namespace_count must equal the "
            "environment-namespace ledger length"
        )
    if generated_metadata.get("environment_dynamic_template_count") != len(
        dynamic_templates
    ):
        errors.append(
            "generated_ledger_metadata.environment_dynamic_template_count must equal "
            "the dynamic environment-template ledger length"
        )
    for count_field in (
        "literal_environment_key_count",
        "dynamic_environment_key_declaration_count",
    ):
        count = generated_metadata.get(count_field)
        if not isinstance(count, int) or count <= 0:
            errors.append(
                f"generated_ledger_metadata.{count_field} must be a positive integer"
            )

    persisted_records = credential_graph.get("persisted_records")
    if not isinstance(persisted_records, list) or not persisted_records:
        errors.append("credential_data_graph.persisted_records must be non-empty")
        persisted_records = []
    persisted_ids: set[str] = set()
    for index, record in enumerate(persisted_records):
        if not isinstance(record, dict):
            errors.append(f"persisted_records[{index}] must be an object")
            continue
        missing = REQUIRED_PERSISTED_RECORD_FIELDS - set(record)
        if missing:
            errors.append(f"persisted_records[{index}] missing fields {sorted(missing)}")
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id:
            errors.append(f"persisted_records[{index}].id must be non-empty")
        elif record_id in persisted_ids:
            errors.append(f"duplicate persisted record id: {record_id}")
        else:
            persisted_ids.add(record_id)
        raw_surfaces = record.get("surface")
        if not isinstance(raw_surfaces, str) or not raw_surfaces.strip():
            errors.append(f"persisted record {record_id}.surface must be non-empty")
        else:
            record_surfaces = {
                surface.strip() for surface in raw_surfaces.split(",") if surface.strip()
            }
            unknown_surfaces = record_surfaces - names
            if unknown_surfaces:
                errors.append(
                    f"persisted record {record_id}.surface has unknown surfaces "
                    f"{sorted(unknown_surfaces)}"
                )
        if not isinstance(record.get("known_gaps"), list):
            errors.append(f"persisted record {record_id}.known_gaps must be a list")
    if persisted_ids != EXPECTED_PERSISTED_RECORD_IDS:
        errors.append(
            "persisted record ids differ from the reviewed C-0 closed set: "
            f"missing={sorted(EXPECTED_PERSISTED_RECORD_IDS - persisted_ids)}, "
            f"extra={sorted(persisted_ids - EXPECTED_PERSISTED_RECORD_IDS)}"
        )

    verification_records = manifest.get("verification_records")
    if not isinstance(verification_records, list) or not verification_records:
        errors.append("verification_records must be a non-empty list")
        verification_records = []
    verification_ids: set[str] = set()
    for index, record in enumerate(verification_records):
        if not isinstance(record, dict):
            errors.append(f"verification_records[{index}] must be an object")
            continue
        missing = REQUIRED_VERIFICATION_FIELDS - set(record)
        if missing:
            errors.append(f"verification_records[{index}] missing fields {sorted(missing)}")
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id:
            errors.append(f"verification_records[{index}].id must be non-empty")
        elif record_id in verification_ids:
            errors.append(f"duplicate verification id: {record_id}")
        else:
            verification_ids.add(record_id)
        if record.get("owner_status") != "accepted":
            errors.append(f"verification {record_id}.owner_status must be accepted")
        if record.get("status") not in {"passed", "blocked_with_evidence", "pending_reviewer"}:
            errors.append(f"verification {record_id}.status is not explicit")

    if scan_repository:
        discovered_core = set(discover_core_platforms(root))
        if discovered_core - classified_names:
            errors.append(
                f"unclassified core Platform values: {sorted(discovered_core - classified_names)}"
            )
        if discovered_core - EXPECTED_BUILTINS:
            errors.append(
                f"unknown core Platform values: {sorted(discovered_core - EXPECTED_BUILTINS)}"
            )
        discovered_plugins = set(discover_bundled_platform_plugins(root))
        if discovered_plugins - classified_names:
            errors.append(
                "unclassified bundled platform plugins: "
                f"{sorted(discovered_plugins - classified_names)}"
            )
        if discovered_plugins - REMOVED_BUNDLED_PLUGINS:
            errors.append(
                "unknown bundled platform plugins: "
                f"{sorted(discovered_plugins - REMOVED_BUNDLED_PLUGINS)}"
            )

        errors.extend(_source_ownership_issues(manifest, root))
        errors.extend(_core_reference_issues(manifest, root))
        errors.extend(_bundle_reference_issues(manifest, root))
        actual_references = collect_typed_reference_ledger(root)
        if references != actual_references:
            errors.append(
                "typed_reference_ledger drift: run "
                "scripts/audit_v050_platform_manifest.py --refresh-generated-ledgers"
            )
        errors.extend(credential_environment_ledger_issues(manifest, root))
        actual_literal_environment_count = len(discover_environment_key_accesses(root))
        actual_dynamic_environment_count = len(
            discover_environment_declarations(root)["exact_keys"]
        )
        if generated_metadata.get("literal_environment_key_count") != (
            actual_literal_environment_count
        ):
            errors.append(
                "generated literal environment-key count drift: "
                f"recorded={generated_metadata.get('literal_environment_key_count')}, "
                f"actual={actual_literal_environment_count}"
            )
        if generated_metadata.get("dynamic_environment_key_declaration_count") != (
            actual_dynamic_environment_count
        ):
            errors.append(
                "generated dynamic environment-key declaration count drift: "
                "recorded="
                f"{generated_metadata.get('dynamic_environment_key_declaration_count')}, "
                f"actual={actual_dynamic_environment_count}"
            )

    shared_inventory = manifest.get("shared_cross_layer_inventory")
    if not isinstance(shared_inventory, list) or not shared_inventory:
        errors.append("shared_cross_layer_inventory must be a non-empty list")
        shared_inventory = []
    shared_ids: set[str] = set()
    for index, item in enumerate(shared_inventory):
        if not isinstance(item, dict):
            errors.append(f"shared_cross_layer_inventory[{index}] must be an object")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            errors.append(f"shared_cross_layer_inventory[{index}].id must be non-empty")
            continue
        if item_id in shared_ids:
            errors.append(f"duplicate shared inventory id: {item_id}")
        shared_ids.add(item_id)
        for key in (
            "owner",
            "owner_status",
            "lifecycle_slices",
            "affected_platform_set",
            "roles",
            "paths",
            "verification",
            "evidence_status",
        ):
            if key not in item:
                errors.append(f"shared inventory {item_id}: missing {key}")
        if not isinstance(item.get("paths"), list) or not item.get("paths"):
            errors.append(f"shared inventory {item_id}.paths must be non-empty")
        if manifest.get("gate_ready") and item.get("owner_status") != "accepted":
            errors.append(f"shared inventory {item_id}.owner_status must be accepted at REVIEW")

    links = manifest.get("surface_reference_links")
    if not isinstance(links, dict):
        errors.append("surface_reference_links must be an object")
        links = {}
    if set(links) != names:
        errors.append(
            "surface_reference_links keys must match surface names: "
            f"missing={sorted(names - set(links))}, extra={sorted(set(links) - names)}"
        )
    for surface_name, reference_ids in links.items():
        if not isinstance(reference_ids, list) or not reference_ids:
            errors.append(f"surface_reference_links.{surface_name} must be a non-empty list")
            continue
        unknown_ids = set(reference_ids) - shared_ids
        if unknown_ids:
            errors.append(
                f"surface_reference_links.{surface_name} has unknown ids {sorted(unknown_ids)}"
            )

    signoffs = manifest.get("review_signoff")
    if not isinstance(signoffs, list):
        errors.append("review_signoff must be a list")
        signoffs = []
    signoff_roles: set[str] = set()
    for index, item in enumerate(signoffs):
        if not isinstance(item, dict):
            errors.append(f"review_signoff[{index}] must be an object")
            continue
        role = item.get("role")
        status = item.get("status")
        if not isinstance(role, str) or not role:
            errors.append(f"review_signoff[{index}].role must be non-empty")
        elif role in signoff_roles:
            errors.append(f"duplicate review_signoff role: {role}")
        else:
            signoff_roles.add(role)
        if status not in ALLOWED_SIGNOFF_STATUSES:
            errors.append(
                f"review_signoff[{index}].status must be one of "
                f"{sorted(ALLOWED_SIGNOFF_STATUSES)}, got {status!r}"
            )
        if status == "approved":
            for field in ("reviewer", "evidence"):
                if not isinstance(item.get(field), str) or not item.get(field):
                    errors.append(
                        f"review_signoff[{index}].{field} must be non-empty when approved"
                    )
        if status == "changes_requested" and (
            not isinstance(item.get("findings"), list) or not item.get("findings")
        ):
            errors.append(
                f"review_signoff[{index}].findings must be non-empty when changes_requested"
            )
    if signoff_roles != REQUIRED_SIGNOFF_ROLES:
        errors.append(
            "review_signoff roles differ from the cross-layer gate: "
            f"missing={sorted(REQUIRED_SIGNOFF_ROLES - signoff_roles)}, "
            f"extra={sorted(signoff_roles - REQUIRED_SIGNOFF_ROLES)}"
        )
    approved_roles = {
        item.get("role")
        for item in signoffs
        if isinstance(item, dict) and item.get("status") == "approved"
    }
    pending_done_items = (
        coverage.get("pending_before_ctl_c01_done", [])
        if isinstance(coverage, dict)
        else []
    )
    if work_package_status == "done":
        if approved_roles != REQUIRED_SIGNOFF_ROLES:
            errors.append(
                "status=done requires all cross-layer review_signoff roles approved: "
                f"missing={sorted(REQUIRED_SIGNOFF_ROLES - approved_roles)}"
            )
        if pending_done_items:
            errors.append(
                "status=done requires pending_before_ctl_c01_done to be empty"
            )
    elif approved_roles == REQUIRED_SIGNOFF_ROLES and not pending_done_items:
        errors.append(
            "all cross-layer signoffs are approved with no pending DONE items; "
            "status must be done"
        )

    if manifest.get("base", {}).get("git_commit") != manifest.get("baseline", {}).get(
        "source_commit"
    ):
        errors.append("base.git_commit and baseline.source_commit must match")
    return errors


def _load_source_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _literal_assignment(path: Path, name: str) -> Any:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        target_name: str | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            if isinstance(node.targets[0], ast.Name):
                target_name = node.targets[0].id
                value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target_name = node.target.id
            value = node.value
        if target_name == name and value is not None:
            return ast.literal_eval(value)
    raise RuntimeError(f"assignment {name} not found in {path}")


def _assignment_value(path: Path, name: str) -> ast.expr:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            if isinstance(node.targets[0], ast.Name) and node.targets[0].id == name:
                return node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == name and node.value is not None:
                return node.value
    raise RuntimeError(f"assignment {name} not found in {path}")


def _string_collection_from_ast(node: ast.expr) -> list[str]:
    if isinstance(node, ast.Dict):
        return [
            key.value
            for key in node.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        ]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values: list[str] = []
        for item in node.elts:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                values.append(item.value)
            elif isinstance(item, ast.Tuple) and item.elts:
                first = item.elts[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    values.append(first.value)
        return values
    if isinstance(node, ast.Call) and node.args:
        return _string_collection_from_ast(node.args[0])
    raise RuntimeError(f"unsupported string collection AST: {ast.dump(node, include_attributes=False)}")


def _string_collection_assignment(path: Path, name: str) -> list[str]:
    return _string_collection_from_ast(_assignment_value(path, name))


def collect_core_observed(root: Path = ROOT) -> dict[str, Any]:
    display = root / "hermes_core" / "gateway" / "display_config.py"
    scheduler = root / "hermes_core" / "cron" / "scheduler.py"
    cli_platforms = root / "hermes_core" / "kabuqina_cli" / "platforms.py"
    cli_raw = _string_collection_assignment(cli_platforms, "PLATFORMS")
    return {
        "builtin_platforms": discover_core_platforms(root),
        "bundled_plugin_platforms": discover_bundled_platform_plugins(root),
        "display_default_platforms": _string_collection_assignment(
            display, "_PLATFORM_DEFAULTS"
        ),
        "cron_known_delivery_platforms": _string_collection_assignment(
            scheduler, "_KNOWN_DELIVERY_PLATFORMS"
        ),
        "cron_home_target_platforms": _string_collection_assignment(
            scheduler, "_HOME_TARGET_ENV_VARS"
        ),
        "cli_platform_registry": cli_raw,
        "cli_platform_aliases_and_pseudos": {
            "cli": "local",
            "cron": "non-gateway tool context",
        },
        "_discovered_ids": sorted(
            {
                _canonical_platform_id(name)
                for name in (
                    _string_collection_assignment(display, "_PLATFORM_DEFAULTS")
                    + _string_collection_assignment(scheduler, "_KNOWN_DELIVERY_PLATFORMS")
                    + _string_collection_assignment(scheduler, "_HOME_TARGET_ENV_VARS")
                    + [name for name in cli_raw if name != "cron"]
                )
            }
        ),
    }


def collect_python_observed(root: Path = ROOT) -> dict[str, Any]:
    product = _load_source_module(
        "_kq_c0_product_profile_policy", root / "python" / "src" / "product_profile_policy.py"
    )
    gateway = _load_source_module(
        "_kq_c0_gateway_policy", root / "python" / "src" / "gateway_policy.py"
    )
    policy = gateway.GatewayPolicy()

    env_loader_path = root / "python" / "src" / "gateway_env_loader.py"
    credential_hosts = _literal_assignment(env_loader_path, "_CREDENTIAL_API_HOSTS")
    families: list[str] = []
    for credential_keys, _ in credential_hosts:
        first = credential_keys[0]
        if first.startswith("WECOM_CALLBACK_"):
            family = "wecom_callback"
        elif first.startswith("WECOM_"):
            family = "wecom"
        elif first.startswith("FEISHU_"):
            family = "feishu"
        elif first.startswith("WEIXIN_"):
            family = "weixin"
        elif first.startswith(("QQ_", "QQBOT_")):
            family = "qqbot"
        else:
            family = first.split("_", 1)[0].lower()
        families.append(family)
    loader_text = env_loader_path.read_text(encoding="utf-8")

    return {
        "visible_gateways": {
            profile: list(product.ProductProfilePolicy.visible_gateways(profile))
            for profile in TARGET_PROFILES
        },
        "autostart_gateways": {
            profile: list(
                product._for_profile(product._AUTOSTART_GATEWAYS, profile)  # noqa: SLF001
            )
            for profile in TARGET_PROFILES
        },
        "gateway_policy_platforms": list(policy.platforms),
        "gateway_policy_flags": {
            "weixin": policy.weixin_enabled,
            "feishu": policy.feishu_enabled,
            "dingtalk": policy.dingtalk_enabled,
        },
        "network_credential_host_families": _ordered_unique(families),
        "generic_url_host_expansion": (
            "for key, value in os.environ.items()" in loader_text
            and "ku.endswith(suffix)" in loader_text
        ),
    }


def _strip_c_style_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", text)


def _canonical_platform_id(name: str) -> str:
    aliases = {
        "qq": "qqbot",
        "cli": "local",
    }
    return aliases.get(name, name)


def _rust_const_platforms(text: str, const_name: str) -> list[str]:
    match = re.search(
        rf"const\s+{re.escape(const_name)}\s*:.*?=\s*&\[(.*?)\];",
        text,
        flags=re.DOTALL,
    )
    if not match:
        raise RuntimeError(f"Rust constant {const_name} not found")
    return re.findall(r"\(\s*\"([a-z0-9_]+)\"\s*,", match.group(1))


def _rust_string_slice(text: str, const_name: str) -> list[str]:
    match = re.search(
        rf"const\s+{re.escape(const_name)}\s*:.*?=\s*&\[(.*?)\];",
        text,
        flags=re.DOTALL,
    )
    if not match:
        raise RuntimeError(f"Rust constant {const_name} not found")
    return re.findall(r'"([a-z0-9_]+)"', match.group(1))


def collect_rust_observed(root: Path = ROOT) -> dict[str, Any]:
    supervisor = _strip_c_style_comments(
        (root / "tauri" / "src" / "gateway_supervisor.rs").read_text(encoding="utf-8")
    )
    credentials = _rust_const_platforms(supervisor, "PLATFORM_CREDENTIAL_KEYS")
    extras = _rust_const_platforms(supervisor, "PLATFORM_EXTRA_KEYS")
    autostart = _rust_string_slice(supervisor, "AUTOSTART_ALLOWED_MAINLAND_CN")
    prefix_match = re.search(
        r"fn\s+platform_env_prefixes\s*\(.*?\)\s*->.*?\{\s*match\s+platform\s*\{(.*?)\n\s*\}\s*\n\s*\}",
        supervisor,
        flags=re.DOTALL,
    )
    if not prefix_match:
        raise RuntimeError("Rust platform_env_prefixes match not found")
    env_prefix_platforms = re.findall(
        r'"([a-z0-9_]+)"\s*=>', prefix_match.group(1)
    )
    lib_text = _strip_c_style_comments(
        (root / "tauri" / "src" / "lib.rs").read_text(encoding="utf-8")
    )
    module_platforms = {
        path.stem.rsplit("_", 1)[0]
        for pattern in ("*_env.rs", "*_qr.rs", "*_oauth.rs")
        for path in (root / "tauri" / "src").glob(pattern)
    }
    registered_modules = {
        module
        for module in re.findall(r"\b([a-z][a-z0-9_]*)::cmd_[a-z0-9_]+", lib_text)
        if module.rsplit("_", 1)[0] in module_platforms
    }
    commands = sorted(
        {
            _canonical_platform_id(module.rsplit("_", 1)[0])
            for module in registered_modules
        }
    )
    discovered_ids = {
        _canonical_platform_id(name)
        for name in credentials + extras + env_prefix_platforms
    } | {
        _canonical_platform_id(name) for name in module_platforms
    }
    return {
        "credential_discovery_platforms": credentials,
        "extra_key_platforms": extras,
        "profile_env_prefix_platforms": env_prefix_platforms,
        "autostart_gateways": {
            "mainland_cn": autostart,
            "sea": autostart,
        },
        "registered_platform_commands": commands,
        "command_aliases": {"qq": "qqbot"},
        "_discovered_ids": sorted(discovered_ids),
    }


def _normalize_web_platform(name: str) -> str:
    return _canonical_platform_id(name)


def _typescript_object_keys(text: str, const_name: str) -> list[str]:
    match = re.search(
        rf"(?:export\s+)?const\s+{re.escape(const_name)}[^=]*=\s*\{{(.*?)\n\}};",
        text,
        flags=re.DOTALL,
    )
    if not match:
        raise RuntimeError(f"TypeScript object {const_name} not found")
    return re.findall(r"^\s*([a-z][a-z0-9_]*)\s*:", match.group(1), flags=re.MULTILINE)


def collect_web_observed(root: Path = ROOT) -> dict[str, Any]:
    nav_text = (root / "web" / "src" / "advanced" / "settings" / "SettingsGateway.tsx").read_text(
        encoding="utf-8"
    )
    nav_keys = re.findall(r'\{\s*key:\s*"([a-z0-9_]+)"[^\n]*path:', nav_text)
    nav = [_normalize_web_platform(name) for name in nav_keys]

    main_text = (root / "web" / "src" / "main.tsx").read_text(encoding="utf-8")
    imported_pages = {
        component: relative
        for component, relative in re.findall(
            r'import\s+\{\s*([A-Za-z0-9_]+Page)\s*\}\s+from\s+"([^"]+)"',
            main_text,
        )
    }
    platform_page_components: set[str] = set()
    for component, relative in imported_pages.items():
        page_path = (root / "web" / "src" / relative).with_suffix(".tsx")
        if page_path.is_file() and "<PlatformPage" in page_path.read_text(encoding="utf-8"):
            platform_page_components.add(component)
    route_keys = [
        slug
        for slug, component in re.findall(
            r'<Route\s+path="/settings/([a-z0-9_]+)"\s+element=\{<([A-Za-z0-9_]+)',
            main_text,
        )
        if component in platform_page_components
    ]
    routes = [_normalize_web_platform(name) for name in route_keys]

    onboarding_text = (
        root / "web" / "src" / "onboarding" / "setupCatalog" / "optionData.ts"
    ).read_text(encoding="utf-8")
    catalog_match = re.search(
        r"export\s+const\s+CATALOG_GATEWAY.*?=\s*\[(.*?)\n\];",
        onboarding_text,
        flags=re.DOTALL,
    )
    if not catalog_match:
        raise RuntimeError("Web CATALOG_GATEWAY not found")
    catalog_pairs = re.findall(
        r'id:\s*"([a-z0-9_]+)".*?configUi:\s*"([a-z0-9_]+)_route_c"',
        catalog_match.group(1),
        flags=re.DOTALL,
    )
    onboarding_ids = [item_id for item_id, _ in catalog_pairs]
    onboarding = [
        _normalize_web_platform(config_ui) for _, config_ui in catalog_pairs
    ]

    registry_text = (
        root / "web" / "src" / "lib" / "gatewayPlatformSettingsRegistry.ts"
    ).read_text(encoding="utf-8")
    registry = _ordered_unique(re.findall(r'platform:\s*"([a-z0-9_]+)"', registry_text))
    host_prefix_keys = _typescript_object_keys(registry_text, "HOST_ENV_PREFIXES")

    command_ids: set[str] = set()
    command_pseudos: set[str] = set()
    for path in (root / "web" / "src").rglob("*"):
        if not path.is_file() or path.suffix not in {".ts", ".tsx"}:
            continue
        text = path.read_text(encoding="utf-8")
        for command in re.findall(r'"cmd_([a-z][a-z0-9_]*)"', text):
            parts = command.split("_")
            action_index = next(
                (
                    index
                    for index, part in enumerate(parts)
                    if part in {"env", "qr", "oauth", "save", "remove"}
                ),
                None,
            )
            if action_index is None or action_index == 0:
                continue
            prefix = "_".join(parts[:action_index])
            if prefix == "gateway_host":
                command_pseudos.add(prefix)
            else:
                command_ids.add(prefix)
    command_platforms = sorted({_normalize_web_platform(name) for name in command_ids})
    discovered_ids = {
        _normalize_web_platform(name)
        for name in nav_keys
        + route_keys
        + onboarding_ids
        + registry
        + host_prefix_keys
        + list(command_ids)
    }
    return {
        "settings_navigation_keys": nav_keys,
        "settings_navigation": nav,
        "settings_route_keys": route_keys,
        "settings_routes": routes,
        "onboarding_catalog_ids": onboarding_ids,
        "onboarding_catalog": onboarding,
        "host_env_prefix_registry": host_prefix_keys,
        "environment_registry": registry,
        "tauri_command_platforms": command_platforms,
        "tauri_command_pseudos": sorted(command_pseudos),
        "platform_aliases": {"qq": "qqbot"},
        "_discovered_ids": sorted(discovered_ids),
    }


def _compare_observed_section(
    section_name: str,
    expected: dict[str, Any],
    actual: dict[str, Any],
    errors: list[str],
) -> None:
    for key, actual_value in actual.items():
        if expected.get(key) != actual_value:
            errors.append(
                f"observed_state.{section_name}.{key} drift: "
                f"expected={expected.get(key)!r} actual={actual_value!r}"
            )


def _claim_has_match(root: Path, claim: str) -> bool:
    normalized = claim.replace("\\", "/")
    if any(char in normalized for char in "*?["):
        return any(root.glob(normalized))
    return (root / normalized).exists()


def validate_observed_snapshot(
    manifest: dict[str, Any], root: Path = ROOT
) -> list[str]:
    errors: list[str] = []
    observed = manifest.get("observed_state", {})
    _compare_observed_section(
        "python", observed.get("python", {}), collect_python_observed(root), errors
    )
    rust_actual = collect_rust_observed(root)
    rust_discovered = set(rust_actual.pop("_discovered_ids", []))
    rust_unknown = rust_discovered - EXPECTED_CLASSIFIED
    if rust_unknown:
        errors.append(f"unknown Rust platform producers: {sorted(rust_unknown)}")
    _compare_observed_section("rust", observed.get("rust", {}), rust_actual, errors)

    web_actual = collect_web_observed(root)
    web_discovered = set(web_actual.pop("_discovered_ids", []))
    web_unknown = web_discovered - EXPECTED_CLASSIFIED
    if web_unknown:
        errors.append(f"unknown Web platform producers/consumers: {sorted(web_unknown)}")
    _compare_observed_section("web", observed.get("web", {}), web_actual, errors)
    core_actual = collect_core_observed(root)
    core_discovered = set(core_actual.pop("_discovered_ids", []))
    core_unknown = core_discovered - EXPECTED_CLASSIFIED
    if core_unknown:
        errors.append(f"unknown Core registry platform ids: {sorted(core_unknown)}")
    _compare_observed_section("core", observed.get("core", {}), core_actual, errors)

    for surface, claim in _all_source_claims(manifest) + _shared_inventory_claims(manifest):
        if not _claim_has_match(root, claim):
            errors.append(f"{surface}: recorded C-0 source path has no match: {claim}")

    for snapshot in manifest.get("base", {}).get("authority_snapshots", []):
        relative = snapshot.get("path", "")
        path = root / relative
        if not path.is_file():
            errors.append(f"authority document missing: {relative}")
            continue
        actual_hash = sha256_file(path)
        if actual_hash.lower() != str(snapshot.get("sha256", "")).lower():
            errors.append(
                f"authority document hash drift: {relative} "
                f"expected={snapshot.get('sha256')} actual={actual_hash}"
            )
        actual_state = _git_state(root, relative)
        if actual_state != snapshot.get("git_state"):
            errors.append(
                f"authority git-state drift: {relative} "
                f"expected={snapshot.get('git_state')} actual={actual_state}"
            )

    head = _run_git(root, "rev-parse", "HEAD")
    if head.returncode != 0:
        errors.append(f"cannot resolve git HEAD: {head.stderr.strip()}")
    else:
        actual_head = head.stdout.strip()
        base_commit = manifest.get("base", {}).get("git_commit")
        ancestor = _run_git(root, "merge-base", "--is-ancestor", str(base_commit), actual_head)
        if ancestor.returncode != 0:
            errors.append(
                "C-0 base is not an ancestor of HEAD: "
                f"base={base_commit} actual={actual_head}"
            )
        elif actual_head != base_commit:
            changed = _run_git(root, "diff", "--name-only", f"{base_commit}..{actual_head}")
            if changed.returncode != 0:
                errors.append(f"cannot list C-0 activation delta: {changed.stderr.strip()}")
            else:
                changed_paths = {
                    line.strip().replace("\\", "/")
                    for line in changed.stdout.splitlines()
                    if line.strip()
                }
                unexpected = changed_paths - ACTIVATION_ALLOWED_PATHS
                if unexpected:
                    errors.append(
                        "C-0 activation delta escaped allowed audit paths: "
                        f"{sorted(unexpected)}"
                    )
    return errors


def _runtime_module_exists(runtime: Path, name: str) -> bool:
    roots = [runtime / "site-packages", runtime / "python" / "Lib" / "site-packages"]
    return any((root / name).exists() or (root / f"{name}.py").exists() for root in roots)


def validate_local_artifacts(
    manifest: dict[str, Any], root: Path = ROOT
) -> list[str]:
    errors: list[str] = []
    baseline = manifest.get("baseline", {})
    runtime_record = baseline.get("runtime", {})
    runtime = root / runtime_record.get("path", "")
    if not runtime.is_dir():
        return [f"recorded runtime is missing: {runtime}"]

    info_path = runtime / "BUNDLE_INFO.json"
    if not info_path.is_file():
        errors.append(f"runtime metadata is missing: {info_path}")
    else:
        info = json.loads(info_path.read_text(encoding="utf-8"))
        runtime_pairs = {
            "bundle_info_built_at": info.get("builtAt"),
            "bundle_info_frozen_commit": info.get("frozenCommit"),
            "python_version": info.get("pythonVersion"),
            "recorded_bundle_size_mb": info.get("bundleSizeMb"),
        }
        for key, actual in runtime_pairs.items():
            if runtime_record.get(key) != actual:
                errors.append(
                    f"baseline.runtime.{key} drift: "
                    f"expected={runtime_record.get(key)!r} actual={actual!r}"
                )

    platform_dir = runtime / "kabuqina" / "gateway" / "platforms"
    source_claims = _all_source_claims(manifest)
    surface_platforms = {
        item["surface"]: item.get("gateway_platforms", [])
        for item in manifest.get("surfaces", [])
    }
    runtime_platform_set: set[str] = set()
    if not platform_dir.is_dir():
        errors.append(f"runtime platform directory is missing: {platform_dir}")
    else:
        for runtime_file in platform_dir.rglob("*"):
            if (
                not runtime_file.is_file()
                or "__pycache__" in runtime_file.parts
                or runtime_file.suffix.lower() in {".pyc", ".pyo"}
            ):
                continue
            source_relative = (
                Path("hermes_core/gateway/platforms")
                / runtime_file.relative_to(platform_dir)
            ).as_posix()
            owners = {
                owner
                for owner, claim in source_claims
                if _source_claim_matches(claim, source_relative)
            }
            if not owners:
                errors.append(f"unclassified runtime platform file: {runtime_file}")
                continue
            if len(owners) > 1:
                errors.append(
                    f"multiply-owned runtime platform file: {runtime_file} owners={sorted(owners)}"
                )
                continue
            owner = next(iter(owners))
            runtime_platform_set.update(surface_platforms.get(owner, []))
    adapters = [
        platform
        for platform in discover_core_platforms(root)
        if platform != "local" and platform in runtime_platform_set
    ]
    if adapters != runtime_record.get("adapter_platforms_present"):
        errors.append(
            "baseline.runtime.adapter_platforms_present drift: "
            f"expected={runtime_record.get('adapter_platforms_present')!r} actual={adapters!r}"
        )

    qr_workers = sorted(
        path.name.removesuffix("_qr_worker.py") for path in runtime.glob("*_qr_worker.py")
    )
    if qr_workers != runtime_record.get("qr_workers_present"):
        errors.append(
            "baseline.runtime.qr_workers_present drift: "
            f"expected={runtime_record.get('qr_workers_present')!r} actual={qr_workers!r}"
        )

    plugin_dir = runtime / "kabuqina" / "plugins" / "platforms"
    runtime_plugins: list[str] = []
    if plugin_dir.is_dir():
        for plugin_path in sorted(path for path in plugin_dir.iterdir() if path.is_dir()):
            source_relative = f"hermes_core/plugins/platforms/{plugin_path.name}"
            owners = {
                owner
                for owner, claim in source_claims
                if _source_claim_matches(claim, source_relative)
            }
            if not owners:
                errors.append(f"unclassified runtime platform plugin: {plugin_path}")
            elif len(owners) > 1:
                errors.append(
                    f"multiply-owned runtime platform plugin: {plugin_path} owners={sorted(owners)}"
                )
            else:
                runtime_plugins.append(plugin_path.name)
    if runtime_plugins != runtime_record.get("bundled_plugin_platforms_present"):
        errors.append(
            "baseline.runtime.bundled_plugin_platforms_present drift: "
            f"expected={runtime_record.get('bundled_plugin_platforms_present')!r} "
            f"actual={runtime_plugins!r}"
        )

    site_packages = {
        name: _runtime_module_exists(runtime, name)
        for name in runtime_record.get("site_packages", {})
    }
    if site_packages != runtime_record.get("site_packages"):
        errors.append(
            "baseline.runtime.site_packages drift: "
            f"expected={runtime_record.get('site_packages')!r} actual={site_packages!r}"
        )

    bridge_candidates = [
        runtime / "kabuqina" / "scripts" / "whatsapp-bridge",
        runtime / "scripts" / "whatsapp-bridge",
    ]
    bridge_present = any(path.exists() for path in bridge_candidates)
    if bridge_present != runtime_record.get("whatsapp_bridge_present"):
        errors.append(
            "baseline.runtime.whatsapp_bridge_present drift: "
            f"expected={runtime_record.get('whatsapp_bridge_present')!r} "
            f"actual={bridge_present!r}"
        )

    installer = baseline.get("installer", {})
    for path_key, size_key, hash_key in (
        ("path", "size_bytes", "sha256"),
        ("updater_zip_path", "updater_zip_size_bytes", "updater_zip_sha256"),
    ):
        path = root / installer.get(path_key, "")
        if not path.is_file():
            errors.append(f"recorded installer artifact is missing: {path}")
            continue
        actual_size = path.stat().st_size
        if actual_size != installer.get(size_key):
            errors.append(
                f"baseline.installer.{size_key} drift: "
                f"expected={installer.get(size_key)} actual={actual_size}"
            )
        actual_hash = sha256_file(path)
        if actual_hash.lower() != str(installer.get(hash_key, "")).lower():
            errors.append(
                f"baseline.installer.{hash_key} drift: "
                f"expected={installer.get(hash_key)} actual={actual_hash}"
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--check-observed",
        action="store_true",
        help="verify the mutable C-0 source snapshot and authority git states",
    )
    parser.add_argument(
        "--verify-local-artifacts",
        action="store_true",
        help="hash and inspect the recorded local runtime/installer artifacts",
    )
    parser.add_argument(
        "--refresh-generated-ledgers",
        action="store_true",
        help="refresh the tracked reference and exact environment-key ledgers in the manifest",
    )
    args = parser.parse_args(argv)

    try:
        manifest = load_manifest(args.manifest)
        if args.refresh_generated_ledgers:
            refresh_generated_ledgers(manifest, ROOT)
            args.manifest.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(
                "Refreshed generated C-0 ledgers: "
                f"references={len(manifest['typed_reference_ledger'])} "
                "environment_keys="
                f"{len(manifest['credential_data_graph']['environment_key_edges'])} "
                "environment_namespaces="
                f"{len(manifest['credential_data_graph']['environment_namespace_edges'])} "
                "environment_dynamic_templates="
                f"{len(manifest['credential_data_graph']['environment_dynamic_key_templates'])}"
            )
        errors = validate_contract(manifest, ROOT)
        if args.check_observed:
            errors.extend(validate_observed_snapshot(manifest, ROOT))
        if args.verify_local_artifacts:
            errors.extend(validate_local_artifacts(manifest, ROOT))
    except (OSError, ValueError, RuntimeError, SyntaxError) as exc:
        print(f"C-0 platform manifest audit failed to run: {exc}", file=sys.stderr)
        return 2

    if errors:
        print(f"C-0 platform manifest audit FAILED ({len(errors)} issue(s))")
        for error in errors:
            print(f"- {error}")
        return 1

    modes = ["contract"]
    if args.check_observed:
        modes.append("observed-source")
    if args.verify_local_artifacts:
        modes.append("local-artifacts")
    surface_count = len(manifest["surfaces"])
    platform_count = sum(len(item["gateway_platforms"]) for item in manifest["surfaces"])
    print(
        "C-0 platform manifest audit passed: "
        f"modes={','.join(modes)} surfaces={surface_count} "
        f"classified_platforms={platform_count} owned_source_unknown=0 "
        f"gate_ready={str(manifest.get('gate_ready')).lower()}"
    )
    if not manifest.get("gate_ready"):
        print(
            "Pre-review evidence is still pending: this does not mark CTL-C01 DONE "
            "and does not prove CTL-C02 runtime enforcement."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
