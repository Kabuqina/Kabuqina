# scripts/package-portable-windows.ps1
#
# Stage a unzip-and-run Kabuqina folder + .7z - no MSI/NSIS.
# Requires a release build: `cd tauri; cargo build --release` (or partial `cargo tauri build`
# after the Rust link step succeeds, even if the WiX/MSI step fails).
#
# Layout matches production resource resolution (`resource_dir()/runtime`): see tauri/src/paths.rs.

[CmdletBinding()]
param(
    [string]$RustReleaseDir = "",
    # Fresh Python bundle from build_bundle.ps1 (preferred over stale tauri/target copy).
    [string]$PythonRuntimeDir = "",
    # Where to drop Kabuqina-<ver>-win64-portable.7z
    [string]$OutDir = "",
    # Official release: assert the frontend was built with the real brand
    # overlay applied (scripts/apply-brand-overlay.ps1 -Apply). Default
    # expects the committed placeholder assets.
    [switch]$ExpectBranded
)

$ErrorActionPreference = "Stop"

function Remove-DirRobust {
    <#
    Robust recursive delete: handles read-only attrs, long paths, and AV-induced
    "directory is not empty" races. Falls back to cmd's rmdir which is the most
    forgiving option on Windows.
    #>
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) { return }

    # Pass 1: clear read-only/hidden/system attrs so .NET delete won't refuse.
    Get-ChildItem -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue | ForEach-Object {
        try { $_.Attributes = 'Normal' } catch {}
    }

    for ($i = 0; $i -lt 5; $i++) {
        try {
            [System.IO.Directory]::Delete($Path, $true)
            if (-not (Test-Path -LiteralPath $Path)) { return }
        } catch {
            Start-Sleep -Milliseconds 250
        }
    }

    # Final fallback: cmd's rmdir. Yes, really. /s recursive, /q quiet.
    cmd /c "rmdir /s /q `"$Path`"" *> $null
    if (Test-Path -LiteralPath $Path) {
        throw "Failed to remove $Path (still present after rmdir). Close any process holding files in it (Explorer, AV, indexer) and retry."
    }
}

function Read-TauriVersion {
    param([string]$Root)
    $path = Join-Path $Root "tauri\tauri.conf.json"
    $j = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
    if (-not $j.version -or "$($j.version)" -eq "") {
        throw "Could not read .version from $path"
    }
    return [string]$j.version
}

function Copy-DirFast {
    param(
        [string]$Source,
        [string]$Destination
    )

    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    robocopy $Source $Destination /MIR /R:2 /W:1 /NFL /NDL /NJH /NJS /XD "*.stale_*" "__pycache__" | Out-Host
    $code = $LASTEXITCODE
    if ($code -gt 7) {
        throw "robocopy failed copying $Source to $Destination (exit code $code)."
    }
}

function Resolve-7Zip {
    $cmd = Get-Command "7z.exe" -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    foreach ($candidate in @(
        (Join-Path ${env:ProgramFiles} "7-Zip\7z.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "7-Zip\7z.exe")
    )) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }

    throw "7z.exe not found. Install 7-Zip or add 7z.exe to PATH, then rerun this script."
}

$root = [string](Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if ([string]::IsNullOrWhiteSpace($RustReleaseDir)) {
    $RustReleaseDir = Join-Path $root "tauri\target\release"
}
if ([string]::IsNullOrWhiteSpace($PythonRuntimeDir)) {
    $PythonRuntimeDir = Join-Path $root "python\dist\runtime"
}
if ([string]::IsNullOrWhiteSpace($OutDir)) {
    $OutDir = Join-Path $root "portable-dist"
}

$exe = Join-Path $RustReleaseDir "kabuqina.exe"
if (-not (Test-Path -LiteralPath $exe)) {
    throw "kabuqina.exe not found under $RustReleaseDir - run: cd tauri; cargo build --release"
}

# Brand sentinel (A-R1b Tier 2): web/dist is what the exe build embedded, so
# its mascot <title> tells which asset set went in. Placeholder SVGs carry a
# "Placeholder" title; the private overlay's real artwork does not.
$mascotDist = Join-Path $root "web\dist\kabuqina_mascot.svg"
if (-not (Test-Path -LiteralPath $mascotDist)) {
    throw "web/dist/kabuqina_mascot.svg missing - build the frontend first (cd web; npm run build) so the brand sentinel can be checked."
}
$isPlaceholderBuild = (Get-Content -Raw -LiteralPath $mascotDist) -match "<title>Placeholder"
if ($ExpectBranded -and $isPlaceholderBuild) {
    throw "Expected a branded build, but web/dist holds PLACEHOLDER assets. Run scripts/apply-brand-overlay.ps1 -Apply, rebuild the frontend and exe, then rerun with -ExpectBranded."
}
if (-not $ExpectBranded -and -not $isPlaceholderBuild) {
    throw "web/dist holds REAL brand assets but -ExpectBranded was not passed. For an official release pass -ExpectBranded; otherwise run scripts/apply-brand-overlay.ps1 -Restore and rebuild."
}
Write-Host ("Brand sentinel: {0} build." -f ($(if ($isPlaceholderBuild) { "placeholder" } else { "BRANDED" }))) -ForegroundColor DarkGray

$pyExe = Join-Path $PythonRuntimeDir "python\python.exe"
if (-not (Test-Path -LiteralPath $pyExe)) {
    throw @"
Embedded Python bundle missing ($pyExe).

Run from repo root: .\python\build_bundle.ps1
"@
}

$ver = Read-TauriVersion -Root $root
$pkgBasename = "Kabuqina-$ver-win64-portable"
$stagingRoot = Join-Path $root "_staging_portable"

Remove-DirRobust -Path $stagingRoot
$itemDir = Join-Path $stagingRoot $pkgBasename
New-Item -ItemType Directory -Force -Path $itemDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $itemDir "resources") | Out-Null

Write-Host "Staging portable tree -> $itemDir" -ForegroundColor Cyan

# Copy the app exe (and any sidecar DLLs) from the release dir.
# Exclude build-only artifacts that are not needed at runtime.
$excludeExts = @('.pdb', '.lib', '.rlib', '.exp', '.ilk', '.d', '.cargo-lock')
Get-ChildItem -LiteralPath $RustReleaseDir -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension.ToLowerInvariant() -notin $excludeExts -and $_.Length -gt 0 } |
    ForEach-Object {
        Write-Host "  + $($_.Name)" -ForegroundColor DarkGray
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $itemDir $_.Name) -Force
    }

$stagedExe = Join-Path $itemDir "kabuqina.exe"
if (-not (Test-Path -LiteralPath $stagedExe)) {
    throw "kabuqina.exe was not copied into the portable tree. Check tauri/target/release/ contents."
}

Write-Host "Syncing python/dist/runtime to resources/runtime (authoritative)." -ForegroundColor DarkGray
$dstRuntime = Join-Path $itemDir "resources\runtime"
Remove-DirRobust -Path $dstRuntime
Copy-DirFast -Source $PythonRuntimeDir -Destination $dstRuntime
Get-ChildItem -LiteralPath $dstRuntime -Directory -Filter "*.stale_*" -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-DirRobust -Path $_.FullName }

# Tauri `cargo build` also places runtime beside the exe (`target/release/runtime`).
# Mirror that layout so path resolution works even if `resource_dir()` differs.
$dstRuntimeSibling = Join-Path $itemDir "runtime"
Remove-DirRobust -Path $dstRuntimeSibling
Copy-DirFast -Source $PythonRuntimeDir -Destination $dstRuntimeSibling
Get-ChildItem -LiteralPath $dstRuntimeSibling -Directory -Filter "*.stale_*" -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-DirRobust -Path $_.FullName }
Write-Host "  mirrored runtime/ next to kabuqina.exe" -ForegroundColor DarkGray

# If Tauri already staged extra bundle files (beside runtime), merge them - do not wipe our runtime.
$TauriResources = Join-Path $RustReleaseDir "resources"
if (Test-Path -LiteralPath $TauriResources) {
    Write-Host "Merging $($TauriResources) extras (excluding runtime subtree) ..." -ForegroundColor DarkGray
    Get-ChildItem -LiteralPath $TauriResources -Force -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.Name -eq "runtime") { return }
        $destPath = Join-Path (Join-Path $itemDir "resources") $_.Name
        Copy-Item -LiteralPath $_.FullName -Destination $destPath -Recurse -Force
    }
}

foreach ($docName in @("README.md", "LICENSE")) {
    $docPath = Join-Path $root $docName
    if (Test-Path -LiteralPath $docPath) {
        Copy-Item -LiteralPath $docPath -Destination (Join-Path $itemDir $docName) -Force
    }
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$sevenZip = Resolve-7Zip
$archivePath = Join-Path $OutDir "$pkgBasename.7z"
if (Test-Path -LiteralPath $archivePath) {
    Remove-Item -Force -LiteralPath $archivePath
}

Write-Host "Compressing to $archivePath" -ForegroundColor Cyan
& $sevenZip a -t7z -mx=9 -mmt=on $archivePath $itemDir | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "7-Zip failed creating $archivePath (exit code $LASTEXITCODE)."
}

Write-Host ""
Write-Host "Portable package ready." -ForegroundColor Green
Write-Host "  Folder: $itemDir"
Write-Host "  7z:     $archivePath"
Write-Host ""
Write-Host "Recipients: extract anywhere and run kabuqina.exe (Windows 10 or 11 x64; WebView2 required)." -ForegroundColor DarkGray
