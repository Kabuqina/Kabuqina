# scripts/make_updater_manifest.ps1
#
# Produces latest-v2.json for Tauri's updater plugin. Must be uploaded to the
# release alongside the *-setup.exe and the *-setup.nsis.zip(.sig).
#
# Schema: https://v2.tauri.app/plugin/updater/#static-json-file

param(
    [Parameter(Mandatory)] [string]$Version,           # e.g. v0.2.0
    [string]$BundleDir = "tauri/target/release/bundle/nsis",
    [string]$Notes = "See release notes on GitHub.",
    [string]$Repo = $env:GITHUB_REPOSITORY,            # set by Actions
    [string]$AssetBaseUrl = "",
    [string]$Out = "latest-v2.json"
)

$ErrorActionPreference = "Stop"

if (-not $Repo) { $Repo = "Kabuqina/Kabuqina" }

$cleanVer = $Version.TrimStart('v')
if ($cleanVer -notmatch '^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$') {
    throw "Version must be a semantic version such as v0.4.0: $Version"
}

$artifactPattern = "*_${cleanVer}_*-setup"
$installers = @(Get-ChildItem -Path $BundleDir -Filter "$artifactPattern.exe")
$zips = @(Get-ChildItem -Path $BundleDir -Filter "$artifactPattern.nsis.zip")
if ($installers.Count -ne 1) {
    throw "expected exactly one v$cleanVer *-setup.exe in $BundleDir, found $($installers.Count)"
}
if ($zips.Count -ne 1) {
    throw "expected exactly one v$cleanVer *-setup.nsis.zip in $BundleDir, found $($zips.Count)"
}

$zip = $zips[0]
$sigPath = "$($zip.FullName).sig"
if (-not (Test-Path -LiteralPath $sigPath)) {
    throw "missing updater signature for $($zip.Name): $($zip.Name).sig"
}

if (-not $AssetBaseUrl) {
    $AssetBaseUrl = "https://github.com/$Repo/releases/download/$Version"
}
$AssetBaseUrl = $AssetBaseUrl.TrimEnd('/')
$url = "$AssetBaseUrl/$($zip.Name)"
$signature = (Get-Content -Raw -LiteralPath $sigPath).Trim()
if ([string]::IsNullOrWhiteSpace($signature)) {
    throw "updater signature is empty: $($zip.Name).sig"
}

$manifest = [ordered]@{
    version    = $cleanVer
    notes      = $Notes
    pub_date   = (Get-Date).ToString("o")
    platforms  = [ordered]@{
        "windows-x86_64" = [ordered]@{
            signature = $signature
            url       = $url
        }
    }
}

$manifest | ConvertTo-Json -Depth 6 | Set-Content -Path $Out -Encoding UTF8
Write-Host "wrote $Out for $Version" -ForegroundColor Green
