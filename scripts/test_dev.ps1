# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$DevScript = Get-Content -Raw -LiteralPath (Join-Path $Root "scripts\dev.ps1")
$ViteSentinel = 'Test-Path "web\node_modules\.bin\vite.cmd"'

if (-not $DevScript.Contains($ViteSentinel)) {
    throw "dev.ps1 must install web dependencies when the Vite command is missing"
}

$SyncScript = Get-Content -Raw -LiteralPath (Join-Path $Root "scripts\sync-runtime-sources.ps1")
if (-not $SyncScript.Contains("[switch]`$IncludeSkills")) {
    throw "sync-runtime-sources.ps1 must expose -IncludeSkills for explicit full skill syncs"
}
if (-not $SyncScript.Contains('if ($IncludeSkills)')) {
    throw "sync-runtime-sources.ps1 must keep the large hermes_core/skills tree out of the default fast sync"
}

Write-Host "dev dependency sentinel test passed" -ForegroundColor Green
