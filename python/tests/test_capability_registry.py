# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
CORE_DIR = Path(__file__).resolve().parents[2] / "hermes_core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))


class CapabilityRegistryTests(unittest.TestCase):
    def test_first_party_capabilities_are_registered(self):
        from capability_registry import list_capability_defs

        ids = {item["id"] for item in list_capability_defs()}

        self.assertIn("document-precise-read", ids)
        self.assertIn("document-math", ids)
        self.assertIn("voice-local-stt", ids)
        self.assertIn("desktop-organizer", ids)
        self.assertIn("student-ppt", ids)

    def test_load_package_dependencies_are_declared_on_capabilities(self):
        from capability_registry import get_capability_def

        math = get_capability_def("document-math")
        voice = get_capability_def("voice-local-stt")

        self.assertEqual(math["required_load_packages"], ["docling-codeformula"])
        self.assertEqual(voice["required_load_packages"], ["local-stt-base-q5_1"])
        self.assertEqual(math["source"], "builtin")
        self.assertEqual(math["trust"], "official")

    def test_capability_toolsets_match_registered_tool_ownership(self):
        from capability_registry import get_capability_def

        precise = get_capability_def("document-precise-read")
        math = get_capability_def("document-math")
        voice = get_capability_def("voice-local-stt")
        student_ppt = get_capability_def("student-ppt")

        self.assertEqual(precise["required_toolsets"], ["documents"])
        self.assertEqual(math["required_toolsets"], ["documents"])
        self.assertEqual(voice["required_toolsets"], [])
        self.assertEqual(student_ppt["required_toolsets"], ["documents", "clarify"])

    def test_every_capability_declares_pipeline_steps(self):
        from capability_registry import list_capability_defs

        for capability in list_capability_defs():
            self.assertTrue(capability.get("pipelines"), capability["id"])
            for pipeline in capability["pipelines"]:
                self.assertTrue(pipeline.get("id"), capability["id"])
                self.assertTrue(pipeline.get("steps"), pipeline.get("id"))
                for step in pipeline["steps"]:
                    self.assertIn(step.get("stage"), {"reader", "material_index", "planner", "writer"})
                    self.assertTrue(step.get("outputs"), step)

    def test_document_math_is_cross_document_reader_pipeline(self):
        from capability_registry import get_capability_def

        math = get_capability_def("document-math")
        pipeline_ids = {item["id"] for item in math["pipelines"]}

        self.assertIn("docling-math-document-read", pipeline_ids)
        self.assertIn("docling-math-pdf-read", pipeline_ids)
        primary = next(item for item in math["pipelines"] if item["id"] == "docling-math-document-read")
        self.assertEqual(primary["stages"], ["reader"])
        self.assertIn("pptx", primary["inputs"])
        self.assertEqual(primary["steps"][0]["tool"], "document_read_precise")
        self.assertEqual(primary["steps"][0]["default_args"], {"mode": "math"})
        self.assertIn("docling-codeformula", primary["steps"][0]["required_load_packages"])
        self.assertIn("formulas", primary["steps"][0]["outputs"])

    def test_student_ppt_pipeline_declares_four_layer_flow(self):
        from capability_registry import get_capability_def

        ppt = get_capability_def("student-ppt")
        pipeline = next(item for item in ppt["pipelines"] if item["id"] == "student-ppt-from-documents")
        stages = [step["stage"] for step in pipeline["steps"]]

        self.assertEqual(stages, ["reader", "material_index", "planner", "writer"])

    def test_shortcuts_reference_existing_pipelines(self):
        from capability_registry import list_capability_defs

        allowed_surfaces = {"chat_quick_action", "wizard", "settings_action", "context_menu"}
        for capability in list_capability_defs():
            pipeline_ids = {pipeline["id"] for pipeline in capability.get("pipelines") or []}
            for shortcut in capability.get("shortcuts") or []:
                self.assertIn(shortcut["surface"], allowed_surfaces)
                self.assertIn(shortcut["entry_pipeline"], pipeline_ids)

    def test_load_package_references_are_registered(self):
        import os

        import load_packages
        from capability_registry import list_capability_defs

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "appdata"
            workspace = Path(tmp) / "workspace"
            data_dir.mkdir()
            workspace.mkdir()
            with patch.dict(
                os.environ,
                {
                    "HERMESDESK_DATA_DIR": str(data_dir),
                    "HERMESDESK_WORKSPACE": str(workspace),
                },
                clear=False,
            ):
                package_ids = {item["id"] for item in load_packages.list_load_packages()}

        for capability in list_capability_defs():
            refs = capability["required_load_packages"] + capability["optional_load_packages"]
            with self.subTest(capability=capability["id"]):
                self.assertLessEqual(set(refs), package_ids)

    def test_missing_required_package_marks_capability_missing(self):
        from capability_registry import get_capability_def
        from capability_status import build_capability_status

        packages = {
            "docling-codeformula": {
                "id": "docling-codeformula",
                "title": "Docling CodeFormula",
                "downloaded": False,
                "sizeMb": 500,
                "job": None,
            }
        }

        status = build_capability_status(get_capability_def("document-math"), packages)

        self.assertEqual(status["status"], "missing_package")
        self.assertEqual(status["requiredLoadPackages"][0]["id"], "docling-codeformula")

    def test_running_required_package_marks_capability_downloading(self):
        from capability_registry import get_capability_def
        from capability_status import build_capability_status

        packages = {
            "docling-codeformula": {
                "id": "docling-codeformula",
                "title": "Docling CodeFormula",
                "downloaded": False,
                "sizeMb": 500,
                "job": {"status": "running", "phase": "downloading", "percent": 12},
            }
        }

        status = build_capability_status(get_capability_def("document-math"), packages)

        self.assertEqual(status["status"], "downloading")

    def test_downloaded_required_package_marks_capability_available(self):
        from capability_registry import get_capability_def
        from capability_status import build_capability_status

        packages = {
            "docling-codeformula": {
                "id": "docling-codeformula",
                "title": "Docling CodeFormula",
                "downloaded": True,
                "sizeMb": 500,
                "job": None,
            }
        }

        status = build_capability_status(get_capability_def("document-math"), packages)

        self.assertEqual(status["status"], "available")

    def test_pipeline_missing_package_marks_capability_missing(self):
        from capability_registry import get_capability_def
        from capability_status import build_capability_status

        packages = {
            "docling-codeformula": {
                "id": "docling-codeformula",
                "title": "Docling CodeFormula",
                "downloaded": False,
                "job": None,
            }
        }
        result = build_capability_status(
            get_capability_def("document-math"),
            load_packages=packages,
            enabled_toolsets={"documents"},
        )

        self.assertEqual(result["status"], "missing_package")
        self.assertIn("docling-codeformula", result["statusReason"])

    def test_pipeline_ready_marks_capability_available(self):
        from capability_registry import get_capability_def
        from capability_status import build_capability_status

        packages = {
            "docling-codeformula": {
                "id": "docling-codeformula",
                "title": "Docling CodeFormula",
                "downloaded": True,
                "job": None,
            }
        }
        result = build_capability_status(
            get_capability_def("document-math"),
            load_packages=packages,
            enabled_toolsets={"documents"},
        )

        self.assertEqual(result["status"], "available")
        self.assertTrue(result["pipelines"][0]["ready"])

    def test_disabled_required_toolset_marks_capability_disabled_after_packages_satisfied(self):
        from capability_registry import get_capability_def
        from capability_status import build_capability_status

        packages = {
            "docling-codeformula": {
                "id": "docling-codeformula",
                "title": "Docling CodeFormula",
                "downloaded": True,
                "sizeMb": 500,
                "job": None,
            }
        }

        status = build_capability_status(
            get_capability_def("document-math"),
            packages,
            enabled_toolsets=["file", "vision"],
        )

        self.assertEqual(status["status"], "disabled_toolset")
        self.assertIn("documents", status["statusReason"])

    def test_package_status_takes_priority_over_disabled_toolset(self):
        from capability_registry import get_capability_def
        from capability_status import build_capability_status

        packages = {
            "docling-codeformula": {
                "id": "docling-codeformula",
                "title": "Docling CodeFormula",
                "downloaded": False,
                "sizeMb": 500,
                "job": {"status": "running", "phase": "downloading", "percent": 12},
            }
        }

        status = build_capability_status(
            get_capability_def("document-math"),
            packages,
            enabled_toolsets=[],
        )

        self.assertEqual(status["status"], "downloading")

    def test_agent_summary_mentions_available_and_missing_capabilities(self):
        from capability_prompt import build_capability_prompt_summary

        capabilities = [
            {
                "id": "document-precise-read",
                "title": "Precise document reading",
                "status": "available",
                "agentHint": "Use for structured document reading.",
                "requiredLoadPackages": [],
            },
            {
                "id": "document-math",
                "title": "Formula extraction and LaTeX",
                "status": "missing_package",
                "agentHint": "Use for math extraction.",
                "requiredLoadPackages": [
                    {"id": "docling-codeformula", "title": "Docling CodeFormula", "downloaded": False}
                ],
            },
        ]

        summary = build_capability_prompt_summary(capabilities)

        self.assertIn("Precise document reading: available", summary)
        self.assertIn("Formula extraction and LaTeX: missing_package", summary)
        self.assertIn("docling-codeformula", summary)
        self.assertIn("Docling CodeFormula", summary)

    def test_agent_summary_does_not_report_available_packages_missing_by_default(self):
        from capability_prompt import build_capability_prompt_summary

        summary = build_capability_prompt_summary([
            {
                "id": "document-math",
                "title": "Formula extraction and LaTeX",
                "status": "available",
                "requiredLoadPackages": [{"id": "docling-codeformula", "title": "Docling CodeFormula"}],
            }
        ])

        self.assertIn("Formula extraction and LaTeX: available", summary)
        self.assertNotIn("Missing package(s)", summary)

    def test_agent_summary_mentions_ready_pipeline_steps(self):
        from capability_prompt import build_capability_prompt_summary
        from capability_registry import get_capability_def
        from capability_status import build_capability_status

        packages = {
            "docling-codeformula": {
                "id": "docling-codeformula",
                "title": "Docling CodeFormula",
                "downloaded": True,
                "job": None,
            }
        }
        capability = build_capability_status(
            get_capability_def("document-math"),
            load_packages=packages,
            enabled_toolsets={"documents"},
        )

        summary = build_capability_prompt_summary([capability])

        self.assertIn("docling-math-document-read", summary)
        self.assertIn("document_read_precise(mode=math)", summary)
        self.assertIn("outputs: read_id, markdown, formulas", summary)


if __name__ == "__main__":
    unittest.main()
