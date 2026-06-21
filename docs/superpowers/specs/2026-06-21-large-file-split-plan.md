# Large-File Split Plan (post-slim)

Date: 2026-06-21

## Progress

- **Step 1 — `document_tools.py`: in progress, 2992 → 1102 lines (-63%).** Package
  `tools/document/` established; reading and the PPTX writer are separated.
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
  - [ ] `pdf_write`/`html_write`/`docx_write` + the **shared spec core** they use
    (`_coerce_json_container`, `_repair_jsonish`, `_build_pdf_spec`, `_pdf_block(s)`,
    `_block_to_html`, `_normalize_pdf_template`) remain in `document_tools.py`
    (~1102 lines). These three share a document/blocks normalization layer, so the
    clean split is a `writers/spec.py` (shared) + thin per-format writers — more
    entangled than PPTX was.
  - Notes: (1) writers/readers are heavily monkeypatched by their tests; each
    extraction must retarget those patches/imports to the new module (as steps 1c/1d
    did). (2) AST symbol extraction must be **decorator-aware** (start at the first
    decorator line) or it silently drops `@dataclass`/`@lru_cache`.
- [ ] **Step 2 — providers** (`auxiliary_client` + `auth` → `providers/`): not started.
- [ ] **Step 3 — `config.py`**: not started.
- [ ] **Step 4 — `run_agent.py`**: not started.

## Handoff — how to finish step 1 (and apply to steps 2-4)

Current `tools/document/` layout (after 5 extractions, all committed + pushed):

```
document_tools.py  1102  pdf/html/docx writers + shared spec core + registration
reading.py         1015  Docling reading pipeline + format readers
pptx_writer.py      465  PPTX deck writer
schemas.py          403  the 6 JSON tool schemas
common.py           162  shared leaf helpers + spec/path/data primitives
latex_render.py     148  LaTeX -> HTML formula renderer
```

**Remaining for step 1 — split the pdf/html/docx writers.** Unlike PPTX (16/17
exclusive), these three share a document/blocks normalization layer, so the clean
shape is:

- `writers/spec.py` (or `document/spec.py`) — the **shared spec core** (reached by
  ≥2 of pdf/html/docx): `_validate_write_path` (already in `common`),
  `_normalize_pdf_template`, `_pdf_block`, `_pdf_section_blocks`, `_pdf_blocks`,
  `_repair_jsonish`, `_coerce_json_container`, `_document_spec_error`,
  `_build_pdf_spec`, and `_block_to_html` (pdf+html). Plus `_build_pdf_html` /
  `_build_standalone_html`.
- `pdf_writer.py` — `pdf_write`, `html_write` (they share the HTML build),
  `_render_pdf_from_html`, `_render_pdf_with_reportlab`, `_wrap_pdf_text`,
  `render_pdf_from_html_source`.
- `docx_writer.py` — `docx_write`, `_docx_add_block`, `_render_docx`.

**Proven recipe (used for reading + pptx):**

1. **Partition with AST.** Compute each public entrypoint's transitive closure of
   local symbols; symbols reached by ≥2 entrypoints are the shared core, the rest
   are per-format exclusive. Verify no cross-cycle.
2. **Surgery script.** Extract symbol source verbatim into the new module(s);
   remove from `document_tools.py`; re-export the public functions
   (`pdf_write`/`docx_write`/…) back into `document_tools` for the registration
   block + `desktop_entrypoint`.
3. **Migrate tests** (`tests/tools/test_document_tools.py`): retarget every
   reference to a *moved internal* symbol from `document_tools` to the new module —
   three forms: `document_tools._X` (calls), `setattr(document_tools, "_X", …)`
   (monkeypatch), and `from tools.document_tools import _X` (direct import). Public
   re-exported names (`pdf_write`, etc.) stay as `document_tools`.
4. Verify: `py_compile`, an import smoke (registration runs), `test_document_tools`,
   the kabuqina compat guardrails, and `test_desk_server`.

**Three gotchas (each cost a debug cycle here):**

1. **Decorator-aware extraction.** `ast` `node.lineno` is the `def`/`class` line,
   *not* the decorator. Start the source range at `min(d.lineno for d in
   node.decorator_list)` or you silently drop `@dataclass`/`@lru_cache`.
2. **Import the full `common` surface into each new module.** The local-symbol AST
   analysis does NOT see dependencies on already-*imported* names (e.g. PPTX uses
   `_validate_read_path`, which moved to `common` in a prior step, so it wasn't
   flagged as a local dep). Import all of `common`'s public symbols to be safe.
3. **`logger` is per-module.** Don't move it; give each new module its own
   `logger = logging.getLogger(__name__)`.

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

## Recommended starting point

**`document_tools.py` (step 1)** — safe, student-relevant, and it proves the
wrapper+test loop before touching the provider core or the agent hot path. If the
goal is to unblock the provider deletion sooner, start instead with **step 2
(`providers/` extraction)** and accept the higher verification cost.

## Non-goals

- No behavior changes during splits (pure moves + wrappers).
- Don't split cut/sea gateway platforms — delete (group ②) or defer (sea).
- Don't remove a wrapper in the same commit that introduces its new path.
