"""Classify every tracked ``hermes`` identifier remaining after A-R3.

The audit is intentionally conservative for active product guidance: an
unrecognised hit is a defect and makes the command fail. Historical plans,
upstream/legal attribution, protocol/model names, and explicit one-release
compatibility seams are reported separately rather than mechanically renamed.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

HISTORY_PREFIXES = (
    ".qoder/specs/",
    "docs/archive/",
    "docs/superpowers/",
    "docs/reviews/",
    "hermes_core/.plans/",
    "hermes_core/website/",
)
HISTORY_FILES = {
    "DECISIONS.md",
    "_analyze.py",
    "docs/depatching-plan.md",
    "hermes_core/hermes-already-has-routines.md",
}
ACTIVE_DOCS = {
    "docs/README.md",
    "docs/architecture.md",
    "docs/embedded-python-bundled.md",
    "docs/onboarding.md",
    "docs/qa-checklist.md",
    "docs/release-checklist.md",
    "docs/safety.md",
    "docs/troubleshooting.md",
}
RETAINED_UPSTREAM_PREFIXES = (
    "hermes_core/.github/",
    "hermes_core/datagen-config-examples/",
    "hermes_core/docker/",
    "hermes_core/nix/",
    "hermes_core/optional-skills/",
    "hermes_core/packaging/",
    "hermes_core/plans/",
    "hermes_core/plugins/",
    "hermes_core/scripts/",
    "hermes_core/web/",
)
RETAINED_UPSTREAM_FILES = {
    "hermes_core/Dockerfile",
    "hermes_core/docker-compose.yml",
    "hermes_core/flake.nix",
    "hermes_core/package-lock.json",
    "hermes_core/package.json",
    "hermes_core/setup-hermes.sh",
}
DESKTOP_PREFIXES = ("python/", "tauri/", "web/")
LEGAL_NAMES = {"license", "license.md", "notice", "notice.md", "security.md"}
LEGACY_SHIMS = {
    "hermes_core/hermes_constants.py",
    "hermes_core/hermes_logging.py",
    "hermes_core/hermes_state.py",
    "hermes_core/hermes_time.py",
    "hermes_core/skills/productivity/google-workspace/scripts/_hermes_home.py",
}
COMPAT_IMPLEMENTATIONS = {
    "hermes_core/kabuqina_constants.py",
    "hermes_core/kabuqina_logging.py",
    "hermes_core/kabuqina_state.py",
    "hermes_core/kabuqina_time.py",
    "hermes_core/skills/productivity/google-workspace/scripts/_kabuqina_home.py",
    "hermes_core/kabuqina_cli/config_home.py",
    "hermes_core/kabuqina_cli/env_loader.py",
    "hermes_core/kabuqina_cli/profiles.py",
    "hermes_core/kabuqina_cli/providers.py",
    "hermes_core/agent/memory_manager.py",
    "hermes_core/agent/prompt_builder.py",
    "hermes_core/gateway/run.py",
    "hermes_core/providers/auth_store.py",
    "hermes_core/tools/environments/file_sync.py",
    "hermes_core/tools/mcp_oauth.py",
    "hermes_core/tools/mcp_oauth_manager.py",
    "hermes_core/tools/xai_http.py",
    "python/src/kabuqina_env.py",
    "python/src/desktop_entrypoint.py",
    "python/src/desktop_config.py",
    "python/src/desktop_timezone.py",
    "python/build_bundle.ps1",
    "scripts/sync-runtime-sources.ps1",
    "tauri/src/gateway_supervisor.rs",
    "tauri/src/python_supervisor.rs",
    "tauri/src/secrets.rs",
}

UPSTREAM_RE = re.compile(
    r"NousResearch/hermes-agent|hermes-agent\.nousresearch\.com|"
    r"upstream|frozen snapshot|derived from|lineage|originally|attribution|"
    r"cherry-pick|github\.com/.*/hermes|ghcr\.io/nousresearch/hermes-agent",
    re.IGNORECASE,
)
PROTOCOL_RE = re.compile(
    r"Nous[- /]?Hermes|Nous Research Hermes|Hermes[-_ ]?[34]|hermes[-_ ]?[34]|"
    r"HermesToolCallParser|hermes_parser|ChatML|HERMES\.md|"
    r"metadata\.hermes|hermes_tools|HermesAgent(?:BaseEnv|EnvConfig)|"
    r"HermesSweEnv|HERMES_INDEX|hermes-agent-setup|toolset|source.?=.?'hermes'|"
    r"source.?=.?'hermes-agent'|hermes_action|hermes\.(?:tool|api|run)|"
    r"hermes_agent\.plugins|hermes_plugins|HermesIndexSource|hermes-index|"
    r"read_hermes_oauth_credentials|is_nous_hermes|_NOUS_HERMES|"
    r"_HERMES_MODEL_WARNING|hermes_warn|hermes-lcm|from=hermes|tp=hermes|"
    r"_find_hermes_md|_load_hermes_md|hermes_md_path|hermes_meta|"
    r"metadata\.get\([\"']hermes[\"']\)|agent-browser-hermes_|"
    r"hermes_(?:approve|confirm|deny)|hermes_pkce|run_hermes_oauth|"
    r"hermes-dialog-bridge|__hermesDialogBridgeInstalled|"
    r"agent_workspace.*hermes|(?:user_id|session_name|txn_id).*hermes_|"
    r"@hermes_bot|source=hermes|hermes_env_access|hermes_config_mod",
    re.IGNORECASE,
)
SOURCE_TREE_RE = re.compile(r"(?:^|[^A-Za-z0-9_])hermes_core(?:[/\\]|[\"'`]|\s|$)")
COMPAT_WORD_RE = re.compile(
    r"legacy|compat|deprecated|fallback|old[- ]only|old name|alias|migration|"
    r"migrat(?:e|ed|ing)|one.release|read.old|old service|old directory|"
    r"historical(?:ly)?|still works|backward|fixture|post_setup|旧|迁移|兼容|回退",
    re.IGNORECASE,
)
COMPAT_TOKEN_RE = re.compile(
    r"HERMESDESK_|HERMES_HOME|HERMES_TIMEZONE|HERMES_AGENT_ENGINE|"
    r"HermesDesk|hermesdesk|hermes-home|~/\.hermes|[\"']\.hermes[\"']|"
    r"Path\.home\(\)\s*/\s*[\"']\.hermes|"
    r"\bhermes_cli\b|\bhermes_home\b|\bhermes_(?:constants|logging|state|time)\b|"
    r"_hermes_(?:verbose|pgid|run_generation)|load_hermes_dotenv",
)
OLD_PERSISTENCE_RE = re.compile(
    r"HERMES_HOME|HERMES_TIMEZONE|hermes-home|~/\.hermes|runtime[/\\]hermes|"
    r"\bhermes_cli\b|\bhermes_(?:constants|logging|state|time)\b"
)
OLD_COMMAND_RE = re.compile(
    r"\bhermes (?:setup|doctor|gateway|status|skills|config|model|profile|cron|"
    r"update|logout|login|chat|tools|--tui)|pip install ['\"]?hermes-agent",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Hit:
    path: str
    line: int
    text: str


def _tracked_hits() -> list[Hit]:
    result = subprocess.run(
        [
            "git",
            "-c",
            "core.quotePath=false",
            "grep",
            "-n",
            "-I",
            "-i",
            "hermes",
            "--",
            ":(exclude)python/dist",
            ":(exclude)tauri/target",
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.strip() or "git grep failed")

    hits: list[Hit] = []
    for raw in result.stdout.splitlines():
        path, line, text = raw.split(":", 2)
        hits.append(Hit(path.replace("\\", "/"), int(line), text))
    return hits


def classify(hit: Hit) -> str:
    path = hit.path
    lower_path = path.lower()
    text = hit.text

    if path == "scripts/audit_a_r3_legacy_names.py":
        return "audit-tool"
    if path == "python/tools/verify_legacy_runtime_imports.py":
        return "compatibility-test-or-fixture"
    if path == "hermes_core/gateway/platforms/api_server.py" and (
        "hermes-agent" in text.lower()
        or "x-hermes-session-id" in text.lower()
        or '"owned_by": "hermes"' in text
    ):
        return "model-or-protocol"
    if path == "hermes_core/gateway/config.py" and "x-hermes-session-id" in text.lower():
        return "model-or-protocol"
    if path.startswith(HISTORY_PREFIXES) or path in HISTORY_FILES:
        return "history"
    if path == "hermes_core/KABUQINA_MODIFICATIONS.md":
        return "history"
    if path.startswith("docs/") and path not in ACTIVE_DOCS:
        return "history"
    if path == "docs/troubleshooting.md" and "hermes" in text.lower():
        return "compatibility-documentation"
    if path == "docs/README.md" and COMPAT_WORD_RE.search(text):
        return "compatibility-documentation"
    if path == "docs/architecture.md" and "/api/hermesdesk/" in text.lower():
        return "model-or-protocol"
    if path.startswith("docs/test-cases/"):
        return "compatibility-test-or-fixture"
    if (
        Path(path).name.lower() in LEGAL_NAMES
        or "release_" in lower_path
        or "authorization" in lower_path
    ):
        return "history"
    if "/tests/" in f"/{path}" or lower_path.startswith("tests/"):
        return "compatibility-test-or-fixture"
    if path in LEGACY_SHIMS or path.startswith("hermes_core/hermes_cli/"):
        return "compatibility-shim"
    if path.startswith(RETAINED_UPSTREAM_PREFIXES) or path in RETAINED_UPSTREAM_FILES:
        return "retained-upstream-surface"
    if path in {
        "scripts/audit_posix_imports.ps1",
        "scripts/_audit_cli_reachability.py",
        "scripts/smoke_llm_openrouter.ps1",
    }:
        return "compatibility-implementation"
    if path.startswith(DESKTOP_PREFIXES):
        if OLD_PERSISTENCE_RE.search(text):
            if path in COMPAT_IMPLEMENTATIONS or COMPAT_WORD_RE.search(text):
                return "compatibility-implementation"
            return "defect"
        return "desktop-compatibility"
    if path.startswith("hermes_core/skills/"):
        if path in COMPAT_IMPLEMENTATIONS:
            return "compatibility-implementation"
        if OLD_COMMAND_RE.search(text) or OLD_PERSISTENCE_RE.search(text):
            return "defect"
        return "model-or-protocol"
    if "HERMESDESK_" in text:
        return "compatibility-implementation"
    if path == ".gitignore" and "hermes" in text.lower():
        return "compatibility-implementation"
    if path == "hermes_core/.gitignore":
        return "compatibility-implementation"
    if path == "hermes_core/.env.example" and re.search(
        r"HERMES_[A-Z0-9_]+|hermes@gmail\.com", text
    ):
        return "compatibility-documentation"
    if path == "hermes_core/cli-config.yaml.example" and re.search(
        r"HERMES_[A-Z0-9_]+|hermes-[a-z0-9_-]+", text
    ):
        return "compatibility-documentation"
    if path in {"AGENTS.md", "hermes_core/AGENTS.md"} and re.search(
        r"HERMES_[A-Z0-9_]+", text
    ):
        return "compatibility-documentation"
    if path == "hermes_core/pyproject.toml":
        return "compatibility-implementation"
    if SOURCE_TREE_RE.search(text):
        return "source-tree-boundary"
    if path in {"AGENTS.md", "README.md", "hermes_core/AGENTS.md"} and re.search(
        r"Hermes (?:Agent|React|module|function|core)", text, re.IGNORECASE
    ):
        return "upstream-or-legal"
    if UPSTREAM_RE.search(text):
        return "upstream-or-legal"
    if PROTOCOL_RE.search(text) or lower_path.startswith("hermes_core/environments/"):
        return "model-or-protocol"
    if re.search(r"^\s*hermes:\s*$|/hermes\b|hermes-ink|_get_default_hermes_home", text):
        return "model-or-protocol"
    if re.search(
        r"HermesACPAgent|HermesOverlay|HERMES_OVERLAYS|HermesTokenStorage|"
        r"_HERMES_PROVIDER_CLS|_resolve_hermes_bin",
        text,
    ):
        return "compatibility-implementation"
    if path == "hermes_core/toolsets.py":
        return "model-or-protocol"
    if path == "hermes_core/kabuqina_cli/model_switch.py":
        return "model-or-protocol"
    if path == "hermes_core/tools/skills_hub.py" and "hermes" in text.lower():
        return "model-or-protocol"
    if path == "hermes_core/tools/skills_tool.py" and re.search(
        r"metadata|get\([\"']hermes[\"']\)", text
    ):
        return "model-or-protocol"
    if path == "hermes_core/providers/nous_auth.py":
        return "model-or-protocol"
    if path == "hermes_core/gateway/platforms/matrix.py" and '"hermes"' in text:
        return "model-or-protocol"
    if path in {
        "hermes_core/kabuqina_cli/config_defaults.py",
        "hermes_core/tools/environments/docker.py",
    } and "'hermes'" in text:
        return "retained-upstream-surface"
    if path == "hermes_core/tools/approval.py":
        return "compatibility-implementation"
    if path in {
        "hermes_core/tools/skills_guard.py",
        "hermes_core/tools/memory_tool.py",
        "hermes_core/tools/terminal_tool.py",
    } and "hermes" in text.lower():
        return "compatibility-implementation"
    if path in {
        "hermes_core/kabuqina_cli/config_home.py",
        "hermes_core/kabuqina_cli/config_managed.py",
    }:
        return "retained-upstream-surface"
    if path == "hermes_core/kabuqina_cli/profiles.py" and "hermes" in text.lower():
        return "compatibility-implementation"
    if path == "hermes_core/run_agent.py" and re.search(
        r"hermes_home|agent_workspace.*hermes", text
    ):
        return "compatibility-implementation"
    if path.startswith("hermes_core/providers/") and re.search(
        r"hermes_pkce|run_hermes_oauth|HermesDesk", text
    ):
        return "model-or-protocol"
    if path.startswith("hermes_core/tools/browser_") and re.search(
        r"hermes[_-]|HermesDesk|__hermes|hermes-dialog", text
    ):
        return "model-or-protocol"
    if lower_path.endswith((".py", ".rs", ".ps1", ".sh", ".ts", ".tsx")) and re.search(
        r"HERMES_[A-Z0-9_]*", text
    ):
        return "compatibility-implementation"
    if path in COMPAT_IMPLEMENTATIONS and (
        COMPAT_TOKEN_RE.search(text) or COMPAT_WORD_RE.search(text)
    ):
        return "compatibility-implementation"
    if path in COMPAT_IMPLEMENTATIONS and re.search(
        r"shutil\.which\([\"']hermes[\"']\)|\bhermes -p\b|\bhermes\.(?:service|[a-z0-9_-]+)",
        text,
        re.IGNORECASE,
    ):
        return "compatibility-implementation"
    if re.search(r"kabuqina.*hermes|hermes.*kabuqina", text, re.IGNORECASE):
        return "compatibility-implementation"
    if COMPAT_WORD_RE.search(text) and "hermes" in text.lower():
        return (
            "compatibility-documentation"
            if lower_path.endswith((".md", ".rst", ".txt"))
            else "compatibility-implementation"
        )
    if COMPAT_WORD_RE.search(text) and COMPAT_TOKEN_RE.search(text):
        return "compatibility-documentation"
    if lower_path.endswith(("uv.lock", "package-lock.json")) and "hermes" in text.lower():
        return "packaging-defect"
    return "defect"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    hits = _tracked_hits()
    classified = [(hit, classify(hit)) for hit in hits]
    counts = Counter(category for _, category in classified)

    print(f"A-R3 legacy-name audit: {len(hits)} tracked hits")
    for category, count in sorted(counts.items()):
        print(f"  {category}: {count}")

    defects = [
        (hit, category)
        for hit, category in classified
        if category in {"defect", "packaging-defect"}
    ]
    if defects:
        print(f"\nUnclassified/defect hits ({len(defects)}):")
        for hit, category in defects[:200]:
            print(f"{hit.path}:{hit.line}: [{category}] {hit.text}")
        if len(defects) > 200:
            print(f"... {len(defects) - 200} additional defect hits omitted")
        return 1

    print("All tracked hits are classified; no active identity defect remains.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
