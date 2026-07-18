"""Contract tests for the v0.5.0 C-0 platform manifest."""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
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
