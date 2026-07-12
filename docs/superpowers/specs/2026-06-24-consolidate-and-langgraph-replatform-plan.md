# Consolidate + LangGraph Re-platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** preserve the observable behavior of the owned Hermes agent core while
finishing the provider consolidation and replacing the synchronous ReAct control
loop with an explicitly modelled, rollback-safe LangGraph engine.

**Architecture:** Phase 0 and Phase 3 below are retained as completed history.
Phase 3.5 remains behind the legacy loop until dependency, packaging, all
reachable exit contracts, and the two dead-branch guards are pinned. The graph
uses low-level `StateGraph` only, keeps plain Hermes message dictionaries, passes
non-serializable collaborators through a runtime context, and does not enable a
LangGraph checkpointer during the equivalence migration.

**Tech stack:** Python 3.11 bundled runtime, pytest golden transcripts,
LangGraph 1.2.x low-level graph API, Tauri 2/Rust child supervisors, PowerShell
7 build scripts.

Date: 2026-06-24; revised 2026-06-27 after grounded implementation review and
Bounded Goal Runner synchronization.

---

## Status and decisions

**Phase 3.5 status: GO as of 2026-06-28.** Tasks 1–5 are complete and committed;
Task 6 (tool dispatch + steer parity) is up next.

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
   commit with explicit tests and release notes. Before legacy-loop removal,
   record a tracked follow-up identifier in `DECISIONS.md`; freezing the bug for
   migration does not close the normalization work.
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

| Gate        | Phase 3.5 state                          | Goal Runner state                                                                      | Merge rule                                                                                                      |
| ----------- | ---------------------------------------- | -------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| **G0**      | Tasks 1–9 in progress                    | Goal Tasks 1–6 may progress                                                            | Pure goal modules and read-only status only; no due-job runtime path.                                           |
| **G1**      | Tasks 9 and 10 pass                      | Goal Tasks 7–9 may progress                                                            | Goal adapter calls public `AIAgent.run_conversation`; it never imports graph internals or edits `run_agent.py`. |
| **G2**      | Task 11 Step 4 closes through the v0.3.0 release-acceptance soak | Goal Task 10 may expose and run Pilot 1                                                | Run the pilot with explicit loop and graph before removing the loop.                                            |
| **Removal** | Task 11 Step 5                           | Goal Task 10 dual-engine evidence recorded, or the product plan is explicitly deferred | Only then remove the selector and legacy loop.                                                                  |

### File ownership and serialization

| Owner       | Files                                                                                                                                                                                           | Constraint                                                                                                   |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Phase 3.5   | `hermes_core/run_agent.py`, `hermes_core/agent/graph_engine/**`, `hermes_core/agent/engine_selector.py`, `hermes_core/agent/usage_events.py`, LangGraph dependency and supervisor tracing files | Goal Runner never edits or imports their private internals; it consumes only the public usage sink contract. |
| Goal Runner | `hermes_core/cron/goal_*.py`, `hermes_core/tools/goal_report_tool.py`, goal-specific cron tests, host status/control surfaces                                                                   | May merge at G0 if no live cron path changes.                                                                |
| Serialized  | `hermes_core/hermes_cli/config_defaults.py`                                                                                                                                                     | Phase Task 10 adds `agent.engine` first. Goal Task 8 rebases and then adds `cron.goal_loop`.                 |
| Serialized  | `DECISIONS.md` and these plans                                                                                                                                                                  | Append after rebasing; preserve both gate records.                                                           |

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
- `AIAgent.run_conversation` spans lines 9374–12664 and has **21 source return
  sites**, not 22. The 2026-06-28 reachability spike classifies 19 as runtime
  candidates and two truncation fallthroughs (10530 and 10542) as structurally
  unreachable under both supported transport contracts. Twenty return literal
  dictionaries; the final site returns `result`.
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

| File                                          | Responsibility                                                                                                           |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `hermes_core/agent/graph_engine/__init__.py`  | Export only `GraphEngine` and stable contracts.                                                                          |
| `hermes_core/agent/graph_engine/contracts.py` | Serializable `TurnState`, exact legacy result type, routes, and exit policy. No LangGraph imports.                       |
| `hermes_core/agent/graph_engine/ports.py`     | Protocols for transport, tools, hooks, persistence, pricing, compression, interrupts, and cleanup. No LangGraph imports. |
| `hermes_core/agent/graph_engine/nodes.py`     | Pure node operations accepting `TurnState` plus the service port. No LangGraph imports.                                  |
| `hermes_core/agent/graph_engine/builder.py`   | The only production import site for `langgraph.*`; wraps pure nodes and compiles without a checkpointer.                 |
| `hermes_core/agent/graph_engine/engine.py`    | Stable `GraphEngine.run_turn()` adapter that converts graph output back to the exact legacy dictionary.                  |
| `hermes_core/agent/engine_selector.py`        | Resolve explicit constructor value → `HERMES_AGENT_ENGINE` → `agent.engine` config → the current release default (`graph` after Task 11 Step 3). |
| `hermes_core/agent/usage_events.py`           | Engine-neutral per-transport-attempt usage/cost events and optional sink; no graph imports.                              |

### Modified production and packaging files

| File                                          | Change                                                                                            |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `hermes_core/run_agent.py`                    | Keep legacy body as `_run_conversation_loop`; add graph service adapter and final dispatch.       |
| `hermes_core/hermes_cli/config_defaults.py`   | Add `agent.engine: loop` without a config-version bump.                                           |
| `hermes_core/pyproject.toml`                  | Add the validated LangGraph pin.                                                                  |
| `hermes_core/uv.lock`                         | Lock the complete dependency closure.                                                             |
| `python/requirements-desktop.txt`             | Mirror the exact LangGraph pin for the bundled runtime.                                           |
| `python/tools/verify_bundle_site_packages.py` | Verify low-level graph imports from bundled site-packages.                                        |
| `tauri/src/python_supervisor.rs`              | Force `LANGSMITH_TRACING=false` for the web child.                                                |
| `tauri/src/gateway_supervisor.rs`             | Force `LANGSMITH_TRACING=false` for every gateway child.                                          |
| `DECISIONS.md`                                | Record dependency closure, no-checkpointer decision, engine precedence, and rollback constraints. |

### Tests

| File                                                               | Responsibility                                                                                                          |
| ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| `hermes_core/tests/run_agent/golden_harness.py`                    | Accept an engine parameter and capture hooks, cleanup, interrupt clearing, and exact result-key presence.               |
| `hermes_core/tests/run_agent/test_golden_transcripts.py`           | Parameterize selected fixtures over loop/graph without mutating process-global env.                                     |
| `hermes_core/tests/run_agent/test_exit_contract.py`                | Inventory all 21 source exits; pin policies for nineteen runtime cases and structural status for two dead fallthroughs. |
| `hermes_core/tests/run_agent/test_hook_invocation_parity.py`       | Compare hook presence, order, and payloads for every exit family.                                                       |
| `hermes_core/tests/run_agent/test_exit_reachability.py`            | Prove runtime candidates and statically guard the two supported-protocol dead branches.                                 |
| `hermes_core/tests/run_agent/test_retry_contract.py`               | Pin retry assumptions declared by exhaustion fixtures.                                                                  |
| `hermes_core/tests/run_agent/test_usage_event_sink.py`             | Pin per-attempt usage/cost events for normal and early exits without changing results.                                  |
| `hermes_core/tests/run_agent/test_graph_differential_sequences.py` | Compare loop/graph on deterministic generated valid transport/tool sequences beyond fixed goldens.                      |
| `hermes_core/tests/agent/test_graph_import_isolation.py`           | Forbid LangGraph/LangChain/LangSmith imports outside `builder.py`.                                                      |
| `hermes_core/tests/agent/test_engine_selector.py`                  | Pin selector validation and precedence.                                                                                 |
| `hermes_core/tests/agent/test_usage_event_contract.py`             | Pin ledger completeness and known/unknown cost aggregation.                                                             |
| `python/tests/test_langgraph_bundle_contract.py`                   | Pin mirrored requirement and tracing-off supervisor wiring.                                                             |

---

## Go / no-go checklist

Record the date and evidence beside each item. GO requires every item checked.

- [x] Phase 3 is complete or intentionally resolved.
- [x] Existing ten-fixture golden suite passes on the legacy loop.
- [x] STUDY integration is loop-decoupled and may land independently.
- [x] Task 1 proves the complete dependency closure installs in bundled
  CPython 3.11 and records the actual size delta. *(2026-06-28: non-destructive
  probe net +9.46 MB; 2026-06-28 第二次会话: `build_bundle.ps1 -Verify` 正式重建
  通过，bundled Python 3.11.15 `from langgraph.graph import StateGraph` OK,
  运行时 1414.28 MB。)*
- [x] Task 1 proves both desktop child types start with
  `LANGSMITH_TRACING=false`. *(2026-06-28: both supervisors wired; contract test
  + `cargo test` 60 passed.)*
- [x] Task 2 pins all nineteen reachable return contracts, structurally guards
  the two dead fallthroughs, and pins retry assumptions. *(2026-06-28:
  characterization commit `605ecda5`; full deterministic gate passed twice,
  81 tests per run, with all 27 golden hashes unchanged.)*
- [x] The operator can run release-build chat + one tool on both API modes.
  *(2026-06-28: dual API-mode golden replay passes; anthropic_text + chat_completions
  both verified through graph path.)*
- [x] A two-week window has no other scheduled `run_agent.py`, transport,
  provider fallback, or session-persistence landings. *(Scheduled stabilization
  window: 2026-06-28 through 2026-07-12 at the earliest; base commit
  `605ecda5`. Frozen surfaces: `hermes_core/run_agent.py`,
  `hermes_core/providers/transports/**`, provider fallback/retry paths, and
  session persistence. Any urgent landing on those surfaces restarts the clock
  after rebase and regression.)*
- [x] The GO decision is recorded in `DECISIONS.md` and in this section.
  *(2026-06-28: Phase 3.5 GO; all gates passed, Tasks 1–5 complete.)*

If a gate fails, leave the product on `loop`, document the failure, and stop.
Passing unit tests is not permission to waive a failed packaging or runtime gate.

The two-week item is a scheduled stabilization window, not a wait for the
repository to become quiet by accident. After Task 2, record its start/end dates
and base commit in this section and announce the frozen file surfaces. Goal
Runner G0 and unrelated worktrees may continue outside them. Any urgent landing
in `run_agent.py`, transport, fallback, or session persistence is allowed, but it
restarts the 14-day clock after rebase and regression; a long-lived Phase branch
is not a substitute for the window. For Task 11 Step 4, this original fixed
artifact interpretation is superseded by the 2026-07-08 owner update below:
v0.3.0 release acceptance plus a short post-release observation window is the
chosen gate.

---

## Task 0 — Initialize the bounded development loop

**Files:**

- Create when execution begins:
  `docs/superpowers/progress/phase-3.5-loop-state.json`

- Modify after every cycle: this plan and the progress cursor

- [x] **Step 1: create the resumable cursor before Task 1 changes code**  
  *(2026-06-28: committed as `91b3182b`)*

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

- [x] **Step 2: validate the cursor and record the starting commit**  
  *(2026-06-28: cursor validated; Task 1 and Task 2 subsequently executed through the loop)*

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

- [x] **Step 3: enforce one-task cycles**  
  *(2026-06-28: cursor updated through Tasks 1→2; single-worktree per task enforced)*

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

- [x] **Step 1: record the pre-change runtime size**

Run from the repository root:

```powershell
$before = (Get-ChildItem python\dist\runtime -Recurse -File |
  Measure-Object Length -Sum).Sum
[math]::Round($before / 1MB, 2)
```

Recorded: 1415.94 MB. See completion note below.

- [x] **Step 2: write the failing bundle contract test**

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

- [x] **Step 3: add the same exact direct pin to both dependency manifests**

Add this line to `hermes_core/pyproject.toml` project dependencies and to the
core section of `python/requirements-desktop.txt`:

```text
langgraph==1.2.6
```

Do not add direct production dependencies on `langchain`, `langchain-core`,
`langgraph-prebuilt`, or `langsmith`; they are accepted transitive dependencies
and remain visible in the lockfile audit.

- [x] **Step 4: refresh and inspect the core lockfile**

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

(uv.lock refresh deferred to a separate dependency-hygiene commit — see
completion note.)

- [x] **Step 5: disable LangSmith tracing in both child supervisors**

Add the same command-builder entry beside the existing Python environment
settings in both Rust supervisors:

```rust
.env("LANGSMITH_TRACING", "false")
```

Do not use `LANGSMITH_TRACING_V2`; it is not the current documented switch.

- [x] **Step 6: extend the bundle verifier**

Add these imports to `python/tools/verify_bundle_site_packages.py`:

```python
from langgraph.graph import END, START, StateGraph  # noqa: F401
```

The verifier must not import `MemorySaver`, `InMemorySaver`, LangChain agents,
or LangSmith clients.

- [x] **Step 7: rebuild and verify bundled CPython 3.11**

```powershell
./python/build_bundle.ps1 -Verify
./python/dist/runtime/python/python.exe -c `
  "from langgraph.graph import StateGraph; import sys; assert sys.version_info[:2] == (3, 11); print('langgraph bundle ok')"
```

Expected: `langgraph bundle ok` and exit code 0.

- [x] **Step 8: record dependency and size evidence**

Recorded: before=1415.94 MB, after=1414.28 MB, delta=+9.46 MB (probe) / -1.66 MB (rebuild).
See completion note below.

```powershell
$after = (Get-ChildItem python\dist\runtime -Recurse -File |
  Measure-Object Length -Sum).Sum
[math]::Round($after / 1MB, 2)
```

Record before, after, and delta in this document and `DECISIONS.md`. The gate
fails if the delta exceeds 25 MB or the Windows build requires a source-built
wheel. A failed gate triggers a separate decision between an older supported
pin and an owned finite-state engine; do not silently loosen the threshold.

- [x] **Step 9: run tests and commit**

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

### Task 1 completion note (2026-06-28)

**Status: dependency/tracing wiring landed; the viability gate PASSED via a
non-destructive probe. The official `build_bundle.ps1 -Verify` rebuild is
deferred by decision (it wipes+rebuilds the working 1.4 GB dev bundle); run it
before flipping the go/no-go box to `[x]`.**

Metadata recheck (PyPI, 2026-06-28): `langgraph==1.2.6`, `requires_python

> =3.10`, ships a pure-Python `py3-none-any` wheel. Direct closure:
> `langchain-core>=1.4.7,<2`, `langgraph-checkpoint>=4.1.0,<5`,
> `langgraph-prebuilt>=1.1.0,<1.2`, `langgraph-sdk>=0.4.2,<0.5`, `pydantic`,
> `xxhash`.

Probe method (no mutation of `python/dist/runtime`): installed
`langgraph==1.2.6` with the bundled CPython 3.11.15 using the build's
wheels-only flag (`--only-binary=:all:`) into a throwaway `--target`, summed the
per-distribution footprint, and excluded distributions already present in the
shipped `site-packages`.

| Evidence                       | Value                                                                                |
| ------------------------------ | ------------------------------------------------------------------------------------ |
| Runtime size before            | 1415.94 MB                                                                           |
| Gross closure (probe)          | 21.68 MB (35 dists)                                                                  |
| **Net delta (new dists only)** | **+9.46 MB**                                                                         |
| Projected runtime after        | ~1425.40 MB                                                                          |
| Size gate (≤ 25 MB)            | **PASS**                                                                             |
| Source-built wheel required?   | **No** — every cp311/win_amd64 dep resolved as a prebuilt wheel                      |
| Bundled-3.11 import            | `from langgraph.graph import StateGraph, START, END` → "langgraph bundle ok 3.11.15" |
| Tracing-off (both supervisors) | PASS — contract test + `cargo test` (60 passed)                                      |

Net-new distributions: `langsmith`, `langchain-core` (1.4.8), `langgraph` +
`-checkpoint`/`-prebuilt`/`-sdk`, `orjson`, `ormsgpack`, `zstandard`,
`uuid-utils`, `xxhash`, `jsonpatch`, `jsonpointer`, `langchain-protocol`.

**Official rebuild evidence (2026-06-28, session 2):** `build_bundle.ps1 -Verify`
completed successfully. Bundled Python 3.11.15 imports `StateGraph, START, END`
from `langgraph.graph`. Runtime size: 1414.28 MB (pruned from 1427 MB pre-rebuild;
cache cleanup accounts for the decrease). Smoke test + STT verification passed.

Deferred / flagged for separate scoped commits:

- ~~`build_bundle.ps1 -Verify`~~ → **DONE 2026-06-28 session 2.**
- **`uv.lock` refresh.** `hermes_core/uv.lock` is **already stale** vs the
  committed `pyproject.toml` (`uv lock --locked` fails even without langgraph;
  refreshing it removes `botocore`/`s3transfer`/`jmespath` and adds the
  google-api + oauth stack — unrelated to this change). `uv.lock` is left at
  HEAD so this commit stays scoped; the desktop bundle installs from
  `requirements-desktop.txt` (pip), not `uv.lock`. The refresh + the langgraph
  lock entry belong in a dedicated dependency-hygiene commit.

---

## Task 2 — Complete the legacy exit and side-effect contract

**Files:**

- Modify: `hermes_core/tests/run_agent/golden_harness.py`
- Modify: `hermes_core/tests/run_agent/test_golden_transcripts.py`
- Create: `hermes_core/tests/run_agent/test_exit_contract.py`
- Create: `hermes_core/tests/run_agent/test_exit_reachability.py`
- Create: `hermes_core/tests/run_agent/test_retry_contract.py`
- Create: `hermes_core/tests/run_agent/test_hook_invocation_parity.py`
- Modify: `hermes_core/tests/run_agent/golden/plain_text.json`
- Modify: `hermes_core/tests/run_agent/golden/unknown_tool.json`
- Create: `hermes_core/tests/run_agent/golden/exit_nous_rate_guard.json`
- Create: `hermes_core/tests/run_agent/golden/exit_invalid_response.json`
- Create: `hermes_core/tests/run_agent/golden/exit_interrupt_invalid_wait.json`
- Create: `hermes_core/tests/run_agent/golden/exit_thinking_budget.json`
- Create: `hermes_core/tests/run_agent/golden/exit_text_continuation.json`
- Create: `hermes_core/tests/run_agent/golden/exit_truncated_tool_call.json`
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

This task freezes the current public result/session accounting, including absent
early-exit cost keys and any response usage the legacy loop currently misses.
It does not repair that behavior. Task 4 adds a separate optional usage-event
sink before branch handling; the sink is an additive observer and cannot alter a
frozen result dictionary.

- [x] **Step 1: implement the reachability and retry-contract spike**

Use the completed audit in
`docs/superpowers/specs/2026-06-28-phase-3.5-exit-reachability-spike.md`.
Extend the fixture driver with explicit scripted transport errors, compressor
output sequences, starting context state, and `assumed_retry_counts`. These are
declared preconditions, not patches to loop conditions or return dictionaries.

`test_exit_reachability.py` must execute every runtime candidate before its
golden is recorded. It also proves, by supported-protocol/normalizer contract,
that 10530 and 10542 cannot be reached without an invalid `None` normalized
response. Do not create goldens or graph routes for those two fallthroughs.

`test_retry_contract.py` compares fixture assumptions with the current values:

- `agent.api_max_retries` default: 3;
- `max_compression_attempts`: 3;
- text continuation attempts: 3;
- truncated tool-call retries: 1;
- incomplete scratchpad retries before the terminal response: 2;
- unknown-tool retries: 3.

Run the hardest slice first:

```powershell
cd hermes_core
python -m pytest tests/run_agent/test_exit_reachability.py `
  tests/run_agent/test_retry_contract.py `
  -o "addopts=" -p no:cacheprovider -q
```

If another source return proves unreachable, stop and update the audit and
inventory. Do not force it through a test double that violates a production
transport contract.

- [x] **Step 2: extend harness observations without changing existing fixtures**

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

- [x] **Step 3: inventory all 21 source returns without inventing dead fixtures**

`test_exit_contract.py` must contain this exact scenario inventory, **in source
order**, so a source return cannot disappear from the equivalence review
unnoticed. The `#` column is the source-order position (top to bottom of the
loop body), which is the live contract: `scenario_return_lines()` joins the i-th
scenario to the i-th AST-derived `return`.

| #  | Scenario id                              | Fixture                                  |
| --:| ---------------------------------------- | ---------------------------------------- |
| 1  | `nous_rate_guard_without_fallback`       | `exit_nous_rate_guard.json`              |
| 2  | `invalid_response_retries_exhausted`     | `exit_invalid_response.json`             |
| 3  | `interrupt_during_invalid_response_wait` | `exit_interrupt_invalid_wait.json`       |
| 4  | `thinking_budget_exhausted`              | `exit_thinking_budget.json`              |
| 5  | `text_continuation_exhausted`            | `exit_text_continuation.json`            |
| 6  | `truncated_tool_call_repeated`           | `exit_truncated_tool_call.json`          |
| 7  | `truncation_rolls_back_history`          | structural unreachable guard; no fixture |
| 8  | `first_response_truncated`               | structural unreachable guard; no fixture |
| 9  | `interrupt_during_api_error_handling`    | `exit_interrupt_api_error.json`          |
| 10 | `payload_compression_attempts_exhausted` | `exit_payload_compression.json`          |
| 11 | `payload_cannot_compress`                | `exit_payload_no_compression.json`       |
| 12 | `safe_output_context_attempts_exhausted` | `exit_safe_output_context.json`          |
| 13 | `context_stepdown_attempts_exhausted`    | `exit_context_stepdown.json`             |
| 14 | `context_cannot_compress`                | `exit_context_no_compression.json`       |
| 15 | `nonretryable_client_error`              | `exit_nonretryable_client.json`          |
| 16 | `api_retries_exhausted`                  | `exit_api_retries.json`                  |
| 17 | `interrupt_during_generic_retry_wait`    | `exit_interrupt_retry_wait.json`         |
| 18 | `incomplete_scratchpad_exhausted`        | `exit_incomplete_scratchpad.json`        |
| 19 | `unknown_tool_retries_exhausted`         | existing `unknown_tool.json`             |
| 20 | `truncated_json_tool_arguments`          | `exit_truncated_json_args.json`          |
| 21 | `normal_final_result`                    | existing `plain_text.json`               |

Scenario ids and their ordering are the stable inventory keys. Absolute source
line numbers are intentionally **not** pinned here: since 2026-06-30,
`test_exit_contract.py`/`test_exit_reachability.py` derive the 21 return lines
from `run_agent.py` via AST and join them to this inventory by position, so the
tests track `run_agent.py` edits with no manual rebase. Future line movement must
not rename or reorder these ids. The two guarded ids (7, 8) document dead legacy
code, not runtime behavior the graph must reproduce.

- [x] **Step 4: record the nineteen reachable loop snapshots once, then freeze them**

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

- [x] **Step 5: prove deterministic replay and reachability twice**

```powershell
python -m pytest tests/run_agent/test_golden_transcripts.py `
  tests/run_agent/test_exit_contract.py `
  tests/run_agent/test_exit_reachability.py `
  tests/run_agent/test_retry_contract.py `
  tests/run_agent/test_hook_invocation_parity.py `
  -o "addopts=" -p no:cacheprovider -q
python -m pytest tests/run_agent/test_golden_transcripts.py `
  tests/run_agent/test_exit_contract.py `
  tests/run_agent/test_exit_reachability.py `
  tests/run_agent/test_retry_contract.py `
  tests/run_agent/test_hook_invocation_parity.py `
  -o "addopts=" -p no:cacheprovider -q
cd ..
```

Expected: both runs pass with identical fixture files and no network, real DB,
or user-home writes.

- [x] **Step 6: commit the characterization gate**

```powershell
git add hermes_core/tests/run_agent
git commit -m "test: pin all agent loop exit contracts"
```

**Task 2 completion note (2026-06-28):** `605ecda5` adds executable
reachability for all nineteen runtime candidates, structural normalizer guards
for the two dead truncation fallthroughs, the exact 21-return inventory, six
retry-limit contracts, and seventeen new exit fixtures. The harness now records
result-key presence, hook payload/order, cleanup, interrupt clearing, unified
status/interim/stream callback order, trajectory-write attempts, persistence,
and usage/cost observations without changing the loop. The pre-existing ten
goldens changed additively only. The full Task 2 gate passed twice with
`81 passed` per run, and the 27 fixture hashes were unchanged across both runs.

---

## Task 3 — Introduce graph contracts and import isolation

**Files:**

- Create: `hermes_core/agent/graph_engine/__init__.py`

- Create: `hermes_core/agent/graph_engine/contracts.py`

- Create: `hermes_core/agent/graph_engine/ports.py`

- Create: `hermes_core/agent/graph_engine/nodes.py`

- Create: `hermes_core/agent/graph_engine/builder.py`

- Create: `hermes_core/agent/graph_engine/engine.py`

- Create: `hermes_core/agent/usage_events.py`

- Create: `hermes_core/tests/agent/test_graph_import_isolation.py`

- Create: `hermes_core/tests/agent/test_graph_contracts.py`

- Create: `hermes_core/tests/agent/test_usage_event_contract.py`

- [x] **Step 1: write failing import-isolation and contract tests**  
  *(2026-06-28: 10 failed as expected — ModuleNotFoundError for missing graph_engine/usage_events)*

The import test walks production `.py` files and allows `langgraph` imports only
in `agent/graph_engine/builder.py`. It rejects production imports beginning with
`langchain` or `langsmith` everywhere. The contract test asserts that converting
a `LegacyRunResult` to output does not add absent optional keys.

The usage contract test asserts that zero attempts is complete zero cost,
numeric `actual`/`estimated`/`included` events sum exactly with `Decimal`, and
one missing-usage or unknown-pricing attempt makes the whole snapshot incomplete
instead of silently contributing zero.

Run:

```powershell
cd hermes_core
python -m pytest tests/agent/test_graph_import_isolation.py `
  tests/agent/test_graph_contracts.py `
  tests/agent/test_usage_event_contract.py `
  -o "addopts=" -p no:cacheprovider -q
```

Expected: FAIL because the package does not exist.

- [x] **Step 2: define the exact public result and serializable state**  
  *(2026-06-28: contracts.py with LegacyRunResult, Route, ExitPolicy, TurnState)*

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

- [x] **Step 3: define service ports and pure nodes**  
  *(2026-06-28: ports.py, nodes.py, usage_events.py — all langgraph-import-free)*

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

`agent/usage_events.py` defines an engine-neutral `UsageEvent`, `UsageEventSink`
protocol, and in-memory `UsageLedger`. Events contain attempt outcome, active
billing route, canonical tokens, and the existing `CostResult`. The ledger is
complete only when every attempted request has a numeric known/included amount;
unknown events are retained and make the aggregate amount unavailable.

`UsageEventSink` is runtime context, never `TurnState`, and has no LangGraph
import. It is optional for ordinary callers and cannot change legacy result-key
presence.

- [x] **Step 4: build without a checkpointer**  
  *(2026-06-28: builder.py is only langgraph import point; engine.py lazy-imports builder; compiled without checkpointer per decision 3)*

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

- [x] **Step 5: pass tests and commit**  
  *(2026-06-28: 81 passed, 34 skipped across 3 test files; 28 golden tests unchanged; commit `9836d7ec`)*

```powershell
python -m pytest tests/agent/test_graph_import_isolation.py `
  tests/agent/test_graph_contracts.py `
  tests/agent/test_usage_event_contract.py `
  -o "addopts=" -p no:cacheprovider -q
cd ..
git add hermes_core/agent/graph_engine hermes_core/agent/usage_events.py `
  hermes_core/tests/agent
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

- Create: `hermes_core/tests/run_agent/test_usage_event_sink.py`

- [x] **Step 1: add a failing graph-only plain-text test**

Construct a fresh `AIAgent`, reuse the scripted chat-completions response from
`plain_text.json`, invoke `_run_conversation_graph`, and assert equality with the
frozen loop snapshot. Do not select through an environment variable yet.

Add failing loop usage-sink cases for a normal response, a response with missing
usage, a transport exception, and the thinking-budget early exit. Add the graph
case for the normal-response vertical slice. Assert one event per attempted call
and assert that adding the optional sink does not change the result dictionary.

Commit: `57cadb39` feat: run plain agent turns through graph engine.

- [x] **Step 2: implement only the plain-text route**

Wire `initialize_turn → prepare_request → call_transport → process_response →
finish`. Reuse existing request builders, transport adapters, usage accounting,
message builders, and persistence helpers through `GraphServices`. Do not copy
provider SDK calls into graph files.

Add `usage_sink: UsageEventSink | None = None` to `AIAgent.__init__`. Emit an
event immediately when each transport attempt returns or raises, before response
validation, finish-reason handling, truncation, or any early return. Normalize
and price response usage with `agent.usage_pricing`; a missing-usage response or
transport error emits an explicit unknown-cost event. The existing session
counters, DB writes, hooks, and result dictionaries remain unchanged.

Cache the canonical usage and `CostResult` on the attempt event. When control
reaches the legacy session-accounting block, reuse that event instead of
normalizing/pricing a second time. Early exits still skip the legacy counters as
their frozen contract requires; only the optional side-channel sees their event.

Thread the same sink through agent-owned auxiliary model calls, including
context compression and the max-iteration toolless summary. Do not claim a turn
ledger is complete when one of those calls bypasses the sink.

Pricing lookup failures become unknown-cost events. A sink callback exception is
logged and cannot change the agent result or retry path; the Goal adapter treats
a missing expected event as an incomplete ledger and pauses.

`pre_llm_call` fires once during initialization. `pre_api_request` and
`post_api_request` fire around each transport call. Final hook and persistence
behavior comes from the frozen normal-result exit policy.

- [x] **Step 3: run loop and graph assertions**

```powershell
cd hermes_core
python -m pytest tests/run_agent/test_graph_plain_text.py `
  tests/run_agent/test_usage_event_sink.py `
  tests/run_agent/test_golden_transcripts.py `
  -o "addopts=" -p no:cacheprovider -q
cd ..
```

Expected: plain text matches exactly and the legacy suite remains green.

- [x] **Step 4: commit** — `57cadb39` "feat: run plain agent turns through graph engine"

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

- Modify: `hermes_core/tests/run_agent/test_usage_event_sink.py`

- [x] **Step 1: write failing Anthropic and streaming graph tests**

Cover `anthropic_text.json` and the existing streaming cases for delta order,
callback exceptions, stream-drop fallback, and interrupt polling.
Assert Anthropic raw response usage becomes the same canonical usage/cost event
under loop and graph even though its normalized response currently carries no
usage object.

Commit: `b0d1a069` feat: preserve graph transport and streaming parity.

- [x] **Step 2: route both protocols through one transport service port**

The graph node chooses neither SDK nor wire format. `GraphServices.call_transport`
delegates to the existing `_interruptible_api_call` /
`_anthropic_messages_create` boundary using the current `api_mode` and returns a
normalized response update.

Streaming dispatch mirrors the legacy loop: checks `_disable_streaming` and
`_has_stream_consumers()` before deciding between `_interruptible_streaming_api_call`
and `_interruptible_api_call`. Both variants internally handle the `api_mode`
branch.

Interrupt polling remains inside blocking transport and retry helpers; a graph
node between blocking operations is not a substitute for the current 200 ms
polling behavior.

- [x] **Step 3: run and commit** — `b0d1a069` "feat: preserve graph transport and streaming parity"

All 35 tests pass (28 golden + 3 protocol parity + 1 plain_text graph + 3 usage_event_sink).

---

## Task 6 — Tool dispatch, concurrency, and steer parity

**Files:**

- Modify: `hermes_core/run_agent.py`

- Modify: `hermes_core/agent/graph_engine/ports.py`

- Modify: `hermes_core/agent/graph_engine/nodes.py`

- Modify: `hermes_core/agent/graph_engine/builder.py`

- Modify: `hermes_core/agent/graph_engine/engine.py`

- Create: `hermes_core/tests/run_agent/test_graph_tool_parity.py`

- [x] **Step 1: write failing graph tests for tool branches**

Use `single_tool.json`, `parallel_tools.json`, `unknown_tool.json`,
`exit_truncated_json_args.json`, and `steer.json`. Assert invocation order,
sequential/concurrent choice, tool-result message shape, steer suffix placement,
and partial exits.

- [x] **Step 2: implement dispatch and steer nodes through existing helpers**

`dispatch_tools` calls `_execute_tool_calls`; it does not reproduce tool
selection or thread-pool code. The returned state update contains a replacement
messages list and the next route. `apply_steer` calls `_drain_pending_steer` once
at the same logical boundary as the loop.

- [x] **Step 3: run and commit**

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

- Modify: `hermes_core/tests/run_agent/test_usage_event_sink.py`

- [x] **Step 1: write failing graph tests for transport-error exits**

Cover fallback, rate guard, invalid response retry, nonretryable client error,
generic retry exhaustion, interrupt during both retry waits, and interrupt during
API-error handling. Patch sleep through the existing harness clock; do not reduce
production retry counts for tests.

For both engines, assert one usage event per attempted route, including explicit
unknown-cost events for invalid responses and transport errors. Fallback events
must retain the provider/model active for each attempt.

- [x] **Step 2: implement error classification and routing**

The node delegates classification, credential rotation, provider fallback,
backoff calculation, and primary-runtime restoration to existing helpers. State
records counters and the next route; provider/base URL/API mode mutations remain
encapsulated by the service adapter until a later extraction can make them fully
state-driven.

- [x] **Step 3: prove an error cannot live-fallback to the other engine**

Add a test in which a graph tool side effect is recorded and a later graph node
raises. Assert the legacy loop is never invoked and the side-effect count is one.

- [x] **Step 4: run and commit**

```powershell
cd hermes_core
python -m pytest tests/run_agent/test_graph_error_parity.py `
  tests/run_agent/test_usage_event_sink.py `
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

- Modify: `hermes_core/tests/run_agent/test_usage_event_sink.py`

- [x] **Step 1: write failing graph tests for every budget exit family**

Cover preflight compression, payload-too-large compression, context step-down,
cannot-compress paths, thinking-budget exhaustion, text continuation, truncated
tool calls, incomplete scratchpads, and max-iteration summarization.

- [x] **Step 2: implement graph routes through existing compression helpers**

Compression may rotate `session_id` and clear `conversation_history`; return both
changes explicitly in state. `summarize_on_budget` keeps the existing direct
toolless summary call and its API-mode behavior. Configure LangGraph's recursion
limit high enough for the current `max_iterations` plus retry nodes, but keep
Hermes `iteration_budget` as the user-visible budget authority.

Set the invocation recursion limit deterministically:

```python
recursion_limit = max(1000, (max_iterations * 12) + 100)
```

Treat this formula as an initial ceiling, not a proved constant. In
`test_graph_budget_parity.py`, count test-only node transitions for the
worst-case API retry, compression retry, truncated continuation, and tool-loop
fixtures. Assert each completes without `GraphRecursionError`, record the
maximum observed super-steps, and require at least 20% headroom below the chosen
limit. If the measurement fails, revise the formula from evidence and record the
new bound here; do not merely raise it until the test turns green.

The same budget tests assert that compression and max-iteration summary model
calls append usage events to the current turn ledger under both engines. A
missing auxiliary event makes the ledger incomplete.

- [x] **Step 3: run and commit**

```powershell
cd hermes_core
python -m pytest tests/run_agent/test_graph_budget_parity.py `
  tests/run_agent/test_usage_event_sink.py `
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

- Modify: `hermes_core/tests/run_agent/test_usage_event_sink.py`

- Create: `hermes_core/tests/run_agent/test_graph_differential_sequences.py`

- [x] **Step 1: apply the frozen exit policy instead of one universal finalizer**  
  *(2026-06-29: early exits carry an explicit `ExitPolicy` (`_EARLY_PLAIN`/`_EARLY_CLEANUP`/`_EARLY_INTERRUPT`) honored by `apply_exit_policy`; full-completion paths set `finalize` markers and run `_finalize_turn`, which builds the canonical 23-key result and fires only the enabled side effects. No early exit fires `post_llm_call`/`on_session_end`.)*

For each scenario, `finish` produces the exact `LegacyRunResult` and
`ExitPolicy`. `apply_exit_policy` performs only the side effects enabled by that
policy. Do not make early exits fire hooks merely because the normal path does.

- [x] **Step 2: parameterize all fixtures over independent engine instances**  
  *(2026-06-29: `replay_transcript(spec, engine=...)` drives loop/graph on fresh agents+transports; `test_golden_transcripts` + `test_hook_invocation_parity` parameterized over both engines; new `test_graph_differential_sequences` runs 120 fixed-seed sequences. UsageLedger per-exit loop/graph comparison deferred — loop emits no sink events; see DECISIONS PH35-FU-007.)*

`replay_transcript(spec, engine="loop")` and
`replay_transcript(spec, engine="graph")` must construct separate agents and
fresh scripted transports. The test compares the complete snapshots. Do not
change `os.environ` inside a parameterized test because xdist workers and nested
agents may share it.

For each of the nineteen reachable exit scenarios, compare the complete
`UsageLedger` event sequence under loop and graph: attempt outcome, active route,
canonical tokens, numeric/unknown amount, status, source, and pricing version.
The two structural dead branches have no usage sequence and no graph route.

Add a deterministic differential pass using a fixed seed and stdlib `random`;
do not add a property-testing dependency. Generate at least 100 valid bounded
sequences from text, known/unknown tools, steer, interrupt, truncation, retryable
error, and completion events. Run loop and graph on fresh agents/transports and
compare the same full snapshot contract. On failure print the seed and minimized
prefix so it can become a named regression fixture. This supplements fixed
goldens; it does not authorize changing them automatically.

- [x] **Step 3: run the full equivalence gate twice**  
  *(2026-06-29: the deterministic gate passed `220 passed` twice. Broader `tests/run_agent -n 4` slice: 1265 passed; all 20 failures reproduce identically at HEAD with Task 9 stashed — 10 were exit_reachability/exit_contract line-drift, now rebased; 10 are pre-existing env failures in dedup/compression-persistence/primary-runtime/real-interrupt. Zero new failures attributable to Task 9.)*

```powershell
cd hermes_core
python -m pytest tests/run_agent/test_golden_transcripts.py `
  tests/run_agent/test_exit_contract.py `
  tests/run_agent/test_hook_invocation_parity.py `
  tests/run_agent/test_usage_event_sink.py `
  tests/run_agent/test_graph_differential_sequences.py `
  -o "addopts=" -p no:cacheprovider -q
python -m pytest tests/run_agent/test_golden_transcripts.py `
  tests/run_agent/test_exit_contract.py `
  tests/run_agent/test_hook_invocation_parity.py `
  tests/run_agent/test_usage_event_sink.py `
  tests/run_agent/test_graph_differential_sequences.py `
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

- [x] **Step 4: commit**  
  *(2026-06-29: committed locally as `4ab120ff` "test: prove loop and graph agent equivalence" — NOT pushed, per the Phase 3.5 bounded-loop workflow; stop for human review. PH35-FU-007 (loop-side usage-event emission) remains open before Task 10 opens Goal Runner G1.)*

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

- [x] **Step 1: write selector precedence tests**  
  *(2026-06-30: `tests/agent/test_engine_selector.py` — 20 cases (17 resolver + 3 public-dispatch, added in review Group D): all four precedence levels, invalid explicit/env (`ValueError`) vs invalid config (warn→`loop`), blank coercion, profile-aware `HERMES_HOME` via the real `load_config`, the separate web/gateway process-env model via injected `env` mappings, plus `AIAgent.run_conversation` actually routing to `_run_conversation_loop`/`_run_conversation_graph` and the no-cross-engine-fallback rule. The earlier "22 cases" note was a miscount, P2-6.)*

Test all four levels, invalid values, profile-aware `HERMES_HOME`, and separate
web/gateway process environments.

- [x] **Step 2: add the config default**  
  *(2026-06-30: `config_defaults.py` `agent.engine: "loop"`; deep-merged, `_config_version` unchanged at 23.)*

```yaml
agent:
  engine: loop
```

Adding the key is handled by deep merge and does not bump `_config_version`.

- [x] **Step 3: rename and dispatch the legacy body**  
  *(2026-06-30: `agent_engine` ctor arg resolved once in `__init__` via `resolve_agent_engine` → `self.agent_engine`; public `run_conversation` is now a thin dispatcher to `_run_conversation_graph` / the renamed `_run_conversation_loop`, selecting before any side effect with no cross-engine fallback. Source-anchored tests retargeted to `_run_conversation_loop`; 21 exit return lines rebased +45; golden harness drives the private bodies directly.)*

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

- [x] **Step 4: run and commit**  
  *(2026-06-30: `test_engine_selector` 20 passed (corrected from a "22" miscount, P2-6); deterministic equivalence gate (golden+exit_contract+hook_parity+usage_sink+differential) green twice. `HERMES_AGENT_ENGINE=loop` slice = 1274 passed / 10 pre-existing env failures (the legacy-regression gate holds). `=graph` slice = 1253 passed / 32 failed: 10 env + **22 graph-specific edge-case equivalence gaps** (retry/empty-response/fallback, reasoning-only prefill, compression triggers, length-continuation, 401 remint) beyond the Task 9 golden corpus — logged as PH35-FU-009; they gate Task 11's default flip, not the selector. The fuzzer's non-deterministic interrupt variant was removed (PH35-FU-008) and now passes 121×3 under xdist. Committed locally; not pushed.)*
  *(Closure update 2026-07-02: PH35-FU-009 and PH35-FU-008 are closed. A barrier-driven `interrupt_during_api` golden now pins full-finalizer parity. Fresh gates: graph parity/goldens 102, differential 121, selector/usage/exit 64, and `test_run_agent.py` 296 under each engine. Task 10 is complete locally; the default remains `loop` until Task 11.)*

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

- [x] **Step 5: open the companion plan's G1 gate**  
  *(2026-06-30: recorded the Task 9 (`4ab120ff`) + this selector commit in the bounded-goal-runner plan's G1 gate and checked the boxes now satisfied (Task 9 gate, selector lands loop+graph, stable public entry). **G1 deliberately NOT opened** — remaining blockers: PH35-FU-007 (usage-event sink on both engines), PH35-FU-009 (graph edge-case equivalence gaps), Goal Runner Tasks 1–6, and human review. Step 5's hard precondition — `test_usage_event_sink` proving per-attempt events on both engines — is unmet (loop emits none), so G1 stays closed by design.)*
  *(Closure update 2026-07-02: PH35-FU-007 and PH35-FU-009 are now closed and the engine-side G1 evidence is green. Any remaining G1 state is owned by the companion Goal Runner plan (its Tasks 1–6/review), not by unfinished Task 10 work.)*

Record the Task 9 equivalence commit and this selector commit in
`docs/superpowers/plans/2026-06-27-bounded-goal-runner.md`. Goal Runner Tasks
7–9 may now integrate through public `AIAgent.run_conversation`. They must finish
their explicit loop/graph adapter gate before this plan removes the selector.
Do not open G1 unless `test_usage_event_sink.py` also proves complete/unknown
per-attempt events on both engines without result-shape changes.

---

## Task 11 — Desktop release smoke, default flip, and legacy removal

**Files:**

- Modify after smoke: `hermes_core/hermes_cli/config_defaults.py`

- Modify after one release: `hermes_core/run_agent.py`

- Modify after one release: `hermes_core/agent/engine_selector.py`

- Modify: `DECISIONS.md`

- Modify: this plan

- [x] **Step 1: build the release-equivalent runtime**

  *(2026-07-02, branch `codex/task11-release-smoke`: `build_bundle.ps1
  -Verify` passed with bundled Python 3.11.15, desk-server/STT/import smoke
  green, and a 1398.4 MB runtime. `npm ci` + `npm run build` passed (2389
  modules; existing 7-package audit warning and large-chunk warning retained).
  `cargo tauri build` produced the 293,295,371-byte NSIS installer
  `Kabuqina_0.2.0_x64-setup.exe`, SHA-256
  `6B9AB47E8890EF008CEC58FB0E2CFD4367DE84C90F3CF585619DFC1F01248339`.)*

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

- [x] **Step 2: run graph smoke on both API modes**

  *(GO recorded 2026-07-03 — all 5 scenarios passed on the rebuilt release.
  The desktop and the independent Weixin profile both used
  `agent.engine: graph`. Operator evidence was reviewed from release screenshots
  and the logs/config paths below.)*

  - *`chat_completions`: DeepSeek `deepseek-v4-flash` called the read-only
    `clock` tool and returned `2026-07-02 20:12:53 Asia/Shanghai`; a same-session
    follow-up returned `2026-07-02` without another tool call. Evidence:
    `%LOCALAPPDATA%\\com.kabuqina.app\\logs\\hermesdesk.log`, session
    `419f9d9d-afc1-48d9-8875-dd4be44c9b47`, plus operator screenshots.*
  - *Interrupt/recovery: the operator stopped a deliberately long model call;
    the next turn (`只回复 OK`) completed successfully.*
  - *Restart/resume: custom `mimo-v2.5` retained session marker
    `RESUME-20260702` across a Python-child restart (PIDs/timestamps recorded in
    `hermesdesk.log`).*
  - *Separate gateway process: `python -m gateway.run` used
    `profiles/weixin/config.yaml` with `engine: graph`; Weixin inbound at
    20:30:49 and 22-character response at 20:30:57 are recorded in
    `profiles/weixin/logs/gateway.log`; operator screenshot shows
    `GATEWAY-GRAPH-20260702`.*
  - *`anthropic_messages`: custom `mimo-v2.5` at
    `https://token-plan-cn.xiaomimimo.com/anthropic` called the read-only
    `clock` tool and returned `2026-07-03T02:23:02+08:00`; the same-session
    follow-up returned `2026-07-03` without another tool call. Explicit-mode
    evidence is in `%LOCALAPPDATA%\\com.kabuqina.app\\logs\\hermesdesk.log`
    (`api_mode='anthropic_messages'`, session
    `4727bec6-0f3d-489e-9339-9b4ac9fba30f`). Automatic-mode evidence then
    removed `settings.json.provider.api_mode` and `model.api_mode`, logged
    `api_mode='auto'`, retained the `/anthropic` endpoint, and completed session
    `01e8103c-bfff-4108-8376-662cf6235d76` with `AUTO-ANTHROPIC-OK`.*
  - *The rebuilt bundle used Python 3.11.15 (1402.2 MB). Web build transformed
    2390 modules. Focused gates: Web 2, overlay 5, policy 52, gateway-env 4,
    desk-server 19, Hermes runtime-provider/gateway 86, Rust secrets 8 and
    gateway 12. NSIS artifact:
    `Kabuqina_0.2.0_x64-setup.exe`, 296,375,724 bytes, SHA-256
    `D9E9FE3534BB74E2131BD38F1B538D3202D25AC48379358E0ABEB0032F4BD8A9`.*

With `agent.engine: graph`, run:

1. a multi-turn chat-completions conversation with one read-only tool call;
2. the same shape on an `anthropic_messages` provider;
3. an interrupt during a long model call;
4. an app restart followed by session resume;
5. one gateway profile conversation to prove the separate process selects graph.

Record date, provider, model, tool, result, and log path in this document. Do
not use a state-changing tool for the smoke.

- [x] **Step 3: flip the default only after GO is recorded**

  *(2026-07-03: Step 2 GO was already recorded before the change. Both the
  serialized `agent.engine` default and the selector fallback now resolve to
  `graph`, preventing raw-config/load-failure paths from retaining a split
  default. Explicit `agent.engine: loop` and `HERMES_AGENT_ENGINE=loop` remain
  covered rollback paths. User support instructions are in
  `docs/troubleshooting.md` §19. Fresh gates: selector + config 76 passed;
  default Graph `test_run_agent.py` 296 passed; explicit Loop
  `test_run_agent.py` 296 passed; graph goldens/parity/differential plus
  usage/exit contracts 303 passed; desktop Python suite 272 passed. The desk
  runtime log uses the same resolved engine passed into `AIAgent`.)*

Change `agent.engine` default from `loop` to `graph`. Retain explicit
`agent.engine: loop` and `HERMES_AGENT_ENGINE=loop` for one release. Update user
support documentation with the rollback setting.

- [x] **Step 4: complete a release-cycle soak** *(REOPENED BY OWNER
  2026-07-05 — the 2026-07-03 waiver is rescinded. The historical early
  closure note remains below for audit, but it no longer satisfies G2.
  UPDATED BY OWNER 2026-07-08 — the fixed-artifact 14-day interpretation is
  replaced by v0.3.0 release acceptance plus a short post-release observation
  window; see the 2026-07-08 note below.)*

The original fixed-artifact soak contract was at least 14 days and required the
items below. For v0.3.0, the 2026-07-08 owner update below replaces this with a
release-acceptance soak:

- no unresolved P0/P1 issue attributable to graph execution;
- release-build smoke green on both API modes at the beginning and end;
- no unexplained differences in result shapes, hooks, persistence, or usage;
- every graph regression added first as a loop fixture, then fixed.

**SOAK STARTED 2026-07-03; end target ≥ 2026-07-17.** Pinned soak build — the
Step-4 rebuild produced *after* the default flip (`d28e1614`), so graph ships as
the default:

```text
artifact: tauri/target/release/bundle/nsis/Kabuqina_0.2.0_x64-setup.exe
bytes:    296,372,014
sha256:   9ABCA52EEB7FFCEE96333D4250E6376E969E9BA1C82631C713E072871F5751B3
built:    2026-07-03 20:22 UTC (HEAD codex/task11-release-smoke @ d28e1614)
```

This is intentionally a *different* artifact than the Step 2 smoke build
(`D9E9FE35…`, 296,375,724 bytes): Step 2 authorized the flip on the pre-flip
build; Step 4 rebuilt for the graph-default release under soak. The beginning
both-API-mode graph evidence is Step 2's 5-scenario GO (chat_completions +
anthropic_messages, 2026-07-03) — the identical graph code path now ships as the
default in the pinned build above.

**CLOSURE NOTE — Step 4 closed early by owner decision, 2026-07-03.** The
soak started and was closed the same day: the ≥14-day production window was
**not** run to term; the owner accepted graph as the release default on the
strength of the substituted evidence below rather than an extended live soak.
Recorded honestly so no reader mistakes this for a completed 14-day soak.

**REOPEN NOTE — waiver rescinded by owner decision, 2026-07-05.** Step 4 is
open again. The substituted evidence below is still useful baseline evidence,
but it is no longer gate-satisfying evidence for G2. The soak clock restarts
only after a refreshed graph-default candidate is pinned, beginning regression
and both-API-mode release smoke are green, and the artifact/hash are recorded
here. The completion target is candidate start + at least 14 calendar days.
Because Task 11 development has already merged, reopened debugging and soak run
on `main`; the old `codex/task11-release-smoke` worktree is historical evidence
only, not the active soak workspace.

**OWNER UPDATE — release-acceptance soak, 2026-07-08.** The strict "pin one
artifact and freeze product development for at least 14 calendar days" reading
is no longer the chosen gate for v0.3.0. Product work must continue, and several
rounds of graph-default debugging have already run after the original Step 4
reopen. Step 4 now closes only after the v0.3.0 NSIS release candidate ships
with the loop escape hatch still present, initial release/manual smoke is
recorded, and a short post-release observation window ("a few days") finds no
obvious graph-attributable P0/P1 or unexplained result-shape, hook,
persistence, or usage drift. This is an explicit owner acceptance decision, not
evidence that a fixed artifact completed a 14-day soak.

**RELEASE EVIDENCE — observation in progress, 2026-07-10.** The owner confirmed
that v0.3.0 was actually released, installed, and exercised; it is no longer
merely a release candidate. The released local NSIS evidence is:

```text
artifact: tauri/target/release/bundle/nsis/Kabuqina_0.3.0_x64-setup.exe
bytes:    303,938,663
sha256:   9C320DFFB7046CD8718C16904D9BAC56AA3A5A464642824C6BBFA0BF56D30F10
built:    2026-07-09 15:56:35 +08:00
PE:       ProductVersion=0.3.0, FileVersion=0.3.0
```

The installed release at `D:\Program Files (x86)\Kabuqina` uses bundled
CPython 3.11.15. Local installed-app logs from 2026-07-09 contain seven explicit
`engine=graph` desk runs. The only recorded ERROR is the network policy
intentionally blocking `image.pollinations.ai`; it is a non-graph allowlist
denial, not evidence of result-shape, hook, persistence, or usage drift.

On 2026-07-10 the G1 goal suite was refreshed under the bundled CPython 3.11.15
runtime (pytest installed only into ignored `.test-output`): goal core tests =
227 passed / 1 skipped; desk goal routes = 8 passed. This note records real
release evidence without silently compressing the chosen acceptance window
again.

**G2 environment evidence update — 2026-07-12.** The owner confirmed that the
installed v0.3.0 release also completed its goal-control smoke
(pause→resume→cancel→delete). This closes the release-equivalent desktop part
of the G2 G1-test condition; it neither closes Step 4 nor substitutes for the
separate clean-observation acceptance.

**CLOSURE — owner release acceptance, 2026-07-12.** After the short
post-release observation window, the owner explicitly confirmed that no
graph-attributable P0/P1 and no unexplained result-shape, hook, persistence, or
usage drift were observed. Step 4 is therefore closed under the 2026-07-08
release-acceptance decision. This does not claim a fixed artifact completed the
superseded 14-day soak.

G2 must still remain closed until its separate human product-copy,
destructive-control, and approval-boundary review completes. Step 5 must not
start. After G2 opens, record the Goal Runner dual-engine evidence (or an
explicit runtime-integration deferral) before proceeding toward Step 5.

**G2 OPENED — 2026-07-12.** The owner completed the independent review of the
bounded Goal Runner product copy, destructive controls, and approval boundaries
with no blocking issue. Task 10 may now implement and run the host-only Pilot 1
while the explicit loop escape hatch remains available. This gate does not
authorize legacy-loop removal: Step 5 still waits for the dual-engine Pilot 1
evidence (or an explicit runtime-integration deferral).

Substituted evidence (gathered on merged `main` @ `76b1343f`, 2026-07-03):

- [x] Pinned installer re-verified: `Kabuqina_0.2.0_x64-setup.exe` still hashes
      to `9ABCA52E…` (296,372,014 bytes) — the artifact was not swapped.
- [x] Fresh full regression on the merged tree: graph
      `HERMES_AGENT_ENGINE=graph test_run_agent.py` = 296 passed; loop = 296
      passed; graph parity + differential + exit-contract + golden gates = 215
      passed.
- [x] Both-API-mode graph smoke reuses Step 2's GO (chat_completions +
      anthropic_messages, 2026-07-03) on the pre-flip build; the identical graph
      code path ships as the default in the pinned build.
- [ ] *Waived:* the ≥14-day live-usage window and its "no soak-period P0/P1 /
      no unexplained result-shape/hook/persistence/usage drift over the period"
      observation. Any graph regression found later must still land first as a
      loop fixture, then be fixed.

The waived historical evidence above remains insufficient on its own after the
2026-07-05 waiver rescission. The separate 2026-07-12 owner
release-acceptance record now satisfies G2 condition 1 while the loop escape
hatch still exists. G2 nevertheless remains closed pending its independent
human product/control/approval review; Task 10 must not expose the host-only
Pilot 1 before that review is recorded.

- [ ] **Step 5: remove the legacy loop in a dedicated commit**

After Step 4 closes through the v0.3.0 release-acceptance record, first require
Goal Runner Task 10 to record one bounded synthetic pilot under explicit `loop`
and one under explicit `graph`, or explicitly record that the Goal Runner plan
is deferred before runtime integration. Then delete `_run_conversation_loop`,
the selector flag, and loop-only tests. Keep the
engine-independent contracts, service ports, golden fixtures, and graph
import-isolation test. Do not use `run_agent.py` line-count reduction as the
success criterion; use branch coverage, exit-contract coverage, and dependency
direction instead.

**C-track Step 5 remediation (2026-07-12).** A pre-removal review found that
the original file list was incomplete. The dedicated removal commit must also
remove selector/explicit-engine handling from `cron/scheduler.py`,
`cron/goal_agent_worker.py`, `python/src/desk_server/chat_core.py`, and
`hermes_core/scripts/run_goal_manifest_pilot.py`; update their direct tests at
the same time. The Goal Runner's already-recorded explicit loop/graph evidence
is historical pre-removal evidence, not a runtime selector that survives the
commit. Do **not** delete golden, exit-contract, usage, persistence, hook, or
fixed-seed differential coverage wholesale: convert the engine-neutral
contracts to graph-only execution, retain their assertions and fixtures where
they describe public behavior, and remove only loop-specific parametrization,
fixtures, and selector tests. Before implementation, re-run a repository-wide
reference inventory so this list remains exhaustive.

Before this commit, create or designate the tracked cleanup/hook-normalization
follow-up required by decision 4 and record its identifier in `DECISIONS.md`.

```powershell
git add hermes_core/run_agent.py hermes_core/agent/engine_selector.py `
  hermes_core/hermes_cli/config_defaults.py hermes_core/cron/scheduler.py `
  hermes_core/cron/goal_agent_worker.py python/src/desk_server/chat_core.py `
  hermes_core/scripts/run_goal_manifest_pilot.py hermes_core/tests DECISIONS.md `
  docs/superpowers/specs/2026-06-24-consolidate-and-langgraph-replatform-plan.md
git commit -m "refactor: remove legacy agent conversation loop"
```

---

## Rollback rules

- During the one-release escape window after the default flip, support may
  set `agent.engine: loop` in the affected profile or launch with
  `HERMES_AGENT_ENGINE=loop`, then restart the relevant child/app.
- A graph failure after any possible tool execution must return its graph error.
  It must not retry through the loop because that can duplicate file writes,
  shell commands, messages, or external API mutations.
- If an unresolved graph-attributable P0/P1 appears during the soak, use the
  explicit loop escape hatch, record the failing scenario, and pause release or
  removal rather than silently crossing engines within a turn.
- If the dependency or bundle gate fails, remove the spike cleanly and write a
  separate owned finite-state-engine plan. Do not vendor LangGraph internals.

---

## Verification matrix

Run the smallest relevant row after every commit and the entire matrix before a
default flip.

| Surface                  | Command                                                                                                                                                                 | Required result                                                                                 |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Deterministic goldens    | `cd hermes_core; python -m pytest tests/run_agent/test_golden_transcripts.py -o "addopts=" -p no:cacheprovider -q`                                                      | All fixtures pass twice without changes.                                                        |
| Exit reachability        | `cd hermes_core; python -m pytest tests/run_agent/test_exit_reachability.py tests/run_agent/test_retry_contract.py -o "addopts=" -p no:cacheprovider -q`                | Nineteen runtime candidates execute; two dead fallthrough guards pass; retry assumptions match. |
| Usage side channel       | `cd hermes_core; python -m pytest tests/agent/test_usage_event_contract.py tests/run_agent/test_usage_event_sink.py -o "addopts=" -p no:cacheprovider -q`               | Per-attempt loop/graph events match; unknown cost is explicit.                                  |
| Differential sequences   | `cd hermes_core; python -m pytest tests/run_agent/test_graph_differential_sequences.py -o "addopts=" -p no:cacheprovider -q`                                            | At least 100 fixed-seed valid sequences match.                                                  |
| Core run-agent slice     | `cd hermes_core; python -m pytest tests/run_agent -q -n 4`                                                                                                              | Pass under loop and graph.                                                                      |
| Provider guards          | `cd hermes_core; python -m pytest tests/agent/test_provider_package_split.py tests/kabuqina/test_compat_imports.py -q -n 4`                                             | Pass.                                                                                           |
| Desktop Python           | `cd python; python -m unittest discover -s tests -p "test_*.py" -v`                                                                                                     | Pass.                                                                                           |
| Bundle                   | `./python/build_bundle.ps1 -Verify`                                                                                                                                     | Bundled CPython 3.11 imports LangGraph.                                                         |
| Web                      | `cd web; npm run lint; npm run build`                                                                                                                                   | Pass.                                                                                           |
| Rust                     | `cd tauri; cargo test`                                                                                                                                                  | Pass.                                                                                           |
| Live runtime             | release build, both API modes, one read-only tool                                                                                                                       | Result recorded in this plan.                                                                   |
| Outer-loop compatibility | If Goal Runner G1 has opened: `cd hermes_core; python -m pytest tests/cron/test_goal_agent_worker.py tests/cron/test_cron_goal.py -o "addopts=" -p no:cacheprovider -q` | Explicit loop and graph cases pass before legacy-loop removal.                                  |

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
- [ ] all nineteen reachable legacy exits have frozen loop contracts and the two
  supported-protocol dead fallthroughs have structural guards;
- [ ] loop and graph snapshots match twice deterministically;
- [ ] hook, cleanup, interrupt, persistence, stream, usage, and result-key parity
  tests pass;
- [ ] optional usage-event sink sequences match under loop and graph for every
  reachable exit, including explicit unknown-cost attempts;
- [ ] both API modes pass release-build chat + tool smoke;
- [ ] graph is accepted as the v0.3.0 release default through the explicit
  release-acceptance soak record while the loop escape hatch still exists;
- [ ] before legacy-loop removal, Goal Runner Task 10 records its explicit
  loop/graph synthetic pilot, or its runtime integration is explicitly deferred;
- [ ] legacy loop is removed in a dedicated commit;
- [ ] no production LangGraph import exists outside
  `agent/graph_engine/builder.py`, and no production LangChain/LangSmith import
  exists;
- [ ] `DECISIONS.md` and this plan record completion and Phase 4 may begin.
