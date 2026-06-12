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
        self.assertIn("document-pdf-generation", ids)

    def test_math_expression_capabilities_are_registered_as_available_v1(self):
        from capability_registry import get_capability_def, list_capability_defs

        ids = {item["id"] for item in list_capability_defs()}

        self.assertIn("math-expression-cleanup", ids)
        self.assertIn("math-formula-to-code", ids)
        self.assertIn("code-to-math-formula", ids)
        for capability_id in [
            "math-expression-cleanup",
            "math-formula-to-code",
            "code-to-math-formula",
        ]:
            capability = get_capability_def(capability_id)
            self.assertEqual(capability["family"], "math-expression-engineering")
            self.assertEqual(capability.get("lifecycle", "available"), "available")
            self.assertEqual(capability["required_toolsets"], ["math"])
            self.assertTrue(capability["pipelines"])

        cleanup = get_capability_def("math-expression-cleanup")
        formula_to_code = get_capability_def("math-formula-to-code")
        code_to_formula = get_capability_def("code-to-math-formula")

        self.assertIn("math_expression_cleanup", cleanup["tools"])
        self.assertIn("math_formula_to_code", formula_to_code["tools"])
        self.assertIn("code_to_math_formula", code_to_formula["tools"])
        self.assertIn("semantic_contract", formula_to_code["agent_hint"])
        self.assertIn(
            "semantic_validation",
            formula_to_code["pipelines"][0]["steps"][0]["outputs"],
        )

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
        pdf_generation = get_capability_def("document-pdf-generation")

        self.assertEqual(precise["required_toolsets"], ["documents"])
        self.assertEqual(math["required_toolsets"], ["documents"])
        self.assertEqual(voice["required_toolsets"], [])
        self.assertEqual(student_ppt["required_toolsets"], ["documents", "clarify"])
        self.assertEqual(pdf_generation["required_toolsets"], ["documents"])

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
        pipeline = next(item for item in ppt["pipelines"] if item["id"] == "student-course-report-ppt")
        stages = [step["stage"] for step in pipeline["steps"]]

        self.assertEqual(stages, ["reader", "material_index", "planner", "planner", "writer"])

    def test_student_ppt_declares_structure_templates_and_visual_masters(self):
        from capability_registry import get_capability_def
        from capability_status import build_capability_status

        ppt = get_capability_def("student-ppt")

        self.assertEqual(ppt["family"], "student-report-generation")
        self.assertEqual(
            {item["id"] for item in ppt["structure_templates"]},
            {"course_report", "paper_report", "code_defense"},
        )
        self.assertEqual(
            {item["id"] for item in ppt["visual_masters"]},
            {"soft_editorial", "blue_professional", "signal", "neo_grid_bold", "editorial_forest"},
        )
        self.assertEqual(
            {pipeline["id"] for pipeline in ppt["pipelines"]},
            {"student-course-report-ppt", "student-paper-report-ppt", "student-code-defense-ppt"},
        )
        for pipeline in ppt["pipelines"]:
            self.assertTrue(pipeline["visual_master_required"])
            self.assertIn("visual_master", pipeline["steps"][-1]["default_args"])

        status = build_capability_status(
            ppt,
            load_packages={},
            enabled_toolsets={"documents", "clarify"},
        )
        self.assertEqual(status["status"], "available")
        self.assertEqual(len(status["structureTemplates"]), 3)
        self.assertEqual(len(status["visualMasters"]), 5)
        self.assertTrue(all(pipeline["ready"] for pipeline in status["pipelines"]))

    def test_document_pdf_generation_declares_writer_path(self):
        from capability_registry import get_capability_def

        pdf = get_capability_def("document-pdf-generation")
        pipeline = pdf["pipelines"][0]

        self.assertEqual(pdf["family"], "document-generation")
        self.assertIn("pdf_write", pdf["tools"])
        self.assertEqual(pipeline["stages"], ["writer"])
        self.assertEqual(pipeline["steps"][0]["tool"], "pdf_write")
        self.assertIn("pdf_path", pipeline["steps"][0]["outputs"])
        self.assertIn("html_path", pipeline["steps"][0]["outputs"])

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

    def test_candidate_capability_is_not_marked_available(self):
        from capability_status import build_capability_status

        definition = {
            "id": "roadmap-math-capability",
            "title": "Roadmap math capability",
            "description": "Future math capability",
            "category": "math",
            "agent_hint": "Candidate only.",
            "family": "math-expression-engineering",
            "lifecycle": "candidate",
            "required_toolsets": ["math"],
            "required_load_packages": [],
            "optional_load_packages": [],
            "roles": ["default"],
            "pipelines": [
                {
                    "id": "roadmap-math-pipeline",
                    "title": "Roadmap math pipeline",
                    "stages": ["writer"],
                    "steps": [
                        {
                            "id": "roadmap-step",
                            "stage": "writer",
                            "kind": "candidate_writer",
                            "outputs": ["result"],
                        }
                    ],
                }
            ],
        }
        status = build_capability_status(
            definition,
            load_packages={},
            enabled_toolsets={"math"},
        )

        self.assertEqual(status["status"], "candidate")
        self.assertFalse(status["pipelines"][0]["ready"])
        self.assertEqual(status["lifecycle"], "candidate")

    def test_math_expression_capability_ready_when_math_toolset_enabled(self):
        from capability_registry import get_capability_def
        from capability_prompt import build_capability_prompt_summary
        from capability_status import build_capability_status

        status = build_capability_status(
            get_capability_def("math-formula-to-code"),
            load_packages={},
            enabled_toolsets={"math"},
        )

        self.assertEqual(status["status"], "available")
        self.assertTrue(status["pipelines"][0]["ready"])
        summary = build_capability_prompt_summary([status])
        self.assertIn("Formula to code: available", summary)
        self.assertIn("math_formula_to_code", summary)
        self.assertIn(
            "outputs: code, language, variable_table, assumptions, example_inputs, semantic_validation",
            summary,
        )
        self.assertIn("semantic_contract", summary)

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

    def test_agent_summary_mentions_ppt_visual_masters_and_renderer_check(self):
        from capability_prompt import build_capability_prompt_summary
        from capability_registry import get_capability_def
        from capability_status import build_capability_status

        capability = build_capability_status(
            get_capability_def("student-ppt"),
            load_packages={},
            enabled_toolsets={"documents", "clarify"},
        )

        summary = build_capability_prompt_summary([capability])

        self.assertIn("visual masters:", summary)
        self.assertIn("soft_editorial=Soft Editorial", summary)
        self.assertIn("neo_grid_bold=Neo Grid Bold", summary)
        self.assertIn("visual_master to pptx_write", summary)
        self.assertIn("visual_master_renderer", summary)
        self.assertIn("pptxgenjs_v1", summary)

    def test_agent_summary_mentions_pdf_writer_renderer_and_html_source(self):
        from capability_prompt import build_capability_prompt_summary
        from capability_registry import get_capability_def
        from capability_status import build_capability_status

        capability = build_capability_status(
            get_capability_def("document-pdf-generation"),
            load_packages={},
            enabled_toolsets={"documents"},
        )

        summary = build_capability_prompt_summary([capability])

        self.assertIn("pdf_write", summary)
        self.assertIn("HTML source", summary)
        self.assertIn("reportlab_pdf_v1", summary)
        self.assertIn("html_path", summary)

    def test_agent_summary_warns_candidate_capabilities_are_not_executable(self):
        from capability_prompt import build_capability_prompt_summary

        summary = build_capability_prompt_summary([
            {
                "id": "math-expression-cleanup",
                "title": "Math expression cleanup",
                "status": "candidate",
                "agentHint": "Candidate only.",
                "requiredLoadPackages": [],
                "pipelines": [],
            }
        ])

        self.assertIn("Math expression cleanup: candidate", summary)
        self.assertIn("not yet executable", summary)


if __name__ == "__main__":
    unittest.main()
