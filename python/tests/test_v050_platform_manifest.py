"""Contract tests for the v0.5.0 C-0 platform manifest."""

from __future__ import annotations

import copy
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUDIT_SCRIPT = ROOT / "scripts" / "audit_v050_platform_manifest.py"


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("_kq_v050_platform_audit", AUDIT_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {AUDIT_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_audit_module()


@contextmanager
def _tracked_scan_root(files: dict[str, str]):
    with tempfile.TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(
            ["git", "init", "-q"],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            ["git", "add", "--", "."],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        yield root


class V050PlatformManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = audit.load_manifest()

    def test_repository_manifest_satisfies_fail_closed_contract(self) -> None:
        self.assertEqual([], audit.validate_contract(self.manifest, ROOT))

    def test_unknown_platform_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.manifest)
        local = next(item for item in mutated["surfaces"] if item["surface"] == "local_delivery")
        local["gateway_platforms"].append("future_chat")

        errors = audit.validate_contract(mutated, ROOT, scan_repository=False)

        self.assertTrue(
            any("classified gateway set differs" in error for error in errors),
            errors,
        )

    def test_missing_required_surface_field_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.manifest)
        del mutated["surfaces"][0]["credential_keys"]

        errors = audit.validate_contract(mutated, ROOT, scan_repository=False)

        self.assertTrue(
            any("missing fields" in error and "credential_keys" in error for error in errors),
            errors,
        )

    def test_profile_allowlist_drift_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.manifest)
        mutated["profiles"]["sea"]["gateway_platforms"] = ["telegram", "email"]

        errors = audit.validate_contract(mutated, ROOT, scan_repository=False)

        self.assertIn(
            "profiles do not match the exact mainland_cn/sea product contract",
            errors,
        )

    def test_typed_reference_missing_semantics_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.manifest)
        del mutated["typed_reference_ledger"][0]["target_contract"]

        errors = audit.validate_contract(mutated, ROOT, scan_repository=False)

        self.assertTrue(
            any("typed_reference_ledger[0] missing fields" in error for error in errors),
            errors,
        )

    def test_dependency_record_missing_license_status_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.manifest)
        del mutated["dependency_graph"][0]["license_status"]

        errors = audit.validate_contract(mutated, ROOT, scan_repository=False)

        self.assertTrue(
            any("dependency_graph[0] missing fields" in error for error in errors),
            errors,
        )

    def test_deleted_dependency_record_is_rejected_by_full_scan(self) -> None:
        mutated = copy.deepcopy(self.manifest)
        removed = mutated["dependency_graph"].pop()

        errors = audit.validate_contract(mutated, ROOT)

        self.assertTrue(
            any(
                "dependency_graph ids differ from the reviewed C-0 closed set" in error
                and removed["id"] in error
                for error in errors
            ),
            errors,
        )

    def test_credential_key_missing_exact_sources_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.manifest)
        mutated["credential_data_graph"]["environment_key_edges"][0][
            "source_paths"
        ] = []

        errors = audit.validate_contract(mutated, ROOT, scan_repository=False)

        self.assertTrue(
            any("source_paths must be non-empty" in error for error in errors),
            errors,
        )

    def test_bundled_plugin_credential_keys_are_scanned(self) -> None:
        edges = {
            record["key"]: record for record in audit.collect_credential_key_edges(ROOT)
        }
        expected = {
            "TEAMS_ALLOWED_USERS",
            "TEAMS_ALLOW_ALL_USERS",
            "TEAMS_CLIENT_ID",
            "TEAMS_CLIENT_SECRET",
            "TEAMS_PORT",
            "TEAMS_TENANT_ID",
        }

        self.assertEqual(set(), expected - set(edges))
        for key in expected:
            self.assertEqual("teams_plugin", edges[key]["surface"])
            self.assertIn(
                "hermes_core/plugins/platforms/teams/adapter.py",
                edges[key]["source_paths"],
            )

    def _assert_removed_environment_group_is_rejected(
        self, keys: set[str]
    ) -> dict[str, dict]:
        tracked = {
            record["key"]: record
            for record in self.manifest["credential_data_graph"][
                "environment_key_edges"
            ]
        }
        self.assertEqual(set(), keys - set(tracked))

        mutated = copy.deepcopy(self.manifest)
        mutated["credential_data_graph"]["environment_key_edges"] = [
            record
            for record in mutated["credential_data_graph"]["environment_key_edges"]
            if record["key"] not in keys
        ]
        errors = audit.credential_environment_ledger_issues(mutated, ROOT)

        self.assertTrue(
            any(
                "credential environment-key ledger drift" in error
                and all(key in error for key in keys)
                for error in errors
            ),
            errors,
        )
        return tracked

    def test_home_assistant_environment_group_cannot_be_omitted(self) -> None:
        tracked = self._assert_removed_environment_group_is_rejected(
            {"HASS_TOKEN", "HASS_URL"}
        )

        for key in ("HASS_TOKEN", "HASS_URL"):
            self.assertEqual("home_assistant", tracked[key]["surface"])
            self.assertIn(
                "hermes_core/gateway/platforms/homeassistant.py",
                tracked[key]["source_paths"],
            )

    def test_email_oauth_environment_group_cannot_be_omitted(self) -> None:
        key = "KABUQINA_MICROSOFT_OAUTH_CLIENT_ID"
        tracked = self._assert_removed_environment_group_is_rejected({key})

        self.assertEqual("email", tracked[key]["surface"])
        self.assertIn("tauri/src/email_oauth.rs", tracked[key]["source_paths"])

    def test_desktop_bridge_environment_group_cannot_be_omitted(self) -> None:
        keys = {
            "HERMESDESK_APPROVAL_URL",
            "HERMESDESK_BRIDGE_SECRET",
            "HERMESDESK_DESKTOP_DELIVERY_URL",
            "HERMESDESK_SECRET_URL",
            "HERMESDESK_SHELL_CHAT_URL",
            "KABUQINA_APPROVAL_URL",
            "KABUQINA_BRIDGE_SECRET",
            "KABUQINA_DESKTOP_DELIVERY_URL",
            "KABUQINA_SECRET_URL",
            "KABUQINA_SHELL_CHAT_URL",
        }
        tracked = self._assert_removed_environment_group_is_rejected(keys)

        for key in keys:
            self.assertEqual("desktop", tracked[key]["surface"])
        self.assertIn(
            "tauri/src/python_supervisor.rs",
            tracked["KABUQINA_BRIDGE_SECRET"]["source_paths"],
        )
        self.assertIn(
            "python/src/approval_backend.py",
            tracked["KABUQINA_APPROVAL_URL"]["source_paths"],
        )

    def test_structured_dynamic_environment_scan_ignores_uppercase_copy(self) -> None:
        files = {
            "python/src/runtime_env.py": """
import os
RUNTIME_ENV_KEYS = {"HASS_TOKEN", "KABUQINA_BRIDGE_SECRET"}
RUNTIME_ENV_PREFIXES = ("HASS_",)
for key in RUNTIME_ENV_KEYS:
    os.getenv(key)
""",
            "web/src/locales/strings.ts": 'export const apiLabel = "API";\n',
            "web/src/chat/pptx/renderDeck.ts": 'const signalShape = "SIGNAL";\n',
        }
        with _tracked_scan_root(files) as scan_root:
            declarations = audit.discover_environment_declarations(scan_root)
            exact_sources = audit.collect_environment_key_sources(scan_root)

        self.assertEqual(
            {"HASS_TOKEN", "KABUQINA_BRIDGE_SECRET"},
            set(declarations["exact_keys"]),
        )
        self.assertEqual({"HASS_"}, set(declarations["namespace_prefixes"]))
        self.assertNotIn("API", exact_sources)
        self.assertNotIn("SIGNAL", exact_sources)
        self.assertNotIn("HASS_", exact_sources)

    def test_unmapped_dynamic_exact_declaration_fails_closed_via_scan(self) -> None:
        files = {
            "python/src/future_runtime.py": (
                'RUNTIME_ENV_KEYS = {"FUTURE_UNKNOWN_TOKEN"}\n'
            )
        }
        with _tracked_scan_root(files) as scan_root:
            with self.assertRaisesRegex(
                ValueError, "FUTURE_UNKNOWN_TOKEN"
            ):
                audit.collect_credential_key_edges(scan_root)

    def test_unmapped_dynamic_namespace_fails_closed_via_scan(self) -> None:
        files = {
            "python/src/future_runtime.py": (
                'RUNTIME_ENV_PREFIXES = ("FUTURE_UNKNOWN_",)\n'
            )
        }
        with _tracked_scan_root(files) as scan_root:
            with self.assertRaisesRegex(
                ValueError, "FUTURE_UNKNOWN_"
            ):
                audit.collect_environment_namespace_edges(scan_root)

    def test_computed_home_channel_keys_expand_via_real_scan(self) -> None:
        platform_values = {
            "whatsapp",
            "email",
            "matrix",
            "homeassistant",
            "wecom_callback",
            "irc",
            "teams",
        }
        files = {
            "hermes_core/gateway/config.py": """
from enum import Enum
class Platform(Enum):
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    MATRIX = "matrix"
    HOMEASSISTANT = "homeassistant"
    WECOM_CALLBACK = "wecom_callback"
""",
            "hermes_core/gateway/home_channel.py": """
import os
def home_channel_env_key(platform):
    return f"{platform.value.upper().replace('-', '_')}_HOME_CHANNEL"
def load_home(platform):
    env_key = home_channel_env_key(platform)
    return os.getenv(env_key), os.getenv(f"{env_key}_NAME", "Home")
""",
            "hermes_core/plugins/platforms/irc/plugin.yaml": "name: irc\n",
            "hermes_core/plugins/platforms/irc/__init__.py": "",
            "hermes_core/plugins/platforms/teams/plugin.yaml": "name: teams\n",
            "hermes_core/plugins/platforms/teams/__init__.py": "",
        }
        with _tracked_scan_root(files) as scan_root:
            edges = {
                record["key"]: record
                for record in audit.collect_credential_key_edges(scan_root)
            }
            templates = audit.collect_environment_dynamic_template_edges(scan_root)

        expected = {
            f"{platform.upper()}_HOME_CHANNEL{suffix}"
            for platform in platform_values
            for suffix in ("", "_NAME")
        }
        self.assertEqual(set(), expected - set(edges))
        self.assertEqual(
            {"{PLATFORM}_HOME_CHANNEL", "{PLATFORM}_HOME_CHANNEL_NAME"},
            {record["template"] for record in templates},
        )
        for key in expected:
            self.assertIn("hermes_core/gateway/home_channel.py", edges[key]["source_paths"])
        for record in templates:
            self.assertIn(
                "runtime_plugin_platforms_allowed=false",
                record["dynamic_namespace_contract"],
            )

    def test_unclassified_computed_plugin_home_key_fails_closed_via_scan(self) -> None:
        files = {
            "hermes_core/gateway/config.py": """
from enum import Enum
class Platform(Enum):
    TELEGRAM = "telegram"
""",
            "hermes_core/gateway/home_channel.py": """
import os
def home_channel_env_key(platform):
    return f"{platform.value.upper().replace('-', '_')}_HOME_CHANNEL"
def load_home(platform):
    env_key = home_channel_env_key(platform)
    return os.getenv(env_key), os.getenv(f"{env_key}_NAME", "Home")
""",
            "hermes_core/plugins/platforms/future_chat/plugin.yaml": "name: future_chat\n",
            "hermes_core/plugins/platforms/future_chat/__init__.py": "",
        }
        with _tracked_scan_root(files) as scan_root:
            with self.assertRaisesRegex(
                ValueError, "FUTURE_CHAT_HOME_CHANNEL"
            ):
                audit.collect_credential_key_edges(scan_root)

    def test_surface_dependency_coverage_cannot_omit_runtime_dependency(self) -> None:
        mutated = copy.deepcopy(self.manifest)
        mutated["surface_dependency_coverage"] = [
            record
            for record in mutated["surface_dependency_coverage"]
            if not (
                record["surface"] == "teams_plugin"
                and record["runtime_dependency"] == "microsoft-teams-apps"
            )
        ]

        errors = audit.validate_contract(mutated, ROOT, scan_repository=False)

        self.assertTrue(
            any(
                "surface_dependency_coverage differs from "
                "surfaces[*].runtime_dependencies" in error
                and "microsoft-teams-apps" in error
                for error in errors
            ),
            errors,
        )

    def test_bundled_plugin_import_without_coverage_is_rejected_by_full_scan(self) -> None:
        mutated = copy.deepcopy(self.manifest)
        mutated["bundled_plugin_dependency_imports"] = [
            record
            for record in mutated["bundled_plugin_dependency_imports"]
            if record["import_root"] != "microsoft_teams"
        ]

        errors = audit.validate_contract(mutated, ROOT)

        self.assertTrue(
            any(
                "bundled plugin dependency imports differ from observed source" in error
                and "microsoft_teams" in error
                for error in errors
            ),
            errors,
        )

    def test_persisted_record_missing_cleanup_mode_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.manifest)
        del mutated["credential_data_graph"]["persisted_records"][0][
            "cleanup_mode"
        ]

        errors = audit.validate_contract(mutated, ROOT, scan_repository=False)

        self.assertTrue(
            any("persisted_records[0] missing fields" in error for error in errors),
            errors,
        )

    def test_deleted_persisted_record_is_rejected_by_full_scan(self) -> None:
        mutated = copy.deepcopy(self.manifest)
        removed = mutated["credential_data_graph"]["persisted_records"].pop()

        errors = audit.validate_contract(mutated, ROOT)

        self.assertTrue(
            any(
                "persisted record ids differ from the reviewed C-0 closed set" in error
                and removed["id"] in error
                for error in errors
            ),
            errors,
        )

    def test_illegal_review_signoff_status_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.manifest)
        mutated["review_signoff"][0]["status"] = "signed"

        errors = audit.validate_contract(mutated, ROOT, scan_repository=False)

        self.assertTrue(
            any("review_signoff[0].status must be one of" in error for error in errors),
            errors,
        )

    def test_done_manifest_requires_every_cross_layer_signoff(self) -> None:
        mutated = copy.deepcopy(self.manifest)
        mutated["review_signoff"][0] = {
            "role": "Gateway/core",
            "status": "pending",
        }

        errors = audit.validate_contract(mutated, ROOT, scan_repository=False)

        self.assertTrue(
            any("status=done requires all cross-layer review_signoff roles approved" in error for error in errors),
            errors,
        )

    def test_done_manifest_cannot_keep_pending_done_items(self) -> None:
        mutated = copy.deepcopy(self.manifest)
        mutated["coverage_status"]["pending_before_ctl_c01_done"] = [
            "stale pending reviewer"
        ]

        errors = audit.validate_contract(mutated, ROOT, scan_repository=False)

        self.assertIn(
            "status=done requires pending_before_ctl_c01_done to be empty",
            errors,
        )

    def test_authority_text_hash_is_checkout_line_ending_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            lf_path = root / "authority-lf.md"
            crlf_path = root / "authority-crlf.md"
            lf_path.write_bytes(b"# Authority\n\nStable text\n")
            crlf_path.write_bytes(b"# Authority\r\n\r\nStable text\r\n")

            self.assertEqual(
                audit.sha256_lf_normalized_text(lf_path),
                audit.sha256_lf_normalized_text(crlf_path),
            )

    def test_activation_delta_stops_at_reviewed_gate_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)

            def commit_all(message: str) -> str:
                subprocess.run(["git", "add", "--", "."], cwd=root, check=True)
                subprocess.run(
                    [
                        "git",
                        "-c",
                        "user.name=C0 Test",
                        "-c",
                        "user.email=c0@example.invalid",
                        "commit",
                        "-q",
                        "-m",
                        message,
                    ],
                    cwd=root,
                    check=True,
                )
                return subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=root,
                    check=True,
                    text=True,
                    stdout=subprocess.PIPE,
                ).stdout.strip()

            (root / "README.md").write_text("base\n", encoding="utf-8")
            base_commit = commit_all("base")
            allowed = root / "scripts" / "audit_v050_platform_manifest.py"
            allowed.parent.mkdir(parents=True)
            allowed.write_text("# reviewed C-0 delta\n", encoding="utf-8")
            gate_commit = commit_all("gate")
            unrelated = root / "docs" / "parallel-track.md"
            unrelated.parent.mkdir(parents=True)
            unrelated.write_text("parallel main work\n", encoding="utf-8")
            head_commit = commit_all("parallel work after gate")

            scoped_manifest = {
                "base": {
                    "git_commit": base_commit,
                    "activation": {
                        "evidence_commit": gate_commit,
                        "gate_commit": gate_commit,
                    },
                }
            }
            self.assertEqual(
                [], audit._activation_scope_issues(scoped_manifest, root)
            )

            scoped_manifest["base"]["activation"]["gate_commit"] = head_commit
            errors = audit._activation_scope_issues(scoped_manifest, root)
            self.assertTrue(
                any("parallel-track.md" in error for error in errors), errors
            )

    def test_review_ready_manifest_cannot_keep_pre_review_work(self) -> None:
        mutated = copy.deepcopy(self.manifest)
        mutated["gate_ready"] = True
        mutated["coverage_status"]["pending_before_ctl_c01_review"] = [
            "unresolved technical ledger"
        ]

        errors = audit.validate_contract(mutated, ROOT, scan_repository=False)

        self.assertIn(
            "gate_ready=true requires pending_before_ctl_c01_review to be empty",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
