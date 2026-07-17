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

$OldPublicKey = "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IEIxMjkwMzI5MzI3NzAzNzEKUldSeEEzY3lLUU1wc1RCN3p4MXJpNkMvYVRxbHdLMldERkpjMStqWDdxRHR3OWFYQlJ0OTdFcDAK"
$ExpectedEndpoints = @(
    "https://kabuqina-installer-1428509047.cos.ap-guangzhou.myqcloud.com/latest-v2.json",
    "https://github.com/Kabuqina/Kabuqina/releases/latest/download/latest-v2.json"
)

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

$actualEndpoints = @($config.plugins.updater.endpoints)
if ($actualEndpoints.Count -ne $ExpectedEndpoints.Count) {
    throw "updater endpoints must contain exactly the COS and GitHub latest-v2.json URLs"
}
for ($i = 0; $i -lt $ExpectedEndpoints.Count; $i++) {
    if ([string]$actualEndpoints[$i] -ne $ExpectedEndpoints[$i]) {
        throw "updater endpoint $i must be $($ExpectedEndpoints[$i])"
    }
}

$publicKey = [string]$config.plugins.updater.pubkey
if ([string]::IsNullOrWhiteSpace($publicKey)) {
    throw "updater public key is missing"
}
if ($publicKey -eq $OldPublicKey) {
    throw "updater public key is still the retired v0.2/v0.3 key; install the new v2 public key before building NSIS"
}

try {
    $decodedPublicKey = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($publicKey))
}
catch {
    throw "updater public key is not valid base64: $($_.Exception.Message)"
}
if ($decodedPublicKey -notmatch 'minisign public key') {
    throw "updater public key does not decode to a minisign public key"
}

Write-Host "updater release configuration passed for v$releaseVersion" -ForegroundColor Green
