# Large-File Split Plan (post-slim)

Date: 2026-06-21

## Progress

- **Step 1 — `document_tools.py`: in progress, 2992 → 1519 lines (-49%).** Package
  `tools/document/` established; the read/write halves are separated.
  - [x] `schemas.py` — the 6 JSON tool schemas (commit `7c4abe02`).
  - [x] `common.py` — shared leaf helpers (`_text/_list/_string_list/_dict`) +
    spec/path/data primitives (`DocumentSpecError`, `_json`, `_validate_read_path`,
    `_desktop_workspace_root`, slide/block constants, `_PDF_TEMPLATES`)
    (commits `c429d658`, `5cfc2142`).
  - [x] `latex_render.py` — self-contained LaTeX→HTML formula renderer (commit `c429d658`).
  - [x] `reading.py` — the Docling reading pipeline + format readers (58 symbols,
    ~950 lines); `document_tools` re-exports the public read API; ~63 test
    references retargeted to `tools.document.reading` (commit `5cfc2142`).
  - [ ] Writers (`pdf_write`/`pptx_write`/`docx_write`/`html_write` + their
    `_build_*_spec`/`_render_*` helpers) remain in `document_tools.py` (~1519 lines).
    Optional further split into `writers/` (per-format) if the file stays unwieldy.
  - Note: reading is heavily monkeypatched by its tests; any further reader split
    must retarget those patches/imports to the new module (as step 1c did).
- [ ] **Step 2 — providers** (`auxiliary_client` + `auth` → `providers/`): not started.
- [ ] **Step 3 — `config.py`**: not started.
- [ ] **Step 4 — `run_agent.py`**: not started.

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

## Recommended starting point

**`document_tools.py` (step 1)** — safe, student-relevant, and it proves the
wrapper+test loop before touching the provider core or the agent hot path. If the
goal is to unblock the provider deletion sooner, start instead with **step 2
(`providers/` extraction)** and accept the higher verification cost.

## Non-goals

- No behavior changes during splits (pure moves + wrappers).
- Don't split cut/sea gateway platforms — delete (group ②) or defer (sea).
- Don't remove a wrapper in the same commit that introduces its new path.
