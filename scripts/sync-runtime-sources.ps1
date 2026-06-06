# Sync edited Python/Hermes sources into python/dist/runtime for dev.
# Full dependency or Hermes tree changes still need: .\python\build_bundle.ps1

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$dist = Join-Path $root "python\dist\runtime"

if (-not (Test-Path (Join-Path $dist "python\python.exe"))) {
    Write-Error "Runtime bundle missing. Run .\python\build_bundle.ps1 first."
}

$srcRoot = Join-Path $root "python\src"
$pyFiles = @(
    "desktop_entrypoint.py",
    "desktop_config.py",
    "desktop_contract.py",
    "desk_voice_paths.py",
    "path_policy.py",
    "secret_store.py",
    "approval_backend.py",
    "docling_math_models.py",
    "load_packages.py",
    "messaging_policy.py",
    "cron_scheduler_runner.py",
    "gateway_env_loader.py",
    "desktop_timezone.py",
    "windows_registry_tz.py",
    "desktop_delivery.py",
    "network_policy.py",
    "tool_policy.py",
    "capability_policy.py",
    "capability_registry.py",
    "capability_status.py",
    "capability_prompt.py",
    "gateway_policy.py",
    "weixin_qr_worker.py",
    "qqbot_qr_worker.py",
    "env_validate.py",
    "feishu_qr_worker.py",
    "stt_wrapper.py"
)

foreach ($name in $pyFiles) {
    $src = Join-Path $srcRoot $name
    if (Test-Path $src) {
        Copy-Item -Force $src (Join-Path $dist $name)
    }
}

function Sync-Directory($src, $dest) {
    if (Test-Path $dest) {
        Remove-Item -Recurse -Force $dest
    }
    Copy-Item -Recurse -Force $src $dest
    Get-ChildItem -Path $dest -Directory -Filter "__pycache__" -Recurse -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

Sync-Directory (Join-Path $srcRoot "desk_server") (Join-Path $dist "desk_server")
Sync-Directory (Join-Path $root "python\overlays") (Join-Path $dist "overlays")
Sync-Directory (Join-Path $root "python\helpers") (Join-Path $dist "helpers")

$hermesCore = Join-Path $root "hermes_core"
$hermesDest = Join-Path $dist "hermes"
$hermesKeep = @(
    "agent",
    "tools",
    "gateway",
    "hermes_cli",
    "skills",
    "plugins",
    "cron",
    "run_agent.py",
    "model_tools.py",
    "toolsets.py",
    "toolset_distributions.py",
    "trajectory_compressor.py",
    "cli.py",
    "hermes_constants.py",
    "hermes_state.py",
    "hermes_time.py",
    "hermes_logging.py",
    "utils.py"
)

foreach ($name in $hermesKeep) {
    $src = Join-Path $hermesCore $name
    $dest = Join-Path $hermesDest $name
    if (-not (Test-Path $src)) {
        continue
    }
    if (Test-Path $src -PathType Container) {
        if (Test-Path $dest) {
            Remove-Item -Recurse -Force $dest
        }
        Copy-Item -Recurse -Force $src $dest
    } else {
        $destDir = Split-Path $dest -Parent
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Force -Path $destDir | Out-Null
        }
        Copy-Item -Force $src $dest
    }
}

Write-Host "Synced runtime sources -> python/dist/runtime" -ForegroundColor Green
