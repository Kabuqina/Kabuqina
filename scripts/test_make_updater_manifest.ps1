# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Temp = Join-Path ([System.IO.Path]::GetTempPath()) ("kabuqina-updater-manifest-test-" + [System.Guid]::NewGuid().ToString("N"))
$BundleDir = Join-Path $Temp "msi"
$Out = Join-Path $Temp "latest.json"

New-Item -ItemType Directory -Force -Path $BundleDir | Out-Null

try {
    $msi = Join-Path $BundleDir "Kabuqina_0.2.0_x64_en-US.msi"
    $zip = Join-Path $BundleDir "Kabuqina_0.2.0_x64_en-US.msi.zip"
    $sig = Join-Path $BundleDir "Kabuqina_0.2.0_x64_en-US.msi.zip.sig"
    Set-Content -Path $msi -Value "installer" -Encoding UTF8
    Set-Content -Path $zip -Value "updater zip" -Encoding UTF8
    Set-Content -Path $sig -Value "sig-value" -Encoding UTF8

    & (Join-Path $Root "scripts\make_updater_manifest.ps1") `
        -Version "v0.2.0" `
        -BundleDir $BundleDir `
        -AssetBaseUrl "https://downloads.example.test/kabuqina" `
        -Out $Out `
        -Notes "Test notes"

    if (-not (Test-Path -LiteralPath $Out)) {
        throw "manifest was not written"
    }

    $json = Get-Content -Raw -LiteralPath $Out | ConvertFrom-Json
    if ($json.version -ne "0.2.0") {
        throw "version mismatch: $($json.version)"
    }
    if ($json.notes -ne "Test notes") {
        throw "notes mismatch: $($json.notes)"
    }
    $platform = $json.platforms.'windows-x86_64'
    if (-not $platform) {
        throw "missing windows-x86_64 platform"
    }
    if ($platform.url -ne "https://downloads.example.test/kabuqina/Kabuqina_0.2.0_x64_en-US.msi.zip") {
        throw "unexpected updater URL: $($platform.url)"
    }
    if ($platform.signature -ne "sig-value") {
        throw "signature mismatch: $($platform.signature)"
    }

    Write-Host "make_updater_manifest test passed" -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $Temp) {
        Remove-Item -LiteralPath $Temp -Recurse -Force
    }
}
