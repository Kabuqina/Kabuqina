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
| License        | MIT                                                      |
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
| Hermes dashboard SPA | **Removed from product path.** Kabuqina shell is the only UI; `web_dist` is not bundled by default (`build_bundle.ps1 -BuildHermesDashboard` opt-in for upstream comparison). |
| Python boot | **`HERMESDESK_DESK_MINIMAL=1`** — lazy tool/plugin discovery, early `port.txt`, background warm thread; chat returns 503 `warming` until tools are ready. |
| Edge CDP | Starts **async** after bridge; does not block Python spawn. |
| Gateway | Unchanged in this pass (still optional second process). |

## Desk server split (2026-05-21)

| Question | Decision |
|----------|----------|
| Product HTTP API | **`python/src/desk_server/`** — Kabuqina-owned FastAPI app with `/api/desk/*`, `/api/sessions*`, `/api/hermesdesk/*`, slim `/api/status`. |
| Upstream `web_server.py` | **Dashboard-only.** Desk routes, HermesDesk auth bridge, and catalog code removed from `hermes_core/`. Optional `-BuildHermesDashboard` still builds `web_dist` for `hermes dashboard` dev comparison. |
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
| Rendering path | Structured `sections`/`blocks` → normalized PDF spec → same-name HTML source sidecar → ReportLab PDF renderer (`reportlab_pdf_v1`). |
| Supported content blocks | `heading`, `paragraph`, `bullets`, `table`, `code`, `formula`, `image_placeholder`, `page_break`. Unknown blocks fall back to paragraphs. |
| Capability model | Exposed as first-party `document-pdf-generation`; agents should call `pdf_write` for PDF deliverables and verify `path`, `html_path`, and `renderer` before claiming success. |
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
