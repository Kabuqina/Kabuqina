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
- **Step 2 — providers** (`auxiliary_client` + `auth` → `providers/`): **DONE**
  (3116 → 2012, **−35%**, auth.py tail extraction).
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
  - [x] Began the `hermes_cli/auth.py` split: extracted the **auth-store
    persistence layer** (`_auth_file_path`, `_auth_store_lock`,
    `_load/_save_auth_store`, `_load/_save/_store_provider_state`,
    `read/write_credential_pool`, the `*_credential_source` suppression
    helpers, `get_provider_auth_state`, `get_active_provider`,
    `clear_provider_auth`, `deactivate_provider`, + the two `AUTH_*`
    constants) into `providers/auth_store.py`. `hermes_cli.auth` re-exports
    every name, so existing imports and the one monkeypatch of
    `_load_auth_store` (which targets `resolve_provider`, still in `auth.py`)
    keep working. Registry-coupled helpers (`is_known_auth_provider`,
    `get_auth_provider_display_name`, `is_provider_explicitly_configured`)
    stayed in `auth.py` — moving them would need `PROVIDER_REGISTRY` and
    create a circular import. Guarded by two new assertions in
    `tests/agent/test_provider_package_split.py`.
  - [x] Extracted the **registry-independent API-key helpers** into
    `providers/api_key_auth.py`: `has_usable_secret`, `_resolve_kimi_base_url`,
    `_resolve_api_key_provider_secret`, `detect_zai_endpoint`,
    `_resolve_zai_base_url`, + the `KIMI_CODE_BASE_URL` / `ZAI_ENDPOINTS` /
    `_PLACEHOLDER_SECRET_VALUES` constants (and the Kimi/Z.AI rationale
    comments). It imports the store primitives from `providers.auth_store` and
    only references `ProviderConfig` under `TYPE_CHECKING`, so there is no
    import cycle. The registry-coupled callers (`get_anthropic_key`,
    `resolve_api_key_provider_credentials`,
    `resolve_external_process_provider_credentials`) stay in `auth.py` and use
    the re-exported helpers. Guarded by two more assertions in
    `tests/agent/test_provider_package_split.py`.
  - [x] Extracted the **shared OAuth/JWT/timestamp leaf helpers** into
    `providers/oauth_helpers.py`: `_token_fingerprint`, `_oauth_trace(_enabled)`,
    `_parse_iso_timestamp`, `_is_expiring`, `_coerce_ttl_seconds`,
    `_optional_base_url`, `_decode_jwt_claims`,
    `_codex_access_token_is_expiring`. Stdlib-only, zero coupling to the CLI /
    registry / store, so any provider module can import them without a cycle —
    this unblocks the per-provider resolver moves. `hermes_cli.auth` re-exports
    them. (Lesson: the split guardrail only checks existence/identity; a missing
    `import hashlib` in the new module passed the guardrail but was caught by the
    functional smoke. Run a quick functional smoke of moved leaf helpers, not
    just the identity test.) Guarded by two more assertions in
    `tests/agent/test_provider_package_split.py`.
  - [x] Extracted **`AuthError` + `format_auth_error`** into the zero-dep leaf
    `providers/auth_errors.py` (`888ef30c`), so per-provider resolver modules can
    `raise AuthError` without a cycle back into the CLI facade. `hermes_cli.auth`
    re-exports both; `AuthError` stays a single class object across every
    importer (verified — `except`/`isinstance` safety).
  - [x] **Step 2 tail — nous + minimax runtime resolvers** (2026-06-22).
    Extracted the **nous** (~970 lines: device-code, agent-key mint, refresh,
    pool snapshot, `_default_verify`/`_resolve_verify` SSL helpers) into
    `providers/nous_auth.py` and the **minimax** (~268 lines: PKCE, user-code
    flow, token polling, refresh, runtime resolver, status) into
    `providers/minimax_auth.py`. `hermes_cli/auth.py` is now 3116 → 2012 lines
    (−35%), keeping only interactive `_login_*` / `*_command` functions, the
    `PROVIDER_REGISTRY`, and registry-coupled dispatchers. `_is_remote_session`
    stays (shared with login flows); `spotify` excluded (it's a tool, not an
    inference provider). Production callers (`runtime_provider.py`, `models.py`,
    `nous_subscription.py`, `managed_tool_gateway.py`, `credential_pool.py`)
    updated to import from `providers.nous_auth` / `providers.minimax_auth`.
    Test monkeypatch targets updated accordingly. Guarded by four new assertions
    in `tests/agent/test_provider_package_split.py` (17 nous + 7 minimax symbols).
    **Pending: `scripts/dev.ps1` runtime smoke gate** (unit tests pass: 152
    passed, 1 pre-existing GBK failure unrelated).
- [x] **Step 3 — `config.py`: DONE** (4597 → 683, **−85%**, `e470b41d`). Split into
  1 facade + 11 siblings: `config_defaults`, `config_env_schema`, `config_managed`,
  `config_home`, `config_env`, `config_merge`, `config_paths`, `config_loader`,
  `config_migrate`, `config_missing`, `config_custom_providers`, `config_validate`.
  `hermes_cli/config.py` is now a thin facade — re-exports + the 4 CLI commands
  (`show_config`/`edit_config`/`set_config_value`/`config_command`). Key technique:
  robust free-name analysis (defs+assigns+imports+builtins) before each slice;
  leaf-first down the dependency stack; one lazy import in `migrate_config` to
  break a top-of-stack cycle.
- [ ] **Step 4 — `run_agent.py`**: not started — and **scope reduced**: its core
  loop is the Phase-3.5 LangGraph re-platform target, so don't fully split it;
  extract only orthogonal keep-forever concerns + add characterization tests.
  See `2026-06-22-provider-deletion-plan.md` siblings / the restructuring phase
  model.

## Handoff — step 2 is DONE (apply pattern to step 4)

Current `providers/` layout (all committed):

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
  auth_store.py            auth.json load/save/update primitives
  api_key_auth.py          registry-independent API-key helpers
  oauth_helpers.py         shared OAuth/JWT/timestamp leaf helpers
  auth_errors.py           AuthError + format_auth_error
  nous_auth.py             Nous Portal runtime (device-code, refresh, mint, status)
  minimax_auth.py          MiniMax OAuth runtime (PKCE, poll, refresh, status)
  transports/              provider response normalization transports
```

Step 2 is complete. The `hermes_cli/auth.py` facade retains: interactive CLI
commands (`login_command`, `logout_command`, `_login_nous`, `_login_minimax_oauth`,
`_nous_device_code_login`, `_minimax_oauth_login`), the `PROVIDER_REGISTRY`,
registry-coupled dispatchers (`resolve_provider`, `get_auth_status`,
`resolve_api_key_provider_credentials`), and spotify (a tool, not a provider).

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
   That deletion is **now in progress** (it became tractable once the shared
   auth infra was extracted); its recipe, tiers, and checklist live in
   `2026-06-22-provider-deletion-plan.md` (`arcee` done as of 2026-06-22).
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

**Steps 1, 2, 3 are DONE.** Only step 4 remains in the overall split effort:

1. **Step 4 — `run_agent.py`** — *scope-reduced*: its core loop is the Phase-3.5
   LangGraph re-platform target, so **don't fully split it** — extract only
   orthogonal keep-forever concerns (usage/pricing, message persistence) + add
   characterization tests; leave the loop for the re-platform.

**Pending gate:** `scripts/dev.ps1` runtime smoke for the step 2 tail
(nous is on the live request path). Unit tests pass (152 passed, 1 pre-existing
GBK failure unrelated).

---

The config.py split (for reference / as the pattern for future big-file splits):

Slices done (each verified: import identity + functional smoke + test_config +
compat):
- `config_defaults.py` — the `DEFAULT_CONFIG` tree (`30d040bb`).
- `config_env_schema.py` — `ENV_VARS_BY_VERSION`/`REQUIRED_ENV_VARS`/`OPTIONAL_ENV_VARS` (`cd8811bc`).
- `config_managed.py` — managed-install + container detection (`281be9ad`).
- `config_home.py` — `~/.hermes` setup + file/dir security (`62ed4c0d`).
- `config_env.py` — `.env` read/write + env-only constants (`c1a5a66c`).
- `config_merge.py` — config-tree merge/normalize helpers below load_config (`5cdf8eea`).
- `config_paths.py` — `config.yaml` path resolvers + `save_config_value` (`7c576d42`).
- `config_loader.py` — the loader core `read_raw_config`/`load_config`/`save_config`
  + mtime caches + save banners (`2ba61288`). Landed cleanly: load/cache/save/
  reload + consumer smoke, 257 passed. `rp.load_config` monkeypatches keep working.

**Key finding — config.py is a dependency *stack*, not flat.** The pure-data
blobs were trivial leaves, but the functional clusters layer:
`config_managed` → `config_home` → `config_env` (.env IO), and a parallel
`config_merge` (tree transforms) — both feed `load_config`. Each layer must be
extracted before the one above it. **Lesson:** for these clusters, run a *robust*
free-name analysis that includes imported names + module-level constants before
extracting — the trivial defined-names scan misses `is_managed`,
`DEFAULT_SOUL_MD`, `Colors`, etc., causing false-start NameErrors. (Use the
per-function AST walk that unions defs+assigns+imports+builtins.)

The `load_config` *consumers* came out last (they import `load_config` from
`config_loader` — no cycle): `config_migrate` (~600 lines; its facade-resident
inspection helpers shared with the CLI are lazy-imported inside the function to
break a top-of-stack cycle), then `config_validate` + `config_custom_providers`
+ `config_missing` in one pass. The **CLI commands** (`show_config`,
`edit_config`, `set_config_value`, `config_command`) **stay** in the
`hermes_cli.config` facade by design.

Aspirational future shape: fold the 11 `config_*.py` siblings into a `config/`
package (`__init__.py` becomes the facade) — purely cosmetic, do only if wanted.

**Step-2 tail — DONE (2026-06-22):** extracted **nous** (~970 lines) into
`providers/nous_auth.py` and **minimax** (~268 lines) into
`providers/minimax_auth.py`. Interactive `_login_*` / `*_command` stay in
`auth.py`; `_is_remote_session` stays (shared with login flows);
`_default_verify`/`_resolve_verify` moved with nous. `spotify` excluded (it's a
tool, not an inference provider). Production callers updated to `providers.*`.
Pending: `scripts/dev.ps1` runtime smoke.

(historical) Earlier remaining list — now obsolete after deletion:
2. **Registry-coupled API-key resolvers** (`get_anthropic_key`,
   `resolve_api_key_provider_credentials`,
   `resolve_external_process_provider_credentials`) move only once
   `PROVIDER_REGISTRY` / `ProviderConfig` / `AuthError` are relocated (or via
   lazy imports) — currently kept in `auth.py` to avoid a cycle.

Keep `hermes_cli.auth` re-exporting each moved name.

## Non-goals

- No behavior changes during splits (pure moves + wrappers).
- Don't split cut/sea gateway platforms — delete (group ②) or defer (sea).
- Don't remove a wrapper in the same commit that introduces its new path.
