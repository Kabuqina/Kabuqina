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
| Gateway platforms | Profile allowlists are exact: `mainland_cn` keeps Weixin, QQ Bot, and DingTalk; `sea` keeps Telegram, WhatsApp, and Email. Desktop/Tauri is the product shell for both profiles, not a gateway adapter. WeCom, Feishu/Lark, Discord, all other built-in long-tail adapters, and bundled IRC/Teams platform plugins are deleted in v0.5. |
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

## STUDY four-layer learning pipeline (2026-07-01)

| Question | Decision |
|----------|----------|
| Four-layer mapping | Keep the existing deliverable path (`Read → Material Index → Deliverable Planner → File Writer`) and add a parallel learning path (`Read / Student State / Activity → Learning Index → Learning Planner → Output Writer`). Learning Index is deterministic and does not modify Material Index v1. |
| Planner architecture | Use a **lightweight `PlannerSpec` / registry**, not plain-function sprawl and not a second executor. Deliverable Planner (PPT/document specializations) and Learning Planner are siblings; the existing `AIAgent` loop still executes tools. |
| Contract authority | Learning artifact kinds, versions, lifecycle and review levels are single-sourced in shared-core `learning_contract.py`. The capability registry references stable ids and remains the product/readiness catalog; drift tests forbid duplicate vocabularies. |
| Review boundary | Deterministic validation always runs. Knowledge bases, learning plans, resource packs, batch flashcards and quizzes also receive prompt-based semantic review. AI-produced content is always a `draft` until a trusted UI/API or deterministic Gateway command activates it. Real user activity writes directly. |
| Writer architecture | Writer has two branches: existing **File Writer** and generic **Output Writer**. Output Writer validates discriminated per-kind payloads, versions and persists non-file learning artifacts; STUDY is its first consumer. A resource pack may fan out to both writers. |
| Persistence scope | Store learning state in a separate SQLite/WAL **`learning.db`** under the common Hermes root, organized by `owner_id + learning_space`. Do not extend per-profile `state.db`; a course workspace, not a chat session, is the durable scope. |
| Identity | Desktop and each Gateway platform user are isolated owners by default. Gateway ids use `gateway:<platform>:<hashed-user-id>`. Owner is runtime-injected through `LearningExecutionContext` and is never model-supplied; future account linking must be explicit. |
| Desktop/Gateway interaction | Draft creation is non-blocking and emits `learning.output.created`; do not reuse the blocking review interaction bridge. Gateway trust-boundary actions use deterministic `/study list/new/use/drafts/approve/reject` commands. |
| STUDY migration | Replace the copy-JSON/import main path with a shared draft inbox and a lifecycle UI (course setup → plan → tutor/learn → practice/review → evaluation/adjustment). Automatically import legacy localStorage per key, idempotently, and retain old data read-only for one release. |
| D5 lifecycle IA boundary (2026-07-16) | Lifecycle IA is a separate Web contract from H5/agent `UsageEvent`: exactly eight approved event names, with only enum `page`/`action`, boolean `success`, and coarse `count_bucket`. Collection is default-off and explicitly enabled in Settings; the current production sink stores bounded aggregate counts only in localStorage, performs no network/Tauri upload, clears aggregates on opt-out, and fails open. Any future upload endpoint requires a separate consent, retention, batching, and security review. |
| D5 legacy Web retirement (2026-07-16) | `/study/:spaceId/:page` is the only Study lifecycle UI. Retire `StudySection` and the full flashcard/quiz localStorage stores and learning helpers, while retaining Python migration diagnostics/export for rollback. The old profile, flashcard, and quiz keys have not completed their release-window gate, so their only remaining readers are isolated one-shot adapters: they forward bounded migration payloads, preserve old values byte-for-byte on failure, and clear a key only after the backend succeeds or confirms its idempotent marker. Final removal waits for post-A-R3 upgrade evidence. |
| Delivery strategy | Ship vertical slices: foundation; course space + flashcards; quiz; student state/evaluation/plan; knowledge/resources/tutoring/quality; lifecycle UI. Each slice must retain owner isolation, migration rollback and existing deliverable-Planner behavior. |
| M1 closure (2026-07-04) | M1 is closed as a candidate/data-spine foundation, not a user-facing STUDY UI. The `learning` toolset is enabled in desktop and gateway tool policies; `student-learning-foundation` stays `lifecycle: candidate` until the M2+ UI/execution surface exists; and envelope validation serializes and sizes the full `LearningOutputEnvelope`, so `source_refs` cannot bypass contract limits or JSON safety. |
| M2 closure (2026-07-04) | M2 is closed as the first user-facing STUDY slice. `flashcard_deck` remains an AI-created draft artifact; trusted desk/Tauri/Web paths activate or reject it, materialize active cards into `learning_items`, and write `flashcard.review` activities for real practice. The desktop API surface is `/api/desk/study/*`, Tauri exposes `cmd_study_*`, and web refreshes on `learning.output.created` via `study-learning-event`. Legacy `kabuqina.study.flashcards.v1` imports idempotently with migration id `localStorage:kabuqina.study.flashcards.v1`. M3 remains quiz-specific; Gateway `/study` commands remain M5. |
| M3 closure (2026-07-04) | M3 is closed as the durable quiz slice. `quiz` remains an AI-created draft artifact; trusted desk/Tauri/Web paths activate or reject it, materialize active questions into `learning_items` with `item_type=quiz_question`, and write `quiz.attempt` activities for real submissions. Scoring is deterministic: `choice` compares selected indexes, `true_false` compares booleans, and `short_answer` compares normalized text against `answer` plus `accepted`; semantic/LLM grading remains out of scope for M3. The desktop API adds `/api/desk/study/quizzes`, `/questions`, `/submit`, and `/migrations/quizzes`; Tauri adds `cmd_study_quizzes`, `cmd_study_quiz_questions`, `cmd_study_quiz_submit`, and `cmd_study_migrate_quizzes`; Web QuizPanel now uses backend drafts/active quizzes and refreshes on `study-learning-event`. Legacy `kabuqina.study.quiz.v1` imports idempotently with migration id `localStorage:kabuqina.study.quiz.v1`. Gateway `/study` commands remain M5. |
| Runtime alignment (2026-07-05) | During the Task 11 Step 4 soak, do not alter graph-engine contracts. The base learning conduct prompt remains shared core behavior, but the `kq-kp` trailer prompt is injected only for the desktop `hermesdesk` surface that strips/renders it; messaging gateways must not see raw fenced blocks. Learning-state observations such as "user is weak at X" go through the learning store/evaluation draft path, not memory. Usage events may carry cheap conduct metrics (assistant visible length, check-question ending, kq-kp emission, answer-then-teach proxy) as additive telemetry. |
| Tutor runtime L-0 contract (2026-07-19, review v3) | Structured Tutor is an explicit desktop learning activity, never inferred from ordinary Chat, and uses a separate `TutorGraphEngine` without changing the stateless Agent graph. Identity/API/DB keys are host-injected `(owner, space, activity_kind, activity_id)`; scoped idempotency stores an RFC-8785 request fingerprint and rejects mismatched replay. Resumable state lives in independent `tutor_runtime.db` v1, while a shared `learning_coordination.db` makes every desk/Gateway/cron `LearningStore` writer obey persistent owner/space operation fences and fixed lock order. Terminal rows persist completion basis, remediation count, and numeric budget truth before attempt rows are folded. v0.5 forbids in-place downgrade with Tutor data; its BundleV2 runtime-only merge restores Tutor state without replacing learning data created under v0.4. Provider calls use an SDK-retry-zero/fallback-zero single-attempt port with durable attempt/token/wall reservations, a 35-second call cap, finalize reserve, and a persisted 120-second active deadline. L-2 preserves the upstream completed-or-once-remediate topology through host-defined `continue/explain_again` controls and `participation_only` completion—never free-text correctness or mastery—while deterministic grading requires a pinned activated/builtin rubric and versioned provenance. BundleV2 keeps a uniform 24 MiB outer cap plus checkpoint/count subcaps. Learner checks remain isolated from tool approvals; Gateway Tutor remains out of v0.5 scope even though Gateway Study writes participate in the shared fence. Full contract: `docs/superpowers/plans/2026-07-19-v0.5.0-ctl-b01-tutor-runtime-design.md`. |
| Tutor lifecycle recovery/canonical hardening (2026-07-23) | Coordination schema stays v1. Each durable operation is paired with a content-free OS advisory sidecar lock held by its writer; only the desktop child scans at startup-before-handshake and every 30 seconds, and it may recover only a journal whose writer lock is free. Outbox pending-read → learning insert → runtime ack holds one owner-wide write guard. A terminal outbox event has one derived `tproj_<sha256(owner,space,kind,activity)>` identity and import accepts it only when terminal run, fixed event type/time, and the complete run-derived terminal/budget payload match; backup replay therefore cannot mint a second history event. `tutor_runtime_merge` checks post-merge owner/space/checkpoint/terminal/attempt/outbox quotas inside its single SQLite write transaction after subtracting exact duplicates. Bundle hashing is a shared Python/Rust canonical contract: recursive NFC for strings/keys, normalized-key collision rejection, sorted compact UTF-8, and integer-only numbers, proven by one shared fixture. These are B02 review hardening changes, not B03 Tutor graph activation. |

Full design: `docs/superpowers/specs/2026-07-01-study-four-layer-learning-pipeline-design.md`.

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
| PH35-FU-007 | **Closed (2026-07-01).** Usage attempt emission is engine-neutral through `AIAgent._record_usage_attempt`; loop and graph now emit matching success, auxiliary-summary, transport-error, invalid-response, and compression sequences. The sink remains a no-op when absent, preserving legacy result shapes. | `test_usage_event_sink.py` | **done** |
| PH35-FU-008 | **Closed (2026-07-02, `944f3433`).** A barrier-driven Anthropic fixture now holds the provider call in flight until a separate interrupter signals Stop, deterministically exercising the real `_interruptible_api_call` polling path without timing sleeps. `call_transport` handles `InterruptedError` as normal turn termination and routes through `_finalize_turn`, preserving the loop's rich result, trajectory, task cleanup, persistence, memory sync, interrupt clearing, and `on_session_end`. | `golden/interrupt_during_api.json`, `test_golden_transcripts.py` (loop+graph) | **done** |
| PH35-FU-009 | **Closed (2026-07-02, through `75c3c3e7`).** The graph now matches the loop across the empty/partial-response ladder, reasoning-only continuation, compression/context-overflow triggers, suspicious Ollama/GLM stops, Nous 401 remint, malformed responses, SafeWriter installation, and request-build failures. The complete `test_run_agent.py` slice passes under both engines (296 each), and the widened fixed-seed differential gate passes all 121 cases. | full dual-engine `test_run_agent.py`; targeted family tests; `test_graph_differential_sequences.py` | **done** |
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

**Task 10 status (2026-06-30):** The rollback-safe strangler selector landed.
`agent/engine_selector.py:resolve_agent_engine` resolves the engine once with
precedence explicit `AIAgent(agent_engine=...)` > `HERMES_AGENT_ENGINE` >
`agent.engine` (active-profile `config.yaml`, read through the HERMES_HOME-aware
`load_config`) > default `loop`. Invalid explicit/env values raise `ValueError`
(operator intent must fail loud); an invalid config value logs a warning and
falls back to `loop` so a bad user file never bricks startup. `config_defaults`
gains `agent.engine: "loop"` (deep-merged, no `_config_version` bump). `AIAgent`
resolves it once in `__init__` (`self.agent_engine`); the public
`run_conversation` is now a thin dispatcher that selects `_run_conversation_graph`
or the renamed `_run_conversation_loop` *before* any per-turn side effect and
never falls back across engines mid-turn (a post-tool graph failure returns its
own error rather than re-running the loop and duplicating effects). The Task 9
golden harness now drives `_run_conversation_loop`/`_run_conversation_graph`
directly so loop/graph parameterization is independent of the selector. The
broader `tests/run_agent` slice passes under `HERMES_AGENT_ENGINE=loop` (the
legacy-regression gate: 1274 passed; the 10 pre-existing env failures remain).
Under `=graph` the selector now lets the full loop unit suite run on the graph
(1253 passed / 32 failed) — beyond the 10 env failures, **22 graph-specific
edge-case equivalence gaps** surface that the Task 9 golden corpus and
differential fuzzer never reached; these are logged as **PH35-FU-009** and gate
the Task 11 default flip, not the selector. The fixed-seed differential fuzzer's
non-deterministic `interrupt` variant was removed (logged as PH35-FU-008); it now
passes deterministically (121×3 under xdist). Source-anchored tests
(`test_exit_contract`, `test_exit_reachability`,
and the five `inspect.getsource` checks in `test_run_agent`) were retargeted to
`_run_conversation_loop` and the 21 exit return lines rebased uniformly (+45) for
the dispatcher/selector inserted above the loop body. **G1 stays closed**: its
usage-event-sink prerequisite is PH35-FU-007 (loop-side emission), still open,
plus Goal Runner Tasks 1–6 and human review.

**Tasks 8/9/10 external review (2026-06-30) — NOT APPROVED; 5×P1 + 1×P2.** All
six verified against source. The Task 9 "full observable equivalence" claim was
overstated: it held only over the snapshot fields the golden harness observed,
and both that observation set and the differential fuzzer's input space were too
narrow, so genuinely divergent side effects passed silently.
- **P1-1** Graph turn-prefix incomplete: `_run_conversation_graph`/`initialize_turn`
  skipped `_restore_primary_runtime` (fallback stickiness on cached agents), todo
  hydration, scrubber reset, and the memory nudge.
- **P1-2** Graph finalizer (`_finalize_turn`) dropped `_sync_external_memory_for_turn`
  and the background memory/skill review; the golden snapshot didn't observe them.
- **P1-3** Aux-model usage event is fake: `summarize_on_budget` emits one
  `response=None` event (null usage/cost) for a real billed call.
- **P1-4** Retry usage event `attempt_index` duplicates (uses `api_call_count`,
  a per-model-turn counter, not transport attempts) → `[(0,err),(1,err),(1,err)]`.
- **P1-5** Differential fuzzer never generates unknown-tool / truncation /
  retryable-error turns — why it missed the 22 PH35-FU-009 gaps.
- **P2-6** `test_engine_selector` only tests the resolver, never constructs
  `AIAgent(agent_engine=…)` to prove dispatch + no cross-engine fallback; and it
  is **17 tests, not the "22" recorded** (a factual error in the Task 10 notes).
  **Resolved 2026-06-30 (Group D):** added three public-dispatch tests (bare
  `AIAgent` whose two engine bodies are stubbed) asserting `run_conversation`
  routes to `_run_conversation_graph`/`_run_conversation_loop` by
  `self.agent_engine` and that a graph exception propagates without re-running the
  loop; the count was corrected to **20** in the plan/cursor.

**Group A (P1-1 + P1-2) resolved 2026-06-30 — observe→fix→verify.** The golden
harness now records a `lifecycle_calls` snapshot field (counts of
`_restore_primary_runtime`, `_hydrate_todo_store`, scrubber reset,
`_sync_external_memory_for_turn`, `_spawn_background_review`, plus the
`_user_turn_count` delta). Re-recording the goldens from the loop (only that
field changed) turned the 27 graph cases red, proving the gap; the graph was then
brought to parity: `initialize_turn` now runs `set_session_context`,
`_restore_primary_runtime`, the non-anthropic dead-connection check, persist-arg
surrogate sanitize, todo hydration, `_user_turn_count++`, scrubber reset, and the
memory-nudge `_should_review_memory` decision; `prepare_request` increments
`_iters_since_skill` once per fresh non-exhausted iteration; `_finalize_turn`
runs the skill-nudge check, `_sync_external_memory_for_turn` (unconditional), and
the conditional background review — matching the loop's order and its
early-exit-vs-completion split (sync runs only on full completion, not early
exits). Deterministic gate (golden+exit+retry+hook+usage+differential) = 251
passed twice; loop unit tests unaffected (33 passed). The differential fuzzer now
also compares `lifecycle_calls` for free. Remaining: B (P1-3/P1-4 usage events),
C (P1-5 fuzzer breadth), D (P2-6 dispatcher test + miscount).

**Group B (P1-3 + P1-4, with PH35-FU-007 down payment) resolved 2026-06-30.**
Usage-event emission is now engine-neutral: `AIAgent._record_usage_attempt(outcome,
route, response)` builds the `UsageEvent` and forwards to the optional sink, using
a per-turn monotonic `_usage_attempt_index` (reset at turn start in both the loop
prefix and graph `initialize_turn`). The graph adapter's `_emit_usage_event`
delegates to it.
- **P1-4 fixed**: `attempt_index` no longer derives from `api_call_count` (a
  per-model-turn counter that made retries collide, e.g. `[0,1,1]`); it is the
  monotonic per-turn counter, so `exit_api_retries` now emits `[0,1,2,…]`.
- **P1-3 fixed**: the max-iteration summary's real usage is recorded inside
  `_handle_max_iterations` itself — one event per actual call (summary + optional
  retry), with the live response usage — and the graph's old single
  `response=None` emit in `summarize_on_budget` was removed. Verified: the
  `max_iterations` summary event now reports the real 150/14 tokens.
- **PH35-FU-007 (partial)**: the loop now emits the **success** attempt via the
  shared recorder (a strict no-op without a sink, so the default path and frozen
  result are untouched), and the aux summary path emits on both engines; loop and
  graph success events match for `plain_text`. **Remaining**: loop-side emission on
  the *error* paths (transport_error / invalid_response / compression) — the graph
  emits these but the loop does not yet, so full per-exit error-path ledger parity
  (the G1 prerequisite) is still open. Tracked under PH35-FU-007.
- The AST-derived exit-contract/reachability tests absorbed the loop-body line
  shifts automatically (no manual rebase — the 2026-06-30 refactor paying off).
Deterministic gate = 255 passed twice; four new usage tests
(`test_usage_event_sink.py`). Remaining review groups: C (P1-5), D (P2-6).

**Group C (P1-5) resolved 2026-06-30.** The differential fuzzer now generates the
required event families: a recoverable **unknown-tool** call (invalid-tool
self-correction), a retryable **5xx transport error** (recovers on the next
attempt), a **length-truncation** → text continuation, and an **empty/malformed
response** (retry/fallback). Three of the four passed immediately (parity from
Tasks 7/9). The truncation family **caught a real graph bug**: the graph's
plain-text completion used the raw content, while the loop folds in any
truncation-continuation prefix and applies `_strip_think_blocks(...).strip()`
(run_agent.py:12548-12554) — so a final response with think blocks or trailing
whitespace diverged (loop `"partial 72"` vs graph `"partial 72 "`). Fixed by
mirroring the loop's finalization at the graph's plain-text exit
(`process_response`). The widened fuzzer is now 121 passed (serial + xdist). This
is exactly the gap class P1-5 said the narrow fuzzer was hiding; one PH35-FU-009
item (the strip divergence) is closed by this fix.

**Group D (P2-6) resolved 2026-06-30.** Added three public-dispatch tests to
`test_engine_selector.py` (a bare `AIAgent` whose two engine bodies are stubbed):
`run_conversation` routes to `_run_conversation_graph`/`_run_conversation_loop`
by `self.agent_engine`, and a graph exception **propagates without re-running the
loop** (no duplicated side effects). The selector file is now **20 tests** (17
resolver + 3 dispatch); the earlier "22" was a miscount, corrected in the plan and
cursor.

**Review status: all 5×P1 + 1×P2 addressed across Groups A–D.** Still open before
G1/Task 11 (pre-existing, separately tracked): PH35-FU-007 error-path loop
emission, the rest of PH35-FU-009 (remaining graph edge-case gaps from the broader
unit suite under graph), and PH35-FU-008 (deterministic interrupt-during-API
fixture). Re-review recommended before approval.

**PH35-FU-007 RESOLVED (2026-07-01).** The legacy loop now emits usage events on
its error paths through the shared engine-neutral `_record_usage_attempt`, closing
the per-exit ledger asymmetry (previously only the success path emitted). Emission
points, each mirroring the graph's transport node / error handlers:
- `transport_error` at the top of the loop's `except Exception as api_error`
  (fires for every caught exception before classification/retry ≡ graph :13407);
- `invalid_response` gated on `response is None` inside the `response_invalid`
  block (the graph emits invalid_response only for None :13421; a non-None-but-
  malformed response is a separate loop/graph divergence left to PH35-FU-009);
- `compression` after the 413 payload compress + history reset (≡ graph :14112)
  and after the general context-overflow step-down compress (≡ graph :14207).
Placement decision: the loop's Anthropic 1M-tier context reduction also compresses,
but the graph has **no** compression handler for `long_context_tier` (its
`handle_transport_error` routes only `payload_too_large`→`_handle_payload_compression`
and `context_overflow`→`_handle_context_overflow`), so the loop intentionally does
NOT emit there — emitting would create a loop-only event. That the graph doesn't
model the 1M-tier reduction at all is a structural gap logged under PH35-FU-009.
Verified: loop≡graph usage-event sequences MATCH on 5 error fixtures
(exit_api_retries, exit_invalid_response, exit_nonretryable_client,
exit_payload_compression, exit_context_stepdown) via a new parametrized test in
`test_usage_event_sink.py`; differential fuzzer 121, loop unit suite 294,
usage/compression/exit 29. No-op without a sink → legacy result dicts untouched.
The initial implementation misplaced the context-overflow emission in the
Anthropic-tier branch; the parity probe caught the divergence (loop had 4×
transport_error, no compression) before commit. G1 blocker cleared; FU-008/009
remain.

**PH35-FU-009 triage (2026-07-01).** With the `_snapshot` test-rot fixed (Step 0)
and FU-007 landed, the clean signal is `test_run_agent.py` (the loop unit suite)
run under `HERMES_AGENT_ENGINE=graph`: **18 failed / 276 passed**. The 18 cluster
into 8 families, and most share ONE root — the graph adapter reproduced the loop's
happy path + major exits but not its deep retry/nudge/fallback ladders, and its
transport node checks only `if response is None` (:13417) where the loop uses
`validate_response` (None **or** malformed):
- **A. empty/malformed nudge ladder (5):** truly_empty (3× nudge → "(empty)",
  api_calls 4), succeeds_on_nudge, triggers_fallback, fallback_also_empty,
  emits_status. Root: graph's `process_response` plain-text path (:13602) finalizes
  empty content as `final_response=""` with no nudge-retry ladder.
- **B. partial stream recovery (2):** on_empty_stub, preempts_prior_turn_fallback.
- **C. reasoning-only / prefill (4):** reasoning_only ×3, kimi empty-reasoning replay.
- **D. compression trigger (2):** context_compression_triggered, minimax_delta_overflow.
- **E. retry-exhaustion returns error not crash (2):** invalid_response (empty
  `choices=[]` → "Invalid API response"; SHARES A's malformed-response root),
  build_api_kwargs UnboundLocal (graph's `prepare_request` calls
  `_build_api_kwargs` at :13367 **outside** any try/except, so a raise escapes
  uncaught instead of surfacing a failed result).
- **F. continuation boundary (1):** ollama_glm_stop_after_tools.
- **H. 401 credential remint (1):** nous_401_refreshes_after_remint_and_retries —
  the loop remints the token on a 401 and retries; the graph's error path does not
  yet reproduce the remint-and-retry.
- **G. SafeWriter install (1):** RESOLVED — the graph did not call
  `_install_safe_stdio()` (loop does at :9555); pytest swaps a fresh capture buffer
  per test so the __init__-time install is not observed. Added the call at the top
  of `_run_conversation_graph`. 6/6 pass on both engines; idempotent guard, cannot
  create a loop/graph divergence.
Sequencing: A + E.1 + B share the invalid/empty-response detection root, so the
next focused cycle is that shared machinery (detect malformed via `validate_response`,
wire the nudge/retry/fallback ladder into the graph) — it unlocks the largest
cluster at once. E.2 (build-error handling) and F are smaller, independent.

**FU-009 families E.1 + E.2 RESOLVED (2026-07-01).**
- **E.1** (test_invalid_response_returns_error_not_crash): the graph's transport
  node checked only `if response is None`, so a structurally malformed response
  (empty `choices=[]`) was mis-emitted as a successful attempt and crashed
  downstream. Fixed by validating with `agent._get_transport().validate_response()`
  (None **or** malformed → `_pending_invalid` → the existing `_handle_invalid_response`
  ladder → "Invalid API response after N retries"). This also closes the FU-007
  deferral: the loop's invalid_response usage emission is now **ungated** (fires for
  None or malformed alike), keeping loop/graph symmetric.
- **E.2** (test_build_api_kwargs_error_no_unbound_local): the graph called
  `_build_api_kwargs` at `prepare_request` :13367 outside any try/except, so a raise
  escaped uncaught. Wrapped it; on failure it stashes `_pending_exc`, emits the same
  `transport_error` usage event the loop does, and routes to `handle_transport_error`
  → `_handle_api_exception` (shared classifier) → non-retryable client error surfaces
  `str(exc)` ("bad messages") with `failed=True`, mirroring the loop.
Verified: TestRetryExhaustion 3 passed on both engines; FU-007 usage parity 12 passed.

**Family A/B/C scope note (2026-07-01).** Reading the loop's empty-response region
(:12360-:12580) shows it is NOT three independent families but ONE ~200-line block
covering, in order: partial-stream recovery (**B**), prior-turn-content shortcut
(housekeeping tools), post-tool empty nudge, thinking-only prefill continuation
(**C**), truly-empty retry ×3 (**A**), fallback provider, and the "(empty)" terminal
— all sharing `_empty_content_retries` / `_thinking_prefill_retries` /
`_post_tool_empty_retried` counters and a strict message-sequence contract
(tool→assistant("(empty)")→user(nudge)). The graph's `process_response` plain-text
path (:13602) currently finalizes empty content as `final_response=""` with none of
this. Porting it is the single highest-leverage FU-009 change (unlocks ~11 tests:
A 5 + C 4 + B 2) but also the highest-risk (hot path, easy to diverge on a counter
or message order), so it warrants its own focused cycle with per-sub-case
verification rather than being rushed alongside the smaller fixes.

**FU-009 families A/B/C RESOLVED (2026-07-02).** The graph adapter now mirrors the
loop's empty-response ladder in `process_response`, split into small commits:
- **B partial-stream recovery** (`8770d3a6`): if the transport returns an empty
  final stub after visible streamed content, the graph finalizes the stripped
  streamed text instead of falling through to stale tool-content or `""`.
- **C reasoning-only/prefill** (`23461009`): structured reasoning with no visible
  answer gets the loop's two `_thinking_prefill` continuations before it can enter
  the true empty ladder; graph `prepare_request` also copies strict-provider
  reasoning fields for API replay, fixing Kimi `reasoning_content=""`.
- **A/shared empty ladder** (`ef037c4b`): graph tool-call turns now preserve visible
  content attached to housekeeping tools, reuse that prior content on an empty
  follow-up, issue the loop-valid post-tool nudge sequence
  `tool -> assistant("(empty)") -> user(nudge)` for substantive tools, retry truly
  empty responses three times, activate fallback providers with a fresh counter,
  and finally persist/return the explicit `"(empty)"` terminal placeholder.
  Two parity tests pin the previously untested housekeeping shortcut and post-tool
  message-order contract.

Verification: targeted A/B/C set under `HERMES_AGENT_ENGINE=graph` = 14 passed;
same targeted set under the default loop = 14 passed. The fixed-seed differential
gate (`test_graph_differential_sequences.py`) was confirmed at 121 passed twice in
this handoff cycle; when local metadata lookups are slow, stubbing only the
metadata-network aliases in the test process avoids unrelated HTTPS latency while
leaving scripted transports unchanged. Full loop regression:
`test_run_agent.py -q -n 4` = 296 passed. Full graph slice:
`HERMES_AGENT_ENGINE=graph test_run_agent.py -q -n 4` = 292 passed / 4 failed; the
remaining failures are exactly the expected FU-009 D/F/H set:
`test_context_compression_triggered`,
`test_minimax_delta_overflow_keeps_known_context_length`,
`test_ollama_glm_stop_after_tools_without_terminal_boundary_requests_continuation`,
and `test_nous_401_refreshes_after_remint_and_retries`.

**FU-009 D/F/H RESOLVED; run_agent graph gaps closed (2026-07-02).**
- **D compression triggers** (`14632efe`): graph `dispatch_tools` now performs the
  loop's post-tool `context_compressor.should_compress(...)` check before the next
  API turn, carries the returned active system prompt forward, clears cached
  conversation history after compression, and emits the same compression usage
  event. Graph `_handle_context_overflow` also gained the MiniMax delta-only guard:
  MiniMax's `"context window exceeds limit (2013)"` reports an overflow amount,
  not the true window, so graph now keeps the known context length and compresses;
  non-MiniMax providers still probe down to the next tier.
- **F Ollama/GLM suspicious `stop` continuation** (`484c356a`): graph now calls the
  existing `_should_treat_stop_as_truncated(...)` helper before usage/post hooks and
  finalization. The narrow Ollama-hosted GLM post-tool pattern is reclassified as
  `length` and routed through the shared continuation handler; naturally terminated
  responses and non-Ollama providers remain unchanged.
- **H Nous 401 remint/retry** (`148ffd30`): graph now mirrors the loop's one-shot
  Nous Portal 401 recovery before generic credential-pool / non-retryable 4xx
  handling. A successful `_try_refresh_nous_client_credentials(force=True)` retries
  the same turn; a failed refresh falls through to the existing client-error path.

Verification: targeted family checks pass on both graph and loop (D compression
set 3/3, F Ollama/GLM stop set 3/3, H Nous 401 1/1). The full `test_run_agent.py`
slice now passes under both engines: `HERMES_AGENT_ENGINE=graph ... -q -n 4` =
296 passed / 300 warnings; default loop `... -q -n 4` = 296 passed / 296 warnings.
The differential gate was not rerun after D/F/H because it had already been
confirmed at 121 passed twice in the same handoff cycle and the user explicitly
called out that duplicate pass; before a default-engine flip or PR review, rerun
the agreed final gate set. **PH35-FU-009's `test_run_agent.py` graph-equivalence
signal is closed; Task 11 remains blocked by PH35-FU-008 and final review.**

**Task 10 re-review + Step 0 harness fix (2026-07-01).** The re-review APPROVED
the selector + Groups A–D (selector 20 passed; deterministic gate
differential+usage+exit = 131 passed). It also surfaced a regression the
Group A change left behind: `7cfce77d` added `lifecycle_calls` as a **required**
positional arg to `golden_harness._snapshot`, but only the canonical
golden/differential callers were updated — the older per-family parity replays
(`test_graph_protocol_parity._replay_graph/_replay_loop`, imported by
`test_graph_tool_parity`, `_error_parity`, `_budget_parity`) still called it with
10 args, so **those files had been red with `TypeError: _snapshot() missing
'lifecycle_calls'` on main since 2026-06-30**, unnoticed because the recorded
"deterministic gate 131 passed" measurement did not include them (the narrow-gate
risk materialising on the review's own gate). Step 0 fix: `lifecycle_calls`
made optional (`=None` → `dict(lifecycle_calls or {})`) — a clean revert of the
accidental signature break; the canonical replays still pass it explicitly and
own the lifecycle invariant, the per-family replays predate it and compare an
empty map on both engines. After the fix all six graph-parity files
(protocol/tool/error/budget/equivalence_gaps/plain_text) pass — 39+ tests green,
**no real divergence underneath the TypeError** (pure test-rot). Two compression
goldens (`exit_context_no_compression`, `exit_context_stepdown`) still fail on
**both** engines locally because the aux-provider status callback differs without
`OPENROUTER_API_KEY` — a pre-existing env failure, not a graph gap, excluded from
PH35-FU-009. Follow-up: the canonical deterministic gate should include the
`test_graph_*_parity.py` files so a shared-helper signature change can't silently
red them again. The clean PH35-FU-009 signal is the ~18 `test_run_agent.py`
loop-suite-under-graph divergences (empty/partial response, reasoning-only
prefill, compression trigger, 401 remint, continuation boundary, retry
exhaustion).

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
asserting the gates passed. Line numbers were rebased in Task 7 (`0a8b7b8b`) and
again +45 in Task 10 (`97ef7ac9`) when the selector inserted code above the loop.

**Resolved 2026-06-30 (Task 2 review):** the recommended fix landed. The two
files no longer hardcode return-line numbers. `EXIT_INVENTORY` is now an ordered
`(scenario_id, fixture)` list (source order is the contract); `loop_return_lines()`
derives the 21 returns from `run_agent.py` via AST at test time, and
`scenario_return_lines()` joins inventory→line by source-order position (with a
count assertion that fails loudly if a return is added/removed/reordered).
`test_exit_reachability` imports that mapping instead of duplicating it. Verified
drift-proof: inserting a line above the loop auto-shifts every derived line and
the gate stays green with no manual rebase (72 passed). Future `run_agent.py`
edits — including the Task 11 loop removal — no longer require a line rebase.

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

**Goal Runner G0 review remediation (2026-06-30; G1 remains closed).** The
post-merge review found seven P1 and two P2 issues. The repair branch binds a
loaded state's embedded `job_id` to its containing goal directory; publishes
immutable evidence from a fully serialized and fsynced same-directory temp file
using an atomic no-overwrite hard link; and treats `transition.json` as a WAL by
embedding the full `next_state`, so recovery finishes an already-decided state
commit instead of inventing a contradictory pause. Usage ledgers are complete
only when attempt indices are exactly zero-based/contiguous/unique and every
present amount is a non-negative finite `Decimal`. `last_evidence_hash` remains
the combined no-progress fingerprint, while the new optional
`last_artifact_hash` is the single comparison domain for
`content_hash_changed`; absent/non-file/out-of-root reported artifacts pause as
`invalid_artifact` and never create progress evidence. A verified candidate may
complete on the final permitted run, but an unfinished final run still pauses.
Goal IPC clears legacy prompt/status/delivery-error text, and legacy Tauri
toggle/delete commands reject `mode: goal` in the backend. These repairs do not
open G1; the G0 diff still requires a second human review after verification.

**Task 10 closure (2026-07-02).** The rollback-safe selector and its review
remediation are complete. The two equivalence follow-ups that blocked closure
are also closed: FU-009 covers the deep graph response/retry/provider ladders,
and FU-008 pins a real interrupt-during-API call with event synchronization and
routes it through the canonical finalizer. Fresh final gates: graph parity +
goldens 102 passed; fixed-seed differential 121 passed; selector/usage/exit
contracts 64 passed; `test_run_agent.py` 296 passed under graph and 296 under
loop. The approximate compression-token count in golden callback events is now
normalized because the system prompt embeds date/cwd; callback ordering and
attempt numbers remain pinned. Task 10 is closed locally on
`codex/fu009-empty-response-ladder`. The configured default remains `loop`;
changing it is Task 11 scope.

**Goal Runner G1 opened; Tasks 7–8 (2026-07-02).** The G1 review gate is open:
Goal Runner Tasks 1–6 pass with no `langgraph`/`graph_engine` imports, the
runtime-contract hardening was reviewed and merged, and Phase 3.5 FU-007/008/009
are closed. Task 7 connects iterations to the agent through the public
`AIAgent.run_conversation` seam via `GoalAgentWorker`: a fresh session and a
fresh injected `UsageLedger` per iteration, engine propagated explicitly, cost
measured from the ledger (never inferred from result keys) so any unpriced
attempt pauses; a missing `goal_report` is `report=None` (never read as "no tool
ran"); a pre-`run_conversation` exception is a safe infra failure while any
exception after entry is `ambiguous_external_effect=True`. `goal_runner.py` is
deliberately not imported by the worker (injection avoids a cycle). Task 8 adds
`mode: goal` behind a disabled `cron.goal_loop.enabled` gate: the nested,
validated goal spec persists under `job["goal"]` and agent/notify records stay
byte-identical; the `.tick.lock` acquisition is extracted verbatim into
`scheduler_lock.tick_lock` (unchanged scope) so a later control service can
share it; `tick`/`_process_job` branch by mode, running exactly one controller
iteration and mirroring its status via `mark_goal_job_run`/`mark_goal_job_crash`
(which never touch `repeat.completed`, `next_run`, or deletion), while a
disabled gate pauses with `feature_disabled` and invokes no model. The public
`cronjob` tool rejects `mode: goal` until G2 opens, though core `create_job`
accepts it for internal tests. `mark_goal_job_run` takes primitive fields rather
than a transition object to keep `jobs.py` free of goal-type imports.

**Task 11 default flip (2026-07-03).** After the release-equivalent Graph smoke
passed on both `chat_completions` and `anthropic_messages`, the release default
changed from `loop` to `graph`. The serialized default in
`hermes_cli/config_defaults.py` and the selector fallback in
`agent/engine_selector.py` change together so desktop, Gateway, raw-config, and
config-load-failure paths cannot disagree about the default. For one release,
operators can still select the legacy engine with `agent.engine: loop` in the
affected profile or with the higher-precedence `HERMES_AGENT_ENGINE=loop`, then
restart the affected app/child. This is a runtime rollback and does not migrate
or rewrite sessions. Existing files that already contain `engine: loop` remain
explicit Loop selections; restoring the new default means deleting that field
or changing it to `graph`. The desk runtime log now records the selector's
resolved value and passes that same value into `AIAgent`, so support evidence
cannot disagree with the engine actually used. The support procedure is documented in
`docs/troubleshooting.md` §19. Legacy-loop removal remains gated by Task 11's
Step 4 release acceptance and bounded Goal Runner A/B evidence.

**Task 11 Step 4 release acceptance (2026-07-08).** The owner replaced the
strict fixed-artifact 14-day soak interpretation with a v0.3.0 release
acceptance gate. v0.3.0 may ship with Graph as the default while the legacy
Loop escape hatch remains available. Step 4 closes only after the NSIS release
candidate, bundle/release smoke, and initial manual checks are recorded, and a
short post-release observation window of a few days finds no obvious
graph-attributable P0/P1 or unexplained result-shape, hook, persistence, or
usage drift. This is an explicit release-risk decision and must not be described
later as a completed 14-day fixed-artifact soak. Step 5 may begin only after
that Step 4 closure, followed by the required Goal Runner dual-engine evidence
or an explicit Goal Runner runtime-defer record.

**STUDY M1 foundation merge + kq-kp capture postfix (2026-07-05).** The
integration branch intentionally stops the data merge at M1: it brings in the
shared learning foundation (`learning_contract`, `learning.db`, owner/space
isolation, Output Writer, Learning Index, PlannerSpec, and the minimal
model-facing `learning` toolset) while preserving the immersive behavior M1
work from `main` (`LEARNING_CONDUCT_GUIDANCE`, `kq-kp` parsing/chips, and
conversational STUDY prompts). The only post-M1 vertical slice added before M2
is trusted single-card capture for kq-kp chips: UI clicks call
`POST /api/desk/study/flashcards/capture`, which writes one active
`flashcard_deck`, materializes one `learning_items` flashcard, and records a
`flashcard.capture` activity. Model tools still cannot activate or capture
cards directly.

Later M2 merge obligations:

1. `hermes_core/learning/flashcards.py`, `python/src/desk_server/routes/study_routes.py`,
   `tauri/src/study.rs`, and `web/src/chat/study/study-api.ts` now exist on the
   integration branch as capture-minimal versions. The M2 merge must union
   methods/routes/commands into these files, not replace them.
2. M2's legacy flashcard migration must dedupe by normalized front against
   existing `learning_items` before import; capture-created cards may predate
   the migration, and the branch migration route does not dedupe.
3. FlashcardPanel remains legacy until M2. Captured cards live in `learning.db`
   and are invisible to the review UI during this accepted dev-only gap.

**ACADEMY→REPORT + math into STUDY (2026-07-05, v0.3.0 structural move).** The
right-rail launchpad tab is renamed ACADEMY→REPORT (mode id `report`; the PPT
launchpad and visual-master picker stay unchanged — REPORT is task-mode work,
the answer-then-teach exemption zone). The math ability section moves into the
STUDY tab as「数学与代码」(Math & Code): math is a learning function, not a
conversion service. Its three prompts are rewritten to the STUDY conversational
contract (one question per turn, no fabrication, no emoji) and end with the
answer-then-teach hook — name the knowledge points involved and offer a variant
practice round (conversational only; the persisted exercise contract, sandbox
grader, and practice ladder are v0.4.0/v0.5.0 per
`docs/superpowers/specs/2026-07-05-study-math-code-practice-design.md`).
Frontend/prompt-layer only: no capability-registry change (the
`math-expression-engineering` ids stay candidates), no backend routes, no
engine change (soak-safe). `workspace.mathAbility` keeps its sectionId so
collapse preferences survive the move.

**Desk first-turn latency (2026-07-10).** `AIAgent` now accepts the
backward-compatible `include_session_start_time` flag (default `True`). The
desktop web child sets it to `False`: the live clock remains available through
`get_current_time`, while new desktop sessions share an identical stored system
prompt prefix and can reuse provider prompt caches. Desktop startup primes one
non-persistent, immediately-closed `AIAgent` in the background; optional load
packages are deferred until the first successful chat turn so multi-hundred-MB
downloads do not contend with onboarding or the first model request. The desk
stream log records agent initialization, time-to-first-token, total time, and
provider cache counters for release observation.

**Profile-aware capability disclosure (2026-07-10).** Non-CLI system prompts
derive their standard-capability statement from the agent's actual registered
tool names, rather than from a universal hardcoded list. This keeps
`mainland_cn` honest when `image_gen` is removed: the prompt explicitly says
image generation is unavailable and forbids fabricating a generated-image URL
or sending a hypothetical image to `vision_analyze`. Tool schemas remain the
source of truth for every profile and gateway.

**STUDY M4 state/evaluation/plan semantics (2026-07-10).** Exactly one active
`student_state` and one active `learning_plan` exist per owner/space; replacing
either archives the previous active artifact. `evaluation` stays evidence-based
and active-only for planning, with bounded `evidence_refs`; fixed ability or
personality labels remain forbidden. Plan tasks materialize as stable items,
while complete/skip are direct learner activities and are valid only once on an
active plan. H3 reads a fresh bounded Learning Index projection into the desk
ephemeral prompt without changing graph/loop contracts. LG6 is a tagged
`mode=notify` cron job: absent by default, dynamically counts due cards across
the persisted desktop owner's active spaces, suppresses zero-count delivery,
and is deleted on opt-out. Notebook UI remains D-track-owned. The default
production learning DB root is protected by an audited current-user ACL so WAL
sidecars inherit the same protection.

**STUDY B-2 practice grader residual-risk sign-off (2026-07-11).** The owner
accepted the v1 residual risks before QuizService dispatch was enabled:
learner code and user-activated model-authored tests run as the current OS user,
so absolute-path access, unrestricted network egress, process creation before
tree kill, and memory exhaustion before the timeout remain possible. The
grader uses isolated CPython, a temporary CWD, minimal environment, bounded
streams, hard timeout/tree kill, and a post-test randomized completion sentinel;
these are risk reductions, not a security boundary. `failure_summary` remains
UI-only; durable activity detail and all model-visible projections retain only
the fixed `failure_kind` classification.

**STUDY M6 lifecycle and governance boundary (2026-07-11).** Artifact collection
APIs are content-minimized, bounded summary projections (hard maximum 100) with
filtered totals and lifecycle counts. In particular, the legacy desktop
`/study/drafts` response no longer carries complete artifact metadata or an
envelope; callers fetch one artifact explicitly when its content is needed.
Wrongbook evidence is likewise bounded and excludes learner responses and
exception text. Learning-data portability uses a versioned owner bundle:
exports omit `owner_id`, imports force the runtime owner and run atomically only
against an empty owner scope, and deletion requires the exact destructive
confirmation phrase. Successful deletion is physical as well as logical:
SQLite `secure_delete` is enabled, then WAL is checkpointed/truncated, the DB
is vacuumed, and WAL is truncated again before success is returned. Migration
failures retain only bounded error type/message diagnostics, while `source_refs`
accept bounded scalar provenance fields rather than nested source-content dumps.

**Brand asset pipeline: Tier 2 private overlay (A-R1b, 2026-07-11).** New brand
artwork — starting with the v0.5 desk-scene assets (desk, bookstand, card box,
whiteboard lesson visuals) — is authored only in the private repository
`Kabuqina/kabuqina-mascot` and never enters the public monorepo. Official
builds inject the real assets through a build-time overlay step (env-var
pointed local checkout, load-package-style copy); without the overlay the
public repository builds a fully functional app with neutral unbranded
placeholder assets under the same filenames. The `Na_logo/` source tree
(masters, generator scripts, exports) moves to the private repository and is
untracked from public HEAD. Already-published artwork is explicitly NOT
recalled: the mascot art in git history, the six dual-marked inline code files,
and the CSS-rendered cup remain public under `LicenseRef-Kabuqina-Brand` legal
protection plus the owner's trademark track — Tier 2's technical moat covers
future artwork, not the past. Any new file that still embeds brand artwork in
code keeps the mandatory `LicenseRef-Kabuqina-Brand` SPDX marker. Implementation:
[Tier 2 overlay plan](docs/superpowers/plans/2026-07-11-brand-asset-tier2-overlay-plan.md).

**Goal Runner Pilot 1 host-only temporary activation (2026-07-12).** The owner
authorized one bounded Pilot 1 execution in the desktop host profile. Enable
only `%LOCALAPPDATA%\com.kabuqina.app\hermes-home\config.yaml` at
`cron.goal_loop.enabled`; gateway profiles remain disabled. The activation is
temporary, uses the already frozen `file`-only, local-delivery, 40-run/four-hour/
USD 5.00 task contract, and must be reverted after the pilot evidence is
captured. It neither makes Goal Tasks generally available nor changes the
default shipped configuration. Credentials remain confined to the desktop child;
the pilot harness must not copy or print them.

**Goal Runner Pilot 1 temporary activation outcome (2026-07-12).** The host
flag was restored to `false` after the initial bounded desktop wake. The initial wake
paused `cost_unknown` rather than treating absent pricing as zero; that exposed
the missing DeepSeek V4 Flash pricing mapping and was repaired before the
synthetic evidence run. A later synthetic graph/loop pair completed with
matching sanitized transitions, verifier outcomes, and artifact hashes. This is
not general enablement: the default and gateway profiles remain disabled pending
the separate Task 11 exit criteria and release smoke.

**Goal Runner Pilot 1 human-host outcome (2026-07-12).** The desktop-created
task `2eb49562f793` completed in the owner-selected disposable workspace after
one bounded recovery. Its first host wake paused with `invalid_artifact` while
cost accounting was complete: the worker reported a Windows absolute path for
an otherwise confined manifest. `00f3225c` accepts only absolute artifact paths
that resolve under the workdir and retains fail-closed rejection outside it.
After a desktop restart loaded that fix, iteration 2 completed with
`verified_complete`, verifier `pass`, complete accounting, and durable
artifact/evidence hashes recorded in the Goal Runner design. The host flag was
restored to `false` directly after each wake; gateway profiles stay disabled.
This is pilot evidence rather than an enablement decision; the explicit restart
cases are recorded below.

**Goal Runner Pilot 1 restart outcome (2026-07-12).** The three required host
restart cases are complete under the same temporary, default-false gate. A
scheduled task survived a desktop restart without a model call. An intentionally
interrupted in-flight task resumed only into `recovery_review`; it did not replay
the prior turn. A bounded sentinel-verifier test preserved its complete-ledger
`verification_failed` state, verifier outcome, and sanitized hashes through a
subsequent desktop restart. Test jobs were cancelled after observation, retaining
evidence. This closes the Task 10 pilot evidence, but is not a decision to
generally enable Goal Tasks or gateway execution.

**Goal Task gateway and write boundary remediation (2026-07-12).** Pilot 1
host-only creation treats `HERMESDESK_GATEWAY_PLATFORM` as the authoritative
desktop gateway-child marker, with the legacy `HERMES_GATEWAY_SESSION` retained
as a defense-in-depth signal. During a bounded Goal worker iteration, the
otherwise normal `file` toolset is constrained by an iteration-local policy:
only one `write_file` attempt to the `manifest_complete` verifier's configured
relative manifest is allowed; `patch`, all non-manifest writes, and writes for
templates without an approved manifest are rejected. The policy is a core
`ContextVar`, so concurrent workers cannot share permission state and desktop
overlays are not part of this safety boundary.

**PH35-FU-010 — post-removal cleanup/hook normalization (tracked 2026-07-12).**
After the dedicated legacy-loop removal is released, normalize the frozen
early-return cleanup, `post_llm_call`, and `on_session_end` behavior in a
separate behavior-change commit with explicit tests and release notes. This
follow-up is deliberately not bundled with loop deletion; it records Decision
4's outstanding normalization work before that deletion commit is permitted.

**Task 11 Step 5 legacy-loop removal (2026-07-12).** After the Step 4 release
acceptance and the bounded Goal Runner Pilot's recorded loop/graph evidence,
the legacy conversation loop, runtime selector, config/environment escape
hatch, and explicit-engine callers were removed in one dedicated commit. The
public `AIAgent.run_conversation` seam is graph-backed unconditionally. Golden,
exit, hook, persistence, usage, and fixed-seed replay contracts remain as
graph-only tests; the historical dual-engine pilot evidence is retained but is
not a supported runtime mode. This commit does not normalize graph cleanup or
hook behavior; that behavior remains scoped to `PH35-FU-010`.

**D-3 practice target disclosure boundary (2026-07-12).** Code `target_code`
and derivation `target_steps` are public only when the question explicitly uses
`mode: transcribe`. Derivation questions without a mode remain backward
compatible as `solve`; generated derivation transcriptions must persist
`mode: transcribe`. The learning contract rejects target fields on ordinary
questions, while `QuizService` also strips them defensively from the public
question wire when mode is not transcribe. This keeps the visible transcription
source available without allowing a normal quiz artifact to disclose its
answer through target-shaped fields.

**A-R3 canonical core and persistence identity (2026-07-14).** Kabuqina is now
the canonical installed/runtime identity: `kabuqina_cli`, the four
`kabuqina_*` core modules, distribution `kabuqina-agent`, console commands
`kabuqina` / `kabuqina-agent` / `kabuqina-acp`, `KABUQINA_HOME`, standalone
`~/.kabuqina`, and desktop `kabuqina-home`. The source-tree boundary remains
`hermes_core/` to preserve owned-fork lineage and avoid conflating a repository
path with an installed namespace. For the v0.4 compatibility release, old
Python imports and console aliases remain available; `KABUQINA_HOME` wins by
key presence and otherwise falls back to `HERMES_HOME`; standalone old-only
homes remain readable; desktop old-only `hermes-home` is atomically renamed,
with failure falling back to the old directory and both-exist preferring the
new directory without deletion. `state.db` and `learning.db` names/schemas do
not change, so home migration carries them intact. Credential Manager reads
service `Kabuqina` first, falls back only on an explicit miss to legacy service
`HermesDesk`, copies recovered secrets forward, and clears both services on
explicit sign-out. Secret values are never logged. Nous Hermes model names,
ChatML/tool-call protocol identifiers, upstream/legal/history references,
gateway owner IDs, and database schemas are deliberately unchanged. Removing
the one-release shims is a separate post-v0.4 task; no engine selector is
reintroduced under a new name.

**v0.4 updater trust-root reset (2026-07-17).** The updater private key used by
the pre-v0.4 release line is no longer recoverable, so v0.4 is the explicit
start of a replacement updater trust chain. Existing v0.2/v0.3 installations
must install v0.4 manually once; v0.4 embeds the replacement public key, and
v0.5 and later releases must remain signed by its retained encrypted private
key. The old `latest.json` channel is retired and must not receive new-key
artifacts; the replacement COS and GitHub endpoints use `latest-v2.json` so old
clients cannot be offered an update they can never authenticate. The encrypted
private key requires two independent recoverable copies, while its password is
stored separately in a password manager; CI secrets are delivery copies, not
the only backup. Local Tauri builds and release CI fail closed while the retired
public key remains configured, versions/endpoints disagree, or signing secrets
are absent. Because the public repository intentionally contains unbranded
placeholder assets, pushing a tag must not automatically build the official
installer. Official v0.4 artifacts are owner-built after applying the private
Tier 2 brand overlay; the GitHub workflow is manual-only and produces an
explicitly labeled unbranded CI candidate. The release operator creates the
official draft and uploads the owner-built signed artifacts separately.

**D-track closeout and legacy Study NSIS waiver (2026-07-17).** D-1 through
D-5 are closed after the post-A-R3 integration/review chain, the installed
current-data WebView2 round, Web components (23 files / 106 tests), focused Web
scripts, production/chunk checks, all three real bundled-runtime verifiers, and
Rust tests (97 passed / 0 failed). The owner explicitly chose not to run the
installed-NSIS upgrade matrix for pre-D5 profile/flashcard/quiz localStorage
fixtures. This is an accepted validation gap, not a passing result. The isolated
one-shot readers/adapters, preserve-old-key-on-failure behavior, migration
diagnostics, and failure export therefore remain part of v0.4. No future cleanup
may physically delete them until real old-app-data success/failure/restart/
idempotency evidence, including coexistence with A-R3 persistence migration,
has been collected. General installer, updater trust-root, and release-artifact
checks stay in the release runbook and do not reopen the D feature track.

**v0.5 gateway profile contraction (2026-07-17).** This decision supersedes
the gateway retention assumptions recorded on 2026-05-03 and in the v0.3
mainland pruning section above. Desktop/Tauri remains the product shell for
both profiles and is recorded separately from gateway adapters. The exact
external gateway allowlists are `mainland_cn = {weixin, qqbot, dingtalk}` and
`sea = {telegram, whatsapp, email}`. WeCom (including callback/crypto),
Feishu/Lark, Discord, SMS/Twilio, Slack, Signal, Matrix, Mattermost,
BlueBubbles, Home Assistant, Yuanbao, Webhook, API Server, and the bundled
IRC/Teams platform plugins are physical deletion targets; Git history is the
recovery path. Bundled `kind: platform` plugins do not receive a retention
exception merely because they register dynamically. DingTalk must be upgraded
off its legacy conflicting SDK/transport before mainland release, and SEA must
gain a real isolated profile implementation instead of falling back to the
mainland mapping. Removed credentials/profile data are not silently executed
or recursively deleted, and removed home-channel/cron targets are never
silently rerouted to another person or channel.

**CTL-C02 stop-producing boundary (2026-07-19).** The profile contraction is
enforced before state creation, not merely hidden in Web. The versioned
contracts are `kabuqina.platform-surface/v1` and `kabuqina.delivery/v1`.
`mainland_cn` admits only Weixin, QQ Bot, and DingTalk; `sea` admits only
Telegram, WhatsApp, and Email. An explicitly unknown profile admits no gateway.
Rust validates the profile/platform before migration, profile-directory writes,
QR launch, config save, or child spawn. Python messaging egress derives hosts
only from exact active-profile keys; wildcard `*_URL` discovery and removed
credential-derived hosts are forbidden. New cron/send targets outside the
active profile fail with `unsupported_delivery` before config/adapter/network
loading. Existing removed target text remains list/edit/delete capable, but
execution reports `unsupported_delivery` without rerouting; independent Core
usage without the desktop profile variable retains its legacy behavior.
Each Tauri gateway child receives the canonical product profile and one
platform identity. Its config is reconstructed with exactly that platform
instead of copying the host YAML verbatim, and Core repeats the filter after
all YAML/env/plugin inputs merge. Generic env upserts and every retained or
legacy config/QR producer validate the profile before writing, contacting an
OAuth endpoint, or launching a worker; read, remove, and cancel operations stay
available for legacy cleanup.
Physical adapter/dependency deletion remains CTL-C03/C04, retained-channel
readiness remains CTL-C06, and explicit legacy cleanup/upgrade remains CTL-C07.

**CTL-C03a Discord physical removal (2026-07-19).** The owned Discord adapter,
direct-send/admin tool, voice doctor, Discord-only tests/stubs, active messaging
route, CLI/toolset/config exposure, and model-tool schema branch are removed.
The core messaging extra and lock no longer contain `discord.py[voice]`;
`PyNaCl`, `audioop-lts`, and `davey` were removed mechanically as orphaned
dependencies. Fresh-runtime verification rejects the removed source paths,
Discord package/dist-info, and NaCl package/dist-info. Generic media,
transcription, TTS, voice-mode, session/thread fields, and retained platform
contracts remain. `Platform.DISCORD`, exact stale-config filtering, C02
unsupported-delivery tombstones, and stored legacy text remain compatibility
records only: they cannot register an adapter, open a network connection, or
reroute delivery. No credentials, profiles, sessions, jobs, channel-directory
files, or home targets are deleted; CTL-C07 owns explicit cleanup and upgrade
evidence. Other platform leaves and release approval remain independent gates.

**CTL-C03b Feishu/Lark physical removal (2026-07-23).** The owned Feishu/Lark
adapter, comment automation, document/drive tools, QR worker, Rust commands and
child state, Web route/settings/onboarding producers, Feishu-only tests and
active messaging route are removed. `lark-oapi` is removed from desktop
requirements, the Core extra/`all` extra and the mechanically regenerated
lock. Runtime pruning rejects the worker, adapter/comment/tool paths,
`lark_oapi` package and dist-info; source sync also removes those stale
artifacts from an existing developer runtime. Legacy `feishu_doc` and
`feishu_drive` toolset names are permanently denied as removed config input.
`Platform.FEISHU`, C02 unsupported-delivery behavior, stale config filtering
and stored old target text remain compatibility-only and cannot register an
adapter, expand network trust or reroute delivery. Existing credentials,
profiles, QR/comment state, sessions, jobs, channel-directory records and home
targets are not deleted. A fresh `build_bundle.ps1 -Verify` run remains a
mandatory operator-provided Gate artifact before C03b review/sign-off; CTL-C05,
C07 and G01 retain their separate closeout responsibilities.

C03b also freezes the bundle-completion contract: an in-place rebuild must
strictly replace the bundled Core and explicitly remove retired root artifacts
instead of merging over stale files. `BUNDLE_INFO.json` is the success
sentinel, is invalidated before mutation, carries `verified: true` only for a
successful `-Verify` run, and is written after pruning, runtime/profile/legacy
imports and STT executable checks pass. A failed verifier must never print or
leave a reusable completed-bundle marker.

**v0.5 desk step-scoped quiz checks (2026-07-23).** The production study desk
uses the existing Study repository, quiz service, activity store, and learning
event as its only submitted-learning truth. `QuizService.submit_attempt` and
the desktop HTTP/Tauri/Web bridge accept an optional `item_ids` subset: when
absent, the historical full-quiz behavior is unchanged; when present, the
service validates that every ID belongs to the quiz, preserves quiz order, and
grades and records only that subset. This prevents the desk's “check this
step” action from marking unanswered future questions wrong. Unsubmitted desk
answers and the current bookmark are a versioned local recovery cache only;
they are not learning evidence, do not replace Study persistence, and become
canonical only after the checked attempt is recorded by the backend. An
explicit `item_ids` subset must be a non-empty list of unique question IDs;
duplicates, unknown IDs, blanks, and invalid IDs fail before an activity is
written. After a check whose mapped verdict is `completed`, the submitted
answer is removed from the recovery cache before `STUDY_LEARNING_EVENT` is
emitted, while the visible answer and completed annotation remain mounted.
Incorrect or ungraded answers map to `needs_revision`, remain in recovery
storage, and continue to activate dirty-leave and `beforeunload` protection.
Unfinished input is persisted synchronously for refresh recovery; confirmed
in-app navigation preserves that recovery draft and says so explicitly.

**CTL-C03c WeCom physical removal (2026-07-23).** The owned WeCom bot,
callback listener/crypto, QR worker, Rust commands and child state, Web
route/settings/onboarding producers, direct-send/toolset/config branches,
WeCom-only tests and active messaging documentation are removed. Existing
`Platform.WECOM` and `Platform.WECOM_CALLBACK` enum values, exact stale-config
filtering, removed-toolset denial, unsupported-delivery records and persisted
credential/profile/QR/session/job/home text remain compatibility-only: they
cannot create an adapter, child, network allowlist or rerouted delivery.
Existing data is not recursively deleted; CTL-C07 owns explicit cleanup and
upgrade evidence.

Weixin is a retained, separate adapter and does not import WeCom callback
crypto. Its QR, account, media and crypto tests remain required after the
deletion. `cryptography`, `aiohttp`, `httpx` and `qrcode` remain shared
runtime dependencies because retained Weixin, QQ Bot, DingTalk or common
runtime paths still consume them; C03c removes only the WeCom dependency
edges. Runtime pruning and source sync reject all three retired Core WeCom
modules and the retired root QR worker. The owner authorized source
integration before bundle on 2026-07-24: a fresh `build_bundle.ps1 -Verify`
run on merged `main` remains operator-provided Gate evidence before final
sign-off, but no longer blocks merge. C04/C05/C07/G01 remain separate
controls.

**CTL-C04 long-tail platform removal (2026-07-24).** SMS/Twilio, Slack,
Signal, Matrix, Mattermost, BlueBubbles, Home Assistant, Yuanbao, gateway
Webhook/API Server, and the bundled IRC/Teams platform plugins are removed as
one owner-authorized integration batch. Their adapters, platform-only tools,
plugin source, dedicated tests/docs and exclusive dependency reachability are
deleted. Product platform discovery is now fixed: third-party plugins cannot
register or override a gateway platform, and adapter/config/toolset/cron/direct
send paths recognize only Weixin, QQBot, DingTalk, Telegram, WhatsApp and
Email. Removed enum values remain compatibility tokens solely to read and
reject old state; they do not create adapters, network trust or delivery
targets. Persisted credentials, sessions, jobs and home targets are not
deleted; CTL-C07 owns cleanup/upgrade. The owner reserved bundle execution, so
fresh integrated runtime, shared dependency/license/SBOM and distribution
proof remain CTL-C05/G01 gates rather than repeated C04 leaf bundles.

**CTL-C05 deterministic shared bundle inputs (2026-07-25).** The exact
retained profile set remains mainland `weixin`/`qqbot`/`dingtalk` and SEA
`telegram`/`whatsapp`/`email`. Desktop requirements directly declare the
Python packages imported by those retained paths (`aiohttp`, `certifi`,
`cryptography`, `qrcode`, and `python-telegram-bot`); DingTalk SDK selection
and its `websockets` conflict remain an explicit CTL-C06 readiness problem,
not a hidden optional import.

The retained WhatsApp bridge is now a build input. `build_bundle.ps1` runs
`npm ci` against the committed lock, caches the result by lock hash in the
machine-wide bundle cache, and copies both bridge source and `node_modules`
into the runtime. The adapter fails closed when that payload is missing and
never performs `npm install` at application runtime. This closes mutable,
network-dependent runtime installation without claiming that the system Node
executable or real WhatsApp transport is release-ready; CTL-C06 owns those
proofs.

Pinned CPython/Whisper archives and locked bridge dependencies use a shared
`%LOCALAPPDATA%\Kabuqina\bundle-cache` (or
`KABUQINA_BUNDLE_CACHE`) so worktrees do not download identical inputs again.
Every build emits `DEPENDENCY_INVENTORY.json` with the exact installed
Python/Node versions, input hashes and published license metadata. Tauri's
`Cargo.lock` is tracked from C05 onward so Rust resolution is reproducible;
fresh external advisory scans and final redistributed-file reconciliation
remain G01/Q checks against these frozen inputs.

The owner-provided C05 bundle passed on 2026-07-25 and C05 received reviewer
sign-off on 2026-07-26. The existing gyan.dev ffmpeg release URL remains
rolling and is not digest-pinned; its warning is accepted for the C05
functional/runtime gate but explicitly remains a G01/Q provenance blocker
before release approval.

**CTL-C06 retained transport readiness (2026-07-26).** This supersedes the
older DingTalk compatibility assumption recorded above: official
`dingtalk-stream==0.24.3` metadata accepts `websockets>=11.0.2`, the existing
lock resolves it with `websockets==15.0.1`, and the desktop runtime now directly
declares the exact Stream SDK plus `alibabacloud-dingtalk==2.2.42`. The
adapter does not publish a connected state until the SDK exposes its live
WebSocket; task creation alone is not readiness.

Five packages in that locked Alibaba closure are source-only releases. The
desktop build pins them to the existing lock, builds their `py3-none-any`
wheels once in a temporary directory, validates the full expected set, and
atomically publishes the result under the shared machine bundle cache. Runtime
dependency installation remains `--only-binary` and reuses that wheelhouse;
pip bootstrap/install failures stop before import verification so an incomplete
runtime cannot emit a misleading secondary missing-module diagnosis.

The retained WhatsApp bridge now runs on an application-owned Node.js 24.18.0
Windows x64 executable. Its official archive SHA-256 is pinned at build time;
the runtime carries only `node.exe`, the Node license and an exact version
marker, while npm remains build-time-only. Bridge installation uses that same
archive's npm, and the reusable cache identity includes the Node version so
native modules cannot cross ABIs. The dependency inventory hashes the
executable and license. Adapter, identity and bridge paths resolve the same
active `KABUQINA_HOME` session/cache locations. The one-release legacy session
reader remains non-destructive for C07; no session is copied, migrated or
deleted by C06.

QQ voice input no longer wraps unknown compressed bytes as invented raw PCM.
It uses QQ ASR, a real SILK/ffmpeg conversion path, or emits the existing
visible recognition-failure marker. The gateway child resolves the verified
bundle's `stt-bin/ffmpeg.exe` before an optional developer system fallback.
The rolling ffmpeg archive provenance remains G01/Q and is not reclassified as
closed by this behavioral repair.

C06 source/unit readiness does not impersonate external transport proof. The
single owner `build_bundle.ps1 -Verify` run completed successfully on `main`.
Profile-isolated real-account smoke for all six retained adapters cannot run
until the A-track product surface is complete, so the owner explicitly deferred
that matrix to post-A verification. It does not block the combined C06+C07
implementation sign-off, but remains mandatory before final release approval.
Installer, advisory, redistributed-license and final release approval remain
G01/Q.

**CTL-C07 explicit legacy-channel cleanup (2026-07-26).** v0.4 messaging
state is never silently mapped to a retained channel. Removed and unknown cron
targets remain raw, visible records and are labelled unavailable; non-delivery
edits and deletion remain possible, while execution continues through the
existing `unsupported_delivery` preflight. Unknown historical session platform
tokens are represented by an opaque persistence-only value instead of being
coerced to `local` or dynamically registered as a live `Platform`.

The desktop exposes one bounded legacy-data boundary. Inventory returns names,
paths and counts but no secret values. Cleanup requires an immediately
verifiable, content-addressed local export and the exact confirmation token;
an incomplete export or malformed JSON record fails before any rewrite.
Only the frozen exact env-key list, removed entries under known config/channel
maps, removed pairing rate-limit keys and a finite exact-file list can change.
Production cleanup contains no directory walk or recursive deletion. Jobs,
sessions, media, unknown files and old profile directories remain user-owned.
Legacy `QQ_HOME_CHANNEL{,_NAME}` values copy to their `QQBOT_` canonical keys
only during this explicit action and only when the canonical key is absent;
no other removed platform receives a replacement destination.

The v0.4 source fixture proves this source-level contract. Official installed
v0.4 → v0.5 update execution, final artifact provenance and uninstall behavior
remain CTL-G01/Q and are not claimed by C07.

The C06+C07 Gate review tightened that contract before sign-off. Shared
`TWILIO_*` credentials belong to the retained telephony skill and are never in
the removed-SMS cleanup allowlist. A cleanup export now authorizes exactly one
filesystem snapshot: every current cleanup candidate path and SHA-256 must
match the export immediately before the first mutation, and any added,
removed, replaced or changed candidate forces a new export. The Web control
also discards the stale authorization after any cleanup rejection.

WhatsApp's legacy `whatsapp/session` directory is no longer a write fallback.
If it is the only session tree, adapter initialization atomically renames the
whole opaque tree to `platforms/whatsapp/session`; if both trees exist, the
canonical tree is the only bridge write target and the legacy tree remains a
read-only identity fallback. QQ voice conversion likewise removes both its
temporary source and any partial generated WAV whenever all real decoders
fail.

**CTL-C06+C07 combined sign-off and smoke deferral (2026-07-26).** Independent
re-review closed all five implementation findings and directly verified the
successful integrated owner bundle. C06 and C07 are therefore `DONE` as one
C-track implementation work package. The six retained-platform real-account
smokes are a named post-A dependency, not a retroactive PASS and not a reason
to keep C-track merged code in REVIEW. They must be recorded before G01/Q can
approve the v0.5 release.
