# Task 3 Contract Repair Design

**Date:** 2026-06-29  
**Scope:** Repair the four Task 3 defects found during review without changing the frozen `LegacyRunResult` contract or the in-progress Task 8c work.

## Goals

1. Make usage events carry the active billing route, canonical usage, and the existing `CostResult` as the single sources of truth.
2. Pass non-serializable graph collaborators through LangGraph `Runtime.context`, not `configurable` or `TurnState`.
3. Enforce import isolation across every production Python file under `hermes_core`.
4. Ensure optional usage observers cannot alter the agent result or retry path.

## Design

### Usage events and ledger

`UsageEvent` will store:

- attempt index and outcome;
- graph attempt route such as `call_transport`;
- a `BillingRoute` resolved from the active provider/model/base URL;
- `CanonicalUsage | None`, where `None` represents an attempt whose usage is unavailable;
- the existing `CostResult` returned by `estimate_usage_cost`.

Read-only compatibility properties will expose the existing provider, model, token, pricing-version, amount, and currency views without retaining a second writable representation. The graph adapter will normalize provider usage, resolve the active billing route, estimate the cost, and emit the rich event. Missing usage produces an explicit unknown `CostResult`.

`UsageLedger` will implement `UsageEventSink.on_attempt` by delegating to `record`. A snapshot is complete only when every event has canonical usage and a numeric cost whose status is `actual`, `estimated`, or `included`. Zero attempts remains complete with exact `Decimal("0.00")`. Forwarding to an optional downstream sink is wrapped so observer failures are logged and suppressed after the event is retained locally.

### LangGraph runtime context

`builder.py` remains the sole LangGraph import point. It will import `Runtime`, define a typed runtime-context schema containing `GraphServices` plus per-turn callback parameters, and construct `StateGraph(TurnState, context_schema=...)`.

Builder-local wrappers receive `Runtime`, then call the LangGraph-free node functions with `runtime.context`. `nodes.py` remains engine-neutral and consumes a typed context protocol rather than inspecting `RunnableConfig`. `GraphEngine.run_turn` passes the context with `invoke(..., context=...)`; recursion limits remain ordinary invocation configuration.

### Import-isolation guard

The test walker will start at the `hermes_core` root, exclude tests and generated/cache directories, and inspect every production `.py` file. Only `agent/graph_engine/builder.py` may statically import `langgraph`; `langchain` and `langsmith` remain forbidden everywhere.

### Error handling and compatibility

- Observer exceptions never escape usage recording or graph execution.
- Unknown pricing and missing usage remain observable and make aggregates incomplete.
- No collaborator is added to `TurnState`.
- No checkpointer or message reducer is introduced.
- Existing `LegacyRunResult` key-presence behavior is unchanged.

## Test strategy

Each defect gets a failing regression test before production changes:

1. Rich usage events preserve canonical cache/reasoning tokens, billing route, and `CostResult` status/source; real graph emission produces known or included costs when pricing allows.
2. The built graph declares a context schema, nodes receive collaborators through runtime context, and services are absent from configurable state.
3. The import walker includes representative root, gateway, cron, tools, and graph files.
4. A throwing downstream sink does not escape, the local event remains recorded, and `UsageLedger` itself satisfies `UsageEventSink`.

After each red-green cycle, run the three Task 3 test files. Final verification runs all graph/usage tests and checks that only intended files plus the pre-existing Task 8c changes are present.
