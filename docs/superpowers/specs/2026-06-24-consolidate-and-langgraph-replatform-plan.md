# Consolidate + LangGraph Re-platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** preserve the observable behavior of the owned Hermes agent core while
finishing the provider consolidation and replacing the synchronous ReAct control
loop with an explicitly modelled, rollback-safe LangGraph engine.

**Architecture:** Phase 0 and Phase 3 below are retained as completed history.
Phase 3.5 remains behind the legacy loop until dependency, packaging, and all
21 current exit-path contracts are pinned. The graph uses low-level
`StateGraph` only, keeps plain Hermes message dictionaries, passes
non-serializable collaborators through a runtime context, and does not enable a
LangGraph checkpointer during the equivalence migration.

**Tech stack:** Python 3.11 bundled runtime, pytest golden transcripts,
LangGraph 1.2.x low-level graph API, Tauri 2/Rust child supervisors, PowerShell
7 build scripts.

Date: 2026-06-24; revised 2026-06-27 after grounded implementation review and
Bounded Goal Runner synchronization.

---

## Status and decisions

**Phase 3.5 status: NO-GO as of 2026-06-27.** Do not begin graph implementation
until Tasks 1 and 2 below pass their gates and the go/no-go checklist is updated
in this document.

The revision makes these decisions explicit:

1. **Keep the LangGraph objective.** Use the low-level graph API, not LangChain
   agents, chains, model wrappers, message classes, or `add_messages`.
2. **Accept the real dependency closure.** The `langgraph` distribution requires
   `langchain-core`, `langgraph-checkpoint`, `langgraph-prebuilt`, and
   `langgraph-sdk`; `langchain-core` requires `langsmith`. These packages may be
   installed transitively, but Kabuqina production code must not import them
   directly outside the graph builder.
3. **No checkpointer in Phase 3.5.** Compile without `MemorySaver` or
   `InMemorySaver`. Hermes `session_db` remains the only persistent conversation
   store. Durable graph resume is a separate future decision, not an accidental
   side effect of this migration.
4. **Preserve before improving.** The current early returns do not all execute
   cleanup, `post_llm_call`, or `on_session_end`. That inconsistency is part of
   the characterization contract. Normalize it only in a later behavior-change
   commit with explicit tests and release notes.
5. **Never live-shadow side effects.** Tests may run loop and graph separately
   on scripted transports. Production must choose one engine before a turn.
   Never run both engines on the same real turn, and never automatically rerun a
   failed graph turn through the loop after a tool may have executed.
6. **Rename remains Phase 4.** The temporary rollout variable is
   `HERMES_AGENT_ENGINE`, not `KABUQINA_AGENT_ENGINE`.
7. **Develop the outer loop in gated parallel.** The Bounded Goal Runner's pure
   state, verifier, reporting, and controller foundations may land beside Tasks
   1–9. Its runtime adapter waits for Tasks 9–10, and its product exposure waits
   for the Task 11 soak. Phase 3.5 never absorbs outer-loop persistence or
   verifier semantics into LangGraph.

Dependency facts must be rechecked immediately before Task 1 because package
metadata can change. At this revision, the relevant official metadata is:

- <https://pypi.org/pypi/langgraph/1.2.6/json>
- <https://pypi.org/pypi/langchain-core/1.4.7/json>
- <https://docs.langchain.com/oss/python/langgraph/persistence>
- <https://docs.langchain.com/langsmith/trace-without-env-vars>

---

## Parallel contract with the Bounded Goal Runner plan

Companion plan:
`docs/superpowers/plans/2026-06-27-bounded-goal-runner.md`.

The plans deliberately cross at explicit gates rather than sharing an
implementation branch:

| Gate | Phase 3.5 state | Goal Runner state | Merge rule |
|---|---|---|---|
| **G0** | Tasks 1–9 in progress | Goal Tasks 1–6 may progress | Pure goal modules and read-only status only; no due-job runtime path. |
| **G1** | Tasks 9 and 10 pass | Goal Tasks 7–9 may progress | Goal adapter calls public `AIAgent.run_conversation`; it never imports graph internals or edits `run_agent.py`. |
| **G2** | Task 11 Step 4 completes the 14-day soak | Goal Task 10 may expose and run Pilot 1 | Run the pilot with explicit loop and graph before removing the loop. |
| **Removal** | Task 11 Step 5 | Goal Task 10 dual-engine evidence recorded, or the product plan is explicitly deferred | Only then remove the selector and legacy loop. |

### File ownership and serialization

| Owner | Files | Constraint |
|---|---|---|
| Phase 3.5 | `hermes_core/run_agent.py`, `hermes_core/agent/graph_engine/**`, `hermes_core/agent/engine_selector.py`, LangGraph dependency and supervisor tracing files | Goal Runner never edits or imports their private internals. |
| Goal Runner | `hermes_core/cron/goal_*.py`, `hermes_core/tools/goal_report_tool.py`, goal-specific cron tests, host status/control surfaces | May merge at G0 if no live cron path changes. |
| Serialized | `hermes_core/hermes_cli/config_defaults.py` | Phase Task 10 adds `agent.engine` first. Goal Task 8 rebases and then adds `cron.goal_loop`. |
| Serialized | `DECISIONS.md` and these plans | Append after rebasing; preserve both gate records. |

No Goal Runner commit may add a LangGraph checkpointer, call graph nodes, change
the 21 exit contracts, or run loop and graph on the same real turn. No Phase 3.5
commit may move goal state into `TurnState` or make the inner engine own cron
rescheduling.

### Development-loop cursor

Execution uses the Track A outer-loop contract from the companion design. The
resumable cursor lives at
`docs/superpowers/progress/phase-3.5-loop-state.json`; plan checkboxes, test
evidence, and commits remain authoritative. A cycle selects one eligible task,
uses one isolated worktree, runs its deterministic commands, records evidence,
and stops for human review. It never auto-merges, pushes, changes a golden, or
waives a failed gate.

---

## Completed baseline

### Phase 0 — golden-transcript harness: COMPLETE

The replay harness (`hermes_core/tests/run_agent/golden_harness.py`), runner
(`hermes_core/tests/run_agent/test_golden_transcripts.py`), and ten fixtures
under `hermes_core/tests/run_agent/golden/` are present. They cover plain text,
single and concurrent tools, Anthropic messages, interrupt, steer, unknown tool,
max iterations, provider fallback, and preflight compression.

Verified on 2026-06-27 with the repository's Windows no-xdist command:

```powershell
cd hermes_core
python -m pytest tests/run_agent/test_golden_transcripts.py `
  -o "addopts=" -p no:cacheprovider -q
```

Expected and observed: `11 passed`. This run used system Python 3.14; Task 1
adds the missing bundled-CPython-3.11 gate.

### Phase 3 — consolidate narrowed architecture: COMPLETE

- **3a complete:** removed the `agent.*` provider aliases and retargeted callers
  to `providers.*`.
- **3b resolved without merge:** `HERMES_OVERLAYS` and `PROVIDER_REGISTRY` serve
  different subsystems. The consistency invariant is pinned in
  `hermes_core/tests/hermes_cli/test_provider_registry_overlay_consistency.py`.
- **3c folded into Phase 3.5:** the two remaining protocols,
  `chat_completions` and `anthropic_messages`, are both live. Their dispatch is
  moved behind the graph transport port rather than trimmed first.

### Grounded loop facts

- `hermes_core/run_agent.py` currently has 12,897 lines.
- `AIAgent.run_conversation` spans lines 9374–12664 and has **21 return sites**,
  not 22. Twenty return literal dictionaries; the final site returns `result`.
- The public dictionaries use several key-presence shapes. Adding absent keys
  with `None` or `False` is an observable behavior change.
- Six plugin hooks are load-bearing: `on_session_start`, `pre_llm_call`,
  `pre_api_request`, `post_api_request`, `post_llm_call`, and `on_session_end`.
- Existing helpers mutate both `self` and the `messages` list. `TurnState` is
  authoritative for per-turn messages, counters, routes, and outcomes;
  `AIAgent` remains the owner of cross-turn runtime configuration such as the
  active provider. Every service mutation that affects both must return a
  mirrored state update, and parity tests must catch divergence.
- `python/build_bundle.ps1` installs from
  `python/requirements-desktop.txt`. Adding a dependency only to
  `hermes_core/pyproject.toml` does not put it in the desktop runtime.

---

## Scope and non-goals

In scope:

- dependency and bundled-runtime validation;
- exact loop/graph result, message, hook, stream, persistence, and cleanup
  parity;
- graph orchestration for both live API modes;
- a one-release loop escape hatch;
- release-build runtime smoke on both API modes.

Out of scope:

- Phase 4 identity rename (`kabuqina_core`, `KABUQINA_*`, `~/.hermes`);
- LangChain agents, model integrations, chains, or message objects;
- LangGraph checkpoint persistence, human-in-the-loop interrupts, Studio, or
  Agent Server;
- new gateway platform work;
- changing result shapes or fixing the current early-return hook inconsistency;
- reintroducing cut providers or removing names from `GLOBAL_STUDENT_CUT`.

---

## Target file map

### New production files

| File | Responsibility |
|---|---|
| `hermes_core/agent/graph_engine/__init__.py` | Export only `GraphEngine` and stable contracts. |
| `hermes_core/agent/graph_engine/contracts.py` | Serializable `TurnState`, exact legacy result type, routes, and exit policy. No LangGraph imports. |
| `hermes_core/agent/graph_engine/ports.py` | Protocols for transport, tools, hooks, persistence, pricing, compression, interrupts, and cleanup. No LangGraph imports. |
| `hermes_core/agent/graph_engine/nodes.py` | Pure node operations accepting `TurnState` plus the service port. No LangGraph imports. |
| `hermes_core/agent/graph_engine/builder.py` | The only production import site for `langgraph.*`; wraps pure nodes and compiles without a checkpointer. |
| `hermes_core/agent/graph_engine/engine.py` | Stable `GraphEngine.run_turn()` adapter that converts graph output back to the exact legacy dictionary. |
| `hermes_core/agent/engine_selector.py` | Resolve explicit constructor value → `HERMES_AGENT_ENGINE` → `agent.engine` config → `loop`. |

### Modified production and packaging files

| File | Change |
|---|---|
| `hermes_core/run_agent.py` | Keep legacy body as `_run_conversation_loop`; add graph service adapter and final dispatch. |
| `hermes_core/hermes_cli/config_defaults.py` | Add `agent.engine: loop` without a config-version bump. |
| `hermes_core/pyproject.toml` | Add the validated LangGraph pin. |
| `hermes_core/uv.lock` | Lock the complete dependency closure. |
| `python/requirements-desktop.txt` | Mirror the exact LangGraph pin for the bundled runtime. |
| `python/tools/verify_bundle_site_packages.py` | Verify low-level graph imports from bundled site-packages. |
| `tauri/src/python_supervisor.rs` | Force `LANGSMITH_TRACING=false` for the web child. |
| `tauri/src/gateway_supervisor.rs` | Force `LANGSMITH_TRACING=false` for every gateway child. |
| `DECISIONS.md` | Record dependency closure, no-checkpointer decision, engine precedence, and rollback constraints. |

### Tests

| File | Responsibility |
|---|---|
| `hermes_core/tests/run_agent/golden_harness.py` | Accept an engine parameter and capture hooks, cleanup, interrupt clearing, and exact result-key presence. |
| `hermes_core/tests/run_agent/test_golden_transcripts.py` | Parameterize selected fixtures over loop/graph without mutating process-global env. |
| `hermes_core/tests/run_agent/test_exit_contract.py` | Pin all 21 exit sites by named scenario and exit policy. |
| `hermes_core/tests/run_agent/test_hook_invocation_parity.py` | Compare hook presence, order, and payloads for every exit family. |
| `hermes_core/tests/agent/test_graph_import_isolation.py` | Forbid LangGraph/LangChain/LangSmith imports outside `builder.py`. |
| `hermes_core/tests/agent/test_engine_selector.py` | Pin selector validation and precedence. |
| `python/tests/test_langgraph_bundle_contract.py` | Pin mirrored requirement and tracing-off supervisor wiring. |

---

## Go / no-go checklist

Record the date and evidence beside each item. GO requires every item checked.

- [x] Phase 3 is complete or intentionally resolved.
- [x] Existing ten-fixture golden suite passes on the legacy loop.
- [x] STUDY integration is loop-decoupled and may land independently.
- [ ] Task 1 proves the complete dependency closure installs in bundled
  CPython 3.11 and records the actual size delta.
- [ ] Task 1 proves both desktop child types start with
  `LANGSMITH_TRACING=false`.
- [ ] Task 2 pins every current return site and its side-effect policy.
- [ ] The operator can run release-build chat + one tool on both API modes.
- [ ] A two-week window has no other scheduled `run_agent.py`, transport,
  provider fallback, or session-persistence landings.
- [ ] The GO decision is recorded in `DECISIONS.md` and in this section.

If a gate fails, leave the product on `loop`, document the failure, and stop.
Passing unit tests is not permission to waive a failed packaging or runtime gate.

---

## Task 0 — Initialize the bounded development loop

**Files:**

- Create when execution begins:
  `docs/superpowers/progress/phase-3.5-loop-state.json`
- Modify after every cycle: this plan and the progress cursor

- [ ] **Step 1: create the resumable cursor before Task 1 changes code**

```json
{
  "plan": "docs/superpowers/specs/2026-06-24-consolidate-and-langgraph-replatform-plan.md",
  "current_task": 1,
  "status": "ready",
  "attempt": 0,
  "worktree": null,
  "last_commit": null,
  "last_verification": [],
  "failed_approaches": [],
  "blocker": null,
  "next_action": "Run the dependency and bundled-runtime spike"
}
```

Allowed statuses are `ready`, `running`, `verifying`, `review_required`,
`blocked`, and `complete`. The file contains no prompts, secrets, model output,
or raw fixture contents.

- [ ] **Step 2: validate the cursor and record the starting commit**

```powershell
$cursor = Get-Content `
  docs/superpowers/progress/phase-3.5-loop-state.json -Raw |
  ConvertFrom-Json
if ($cursor.current_task -ne 1 -or $cursor.status -ne "ready") {
  throw "invalid Phase 3.5 loop cursor"
}
git rev-parse HEAD
```

Write the returned commit to `last_commit`. Commit the initial cursor separately
from production work so later task diffs stay reviewable.

```powershell
git add docs/superpowers/progress/phase-3.5-loop-state.json
git commit -m "chore: initialize phase 3.5 execution cursor"
```

- [ ] **Step 3: enforce one-task cycles**

For each later task, set `running` before edits, `verifying` before its required
commands, and `review_required` only after they pass. Record command, exit code,
changed files, commit, and next eligible task. Stop after two identical failure
signatures, an out-of-scope file need, a golden/dependency decision, or any human
gate. The cursor cannot mark a plan checkbox complete by itself.

---

## Task 1 — Dependency, tracing, and bundled-runtime spike

**Files:**

- Modify: `hermes_core/pyproject.toml`
- Modify: `hermes_core/uv.lock`
- Modify: `python/requirements-desktop.txt`
- Modify: `python/tools/verify_bundle_site_packages.py`
- Modify: `tauri/src/python_supervisor.rs`
- Modify: `tauri/src/gateway_supervisor.rs`
- Create: `python/tests/test_langgraph_bundle_contract.py`
- Modify: `DECISIONS.md`

- [ ] **Step 1: record the pre-change runtime size**

Run from the repository root:

```powershell
$before = (Get-ChildItem python\dist\runtime -Recurse -File |
  Measure-Object Length -Sum).Sum
[math]::Round($before / 1MB, 2)
```

Record the number under the Task 1 completion note in this document. If the
runtime does not exist, run `./python/build_bundle.ps1 -Verify` first.

- [ ] **Step 2: write the failing bundle contract test**

The test must assert all of these invariants:

```python
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class LangGraphBundleContractTests(unittest.TestCase):
    def test_desktop_requirements_pin_langgraph_exactly_once(self):
        path = ROOT / "python" / "requirements-desktop.txt"
        text = path.read_text("utf-8")
        self.assertEqual(text.count("langgraph==1.2.6"), 1)

    def test_both_children_force_langsmith_tracing_off(self):
        for relpath in (
            "tauri/src/python_supervisor.rs",
            "tauri/src/gateway_supervisor.rs",
        ):
            with self.subTest(relpath=relpath):
                text = (ROOT / relpath).read_text("utf-8")
                self.assertIn('.env("LANGSMITH_TRACING", "false")', text)
```

Run:

```powershell
cd python
python -m unittest tests.test_langgraph_bundle_contract -v
cd ..
```

Expected: FAIL because the pin and supervisor env are absent.

- [ ] **Step 3: add the same exact direct pin to both dependency manifests**

Add this line to `hermes_core/pyproject.toml` project dependencies and to the
core section of `python/requirements-desktop.txt`:

```text
langgraph==1.2.6
```

Do not add direct production dependencies on `langchain`, `langchain-core`,
`langgraph-prebuilt`, or `langsmith`; they are accepted transitive dependencies
and remain visible in the lockfile audit.

- [ ] **Step 4: refresh and inspect the core lockfile**

```powershell
cd hermes_core
uv lock
uv tree | Select-String -Pattern "langgraph|langchain-core|langsmith"
cd ..
```

Expected: the tree contains `langgraph`, `langchain-core`,
`langgraph-checkpoint`, `langgraph-prebuilt`, `langgraph-sdk`, and `langsmith`.
Stop if the resolver selects a different `langgraph` version or requires a
Python version newer than 3.11.

- [ ] **Step 5: disable LangSmith tracing in both child supervisors**

Add the same command-builder entry beside the existing Python environment
settings in both Rust supervisors:

```rust
.env("LANGSMITH_TRACING", "false")
```

Do not use `LANGSMITH_TRACING_V2`; it is not the current documented switch.

- [ ] **Step 6: extend the bundle verifier**

Add these imports to `python/tools/verify_bundle_site_packages.py`:

```python
from langgraph.graph import END, START, StateGraph  # noqa: F401
```

The verifier must not import `MemorySaver`, `InMemorySaver`, LangChain agents,
or LangSmith clients.

- [ ] **Step 7: rebuild and verify bundled CPython 3.11**

```powershell
./python/build_bundle.ps1 -Verify
./python/dist/runtime/python/python.exe -c `
  "from langgraph.graph import StateGraph; import sys; assert sys.version_info[:2] == (3, 11); print('langgraph bundle ok')"
```

Expected: `langgraph bundle ok` and exit code 0.

- [ ] **Step 8: record dependency and size evidence**

```powershell
$after = (Get-ChildItem python\dist\runtime -Recurse -File |
  Measure-Object Length -Sum).Sum
[math]::Round($after / 1MB, 2)
```

Record before, after, and delta in this document and `DECISIONS.md`. The gate
fails if the delta exceeds 25 MB or the Windows build requires a source-built
wheel. A failed gate triggers a separate decision between an older supported
pin and an owned finite-state engine; do not silently loosen the threshold.

- [ ] **Step 9: run tests and commit**

```powershell
cd python
python -m unittest tests.test_langgraph_bundle_contract -v
cd ..
cd tauri
cargo test
cd ..
git add hermes_core/pyproject.toml hermes_core/uv.lock `
  python/requirements-desktop.txt python/tools/verify_bundle_site_packages.py `
  python/tests/test_langgraph_bundle_contract.py tauri/src/python_supervisor.rs `
  tauri/src/gateway_supervisor.rs DECISIONS.md `
  docs/superpowers/specs/2026-06-24-consolidate-and-langgraph-replatform-plan.md
git commit -m "build: validate langgraph desktop dependency closure"
```

Expected: Python contract and Rust tests pass.

---

## Task 2 — Complete the legacy exit and side-effect contract

**Files:**

- Modify: `hermes_core/tests/run_agent/golden_harness.py`
- Modify: `hermes_core/tests/run_agent/test_golden_transcripts.py`
- Create: `hermes_core/tests/run_agent/test_exit_contract.py`
- Create: `hermes_core/tests/run_agent/test_hook_invocation_parity.py`
- Modify: `hermes_core/tests/run_agent/golden/plain_text.json`
- Modify: `hermes_core/tests/run_agent/golden/unknown_tool.json`
- Create: `hermes_core/tests/run_agent/golden/exit_nous_rate_guard.json`
- Create: `hermes_core/tests/run_agent/golden/exit_invalid_response.json`
- Create: `hermes_core/tests/run_agent/golden/exit_interrupt_invalid_wait.json`
- Create: `hermes_core/tests/run_agent/golden/exit_thinking_budget.json`
- Create: `hermes_core/tests/run_agent/golden/exit_text_continuation.json`
- Create: `hermes_core/tests/run_agent/golden/exit_truncated_tool_call.json`
- Create: `hermes_core/tests/run_agent/golden/exit_truncation_rollback.json`
- Create: `hermes_core/tests/run_agent/golden/exit_first_response_truncated.json`
- Create: `hermes_core/tests/run_agent/golden/exit_interrupt_api_error.json`
- Create: `hermes_core/tests/run_agent/golden/exit_payload_compression.json`
- Create: `hermes_core/tests/run_agent/golden/exit_payload_no_compression.json`
- Create: `hermes_core/tests/run_agent/golden/exit_safe_output_context.json`
- Create: `hermes_core/tests/run_agent/golden/exit_context_stepdown.json`
- Create: `hermes_core/tests/run_agent/golden/exit_context_no_compression.json`
- Create: `hermes_core/tests/run_agent/golden/exit_nonretryable_client.json`
- Create: `hermes_core/tests/run_agent/golden/exit_api_retries.json`
- Create: `hermes_core/tests/run_agent/golden/exit_interrupt_retry_wait.json`
- Create: `hermes_core/tests/run_agent/golden/exit_incomplete_scratchpad.json`
- Create: `hermes_core/tests/run_agent/golden/exit_truncated_json_args.json`

The contract for each exit is:

- exact result-key presence and values;
- exact message trajectory and tool ordering;
- stream/status/interim event order;
- persisted rows and trajectory writes;
- cleanup call count and task id;
- whether `clear_interrupt()` runs;
- plugin hook names, order, and payloads, including hooks that are absent;
- usage and cost accounting.

- [ ] **Step 1: extend harness observations without changing fixtures**

Add these snapshot fields with deterministic lists and booleans:

```python
snapshot["result_keys"] = sorted(result)
snapshot["hook_calls"] = hook_calls
snapshot["cleanup_task_ids"] = cleanup_task_ids
snapshot["clear_interrupt_calls"] = clear_interrupt_calls
```

Patch the shared hook dispatcher, `_cleanup_task_resources`, and
`clear_interrupt` at their existing boundaries. Do not patch the loop branches
being characterized.

- [ ] **Step 2: add named scenarios for all 21 return sites**

`test_exit_contract.py` must contain this exact scenario inventory so a source
return cannot disappear from the equivalence review unnoticed:

| Return | Scenario id | Fixture |
|---:|---|---|
| 10086 | `nous_rate_guard_without_fallback` | `exit_nous_rate_guard.json` |
| 10311 | `invalid_response_retries_exhausted` | `exit_invalid_response.json` |
| 10332 | `interrupt_during_invalid_response_wait` | `exit_interrupt_invalid_wait.json` |
| 10445 | `thinking_budget_exhausted` | `exit_thinking_budget.json` |
| 10485 | `text_continuation_exhausted` | `exit_text_continuation.json` |
| 10513 | `truncated_tool_call_repeated` | `exit_truncated_tool_call.json` |
| 10530 | `truncation_rolls_back_history` | `exit_truncation_rollback.json` |
| 10542 | `first_response_truncated` | `exit_first_response_truncated.json` |
| 11097 | `interrupt_during_api_error_handling` | `exit_interrupt_api_error.json` |
| 11267 | `payload_compression_attempts_exhausted` | `exit_payload_compression.json` |
| 11298 | `payload_cannot_compress` | `exit_payload_no_compression.json` |
| 11351 | `safe_output_context_attempts_exhausted` | `exit_safe_output_context.json` |
| 11424 | `context_stepdown_attempts_exhausted` | `exit_context_stepdown.json` |
| 11457 | `context_cannot_compress` | `exit_context_no_compression.json` |
| 11552 | `nonretryable_client_error` | `exit_nonretryable_client.json` |
| 11635 | `api_retries_exhausted` | `exit_api_retries.json` |
| 11677 | `interrupt_during_generic_retry_wait` | `exit_interrupt_retry_wait.json` |
| 11831 | `incomplete_scratchpad_exhausted` | `exit_incomplete_scratchpad.json` |
| 11878 | `unknown_tool_retries_exhausted` | existing `unknown_tool.json` |
| 11944 | `truncated_json_tool_arguments` | `exit_truncated_json_args.json` |
| 12664 | `normal_final_result` | existing `plain_text.json` |

Line numbers document the 2026-06-27 audit; scenario ids are the stable
contract. Future line movement must not rename the scenarios.

- [ ] **Step 3: record loop snapshots once, then freeze them**

```powershell
cd hermes_core
$env:GOLDEN_RECORD = "1"
python -m pytest tests/run_agent/test_golden_transcripts.py `
  -o "addopts=" -p no:cacheprovider
Remove-Item Env:GOLDEN_RECORD
git diff -- tests/run_agent/golden
```

Review every fixture diff. Once committed, Phase 3.5 graph work must not run
with `GOLDEN_RECORD=1`.

- [ ] **Step 4: prove deterministic replay twice**

```powershell
python -m pytest tests/run_agent/test_golden_transcripts.py `
  tests/run_agent/test_exit_contract.py `
  tests/run_agent/test_hook_invocation_parity.py `
  -o "addopts=" -p no:cacheprovider -q
python -m pytest tests/run_agent/test_golden_transcripts.py `
  tests/run_agent/test_exit_contract.py `
  tests/run_agent/test_hook_invocation_parity.py `
  -o "addopts=" -p no:cacheprovider -q
cd ..
```

Expected: both runs pass with identical fixture files and no network, real DB,
or user-home writes.

- [ ] **Step 5: commit the characterization gate**

```powershell
git add hermes_core/tests/run_agent
git commit -m "test: pin all agent loop exit contracts"
```

---

## Task 3 — Introduce graph contracts and import isolation

**Files:**

- Create: `hermes_core/agent/graph_engine/__init__.py`
- Create: `hermes_core/agent/graph_engine/contracts.py`
- Create: `hermes_core/agent/graph_engine/ports.py`
- Create: `hermes_core/agent/graph_engine/nodes.py`
- Create: `hermes_core/agent/graph_engine/builder.py`
- Create: `hermes_core/agent/graph_engine/engine.py`
- Create: `hermes_core/tests/agent/test_graph_import_isolation.py`
- Create: `hermes_core/tests/agent/test_graph_contracts.py`

- [ ] **Step 1: write failing import-isolation and contract tests**

The import test walks production `.py` files and allows `langgraph` imports only
in `agent/graph_engine/builder.py`. It rejects production imports beginning with
`langchain` or `langsmith` everywhere. The contract test asserts that converting
a `LegacyRunResult` to output does not add absent optional keys.

Run:

```powershell
cd hermes_core
python -m pytest tests/agent/test_graph_import_isolation.py `
  tests/agent/test_graph_contracts.py -o "addopts=" -p no:cacheprovider -q
```

Expected: FAIL because the package does not exist.

- [ ] **Step 2: define the exact public result and serializable state**

`contracts.py` starts with these result fields and keeps optional key presence:

```python
from typing import Any, Literal, NotRequired, TypedDict


class LegacyRunResult(TypedDict, total=False):
    final_response: str | None
    messages: list[dict[str, Any]]
    api_calls: int
    completed: bool
    partial: bool
    interrupted: bool
    failed: bool
    error: str
    compression_exhausted: bool


Route = Literal[
    "prepare_request",
    "call_transport",
    "process_response",
    "handle_transport_error",
    "dispatch_tools",
    "apply_steer",
    "summarize_on_budget",
    "finish",
]


class ExitPolicy(TypedDict):
    cleanup_task_resources: bool
    persist_session: bool
    save_trajectory: bool
    fire_post_llm_call: bool
    fire_on_session_end: bool
    clear_interrupt: bool


class TurnState(TypedDict):
    user_message: Any
    system_message: str | None
    conversation_history: list[dict[str, Any]] | None
    messages: list[dict[str, Any]]
    effective_task_id: str
    api_call_count: int
    retry_count: int
    compression_attempts: int
    iteration_budget_remaining: int
    fallback_index: int
    route: Route
    result: NotRequired[LegacyRunResult]
    exit_policy: NotRequired[ExitPolicy]
```

Callbacks, clients, plugin managers, DB handles, and the `AIAgent` instance must
not be fields of `TurnState`.

- [ ] **Step 3: define service ports and pure nodes**

`ports.py` defines a `GraphServices` protocol with named methods for:

`initialize_turn`, `prepare_request`, `call_transport`, `process_response`,
`handle_transport_error`, `dispatch_tools`, `apply_steer`,
`summarize_on_budget`, and `apply_exit_policy`.

Every method accepts `TurnState` and returns a partial state update dictionary.
It may call existing `AIAgent` helpers through the adapter, but it must not
return LangGraph or LangChain types. If an existing helper mutates per-turn
state on `AIAgent`, the adapter copies the resulting value into its returned
state update before the next node. `nodes.py` contains one function per method
and delegates through this protocol.

- [ ] **Step 4: build without a checkpointer**

`builder.py` is the only file that imports:

```python
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
```

It declares a runtime context containing `GraphServices`, wraps the pure node
functions, adds explicit conditional edges based on `state["route"]`, and calls:

```python
compiled = graph.compile()
```

Do not pass a checkpointer. Do not use message reducers; Hermes message lists
remain ordinary dictionaries and each node returns the complete replacement
list when it changes messages.

- [ ] **Step 5: pass tests and commit**

```powershell
python -m pytest tests/agent/test_graph_import_isolation.py `
  tests/agent/test_graph_contracts.py -o "addopts=" -p no:cacheprovider -q
cd ..
git add hermes_core/agent/graph_engine hermes_core/tests/agent
git commit -m "feat: add isolated agent graph contracts"
```

---

## Task 4 — Plain-text vertical slice

**Files:**

- Modify: `hermes_core/run_agent.py`
- Modify: `hermes_core/agent/graph_engine/nodes.py`
- Modify: `hermes_core/agent/graph_engine/builder.py`
- Modify: `hermes_core/agent/graph_engine/engine.py`
- Modify: `hermes_core/tests/run_agent/golden_harness.py`
- Create: `hermes_core/tests/run_agent/test_graph_plain_text.py`

- [ ] **Step 1: add a failing graph-only plain-text test**

Construct a fresh `AIAgent`, reuse the scripted chat-completions response from
`plain_text.json`, invoke `_run_conversation_graph`, and assert equality with the
frozen loop snapshot. Do not select through an environment variable yet.

- [ ] **Step 2: implement only the plain-text route**

Wire `initialize_turn → prepare_request → call_transport → process_response →
finish`. Reuse existing request builders, transport adapters, usage accounting,
message builders, and persistence helpers through `GraphServices`. Do not copy
provider SDK calls into graph files.

`pre_llm_call` fires once during initialization. `pre_api_request` and
`post_api_request` fire around each transport call. Final hook and persistence
behavior comes from the frozen normal-result exit policy.

- [ ] **Step 3: run loop and graph assertions**

```powershell
cd hermes_core
python -m pytest tests/run_agent/test_graph_plain_text.py `
  tests/run_agent/test_golden_transcripts.py `
  -o "addopts=" -p no:cacheprovider -q
cd ..
```

Expected: plain text matches exactly and the legacy suite remains green.

- [ ] **Step 4: commit**

```powershell
git add hermes_core/run_agent.py hermes_core/agent/graph_engine `
  hermes_core/tests/run_agent
git commit -m "feat: run plain agent turns through graph engine"
```

---

## Task 5 — Anthropic protocol and streaming parity

**Files:**

- Modify: `hermes_core/run_agent.py`
- Modify: `hermes_core/agent/graph_engine/ports.py`
- Modify: `hermes_core/agent/graph_engine/nodes.py`
- Modify: `hermes_core/agent/graph_engine/builder.py`
- Modify: `hermes_core/agent/graph_engine/engine.py`
- Modify: `hermes_core/tests/run_agent/test_streaming.py`
- Create: `hermes_core/tests/run_agent/test_graph_protocol_parity.py`

- [ ] **Step 1: write failing Anthropic and streaming graph tests**

Cover `anthropic_text.json` and the existing streaming cases for delta order,
callback exceptions, stream-drop fallback, and interrupt polling.

- [ ] **Step 2: route both protocols through one transport service port**

The graph node chooses neither SDK nor wire format. `GraphServices.call_transport`
delegates to the existing `_interruptible_api_call` /
`_anthropic_messages_create` boundary using the current `api_mode` and returns a
normalized response update.

Interrupt polling remains inside blocking transport and retry helpers; a graph
node between blocking operations is not a substitute for the current 200 ms
polling behavior.

- [ ] **Step 3: run and commit**

```powershell
cd hermes_core
python -m pytest tests/run_agent/test_graph_protocol_parity.py `
  tests/run_agent/test_streaming.py `
  tests/run_agent/test_golden_transcripts.py `
  -o "addopts=" -p no:cacheprovider -q
cd ..
git add hermes_core/run_agent.py hermes_core/agent/graph_engine `
  hermes_core/tests/run_agent
git commit -m "feat: preserve graph transport and streaming parity"
```

---

## Task 6 — Tool dispatch, concurrency, and steer parity

**Files:**

- Modify: `hermes_core/run_agent.py`
- Modify: `hermes_core/agent/graph_engine/ports.py`
- Modify: `hermes_core/agent/graph_engine/nodes.py`
- Modify: `hermes_core/agent/graph_engine/builder.py`
- Modify: `hermes_core/agent/graph_engine/engine.py`
- Create: `hermes_core/tests/run_agent/test_graph_tool_parity.py`

- [ ] **Step 1: write failing graph tests for tool branches**

Use `single_tool.json`, `parallel_tools.json`, `unknown_tool.json`,
`exit_truncated_json_args.json`, and `steer.json`. Assert invocation order,
sequential/concurrent choice, tool-result message shape, steer suffix placement,
and partial exits.

- [ ] **Step 2: implement dispatch and steer nodes through existing helpers**

`dispatch_tools` calls `_execute_tool_calls`; it does not reproduce tool
selection or thread-pool code. The returned state update contains a replacement
messages list and the next route. `apply_steer` calls `_drain_pending_steer` once
at the same logical boundary as the loop.

- [ ] **Step 3: run and commit**

```powershell
cd hermes_core
python -m pytest tests/run_agent/test_graph_tool_parity.py `
  tests/run_agent/test_golden_transcripts.py `
  -o "addopts=" -p no:cacheprovider -q
cd ..
git add hermes_core/run_agent.py hermes_core/agent/graph_engine `
  hermes_core/tests/run_agent
git commit -m "feat: preserve graph tool and steer behavior"
```

---

## Task 7 — Retry, fallback, interruption, and error parity

**Files:**

- Modify: `hermes_core/run_agent.py`
- Modify: `hermes_core/agent/graph_engine/contracts.py`
- Modify: `hermes_core/agent/graph_engine/ports.py`
- Modify: `hermes_core/agent/graph_engine/nodes.py`
- Modify: `hermes_core/agent/graph_engine/builder.py`
- Modify: `hermes_core/agent/graph_engine/engine.py`
- Create: `hermes_core/tests/run_agent/test_graph_error_parity.py`

- [ ] **Step 1: write failing graph tests for transport-error exits**

Cover fallback, rate guard, invalid response retry, nonretryable client error,
generic retry exhaustion, interrupt during both retry waits, and interrupt during
API-error handling. Patch sleep through the existing harness clock; do not reduce
production retry counts for tests.

- [ ] **Step 2: implement error classification and routing**

The node delegates classification, credential rotation, provider fallback,
backoff calculation, and primary-runtime restoration to existing helpers. State
records counters and the next route; provider/base URL/API mode mutations remain
encapsulated by the service adapter until a later extraction can make them fully
state-driven.

- [ ] **Step 3: prove an error cannot live-fallback to the other engine**

Add a test in which a graph tool side effect is recorded and a later graph node
raises. Assert the legacy loop is never invoked and the side-effect count is one.

- [ ] **Step 4: run and commit**

```powershell
cd hermes_core
python -m pytest tests/run_agent/test_graph_error_parity.py `
  tests/run_agent/test_exit_contract.py `
  -o "addopts=" -p no:cacheprovider -q
cd ..
git add hermes_core/run_agent.py hermes_core/agent/graph_engine `
  hermes_core/tests/run_agent
git commit -m "feat: preserve graph retry and fallback behavior"
```

---

## Task 8 — Compression, truncation, and budget parity

**Files:**

- Modify: `hermes_core/run_agent.py`
- Modify: `hermes_core/agent/graph_engine/contracts.py`
- Modify: `hermes_core/agent/graph_engine/ports.py`
- Modify: `hermes_core/agent/graph_engine/nodes.py`
- Modify: `hermes_core/agent/graph_engine/builder.py`
- Modify: `hermes_core/agent/graph_engine/engine.py`
- Create: `hermes_core/tests/run_agent/test_graph_budget_parity.py`

- [ ] **Step 1: write failing graph tests for every budget exit family**

Cover preflight compression, payload-too-large compression, context step-down,
cannot-compress paths, thinking-budget exhaustion, text continuation, truncated
tool calls, incomplete scratchpads, and max-iteration summarization.

- [ ] **Step 2: implement graph routes through existing compression helpers**

Compression may rotate `session_id` and clear `conversation_history`; return both
changes explicitly in state. `summarize_on_budget` keeps the existing direct
toolless summary call and its API-mode behavior. Configure LangGraph's recursion
limit high enough for the current `max_iterations` plus retry nodes, but keep
Hermes `iteration_budget` as the user-visible budget authority.

Set the invocation recursion limit deterministically:

```python
recursion_limit = max(1000, (max_iterations * 12) + 100)
```

- [ ] **Step 3: run and commit**

```powershell
cd hermes_core
python -m pytest tests/run_agent/test_graph_budget_parity.py `
  tests/run_agent/test_exit_contract.py `
  -o "addopts=" -p no:cacheprovider -q
cd ..
git add hermes_core/run_agent.py hermes_core/agent/graph_engine `
  hermes_core/tests/run_agent
git commit -m "feat: preserve graph compression and budget behavior"
```

---

## Task 9 — Finalization and full dual-engine equivalence

**Files:**

- Modify: `hermes_core/run_agent.py`
- Modify: `hermes_core/agent/graph_engine/contracts.py`
- Modify: `hermes_core/agent/graph_engine/ports.py`
- Modify: `hermes_core/agent/graph_engine/nodes.py`
- Modify: `hermes_core/agent/graph_engine/builder.py`
- Modify: `hermes_core/agent/graph_engine/engine.py`
- Modify: `hermes_core/tests/run_agent/golden_harness.py`
- Modify: `hermes_core/tests/run_agent/test_golden_transcripts.py`
- Modify: `hermes_core/tests/run_agent/test_hook_invocation_parity.py`

- [ ] **Step 1: apply the frozen exit policy instead of one universal finalizer**

For each scenario, `finish` produces the exact `LegacyRunResult` and
`ExitPolicy`. `apply_exit_policy` performs only the side effects enabled by that
policy. Do not make early exits fire hooks merely because the normal path does.

- [ ] **Step 2: parameterize all fixtures over independent engine instances**

`replay_transcript(spec, engine="loop")` and
`replay_transcript(spec, engine="graph")` must construct separate agents and
fresh scripted transports. The test compares the complete snapshots. Do not
change `os.environ` inside a parameterized test because xdist workers and nested
agents may share it.

- [ ] **Step 3: run the full equivalence gate twice**

```powershell
cd hermes_core
python -m pytest tests/run_agent/test_golden_transcripts.py `
  tests/run_agent/test_exit_contract.py `
  tests/run_agent/test_hook_invocation_parity.py `
  -o "addopts=" -p no:cacheprovider -q
python -m pytest tests/run_agent/test_golden_transcripts.py `
  tests/run_agent/test_exit_contract.py `
  tests/run_agent/test_hook_invocation_parity.py `
  -o "addopts=" -p no:cacheprovider -q
python -m pytest tests/run_agent -q -n 4
cd ..
```

Expected: both deterministic runs pass; the broader slice passes under both
engines after Task 10 installs the selector. At this task, the broader slice is
the legacy-regression gate; graph coverage comes from the explicitly
parameterized golden and exit-contract tests. Any newly discovered branch gets
a loop fixture before its graph fix.

Passing this task alone does not open Goal Runner G1. Task 10 must also land the
public selector so the outer-loop adapter can select each engine without calling
private methods.

- [ ] **Step 4: commit**

```powershell
git add hermes_core/run_agent.py hermes_core/agent/graph_engine `
  hermes_core/tests/run_agent
git commit -m "test: prove loop and graph agent equivalence"
```

---

## Task 10 — Strangler selector and one-release escape hatch

**Files:**

- Create: `hermes_core/agent/engine_selector.py`
- Create: `hermes_core/tests/agent/test_engine_selector.py`
- Modify: `hermes_core/hermes_cli/config_defaults.py`
- Modify: `hermes_core/run_agent.py`
- Modify: `DECISIONS.md`

The selector precedence is:

1. explicit `AIAgent(agent_engine="graph")` constructor argument;
2. `HERMES_AGENT_ENGINE` environment override;
3. `agent.engine` from the active profile's `config.yaml`;
4. default `loop` during migration.

Only `loop` and `graph` are valid. An invalid explicit or environment value
raises `ValueError`; an invalid config value logs a warning and falls back to
`loop` so a bad user file does not brick startup.

- [ ] **Step 1: write selector precedence tests**

Test all four levels, invalid values, profile-aware `HERMES_HOME`, and separate
web/gateway process environments.

- [ ] **Step 2: add the config default**

```yaml
agent:
  engine: loop
```

Adding the key is handled by deep merge and does not bump `_config_version`.

- [ ] **Step 3: rename and dispatch the legacy body**

Add `agent_engine: str | None = None` to `AIAgent.__init__`, resolve it once
through `engine_selector.py`, and store the validated value on
`self.agent_engine`. Keep the current body intact as `_run_conversation_loop`.
The public method selects once before any per-turn setup or side effect:

```python
def run_conversation(self, user_message, system_message=None,
                     conversation_history=None, task_id=None,
                     stream_callback=None, persist_user_message=None):
    if self.agent_engine == "graph":
        return self._run_conversation_graph(
            user_message=user_message,
            system_message=system_message,
            conversation_history=conversation_history,
            task_id=task_id,
            stream_callback=stream_callback,
            persist_user_message=persist_user_message,
        )
    return self._run_conversation_loop(
        user_message=user_message,
        system_message=system_message,
        conversation_history=conversation_history,
        task_id=task_id,
        stream_callback=stream_callback,
        persist_user_message=persist_user_message,
    )
```

Do not catch a graph exception and invoke `_run_conversation_loop` for the same
turn.

- [ ] **Step 4: run and commit**

```powershell
cd hermes_core
python -m pytest tests/agent/test_engine_selector.py `
  -o "addopts=" -p no:cacheprovider -q
$env:HERMES_AGENT_ENGINE = "loop"
python -m pytest tests/run_agent -q -n 4
$env:HERMES_AGENT_ENGINE = "graph"
python -m pytest tests/run_agent -q -n 4
Remove-Item Env:HERMES_AGENT_ENGINE
cd ..
git add hermes_core/agent/engine_selector.py `
  hermes_core/tests/agent/test_engine_selector.py `
  hermes_core/hermes_cli/config_defaults.py hermes_core/run_agent.py DECISIONS.md
git commit -m "feat: add rollback-safe agent engine selector"
```

- [ ] **Step 5: open the companion plan's G1 gate**

Record the Task 9 equivalence commit and this selector commit in
`docs/superpowers/plans/2026-06-27-bounded-goal-runner.md`. Goal Runner Tasks
7–9 may now integrate through public `AIAgent.run_conversation`. They must finish
their explicit loop/graph adapter gate before this plan removes the selector.

---

## Task 11 — Desktop release smoke, default flip, and legacy removal

**Files:**

- Modify after smoke: `hermes_core/hermes_cli/config_defaults.py`
- Modify after one release: `hermes_core/run_agent.py`
- Modify after one release: `hermes_core/agent/engine_selector.py`
- Modify: `DECISIONS.md`
- Modify: this plan

- [ ] **Step 1: build the release-equivalent runtime**

```powershell
./python/build_bundle.ps1 -Verify
cd web
npm ci
npm run build
cd ..
cd tauri
cargo tauri build
cd ..
```

Expected: bundle verification, web build, and Tauri build all succeed.

- [ ] **Step 2: run graph smoke on both API modes**

With `agent.engine: graph`, run:

1. a multi-turn chat-completions conversation with one read-only tool call;
2. the same shape on an `anthropic_messages` provider;
3. an interrupt during a long model call;
4. an app restart followed by session resume;
5. one gateway profile conversation to prove the separate process selects graph.

Record date, provider, model, tool, result, and log path in this document. Do
not use a state-changing tool for the smoke.

- [ ] **Step 3: flip the default only after GO is recorded**

Change `agent.engine` default from `loop` to `graph`. Retain explicit
`agent.engine: loop` and `HERMES_AGENT_ENGINE=loop` for one release. Update user
support documentation with the rollback setting.

- [ ] **Step 4: complete a release-cycle soak**

The soak is at least 14 days and requires:

- no unresolved P0/P1 issue attributable to graph execution;
- release-build smoke green on both API modes at the beginning and end;
- no unexplained differences in result shapes, hooks, persistence, or usage;
- every graph regression added first as a loop fixture, then fixed.

When this evidence is recorded, open Goal Runner G2. Its Task 10 may expose the
host-only Pilot 1 while the loop escape hatch still exists.

- [ ] **Step 5: remove the legacy loop in a dedicated commit**

After the soak, first require Goal Runner Task 10 to record one bounded synthetic
pilot under explicit `loop` and one under explicit `graph`, or explicitly record
that the Goal Runner plan is deferred before runtime integration. Then delete
`_run_conversation_loop`, the selector flag, and loop-only tests. Keep the
engine-independent contracts, service ports, golden fixtures, and graph
import-isolation test. Do not use `run_agent.py` line-count reduction as the
success criterion; use branch coverage, exit-contract coverage, and dependency
direction instead.

```powershell
git add hermes_core/run_agent.py hermes_core/agent/engine_selector.py `
  hermes_core/hermes_cli/config_defaults.py hermes_core/tests DECISIONS.md `
  docs/superpowers/specs/2026-06-24-consolidate-and-langgraph-replatform-plan.md
git commit -m "refactor: remove legacy agent conversation loop"
```

---

## Rollback rules

- Before the default flip, rollback is `agent.engine: loop`; no code rollback is
  required.
- After the default flip and during the one-release escape window, support may
  set `agent.engine: loop` in the affected profile or launch with
  `HERMES_AGENT_ENGINE=loop`, then restart the relevant child/app.
- A graph failure after any possible tool execution must return its graph error.
  It must not retry through the loop because that can duplicate file writes,
  shell commands, messages, or external API mutations.
- If equivalence work stalls for two weeks, keep default `loop`, retain graph as
  an opt-in test path, record the failing scenarios, and close Phase 3.5 as
  deferred.
- If the dependency or bundle gate fails, remove the spike cleanly and write a
  separate owned finite-state-engine plan. Do not vendor LangGraph internals.

---

## Verification matrix

Run the smallest relevant row after every commit and the entire matrix before a
default flip.

| Surface | Command | Required result |
|---|---|---|
| Deterministic goldens | `cd hermes_core; python -m pytest tests/run_agent/test_golden_transcripts.py -o "addopts=" -p no:cacheprovider -q` | All fixtures pass twice without changes. |
| Core run-agent slice | `cd hermes_core; python -m pytest tests/run_agent -q -n 4` | Pass under loop and graph. |
| Provider guards | `cd hermes_core; python -m pytest tests/agent/test_provider_package_split.py tests/kabuqina/test_compat_imports.py -q -n 4` | Pass. |
| Desktop Python | `cd python; python -m unittest discover -s tests -p "test_*.py" -v` | Pass. |
| Bundle | `./python/build_bundle.ps1 -Verify` | Bundled CPython 3.11 imports LangGraph. |
| Web | `cd web; npm run lint; npm run build` | Pass. |
| Rust | `cd tauri; cargo test` | Pass. |
| Live runtime | release build, both API modes, one read-only tool | Result recorded in this plan. |
| Outer-loop compatibility | If Goal Runner G1 has opened: `cd hermes_core; python -m pytest tests/cron/test_goal_agent_worker.py tests/cron/test_cron_goal.py -o "addopts=" -p no:cacheprovider -q` | Explicit loop and graph cases pass before legacy-loop removal. |

On environments where `hermes_core/scripts/run_tests.sh` is available, prefer
that wrapper for CI-parity. Native Windows fallback uses `-n 4`; golden recording
and deterministic replay deliberately clear repository addopts and disable
xdist.

---

## Phase 3.5 exit criteria

All must hold:

- [ ] dependency closure and actual bundle-size delta are recorded;
- [ ] bundled Python 3.11 imports and runs the low-level graph;
- [ ] LangSmith tracing is forced off for web and gateway children;
- [ ] all 21 legacy exit scenarios have frozen loop contracts;
- [ ] loop and graph snapshots match twice deterministically;
- [ ] hook, cleanup, interrupt, persistence, stream, usage, and result-key parity
  tests pass;
- [ ] both API modes pass release-build chat + tool smoke;
- [ ] graph is default for a 14-day release soak with the loop escape hatch;
- [ ] before legacy-loop removal, Goal Runner Task 10 records its explicit
  loop/graph synthetic pilot, or its runtime integration is explicitly deferred;
- [ ] legacy loop is removed in a dedicated commit;
- [ ] no production LangGraph import exists outside
  `agent/graph_engine/builder.py`, and no production LangChain/LangSmith import
  exists;
- [ ] `DECISIONS.md` and this plan record completion and Phase 4 may begin.
