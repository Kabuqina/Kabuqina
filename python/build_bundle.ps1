# python/build_bundle.ps1
#
# Produces a self-contained Python bundle suitable for shipping inside
# the Tauri installer.
#
# Output: python/dist/runtime/
#   ├── python/                   <- standalone CPython 3.11 (python.exe etc.)
#   ├── site-packages/            <- pruned Hermes + its deps
#   ├── hermes/                   <- the upstream submodule, prune-copied in
#   ├── overlays/                 <- HermesDesk runtime overlays
#   ├── desktop_entrypoint.py     <- Tauri spawns this
#   ├── weixin_qr_worker.py       <- optional Route C Weixin QR child
#   └── BUNDLE_INFO.json          <- versions + hashes for the updater
#
# Usage:
#   .\python\build_bundle.ps1                # build
#   .\python\build_bundle.ps1 -Verify        # build + smoke-test (+ STT binary checks)
#   .\python\build_bundle.ps1 -Clean         # wipe and rebuild
#   .\python\build_bundle.ps1 -Force         # rebuild even if a fresh bundle already exists
#   .\python\build_bundle.ps1 -NoSuccessPause # don't pause after success in an interactive shell
#   .\python\build_bundle.ps1 -SkipWebBuild  # legacy no-op; upstream Hermes dashboard is not bundled
#   .\python\build_bundle.ps1 -BundleDoclingModels  # dev/offline: embed Docling models despite larger installer
#
# NOTE (PowerShell): named parameters conventionally use ONE dash (`-Verify`), unlike many
# POSIX/GNU CLIs (`--verify`). Passing `--Verify` unquoted can accidentally bind as -PythonVersion
# and corrupt the download URL — we remap common `--flags` below for muscle memory.

[CmdletBinding()]
param(
    [string]$PythonVersion = "3.11.15",
    [string]$PbsRelease    = "20260414",   # python-build-standalone tag (latest as of 2026-04-19)
    [switch]$Clean,
    [switch]$Force,
    [switch]$NoSuccessPause,
    [switch]$Verify,
    [switch]$SkipWebBuild,
    [switch]$SkipDoclingModels,
    [switch]$BundleDoclingModels
)

# Recover GNU-style `--Flag` mistakenly bound to positional -PythonVersion (PowerShell habit vs
# Rust/npm/git habit).
if ($PythonVersion -match '^-{2,}(.+)$') {
    $gnu = $matches[1].ToLowerInvariant()
    $defaultPy = '3.11.15'
    switch ($gnu) {
        'verify' {
            Write-Warning "Interpreting '$PythonVersion' as -Verify (PowerShell prefers -Verify over --Verify)."
            $PythonVersion = $defaultPy
            $Verify = $true
            break
        }
        'clean' {
            Write-Warning "Interpreting '$PythonVersion' as -Clean."
            $PythonVersion = $defaultPy
            $Clean = $true
            break
        }
        'force' {
            Write-Warning "Interpreting '$PythonVersion' as -Force."
            $PythonVersion = $defaultPy
            $Force = $true
            break
        }
        'nosuccesspause' {
            Write-Warning "Interpreting '$PythonVersion' as -NoSuccessPause."
            $PythonVersion = $defaultPy
            $NoSuccessPause = $true
            break
        }
        'skipwebbuild' {
            Write-Warning "Interpreting '$PythonVersion' as -SkipWebBuild."
            $PythonVersion = $defaultPy
            $SkipWebBuild = $true
            break
        }
        'skipdoclingmodels' {
            Write-Warning "Interpreting '$PythonVersion' as -SkipDoclingModels."
            $PythonVersion = $defaultPy
            $SkipDoclingModels = $true
            break
        }
        'bundledoclingmodels' {
            Write-Warning "Interpreting '$PythonVersion' as -BundleDoclingModels."
            $PythonVersion = $defaultPy
            $BundleDoclingModels = $true
            break
        }
        default {
            Write-Error @"
Unknown option '$PythonVersion'. If you meant a switch, PowerShell expects one hyphen (-Verify).

If you intended a Python version string, expected form is like 3.11.15.
"@
            exit 99
        }
    }
}

if ($PythonVersion -notmatch '^\d+\.\d+(\.\d+)?') {
    Write-Error @"
Invalid -PythonVersion '$PythonVersion'. Expected something like 3.11.15.

Common mistake: use -Verify not --Verify unless this script rewrote GNU-style arguments (see header).
"@
    exit 99
}

if ($SkipWebBuild) {
    Write-Warning "-SkipWebBuild is retained for compatibility; the upstream Hermes dashboard SPA is no longer bundled."
}

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Root      = Resolve-Path (Join-Path $PSScriptRoot "..")
$BuildDir  = Join-Path $PSScriptRoot "_build"
$Download  = Join-Path $PSScriptRoot "_download"
$Dist      = Join-Path $PSScriptRoot "dist\runtime"
$CoreDir   = Join-Path $Root "hermes_core"

function Test-BundleSentinels {
    param([string]$Runtime)

    $required = @(
        "BUNDLE_INFO.json",
        "python\python.exe",
        "kabuqina\run_agent.py",
        "site-packages\yaml\__init__.py",
        "site-packages\fastapi\__init__.py",
        "site-packages\uvicorn\__init__.py",
        "site-packages\click\__init__.py",
        "overlays\__init__.py",
        "desktop_entrypoint.py"
    )

    foreach ($rel in $required) {
        if (-not (Test-Path -LiteralPath (Join-Path $Runtime $rel))) {
            return $false
        }
    }
    return $true
}

function Test-RecentCompletedBundle {
    param([string]$Runtime)

    $infoPath = Join-Path $Runtime "BUNDLE_INFO.json"
    if (-not (Test-Path -LiteralPath $infoPath)) { return $false }
    if (-not (Test-BundleSentinels -Runtime $Runtime)) { return $false }

    try {
        $info = Get-Content -Raw -LiteralPath $infoPath | ConvertFrom-Json
        $builtAt = [DateTimeOffset]::Parse([string]$info.builtAt)
    } catch {
        return $false
    }

    $ageMinutes = ([DateTimeOffset]::UtcNow - $builtAt.ToUniversalTime()).TotalMinutes
    if ($ageMinutes -lt 0 -or $ageMinutes -gt 30) { return $false }

    return $true
}

function Invoke-BundleSuccessPause {
    if ($NoSuccessPause) { return }
    if ($env:CI -or $env:HERMESDESK_NO_BUNDLE_SUCCESS_PAUSE) { return }
    if (-not [Environment]::UserInteractive) { return }

    Write-Host "[bundle] Success marker stays visible for 5 seconds before returning to the shell..." -ForegroundColor DarkGray
    Start-Sleep -Seconds 5
}

if (-not $Clean -and -not $Force -and (Test-RecentCompletedBundle -Runtime $Dist)) {
    Write-Host "[bundle] Skipping immediate duplicate bundle run; existing runtime was just completed." -ForegroundColor Yellow
    Write-Host "[bundle] Pass -Force or -Clean to rebuild anyway." -ForegroundColor Yellow
    exit 0
}

if ($Clean) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $BuildDir, $Dist
}

New-Item -ItemType Directory -Force -Path $BuildDir, $Download, $Dist | Out-Null

if (-not (Test-Path (Join-Path $CoreDir "pyproject.toml"))) {
    Write-Error "hermes_core/ directory not found. The frozen upstream source is missing."
    exit 2
}

# ------------------------------------------------------------------ 1. CPython
$asset = "cpython-$PythonVersion+$PbsRelease-x86_64-pc-windows-msvc-install_only.tar.gz"
$pbsUrl = "https://github.com/astral-sh/python-build-standalone/releases/download/$PbsRelease/$asset"
$tarball = Join-Path $Download $asset

if (-not (Test-Path $tarball)) {
    Write-Host "Downloading $pbsUrl"
    Invoke-WebRequest -Uri $pbsUrl -OutFile $tarball -UseBasicParsing
}

$pyDir = Join-Path $Dist "python"
if (-not (Test-Path (Join-Path $pyDir "python.exe"))) {
    Write-Host "Extracting CPython"
    tar -xzf $tarball -C $Dist
    if (Test-Path (Join-Path $Dist "python\python.exe")) {
        # Already named "python\python.exe" by the tarball
    } else {
        Rename-Item (Join-Path $Dist "python") $pyDir -ErrorAction SilentlyContinue
    }
}

$Py = Join-Path $pyDir "python.exe"
if (-not (Test-Path $Py)) {
    Write-Error "python.exe not found in $pyDir after extraction"
    exit 3
}

Write-Host "Using Python: " (& $Py --version)

# Remove the .pth from any prior build before invoking pip.  Python processes
# the runtime .pth on every startup; after Clear-BundleSitePackages wipes the
# external site-packages, the "import pywin32_bootstrap" line in the .pth fails
# with a noisy-but-non-fatal ModuleNotFoundError on every pip call.  The file
# is rewritten unconditionally later in this script, so deleting it here is safe.
Remove-Item -Force -ErrorAction SilentlyContinue `
    (Join-Path $pyDir "Lib\site-packages\kabuqina.pth"), `
    (Join-Path $pyDir "Lib\site-packages\hermesdesk.pth")

# ------------------------------------------------------------------ 2. pip
& $Py -m pip install --upgrade pip wheel | Out-Null

# ------------------------------------------------------------------ 3. Prune the owned core into the bundle
$bundledCore = Join-Path $Dist "kabuqina"
$legacyBundledCore = Join-Path $Dist "hermes"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $legacyBundledCore
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $bundledCore
New-Item -ItemType Directory -Force -Path $bundledCore | Out-Null

# Files / directories we copy.
$keep = @(
    "agent",
    "providers",                        # provider package (chat_completions, *_auth, transports) — agent/* are thin aliases into it; required for the inference path
    "tools",
    "gateway",                          # session_context, approval.py — required for terminal + desk
    "kabuqina_cli",
    "hermes_cli",                       # one-release import compatibility shim
    "learning",
    "skills",
    "plugins",
    "cron",
    "pyproject.toml",
    "run_agent.py",
    "model_tools.py",
    "toolsets.py",
    "toolset_distributions.py",
    "trajectory_compressor.py",          # imported by agent code; harmless if unused
    "kabuqina_constants.py",
    "kabuqina_state.py",
    "kabuqina_time.py",
    "kabuqina_logging.py",
    "hermes_constants.py",              # one-release module shims
    "hermes_state.py",
    "hermes_time.py",
    "hermes_logging.py",
    "utils.py",
    "MANIFEST.in",
    "LICENSE"
)

foreach ($name in $keep) {
    $src = Join-Path $CoreDir $name
    if (Test-Path $src) {
        Copy-Item -Recurse -Force $src (Join-Path $bundledCore $name)
    } else {
        Write-Warning "keep-list item missing in upstream: $name"
    }
}

# Drop unwanted subtrees that snuck in through broad package copies.
$drop = @(
    # v0.3.0 global-cut gateway adapters. Keep gateway/base helpers and the
    # retained mainland adapters (weixin, qqbot, feishu, wecom).
    "gateway\platforms\api_server.py",
    "gateway\platforms\bluebubbles.py",
    "gateway\platforms\homeassistant.py",
    "gateway\platforms\matrix.py",
    "gateway\platforms\mattermost.py",
    "gateway\platforms\signal.py",
    "gateway\platforms\signal_rate_limit.py",
    "gateway\platforms\slack.py",
    "gateway\platforms\sms.py",
    "gateway\platforms\webhook.py",
    "gateway\platforms\yuanbao.py",
    "gateway\platforms\yuanbao_media.py",
    "gateway\platforms\yuanbao_proto.py",
    "gateway\platforms\yuanbao_sticker.py",
    # Keep tools/environments/file_sync.py — ssh/modal/daytona import it; dropping it breaks agent init.
    "tools\rl_training_tool.py",
    "tools\feishu_doc_tool.py",
    "tools\feishu_drive_tool.py",
    "tools\homeassistant_tool.py",
    "tools\browser_camofox.py",
    "tools\browser_camofox_state.py",
    "tools\mixture_of_agents_tool.py",
    # v0.3.0 mainland_cn cut (Phase E). Yuanbao is a global cut.
    # The tool registry discovers tools/*.py by glob and skips missing ones, so
    # the gateway adapters (cut/non-eligible in mainland) degrade gracefully.
    "tools\yuanbao_tools.py",
    # v0.3.0 student runtime plugin/skill cuts.
    "plugins\disk-cleanup",
    "plugins\platforms",
    "plugins\spotify",
    "skills\creative\popular-web-designs\templates\spotify.md",
    "skills\dogfood",
    "skills\media\spotify"
)
foreach ($d in $drop) {
    $f = Join-Path $bundledCore $d
    if (Test-Path $f) { Remove-Item -Force -Recurse -LiteralPath $f }
}

# Prevent implicit namespace package causing subthread import failures
# (gateway/run.py spawns cron-ticker thread — from cron.scheduler import tick)
$coreInit = Join-Path $bundledCore "__init__.py"
if (-not (Test-Path $coreInit)) {
    "" | Set-Content -Path $coreInit -Encoding ASCII
}

# ------------------------------------------------------------------ 5. Install deps into a target dir (no venv)
$siteDir = Join-Path $Dist "site-packages"
function Clear-BundleSitePackages {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $lastErr = $null
    for ($i = 0; $i -lt 6; $i++) {
        try {
            Remove-Item -Recurse -Force -LiteralPath $Path -ErrorAction Stop
            return
        } catch {
            $lastErr = $_
            Start-Sleep -Seconds 2
        }
    }
    $stale = "$Path.stale_" + [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    try {
        Move-Item -LiteralPath $Path -Destination $stale -Force -ErrorAction Stop
        Write-Host "Note: could not delete site-packages in place (files locked). Renamed to:" -ForegroundColor Yellow
        Write-Host "  $stale" -ForegroundColor Yellow
        Write-Host "Quit HermesDesk / kill any python.exe using this runtime, then delete that folder manually." -ForegroundColor Yellow
        return
    } catch {
        $hint = "Usually a .pyd is still loaded: close HermesDesk, end any python.exe under:`n  $Dist`nthen rerun: .\python\build_bundle.ps1"
        throw ("Cannot remove or rename site-packages: " + $lastErr.Exception.Message + "`n`n" + $hint)
    }
}
Clear-BundleSitePackages -Path $siteDir
New-Item -ItemType Directory -Force -Path $siteDir | Out-Null

function Remove-BundleGeneratedJunk {
    param([string]$RootPath)

    if (-not (Test-Path -LiteralPath $RootPath)) { return }

    Write-Host "Pruning generated cache/stale files from runtime..." -ForegroundColor DarkGray

    $staleDirs = Get-ChildItem -LiteralPath $RootPath -Force -Directory -Filter "*.stale_*" -ErrorAction SilentlyContinue
    foreach ($dir in $staleDirs) {
        Remove-Item -Recurse -Force -LiteralPath $dir.FullName -ErrorAction Stop
    }

    $pycacheDirs = Get-ChildItem -LiteralPath $RootPath -Force -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending
    foreach ($dir in $pycacheDirs) {
        Remove-Item -Recurse -Force -LiteralPath $dir.FullName -ErrorAction Stop
    }

    $generatedFiles = Get-ChildItem -LiteralPath $RootPath -Force -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Extension -iin @(".pyc", ".pyo", ".pdb") -or
            $_.Name -like "*.pyc.*"
        }
    foreach ($file in $generatedFiles) {
        Remove-Item -Force -LiteralPath $file.FullName -ErrorAction Stop
    }
}

function Remove-VisualMasterGeneratedOutputs {
    param([string]$VisualMastersPath)

    if (-not (Test-Path -LiteralPath $VisualMastersPath)) { return }

    $rootFull = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $VisualMastersPath).Path).TrimEnd('\', '/')
    $rootPrefix = $rootFull + [IO.Path]::DirectorySeparatorChar

    Get-ChildItem -LiteralPath $rootFull -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $outputs = Join-Path $_.FullName "outputs"
        if (-not (Test-Path -LiteralPath $outputs -PathType Container)) { return }

        $targetFull = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $outputs).Path)
        if (-not $targetFull.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to delete visual-master outputs outside runtime root: $targetFull"
        }

        Remove-Item -Recurse -Force -LiteralPath $targetFull -ErrorAction Stop
    }
}

# ``--upgrade`` avoids "Target directory … already exists" when anything survived under
# ``site-packages`` or pip merges wheels that touch the same top-level names.
Write-Host "[bundle] 5/8 Installing Python dependencies..." -ForegroundColor Cyan
& $Py -m pip install `
    --upgrade `
    --target $siteDir `
    --no-warn-script-location `
    --platform win_amd64 `
    --python-version 3.11 `
    --only-binary=:all: `
    -r (Join-Path $PSScriptRoot "requirements-desktop.txt")

Write-Host "Verifying pip install (PyYAML / fastapi / uvicorn)..." -ForegroundColor DarkGray
$verifyScript = Join-Path $PSScriptRoot "tools\verify_bundle_site_packages.py"
& $Py $verifyScript $Dist
if ($LASTEXITCODE -ne 0) {
    Write-Error "pip verification failed (exit $LASTEXITCODE). Fix errors above, or delete python/dist/runtime and rebuild."
    exit 11
}

# ------------------------------------------------------------------ 5b. Docling models (load-packages by default)
#
# Docling base models are load-packages by default so the NSIS installer stays
# friendly for student users. ``docling-base`` is downloaded after onboarding
# and can be retried/deleted from Settings -> Load packages.
#
# Dev/offline override: pass -BundleDoclingModels. CodeFormula still requires
# DOCLING_BUNDLE_CODE_FORMULA=1. See python/tools/bundle_docling_models.py.
$doclingModelsDir = Join-Path $Dist "docling-models"
if ($SkipDoclingModels -or -not $BundleDoclingModels) {
    if (Test-Path $doclingModelsDir) {
        Remove-Item -Recurse -Force $doclingModelsDir
    }
    Write-Host "Skipping Docling model bundling by default. Docling base models are load-packages." -ForegroundColor DarkGray
} else {
Write-Host "Bundling Docling models for dev/offline build (layout + table + EasyOCR; CodeFormula excluded)..." -ForegroundColor DarkGray
$bundleModelsScript = Join-Path $PSScriptRoot "tools\bundle_docling_models.py"
$prevHfEndpoint = $env:HF_ENDPOINT
if (-not $env:HF_ENDPOINT) {
    $env:HF_ENDPOINT = "https://hf-mirror.com"
}
$env:PYTHONPATH = "$siteDir"
& $Py $bundleModelsScript $Dist
$modelExit = $LASTEXITCODE
if ($prevHfEndpoint) {
    $env:HF_ENDPOINT = $prevHfEndpoint
} else {
    Remove-Item Env:HF_ENDPOINT -ErrorAction SilentlyContinue
}
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
if ($modelExit -ne 0) {
    Write-Error @"
Docling model bundling failed (exit $modelExit).
Layout/table weights use HuggingFace (default mirror: hf-mirror.com via HF_ENDPOINT).
EasyOCR weights download from GitHub Releases — if that step failed, retry with:
  `$env:GITHUB_MIRROR='https://ghfast.top'
  .\python\build_bundle.ps1
Or skip bundling OCR (scanned PDF OCR may fail offline):
  `$env:DOCLING_BUNDLE_EASYOCR='0'
Or skip model bundling entirely when already present:
  .\python\build_bundle.ps1 -SkipDoclingModels
"@
    exit 14
}
}

# ------------------------------------------------------------------ 6. Copy overlays + entrypoint
Write-Host "[bundle] 6/8 Copying runtime sources..." -ForegroundColor Cyan
$overlaysDest = Join-Path $Dist "overlays"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $overlaysDest
Copy-Item -Recurse -Force (Join-Path $PSScriptRoot "overlays") $overlaysDest
$helpersDest = Join-Path $Dist "helpers"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $helpersDest
Copy-Item -Recurse -Force (Join-Path $PSScriptRoot "helpers") $helpersDest
Copy-Item -Force (Join-Path $PSScriptRoot "src\desktop_entrypoint.py") (Join-Path $Dist "desktop_entrypoint.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\desktop_config.py") (Join-Path $Dist "desktop_config.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\desktop_contract.py") (Join-Path $Dist "desktop_contract.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\desk_voice_paths.py") (Join-Path $Dist "desk_voice_paths.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\path_policy.py") (Join-Path $Dist "path_policy.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\secret_store.py") (Join-Path $Dist "secret_store.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\approval_backend.py") (Join-Path $Dist "approval_backend.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\docling_base_models.py") (Join-Path $Dist "docling_base_models.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\docling_math_models.py") (Join-Path $Dist "docling_math_models.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\easyocr_models.py") (Join-Path $Dist "easyocr_models.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\load_packages.py") (Join-Path $Dist "load_packages.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\messaging_policy.py") (Join-Path $Dist "messaging_policy.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\kabuqina_env.py") (Join-Path $Dist "kabuqina_env.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\learning_owner.py") (Join-Path $Dist "learning_owner.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\study_review_reminder.py") (Join-Path $Dist "study_review_reminder.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\cron_scheduler_runner.py") (Join-Path $Dist "cron_scheduler_runner.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\gateway_env_loader.py") (Join-Path $Dist "gateway_env_loader.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\desktop_timezone.py") (Join-Path $Dist "desktop_timezone.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\windows_registry_tz.py") (Join-Path $Dist "windows_registry_tz.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\desktop_delivery.py") (Join-Path $Dist "desktop_delivery.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\network_policy.py") (Join-Path $Dist "network_policy.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\tool_policy.py") (Join-Path $Dist "tool_policy.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\capability_policy.py") (Join-Path $Dist "capability_policy.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\product_profile_policy.py") (Join-Path $Dist "product_profile_policy.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\capability_registry.py") (Join-Path $Dist "capability_registry.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\capability_status.py") (Join-Path $Dist "capability_status.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\capability_prompt.py") (Join-Path $Dist "capability_prompt.py")
$deskServerDest = Join-Path $Dist "desk_server"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $deskServerDest
Copy-Item -Recurse -Force (Join-Path $PSScriptRoot "src\desk_server") $deskServerDest
foreach ($copiedTree in @($overlaysDest, $helpersDest, $deskServerDest)) {
    if (Test-Path $copiedTree) {
        Get-ChildItem -Path $copiedTree -Directory -Filter "__pycache__" -Recurse -ErrorAction SilentlyContinue |
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }
}
Copy-Item -Force (Join-Path $PSScriptRoot "src\gateway_policy.py") (Join-Path $Dist "gateway_policy.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\weixin_qr_worker.py") (Join-Path $Dist "weixin_qr_worker.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\qqbot_qr_worker.py") (Join-Path $Dist "qqbot_qr_worker.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\env_validate.py") (Join-Path $Dist "env_validate.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\feishu_qr_worker.py") (Join-Path $Dist "feishu_qr_worker.py")
Copy-Item -Force (Join-Path $PSScriptRoot "src\stt_wrapper.py") (Join-Path $Dist "stt_wrapper.py")

# PPT visual masters are loaded at runtime by hermes/tools/document_tools.py.
# Keep this path at runtime/assets/ppt/visual-masters so source and bundled layouts match.
$visualMastersSrc = Join-Path (Join-Path (Join-Path $Root "assets") "ppt") "visual-masters"
$visualMastersDest = Join-Path (Join-Path (Join-Path $Dist "assets") "ppt") "visual-masters"
if (-not (Test-Path $visualMastersSrc)) {
    throw "PPT visual masters missing at $visualMastersSrc"
}
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $visualMastersDest
New-Item -ItemType Directory -Force -Path (Split-Path $visualMastersDest -Parent) | Out-Null
Copy-Item -Recurse -Force $visualMastersSrc $visualMastersDest

# Prune stray generation outputs (each holds a node_modules tree) that bloat the
# bundle and exceed Windows MAX_PATH for the NSIS bundler — makensis cannot open
# >260-char paths and aborts. Visual masters are layout templates only; the
# per-master `outputs/` folders are generation junk that must not ship.
Remove-VisualMasterGeneratedOutputs -VisualMastersPath $visualMastersDest

# A pth file so the bundled Kabuqina core + site-packages are on sys.path
$pthBody = @(
    "..\..\..",
    "..\..\..\kabuqina",
    "..\..\..\site-packages",
    "..\..\..\site-packages\win32",
    "..\..\..\site-packages\win32\lib",
    "..\..\..\site-packages\pythonwin",
    "import pywin32_bootstrap"
) -join "`n"
Set-Content -Path (Join-Path $pyDir "Lib\site-packages\kabuqina.pth") -Value $pthBody -Encoding ASCII

# ------------------------------------------------------------------ 6b. Bundle whisper.cpp + ffmpeg for offline STT
#
# Ships the binaries needed for the local-command STT path so HermesDesk can
# transcribe audio without an API key. The model itself (~57 MB) is NOT
# bundled — it is lazy-downloaded on first use (see desk_stt_model_*
# endpoints in desk_server). Default:
# ``HERMESDESK_WORKSPACE\.hermesdesk\stt-models\``; when workspace is unset,
# ``HERMESDESK_DATA_DIR\stt-models`` or ``%LOCALAPPDATA%\HermesDesk\stt-models``.
#
# Cached in python/_download/ alongside the CPython tarball. SHA-256 verified
# against pinned constants. Net add to bundle: ~37 MB.
#
# To bump versions: update the URL + SHA below, run with -Clean once to
# refresh the download cache.
#
# Note: whisper.cpp moved to ``ggml-org/whisper.cpp``; v1.7.4 and some older
# tags ship **no** prebuilt zips (empty release assets) — the 404 you saw was
# from the old ggerganov URL + missing artifact. We pin a tag that CI
# actually publishes (``whisper-bin-x64.zip`` on the release page).
$WhisperVersion   = "v1.8.4"
$WhisperAsset     = "whisper-bin-x64.zip"
$WhisperUrl       = "https://github.com/ggml-org/whisper.cpp/releases/download/$WhisperVersion/$WhisperAsset"
# GitHub release asset digest for whisper-bin-x64.zip (v1.8.4)
$WhisperSha256    = "74f973345cb52ef5ba3ec9e7e7af8e48cc8c71722d1528603b80588a11f82e3e"

$FfmpegAsset      = "ffmpeg-release-essentials.zip"
$FfmpegUrl        = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
$FfmpegSha256     = ""

$SttBinDir = Join-Path $Dist "stt-bin"
New-Item -ItemType Directory -Force -Path $SttBinDir | Out-Null

function Test-Sha256 {
    param([string]$Path, [string]$Expected)
    if ([string]::IsNullOrWhiteSpace($Expected)) {
        Write-Warning "  (skip) SHA-256 not pinned for $(Split-Path $Path -Leaf); using download as-is"
        return
    }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
    if ($actual -ne $Expected.ToLowerInvariant()) {
        throw "SHA-256 mismatch for $Path`n  expected: $Expected`n  actual:   $actual"
    }
}

# whisper-cli.exe (+ its runtime DLLs if any). Static-linked builds are ~10 MB.
$whisperZip = Join-Path $Download $WhisperAsset
if (-not (Test-Path $whisperZip)) {
    Write-Host "Downloading $WhisperUrl"
    Invoke-WebRequest -Uri $WhisperUrl -OutFile $whisperZip -UseBasicParsing
}
Test-Sha256 -Path $whisperZip -Expected $WhisperSha256

$whisperExtract = Join-Path $BuildDir "whisper-bin"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $whisperExtract
Expand-Archive -LiteralPath $whisperZip -DestinationPath $whisperExtract -Force

# Pick whisper-cli.exe (newer releases) or main.exe (older). Drag along any
# sibling DLLs (e.g. ggml-cpu.dll / ggml.dll / SDL2.dll) so the binary runs
# without external runtime packages.
# NOTE: Use Where-Object instead of -Include with -LiteralPath -Recurse;
#       -Include is unreliable with -LiteralPath on some PowerShell versions.
$cliCandidates = Get-ChildItem -Recurse -LiteralPath $whisperExtract -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -in 'whisper-cli.exe','main.exe' }
if (-not $cliCandidates) {
    throw "No whisper-cli.exe / main.exe found inside $WhisperAsset (extracted to $whisperExtract). Inspect the archive layout."
}
# Prefer 'whisper-cli.exe' over 'main.exe'; if multiple matches, pick the one
# in a 'bin' subdirectory (release layout: whisper-bin-x64/bin/whisper-cli.exe).
$whisperExe = $cliCandidates | Where-Object { $_.Name -eq 'whisper-cli.exe' } | Select-Object -First 1
if (-not $whisperExe) { $whisperExe = $cliCandidates | Select-Object -First 1 }
$whisperSrcDir = Split-Path $whisperExe.FullName -Parent

Copy-Item -Force $whisperExe.FullName (Join-Path $SttBinDir "whisper-cli.exe")
Get-ChildItem -LiteralPath $whisperSrcDir -File | Where-Object {
    $_.Extension -ieq ".dll" -or $_.Name -ieq "whisper.exe"
} | ForEach-Object {
    Copy-Item -Force $_.FullName (Join-Path $SttBinDir $_.Name)
}

# ffmpeg.exe (we don't need ffprobe / ffplay).
$ffmpegZip = Join-Path $Download $FfmpegAsset
if (-not (Test-Path $ffmpegZip)) {
    Write-Host "Downloading $FfmpegUrl"
    Invoke-WebRequest -Uri $FfmpegUrl -OutFile $ffmpegZip -UseBasicParsing
}
Test-Sha256 -Path $ffmpegZip -Expected $FfmpegSha256

$ffmpegExtract = Join-Path $BuildDir "ffmpeg-bin"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $ffmpegExtract
Expand-Archive -LiteralPath $ffmpegZip -DestinationPath $ffmpegExtract -Force

$ffmpegBins = Get-ChildItem -Recurse -LiteralPath $ffmpegExtract -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq 'ffmpeg.exe' }
if (-not $ffmpegBins) {
    throw "No ffmpeg.exe found inside $FfmpegAsset (extracted to $ffmpegExtract)."
}
# If multiple ffmpeg.exe exist (unlikely), prefer the one in a 'bin' subdirectory.
$ffmpegExe = $ffmpegBins | Where-Object { $_.DirectoryName -like '*\\bin' } | Select-Object -First 1
if (-not $ffmpegExe) { $ffmpegExe = $ffmpegBins | Select-Object -First 1 }
Copy-Item -Force $ffmpegExe.FullName (Join-Path $SttBinDir "ffmpeg.exe")

Write-Host "STT binaries staged at $SttBinDir" -ForegroundColor DarkGray

Remove-BundleGeneratedJunk -RootPath $Dist

# ------------------------------------------------------------------ 7. Bundle metadata
$info = @{
    pythonVersion  = $PythonVersion
    pbsRelease     = $PbsRelease
    builtAt        = (Get-Date).ToString("o")
    frozenCommit   = "90b304b7c (v2026.4.23 — frozen upstream snapshot)"
    bundleSizeMb   = [math]::Round(((Get-ChildItem -Recurse $Dist | Measure-Object Length -Sum).Sum / 1MB), 1)
}
$info | ConvertTo-Json | Set-Content -Path (Join-Path $Dist "BUNDLE_INFO.json") -Encoding UTF8

Write-Host ""
Write-Host "Bundle ready at $Dist  ($($info.bundleSizeMb) MB)" -ForegroundColor Green
if (-not $Verify) {
    Invoke-BundleSuccessPause
}

# ------------------------------------------------------------------ 8. Verify
if ($Verify) {
    Write-Host "`n--- Smoke test ---" -ForegroundColor Cyan
    $env:KABUQINA_BUNDLE_DIR = $Dist
    $env:KABUQINA_DATA_DIR   = (Join-Path $env:TEMP "kabuqina-smoke")
    $env:KABUQINA_WORKSPACE  = (Join-Path $env:TEMP "kabuqina-smoke\workspace")
    $env:KABUQINA_HOME       = (Join-Path $env:TEMP "kabuqina-smoke\kabuqina-home")
    $env:KABUQINA_OVERLAY_LENIENT = "0"
    $env:PYTHONDONTWRITEBYTECODE = "1"
    New-Item -ItemType Directory -Force -Path $env:KABUQINA_WORKSPACE, $env:KABUQINA_HOME | Out-Null
    $runtimePrunedScript = Join-Path $PSScriptRoot "tools\verify_runtime_pruned.py"
    & $Py $runtimePrunedScript $Dist
    if ($LASTEXITCODE -ne 0) {
        Write-Error "runtime pruning verification FAILED"
        exit $LASTEXITCODE
    }
    $runtimeImportScript = Join-Path $PSScriptRoot "tools\verify_runtime_imports.py"
    & $Py $runtimeImportScript $Dist
    if ($LASTEXITCODE -ne 0) {
        Write-Error "smoke test FAILED"
        exit $LASTEXITCODE
    }
    $profilePlatformImportScript = Join-Path $PSScriptRoot "tools\verify_profile_platform_imports.py"
    & $Py $profilePlatformImportScript $Dist
    if ($LASTEXITCODE -ne 0) {
        Write-Error "profile platform import smoke test FAILED"
        exit $LASTEXITCODE
    }
    $legacyRuntimeImportScript = Join-Path $PSScriptRoot "tools\verify_legacy_runtime_imports.py"
    & $Py $legacyRuntimeImportScript $Dist
    if ($LASTEXITCODE -ne 0) {
        Write-Error "legacy import identity smoke test FAILED"
        exit $LASTEXITCODE
    }
    Write-Host "smoke test passed" -ForegroundColor Green

    # STT binaries must be runnable; they're invoked by stt_wrapper.py
    # at first mic click, so any missing runtime DLLs would surface there
    # at the worst possible moment.
    $whisperCli = Join-Path $SttBinDir "whisper-cli.exe"
    $ffmpegCli  = Join-Path $SttBinDir "ffmpeg.exe"
    Write-Host "Verifying STT binaries..." -ForegroundColor DarkGray

    # whisper/ffmpeg print version/help on stderr; many builds exit non-zero on `--help`.
    # With `$ErrorActionPreference='Stop'` and pwsh native error bridging, stderr / non-zero
    # exits become terminating errors unless we temporarily relax that here.
    $prevEAP = $ErrorActionPreference
    [bool]$hadNativePrefer = $false
    $prevNativePrefer = $null
    try {
        $ErrorActionPreference = "Continue"
        if ($null -ne (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue)) {
            $hadNativePrefer = $true
            $prevNativePrefer = $PSNativeCommandUseErrorActionPreference
            $PSNativeCommandUseErrorActionPreference = $false
        }

        & $whisperCli "--help" *> $null
        $wExit = $LASTEXITCODE

        # Treat 0/1 as typical "usage/help" exits; negatives are often Windows NTSTATUS
        # wrappers for missing MSVC runtime DLLs etc.
        if ($wExit -ne 0 -and $wExit -ne 1) {
            Write-Error "whisper-cli.exe failed to start (exit $wExit). DLLs missing?"
            exit 12
        }

        & $ffmpegCli "-version" *> $null
        if ($LASTEXITCODE -ne 0) {
            Write-Error "ffmpeg.exe failed to start (exit $LASTEXITCODE)."
            exit 13
        }
    }
    finally {
        $ErrorActionPreference = $prevEAP
        if ($hadNativePrefer -and ($null -ne $prevNativePrefer)) {
            $PSNativeCommandUseErrorActionPreference = $prevNativePrefer
        }
    }
    Write-Host "STT binaries OK" -ForegroundColor Green
    Invoke-BundleSuccessPause
}
