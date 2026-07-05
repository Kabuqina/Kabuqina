# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Drift tests binding the desk capability registry to the STUDY learning
contract/registry by STABLE ID only.

The catalog must reference the learning Planner id, learning artifact kinds, and
framework stage ids — never duplicate their prompts or schemas. These tests fail
if a referenced id does not exist in ``hermes_core`` (forward drift) or if the
contract gains a kind the catalog never references (backward drift).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
CORE_DIR = Path(__file__).resolve().parents[2] / "hermes_core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))


def _learning_capabilities() -> list[dict]:
    from capability_registry import list_capability_defs

    # A learning capability is marked by referencing learning output kinds.
    return [c for c in list_capability_defs() if "learning_output_kinds" in c]


def _learning_capability() -> dict:
    for cap in _learning_capabilities():
        if cap["id"] == "student-learning-foundation":
            return cap
    raise AssertionError("student-learning-foundation missing")


class LearningCapabilityDriftTests(unittest.TestCase):
    def test_learning_capability_is_registered(self):
        caps = _learning_capabilities()
        self.assertTrue(caps, "no learning capability registered")
        self.assertIn("student-learning-foundation", {c["id"] for c in caps})

    def test_learning_capability_remains_candidate_until_ui_exists(self):
        from capability_status import build_capability_status

        cap = _learning_capability()
        self.assertEqual(cap.get("lifecycle"), "candidate")
        self.assertNotIn("status", cap)

        status = build_capability_status(cap, {}, enabled_toolsets={"learning"})
        self.assertEqual(status["status"], "candidate")
        self.assertEqual(status["lifecycle"], "candidate")
        self.assertTrue(status["pipelines"])
        self.assertTrue(all(pipeline["ready"] is False for pipeline in status["pipelines"]))

    def test_referenced_planner_ids_exist(self):
        from learning.planner_registry import planner_ids

        valid = planner_ids()
        for cap in _learning_capabilities():
            pid = cap.get("learning_planner_id")
            self.assertIsNotNone(pid, f"{cap['id']} missing learning_planner_id")
            self.assertIn(pid, valid, f"{cap['id']} references unknown planner {pid!r}")
            for pipeline in cap.get("pipelines") or []:
                for step in pipeline.get("steps") or []:
                    step_pid = step.get("planner_id")
                    if step_pid is not None:
                        self.assertIn(step_pid, valid)

    def test_referenced_kinds_all_exist(self):
        from learning.learning_contract import KINDS

        for cap in _learning_capabilities():
            for kind in cap.get("learning_output_kinds") or []:
                self.assertIn(kind, KINDS, f"{cap['id']} references unknown kind {kind!r}")

    def test_catalog_covers_every_contract_kind(self):
        # Backward drift: adding a kind to the contract must be reflected here.
        from learning.learning_contract import KINDS

        referenced: set[str] = set()
        for cap in _learning_capabilities():
            referenced |= set(cap.get("learning_output_kinds") or [])
        self.assertEqual(referenced, set(KINDS))

    def test_stage_ids_are_framework_stages(self):
        from capability_registry import VALID_FRAMEWORK_STAGES

        for cap in _learning_capabilities():
            for pipeline in cap.get("pipelines") or []:
                for stage in pipeline.get("stages") or []:
                    self.assertIn(stage, VALID_FRAMEWORK_STAGES)

    def test_no_prompt_or_schema_duplication(self):
        # Learning entries carry id/tool references, not prompts or payload schemas.
        for cap in _learning_capabilities():
            self.assertNotIn("prompt", cap)
            self.assertNotIn("schema", cap)
            for kind in cap.get("learning_output_kinds") or []:
                self.assertIsInstance(kind, str)

    def test_capability_definitions_still_valid(self):
        # The learning entry must not introduce a phantom/undeclared stage.
        from capability_registry import validate_capability_definitions

        self.assertEqual(validate_capability_definitions(), [])


if __name__ == "__main__":
    unittest.main()
