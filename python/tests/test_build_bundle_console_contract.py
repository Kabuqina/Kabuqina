from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class BuildBundleConsoleContractTests(unittest.TestCase):
    def test_suppresses_powershell_progress_overlay(self):
        text = (ROOT / "python" / "build_bundle.ps1").read_text(encoding="utf-8")

        self.assertIn('$ProgressPreference = "SilentlyContinue"', text)

    def test_prints_stage_labels_before_long_operations(self):
        text = (ROOT / "python" / "build_bundle.ps1").read_text(encoding="utf-8")

        pip_label = 'Write-Host "[bundle] 5/8 Installing Python dependencies..."'
        copy_label = 'Write-Host "[bundle] 6/8 Copying runtime sources..."'
        pip_install = "& $Py -m pip install `"
        copy_overlays = 'Copy-Item -Recurse -Force (Join-Path $PSScriptRoot "overlays") $overlaysDest'

        self.assertLess(text.index(pip_label), text.index(pip_install))
        self.assertLess(text.index(copy_label), text.index(copy_overlays))

    def test_skips_immediate_duplicate_run_before_destructive_cleanup(self):
        text = (ROOT / "python" / "build_bundle.ps1").read_text(encoding="utf-8")

        self.assertIn("[switch]$Force", text)
        self.assertIn("Test-BundleSentinels", text)
        self.assertIn("Skipping immediate duplicate bundle run", text)
        self.assertIn("Pass -Force or -Clean", text)
        self.assertNotIn("Test-BundleSourcesNewerThan", text)

        guard = "Skipping immediate duplicate bundle run"
        first_destructive_cleanup = 'Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $BuildDir, $Dist'
        self.assertLess(text.index(guard), text.index(first_destructive_cleanup))

    def test_success_marker_pauses_before_returning_to_interactive_shell(self):
        text = (ROOT / "python" / "build_bundle.ps1").read_text(encoding="utf-8")

        self.assertIn("[switch]$NoSuccessPause", text)
        self.assertIn("Invoke-BundleSuccessPause", text)
        self.assertIn("Start-Sleep -Seconds 5", text)
        self.assertIn("HERMESDESK_NO_BUNDLE_SUCCESS_PAUSE", text)

        ready_line = 'Write-Host "Bundle ready at $Dist  ($($info.bundleSizeMb) MB)"'
        pause_call = "Invoke-BundleSuccessPause"
        self.assertLess(text.index(ready_line), text.rindex(pause_call))


if __name__ == "__main__":
    unittest.main()
