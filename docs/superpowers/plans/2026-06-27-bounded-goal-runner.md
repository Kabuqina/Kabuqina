# Bounded Goal Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** add a bounded, durable `mode: goal` cron execution mode that performs
one fresh agent iteration per scheduler wake, accepts completion only after an
independent verifier passes, and pauses safely when limits or human judgment are
required.

**Architecture:** build the persistence, transition, verifier, reporting, and
controller modules as engine-neutral pure foundations while Phase 3.5 is in
progress. After Phase 3.5 proves full loop/graph equivalence and lands the engine
selector, connect a thin worker adapter to public `AIAgent.run_conversation`.
After the graph-default release soak, expose creation and rollout surfaces. The
Goal Runner never imports LangGraph, never checkpoints an inner graph, never
edits `run_agent.py`, and never runs both inner engines for one iteration.
Phase 3.5 supplies the engine-neutral usage-event sink that makes early-exit
cost accounting complete without changing the public result shape.

**Tech stack:** Python 3.11, existing Hermes cron scheduler and tool registry,
JSON state with atomic `os.replace`, pytest, Tauri 2/Rust, React/TypeScript, and
the existing desktop delivery bridge.

Date: 2026-06-27

Source design:
`docs/superpowers/specs/2026-06-27-loop-engineering-bounded-goal-runner-design.md`

Companion Phase 3.5 plan:
`docs/superpowers/specs/2026-06-24-consolidate-and-langgraph-replatform-plan.md`

---

## Delivery model: two plans, three gates

This plan and the Phase 3.5 plan are intentionally developed together. They
share an agent runtime but not an implementation hot path.

| Gate | When it opens | Goal Runner work allowed |
|---|---|---|
| **G0 — foundation** | Immediately | Tasks 1–6: state, transitions, verifiers, internal reporting, pure controller, and read-only status projection. |
| **G1 — runtime integration** | Phase 3.5 Tasks 9 and 10 pass: full loop/graph equivalence plus selector | Tasks 7–9: `AIAgent` adapter, cron wiring behind a disabled flag, desktop integration. |
| **G2 — product rollout** | Phase 3.5 Task 11 Step 4 records the 14-day graph-default soak | Tasks 10–11: public creation/control contract, Pilot 1, and staged enablement. |

G0 work may merge while Phase 3.5 remains `NO-GO`; it cannot change existing
cron behavior or become reachable from a due job. G1 work may run goal tests
against both explicitly selected inner engines, but the feature flag remains
off. G2 is the first point at which a non-developer user may create a Goal Task.

### Shared-file serialization

| Ownership | Files | Rule |
|---|---|---|
| Phase 3.5 only | `hermes_core/run_agent.py`, `hermes_core/agent/graph_engine/**`, initial `hermes_core/agent/usage_events.py` integration, LangGraph dependency files, supervisor tracing settings | Goal Runner commits never touch these files. |
| Goal Runner only | `hermes_core/cron/goal_*.py`, `hermes_core/tools/goal_report_tool.py`, goal-specific tests, `tauri/src/cron.rs`, Scheduled Tasks goal presentation | May progress at G0. |
| Serialized | `hermes_core/hermes_cli/config_defaults.py` | Phase 3.5 Task 10 lands `agent.engine` first; Goal Runner Task 8 rebases, then adds `cron.goal_loop`. |
| Serialized | `hermes_core/cron/jobs.py`, `scheduler.py`, `tools/cronjob_tools.py` | Reserved for Goal Runner only after G1; do not mix Phase 3.5 refactors into those commits. |
| Append-only coordination | `DECISIONS.md`, both plan documents | Rebase before editing and preserve the other plan's entries. |

If a task discovers it must edit a file outside its row, stop and update both
plans before continuing. Do not solve a merge collision by duplicating core
semantics in an overlay.

### Non-negotiable invariants

- Each scheduler wake executes at most one worker turn for one Goal Task.
- The scheduler's existing profile lock still provides single-executor behavior.
- State is scoped to the active `HERMES_HOME`; host and gateway profiles never
  inspect or execute each other's goals.
- The worker's self-report is evidence, not authority. Only the controller plus
  verifier may declare `completed`.
- A fresh inner-agent session is created for every iteration. Compact goal state
  is injected explicitly; no inner graph checkpoint is reused.
- No automatic retry occurs after an ambiguous external side effect.
- Missing usage or pricing is never charged as zero; an incomplete cost ledger
  pauses before verification or completion.
- `agent` and `notify` jobs keep their current JSON defaults and scheduler path.
- Intermediate progress is not delivered to chat unless the job requests a
  periodic progress cadence; completion, pause, failure, and cancellation are.

---

## Task 1 — Define goal state, usage summary, and atomic profile-local storage (G0)

**Files:**

- Create: `hermes_core/cron/goal_state.py`
- Create: `hermes_core/cron/goal_usage.py`
- Create: `hermes_core/tests/cron/test_goal_state.py`
- Create: `hermes_core/tests/cron/test_goal_usage.py`

- [x] **Step 1: write failing model, path, and round-trip tests**

The tests must cover valid states, rejected job IDs, missing state, unknown
schema versions, atomic replacement, and recovery when a stale `.tmp` file is
present. Use `monkeypatch` to point `cron.goal_state.get_hermes_home` at
`tmp_path`; never mutate the real profile.

Usage tests cover no-attempt zero cost, multiple known events, included routes,
mixed known/unknown events, missing usage, unknown pricing, exact decimal
addition, and sanitized JSON round-trip. Any unknown event makes the aggregate
amount unavailable rather than contributing zero.

The public contract is:

```python
GoalStatus = Literal[
    "scheduled", "running", "verifying", "completed",
    "paused", "failed", "cancelled",
]

@dataclass(frozen=True)
class GoalLimits:
    max_runs: int
    max_cost_usd: Decimal | None
    max_wall_seconds: int
    deadline: datetime | None
    no_progress_limit: int
    max_infrastructure_failures: int = 3

@dataclass(frozen=True)
class GoalReport:
    status: Literal["progress", "candidate_done", "blocked"]
    summary: str
    artifacts: tuple[str, ...]
    evidence: Mapping[str, JSONValue]
    next_step: str | None
    external_side_effects: tuple[str, ...]

@dataclass(frozen=True)
class GoalDefinition:
    job_id: str
    objective: str
    iteration_prompt: str
    workdir: Path
    verifier_kind: str
    verifier_config: Mapping[str, JSONValue]
    limits: GoalLimits
    enabled_toolsets: tuple[str, ...]
    approval_mode: Literal["ask_before_external_side_effect", "always"]
    progress_delivery_every: int | None

@dataclass(frozen=True)
class GoalRunState:
    schema_version: Literal[1]
    job_id: str
    status: GoalStatus
    iteration: int
    accumulated_cost_usd: Decimal
    cost_accounting: Literal["complete", "incomplete"]
    accumulated_wall_seconds: float
    no_progress_count: int
    infrastructure_failures: int
    last_evidence_hash: str | None
    last_summary: str | None
    last_verifier_outcome: Literal["pass", "fail", "error"] | None
    pause_reason: str | None
    last_error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime
```

`goal_usage.py` defines the engine-independent persisted view of Phase 3.5's
usage-event stream:

```python
@dataclass(frozen=True)
class GoalUsageEvent:
    attempt_index: int
    outcome: Literal["response", "invalid_response", "transport_error"]
    provider: str
    model: str
    api_mode: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    reasoning_tokens: int
    amount_usd: Decimal | None
    cost_status: Literal["actual", "estimated", "included", "unknown"]
    cost_source: str
    pricing_version: str | None

@dataclass(frozen=True)
class GoalUsageSnapshot:
    events: tuple[GoalUsageEvent, ...]
    amount_usd: Decimal | None
    complete: bool
    incomplete_reason: str | None

def summarize_usage_events(
    events: Sequence[GoalUsageEvent],
) -> GoalUsageSnapshot: ...
```

No events means a complete zero-cost iteration because no transport attempt was
made. Every attempted request must have a numeric `actual`, `estimated`, or
`included` event; otherwise the snapshot amount is `None` and `complete=False`.
Never sum known events and silently discard an unknown event.

Persist decimals and datetimes as strings. The file layout is:

```text
<HERMES_HOME>/cron/goal-runs/<job-id>/state.json
<HERMES_HOME>/cron/goal-runs/<job-id>/iterations/000001/report.json
<HERMES_HOME>/cron/goal-runs/<job-id>/iterations/000001/verification.json
<HERMES_HOME>/cron/goal-runs/<job-id>/iterations/000001/transition.json
```

- [x] **Step 2: run the test and confirm it fails for the missing module**

```powershell
cd hermes_core
python -m pytest tests/cron/test_goal_state.py `
  tests/cron/test_goal_usage.py `
  -o "addopts=" -p no:cacheprovider -q
```

- [x] **Step 3: implement validation and atomic writes**

Use `get_hermes_home()` at call time, not module import time. Accept only job IDs
matching `^[a-f0-9]{12}$`; resolve the final directory and confirm its parent is
the resolved `goal-runs` root. Write JSON to `state.json.tmp`, flush and
`os.fsync`, then `os.replace`. A stale temp file is ignored and may be replaced;
it is never treated as committed state.

Iteration record files are immutable: create them with exclusive-create
semantics and
fail if the iteration path already exists. This prevents a retry or recovery
path from rewriting the evidence used for a prior decision.

Required functions:

```python
def goal_run_dir(job_id: str) -> Path: ...
def new_goal_state(job_id: str, *, now: datetime) -> GoalRunState: ...
def load_goal_state(job_id: str) -> GoalRunState | None: ...
def save_goal_state(state: GoalRunState) -> Path: ...
def save_iteration_record(
    job_id: str,
    iteration: int,
    kind: Literal["report", "verification", "transition"],
    payload: Mapping[str, JSONValue],
) -> Path: ...
```

Reject malformed committed JSON and unsupported schema versions with a typed
`GoalStateError`; do not silently reset them.

- [x] **Step 4: verify and commit**

```powershell
cd hermes_core
python -m pytest tests/cron/test_goal_state.py `
  -o "addopts=" -p no:cacheprovider -q
cd ..
git add hermes_core/cron/goal_state.py `
  hermes_core/cron/goal_usage.py `
  hermes_core/tests/cron/test_goal_state.py `
  hermes_core/tests/cron/test_goal_usage.py
git commit -m "feat: add durable goal run state"
```

---

## Task 2 — Implement the pure transition and limit engine (G0)

**Files:**

- Create: `hermes_core/cron/goal_transitions.py`
- Create: `hermes_core/tests/cron/test_goal_transitions.py`

- [x] **Step 1: write a table-driven state-transition test**

Cover these exact outcomes:

| Worker report | Verifier | Limits/evidence | Next status |
|---|---|---|---|
| `progress` | not run | within limits, changed | `scheduled` |
| `candidate_done` | pass | within limits | `completed` |
| `candidate_done` | fail | within limits, changed | `scheduled` |
| `blocked` | not run | any | `paused` |
| any | verifier error | any | `paused` |
| any | run/cost/wall/deadline exceeded | any | `paused` |
| any | usage/cost incomplete | any | `paused` with `cost_unknown` |
| `progress` or failed candidate | unchanged hash reaches limit | any | `paused` |
| infrastructure exception below limit | not run | no ambiguous side effect | `scheduled` |
| infrastructure exception reaches limit | not run | any | `failed` |
| any exception after reported external effect | not run | ambiguous | `paused` |

- [x] **Step 2: implement a side-effect-free reducer**

```python
@dataclass(frozen=True)
class IterationObservation:
    report: GoalReport | None
    verifier: VerifierResult | None
    usage: GoalUsageSnapshot
    wall_seconds: float
    evidence_hash: str | None
    infrastructure_error: str | None
    ambiguous_external_effect: bool

@dataclass(frozen=True)
class GoalTransition:
    previous_status: GoalStatus
    next_state: GoalRunState
    reason: str
    should_deliver: bool

def reduce_iteration(
    state: GoalRunState,
    limits: GoalLimits,
    observation: IterationObservation,
    *,
    now: datetime,
) -> GoalTransition: ...
```

The reducer must not read the clock, filesystem, environment, config, or model.
If `usage.complete` is false, set `cost_accounting="incomplete"`, preserve the
last known accumulated amount, and pause before accepting any verifier result.
Otherwise add `usage.amount_usd` and apply limits. A verifier pass can
complete only a `candidate_done` report. A worker cannot complete by writing
`status=completed` because that value is not in the report schema.

When several pause causes apply, use this stable reason precedence:
`ambiguous_external_effect`, `cost_unknown`, `worker_blocked`, verifier error,
budget/deadline, then no-progress. Persist all applicable diagnostics even
though only the first becomes `pause_reason`.

- [x] **Step 3: prove determinism and invalid-transition rejection**

Call the reducer twice with equal inputs and compare dataclass equality. Reject
attempts to run from `completed`, `cancelled`, or `failed` with
`InvalidGoalTransition`.

- [x] **Step 4: verify and commit**

```powershell
cd hermes_core
python -m pytest tests/cron/test_goal_transitions.py `
  -o "addopts=" -p no:cacheprovider -q
cd ..
git add hermes_core/cron/goal_transitions.py `
  hermes_core/tests/cron/test_goal_transitions.py
git commit -m "feat: add bounded goal transitions"
```

---

## Task 3 — Add deterministic verifier registry (G0)

**Files:**

- Create: `hermes_core/cron/goal_verifiers.py`
- Create: `hermes_core/tests/cron/test_goal_verifiers.py`

- [x] **Step 1: test path confinement and verifier results**

Every artifact path is relative to the configured absolute `workdir`. Reject
absolute paths, `..` traversal, symlink escapes, missing workdirs, and files
outside the root. Tests run on Windows and must compare resolved `Path` objects,
not slash-formatted strings.

- [x] **Step 2: define the verifier port and registry**

```python
@dataclass(frozen=True)
class VerificationContext:
    workdir: Path
    report: GoalReport
    config: Mapping[str, JSONValue]
    previous_evidence_hash: str | None

@dataclass(frozen=True)
class VerifierResult:
    outcome: Literal["pass", "fail", "error"]
    summary: str
    evidence: Mapping[str, JSONValue]

Verifier = Callable[[VerificationContext], VerifierResult]

def verify(kind: str, context: VerificationContext) -> VerifierResult: ...
```

Unknown verifier kinds return `error` and pause the goal; they never fall back to
an LLM judgment.

- [x] **Step 3: implement the Pilot 1 verifier set**

Implement and test:

- `artifact_exists`: all configured relative files exist and are regular files;
- `manifest_complete`: every supported file under configured roots has exactly
  one normalized manifest record, the pilot's fixed required fields and value
  types are valid, and no out-of-root record exists;
- `content_hash_changed`: canonical evidence hash differs from the previous one.

The desktop requirements currently receive `jsonschema` only as a transitive
dependency of `mcp`; neither the core nor desktop requirements declare the
verifier dependency directly. Do not touch dependency files during G0, rely on
that transitive accident, or write a partial JSON Schema engine. Generic
`json_schema` remains reserved but unsupported until a separate post-Phase-3.5
dependency gate adds and bundles an explicit pin.
`manifest_complete` is a purpose-built verifier and must sort normalized
relative paths before hashing so filesystem enumeration order cannot change the
result.

Do not implement `test_command` or `llm_rubric` in this task. They are outside
Pilot 1 and require separate power-user and evaluator-risk decisions.

- [x] **Step 4: verify and commit**

```powershell
cd hermes_core
python -m pytest tests/cron/test_goal_verifiers.py `
  -o "addopts=" -p no:cacheprovider -q
cd ..
git add hermes_core/cron/goal_verifiers.py `
  hermes_core/tests/cron/test_goal_verifiers.py
git commit -m "feat: add deterministic goal verifiers"
```

---

## Task 4 — Add an iteration-scoped internal report tool (G0)

**Files:**

- Create: `hermes_core/cron/goal_report.py`
- Create: `hermes_core/tools/goal_report_tool.py`
- Create: `hermes_core/tests/cron/test_goal_report.py`

- [x] **Step 1: write isolation and schema tests**

Prove that the tool is unavailable without an active goal-report scope, accepts
exactly one valid report inside a scope, rejects unknown keys and oversized
fields, and keeps independently created scopes isolated across copied contexts
and parallel threads.

- [x] **Step 2: implement the scoped report collector**

Use a `ContextVar[GoalReportCollector | None]`. The context manager returns a
collector and always resets its token:

```python
@contextmanager
def goal_report_scope(job_id: str, iteration: int) -> Iterator[GoalReportCollector]:
    collector = GoalReportCollector(job_id=job_id, iteration=iteration)
    token = _active_goal_report.set(collector)
    try:
        yield collector
    finally:
        _active_goal_report.reset(token)
```

The collector rejects a second report. Cap summaries and next steps at 4,000
characters, artifact entries at 200, and serialized evidence at 64 KiB. Secret
redaction remains the caller's responsibility; the tool schema explicitly tells
the worker never to include secrets or raw document bodies.

- [x] **Step 3: register `goal_report` in an internal toolset**

Register through the existing `ToolRegistry` as toolset `goal_internal`. Its
module-level registration is discovered by the existing built-in tool scan; no
bootstrap import is added. Do not use the scope in `check_fn`, because registry
availability checks are TTL-cached. The handler itself requires an active scope
and returns a structured tool error outside one. It returns the normal registry
JSON string and never writes goal state directly.

Do not add `goal_internal` to default toolsets or static core-tool lists. The
Goal Agent adapter in Task 7 enables it explicitly for one worker turn.

- [x] **Step 4: verify and commit**

```powershell
cd hermes_core
python -m pytest tests/cron/test_goal_report.py `
  -o "addopts=" -p no:cacheprovider -q
cd ..
git add hermes_core/cron/goal_report.py `
  hermes_core/tools/goal_report_tool.py `
  hermes_core/tests/cron/test_goal_report.py
git commit -m "feat: add scoped goal report tool"
```

---

## Task 5 — Build the engine-neutral one-iteration controller (G0)

**Files:**

- Create: `hermes_core/cron/goal_runner.py`
- Create: `hermes_core/tests/cron/test_goal_runner.py`

- [x] **Step 1: define injected ports and fake-driven tests**

```python
class GoalWorker(Protocol):
    def run_iteration(
        self,
        definition: GoalDefinition,
        state: GoalRunState,
    ) -> WorkerObservation: ...

class GoalVerifier(Protocol):
    def verify(
        self,
        definition: GoalDefinition,
        report: GoalReport,
        previous_evidence_hash: str | None,
    ) -> VerifierResult: ...

@dataclass(frozen=True)
class GoalIterationResult:
    transition: GoalTransition
    full_output: str
    delivery_text: str
    evidence_path: Path

def run_goal_iteration(
    definition: GoalDefinition,
    *,
    worker: GoalWorker,
    verifier: GoalVerifier,
    now: datetime,
) -> GoalIterationResult: ...
```

Tests use fakes only. They cover initialization, one worker call, verifier only
for `candidate_done`, progress reschedule, verified completion, pause, persistence
before return, restart from committed state, and no second iteration in one call.

- [x] **Step 2: implement orchestration in this exact order**

1. Load or initialize state.
2. Reject terminal/paused states. If committed state is `running` or
   `verifying`, persist a `paused` recovery transition and return without a
   worker call; never guess whether the prior turn had side effects.
3. Persist `running` before invoking the worker.
4. Invoke the worker exactly once.
5. Persist the sanitized report and usage as immutable `report.json`.
6. If the usage snapshot is incomplete, persist a `cost_unknown` pause and do
   not run the verifier.
7. Persist `verifying` before a candidate verifier call.
8. Run the verifier, persist `verification.json`, then canonicalize and hash the
   verifier inputs and outputs.
9. Reduce the observation, persist `transition.json`, then persist next state.
10. Return output and delivery intent; never call a delivery adapter itself.

The progress fingerprint is the canonical JSON hash of only:

```json
{
  "artifacts": [{"path": "learning-materials.json", "sha256": "0000000000000000000000000000000000000000000000000000000000000000"}],
  "verifier": {"outcome": "pass", "evidence": {"manifest_complete": true}}
}
```

Sort artifacts by normalized path and canonicalize verifier evidence keys. Do
not include worker `summary`, `next_step`, self-reported `evidence`, other model
text, timestamps, iteration, usage, or cost. Tests vary every excluded field
while keeping artifacts/verifier output fixed and assert the fingerprint is
unchanged; changing one artifact digest must change it.

If the process exits between steps 3 and 8, the next wake sees `running` or
`verifying` and pauses for recovery review. It must not replay automatically.

- [x] **Step 3: add restart and fault-injection tests**

Inject failures before and after every state write. Assert that a committed
terminal state is never overwritten, evidence is immutable per iteration, and a
missing report becomes a controlled pause rather than guessed progress.

- [x] **Step 4: run the G0 core gate and commit**

```powershell
cd hermes_core
python -m pytest tests/cron/test_goal_state.py `
  tests/cron/test_goal_usage.py `
  tests/cron/test_goal_transitions.py `
  tests/cron/test_goal_verifiers.py `
  tests/cron/test_goal_report.py `
  tests/cron/test_goal_runner.py `
  -o "addopts=" -p no:cacheprovider -q
cd ..
git add hermes_core/cron/goal_runner.py `
  hermes_core/tests/cron/test_goal_runner.py
git commit -m "feat: add engine-neutral bounded goal controller"
```

---

## Task 6 — Add read-only host-profile status projection (G0)

**Files:**

- Modify: `tauri/src/cron.rs`
- Modify: `web/src/advanced/pages/ScheduledTasks.tsx`
- Modify: `web/src/locales/strings.ts`
- Create: `web/src/advanced/scheduledTasksGoalUx.test.mjs`

- [x] **Step 1: add Rust deserialization and sanitization tests**

Extend `CronJobEntry` with optional fields only:

```rust
pub mode: Option<String>,
pub goal_status: Option<String>,
pub goal_iteration: Option<u64>,
pub goal_cost_usd: Option<String>,
pub goal_cost_accounting: Option<String>,
pub goal_pause_reason: Option<String>,
pub goal_updated_at: Option<String>,
```

For `mode: goal`, `cmd_cron_list` may read only
`<host HERMES_HOME>/cron/goal-runs/<id>/state.json`. It must not enumerate
gateway profile directories and must not expose evidence, prompts, or error
stacks. Malformed state produces `goal_status: "state_error"` without failing
the entire task list.

- [x] **Step 2: render status without adding creation or execution controls**

Show a “持续目标 / Goal Task” badge, iteration, accumulated cost, updated time,
cost-accounting completeness, and sanitized pause reason. Never render an
incomplete amount as `$0`. Existing `agent` and `notify` cards stay unchanged;
goal cards are status-only at G0 and do not call the legacy raw-file toggle or
delete commands. No create form is added at G0. The view is naturally dormant
until a developer fixture or later runtime wiring creates a goal job.

- [x] **Step 3: verify legacy and goal rendering**

```powershell
cd tauri
cargo test cron
cd ..\web
node --test src/advanced/scheduledTasksGoalUx.test.mjs
npm run lint
npm run build
cd ..
```

- [x] **Step 4: commit**

```powershell
git add tauri/src/cron.rs `
  web/src/advanced/pages/ScheduledTasks.tsx `
  web/src/advanced/scheduledTasksGoalUx.test.mjs `
  web/src/locales/strings.ts
git commit -m "feat: show bounded goal status in scheduled tasks"
```

---

## G1 review gate — Phase 3.5 runtime contract

Do not start Task 7 until all boxes are checked in both plans:

- [x] Phase 3.5 Task 9 passes the deterministic loop/graph equivalence gate
  twice and its broader run-agent suite passes. *(2026-06-29, commit `4ab120ff`.)*
- [x] Phase 3.5 Task 10 lands the explicit constructor/environment/config
  selector and proves both `loop` and `graph` independently. *(2026-06-30 — selector + dispatcher; loop and graph are each independently selectable and exercised. NOTE: routing the full loop unit suite through graph surfaced 22 edge-case equivalence gaps, PH35-FU-009 — these gate the Task 11 default flip but not selectability.)*
- [x] Phase 3.5's usage-event sink records normal and early-exit transport
  attempts before branching, without changing legacy result dictionaries.
  *(2026-07-01 — PH35-FU-007 resolved: the loop now emits transport_error,
  invalid_response (gated on a None response), and compression (413 +
  general context-overflow) events via the shared `_record_usage_attempt`,
  matching the graph's per-attempt sequence on 5 error fixtures. No-op without a
  sink, so legacy result dicts are untouched. Verified: differential 121, loop
  suite 294, usage/compression/exit 29.)*
- [x] `AIAgent.run_conversation` remains the stable public entry point.
  *(2026-06-30 — now a thin dispatcher; signature unchanged.)*
- [x] Goal Runner Tasks 1–6 pass and introduce no imports from
  `agent.graph_engine` or `langgraph`. *(2026-07-02 — goal cron tests 107 passed;
  full `tests/cron` 423 passed / 2 skipped, only the known Windows env failures
  (chmod/`~`-expansion); `grep graph_engine|langgraph|GraphEngine` over
  `cron/goal_*.py` is empty — isolation contract holds.)*
- [x] The integration diff and file ownership are reviewed by a person.
  *(2026-07-02 — G1 runtime-contract hardening `7326c333` "fail closed on
  incomplete iteration evidence" + `3ed4ae9c` "require timezone-aware persisted
  timestamps" reviewed and signed off, fast-forwarded onto `main`.)*

**G1 is OPEN (2026-07-02).** All substantive blockers cleared: PH35-FU-007
(2026-07-01) plus PH35-FU-008 and PH35-FU-009 (both closed 2026-07-02 on the
Phase 3.5 plan — the earlier "needed for confidence" caveat no longer applies),
Goal Runner Tasks 1–6, and human review. Task 7 may start.

Phase 3.5 commits to date:

```text
Task 9 equivalence: 4ab120ff (2026-06-29)
Task 10 selector:   97ef7ac9 (2026-06-30)
G1 opened: 3ed4ae9c at 2026-07-02; reviewed by ladylydia
```

---

## Task 7 — Connect a thin `AIAgent` worker adapter (G1)

**Files:**

- Create: `hermes_core/cron/goal_agent_worker.py`
- Create: `hermes_core/tests/cron/test_goal_agent_worker.py`
- ~~Modify: `hermes_core/cron/goal_runner.py`~~ *(not modified — `GoalAgentWorker`
  satisfies the existing `GoalWorker` protocol by injection; importing it into
  `goal_runner` would create a `goal_runner ↔ goal_agent_worker` cycle. The
  construction wiring lands in Task 8's scheduler routing.)*

- [x] **Step 1: write adapter tests against a fake `AIAgent` factory**
  *(2026-07-02, `990320d5` — `tests/cron/test_goal_agent_worker.py`, 20 cases,
  loop/graph parametrized: one agent + one `run_conversation` per iteration,
  fresh session id, engine propagation, report-scope lifetime, complete/unpriced
  usage propagation, missing-report → `report=None`, pre-entry exception = safe
  infra, post-entry exception = `ambiguous_external_effect=True`.)*

Assert one agent instance and one `run_conversation` call per iteration, a fresh
session ID, explicit selected engine propagation, exact report-scope lifetime,
complete usage-event propagation, and rejection when no valid `goal_report` is
submitted. Run each case with
`agent_engine="loop"` and `agent_engine="graph"`; never run both for one case.
An exception before entering `run_conversation` may be classified as a safe
infrastructure failure. Any exception after entry is conservatively marked
`ambiguous_external_effect=True` and pauses; the adapter never infers from a
missing report that no tool ran.

Usage cases include a normal numeric result, thinking-budget/truncation exits
whose result dictionaries omit cost, missing provider usage, unknown pricing,
fallback route changes, compression, and max-iteration summary. The injected
ledger—not result-key presence—must account for every attempt; any gap yields
`complete=False`.

- [x] **Step 2: build bounded context from durable state**
  *(2026-07-02 — `_build_system_message` carries objective, current iteration,
  remaining runs/cost/deadline, compact `last_summary` + evidence fingerprint,
  workdir, verifier kind, and the report-tool schema; excludes raw transcripts
  and evidence bodies. User message = `definition.iteration_prompt`.)*

The system message includes the objective, current iteration, compact previous
summary, last evidence hash, remaining limits, allowed workdir, verifier
description, and report schema. It excludes prior raw transcripts and evidence
bodies. The user message is the job's per-iteration prompt.

- [x] **Step 3: instantiate the agent through its public API**
  *(2026-07-02 — lazy `from run_agent import AIAgent` inside the default factory
  only; injected factory for tests; calls public `run_conversation`. Fresh
  `UsageLedger` passed via `usage_sink=`, snapshot converted to
  `GoalUsageSnapshot` after return; any unpriced attempt → `complete=False`.
  enabled_toolsets = job allowlist ∪ `goal_internal` (dedup, no broadening);
  profile-policy intersection stays inside `AIAgent`.)*

`GoalAgentWorker` imports `AIAgent` lazily from `run_agent`, accepts an injected
factory for tests, and calls public `run_conversation`. It never imports or calls
`_run_conversation_loop`, `_run_conversation_graph`, `GraphEngine`, or a graph
node.

Construct a fresh Phase 3.5 `UsageLedger`, pass it through the public optional
`AIAgent(..., usage_sink=ledger)` argument, and convert its snapshot to
`GoalUsageSnapshot` after `run_conversation` returns. Do not infer cost from
missing early-exit result keys or read aggregate session DB rows. If any event is
unknown, return an incomplete usage snapshot so the controller pauses.

The enabled toolsets are the job's allowlist intersected with the profile's
policy, plus `goal_internal`. Pilot 1 enables only `file` and `goal_internal`;
skills are preloaded context, not an expandable runtime toolset. It excludes
network/browser, messaging, `cronjob`, `terminal`, `code_execution`, `moa`,
`delegation`, vision, image generation, and TTS. The adapter cannot broaden a
desktop policy allowlist. More generally, a toolset that can incur a separate
model/API charge remains unavailable to Goal Tasks until it emits complete cost
events into the iteration ledger.

- [x] **Step 4: verify both selected engines and commit**
  *(2026-07-02, `990320d5` — adapter suite 20 passed (engine propagation
  verified for both `loop` and `graph` via the injected factory); Step 4 suite
  `test_goal_agent_worker + test_goal_runner + test_goal_state + test_goal_report`
  = 130 passed. Real-engine end-to-end deferred to Task 8+ integration. Isolation
  grep over `goal_agent_worker.py` clean.)*

```powershell
cd hermes_core
python -m pytest tests/cron/test_goal_agent_worker.py `
  tests/cron/test_goal_runner.py `
  -o "addopts=" -p no:cacheprovider -q
cd ..
git add hermes_core/cron/goal_agent_worker.py `
  hermes_core/cron/goal_runner.py `
  hermes_core/tests/cron/test_goal_agent_worker.py
git commit -m "feat: connect goal iterations to the public agent API"
```

---

## Task 8 — Add `mode: goal` and scheduler routing behind a disabled flag (G1)

**Files:**

- Modify: `hermes_core/hermes_cli/config_defaults.py`
- Create: `hermes_core/cron/scheduler_lock.py`
- Modify: `hermes_core/cron/jobs.py`
- Modify: `hermes_core/cron/scheduler.py`
- Modify: `hermes_core/tools/cronjob_tools.py`
- Create: `hermes_core/tests/cron/test_cron_goal.py`
- Create: `hermes_core/tests/cron/test_scheduler_lock.py`
- Modify: `DECISIONS.md`

- [ ] **Step 1: rebase after Phase 3.5 Task 10 and add the disabled default**

Add under the existing `cron` section:

```yaml
cron:
  goal_loop:
    enabled: false
```

The config version does not change. `false` means no due goal can invoke a model;
the scheduler pauses it with `feature_disabled` and preserves state for
inspection. Do not use a top-level `goal_loop` key. Because every host/gateway
profile has its own `HERMES_HOME` and config, Pilot 1 enables only the host
profile; gateway profile configs remain false.

- [ ] **Step 2: characterize legacy modes before modifying normalization**

Extend tests to prove missing/unknown mode still normalizes to `agent`, aliases
still normalize to `notify`, and existing serialized job fixtures are unchanged.
Then allow exact `goal` as a third mode.

Add goal-only fields to `create_job` with `None` defaults: `goal`, `verifier`,
`limits`, `approval_mode`, and `progress_delivery_every`. Reject `goal` without
an absolute confined workdir, non-empty objective, known deterministic verifier,
and explicit finite limits. Existing modes ignore no unknown goal fields: they
must reject them so a typo cannot silently create an ordinary agent job.

- [ ] **Step 3: route one due wake through the controller**

First extract the existing cross-platform `.tick.lock` acquisition into
`scheduler_lock.py` and pin its nonblocking/single-owner behavior without
changing lock scope: `tick()` still holds it from due-job selection through all
execution, delivery, and marking. The later control service uses the same helper
and fails with a busy result instead of racing an active iteration.

Extend `_job_execution_mode` to return `goal`. Add `_run_goal_job` beside
`_run_notify_job`. It loads config, checks the feature/profile gate, constructs
the definition and adapter, and executes exactly one controller iteration.

Keep the public `run_job(job) -> tuple[bool, str, str, str | None]` contract
unchanged for legacy `agent` and `notify` callers. Branch inside `tick()`'s
private `_process_job` so the goal transition remains available for marking:

The current `tick()` calls `advance_next_run` before execution and
`mark_job_run` afterward. Preserve advance-before-run at-most-once behavior, but
branch final bookkeeping:

```python
mode = _job_execution_mode(job)
goal_result = None
if mode == "goal":
    goal_result = _run_goal_job(job)
    success = goal_result.transition.next_state.status != "failed"
    output = goal_result.full_output
    final_response = goal_result.delivery_text
    error = goal_result.transition.next_state.last_error
else:
    success, output, final_response, error = run_job(job)

# Existing save and delivery pipeline remains here.

if goal_result is not None:
    mark_goal_job_run(
        job["id"],
        transition=goal_result.transition,
        delivery_error=delivery_error,
    )
else:
    mark_job_run(job["id"], success, error, delivery_error=delivery_error)
```

`mark_goal_job_run` updates last-run metadata and mirrors terminal/pause status
onto the job record. It does not increment ordinary `repeat.completed`, compute a
second next run, or delete the job. `completed`, `paused`, `failed`, and
`cancelled` disable future wakes; `scheduled` keeps the next time already
advanced by `tick()`.

The `_process_job` exception path also branches by mode. A catastrophic goal
exception calls `mark_goal_job_crash`, disables future wakes, records a sanitized
error on the job mirror, and leaves committed goal state/evidence untouched for
recovery review. It must not call ordinary `mark_job_run`.

- [ ] **Step 4: keep the public tool contract hidden**

Core `create_job` may accept the new mode for internal tests, but the registered
`cronjob` tool schema and handler reject `mode: goal` while G2 is closed. This
prevents an agent or user from creating live Goal Tasks during the inner-engine
soak.

- [ ] **Step 5: prove scheduler and legacy behavior**

Tests cover flag off in a gateway-shaped profile, flag on in the host-shaped
profile, one call/wake, state reschedule, terminal disable,
pause/resume/cancel bookkeeping, no double schedule computation,
delivery only on configured transitions, and unchanged `agent`/`notify` paths.

```powershell
cd hermes_core
python -m pytest tests/cron/test_cron_goal.py `
  tests/cron/test_cron_notify.py tests/cron/test_jobs.py `
  tests/cron/test_scheduler.py tests/cron/test_scheduler_lock.py `
  -o "addopts=" -p no:cacheprovider -q
cd ..
git add hermes_core/hermes_cli/config_defaults.py `
  hermes_core/cron/jobs.py hermes_core/cron/scheduler.py `
  hermes_core/cron/scheduler_lock.py `
  hermes_core/tools/cronjob_tools.py `
  hermes_core/tests/cron/test_cron_goal.py `
  hermes_core/tests/cron/test_scheduler_lock.py DECISIONS.md
git commit -m "feat: route disabled-by-default goal cron jobs"
```

---

## Task 9 — Integrate desktop delivery, controls, and profile boundaries (G1)

**Files:**

- Create: `hermes_core/cron/goal_controls.py`
- Create: `hermes_core/tests/cron/test_goal_controls.py`
- Modify: `python/overlays/cron_desktop_delivery.py`
- Create: `python/src/desk_server/goal_routes.py`
- Modify: `python/src/desk_server/app.py`
- Create: `python/tests/test_goal_desktop_delivery.py`
- Create: `python/tests/test_goal_routes.py`
- Create: `python/tests/test_goal_profile_isolation.py`
- Modify: `tauri/src/cron.rs`
- Modify: `tauri/src/lib.rs`
- Modify: `web/src/advanced/pages/ScheduledTasks.tsx`

- [ ] **Step 1: characterize existing desktop delivery exactly-once behavior**

Write tests before changing the overlay. A normal intermediate iteration produces
no toast or chat item. Completion, pause, failure, and cancellation produce one
sanitized delivery. A configured progress cadence may deliver only at its exact
iteration multiple.

- [ ] **Step 2: prove per-profile isolation with process-shaped fixtures**

Create separate host and gateway `HERMES_HOME` trees containing the same job ID
with different state. Each scheduler instance must load, lock, update, and project
only its active home. Pilot 1 rejects gateway-profile execution even if a goal
job file is copied there.

- [ ] **Step 3: implement crash-safe core control transitions**

Add `pause_goal`, `resume_goal`, `cancel_goal`, and `delete_goal` in
`goal_controls.py`. State is authoritative and the cron job record is its
scheduling mirror. Use this write order so any interrupted operation fails
closed:

- pause/cancel: persist goal state first, then disable the cron job;
- resume: enable the cron job and compute its next wake first, then persist
  `scheduled` goal state;
- scheduler execution requires both an enabled job and runnable goal state.
- delete is allowed only after `completed`, `failed`, or `cancelled`; it removes
  the job record and deliberately retains the goal-run directory for inspection.

Fault-injection tests stop between the two writes. A partial pause/cancel cannot
run; a partial resume remains blocked by paused goal state. Retrying the same
control is idempotent and repairs the mirror.

Every control acquires the same nonblocking profile scheduler lock extracted in
Task 8. If an iteration or another tick owns it, return `GoalControlBusy`; the
desk route maps that to HTTP 409 and performs no write. This deliberately
cancels future iterations, not an already executing agent turn.

- [ ] **Step 4: proxy pause, resume, cancel, and delete through the core**

Add authenticated desk-server routes that delegate only to the core control
service:

```text
POST /api/desk/goals/{job_id}/pause
POST /api/desk/goals/{job_id}/resume
POST /api/desk/goals/{job_id}/cancel
DELETE /api/desk/goals/{job_id}
```

Validate the host-profile job ID, return sanitized state, and reuse the existing
desk authentication middleware. Add async Tauri commands in `cron.rs` that proxy
to these routes using the same loopback client/auth pattern as `chat.rs`.
Register them in `lib.rs`; React invokes the Tauri commands and never calls the
Python port directly.

The controls behave as follows:

- pause records a human action and disables future wakes;
- resume accepts only non-terminal paused state and schedules the next wake
  without running immediately;
- delete requires destructive confirmation, refuses an active goal, removes the
  job through the core service, and retains goal-run evidence until an explicit
  later retention decision;
- cancellation is distinct from deletion and retains the cancelled job and
  state for inspection.

Do not reuse the current raw-file `cmd_cron_toggle` for Goal Tasks; it writes a
legacy `paused` field that is not the core goal-state contract. Ordinary cron
jobs keep their existing command until that separate compatibility issue is
planned. Rust and React contain no mutable goal-state transition logic.

- [ ] **Step 5: run the G1 integration gate and commit**

```powershell
cd python
python -m unittest discover -s tests -p "test_goal_*.py" -v
cd ..\hermes_core
python -m pytest tests/cron -q -n 4
cd ..\tauri
cargo test cron
cd ..\web
npm run lint
npm run build
cd ..
git add python/overlays/cron_desktop_delivery.py `
  python/tests/test_goal_desktop_delivery.py `
  python/tests/test_goal_routes.py `
  python/tests/test_goal_profile_isolation.py `
  python/src/desk_server/goal_routes.py python/src/desk_server/app.py `
  hermes_core/cron/goal_controls.py `
  hermes_core/tests/cron/test_goal_controls.py `
  tauri/src/cron.rs tauri/src/lib.rs `
  web/src/advanced/pages/ScheduledTasks.tsx
git commit -m "feat: integrate bounded goals with desktop profiles"
```

---

## G2 review gate — product exposure

Do not expose `mode: goal` until:

- [ ] Phase 3.5 Task 11 records a successful 14-day graph-default release soak.
- [ ] The loop escape hatch still works, or its planned removal has not yet
  landed; Goal Runner passes with explicit `loop` and `graph` before removal.
- [ ] G1 tests pass in bundled CPython 3.11 and a release-equivalent desktop.
- [ ] Pilot 1's verifier and limits are frozen in fixtures.
- [ ] Product copy, destructive controls, and approval boundaries receive human
  review.

Record the Phase 3.5 soak evidence here:

```text
G2 opened: __________ at __________; reviewed by __________
```

---

## Task 10 — Expose the bounded creation/control contract and run Pilot 1 (G2)

**Files:**

- Modify: `hermes_core/tools/cronjob_tools.py`
- Modify: `hermes_core/tests/cron/test_cron_goal.py`
- Modify: `hermes_core/tests/cron/test_goal_verifiers.py`
- Modify: `python/src/desk_server/goal_routes.py`
- Modify: `python/tests/test_goal_routes.py`
- Modify: `tauri/src/cron.rs`
- Modify: `tauri/src/lib.rs`
- Modify: `web/src/advanced/pages/ScheduledTasks.tsx`
- Modify: `web/src/locales/strings.ts`
- Modify: `web/src/advanced/scheduledTasksGoalUx.test.mjs`
- Create: `hermes_core/tests/cron/fixtures/goal_manifest_pilot/`
- Modify: `docs/superpowers/specs/2026-06-27-loop-engineering-bounded-goal-runner-design.md`

- [ ] **Step 1: expose a strict `mode: goal` tool schema**

The tool requires objective, per-iteration prompt, schedule, workdir, one known
verifier config, finite limits, and delivery preference. It refuses nested Goal
Task creation while `goal_internal` is active and refuses Goal Tasks in gateway
profiles for Pilot 1. Creation remains an approval-requiring action under the
existing messaging/cron policy when requested by an agent.
Goal pause, resume, cancel, and delete actions delegate to `goal_controls.py`;
the tool handler does not mutate goal state or job JSON itself.

- [ ] **Step 2: add UI creation only after the core contract is stable**

Add `POST /api/desk/goals` to the authenticated route module. It delegates to
core `create_job` validation, returns the sanitized created record, and is
proxied by a new async Tauri command; the webview never receives the Python port
or auth token. The form exposes Pilot 1's `manifest_complete` template,
conservative limits, and a clear statement that one iteration runs per wake.
Advanced arbitrary verifier JSON, terminal verifiers, and LLM-only completion
are not exposed. UI creation is an explicit confirmed user action;
pause/resume/cancel controls display their consequences before confirmation.

- [ ] **Step 3: run the read-mostly workspace inventory pilot**

Before Phase 3.5 removes its escape hatch, complete the synthetic workspace once
with explicit `agent_engine="loop"` and once with explicit
`agent_engine="graph"`; compare controller transitions, verifier results, and
sanitized artifacts, not raw inner transcripts. Then use a human-selected
disposable local workspace. Enforce:

- host profile only;
- file read plus one manifest write;
- only `file` and `goal_internal` runtime toolsets; no network/browser,
  messaging, terminal, code execution, subagents, vision, image generation, TTS,
  or other separately billed tool;
- maximum 40 runs, four hours, and a configured cost cap;
- restart once while `scheduled`, once after `running` recovery pause, and once
  after a failed verifier;
- deterministic manifest verification before completion.

Record each pilot run's state transitions and verification command in the design
document. Never record prompts, document contents, or secrets.

- [ ] **Step 4: verify and commit**

```powershell
cd hermes_core
python -m pytest tests/cron/test_cron_goal.py `
  tests/cron/test_goal_verifiers.py `
  -o "addopts=" -p no:cacheprovider -q
cd ..\web
node --test src/advanced/scheduledTasksGoalUx.test.mjs
npm run lint
npm run build
cd ..
git add hermes_core/tools/cronjob_tools.py `
  hermes_core/tests/cron/test_cron_goal.py `
  hermes_core/tests/cron/test_goal_verifiers.py `
  hermes_core/tests/cron/fixtures/goal_manifest_pilot `
  python/src/desk_server/goal_routes.py python/tests/test_goal_routes.py `
  tauri/src/cron.rs tauri/src/lib.rs `
  web/src/advanced/pages/ScheduledTasks.tsx `
  web/src/advanced/scheduledTasksGoalUx.test.mjs `
  web/src/locales/strings.ts `
  docs/superpowers/specs/2026-06-27-loop-engineering-bounded-goal-runner-design.md
git commit -m "feat: expose the bounded goal pilot"
```

---

## Task 11 — Release hardening and staged enablement (G2)

**Files:**

- Modify: `hermes_core/hermes_cli/config_defaults.py`
- Modify: `DECISIONS.md`
- Modify: this plan
- Modify: `docs/architecture.md`
- Modify: `docs/safety.md`
- Modify: `docs/troubleshooting.md`

- [ ] **Step 1: satisfy the pilot exit criteria**

Complete 30 consecutive correct completions or pauses, at least five process/app
restarts, zero out-of-workspace writes, zero secret leakage, zero duplicate
non-idempotent effects, exact per-attempt usage/cost accumulation, explicit
`cost_unknown` pauses for incomplete ledgers, and no false completion found by
manual review.

- [ ] **Step 2: run the full regression and release-build smoke**

```powershell
cd hermes_core
python -m pytest tests/cron tests/run_agent -q -n 4
cd ..\python
python -m unittest discover -s tests -p "test_*.py" -v
cd ..
./python/build_bundle.ps1 -Verify
cd web
npm ci
npm run lint
npm run build
cd ..\tauri
cargo test
cargo tauri build
cd ..
```

In the release build, run one legacy `notify`, one legacy `agent`, and Pilot 1.
Restart the app mid-goal and verify exact state recovery. Test host and one
gateway profile and confirm the gateway cannot see or execute the host pilot.

- [ ] **Step 3: choose the enablement level explicitly**

The default remains `cron.goal_loop.enabled: false` until the pilot exit criteria
and release smoke are recorded. Enable it only in the host profile and only in a
dedicated decision commit. Gateway profile configs remain false for the first
release. Gateway support is a separate later plan, not an automatic consequence
of enabling the host feature.

- [ ] **Step 4: document rollback and commit**

Disabling the flag stops new iterations, preserves state/evidence, and keeps
inspection/cancel/delete available. A controller defect pauses affected goals;
it never replays their last turn. Removing goal support must leave legacy job
loading and delivery unchanged.

```powershell
git add hermes_core/hermes_cli/config_defaults.py DECISIONS.md `
  docs/superpowers/plans/2026-06-27-bounded-goal-runner.md `
  docs/architecture.md docs/safety.md docs/troubleshooting.md
git commit -m "docs: record bounded goal rollout decision"
```

---

## Verification matrix

| Surface | Command | Required result |
|---|---|---|
| Pure goal core | `cd hermes_core; python -m pytest tests/cron/test_goal_state.py tests/cron/test_goal_usage.py tests/cron/test_goal_transitions.py tests/cron/test_goal_verifiers.py tests/cron/test_goal_report.py tests/cron/test_goal_runner.py -o "addopts=" -p no:cacheprovider -q` | Pass at G0 without LangGraph imports. |
| Runtime adapter | `cd hermes_core; python -m pytest tests/cron/test_goal_agent_worker.py tests/cron/test_cron_goal.py -o "addopts=" -p no:cacheprovider -q` | Pass under explicit loop and graph selection. |
| Cron regression | `cd hermes_core; python -m pytest tests/cron -q -n 4` | Legacy and goal tests pass. |
| Run-agent regression | `cd hermes_core; python -m pytest tests/run_agent -q -n 4` | Inner-engine contracts remain green. |
| Desktop Python | `cd python; python -m unittest discover -s tests -p "test_*.py" -v` | Delivery and profile isolation pass. |
| Rust projection | `cd tauri; cargo test cron` | Host-only sanitized status passes. |
| Web | `cd web; node --test src/advanced/scheduledTasksGoalUx.test.mjs; npm run lint; npm run build` | UI contract, lint, and build pass. |
| Bundle | `./python/build_bundle.ps1 -Verify` | Bundled CPython 3.11 imports all goal modules. |
| Release smoke | Release build: notify + agent + Pilot 1 + restart | Correct delivery, recovery, and isolation. |

## Completion criteria

- [ ] Tasks 1–6 merged without changing live cron execution.
- [ ] G1 evidence recorded; Tasks 7–9 pass with explicit loop and graph engines.
- [ ] `mode: goal` remains unreachable while the feature flag is false.
- [ ] G2 evidence recorded after the Phase 3.5 graph-default soak.
- [ ] Pilot 1 satisfies every safety and correctness exit criterion.
- [ ] Existing `agent` and `notify` jobs remain behaviorally unchanged.
- [ ] Goal Runner has no LangGraph import, checkpointer, or `run_agent.py` edit.
- [ ] Every iteration persists a complete per-attempt usage ledger or pauses as
  `cost_unknown`; unknown cost is never treated as zero.
- [ ] Host/gateway profile isolation and single-executor behavior are proven.
- [ ] Rollback is a config change that preserves inspectable state.
- [ ] `DECISIONS.md` records the final enablement scope and any deferred work.
