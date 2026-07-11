# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
#
# Tier 2 brand overlay (A-R1b): swap the committed placeholder assets for the
# real Kabuqina artwork from the private repo, and back.
#
#   apply-brand-overlay.ps1 -Apply    # placeholder -> real (working tree only)
#   apply-brand-overlay.ps1 -Restore  # real -> placeholder (git checkout)
#   apply-brand-overlay.ps1 -Check    # assert the tree holds the committed
#                                     # placeholder set (guard for CI/tests)
#
# The overlay source is $env:KABUQINA_BRAND_DIR (or -BrandDir), a local
# checkout of the private Kabuqina/kabuqina-mascot repository. Only files that
# exist under its overlay/ tree are copied — never a wildcard over the target
# directories. Real assets must never be committed to this repository.

[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$Restore,
    [switch]$Check,
    [string]$BrandDir = $env:KABUQINA_BRAND_DIR
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$targets = @("web/public", "tauri/icons")

$modes = @($Apply, $Restore, $Check) | Where-Object { $_ }
if ($modes.Count -ne 1) {
    throw "Pass exactly one of -Apply, -Restore, -Check."
}

function Get-TargetStatus {
    (git -C $repo status --porcelain -- @targets) | Where-Object { $_ }
}

if ($Check) {
    $dirty = Get-TargetStatus
    if ($dirty) {
        $dirty | ForEach-Object { Write-Host $_ }
        throw "Brand asset paths differ from the committed placeholder set. Run -Restore before committing or testing."
    }
    Write-Host "OK: web/public and tauri/icons match the committed placeholder set."
    exit 0
}

if ($Restore) {
    git -C $repo checkout -- @targets
    if ($LASTEXITCODE -ne 0) { throw "git checkout failed" }
    Write-Host "Restored committed placeholder assets."
    exit 0
}

# ── -Apply ─────────────────────────────────────────────────────────────── #

if (-not $BrandDir) {
    throw "Set KABUQINA_BRAND_DIR (or pass -BrandDir) to the local kabuqina-mascot checkout."
}
$overlay = Join-Path $BrandDir "overlay"
if (-not (Test-Path (Join-Path $overlay "web/public/kabuqina_mascot.svg"))) {
    throw "No overlay tree at '$overlay' — wrong path or incomplete private checkout."
}

$dirty = Get-TargetStatus
if ($dirty) {
    $dirty | ForEach-Object { Write-Host $_ }
    throw "web/public or tauri/icons already differ from HEAD; run -Restore (or commit your changes) first."
}

# Copy exactly the files present in the overlay tree (README.md excluded so
# the private copy never clobbers the public one).
$files = Get-ChildItem -Path $overlay -Recurse -File | Where-Object { $_.Name -ne "README.md" }
$count = 0
foreach ($file in $files) {
    $relative = [System.IO.Path]::GetRelativePath($overlay, $file.FullName)
    $destination = Join-Path $repo $relative
    New-Item -ItemType Directory -Force (Split-Path -Parent $destination) | Out-Null
    Copy-Item -Force $file.FullName $destination
    $count++
}

Write-Host ""
Write-Host "=== OFFICIAL BRANDED BUILD: $count real assets applied over placeholders ===" -ForegroundColor Yellow
Write-Host "Working tree is now dirty on purpose. Run '-Restore' after building;"
Write-Host "never commit while the overlay is applied."
