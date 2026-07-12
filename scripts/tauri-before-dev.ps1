# Prepares the bundled Python runtime before Tauri starts the web dev server.
# This runs for direct `cargo tauri dev` launches as well as scripts/dev.ps1.

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $root
try {
    if ($env:KABUQINA_RUNTIME_SYNCED -ne "1") {
        if (-not (Test-Path "python\dist\runtime\python\python.exe")) {
            Write-Host "Building Python bundle..." -ForegroundColor Cyan
            ./python/build_bundle.ps1
        } else {
            Write-Host "Syncing runtime sources for Tauri dev..." -ForegroundColor DarkGray
            ./scripts/sync-runtime-sources.ps1
        }
    }

    if (-not (Test-Path "web\node_modules\.bin\vite.cmd")) {
        Write-Host "Installing web deps..." -ForegroundColor Cyan
        Push-Location web
        npm ci
        Pop-Location
    }

    Push-Location web
    npm run dev
    $exitCode = $LASTEXITCODE
    Pop-Location
    exit $exitCode
} finally {
    Pop-Location
}
