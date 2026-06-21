# Large-File Split Plan (post-slim)

Date: 2026-06-21

## Progress

- **Step 1 — `document_tools.py`: completed, 2992 → 145-line facade.** Package
  `tools/document/` established; reading, PPTX, shared spec, PDF/HTML, and DOCX
  writers are separated.
  - [x] `schemas.py` — the 6 JSON tool schemas (commit `7c4abe02`).
  - [x] `common.py` — shared leaf helpers (`_text/_list/_string_list/_dict`) +
    spec/path/data primitives (`DocumentSpecError`, `_json`, `_validate_read_path`,
    `_desktop_workspace_root`, slide/block constants, `_PDF_TEMPLATES`)
    (commits `c429d658`, `5cfc2142`).
  - [x] `latex_render.py` — self-contained LaTeX→HTML formula renderer (commit `c429d658`).
  - [x] `reading.py` — the Docling reading pipeline + format readers (58 symbols,
    ~950 lines); `document_tools` re-exports the public read API; ~63 test
    references retargeted to `tools.document.reading` (commit `5cfc2142`).
  - [x] `pptx_writer.py` — the PPTX deck writer (17 symbols; the most independent
    writer, only `_validate_write_path` was shared → moved to `common.py`).
    Extraction is decorator-aware (preserves `@dataclass` on `_PptxTheme`) (commit `e27f8b64`).
  - [x] `pdf_write`/`html_write`/`docx_write` + the **shared spec core** they use
    (`_coerce_json_container`, `_repair_jsonish`, `_build_pdf_spec`, `_pdf_block(s)`,
    `_block_to_html`, `_normalize_pdf_template`) moved to `tools/document/spec.py`,
    `pdf_writer.py`, and `docx_writer.py`; `document_tools.py` remains a public
    registration/compat facade (commit `0cbd1816`).
  - Notes: (1) writers/readers are heavily monkeypatched by their tests; each
    extraction must retarget those patches/imports to the new module (as steps 1c/1d
    did). (2) AST symbol extraction must be **decorator-aware** (start at the first
    decorator line) or it silently drops `@dataclass`/`@lru_cache`.
- **Step 2 — providers** (`auxiliary_client` + `auth` → `providers/`): in progress.
  - [x] Established `providers/` package surface and moved the first provider
    slice mechanically:
    `agent/auxiliary_client.py` → `providers/chat_completions.py`,
    `agent/anthropic_adapter.py` → `providers/anthropic.py`,
    `agent/gemini_native_adapter.py` → `providers/gemini.py`,
    `agent/model_metadata.py` → `providers/model_metadata.py`,
    `agent/credential_pool.py` → `providers/credential_pool.py`,
    `agent/retry_utils.py` → `providers/retry.py`,
    `agent/error_classifier.py` → `providers/error_classifier.py`,
    `agent/image_routing.py` → `providers/image_routing.py`.
  - [x] Old `agent.*` paths are module-alias wrappers, so monkeypatches and
    imports still hit the same module object.
  - [x] Production imports in `run_agent.py`, `gateway/`, `tools/`, `hermes_cli/`,
    and nearby `agent/` modules now prefer `providers.*`.
  - [x] Moved the next provider-adjacent agent slice into `providers/` with
    alias wrappers:
    `agent/credential_sources.py` -> `providers/credential_sources.py`,
    `agent/nous_rate_guard.py` -> `providers/nous_rate_guard.py`,
    `agent/rate_limit_tracker.py` -> `providers/rate_limit_tracker.py`,
    `agent/image_gen_provider.py` -> `providers/image_gen_provider.py`,
    `agent/image_gen_registry.py` -> `providers/image_gen_registry.py`.
    Production imports now prefer the provider package for this slice too.
  - [x] Moved the transport layer package
    `agent/transports/` -> `providers/transports/`; the legacy
    `agent.transports` package aliases the provider package and its submodules
    so the registry remains single-copy for old import paths.
  - [ ] Deeper `hermes_cli/auth.py` provider/credential extraction remains.
- [ ] **Step 3 — `config.py`**: not started.
- [ ] **Step 4 — `run_agent.py`**: not started.

## Handoff — how to finish step 2 (then apply to steps 3-4)

Current `providers/` layout (after the completed step 2 slices, all committed +
pushed):

```
providers/
  chat_completions.py      OpenAI-compatible client selection + routing
  anthropic.py             Anthropic adapter helpers
  gemini.py                Gemini native adapter helpers
  model_metadata.py        model/provider metadata
  credential_pool.py       pooled credential discovery and routing
  credential_sources.py    credential-source removal contract
  retry.py                 retry helper utilities
  error_classifier.py      provider/API error classification
  image_routing.py         image input routing helpers
  image_gen_provider.py    image generation provider ABC
  image_gen_registry.py    image generation provider registry
  nous_rate_guard.py       shared Nous rate-limit guard
  rate_limit_tracker.py    rate-limit header parsing/display
  transports/              provider response normalization transports
```

**Remaining for step 2 — split provider/credential code out of
`hermes_cli/auth.py`.** The `agent/` provider-adjacent modules have been moved.
The remaining large-file work is the CLI auth surface: keep
`hermes_cli.auth` as the command/public facade, and move reusable
provider/credential mechanics into `providers/` modules in small slices.

Likely next extraction shape:

- `providers/auth_store.py` or `providers/credential_auth_store.py` — shared
  auth.json load/save/update helpers that provider runtime code can import
  without depending on CLI command wiring.
- Provider-specific auth helpers, only where they are reusable outside the CLI:
  e.g. Nous device-code state, Codex/OpenAI OAuth token readers, Qwen/Ollama
  credential readers.
- `hermes_cli/auth.py` keeps argparse/printing/interactive command behavior and
  delegates to the provider modules.

**Recipe for the remaining step 2 slice:**

1. **Inventory first.** Use `rg`/AST to separate CLI-only command code from
   reusable credential/provider helpers. Do not move UI prompts, command output,
   or argparse handlers into `providers/`.
2. **TDD guardrail.** Extend the provider package split/compat tests, or add a
   focused auth extraction test, before moving production code. Watch it fail on
   the new `providers.*` path first.
3. **Move one cluster only.** Prefer one cohesive cluster per commit (for
   example auth-store primitives before provider-specific OAuth flows).
4. **Keep old paths working.** `hermes_cli.auth` must re-export or delegate so
   existing CLI tests and monkeypatches keep hitting the same behavior.
5. **Verify auth/runtime coverage.** At minimum run the relevant
   `tests/hermes_cli/test_auth_*.py`, `test_non_ascii_credential.py`,
   `test_profile_export_credentials.py`, credential-pool tests,
   `tests/kabuqina/test_compat_imports.py`, and `python/tests/test_desk_server.py`.

Step 1's old document-writer handoff is now historical. Its completed layout is
captured in the progress section above; use the same wrapper+compat-test pattern,
not the old "remaining step 1" checklist.

Splitting only reorganizes — it does not reduce bundle size. Its payoff is
maintainability and (for step 2) unblocking the deferred provider deletion.

## Context

v0.3.0 slimming removed the upstream CLI (~42k lines: `cli.py`, `hermes_cli/{main,
setup,web_server,…}`), the global-cut plugins/skills, and the TUI/ACP/website
surface. With that gone, the remaining large files split into three very
different buckets — and **only one bucket should be "split".**

This plan re-grounds the splitting work on current line counts and points to the
existing refactor plan for the per-phase mechanics:
- Mechanics + per-phase recipes: `.qoder/specs/Core重构架构设计_task-eee.md`
  (facade-first, leaf-first, wrappers with explicit deletion conditions, test
  guards). Its Phase 7 "delete standalone CLI entrypoints" is now **done**.
- Product cuts already applied: `docs/superpowers/specs/2026-06-19-v0.3.0-slim-and-focus-plan.md`.

## Current large files (tracked `.py`, excl. tests), classified

| Lines | File | Bucket |
|---:|---|---|
| 14018 | `run_agent.py` | **SPLIT** — agent loop, hot path |
| 13006 | `gateway/run.py` | SPLIT (gateway, later) |
| 4780 | `hermes_cli/config.py` | **SPLIT** — heavily imported |
| 4748 | `gateway/platforms/yuanbao.py` | DELETE (cut gateway, group ②) |
| 4745 | `hermes_cli/auth.py` | **SPLIT** — provider/credential core |
| 4646 | `gateway/platforms/feishu.py` | SPLIT (kept gateway, later) |
| 4208 | `gateway/platforms/discord.py` | DEFER (sea) |
| 3833 | `agent/auxiliary_client.py` | **SPLIT** — provider core; unblocks provider deletion |
| 3479 | `hermes_cli/models.py` | SPLIT (secondary) |
| 3463 | `gateway/platforms/telegram.py` | DEFER (sea) |
| 3225 | `tools/skills_hub.py` | SPLIT (secondary) |
| 3157 | `gateway/platforms/base.py` | keep (shared gateway base) |
| 3145 | `tools/mcp_tool.py` | SPLIT (secondary) |
| 3053 | `tools/browser_tool.py` | SPLIT (secondary) |
| 2992 | `tools/document_tools.py` | **SPLIT** — student-critical, safe leaf |
| 2901 | `gateway/platforms/api_server.py` | DELETE (cut gateway) |
| 2703 | `gateway/platforms/slack.py` | DELETE (cut gateway) |
| 2676 | `gateway/platforms/matrix.py` | DELETE (cut gateway) |
| 2520 | `hermes_cli/tools_config.py` | SPLIT (secondary) |

Two reminders before splitting:
- **Don't split what's being deleted.** `yuanbao/api_server/slack/matrix`
  platforms (group ②, ~13k lines) are cut — delete them, don't restructure them.
  `discord/telegram` are sea-deferred. Finishing group ② shrinks `gateway/`
  more than splitting would.
- **Splitting does not reduce size** — it reorganizes for maintainability and to
  unblock follow-on work. The size wins are deletion (done) and group ②.

## Why split at all (the two real payoffs)

1. **Unblock the deferred provider deletion.** The global-cut providers
   (`bedrock`, `openai-codex`, `copilot-acp`, `opencode`, …) are entangled inside
   `agent/auxiliary_client.py` (3833) + `hermes_cli/auth.py` (4745) with the
   retained providers (`kimi`, `zai`, `minimax`, `alibaba`, …). Extracting these
   into a `providers/` package turns "surgery in a shared 3.8k-line file" into
   "delete a few provider files" — the v0.3.x provider-deletion item depends on it.
2. **Maintainability of the hot path + the student surface.** `run_agent.py`
   (14k) and `document_tools.py` (3k, the student PPT/report/docling path) are the
   files most in the way of ongoing work.

## Recommended split sequence

Leaf-first, lowest-risk-first (matches the refactor plan's ordering). Each step is
a separate branch; keep the old import paths working via thin wrappers until all
internal callers move; the kabuqina compat guardrails stay green throughout.

1. **`document_tools.py` → `tools/document/{pdf_writer,pptx_writer,docx_writer,templates}.py`**
   (refactor Phase 2). Safest, highest product value (student docs). Establishes
   the wrapper+test pattern. `document_tools.py` stays as a re-export shim.
2. **`auxiliary_client.py` + `auth.py` → `providers/` package** (refactor Phase 3):
   `base`, `chat_completions`, `anthropic`, `gemini`, `model_metadata`,
   `credential_pool`, `retry`, `error_classifier`. **Strategic** — afterwards each
   cut provider is its own file, so the deferred provider deletion becomes
   file-level. Touches the live request path → runtime smoke required (refactor
   Phase 3 Step 4).
3. **`config.py` → `config/{loader,env_loader,paths,profiles,models}.py`**
   (refactor Phase 4). Heavily imported by desk_server/runtime; keep
   `hermes_cli.config` re-exporting. Split `load_config`/`save_config` first.
4. **`run_agent.py` → `agent/{loop,tool_dispatch,message_manager,response_handler,openai_client,usage}.py`**
   (refactor Phase 5). **Last** — hottest path, monkeypatch/lazy-import sensitive.
   One extraction per commit; runtime smoke after each. `AIAgent.run_conversation`
   stays the public method delegating to the new loop.
5. **Secondary, as capacity allows**: `tools_config.py`, `models.py`,
   `browser_tool.py`, `skills_hub.py`, `mcp_tool.py`, and `gateway/run.py` (after
   group ② deletes the cut platforms it dispatches).

## Guardrails (every step)

- Keep old import paths as wrappers; **don't** combine a behavior change with a
  file move (refactor plan Execution Notes).
- After each step: `hermes_core/tests/kabuqina` (compat guardrails),
  `python/tests/test_desk_server.py`, the target's own tests, then
  `python -m unittest discover` (desktop). For steps 2 and 4 also run a
  `scripts/dev.ps1` runtime smoke (chat + one file/web/document tool) — unit tests
  pass while a circular import or missed wrapper breaks a live conversation.
- The compat guardrail test (`test_compat_imports.py`) must stay green; a red here
  means a split broke a retained import.

## Current continuation point

Continue with the remaining **step 2** work: extract the reusable
provider/credential mechanics still embedded in `hermes_cli/auth.py` into
`providers/`, while keeping `hermes_cli.auth` as the CLI-facing facade.

## Non-goals

- No behavior changes during splits (pure moves + wrappers).
- Don't split cut/sea gateway platforms — delete (group ②) or defer (sea).
- Don't remove a wrapper in the same commit that introduces its new path.
