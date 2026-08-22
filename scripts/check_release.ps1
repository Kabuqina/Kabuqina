# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

param(
    [string]$ExpectedVersion = ""
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$ConfigPath = Join-Path $Root "tauri\tauri.conf.json"
$CargoTomlPath = Join-Path $Root "tauri\Cargo.toml"
$WebPackagePath = Join-Path $Root "web\package.json"
$WebLockPath = Join-Path $Root "web\package-lock.json"

$config = Get-Content -Raw -LiteralPath $ConfigPath | ConvertFrom-Json
$webPackage = Get-Content -Raw -LiteralPath $WebPackagePath | ConvertFrom-Json
$webLock = Get-Content -Raw -LiteralPath $WebLockPath | ConvertFrom-Json -AsHashtable
$cargoToml = Get-Content -Raw -LiteralPath $CargoTomlPath
$cargoVersionMatch = [regex]::Match($cargoToml, '(?ms)^\[package\]\s+name\s*=\s*"kabuqina"\s+version\s*=\s*"([^"]+)"')

if (-not $cargoVersionMatch.Success) {
    throw "could not read package.version from tauri/Cargo.toml"
}

$versions = [ordered]@{
    "tauri/tauri.conf.json" = [string]$config.version
    "tauri/Cargo.toml" = $cargoVersionMatch.Groups[1].Value
    "web/package.json" = [string]$webPackage.version
    "web/package-lock.json" = [string]$webLock["version"]
    "web/package-lock.json root package" = [string]$webLock["packages"][""]["version"]
}
$distinctVersions = @($versions.Values | Select-Object -Unique)
if ($distinctVersions.Count -ne 1) {
    throw "release versions are not aligned: $($versions | ConvertTo-Json -Compress)"
}

$releaseVersion = $distinctVersions[0]
if ($ExpectedVersion) {
    $cleanExpectedVersion = $ExpectedVersion.TrimStart('v')
    if ($releaseVersion -ne $cleanExpectedVersion) {
        throw "release version $releaseVersion does not match tag $ExpectedVersion"
    }

    $releaseNotesPath = Join-Path $Root "docs\releases\$ExpectedVersion.md"
    if (-not (Test-Path -LiteralPath $releaseNotesPath)) {
        throw "release notes are missing: docs/releases/$ExpectedVersion.md"
    }
}

Write-Host "release configuration passed for v$releaseVersion" -ForegroundColor Green
