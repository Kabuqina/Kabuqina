from __future__ import annotations

from pathlib import Path
from unittest import SkipTest
import unittest


ROOT = Path(__file__).resolve().parents[2]


class BundleVisualMasterTests(unittest.TestCase):
    def test_bundle_scripts_copy_ppt_visual_master_assets(self):
        expected_fragment = 'assets"'
        expected_leaf = '"visual-masters"'

        for script in [
            ROOT / "python" / "build_bundle.ps1",
            ROOT / "scripts" / "sync-runtime-sources.ps1",
        ]:
            text = script.read_text(encoding="utf-8")
            self.assertIn(
                expected_fragment,
                text,
                f"{script.name} must copy assets/ppt/visual-masters into the runtime bundle",
            )
            self.assertIn(
                expected_leaf,
                text,
                f"{script.name} must copy assets/ppt/visual-masters into the runtime bundle",
            )

    def test_existing_runtime_contains_ppt_visual_master_assets(self):
        runtime = ROOT / "python" / "dist" / "runtime"
        if not (runtime / "python" / "python.exe").exists():
            raise SkipTest("runtime bundle is not built")

        visual_masters = runtime / "assets" / "ppt" / "visual-masters"
        self.assertTrue((visual_masters / "manifest.json").exists())
        self.assertTrue((visual_masters / "blue-professional" / "template.pptx").exists())
