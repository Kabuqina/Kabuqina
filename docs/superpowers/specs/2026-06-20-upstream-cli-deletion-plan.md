# Upstream CLI Deletion Plan (v0.3.x slim completion)

Date: 2026-06-20

## Progress

- [x] **Step 1 — Resolve the knot** (2026-06-20, commit `5cdb5c01`). `hermes_cli/gateway`
  is deletable; gateway runtime never imports it. Benign.
- [x] **Step 2 — Sever the cheap hooks** #1, #2 (2026-06-20, commit `5cdb5c01`).
  `save_config_value` → `hermes_cli/config.py`; dropped delegate's `CLI_CONFIG`
  branch. Audit confirms both `→ cli` hooks gone. Verified green.
- [ ] **Step 3 — Relocate `setup` console helpers**; repoint `dingtalk_auth` &
  `nous_subscription`; decide the Nous subscription feature.
- [ ] **Step 4 — Delete `hermes_cli/gateway`** (+ remove the lazy import in `profiles.py`).
- [ ] **Step 5 — Re-run the audit**; confirm cluster unreachable.
- [ ] **Step 6 — Per-module dynamic-reference check** (`importlib`/string imports).
- [ ] **Step 7 — Bulk-delete** the cluster + tests, grouped commits + verify each.
- [ ] **Step 8 — Rebuild the bundle**; confirm the ~42k-line reduction + smoke.

## Why

The v0.3.0 slim pass deleted global-cut plugins (~4.2M) and skill categories
(~9.5M). A reachability audit then showed the **single biggest remaining slim is
the upstream Hermes CLI**: ~42,000 lines of `cli.py` + `hermes_cli/*` that are
**bundled into the shipped runtime but never used by the desktop product**. The
desktop launches `python/src/desktop_entrypoint.py` → `desk_server` + a small set
of `hermes_cli` modules (`config`, `tools_config`, …); it never invokes the
`hermes` CLI, the TUI, or the upstream dashboard.

Deleting this cluster is the natural completion of the slim. It is **not** a bulk
`rm` — the retained runtime is woven into the cluster through a small, now-known
set of hooks that must be severed first.

This plan is the executable output of that audit. Related:
- `docs/superpowers/specs/2026-06-19-v0.3.0-slim-and-focus-plan.md` (slim plan)
- `.qoder/specs/Core重构架构设计_task-eee.md` (refactor: Phase 4 config/web_server
  split, Phase 7 "delete standalone CLI entrypoints")

## Audit method

`scripts/_audit_cli_reachability.py` (committed alongside this plan so step 5 can
re-run it) does a static AST import trace from the real runtime entrypoints (`run_agent`, `gateway.run`,
`cron.scheduler`, `toolsets`, `tools.registry`, and the `hermes_cli` modules
`desk_server` imports directly). It walks **all** import statements, including
lazy imports inside functions, so it is conservative: any module imported
anywhere in a reachable module is treated as kept.

To find what is deletable, the four CLI entrypoints (`cli`, `hermes_cli.main`,
`hermes_cli.setup`, `hermes_cli.web_server`) are marked "blocked" (not
traversed), simulating their removal. Whatever then becomes unreachable is the
deletable cluster; every edge from a still-reachable module into a blocked/
deletable module is a "hook to sever".

Caveat: the trace is static, so it cannot see `importlib.import_module(<string>)`
dynamic imports. Before deleting each module, re-grep its name across the repo to
confirm no dynamic/string reference remains.

## Deletable cluster (~42,087 lines, 32 modules)

Unreachable once the hooks below are severed. Line counts from the audit:

| Lines | Module | Note |
|---:|---|---|
| 11643 | `cli.py` | upstream interactive CLI (god-module) |
| 10276 | `hermes_cli/main.py` | argparse CLI dispatcher |
| 3509 | `hermes_cli/web_server.py` | upstream dashboard server (desk_server replaced it) |
| 3374 | `hermes_cli/setup.py` | CLI setup wizard |
| 1594 | `hermes_cli/skills_hub.py` | CLI `/skills` slash handler |
| 1423 | `hermes_cli/doctor.py` | `hermes doctor` |
| 926 | `hermes_cli/backup.py` | CLI backup |
| 795 | `hermes_cli/claw.py` | openclaw migration CLI |
| 778 | `hermes_cli/mcp_config.py` | `hermes mcp` (also the `mcp_serve` hook) |
| 677 | `hermes_cli/auth_commands.py` | `hermes auth` command wiring (NOT `auth.py`) |
| 635 | `hermes_cli/banner.py` | CLI banner art |
| 548 | `hermes_cli/voice.py` | already orphaned (unreachable even before blocking) |
| 530 | `hermes_cli/status.py` | `hermes status` |
| 481 | `hermes_cli/clipboard.py` | CLI clipboard |
| 481 | `hermes_cli/uninstall.py` | `hermes uninstall` |
| 457 | `hermes_cli/memory_setup.py` | CLI memory setup |
| 385 | `hermes_cli/hooks.py` | CLI shell hooks |
| 373 | `hermes_cli/_parser.py` | argparse builder |
| 361 | `hermes_cli/fallback_cmd.py` | |
| 331 | `hermes_cli/oneshot.py` | |
| 315 | `hermes_cli/completion.py` | shell completion |
| 300 | `hermes_cli/azure_detect.py` | already orphaned |
| 299 | `hermes_cli/cron.py` | `hermes cron` **CLI** (NOT runtime `cron/scheduler.py`) |
| 274 | `hermes_cli/webhook.py` | `hermes webhook` CLI (webhook gateway is global-cut) |
| 242 | `hermes_cli/callbacks.py` | |
| 239 | `hermes_cli/pty_bridge.py` | |
| 235 | `hermes_cli/curator.py` | |
| 152 | `hermes_cli/slack_cli.py` | slack CLI (slack is global-cut) |
| 149 | `hermes_cli/relaunch.py` | |
| 97 | `hermes_cli/pairing.py` | CLI pairing (desktop pairing is Rust + qr workers) |
| 70 | `hermes_cli/vercel_auth.py` | vercel (global-cut provider) |

This is a **floor**: several CLI-display modules (`commands`, `curses_ui`,
`skin_engine`, `cli_output`, `dump`, `logs`, `debug`, `default_soul`) currently
stay only because the `hermes_cli.gateway` bridge (see knot below) pulls them in.
Resolving that bridge frees them too.

## Keep — runtime genuinely needs these `hermes_cli` modules

`auth`, `config`, `tools_config`, `models`, `model_catalog`, `model_normalize`,
`model_switch`, `runtime_provider`, `providers`, `plugins`, `plugins_cmd`,
`skills_config`, `env_loader`, `colors`, `timeouts`, `copilot_auth`,
`codex_models`, `profiles`, `nous_subscription`, `tips`, `dingtalk_auth`,
`gateway`, plus the display modules pulled by the gateway bridge.

`auth.py` (4745) is **core**, not CLI — the agent/provider/credential layer
(`credential_pool`, `auxiliary_client`, `account_usage`, `credential_sources`)
depends on it heavily. It is a *split* candidate (with the provider work), never
a delete.

## Hooks to sever (the gate — 6 edges)

| # | Hook | Handling |
|---|---|---|
| 1 | `gateway/run.py` → `from cli import save_config_value` | ✅ Done — `save_config_value` added to `hermes_cli/config.py`; gateway imports it from there. |
| 2 | `tools/delegate_tool.py` → `from cli import CLI_CONFIG` | ✅ Done — dropped the `CLI_CONFIG` branch; `_load_config` uses `load_config()` only. |
| 3 | `hermes_cli/gateway.py` → `hermes_cli.main`, `hermes_cli.setup` | ✅ Resolved (knot) — `hermes_cli/gateway` is deletable; dissolved by deleting it (remove one lazy import in `profiles.py`). See below. |
| 4 | `hermes_cli/dingtalk_auth.py` → `hermes_cli.setup` | `dingtalk_auth` only uses `setup`'s `print_info/print_success/...`. Move those tiny console helpers to a retained util (e.g. `hermes_cli/cli_output.py`). DingTalk source is kept for `sea`. |
| 5 | `hermes_cli/nous_subscription.py` → `hermes_cli.setup` | Same console-helper relocation, plus decide whether the Nous subscription feature is retained (`agent/prompt_builder.py` calls `get_nous_subscription_features`). If dropped, sever that call too. |

(`gateway/run.py` also imports `hermes_cli.tips.get_random_tip`; `tips` is in the
keep set today, but if the gateway banner/tip is dropped, `tips` becomes
deletable too — optional extra ~ a few hundred lines.)

## The knot: `hermes_cli/gateway.py` — RESOLVED (2026-06-20, benign)

Investigated in step 1. **`gateway/run.py` does not import `hermes_cli/gateway`
at all.** The gateway runtime only needs `hermes_cli.profiles.get_active_profile_name`
(small, keep). `hermes_cli/gateway` is reachable only because `profiles.py:627`
has a **lazy** `from hermes_cli.gateway import get_service_name, get_launchd_plist_path`
inside a CLI-only service/launchd-management function that the desktop/gateway
runtime never calls — plus imports from other deletable CLI modules (cron/doctor/
dump/status/uninstall).

Conclusion: **`hermes_cli/gateway.py` is deletable**, not a split. No extraction
needed — during the bulk delete, remove that one lazy import (and the CLI-only
service function around it) from `profiles.py`. Deleting `hermes_cli/gateway`
also dissolves hook #3 (its `→ main`/`→ setup` edges). The knot is **not** a
blocker, and resolving it frees the display modules `hermes_cli/gateway` pulled.

## Execution sequence

1. **Resolve the knot first** — ✅ **DONE (2026-06-20).** `hermes_cli/gateway` is
   deletable (gateway runtime does not import it; only a lazy CLI-only import in
   `profiles.py` references it). See the knot section above.
2. **Sever the cheap hooks** (#1, #2) — ✅ **DONE (2026-06-20).**
   `save_config_value` was copied into `hermes_cli/config.py` and `gateway/run.py`
   now imports it from there; `tools/delegate_tool._load_config` dropped its
   `from cli import CLI_CONFIG` branch (it already fell back to `load_config()`).
   The re-run audit shows both `→ cli` hooks gone. Verified by compat guardrails,
   desk_server, and the delegate tests. (cli.py's own `save_config_value` stays
   until the bulk delete removes cli.py.)
3. **Relocate console helpers** (#4, #5): move `setup`'s `print_*` helpers to a
   retained util; repoint `dingtalk_auth` and `nous_subscription`. Decide the Nous
   feature. Commit.
4. **Sever the knot** (#3) per step 1's decision. Commit.
5. **Re-run the audit** (`scripts/_audit_cli_reachability.py`) — confirm `cli`,
   `main`, `setup`, `web_server` and the support cluster are now unreachable.
6. **Per-module dynamic-reference check**: grep each deletable module name for
   `importlib`/string imports before removal.
7. **Bulk-delete** the cluster + its tests, in grouped commits (entrypoints;
   command modules; display modules). After each group: kabuqina compat
   guardrails + `desk_server` tests + gateway/cron tests + a runtime smoke.
8. **Rebuild the bundle** and confirm the ~42k-line reduction lands and the
   desktop still boots, chats, and runs file/web/document tools.

## Verification

Per group: `hermes_core/tests/kabuqina` (compat guardrails), `python/tests/test_desk_server.py`,
`hermes_core/tests/gateway` + `tests/cron`, then `python -m unittest discover`
(desktop) and a `scripts/dev.ps1` runtime smoke. Final: bundle rebuild + manual
smoke (boot, chat, one file/web/document tool, gateway optional child start).

## Non-goals

- Do not delete `hermes_cli/auth.py` or the other keep-set modules.
- Do not delete the runtime `cron/scheduler.py` (only the CLI `hermes_cli/cron.py`).
- Do not start the bulk delete before the knot (step 1) is resolved.
