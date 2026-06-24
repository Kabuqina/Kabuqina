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

**Status (2026-06-24): COMPLETE — gate met, 10/10 branches.** The replay harness
(`tests/run_agent/golden_harness.py`) + runner (`test_golden_transcripts.py`) +
fixtures (`tests/run_agent/golden/*.json`) are in place and green (11 tests,
deterministic across two runs, hermetic — no network/disk/DB, passes under the
default `-n auto` xdist addopts). It mocks the transport boundary
(`_interruptible_api_call` / `_anthropic_messages_create`), stubs tools at the
shared `handle_function_call` primitive, and snapshots the result dict +
normalized message trajectory + tool invocations + usage/cost + would-be-persisted
rows + stream deltas. **Covered cases:** plain text, single-tool (sequential),
parallel multi-tool (concurrent), anthropic_messages text, interrupt, steer,
unknown-tool rejection, max-iterations (toolless summary via the raw client),
provider fallback, **preflight compression.** Gotchas handled: persisted tool_calls
carry a per-run-random `response_item_id` (normalized out); interrupt/steer driven
via a per-turn action hook in the scripted transport; max-iterations needs a fake
`client.chat.completions.create` (the summary call bypasses
`_interruptible_api_call`); fallback needs `resolve_provider_client` faked;
compression keeps `_compress_context` real (it rotates `session_id` to a random
id — not snapshotted, so still deterministic) and stubs only the model-calling
`context_compressor.compress`. Record/update goldens with
`GOLDEN_RECORD=1 python -m pytest tests/run_agent/test_golden_transcripts.py -o "addopts=" -p no:cacheprovider`.

**→ Phase 3 (consolidate) may now begin behind this net.** Start with 3a.

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

### 3a — Remove the `agent.*` alias shims (leaf, mechanical, do first) — DONE (2026-06-24)

**Landed.** Deleted the 13 `agent/*` alias modules + the `agent/transports/`
package alias, and retargeted every caller `agent.X` → `providers.Y` (4 production
import sites + ~80 files of test imports/monkeypatch strings). Behavior-preserving
by construction — the shims made `agent.X` and `providers.Y` the same module
object, so any name importable/patchable via the old path is identical via the
new one. The two identity-assertion guard tests in
`tests/agent/test_provider_package_split.py` were rewritten to assert the legacy
paths are gone (`ModuleNotFoundError`) and the canonical `providers.*` modules
import. Verified: the heaviest-touched files (913 tests: auxiliary_client,
model_metadata, anthropic_adapter, credential_pool, nous/rate-limit, gemini,
image_*, golden, run_agent, compat) all pass; production modules cold-import
clean; a stash-baseline confirmed the remaining suite failures (gateway cut
platforms, optional-dep tools, Windows file-permission/prompt_toolkit tests) are
pre-existing, identical with or without this change. (Lesson: the retarget script's
dir-exclusion `agent/transports/` also matched the test path
`tests/agent/transports/`, so those 3 files were missed on the first pass — caught
by running the broader suite, then fixed.)

Original notes:



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

### 3b — Overlay + registry: DEFERRED after investigation (2026-06-24)

Investigated `HERMES_OVERLAYS`/`HermesOverlay` (`hermes_cli/providers.py:46`) vs
`PROVIDER_REGISTRY`/`ProviderConfig` (`hermes_cli/auth.py:233`). **They are not a
redundant double layer** — they are two registries serving two subsystems with
only incidental field overlap, and the assumption behind this step (one structure
should obviously own the metadata) does not hold cleanly:

- **`PROVIDER_REGISTRY` is on the live request path.** It's read by
  `runtime_provider.py` (5 sites — `resolve_runtime_provider`, which resolves the
  per-request base_url / api_key env / api_mode), plus `model_switch.py`,
  `providers/chat_completions.py` (api-key fallback iteration), and
  `credential_pool.py`. It also carries the OAuth login fields
  (`portal_base_url`/`client_id`/`scope`/`extra`).
- **`HERMES_OVERLAYS` is identity/routing only** — read by `model_switch.py` (the
  `/model` picker) and `providers.py:get_provider`; it adds `transport` /
  `is_aggregator` on top of the models.dev catalog.
- **Different id conventions + membership:** registry has `gemini`,
  `kimi-coding`, `kimi-coding-cn`; overlay has `openrouter`, `kimi-for-coding`
  (models.dev id). A merge must first *reconcile the id schemes* — a
  behavior-affecting decision, not a mechanical move.

A real merge therefore re-routes the **live request path** through a single
structure and reconciles ids — exactly the change class the provider-deletion
plan flags as "unit tests pass while a missed hot-path branch breaks a live
conversation," requiring a **`scripts/dev.ps1` runtime smoke**. The golden net
does not cover provider resolution (it constructs `AIAgent` with an explicit
provider/base_url and stubs the transport).

**Resolution (2026-06-24): keep the two structures separate; guard against drift
instead of merging.** A user-run smoke unblocked a structural merge, but deeper
investigation confirmed the merge is high-risk / low-value: it reconciles two id
schemes and re-routes the hot path to de-duplicate ~18 small entries, with a
regression surface (the full `/model` picker matrix + login flows) wider than one
chat smoke validates. The actual hazard of a double layer is **drift of the
shared fields**, and the codebase already treats `PROVIDER_REGISTRY` as the
source of truth ([model_switch.py:1068]). So instead of merging, added
`tests/hermes_cli/test_provider_registry_overlay_consistency.py` — a guard pinning
the membership asymmetry (overlay-only `openrouter`; registry-only `gemini`,
`kimi-coding-cn`) and the shared fields (`base_url_env_var` agreement, overlay
`extra_env_vars` ⊆ registry `api_key_env_vars`, `auth_type` agreement). The guard
**already caught a real drift**: `minimax-oauth` was `oauth_external` in the
overlay vs `oauth_minimax` in the registry (the latter drives the actual login).
**Reconciled** — the overlay now uses `oauth_minimax` to match; the change is
behavior-inert (`ProviderDef.auth_type` is set but never branched on; every
`auth_type` dispatch reads the registry `pconfig`, and minimax-oauth resolves via
the dedicated `runtime_provider.py` branch), verified by 209 tests, and the guard
now asserts full agreement (empty exception set). A full structural merge remains
possible but is **not recommended**; if pursued it needs the runtime smoke +
id-scheme reconciliation as its own effort.

### 3c — `api_mode` at N=2: DEFERRED into 3.5 (2026-06-24)

`_VALID_API_MODES = {"chat_completions", "anthropic_messages"}`
(`runtime_provider.py:141`) — two genuinely different wire protocols, 77 refs in
`run_agent.py`. The earlier-hoped win was removing *dead* scaffolding from the cut
api_modes — but the tier-3 provider deletion already did that: a grep of
`run_agent.py` finds only the two live literals (`bedrock_converse` /
`codex_responses` are gone). So **what remains is the live 2-protocol dispatch
threaded through the request/response loop** — and trimming it is exactly the
"loop surgery" this step's own conservative rule says to **defer into 3.5**, where
the LangGraph re-platform rewrites that dispatch behind the anti-corruption port
anyway. Doing it now would be throwaway work against a hot path with no runtime
smoke. Deferred per rule — the correct outcome, not a failure.

**Phase 3 status (2026-06-24): 3a DONE; 3b RESOLVED (guard, no merge); 3c DEFERRED
into 3.5.** 3a (the safe, mechanical, behavior-preserving leaf) landed and is
verified. 3b was investigated to a conclusion — the overlay and registry are
genuinely separate subsystems, so rather than a risky structural merge a drift
guard was added (and it already found the `minimax-oauth` `auth_type` divergence).
3c's remaining `api_mode` machinery is the live 2-protocol dispatch — loop surgery,
folded into 3.5. **Net:** phase 3 delivered the import-surface consolidation (3a)
and the drift guard (3b); the structural registry merge is intentionally *not*
done (high-risk/low-value), and the api_mode trim belongs to the re-platform.

**Phase 3 exit criteria (for the deferred parts):** golden harness green;
`scripts/dev.ps1` runtime smoke (chat + one tool, both a chat-completions and an
Anthropic backend); the `providers/` split guardrails
(`test_provider_package_split.py`) and compat guardrails
(`tests/kabuqina/test_compat_imports.py`) green.

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
