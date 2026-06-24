# Consolidate + LangGraph Re-platform Plan (phases 0 / 3 / 3.5)

Date: 2026-06-24

Successor to `2026-06-21-large-file-split-plan.md` (CLOSED). Covers the
restructuring tail: a **golden-transcript characterization harness** (the safety
net), **Phase 3 — consolidate the narrowed architecture**, and **Phase 3.5 —
ReAct→LangGraph core re-platform**. Sequencing and rationale come from the
restructuring phase model (memory `restructuring-phase-model`); this doc turns
its "NO PLAN WRITTEN YET" Phase 3 into concrete touchpoints and fixes the
ordering of the characterization work.

## Where this fits

The phase model orders work by **churn-radius × verifiability** — subtractive /
verifiable early, transformative / unverifiable late on the most stable surface:

- **0–1** scope decision + big-bang delete: done (v0.3.0).
- **2** split shared auth infra ⇄ delete entangled set-D providers: **done** —
  `providers/` extraction landed (split plan steps 1–3) and all 15 set-D
  providers cut (`2026-06-22-provider-deletion-plan.md`).
- **0 (this doc, but do first)** golden-transcript characterization harness:
  the behavioral safety net. **Prerequisite for Phase 3, not a tail task** — it
  protects the consolidate refactor *and* the re-platform.
- **3** consolidate the narrowed architecture: collapse abstractions built for
  the full provider set that now serve `kimi/zai/minimax/alibaba/anthropic/…`.
  **The gate for everything below.**
- **3.5** ReAct→LangGraph re-platform of the core loop. Go/no-go **deferred
  until Phase 3 lands**.
- **4** rename / identity migration (`kabuqina_core`, `KABUQINA_*`, `~/.hermes`):
  last, mechanical sweep over the final surface. Out of scope here.

Guiding constraint from the phase model: **do not rename before re-platforming**,
and **build on langgraph-core only** (StateGraph/state/checkpoint — 1.0/GA), not
the fast-churning LangChain chains/agents periphery, wrapped behind a thin
anti-corruption port so API churn has a one-file blast radius.

---

## Phase 0 — Golden-transcript characterization harness (DO FIRST)

**Status (2026-06-24): LANDED, 9/10 branches.** The replay harness
(`tests/run_agent/golden_harness.py`) + runner (`test_golden_transcripts.py`) +
fixtures (`tests/run_agent/golden/*.json`) are in place and green (10 tests,
deterministic across two runs, hermetic — no network/disk/DB, passes under the
default `-n auto` xdist addopts). It mocks the transport boundary
(`_interruptible_api_call` / `_anthropic_messages_create`), stubs tools at the
shared `handle_function_call` primitive, and snapshots the result dict +
normalized message trajectory + tool invocations + usage/cost + would-be-persisted
rows + stream deltas. **Covered cases:** plain text, single-tool (sequential),
parallel multi-tool (concurrent), anthropic_messages text, **interrupt, steer,
unknown-tool rejection, max-iterations (toolless summary via the raw client),
provider fallback.** Gotchas handled: persisted tool_calls carry a per-run-random
`response_item_id` (normalized out); interrupt/steer are driven via a per-turn
action hook in the scripted transport; max-iterations needs a fake
`client.chat.completions.create` because the summary call bypasses
`_interruptible_api_call`; fallback needs `resolve_provider_client` faked.
**One branch still deferred: compression** — `_compress_context` runs the
ContextCompressor (which itself makes model calls), so a deterministic fixture
needs the compressor stubbed, not just a high `prompt_tokens`; deferred to avoid a
brittle golden, do as a focused follow-up. Record/update goldens with
`GOLDEN_RECORD=1 python -m pytest tests/run_agent/test_golden_transcripts.py -o "addopts=" -p no:cacheprovider`.

**Goal:** pin the *observable* behavior of `AIAgent.run_conversation`
(`run_agent.py:9374`) with replayable golden transcripts, so both the consolidate
refactor (Phase 3) and the re-platform (Phase 3.5) can be proven
behavior-equivalent by test rather than by inspection. "New graph ≡ old loop" and
"consolidated dispatch ≡ old dispatch" are exactly the claims that can't be eyeballed.

**Why first (corrects the split plan's "tests last"):** consolidate collapses
api_mode / overlay+registry / alias machinery that threads through the request
path — behavior-preserving *in intent*, risky *in fact*. The same harness that
de-risks 3.5 de-risks 3, so it must exist before Phase 3 edits begin.

**What exists to build on:**
- ~80 focused unit tests under `tests/run_agent/` (streaming, tool repair,
  compression, interrupts, client lifecycle) — keep them; they're not full-loop.
- A `MockMessage/MockToolCall/MockChoice/MockFunction` dataclass pattern in
  `tests/run_agent/test_agent_loop.py` (built for the atropos `environments`
  loop) — reuse the shape to fake OpenAI/Anthropic responses for `AIAgent`.
- `agent/usage_pricing.py` (`estimate_usage_cost`, `normalize_usage`) — already
  the usage accounting; golden assertions on cost should call through it.

**Design — record/replay a conversation, assert observable outputs:**
1. **Mock the transport boundary, not the loop.** Drive the loop through a fake
   client that yields a *scripted sequence* of assistant turns (text +
   tool_calls), one per API call, for both api_modes (`chat_completions` and
   `anthropic_messages`). The fake records the `api_kwargs` it was handed.
2. **A transcript = (input user message, scripted model turns, stubbed tool
   results, expected observable outputs).** Store as JSON fixtures under
   `tests/run_agent/golden/`.
3. **Observable outputs to snapshot** (the equivalence contract):
   - final assistant text + the full `messages` list shape (roles, tool_call ids,
     ordering, thinking-block handling);
   - the sequence of tool invocations (`_invoke_tool` name + args) and the
     dispatch decision (sequential vs concurrent, `_should_parallelize_tool_batch`);
   - persisted session rows (`_flush_messages_to_session_db`) and trajectory
     (`_convert_to_trajectory_format`) — capture via the existing hooks;
   - usage/cost (`normalize_usage` / `estimate_usage_cost`);
   - emitted stream deltas / status / interim messages (stream-callback log).
4. **Cover the load-bearing branches** at least once each: a plain text answer,
   a single-tool turn, a parallel multi-tool batch, a compression trigger
   (`_compress_context`), an interrupt/steer, a provider-fallback
   (`_try_activate_fallback`), max-iterations (`_handle_max_iterations`), and one
   `anthropic_messages` path. These are the behaviors consolidate/3.5 are most
   likely to perturb.

**Deliverables:** `tests/run_agent/golden/` fixtures + a `replay_transcript()`
helper + a `test_golden_transcripts.py` runner. A `--record` mode that captures a
fresh snapshot makes adding cases cheap (review the diff, commit the fixture).

**Exit criteria:** harness runs green on `main`; each branch above has ≥1 golden
case; the snapshot is stable across two runs (no nondeterminism leaking — seed
`_deterministic_call_id`, freeze timestamps in persisted rows). **Do not start
Phase 3 until this is green.**

**Non-goal:** this is not a live-API test. Keep the existing `scripts/dev.ps1`
runtime smoke as the separate manual gate for real-network behavior.

---

## Phase 3 — Consolidate the narrowed architecture

**Goal:** remove indirection that only earned its keep when the provider set was
large. After the set-D deletion the live providers are a handful of
OpenAI-compatible chat backends + Anthropic. Three targets, leaf-first, each its
own commit, golden harness green after each.

### 3a — Remove the `agent.*` alias shims (leaf, mechanical, do first)

The step-2 extraction left `sys.modules[__name__] = _impl` redirects in `agent/`
(`auxiliary_client`, `anthropic_adapter`, `gemini_native_adapter`,
`credential_pool`, `error_classifier`, `model_metadata`, `image_routing`,
`retry_utils`, `transports/`, …). They exist only so old import paths keep
working — they were always meant to die once callers migrate.

- Several already have **0 internal source callers** (`anthropic_adapter`,
  `gemini_native_adapter`, `error_classifier`, `image_routing`) → delete the shim
  outright.
- The rest have a handful (`auxiliary_client`×3, `model_metadata`×3,
  `credential_pool`×2, `retry_utils`×1) → migrate those imports to `providers.*`
  first, then delete the shim.
- The deletion conditions are already encoded in
  `tests/agent/test_provider_package_split.py` (the `agent.X is providers.Y`
  identity assertions) — flip each from "is the same object" to "agent.X no
  longer imports" as you delete, or remove the assertion if the path is gone.

Lowest risk, no behavior surface; warms up the harness wiring.

### 3b — Merge the overlay + registry double layer

Two parallel provider-description structures survive:
`HERMES_OVERLAYS`/`HermesOverlay` (`hermes_cli/providers.py:46`) and
`PROVIDER_REGISTRY`/`ProviderConfig` (`hermes_cli/auth.py:233`). They were a
double layer to let the upstream registry and the Hermes overlay coexist; with a
small fixed provider set, one structure should own provider metadata.

- Inventory what each field of `HermesOverlay` adds over `ProviderConfig` and
  where each is read (`model_switch.py:1124`, `providers.py:282`, the model
  catalog in `models.py`). Decide a single source of truth (likely fold overlay
  fields into the registry, keep `providers.py` as the read API).
- This touches `/model` switching and model-catalog code, not the hot request
  loop directly — but run the golden harness anyway (model identity affects
  `_build_api_kwargs`).

### 3c — Review the `api_mode` indirection at N=2

`_VALID_API_MODES = {"chat_completions", "anthropic_messages"}`
(`runtime_provider.py:141`). These are **two genuinely different wire protocols**,
so the dimension does *not* simply collapse — but its *machinery* is spread thin:
77 refs in `run_agent.py`, 62 in `providers/chat_completions.py`, 61 in
`runtime_provider.py`, 35 in `models.py`.

- The win here is **not** deleting the dimension — it's removing dead branches
  and dispatch scaffolding left over from the cut api_modes (`bedrock_converse`,
  `codex_responses`) and concentrating the 2-way switch behind the transport
  layer (`providers/transports/`) instead of re-deciding `api_mode == "…"` at 77
  call-sites in the loop.
- **Be conservative:** this is the consolidate target most entangled with the
  loop, and the loop is about to be re-platformed. Only collapse what's clearly
  dead or trivially behind the transport boundary; leave deeper api_mode
  threading for the re-platform to absorb. If 3c looks like it's turning into
  loop surgery, **stop and defer it into 3.5** — that's the correct outcome, not
  a failure.

**Phase 3 exit criteria:** golden harness green; `scripts/dev.ps1` runtime smoke
(chat + one tool, both a chat-completions and an Anthropic backend); the
`providers/` split guardrails (`test_provider_package_split.py`) and compat
guardrails (`tests/kabuqina/test_compat_imports.py`) green. Then **write the
Phase 3.5 go/no-go note** and re-confirm the re-platform decision against the
consolidated surface.

---

## Phase 3.5 — ReAct→LangGraph core re-platform

**Gated** on Phase 3 landing + the golden harness. Go/no-go is a deliberate
decision made *after* consolidate, not assumed here. The phase model's myths are
already resolved: bundle size is a non-issue (~10–20 MB pure-Python marginal add;
see memory `msi-bundle-size-2gb-limit`); the real cost is LangChain-ecosystem
version churn + locking `langsmith` tracing off.

**Approach (from the phase model — restated as build rules):**
1. **langgraph-core only.** Use `StateGraph` / typed state / checkpointer. Do
   **not** pull in LangChain chains/agents or LangGraph prebuilt periphery (the
   churn lives there). No `langchain`-framework runtime dependency.
2. **Anti-corruption port.** Wrap LangGraph behind one thin module
   (`agent/graph_port.py` or similar) that the rest of the codebase imports —
   so a LangGraph API break is a one-file edit, not a repo-wide churn.
3. **Strangler / parallel-run behind a feature flag.** Keep `run_conversation`
   as the public entrypoint; add the graph path behind a flag (env or config),
   default off. Run both against the **golden transcripts** and diff observable
   outputs until the graph matches the loop case-for-case; only then flip the
   default. Keep the old loop deletable in one commit once the graph is trusted.
4. **Map the state, not the line-by-line control flow.** The graph state carries
   the message list, tool-call queue, iteration budget (`IterationBudget`),
   compression/interrupt/steer signals, fallback state, and usage accumulator.
   The orthogonal keep-forever concerns (persistence via
   `_flush_messages_to_session_db`, trajectory, usage via `usage_pricing`) stay
   as side-effect nodes / post-hooks — they are *not* re-implemented in the graph.

**Optional pre-3.5 extraction (the residual from old split-plan step 4):** if it
helps the graph have a clean loop to replace, extract the session-persistence
helpers (`_persist_session`, `_flush_messages_to_session_db`, `_save_session_log`,
~`run_agent.py:3493–4115`) and the trajectory helpers (`_save_trajectory`,
`_convert_to_trajectory_format`) into `agent/session_persistence.py` (trajectory
folds into the existing `agent/trajectory.py`). This is **optional and low-value**
on its own (~600–900 lines off a 12.9k file, no size win, adds wrapper churn) —
do it only as 3.5 prep, behind the golden harness, never as a standalone branch.

**Exit criteria:** graph path matches all golden transcripts; `scripts/dev.ps1`
live smoke on a chat-completions and an Anthropic backend; flag default flipped;
old loop removed in a dedicated commit; anti-corruption port is the only
LangGraph import site.

---

## Guardrails (every phase)

- **Golden harness green after every commit** in Phase 3 / 3.5 — it is the
  equivalence contract.
- No behavior change bundled with a move (the split plan's rule still holds).
- After each step: the golden harness, `tests/run_agent/`,
  `tests/kabuqina/test_compat_imports.py`,
  `tests/agent/test_provider_package_split.py`,
  `python/tests/test_product_profile.py` (provider-cut absence contract), then a
  desktop `python -m unittest discover`. For any hot-path change and for 3.5, a
  `scripts/dev.ps1` runtime smoke (live chat + one tool, **both** api_modes) —
  unit + golden tests pass while a missed branch breaks a live conversation.
- Test-env on this Windows box (memory `running-tests-windows-dev`): system
  Python, `-o "addopts=" -p no:cacheprovider`; GBK-locale / `prompt_toolkit` /
  Windows-permission failures are pre-existing environmental noise.

## Non-goals

- No rename / identity migration (Phase 4) before the re-platform.
- No new gateway-platform splits (separate track).
- Don't reintroduce a cut provider or remove names from `GLOBAL_STUDENT_CUT`.
- Phase 3.5 is **not pre-approved** — its go/no-go is decided after Phase 3.
