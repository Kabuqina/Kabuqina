# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$DevScript = Get-Content -Raw -LiteralPath (Join-Path $Root "scripts\dev.ps1")
$ViteSentinel = 'Test-Path "web\node_modules\.bin\vite.cmd"'

if (-not $DevScript.Contains($ViteSentinel)) {
    throw "dev.ps1 must install web dependencies when the Vite command is missing"
}

Write-Host "dev dependency sentinel test passed" -ForegroundColor Green
