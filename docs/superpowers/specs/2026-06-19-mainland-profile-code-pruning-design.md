# v0.3.0 Student Profile Code Pruning Design

Date: 2026-06-19

## Goal

Prepare the v0.3.0 cleanup path for Kabuqina by making the current branch a
focused `mainland_cn` product profile for Xiaona, a student academic assistant
for mainland China university users.

The v0.3.0 cleanup should reduce product noise before deeper core separation
work. It has two layers:

1. Delete `global_student_cut` code that no student product line needs.
2. Split the remaining student-capable surface between `mainland_cn` and `sea`.

A later branch will target students in Singapore and Malaysia, so international
student-relevant providers and platform adapters should remain available for the
`sea` profile.

## v0.3.0 Scope

v0.3.0 is the deletion and profile-splitting release.

The order matters:

1. First, delete the `global_student_cut` list from the student branch.
2. Then classify the remaining capabilities into `mainland_cn` and `sea`.
3. Regional cuts are profile policy decisions, not deletion decisions.

## Global Student Cut Deletion List

`global_student_cut` is the overall delete list for v0.3.0. These items should
be removed from student-product source and runtime bundles, not merely hidden
from catalogs.

Deletion rules:

1. If the item is an independent file or directory, physically delete it.
2. If the item is mixed into a file that also contains retained student
   behavior, delete the cut behavior, registry entries, UI routes, docs, tests,
   config fields, and dependencies. Split retained behavior into a smaller file
   first when that makes deletion safe.
3. The item is not bundled in student runtimes.
4. Git history is the fallback. Do not keep dead student-product source around
   "just in case" after the deletion pass succeeds.
5. A deletion PR is complete only when searching the student branch no longer
   finds live imports, routes, registry entries, build-copy rules, tests, docs,
   or user-facing strings for that item, except for explicit historical notes in
   this design or changelog entries.

Provider first-party surfaces to delete:

- `openai-codex`
- `copilot-acp`
- `github-copilot`
- `google-gemini-cli`
- `qwen-oauth`
- `bedrock`
- `azure-foundry`
- `vercel`
- `opencode`
- `opencode-go`
- `kilo`
- `nvidia`
- `arcee`
- `gmi`
- `ollama-cloud`

Gateway/platform surfaces to delete:

- `homeassistant`
- `slack`
- `signal`
- `matrix`
- `mattermost`
- `bluebubbles`
- `webhook`
- `api_server`
- `yuanbao`

`dingtalk` was removed from this global delete list by the v0.3.0 scope
decision (2026-06-19): its source is retained (a school may use it later) but
hidden in `mainland_cn`, and its stale Alibaba Cloud SDKs are bundle-dropped.
See `Gateway Surface` and `Bundle Pruning`.

`discord_admin` was moved to the Toolsets/tools section below; it is a toolset,
not a gateway platform (it is not in the `PLATFORMS` registry). `sms` was
removed: it has no source surface in the current Kabuqina tree (no platform
registry entry and no live references in Python/Rust/Web). See
`Audit Findings`.

Toolsets/tools to delete:

- `rl`
- `homeassistant`
- `discord_admin`
- `spotify`
- `yuanbao`
- `moa`

Plugin directories to delete:

- `spotify`
- `google_meet`
- `example-dashboard`
- `hermes-achievements`
- `strike-freedom-cockpit`

Skill categories to delete:

- `apple`
- `autonomous-ai-agents`
- `devops`
- `dogfood`
- `gaming`
- `gifs`
- `mcp`
- `mlops`
- `red-teaming`
- `smart-home`
- `social-media`
- `yuanbao`

Runtime/source deletion targets:

- `tools/rl_training_tool.py`
- `tools/homeassistant_tool.py`
- `tools/discord_tool.py` admin surface, or the whole file if plain Discord is
  also excluded by the active profile;
- `tools/yuanbao_tools.py`
- global-cut plugin directories;
- global-cut skill directories.

Do not delete normal OpenAI, Google/Gemini, Anthropic, OpenRouter, Groq,
Mistral, Hugging Face, Telegram, WhatsApp, Discord, or Email in this global
pass. Those are `sea` profile decisions unless a later SEA design cuts them.

## Current Context

Kabuqina already has several partial narrowing layers:

- `web/src/lib/providers.ts` exposes a China-focused provider list in the
  onboarding UI.
- `python/src/tool_policy.py` narrows default desktop toolsets.
- `python/src/capability_policy.py` and `python/src/desk_server/capabilities.py`
  hide some irrelevant toolsets from the capability catalog.
- `python/build_bundle.ps1` already omits the upstream Hermes dashboard SPA by
  default and drops several heavy tools from the runtime bundle.

The remaining problem is that pruning is scattered across Web, Rust, Python
policy code, Hermes core metadata, and the bundle script. The v0.3.0
development step should delete the global cuts first, then consolidate the
remaining student surface into a product profile contract.

## Product Profiles

Introduce region product profiles:

| Profile | Purpose |
| --- | --- |
| `mainland_cn` | Default for the current branch. Focused on mainland China students, China-friendly LLM providers, China messaging channels, student documents, learning, reminders, and lightweight daily help. |
| `sea` | Reserved for Singapore and Malaysia student branches. Can enable international student-relevant providers and common regional channels after the global student deletion pass. |

The product profile controls the release surface:

- onboarding provider choices;
- Settings provider choices;
- Gateway platform entries;
- capability catalog visibility;
- default toolsets;
- network allowlist defaults;
- runtime bundle drop rules;
- smoke and regression test expectations.

Product profiles do not own global deletion. They only decide how the remaining
student-capable surface is exposed for `mainland_cn` or `sea`.

## Configuration Source

Persist the selected profile in settings:

```text
settings.json
  hermesdesk.product_profile = "mainland_cn"
```

Rust should inject it into Python children:

```text
HERMESDESK_PRODUCT_PROFILE=mainland_cn
```

For this branch, missing or unknown profile values resolve to `mainland_cn`.

v0.3.0 scope decision (2026-06-19): the new variable is
`KABUQINA_PRODUCT_PROFILE` (primary) with `HERMESDESK_PRODUCT_PROFILE` accepted
as a fallback, so the variable does not need renaming when the v0.4.0 core
rename lands. See `DECISIONS.md` and the v0.3.0 Slim & Focus plan.

## Product Profile Policy

Add a thin policy object:

```text
python/src/product_profile_policy.py
```

It should expose profile-aware lists for:

- visible LLM providers;
- visible gateway platforms;
- allowed gateway auto-start platforms;
- default desktop toolsets;
- hidden desktop toolsets;
- global student cut items;
- default network hosts;
- visible skill categories;
- bundle drop rules and global deletion targets.

Existing policy modules should consume this object instead of repeating region
checks:

- `python/src/capability_policy.py`
- `python/src/tool_policy.py`
- `python/src/network_policy.py`
- `python/src/gateway_policy.py`
- `python/src/desk_server/capabilities.py`

Web should render policy payloads instead of owning region decisions directly.
Rust should use the same profile contract for child process launch and gateway
eligibility.

## Mainland CN Hard Cut Contract

For `mainland_cn`, "must cut" means:

1. The item is not visible in onboarding, Settings, or capability catalogs.
2. The item is not enabled by default.
3. The item cannot make the gateway eligible for auto-start from stale `.env`
   keys.
4. Heavy runtime payloads for the item are not bundled unless required by a
   retained student workflow.
5. Source code may remain for `sea`.

## Provider Surface

Visible in `mainland_cn`:

- `deepseek`
- `zai`
- `kimi-coding`
- `kimi-coding-cn`
- `stepfun`
- `minimax-cn`
- `alibaba`
- `custom`

Cut from `mainland_cn` product surfaces (source retained for `sea`):

- `openai`
- `google`
- `gemini`
- `anthropic`
- `claude`
- `openrouter`
- `nous`
- `groq`
- `mistral`
- `xai`
- `huggingface`

`nvidia`, `arcee`, `gmi`, and `ollama-cloud` were removed from this list: they
are already in the global `Global Student Cut Deletion List`, which deletes
them for every profile including `sea`. Listing them here too implied "source
retained for `sea`", contradicting the global cut. They are now globally
deleted only. If the intent was to keep them for `sea`, move them out of the
global list instead — see `Audit Findings`.

Keep the Python `openai` SDK and neutral OpenAI-compatible wire support in
runtime, because DeepSeek, Alibaba, Kimi, and other retained providers rely on
compatible chat-completions behavior. User-facing copy should say "compatible
API" or "custom API" instead of making OpenAI the brand anchor.

Global provider deletion items are listed in the opening
`Global Student Cut Deletion List`. Normal OpenAI, Google/Gemini, Anthropic,
OpenRouter, Groq, Mistral, and Hugging Face API providers remain `sea` profile
decisions unless a later SEA design cuts them.

## Gateway Surface

Visible and supported in `mainland_cn`:

- `desktop`
- `weixin`
- `qqbot`
- `feishu`
- `wecom`

Cut from `mainland_cn` product surfaces and auto-start eligibility:

- `telegram`
- `discord`
- `slack`
- `signal`
- `whatsapp`
- `matrix`
- `mattermost`
- `bluebubbles`
- `homeassistant`
- `webhook`
- `api_server`
- `dingtalk`
- `email`

`sms` is not listed here because it has no platform surface in the current
tree (see `Audit Findings`). `desktop` in the visible list above is the Tauri
shell, not a `PLATFORMS` gateway entry, so profile tests should not expect a
`desktop` platform key.

Email is intentionally cut for the current branch. If school email workflows
become a product priority, they should return as a student learning or
assignment-specific feature, not as a generic upstream mail gateway.

Global gateway deletion items are listed in the opening
`Global Student Cut Deletion List`. `telegram`, `whatsapp`, `email`, and plain
`discord` remain `sea` profile decisions (source kept; `discord` overlaps the
student demographic, so it stays available for the future `sea` branch).

`dingtalk` is a special case (v0.3.0 decision): not student-relevant for most
users, but a school may use it, so its source at
`hermes_core/gateway/platforms/dingtalk.py` and `hermes_cli/dingtalk_auth.py`
is retained and hidden in `mainland_cn`. Its stale Alibaba Cloud SDKs
(`dingtalk_stream`, `alibabacloud_dingtalk`, `alibabacloud_tea_openapi`,
`alibabacloud_tea_util`) are excluded from the runtime bundle — the adapter
already degrades gracefully when they are absent (`DINGTALK_STREAM_AVAILABLE`).

## Toolset Surface

Keep in `mainland_cn` default or first-party student surfaces:

- `web`
- `file`
- `vision`
- `tts`
- `skills`
- `clock`
- `todo`
- `browser`
- `clarify`
- `documents`
- `math`
- `cronjob`
- `messaging`

Cut from `mainland_cn` visible/default surfaces:

- `moa`
- `rl`
- `homeassistant`
- `discord`
- `discord_admin`
- `spotify`
- `feishu_doc`
- `feishu_drive`
- `yuanbao`
- `delegation`

`terminal` and `code_execution` remain power-user-only. They are not student
default capabilities.

`image_gen` should be removed from the default mainland toolset unless a
China-available backend is configured. Student PPT and report visuals should
prefer templates, local rendering, and deterministic layout first.

Global toolset deletion items are listed in the opening
`Global Student Cut Deletion List`. `delegation` is not a physical deletion
target in this spec. It should be hidden from all student profiles unless a
concrete Xiaona workflow needs multi-agent execution, then decided in a
separate design.

## Plugin Surface

Cut from the `mainland_cn` runtime bundle and catalog:

- `spotify`
- `google_meet`
- `example-dashboard`
- `hermes-achievements`
- `strike-freedom-cockpit`
- non-mainland platform plugins under plugin platform surfaces

For `mainland_cn`-only plugin cuts, keep source for the `sea` profile where useful.

Do not expose `observability` or `context_engine` as student-facing product
features in `mainland_cn` until there is a concrete Xiaona workflow.

Global plugin deletion items are listed in the opening
`Global Student Cut Deletion List`. `memory`, `image_gen`, and `context_engine`
are not global deletion targets in this spec; keep them for future evaluation,
but do not surface them as standalone student product features without a Xiaona
workflow.

## Skill Surface

Hide these bundled skill categories from `mainland_cn` capability catalogs:

- `apple`
- `autonomous-ai-agents`
- `devops`
- `dogfood`
- `gaming`
- `gifs`
- `github`
- `inference-sh`
- `mcp`
- `mlops`
- `red-teaming`
- `smart-home`
- `social-media`
- `yuanbao`

Keep and curate these categories first:

- `data-science`
- `diagramming`
- `domain`
- `index-cache`
- `media`
- `note-taking`
- `productivity`
- `research`
- `software-development`

Add Xiaona-specific learning skills separately:

- explain;
- step-by-step derivation;
- hint mode;
- quiz or check understanding;
- review cards;
- presentation practice;
- formula-to-code and code-to-formula study workflows.

Optional skills should be hidden by default in `mainland_cn` unless explicitly
curated into the student profile.

Global skill category deletion items are listed in the opening
`Global Student Cut Deletion List`. `github`, `software-development`,
`data-science`, and `research` remain profile decisions because student
coursework may need coding, repository, data, or research workflows.

## Bundle Pruning

`python/build_bundle.ps1` must continue dropping:

- `tools/rl_training_tool.py`
- `tools/feishu_doc_tool.py`
- `tools/feishu_drive_tool.py`
- `tools/homeassistant_tool.py`
- `tools/mixture_of_agents_tool.py`
- upstream Hermes dashboard SPA by default

Add `mainland_cn` runtime drop rules for:

- `tools/discord_tool.py`
- `tools/yuanbao_tools.py`
- the stale DingTalk SDK packages from bundled site-packages:
  `dingtalk_stream`, `alibabacloud_dingtalk`, `alibabacloud_tea_openapi`,
  `alibabacloud_tea_util` (source under `gateway/platforms/dingtalk.py` stays;
  only the heavy/old dependency is excluded — it degrades gracefully);
- non-mainland plugin directories listed in this design;
- skill directories hidden by the `mainland_cn` profile, if the bundle script
  moves from catalog hiding to runtime source pruning.

Bundle pruning is a second layer. The first correctness layer is the profile
policy that hides and disables the item before runtime copying is considered.

Global runtime deletion targets are listed in the opening
`Global Student Cut Deletion List`. Do not delete provider SDKs or
OpenAI-compatible transport libraries under the global student rule. They are
infrastructure for retained providers and future regional profiles.

## Data Flow

```text
settings.json
  -> Rust resolves product profile
  -> Rust injects HERMESDESK_PRODUCT_PROFILE
  -> Python ProductProfilePolicy resolves profile rules
  -> tool/network/gateway/capability policies consume profile rules
  -> desk_server exposes profile-filtered catalog payloads
  -> Web renders returned providers, platforms, tools, skills, and capabilities
```

For gateway startup:

```text
hermes-home/.env
  -> Rust reads keys
  -> Product profile filters eligible platforms
  -> only mainland_cn allowed platforms can start gateway child
```

This prevents stale Telegram, Discord, Slack, Signal, DingTalk, or Email keys
from making the mainland build look gateway-ready.

## Error Handling

Unknown profile values resolve to `mainland_cn` and log a warning.

If a user has saved credentials for a cut provider or platform:

- keep the secret on disk or in the OS vault unless the user explicitly removes
  it;
- do not show it as configured in the mainland product UI;
- do not use it to auto-start gateway children;
- show a neutral "not available in this build profile" message only if the user
  reaches a legacy deep link.

If a custom API points to a non-mainland host, validation should still follow
the custom endpoint safety rules. The profile should not block advanced users
from using a valid custom provider through the custom path.

## Testing

Python policy tests:

- missing profile resolves to `mainland_cn`;
- `mainland_cn` visible providers equal the approved whitelist;
- `mainland_cn` visible gateway platforms equal the approved whitelist;
- `mainland_cn` hidden toolsets include the approved hard cuts;
- `global_student_cut` entries are absent from both `mainland_cn` and `sea`;
- global student cuts have no live registry entries, imports, UI routes, or
  build-copy rules in the student branch;
- OpenAI, Google/Gemini, Anthropic, OpenRouter, Telegram, WhatsApp, and Email
  are not marked as `global_student_cut`;
- skill category visibility hides the approved categories;
- default network hosts include retained China providers and messaging hosts.

Rust tests:

- gateway eligibility ignores Telegram, Discord, Slack, Signal, DingTalk, and
  Email keys under `mainland_cn`;
- gateway eligibility accepts Weixin, QQBot, Feishu, and WeCom credentials;
- Python child launch includes `HERMESDESK_PRODUCT_PROFILE`.

Frontend tests:

- onboarding provider registry only shows mainland providers plus custom;
- gateway settings navigation only shows Feishu, QQ, Weixin, and WeCom;
- Settings does not expose Email, Telegram, DingTalk, Discord, Slack, or Signal
  routes under `mainland_cn`;
- capability catalog normalizes hidden tools, plugins, and skills.

Bundle smoke tests:

- mainland runtime import still loads the retained desktop server;
- retained tools import successfully;
- global-cut tools are absent from runtime;
- mainland-only dropped tools are absent from runtime or unavailable through
  catalog policy;
- `openai` SDK import remains available for compatible providers.

## Non-Goals

- Do not physically delete international provider source code in this cleanup.
- Do not remove OpenAI-compatible protocol support.
- Do not remove source needed by the future `sea` branch.
- Do not classify future regional needs as `global_student_cut` merely because
  they are hidden in `mainland_cn`.
- Do not replace the owned `hermes_core` snapshot wholesale.
- Do not build a second scheduler or agent core in overlays.
- Do not redesign Xiaona learning interactions in this spec; this spec only
  clears the product surface so learning work can proceed cleanly.

## Implementation Notes

Likely files:

- `python/src/product_profile_policy.py`
- `python/src/capability_policy.py`
- `python/src/tool_policy.py`
- `python/src/network_policy.py`
- `python/src/gateway_policy.py`
- `python/src/desk_server/capabilities.py`
- `tauri/src/secrets.rs`
- `tauri/src/gateway_supervisor.rs`
- `tauri/src/python_supervisor.rs`
- `tauri/src/paths.rs`
- `web/src/lib/providers.ts`
- `web/src/onboarding/setupCatalog/optionData.ts`
- `web/src/advanced/settings/SettingsGateway.tsx`
- `web/src/lib/gatewayPlatformSettingsRegistry.ts`
- `python/build_bundle.ps1`
- `hermes_core/toolsets.py`
- `hermes_core/hermes_cli/platforms.py`
- `hermes_core/agent/auxiliary_client.py` — provider-resolution core where the
  global-cut providers actually live (approach pending discussion; see
  `Audit Findings`)
- `hermes_core/agent/account_usage.py` — provider usage accounting that also
  references global-cut providers

Prefer additive metadata and policy routing for regional cuts. For
`global_student_cut`, prefer real deletion after a dependency audit proves the
item is not shared with retained student behavior. Physical bundle pruning
should happen only after profile policy tests prove regional items are not
reachable in the `mainland_cn` release surface.

## Audit Findings (2026-06-19)

A pre-implementation audit of this design against the current branch produced
the findings below. Inline list fixes have already been applied; the remaining
items are recorded here.

### Verified consistent with the tree

- All implementation files in `Implementation Notes` exist;
  `python/src/product_profile_policy.py` is the only new file.
- `web/src/lib/providers.ts` already exposes exactly the eight `mainland_cn`
  providers in `Provider Surface`.
- `python/build_bundle.ps1` already drops exactly the five tools and the
  upstream dashboard SPA listed in `Bundle Pruning`.
- All five global-cut plugin directories and all named skill categories exist
  (`mlops`, `github`, `inference-sh` included).
- No pre-existing `product_profile` logic exists; the central policy is new,
  confirming the "pruning is scattered" premise.

### Applied fixes

- `sms` removed from both the global gateway delete list and the `mainland_cn`
  gateway cut list. It has no platform-registry entry and zero live references
  in Python/Rust/Web — it appears to be an upstream-only surface already absent
  here. Treat any `sms` cut as a no-op pending a final check.
- `discord_admin` moved out of "Gateway/platform surfaces to delete"; it is a
  toolset, not a `PLATFORMS` gateway, and was already listed under toolsets.
- `nvidia`, `arcee`, `gmi`, `ollama-cloud` removed from the `mainland_cn`
  provider cut list. They are in the global delete list (delete-everywhere),
  which contradicted "source retained for `sea`". Resolved in favor of global
  deletion. **Flag if you intended to retain them for `sea`** — then they
  should leave the global list instead.

### Open item 1 — provider global deletion is core surgery, not file deletion (for discussion)

The global-cut providers do not live in standalone files. They are embedded in
`hermes_core/agent/auxiliary_client.py` (~3,833 lines) and
`hermes_core/agent/account_usage.py`, interleaved with **retained** mainland
providers in the same file:

- Global-cut hit counts in `hermes_core/agent`: `bedrock` ~92, `opencode` ~16,
  `nvidia` ~8, `gmi` ~7, `kilo` ~6, `ollama-cloud` ~4, `arcee` ~3, `vercel` ~2,
  plus `openai-codex` / `copilot-acp` / `github-copilot` / `opencode-go` /
  `qwen-oauth` throughout.
- Retained providers in the same `auxiliary_client.py`: `kimi` ~28, `zai` ~8,
  `minimax` ~7, `alibaba`, `stepfun`.

Deletion rule #2 (split mixed files first) and rule #5 (no live references
remain) therefore make provider deletion a surgical extraction from a large
shared core, not a "delete these files" task. The original `Implementation
Notes` omitted both files (now added). **Approach is deferred for discussion**
before any code changes — sequencing, how far to extract, and whether to gate
this behind the profile policy first.

### Open item 2 — surfaces with no disposition

These exist in the tree but the design neither hides nor keeps them. Each needs
an explicit decision so the rule #5 "no live entries" completion test is
checkable. Recommended defaults in parentheses:

- bundled skill category `creative` (decide: keep/curate vs hide)
- bundled skill category `email` (recommend hide in `mainland_cn`, consistent
  with the email gateway being cut)
- plugin `disk-cleanup` (recommend hide — utility, not a student feature)
- plugin `platforms` (keep — platform-registry infrastructure, not a product
  feature)
- platform `wecom_callback` (keep — variant of retained `wecom`)
- platform `cron` (keep — internal scheduler, `cronjob` toolset is retained)
- platform `cli` (out of scope — not a desktop product surface)

### Open item 3 — ordering reconciliation

`v0.3.0 Scope` says "delete global cuts first"; `Bundle Pruning` and
`Implementation Notes` say build profile policy and tests first, prune
physically only after tests prove unreachability. For provider deletion (Open
item 1) the safe order is policy + characterization tests + dependency audit
first, then deletion — even though it is a global cut. Read "delete global cuts
first" as ordering relative to *regional* profile-splitting, not as license to
delete shared-core code before the policy and tests exist.

### Open item 4 — runtime-copy caveat

Deletion targets are written as `tools/<file>.py` but live at
`hermes_core/tools/<file>.py`, with build-time copies in
`python/dist/runtime/...` and `tauri/target/debug/runtime/...`. Deleting source
does not update those copies until a runtime re-sync / rebuild. The "absent from
runtime" bundle test must account for this so it does not pass or fail on a
stale copy. Note also `build_bundle.ps1` keeps `tools/environments/file_sync.py`
deliberately (ssh/modal/daytona import it) — a concrete example that the
dependency audit matters.

### Intentional, not a defect

The Feishu split is deliberate: the `feishu` **gateway** is retained for
`mainland_cn`, while the `feishu_doc` / `feishu_drive` **toolsets** are cut and
already bundle-dropped. Do not "reconcile" these into a single decision.
