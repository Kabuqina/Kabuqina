# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Contract tests for the artifact-level dependency inventory."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "python" / "tools" / "generate_dependency_inventory.py"


class DependencyInventoryTests(unittest.TestCase):
    def test_desktop_direct_retained_dependencies_and_rust_lock_are_frozen(self):
        requirements = (
            ROOT / "python" / "requirements-desktop.txt"
        ).read_text(encoding="utf-8")
        for requirement in (
            "aiohttp>=3.13.3,<4",
            "certifi>=2024.8.30,<2027",
            "cryptography>=43,<47",
            "qrcode>=7.0,<8",
            "python-telegram-bot[webhooks]>=22.6,<23",
            "dingtalk-stream==0.24.3",
            "alibabacloud-dingtalk>=2.2.42,<3",
        ):
            self.assertIn(requirement, requirements)

        self.assertTrue((ROOT / "tauri" / "Cargo.lock").is_file())
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertNotIn("/tauri/Cargo.lock", ignore)

    def test_bundle_generates_inventory_before_verification(self):
        build = (ROOT / "python" / "build_bundle.ps1").read_text(encoding="utf-8")

        self.assertIn("generate_dependency_inventory.py", build)
        self.assertIn('"DEPENDENCY_INVENTORY.json"', build)
        for metadata_field in (
            "dependencyInventorySha256",
            "desktopRequirementsSha256",
            "whatsappLockSha256",
            "nodeArchiveSha256",
            "cargoLockSha256",
        ):
            self.assertIn(metadata_field, build)
        self.assertLess(
            build.index("$dependencyInventoryScript"),
            build.index("# ------------------------------------------------------------------ 8. Verify"),
        )

    def test_generator_fails_closed_when_direct_requirement_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = root / "runtime"
            (runtime / "site-packages").mkdir(parents=True)
            requirements = root / "requirements.txt"
            requirements.write_text("definitely-missing>=1,<2\n", encoding="utf-8")
            lock = root / "package-lock.json"
            lock.write_text(
                json.dumps({
                    "packages": {
                        "node_modules/@whiskeysockets/baileys": {},
                        "node_modules/express": {},
                        "node_modules/pino": {},
                        "node_modules/qrcode-terminal": {},
                    }
                }),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(GENERATOR),
                    str(runtime),
                    str(requirements),
                    str(lock),
                ],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "desktop direct requirements missing from runtime: definitely-missing",
            result.stderr,
        )

    def test_generator_writes_exact_input_hashes_and_license_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = root / "runtime"
            dist_info = runtime / "site-packages" / "demo_pkg-1.2.3.dist-info"
            dist_info.mkdir(parents=True)
            node_dir = runtime / "node"
            node_dir.mkdir()
            (node_dir / "node.exe").write_bytes(b"test executable")
            (node_dir / "LICENSE").write_text("test runtime license\n", encoding="utf-8")
            (node_dir / "VERSION").write_text("v24.18.0\n", encoding="ascii")
            (dist_info / "METADATA").write_text(
                "Metadata-Version: 2.4\n"
                "Name: demo-pkg\n"
                "Version: 1.2.3\n"
                "License-Expression: MIT\n",
                encoding="utf-8",
            )
            requirements = root / "requirements.txt"
            requirements.write_text("demo-pkg>=1,<2\n", encoding="utf-8")
            lock = root / "package-lock.json"
            lock.write_text(
                json.dumps({
                    "packages": {
                        "node_modules/@whiskeysockets/baileys": {
                            "version": "7.0.0",
                            "license": "MIT",
                        },
                        "node_modules/express": {"version": "4", "license": "MIT"},
                        "node_modules/pino": {"version": "9", "license": "MIT"},
                        "node_modules/qrcode-terminal": {
                            "version": "0.12",
                            "license": "MIT",
                        },
                    }
                }),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(GENERATOR),
                    str(runtime),
                    str(requirements),
                    str(lock),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            inventory = json.loads(
                (runtime / "DEPENDENCY_INVENTORY.json").read_text(encoding="utf-8")
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            inventory["inputs"]["desktop_requirements"]["direct_packages"],
            ["demo-pkg"],
        )
        self.assertEqual(inventory["python_packages"][0]["version"], "1.2.3")
        self.assertEqual(
            inventory["python_packages"][0]["license_expression"],
            "MIT",
        )
        self.assertEqual(
            inventory["node_packages"][0]["name"],
            "@whiskeysockets/baileys",
        )
        self.assertEqual(inventory["runtime_components"][0]["name"], "node")
        self.assertEqual(
            inventory["runtime_components"][0]["license_path"],
            "node/LICENSE",
        )

    def test_generator_records_python_and_node_license_metadata(self):
        text = GENERATOR.read_text(encoding="utf-8")

        for field in (
            "license_expression",
            "license_metadata",
            "license_classifiers",
            "integrity",
            "desktop_requirements",
            "whatsapp_package_lock",
            "runtime_components",
            "license_sha256",
        ):
            self.assertIn(field, text)


if __name__ == "__main__":
    unittest.main()
