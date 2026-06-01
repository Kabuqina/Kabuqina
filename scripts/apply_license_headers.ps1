#Requires -Version 7
<#
.SYNOPSIS
  Bulk-add Apache-2.0 SPDX license headers to Kabuqina source files.
.DESCRIPTION
  Idempotent: skips files that already contain "SPDX-License-Identifier".
  Preserves Python shebang lines (places header after shebang + encoding).
  Targets:
    - tauri/src/**/*.rs
    - web/src/**/*.ts, web/src/**/*.tsx
    - python/src/**/*.py, python/overlays/**/*.py, python/tests/**/*.py,
      python/scripts/**/*.py, python/tools/**/*.py
  Does NOT touch hermes_core/ (remains MIT upstream).
.EXAMPLE
  .\scripts\apply_license_headers.ps1
  .\scripts\apply_license_headers.ps1 -WhatIf   # dry-run
#>
param(
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

$headerText = "Copyright 2026 Kabuqina Contributors"
$spdxTag    = "SPDX-License-Identifier: Apache-2.0"

# Return $true if file already has SPDX header
function Test-HasHeader([string]$Path) {
    $firstLines = Get-Content -Path $Path -TotalCount 5 -ErrorAction SilentlyContinue
    return ($firstLines -join "`n").Contains("SPDX-License-Identifier")
}

function Add-HeaderRust([string]$Path) {
    if (Test-HasHeader $Path) { return $false }
    $content = Get-Content -Raw -Path $Path
    $header = "// $headerText`n// $spdxTag`n`n"
    if ($WhatIf) {
        Write-Host "[WHATIF] Would update: $Path" -ForegroundColor Cyan
        return $true
    }
    Set-Content -Path $Path -Value ($header + $content) -NoNewline -Encoding utf8
    return $true
}

function Add-HeaderTs([string]$Path) {
    if (Test-HasHeader $Path) { return $false }
    $content = Get-Content -Raw -Path $Path
    $header = "// $headerText`n// $spdxTag`n`n"
    if ($WhatIf) {
        Write-Host "[WHATIF] Would update: $Path" -ForegroundColor Cyan
        return $true
    }
    Set-Content -Path $Path -Value ($header + $content) -NoNewline -Encoding utf8
    return $true
}

function Add-HeaderPython([string]$Path) {
    if (Test-HasHeader $Path) { return $false }
    $lines = Get-Content -Path $Path
    $shebang = $null
    $encoding = $null
    $idx = 0

    # Preserve shebang
    if ($lines[$idx] -match '^#!') {
        $shebang = $lines[$idx]
        $idx++
    }
    # Preserve encoding declaration (PEP 263)
    if ($lines[$idx] -match '^#\s*-\*-\s*coding:') {
        $encoding = $lines[$idx]
        $idx++
    }

    $rest = $lines[$idx..($lines.Count - 1)] -join "`n"
    if (-not $rest.EndsWith("`n")) { $rest += "`n" }

    $parts = @()
    if ($shebang)   { $parts += $shebang }
    if ($encoding)  { $parts += $encoding }
    $parts += "# $headerText"
    $parts += "# $spdxTag"
    $parts += ""
    $parts += $rest

    if ($WhatIf) {
        Write-Host "[WHATIF] Would update: $Path" -ForegroundColor Cyan
        return $true
    }
    Set-Content -Path $Path -Value ($parts -join "`n") -NoNewline -Encoding utf8
    return $true
}

$targets = @(
    @{ Path = "tauri/src";     Filter = "*.rs";  Handler = "Add-HeaderRust" }
    @{ Path = "web/src";       Filter = "*.ts";   Handler = "Add-HeaderTs" }
    @{ Path = "web/src";       Filter = "*.tsx";  Handler = "Add-HeaderTs" }
    @{ Path = "python/src";    Filter = "*.py";   Handler = "Add-HeaderPython" }
    @{ Path = "python/overlays"; Filter = "*.py";  Handler = "Add-HeaderPython" }
    @{ Path = "python/tests";  Filter = "*.py";   Handler = "Add-HeaderPython" }
    @{ Path = "python/scripts"; Filter = "*.py";  Handler = "Add-HeaderPython" }
    @{ Path = "python/tools";  Filter = "*.py";   Handler = "Add-HeaderPython" }
)

$updated = 0
$skipped = 0

foreach ($t in $targets) {
    $fullPath = Resolve-Path $t.Path -ErrorAction SilentlyContinue
    if (-not $fullPath) {
        Write-Warning "Directory not found: $($t.Path); skipping."
        continue
    }
    $files = Get-ChildItem -Path $fullPath -Filter $t.Filter -Recurse -File
    foreach ($f in $files) {
        $result = & $t.Handler $f.FullName
        if ($result) {
            $updated++
            if (-not $WhatIf) {
                Write-Host "Updated: $($f.FullName)" -ForegroundColor Green
            }
        } else {
            $skipped++
        }
    }
}

Write-Host "`nDone. Updated: $updated  Skipped (already has header): $skipped" -ForegroundColor White
if ($WhatIf) {
    Write-Host "This was a dry-run. Re-run without -WhatIf to apply." -ForegroundColor Yellow
}
