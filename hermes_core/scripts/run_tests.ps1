<#
.SYNOPSIS
Canonical Windows test runner for hermes-agent.

.DESCRIPTION
Mirrors scripts/run_tests.sh for native Windows virtual environments:
four xdist workers, UTC/locale/hash determinism, and removal of credential and
behavioural environment variables before pytest starts.

.EXAMPLE
./scripts/run_tests.ps1 tests/cron/
./scripts/run_tests.ps1 tests/agent/test_foo.py::test_bar -q
#>

[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$candidateRoots = @(
    (Join-Path $repoRoot '.venv'),
    (Join-Path $repoRoot 'venv'),
    (Join-Path $env:USERPROFILE '.hermes\hermes-agent\venv')
)

$venv = $null
$python = $null
foreach ($candidate in $candidateRoots) {
    $candidatePython = Join-Path $candidate 'Scripts\python.exe'
    if (Test-Path -LiteralPath $candidatePython -PathType Leaf) {
        $venv = $candidate
        $python = $candidatePython
        break
    }
}

if ($null -eq $python) {
    throw "No Windows virtual environment found in $repoRoot\.venv or $repoRoot\venv (expected Scripts\python.exe)."
}

# The Unix runner installs this on demand so shard-equivalent local runs have
# the same plugin available as CI. Keep the Windows runner behaviour aligned.
& $python -c 'import pytest_split' 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "→ installing pytest-split into $venv"
    & $python -m pip install --quiet 'pytest-split>=0.9,<1'
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to install pytest-split.'
    }
}

$credentialPattern = '(_API_KEY|_TOKEN|_SECRET|_PASSWORD|_CREDENTIALS|_ACCESS_KEY|_SECRET_ACCESS_KEY|_PRIVATE_KEY|_OAUTH_TOKEN|_WEBHOOK_SECRET|_ENCRYPT_KEY|_APP_SECRET|_CLIENT_SECRET|_CORP_SECRET|_AES_KEY)$|^(AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN|FAL_KEY|GH_TOKEN|GITHUB_TOKEN)$'
Get-ChildItem Env: | ForEach-Object {
    if ($_.Name -match $credentialPattern) {
        Remove-Item -LiteralPath "Env:$($_.Name)" -ErrorAction SilentlyContinue
    }
}

$behaviouralVars = @(
    'HERMES_YOLO_MODE', 'HERMES_INTERACTIVE', 'HERMES_QUIET',
    'HERMES_TOOL_PROGRESS', 'HERMES_TOOL_PROGRESS_MODE',
    'HERMES_MAX_ITERATIONS', 'HERMES_SESSION_PLATFORM',
    'HERMES_SESSION_CHAT_ID', 'HERMES_SESSION_CHAT_NAME',
    'HERMES_SESSION_THREAD_ID', 'HERMES_SESSION_SOURCE',
    'HERMES_SESSION_KEY', 'HERMES_GATEWAY_SESSION', 'HERMES_PLATFORM',
    'HERMES_INFERENCE_PROVIDER', 'HERMES_MANAGED', 'HERMES_DEV',
    'HERMES_CONTAINER', 'HERMES_EPHEMERAL_SYSTEM_PROMPT',
    'HERMES_TIMEZONE', 'HERMES_REDACT_SECRETS',
    'HERMES_BACKGROUND_NOTIFICATIONS', 'HERMES_EXEC_ASK',
    'HERMES_HOME_MODE'
)
foreach ($name in $behaviouralVars) {
    Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
}

$env:TZ = 'UTC'
$env:LANG = 'C.UTF-8'
$env:LC_ALL = 'C.UTF-8'
$env:PYTHONHASHSEED = '0'
$workers = if ([string]::IsNullOrWhiteSpace($env:HERMES_TEST_WORKERS)) {
    '4'
} else {
    $env:HERMES_TEST_WORKERS
}
$pytestBaseTemp = Join-Path ([System.IO.Path]::GetTempPath()) (
    'hermes-pytest-' + [Guid]::NewGuid().ToString('N')
)

Set-Location $repoRoot
Write-Host "▶ running pytest with $workers workers, hermetic env, in $repoRoot"
Write-Host '  (TZ=UTC LANG=C.UTF-8 PYTHONHASHSEED=0; all credential env vars unset)'

& $python -m pytest `
    -o 'addopts=' `
    -n $workers `
    --ignore=tests/integration `
    --ignore=tests/e2e `
    -m 'not integration' `
    --basetemp $pytestBaseTemp `
    @PytestArgs
exit $LASTEXITCODE
