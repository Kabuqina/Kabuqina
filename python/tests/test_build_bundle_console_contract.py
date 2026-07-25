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
        self.assertIn('$info.PSObject.Properties["verified"]', text)
        self.assertRegex(text, r"verified\s+= \[bool\]\$Verify")
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

    def test_failed_verification_cannot_publish_or_reuse_success_marker(self):
        text = (ROOT / "python" / "build_bundle.ps1").read_text(encoding="utf-8")

        invalidate = (
            'Remove-BundlePathStrict -Path $bundleInfoPath '
            '-Label "bundle success marker"'
        )
        write_marker = (
            "$info | ConvertTo-Json | "
            "Set-Content -Path $bundleInfoPath -Encoding UTF8"
        )

        self.assertLess(text.index("Test-RecentCompletedBundle"), text.index(invalidate))
        self.assertLess(text.index('Write-Host "STT binaries OK"'), text.index(write_marker))
        self.assertLess(text.index(write_marker), text.index('Write-Host "Bundle ready at $Dist'))

    def test_rebuild_strictly_replaces_core_and_retires_root_worker(self):
        text = (ROOT / "python" / "build_bundle.ps1").read_text(encoding="utf-8")

        self.assertIn(
            'Remove-BundlePathStrict -Path $bundledCore -Label "bundled core"',
            text,
        )
        self.assertIn(
            'foreach ($retiredRootPath in @("feishu_qr_worker.py", "wecom_qr_worker.py"))',
            text,
        )
        self.assertIn('"gateway\\platforms\\discord.py"', text)
        self.assertIn('"gateway\\platforms\\feishu.py"', text)
        self.assertIn('"gateway\\platforms\\wecom.py"', text)
        self.assertIn('"gateway\\platforms\\wecom_callback.py"', text)
        self.assertIn('"gateway\\platforms\\wecom_crypto.py"', text)
        self.assertIn('"gateway\\platforms\\slack.py"', text)
        self.assertIn('"gateway\\platforms\\yuanbao.py"', text)
        self.assertIn('"tools\\homeassistant_tool.py"', text)
        self.assertIn('"tools\\yuanbao_tools.py"', text)
        self.assertIn('"plugins\\platforms"', text)


if __name__ == "__main__":
    unittest.main()
