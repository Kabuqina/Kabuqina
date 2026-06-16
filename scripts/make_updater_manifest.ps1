# scripts/make_updater_manifest.ps1
#
# Produces latest.json for Tauri's updater plugin. Must be uploaded to the
# release alongside the .msi and the .msi.sig.
#
# Schema: https://v2.tauri.app/plugin/updater/#static-json-file

param(
    [Parameter(Mandatory)] [string]$Version,           # e.g. v0.1.0
    [string]$BundleDir = "tauri/target/release/bundle/msi",
    [string]$Notes = "See release notes on GitHub.",
    [string]$Repo = $env:GITHUB_REPOSITORY,            # set by Actions
    [string]$AssetBaseUrl = "",
    [string]$Out = "latest.json"
)

$ErrorActionPreference = "Stop"

if (-not $Repo) { $Repo = "Kabuqina/Kabuqina" }

$zip = Get-ChildItem -Path $BundleDir -Filter "*.msi.zip" | Select-Object -First 1
$sig = Get-ChildItem -Path $BundleDir -Filter "*.msi.zip.sig" | Select-Object -First 1
if (-not $zip) { throw "no .msi.zip found in $BundleDir (enable bundle.createUpdaterArtifacts)" }
if (-not $sig) { throw "no .msi.zip.sig found in $BundleDir (configure tauri updater signing key)" }

$cleanVer = $Version.TrimStart('v')
if (-not $AssetBaseUrl) {
    $AssetBaseUrl = "https://github.com/$Repo/releases/download/$Version"
}
$AssetBaseUrl = $AssetBaseUrl.TrimEnd('/')
$url = "$AssetBaseUrl/$($zip.Name)"
$signature = (Get-Content -Raw $sig.FullName).Trim()

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
