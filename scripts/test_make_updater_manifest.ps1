# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Temp = Join-Path ([System.IO.Path]::GetTempPath()) ("kabuqina-updater-manifest-test-" + [System.Guid]::NewGuid().ToString("N"))
$BundleDir = Join-Path $Temp "nsis"
$Out = Join-Path $Temp "latest-v2.json"

New-Item -ItemType Directory -Force -Path $BundleDir | Out-Null

try {
    $installer = Join-Path $BundleDir "Kabuqina_0.4.0_x64-setup.exe"
    $zip = Join-Path $BundleDir "Kabuqina_0.4.0_x64-setup.nsis.zip"
    $sig = Join-Path $BundleDir "Kabuqina_0.4.0_x64-setup.nsis.zip.sig"
    Set-Content -Path $installer -Value "installer" -Encoding UTF8
    Set-Content -Path $zip -Value "updater zip" -Encoding UTF8
    Set-Content -Path $sig -Value "sig-value" -Encoding UTF8

    # A stale bundle from another version must never be selected.
    Set-Content -Path (Join-Path $BundleDir "Kabuqina_0.3.0_x64-setup.exe") -Value "stale installer" -Encoding UTF8
    Set-Content -Path (Join-Path $BundleDir "Kabuqina_0.3.0_x64-setup.nsis.zip") -Value "stale zip" -Encoding UTF8
    Set-Content -Path (Join-Path $BundleDir "Kabuqina_0.3.0_x64-setup.nsis.zip.sig") -Value "stale sig" -Encoding UTF8

    & (Join-Path $Root "scripts\make_updater_manifest.ps1") `
        -Version "v0.4.0" `
        -BundleDir $BundleDir `
        -AssetBaseUrl "https://downloads.example.test/kabuqina" `
        -Out $Out `
        -Notes "Test notes"

    if (-not (Test-Path -LiteralPath $Out)) {
        throw "manifest was not written"
    }

    $json = Get-Content -Raw -LiteralPath $Out | ConvertFrom-Json
    if ($json.version -ne "0.4.0") {
        throw "version mismatch: $($json.version)"
    }
    if ($json.notes -ne "Test notes") {
        throw "notes mismatch: $($json.notes)"
    }
    $platform = $json.platforms.'windows-x86_64'
    if (-not $platform) {
        throw "missing windows-x86_64 platform"
    }
    if ($platform.url -ne "https://downloads.example.test/kabuqina/Kabuqina_0.4.0_x64-setup.nsis.zip") {
        throw "unexpected updater URL: $($platform.url)"
    }
    if ($platform.signature -ne "sig-value") {
        throw "signature mismatch: $($platform.signature)"
    }

    # Ambiguous artifacts for the target version must fail closed.
    $duplicateInstaller = Join-Path $BundleDir "Kabuqina-copy_0.4.0_x64-setup.exe"
    $duplicateZip = Join-Path $BundleDir "Kabuqina-copy_0.4.0_x64-setup.nsis.zip"
    Set-Content -Path $duplicateInstaller -Value "duplicate installer" -Encoding UTF8
    Set-Content -Path $duplicateZip -Value "duplicate zip" -Encoding UTF8
    Set-Content -Path "$duplicateZip.sig" -Value "duplicate sig" -Encoding UTF8

    $duplicateRejected = $false
    try {
        & (Join-Path $Root "scripts\make_updater_manifest.ps1") `
            -Version "v0.4.0" `
            -BundleDir $BundleDir `
            -Out $Out
    }
    catch {
        $duplicateRejected = $true
    }
    if (-not $duplicateRejected) {
        throw "duplicate target-version artifacts were not rejected"
    }

    Write-Host "make_updater_manifest test passed" -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $Temp) {
        Remove-Item -LiteralPath $Temp -Recurse -Force
    }
}
