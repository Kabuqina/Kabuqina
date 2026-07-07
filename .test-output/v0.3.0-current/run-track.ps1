param(
    [string]$Track,
    [string]$RepoRoot
)
$ErrorActionPreference = "Continue"
$OutRoot = Join-Path $RepoRoot ".test-output\v0.3.0-current"
New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null
$Summary = Join-Path $OutRoot ("summary-{0}.tsv" -f $Track)
"id`tcwd`tcommand`texit_code`tduration_seconds`tlog" | Set-Content -Encoding UTF8 $Summary
function Invoke-Gate {
    param(
        [string]$Id,
        [string]$Cwd,
        [string]$Command,
        [scriptblock]$Script
    )
    $log = Join-Path $OutRoot ("{0}-{1}.log" -f $Track, $Id)
    $tmp = "$log.tmp"
    $start = Get-Date
    "START $Id $start" | Set-Content -Encoding UTF8 $log
    Push-Location $Cwd
    try {
        & $Script *> $tmp
        $code = $LASTEXITCODE
        if ($null -eq $code) { $code = 0 }
    } catch {
        $_ | Out-File -FilePath $tmp -Append -Encoding UTF8
        if ($LASTEXITCODE) { $code = $LASTEXITCODE } else { $code = 999 }
    } finally {
        Pop-Location
    }
    if (Test-Path $tmp) {
        Get-Content $tmp | Add-Content -Encoding UTF8 $log
        Remove-Item $tmp -ErrorAction SilentlyContinue
    }
    $end = Get-Date
    $duration = [int](New-TimeSpan -Start $start -End $end).TotalSeconds
    "END $Id $end exit=$code duration=${duration}s" | Add-Content -Encoding UTF8 $log
    $safeCmd = $Command -replace "`t", " "
    "$Id`t$Cwd`t$safeCmd`t$code`t$duration`t$log" | Add-Content -Encoding UTF8 $Summary
}
function Run-Cmd([scriptblock]$Cmd) {
    & $Cmd
    if ($LASTEXITCODE -ne 0) { throw "command failed with exit $LASTEXITCODE" }
}
if ($Track -eq "A") {
    $core = Join-Path $RepoRoot "hermes_core"
    Invoke-Gate "2.1-learning" $core 'python -m pytest tests/learning -o "addopts=" -p no:cacheprovider -q' { python -m pytest tests/learning -o "addopts=" -p no:cacheprovider -q --basetemp "$env:TEMP\kabuqina-current-2-1-learning" }
    Invoke-Gate "2.2-agent" $core 'python -m pytest tests/agent -o "addopts=" -p no:cacheprovider -q' { python -m pytest tests/agent -o "addopts=" -p no:cacheprovider -q --basetemp "$env:TEMP\kabuqina-current-2-2-agent" }
    Invoke-Gate "2.3-run-agent-graph" $core '$env:HERMES_AGENT_ENGINE="graph"; python -m pytest tests/run_agent -o "addopts=" -p no:cacheprovider -q' { $env:HERMES_AGENT_ENGINE="graph"; python -m pytest tests/run_agent -o "addopts=" -p no:cacheprovider -q --basetemp "$env:TEMP\kabuqina-current-2-3-graph"; Remove-Item Env:HERMES_AGENT_ENGINE -ErrorAction SilentlyContinue }
    Invoke-Gate "2.3-run-agent-loop" $core '$env:HERMES_AGENT_ENGINE="loop"; python -m pytest tests/run_agent -o "addopts=" -p no:cacheprovider -q' { $env:HERMES_AGENT_ENGINE="loop"; python -m pytest tests/run_agent -o "addopts=" -p no:cacheprovider -q --basetemp "$env:TEMP\kabuqina-current-2-3-loop"; Remove-Item Env:HERMES_AGENT_ENGINE -ErrorAction SilentlyContinue }
    Invoke-Gate "2.4-graph-gates" $core 'python -m pytest listed graph gates -o "addopts=" -p no:cacheprovider -q' { python -m pytest tests/run_agent/test_graph_protocol_parity.py tests/run_agent/test_graph_tool_parity.py tests/run_agent/test_graph_error_parity.py tests/run_agent/test_graph_budget_parity.py tests/run_agent/test_graph_differential_sequences.py tests/run_agent/test_graph_equivalence_gaps.py tests/run_agent/test_graph_plain_text.py tests/run_agent/test_exit_contract.py tests/run_agent/test_exit_reachability.py tests/run_agent/test_exit_cleanup_interrupt.py tests/run_agent/test_golden_transcripts.py -o "addopts=" -p no:cacheprovider -q --basetemp "$env:TEMP\kabuqina-current-2-4-graph-gates" }
    Invoke-Gate "2.5-tools-gateway-kabuqina" $core 'python -m pytest tests/tools tests/gateway tests/kabuqina -o "addopts=" -p no:cacheprovider -q' { python -m pytest tests/tools tests/gateway tests/kabuqina -o "addopts=" -p no:cacheprovider -q --basetemp "$env:TEMP\kabuqina-current-2-5-tools-gateway" }
    Invoke-Gate "2.6-cron" $core 'python -m pytest tests/cron -o "addopts=" -p no:cacheprovider -q' { python -m pytest tests/cron -o "addopts=" -p no:cacheprovider -q --basetemp "$env:TEMP\kabuqina-current-2-6-cron" }
    Invoke-Gate "2.7-core-misc" $core 'python -m pytest tests ... ignores -o "addopts=" -p no:cacheprovider -q' { python -m pytest tests -o "addopts=" -p no:cacheprovider -q --ignore=tests/learning --ignore=tests/agent --ignore=tests/run_agent --ignore=tests/tools --ignore=tests/gateway --ignore=tests/kabuqina --ignore=tests/cron --ignore=tests/e2e --ignore=tests/integration --basetemp "$env:TEMP\kabuqina-current-2-7-core-misc" }
} elseif ($Track -eq "B") {
    $py = Join-Path $RepoRoot "python"
    Invoke-Gate "3.1-study-policy" $py 'python -m pytest listed STUDY/policy tests -o "addopts=" -p no:cacheprovider -q' { python -m pytest tests/test_study_routes.py tests/test_study_capture_routes.py tests/test_study_m2_capture_union.py tests/test_learning_owner_context.py tests/test_capability_registry_learning.py tests/test_desk_chat_learning_context.py tests/test_policy_contract.py tests/test_capability_registry.py -o "addopts=" -p no:cacheprovider -q --basetemp "$env:TEMP\kabuqina-current-3-1-study-policy" }
    Invoke-Gate "3.2-desk-delivery" $py 'python -m pytest listed desk/delivery tests -o "addopts=" -p no:cacheprovider -q' { python -m pytest tests/test_desk_server.py tests/test_desk_system_prompt.py tests/test_desk_interactions.py tests/test_desktop_delivery.py tests/test_goal_routes.py -o "addopts=" -p no:cacheprovider -q --basetemp "$env:TEMP\kabuqina-current-3-2-desk-delivery" }
    Invoke-Gate "3.3-bundle-contracts" $py 'python -m pytest listed bundle tests -o "addopts=" -p no:cacheprovider -q' { python -m pytest tests/test_langgraph_bundle_contract.py tests/test_build_bundle_console_contract.py tests/test_bundle_docling_models.py tests/test_bundle_visual_masters.py -o "addopts=" -p no:cacheprovider -q --basetemp "$env:TEMP\kabuqina-current-3-3-bundle" }
    Invoke-Gate "3.4-python-full" $py 'python -m pytest tests -o "addopts=" -p no:cacheprovider -q' { python -m pytest tests -o "addopts=" -p no:cacheprovider -q --basetemp "$env:TEMP\kabuqina-current-3-4-python-full" }
} elseif ($Track -eq "C") {
    $web = Join-Path $RepoRoot "web"
    Invoke-Gate "4.1-web-node-scripts" $web 'all npm run test:* scripts listed in plan' { Run-Cmd { npm run test:chat-ux }; Run-Cmd { npm run test:chat-display }; Run-Cmd { npm run test:study-store }; Run-Cmd { npm run test:capture-index }; Run-Cmd { npm run test:flashcard-store }; Run-Cmd { npm run test:knowledge-points }; Run-Cmd { npm run test:flashcard-learning-store }; Run-Cmd { npm run test:quiz-store }; Run-Cmd { npm run test:quiz-learning-store }; Run-Cmd { npm run test:ui-prefs }; Run-Cmd { npm run test:gateway-ux }; Run-Cmd { npm run test:capabilities-page }; Run-Cmd { npm run test:settings-load-packages }; Run-Cmd { npm run test:settings-update }; Run-Cmd { npm run test:onboarding-providers }; Run-Cmd { npm run test:companion-ux }; Run-Cmd { npm run test:desktop-delivery }; npm run test:desktop-startup }
    Invoke-Gate "4.2-web-lint-build" $web 'npm run lint; npm run build' { Run-Cmd { npm run lint }; npm run build }
} elseif ($Track -eq "D") {
    $tauri = Join-Path $RepoRoot "tauri"
    Invoke-Gate "5.1-cargo-check-test" $tauri 'cargo check; cargo test' { Run-Cmd { cargo check }; cargo test }
}
