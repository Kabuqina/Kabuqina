# Sync edited Python/Kabuqina sources into python/dist/runtime for dev.
# Full dependency or Kabuqina tree changes still need: .\python\build_bundle.ps1

[CmdletBinding()]
param(
    [switch]$IncludeSkills
)

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
    "docling_base_models.py",
    "docling_math_models.py",
    "easyocr_models.py",
    "load_packages.py",
    "messaging_policy.py",
    "kabuqina_env.py",
    "learning_owner.py",
    "study_review_reminder.py",
    "cron_scheduler_runner.py",
    "gateway_env_loader.py",
    "desktop_timezone.py",
    "windows_registry_tz.py",
    "desktop_delivery.py",
    "network_policy.py",
    "tool_policy.py",
    "capability_policy.py",
    "product_profile_policy.py",
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
    $destParent = Split-Path $dest -Parent
    if (-not (Test-Path $destParent)) {
        New-Item -ItemType Directory -Force -Path $destParent | Out-Null
    }
    Copy-Item -Recurse -Force $src $dest
    Get-ChildItem -Path $dest -Directory -Filter "__pycache__" -Recurse -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
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

Sync-Directory (Join-Path $srcRoot "desk_server") (Join-Path $dist "desk_server")
Sync-Directory (Join-Path $root "python\overlays") (Join-Path $dist "overlays")
Sync-Directory (Join-Path $root "python\helpers") (Join-Path $dist "helpers")
Sync-Directory ([IO.Path]::Combine([string]$root, "assets", "ppt", "visual-masters")) ([IO.Path]::Combine([string]$dist, "assets", "ppt", "visual-masters"))

# Prune stray outputs/ generation junk from visual masters (see build_bundle.ps1)
# so dev syncs match release and NSIS bundling never hits MAX_PATH.
$vmDest = [IO.Path]::Combine([string]$dist, "assets", "ppt", "visual-masters")
Remove-VisualMasterGeneratedOutputs -VisualMastersPath $vmDest

$coreSource = Join-Path $root "hermes_core"
$coreDest = Join-Path $dist "kabuqina"
$legacyCoreDest = Join-Path $dist "hermes"
if (Test-Path -LiteralPath $legacyCoreDest) {
    Remove-Item -Recurse -Force -LiteralPath $legacyCoreDest
}
$coreKeep = @(
    "agent",
    "providers",
    "tools",
    "gateway",
    "kabuqina_cli",
    "hermes_cli",
    "learning",
    "plugins",
    "cron",
    "run_agent.py",
    "model_tools.py",
    "toolsets.py",
    "toolset_distributions.py",
    "trajectory_compressor.py",
    "kabuqina_constants.py",
    "kabuqina_state.py",
    "kabuqina_time.py",
    "kabuqina_logging.py",
    "hermes_constants.py",
    "hermes_state.py",
    "hermes_time.py",
    "hermes_logging.py",
    "utils.py"
)
if ($IncludeSkills) {
    $coreKeep += "skills"
} else {
    Write-Host "Skipping hermes_core/skills in fast sync (use -IncludeSkills after editing skills)." -ForegroundColor DarkGray
}

foreach ($name in $coreKeep) {
    $src = Join-Path $coreSource $name
    $dest = Join-Path $coreDest $name
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

$runtimeDrop = @(
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
    "tools\rl_training_tool.py",
    "tools\feishu_doc_tool.py",
    "tools\feishu_drive_tool.py",
    "tools\homeassistant_tool.py",
    "tools\browser_camofox.py",
    "tools\browser_camofox_state.py",
    "tools\mixture_of_agents_tool.py",
    "tools\discord_tool.py",
    "tools\yuanbao_tools.py",
    "plugins\disk-cleanup",
    "plugins\platforms",
    "plugins\spotify",
    "skills\creative\popular-web-designs\templates\spotify.md",
    "skills\dogfood",
    "skills\media\spotify"
)
foreach ($d in $runtimeDrop) {
    $target = Join-Path $coreDest $d
    if (Test-Path $target) {
        Remove-Item -Recurse -Force -LiteralPath $target
    }
}

$py = Join-Path $dist "python\python.exe"
$verifyRuntimePruned = Join-Path $root "python\tools\verify_runtime_pruned.py"
& $py $verifyRuntimePruned $dist
if ($LASTEXITCODE -ne 0) {
    Write-Error "Runtime pruning verification failed after source sync."
    exit $LASTEXITCODE
}
$verifyRuntimeImports = Join-Path $root "python\tools\verify_runtime_imports.py"
& $py $verifyRuntimeImports $dist
if ($LASTEXITCODE -ne 0) {
    Write-Error "Runtime import verification failed after source sync."
    exit $LASTEXITCODE
}
$verifyProfilePlatformImports = Join-Path $root "python\tools\verify_profile_platform_imports.py"
& $py $verifyProfilePlatformImports $dist
if ($LASTEXITCODE -ne 0) {
    Write-Error "Profile platform import verification failed after source sync."
    exit $LASTEXITCODE
}
$verifyLegacyRuntimeImports = Join-Path $root "python\tools\verify_legacy_runtime_imports.py"
& $py $verifyLegacyRuntimeImports $dist
if ($LASTEXITCODE -ne 0) {
    Write-Error "Legacy runtime identity verification failed after source sync."
    exit $LASTEXITCODE
}

Write-Host "Synced runtime sources -> python/dist/runtime" -ForegroundColor Green
