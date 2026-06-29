# Locked product decisions

This file freezes the choices that shape the rest of the codebase. Anything
not on this list is open for change. Anything on this list requires a PR with
explicit reasoning to alter.

## Identity

| Field          | Value                                                    |
|----------------|----------------------------------------------------------|
| Working name   | **Kabuqina**                                           |
| Bundle id      | `com.kabuqina.app`                                     |
| Install target | Per-user, `%LOCALAPPDATA%\com.kabuqina.app` (no admin needed)  |
| License        | Apache-2.0                                               |
| Upstream       | Frozen snapshot at `hermes_core/` (from `NousResearch/hermes-agent` pinned to `v0.10.0`). No submodule, no automatic sync. |
| Tagline        | "A friendly AI helper for your PC. No setup, no terminal." |

The "Kabuqina" name is provisional. Trademark check is pending — see
`docs/branding-todo.md` (not yet written).

## De-patching migration (2026-05-03)

| Question | Decision |
|----------|----------|
| Product relationship | **Independent.** Kabuqina is a standalone monorepo. The upstream `NousResearch/hermes-agent` is frozen at `hermes_core/`. |
| Upstream sync | **Cherry-pick only.** Security advisories, CVEs, and provider API breaking changes are manually cherry-picked and logged in this file. No batch merges. |
| Gateway platforms | Student runtime keeps Weixin, QQ Bot, Feishu/Lark, Telegram, and WeCom. DingTalk is temporarily disabled because `dingtalk-stream` requires legacy `websockets<13`, which conflicts with Browser/CDP; revisit for the office-oriented edition or after the SDK supports modern websockets. Weixin and Feishu remain feature-flagged at the `GatewayPolicy` level. |
| Architecture | `agent_core` (frozen Hermes) + `desktop_policy` (6 injected policy objects). Overlays are transitional and tagged `# DEPRECATED`. |

## Desk-minimal runtime (2026-05-21)

| Question | Decision |
|----------|----------|
| Hermes dashboard SPA | **Removed from product path.** Kabuqina shell is the only UI; `web_dist` and the `-BuildHermesDashboard` opt-in are no longer bundled. |
| Python boot | **`HERMESDESK_DESK_MINIMAL=1`** — lazy tool/plugin discovery, early `port.txt`, background warm thread; chat returns 503 `warming` until tools are ready. |
| Edge CDP | Starts **async** after bridge; does not block Python spawn. |
| Gateway | Unchanged in this pass (still optional second process). |

## Desk server split (2026-05-21)

| Question | Decision |
|----------|----------|
| Product HTTP API | **`python/src/desk_server/`** — Kabuqina-owned FastAPI app with `/api/desk/*`, `/api/sessions*`, `/api/hermesdesk/*`, slim `/api/status`. |
| Upstream `web_server.py` | **Deleted from the retained runtime.** Desk routes, HermesDesk auth bridge, and catalog code live in Kabuqina `desk_server`; there is no `web_dist` bundle path. |
| Entrypoint | `desktop_entrypoint.py` imports and starts `desk_server`, not `hermes_cli.web_server`. |

## Cron notify mode (2026-05-21)

| Question | Decision |
|----------|----------|
| Fixed-text reminders | **`mode: notify`** on cron jobs in `hermes_core/cron/`. Delivers `message` (or `prompt`) via existing `tick()` → `_deliver_result` pipeline **without** invoking `AIAgent`. |
| Default | `mode` omitted or `agent` — unchanged LLM cron behavior. |
| Aliases | `static`, `message` normalized to `notify`. |
| vs `wakeAgent: false` | Script gate skips LLM and returns `[SILENT]` (**no delivery**). Notify is for user-visible reminders only. |
| Desktop delivery | Still `python/overlays/cron_desktop_delivery.py` for `deliver=desktop` / `local`. |

## Product capabilities vs load packages (2026-06-01)

| Question | Decision |
|----------|----------|
| Product model | First-party features such as formula extraction, local STT, CodeT5-style code intelligence, and Latexify-style conversion are modeled as **product capabilities**. |
| Large local assets | Model weights and heavyweight runtime assets are modeled as **load packages**. |
| Relationship | Capabilities reference required/optional load packages; load packages do not encode product semantics. |
| User surface | Capability page is the feature readiness view. Settings load-package management is the storage/download/cache view. |
| Agent self-knowledge | Desktop chat receives a compact capability summary via `ephemeral_system_prompt`, generated from the same backend catalog as the UI. |

Future first-party additions follow this order: add a load package in `python/src/load_packages.py` when large local assets are needed; add the product capability in `python/src/capability_registry.py`; add or expose shared agent tools in `hermes_core/` when web and gateway children should share semantics; keep Windows-only cache/path/download wiring in `python/src/`.

## Math capability: language list & code→formula guard (2026-06-15)

| Question | Decision |
|----------|----------|
| Offered target languages | **Python, NumPy, JavaScript, MATLAB/Octave, C++17.** Fortran removed — not in the undergraduate curriculum. C++17 promoted from "internal-only" (the `_emit_code` / `cxxcode` path was already written); pure C is never exposed. |
| Frontend | `MATH_TARGET_LANGUAGES` in `WorkspacePanel.tsx` mirrors `OFFERED_LANGUAGES` in `math_expression_tools.py`. Always keep these in sync. |
| code→formula guard | **Deterministic AST whitelist in the tool layer, not prompt-level heuristics.** `_assert_math_expression` walks the extracted expression node before it reaches SymPy and rejects anything that is not closed-form math (attribute calls, subscripts, comparisons, string constants, list/dict literals, etc.). Only arithmetic operators, whitelisted math-function calls (`sin/cos/exp/log/sqrt/…` including `math.`/`np.` prefixes via `_FlattenMathNamespaces`), numeric constants, and variable names are permitted. A bare variable with no operation is also rejected ("at least one math signal" rule). Violations return `tool_error` with a clear message; the model never sees nonsense LaTeX. |
| Why tool-layer, not agent_hint only | Agent hints cannot guarantee the model will refuse before calling. A deterministic gate is free, always on, and cannot be talked around. Follows the "good quality, nearly free" philosophy: structure does what structure can. |

## PDF writer path (2026-06-12)

| Question | Decision |
|----------|----------|
| Writer-layer PDF output | **`pdf_write` in `hermes_core/tools/document_tools.py`.** PDF generation is an agent core document writer, not an overlay. |
| Rendering path | Structured `sections`/`blocks` → normalized PDF spec → same-name canonical HTML print source → Chromium print PDF renderer (`chromium_print_v1`); ReportLab (`reportlab_pdf_v1`) is fallback only. |
| Supported content blocks | `heading`, `paragraph`, `bullets`, `table`, `code`, `formula`, `image_placeholder`, `page_break`. Unknown blocks fall back to paragraphs. |
| Capability model | Exposed as first-party `document-pdf-generation`; agents should call `pdf_write` for PDF deliverables and verify `path`, `html_path`, and `renderer` before claiming success. `chromium_print_v1` means the PDF was printed from the HTML source; `reportlab_pdf_v1` means degraded fallback. |
| Pipeline shape (Phase B, 2026-06-12) | Primary pipeline `document-report-pdf` is the **full four layers** (reader → material_index → planner/`review_outline` → `pdf_write`), mirroring the student-PPT flow; `document-pdf-writer-v1` is kept as a non-primary direct-from-blocks path. Report types (`academic_report` / `code_report` / `math_report`) are `structure_templates` binding a `pdf_template` to a `material_index` profile. The four-layer↔step consistency is enforced by `validate_capability_definitions()`. |
| HTML writer path (Phase C, 2026-06-12) | First-class HTML output is **`html_write` in `hermes_core/tools/document_tools.py`** (renderer `standalone_html_v1`), registered in the `documents` toolset. It reuses pdf_write's structured `sections`/`blocks` contract and `_block_to_html`, but wraps output in a responsive, self-contained page (`_build_standalone_html`) — distinct from the print-oriented `.html` sidecar pdf_write emits. Exposed as first-party `document-html-generation` with a full four-layer primary pipeline `document-report-html` plus a non-primary `document-html-writer-v1` direct path; report types are `web_report` / `study_notes` / `code_walkthrough`. |
| Planner sink (Phase C planner, 2026-06-12) | The Planner layer is sunk into the agent core: **`build_deliverable_planner_prompt` in `hermes_core/agent/prompt_builder.py`**, called by `run_agent._build_system_prompt` and self-gated on the deliverable writer tools, so the **desk child and gateway child plan identically** (both construct `run_agent.AIAgent`). Slide vocabulary is single-sourced from new **`hermes_core/tools/deliverable_contract.py`** — `document_tools` normalizes against the same sets a drift-guard test enforces, so planner guidance and writer normalization cannot diverge. `WorkspacePanel.tsx` quick-actions are thinned to intent + structure id + visual-master selection. |
| DOCX writer path (Phase C, 2026-06-12) | Editable Word output is **`docx_write` in `hermes_core/tools/document_tools.py`** (renderer `python_docx_v1`, via the already-bundled `python-docx`), registered in the `documents` toolset. It reuses the shared `sections`/`blocks` contract (`_build_pdf_spec` normalization) and renders the same block types to Word (`_render_docx` / `_docx_add_block`), so one reviewed outline can target PDF, HTML, or DOCX. Exposed as first-party `document-docx-generation` with a full four-layer primary pipeline `document-report-docx` plus a non-primary `document-docx-writer-v1` direct path; report types are `word_report` / `study_notes` / `project_report`. |

**Cherry-pick log:**

| Date | Commit | Origin | Reason |
|------|--------|--------|--------|

## Distribution & signing

| Field          | Value                                                    |
|----------------|----------------------------------------------------------|
| Format         | Windows `.msi` produced by Tauri bundler                 |
| Architectures  | x86_64 only at v1. ARM64 deferred.                       |
| Min OS         | Windows 10 22H2 (1809+ for WebView2 evergreen)           |
| Signing cert   | OV cert (~$80/yr, e.g. SSL.com or Sectigo) for v1; reassess EV cert (~$300/yr, removes SmartScreen reputation wait) before public launch |
| Update channel | Tauri updater -> GitHub Releases (signed manifest)       |

**Code-signing budget locked:** $100/yr for OV cert + $0 for GitHub Releases
hosting. Total infra cost target = $100/yr until we hit 10k users.

## LLM access (zero-threshold path)

Decided in plan-mode Q&A: **BYO key with a guided wizard.** The wizard:

1. Defaults to **OpenRouter** as the recommended provider — biggest model
   selection, $5 minimum top-up, single key works across all models.
2. Offers a **Free starter** path: OpenRouter free-tier models
   (`*:free` model IDs, e.g. `google/gemini-2.0-flash-exp:free`,
   `meta-llama/llama-3.3-70b-instruct:free`). Rate-limited but $0.
3. Allows **manual provider entry** (Anthropic, OpenAI, Nous Portal, etc.)
   under "I have my own".

Hosted backend is **explicitly deferred** — re-open this decision if BYO
friction proves to block adoption (see plan risks).

## Initial Hermes tool keep-list

These tools are enabled by default for non-pros. Everything else is hidden
behind the "Power user" toggle, off by default.

| Tool module                              | Why we keep it                            |
|------------------------------------------|-------------------------------------------|
| `tools/file_operations.py`               | Read/write files in workspace             |
| `tools/file_tools.py`                    | Search/glob/list inside workspace         |
| `tools/web_tools.py` (search subset)     | Web search via Exa/Brave/etc.             |
| `tools/image_generation_tool.py`         | Image generation (fal/etc.)               |
| `tools/tts_tool.py` (Edge TTS only)      | Free text-to-speech, no API key           |
| `tools/transcription_tools.py`           | Voice memo transcription                  |
| `tools/memory_tool.py`                   | Persistent memory                         |
| `tools/skills_tool.py`                   | Skills system (core differentiator) — see [docs/skills-design-decision.md](docs/skills-design-decision.md) for tiering model |
| `run_builtin_helper` (Kabuqina overlay) | L1 only: whitelist dispatch to bundled `python/helpers/*` — see [docs/skills-security.md](docs/skills-security.md); **not** generic `code_execution` |
| `tools/todo_tool.py`                     | Lightweight todo list                     |
| `tools/vision_tools.py`                  | Image understanding                       |
| `tools/clarify_tool.py`                  | Ask clarifying questions                  |

**Kabuqina Skills — recipe market strip (v1):** Off by default. The shell **Settings** app stores `hermesdesk.show_recipe_market` and mirrors it to `hermesdesk_show_recipe_market.txt` under `%LOCALAPPDATA%\com.kabuqina.app\` so the embedded web `/api/status` and **Skills** page can show a **UI-only** placeholder banner without restarting Python. No remote catalog in v1.

**Hidden behind "Power user" toggle (off by default):**

- `tools/terminal_tool.py` (shell)
- `tools/code_execution_tool.py`
- `tools/browser_tool.py`, `tools/browser_camofox.py`
- `tools/mcp_tool.py`, MCP OAuth
- `tools/cronjob_tools.py`
- `tools/delegate_tool.py` (subagent spawning)
- `tools/mixture_of_agents_tool.py`
- `tools/rl_training_tool.py`
- `tools/send_message_tool.py` (multi-platform)
- `tools/feishu_*`, `tools/homeassistant_tool.py`

**Not shipped at all (out of scope for desktop):**

- `rl_cli.py`, `tinker-atropos/`
- `batch_runner.py`, `mini_swe_runner.py`
- `trajectory_compressor.py`
- `gateway/` (entire directory)
- `acp_adapter/`, `acp_registry/`
- `mcp_serve.py` (we host MCP clients only, not a server)
- All cloud terminal backends (Modal, Daytona, Singularity, SSH)

## Personality presets shipped at v1

The "Pick a vibe" onboarding step picks one of:

- **Helpful** (default) — neutral, clear, gets things done
- **Friendly** — warmer, more conversational
- **Concise** — short answers, no fluff

These map to existing Hermes personality files. Custom personalities are an
"Advanced" feature.

## Safety defaults

See [docs/safety.md](docs/safety.md). Highlights:

- Workspace folder: `%USERPROFILE%\Documents\KabuqinaWork` (created on first
  launch). Single jail; the user can change it in Settings, but it always
  stays a single folder.
- Shell approval: **deny by default**, prompt every time, no "always allow".
- Network egress allowlist: LLM provider host + a small fixed allowlist
  (`*.agentskills.io` for the skills hub, `speech.platform.bing.com` for
  Edge TTS).
- Telemetry: **off by default**, opt-in only, anonymized.

## Skills exposure model

Replaces the original "Skills hidden behind Power-user toggle" plan.
Skills are tiered by *action* (use / install / author), not by user.
Default users get a curated set of built-in "Quick Actions" surfaced
on the chat screen; advanced mode unlocks an officially signed Skill
market; power-user mode unlocks unsigned third-party install and a
YAML editor. Full reasoning, security model, and implementation plan
in [docs/skills-design-decision.md](docs/skills-design-decision.md).

## Planned: Native document read/write tools (2026-05-06)

| Question | Decision |
|----------|----------|
| Formats | `.docx`, `.pptx`, `.pdf` — read + write. Skip legacy `.doc`/`.ppt` (OLE binary, no lightweight Python lib). |
| Availability | All users (standard `KEEP_LIST` + `GATEWAY_KEEP_LIST`). |
| PDF write capability | Markdown → PDF with basic formatting (headings, bold, lists). |
| Status | **Planned, not implemented.** See [`docs/document-tools-plan.md`](docs/document-tools-plan.md) for full plan. |

## Out of scope for v1

- Linux / macOS builds
- ARM64 Windows
- Multi-user / per-machine install
- Hosted backend
- Mobile (Telegram bridge etc.)
- Third-party (unsigned) Skill marketplace — v1.0 ships only built-in
  Recipes; signed market is v1.1, unsigned third-party is v1.2
- Voice-first / always-listening mode (push-to-talk only)

## v0.3.0 Slim & Focus scope (2026-06-19)

Plan: [`docs/superpowers/specs/2026-06-19-v0.3.0-slim-and-focus-plan.md`](docs/superpowers/specs/2026-06-19-v0.3.0-slim-and-focus-plan.md).
Merges the core refactor mechanics ([`.qoder/specs/Core重构架构设计_task-eee.md`](.qoder/specs/Core重构架构设计_task-eee.md))
and the product pruning policy ([`docs/superpowers/specs/2026-06-19-mainland-profile-code-pruning-design.md`](docs/superpowers/specs/2026-06-19-mainland-profile-code-pruning-design.md)).

| Question | Decision |
|----------|----------|
| v0.3.0 theme | Reduce bundle size + converge the product to the `mainland_cn` student profile. No agent hot-path changes, no package rename. |
| `mainland_cn` visible gateways | `desktop, weixin, qqbot, feishu, wecom` only. |
| **Telegram** | **Supersedes 2026-05-03.** Moved out of the student (`mainland_cn`) runtime to the future `sea` profile: source retained, hidden in `mainland_cn`. Mainland students do not use it. |
| Discord / WhatsApp / Email | `sea`-profile: source retained, hidden in `mainland_cn`. Discord overlaps the student/gamer demographic, so it is kept for `sea`. |
| **DingTalk** | **Extends 2026-05-03.** Source retained (a school / office edition may use it), hidden in `mainland_cn`. Its Alibaba Cloud SDKs (`dingtalk_stream` — needs `websockets<13`, conflicts with Browser/CDP — plus `alibabacloud_dingtalk`/`alibabacloud_tea_openapi`/`alibabacloud_tea_util`) are excluded from the runtime bundle; the adapter degrades gracefully when absent. |
| webhook / api_server | **Global delete** — technical integration surfaces unsuitable for student users. |
| Globally deleted (both specs agree) | Gateways `slack`, `signal`, `matrix`, `mattermost`, `bluebubbles`, `homeassistant`, `yuanbao`; tools `rl_training`, `homeassistant`, `mixture_of_agents`, `yuanbao`; global-cut plugins and skill categories; upstream `ui-tui`/`tui_gateway`/`acp_adapter`/`acp_registry`/`website`/RL-benchmark/`mcp_serve` surface. |
| Provider global deletion | **Deferred to v0.3.x.** The global-cut providers (`bedrock`, `openai-codex`, `copilot-acp`, `opencode`, etc.) are entangled in `hermes_core/agent/auxiliary_client.py` (~3,833 lines) with retained providers. Do refactor Phase 3 (provider extraction) first, then delete at file level. In v0.3.0 they are only hidden via profile policy. |
| Core rename + user-data migration | **Deferred to v0.4.0.** Refactor Phases 8-9 (`kabuqina_core` rename, `KABUQINA_*` env beyond the profile var, `%LOCALAPPDATA%` home migration) are orthogonal to size/focus. |
| Profile env var | `KABUQINA_PRODUCT_PROFILE` (primary), `HERMESDESK_PRODUCT_PROFILE` fallback; unknown/missing → `mainland_cn`. |

## Phase 3.5 LangGraph dependency closure (2026-06-28)

Plan: [`docs/superpowers/specs/2026-06-24-consolidate-and-langgraph-replatform-plan.md`](docs/superpowers/specs/2026-06-24-consolidate-and-langgraph-replatform-plan.md) Task 1.

| Question | Decision |
|----------|----------|
| Pin | `langgraph==1.2.6` in `hermes_core/pyproject.toml` (core deps) and `python/requirements-desktop.txt` (desktop bundle). Low-level `StateGraph` API only. |
| Transitive deps | `langchain-core`, `langgraph-checkpoint`, `langgraph-prebuilt`, `langgraph-sdk`, `langsmith` are accepted **transitive** deps; production code must not import them outside the graph builder. No direct pins on them. |
| Checkpointer | **None** in Phase 3.5 — compile the graph without `MemorySaver`/`InMemorySaver`; Hermes `session_db` stays the only conversation store. |
| Bundle viability (probe, 2026-06-28) | Wheels-only resolution under bundled CPython 3.11.15; **net +9.46 MB** (gross closure 21.68 MB; ≤ 25 MB gate **PASS**); `from langgraph.graph import StateGraph` imports OK. No source-built wheel required. |
| LangSmith tracing | Forced `LANGSMITH_TRACING=false` in `tauri/src/python_supervisor.rs` and `tauri/src/gateway_supervisor.rs` (verified by contract test + `cargo test`, 60 passed). |
| Deferred | Official `build_bundle.ps1 -Verify` destructive rebuild (true on-disk after-size); and the `uv.lock` refresh — committed `uv.lock` is **already stale** vs `pyproject.toml` (`uv lock --locked` fails even without langgraph; refresh pulls in unrelated `botocore`→google-api drift), so it is split into a separate dependency-hygiene commit. |
| GO (2026-06-28) | **Phase 3.5 GO.** All go/no-go gates passed. Tasks 1–5 complete and committed (`57cadb39`, `b0d1a069`). Stabilization window: 2026-06-28 through 2026-07-12 at the earliest; base commit `605ecda5`. Frozen surfaces: `hermes_core/run_agent.py`, `hermes_core/providers/transports/**`, provider fallback/retry paths, session persistence. Next: Task 6 (tool dispatch + steer parity). |

## Phase 3.5 graph-engine parity follow-ups (2026-06-29)

A review of the committed graph-engine tasks (4–7) on 2026-06-29 found that they
achieved **core-result** parity (final_response, api_calls, completed, messages,
provider/model, streaming dispatch, tool ordering, steer placement,
retry/fallback/interrupt) but left several **side-effect** parity items
unimplemented — and the graph-specific tests were scoped narrowly enough that the
gaps did not surface as failures. The graph engine is **gated off** (no selector
until Task 10), so production runs the loop and end users are unaffected today.

Decision: the items below are **deferred to Task 9 ("Finalization and full
dual-engine equivalence")** and MUST be closed before the engine selector
(Task 10) defaults to `graph` or the legacy loop is removed (Task 11). Each is
now *measured* by `hermes_core/tests/run_agent/test_graph_equivalence_gaps.py`
as `xfail(strict=True)` — when a gap closes the case XPASSes, which strict mode
reports as a failure, forcing promotion to an enforced parity assertion.

| ID | Gap | Evidence | Close in |
|----|-----|----------|----------|
| PH35-FU-001 | **Closed by Task 9 (2026-06-29).** The graph fires all six load-bearing hooks at the same boundaries as the loop: `on_session_start`/`pre_llm_call` in `initialize_turn` (with the loop's new-session-vs-continuation gating), `pre_api_request`/`post_api_request` around each transport attempt in `call_transport`/`process_response`, and `post_llm_call`/`on_session_end` in `_finalize_turn` (post_llm_call only on a completed, non-interrupted turn). `pre_tool_call` already fired via the shared `_execute_tool_calls`. | `test_golden_transcripts` (loop+graph), `test_hook_invocation_parity` (loop+graph) | **done** |
| PH35-FU-002 | **Closed by Task 9 (2026-06-29).** `_accumulate_session_usage` folds each successful response's canonical usage + `CostResult` into the session counters (mirroring run_agent.py:10581), so the finalized result reports the same token/cost totals. | `test_golden_transcripts` (loop+graph), `test_graph_equivalence_gaps` | **done** |
| PH35-FU-003 | **Closed by Task 9 (2026-06-29).** `_finalize_turn` calls `_save_trajectory` on every full-completion exit, matching the loop's frozen exit policy. | `test_golden_transcripts` (loop+graph) | **done** |
| PH35-FU-004 | **Closed by Task 9 (2026-06-29).** `test_golden_transcripts` is now parameterised over `["loop", "graph"]` and both engines are pinned to the same committed `expected` snapshot. The interim `test_graph_equivalence_gaps` xfail cases were promoted to plain parity assertions. | `test_golden_transcripts` | **done** |
| PH35-FU-005 | **Closed by Task 9 (2026-06-29).** Full-snapshot loop/graph equality (incl. stream deltas and the unified callback stream) holds across all 27 fixtures and 120 fixed-seed generated sequences. The graph also replays the compression lifecycle warning and emits the loop's retry/fallback/compression/budget/nous `_emit_status` lifecycle messages. | `test_golden_transcripts`, `test_graph_differential_sequences` | **done** |
| PH35-FU-007 | **Open (deferred from Task 9).** The optional `UsageEventSink` is emitted **only by the graph** (`_GraphServicesAdapter._emit_usage_event`); the legacy loop never emits to it. So a full per-exit *loop-vs-graph UsageLedger sequence* comparison (plan Task 9 Step 2 / a phase exit criterion) is not yet possible. The **observable** result-usage parity (session token/cost counters in `LegacyRunResult`) is fully proven by `test_golden_transcripts` (loop+graph). Loop-side emission must be added — guarded by `_usage_sink is None` so it stays a no-op for sink-less callers — before Task 10 opens Goal Runner G1 (which consumes the ledger). | `test_usage_event_sink.py` | Task 10 (or a scoped follow-up before G1) |
| PH35-FU-006 | **Closed by Task 8 (2026-06-29).** The graph consumes `iteration_budget` and enforces `max_iterations` at the `prepare_request` iteration boundary (the dead `apply_steer` gate was removed) and routes to a toolless summary on exhaustion. The recursion ceiling was **revised from measurement**: the per-iteration worst case (an iteration hitting the max api-retry / compression attempts) measured ~14 super-steps, so the original `max_iterations*12 + 100` (= 1180 at the default 90) sat *below* the realistic worst case `90*14 = 1260`; `engine.run_turn` now uses `max(2000, max_iterations*24 + 200)` (= 2360 at 90), validated by `test_recursion_limit_has_20pct_headroom` across every routed retry/compression/continuation family with >20% headroom. | `test_graph_budget_parity.py` | **done** |

**Task 9 status (2026-06-29):** Full dual-engine observable equivalence
implemented; committed locally, not pushed. The graph engine now reproduces the
loop's complete observable contract: all six load-bearing plugin hooks at the
same boundaries (FU-001), session token/cost accounting (FU-002), trajectory
writes (FU-003), and per-exit side-effect policy (cleanup / persistence /
interrupt-clearing / `post_llm_call` / `on_session_end`) via a frozen
`ExitPolicy` + `_finalize_turn` split. `_run_conversation_graph` now binds the
execution thread and self-heals stale interrupt state like the loop, replays the
compression lifecycle warning, and emits the loop's retry/fallback/compression/
budget/nous `_emit_status` lifecycle messages. `test_golden_transcripts` is
parameterised over `["loop", "graph"]` (both pinned to the same committed
snapshot, all 27 fixtures), `test_hook_invocation_parity` over both engines, and
a new `test_graph_differential_sequences` proves loop≡graph on 120 fixed-seed
generated sequences (text / known+unknown tools / steer / interrupt). The
interim `test_graph_equivalence_gaps` xfail cases were promoted to plain parity
assertions. The exit-contract line inventory was rebased (+5, from Task 8's
loop-side additions). One sub-item deferred: PH35-FU-007 (loop-side
`UsageEventSink` emission for a full per-exit ledger comparison).

**Closed by the 2026-06-29 review (commit pending):** *Tool-loop interrupt
parity* — the loop checks for a pending interrupt at the top of every iteration
(run_agent.py:9773) and breaks before the next API call; the graph had no such
check, so a Stop during tool execution would issue another transport call. Fixed
by an iteration-boundary check at the top of `prepare_request`; the graph now
ends the turn cleanly (interrupted=True, api_calls unchanged, no extra call),
covered by `test_graph_error_parity.py::test_graph_interrupt_in_tool_loop`
against the existing `interrupt.json` golden. Core parity only — the full
post-loop side effects on this exit remain PH35-FU-001/002.

**Process note — characterization gate was committed red.** Tasks 5/6 shifted the
`run_conversation` return-line positions and committed without re-running the
Task 2 gate: `test_exit_contract.py` and `test_exit_reachability.py` were
**failing at HEAD** (`ca6832f1`) when Task 7 began, despite the completion notes
asserting the gates passed. Line numbers were rebased in Task 7 (`0a8b7b8b`).
Both files hardcode the same 21 return-line numbers and will drift again on any
`run_agent.py` edit; if this keeps generating false alarms, derive the numbers
once via AST and assert on scenario *ordering* rather than absolute positions.

**Task 8 status (2026-06-29):** Exit-family parity complete, committed locally,
not pushed. 8a (budget consumption + max-iteration summary + recursion ceiling,
`0d15a7e5`), 8b (all six compression fixtures: 413 payload `4d5d6c30`, context
step-down / safe-output / cannot-compress / preflight `7c4b401e`), and 8c
(truncation/continuation: thinking budget, text continuation, truncated tool-call,
truncated json args, incomplete scratchpad) are done — 16 budget/compression/
truncation parity tests. The recursion-limit super-step measurement is done and
the formula was revised from evidence (PH35-FU-006 closed). **Task 8 complete.**
Next: Task 9 (finalization + full dual-engine equivalence — closes the remaining
PH35-FU-001/002/003/005 side-effect gaps).

**Task 7 status (2026-06-29):** Complete, committed locally (`0a8b7b8b`), not
pushed. Retry/fallback/interrupt/error parity. Invalid responses now retry to
exhaustion; interrupt-during-retry-wait reproduced via
`AIAgent._graph_backoff_with_interrupt`; the loop's real classifier is reused;
the live exception is carried on the adapter (not `TurnState`); a `first_attempt`
state field replaces the hidden `_retrying` flag. Full Phase 3.5 suite: 211
passed / 34 skipped, twice. Follow-ups PH35-FU-001..005 logged above.
