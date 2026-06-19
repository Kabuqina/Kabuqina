# Mainland Profile Code Pruning Design

Date: 2026-06-19

## Goal

Prepare the post-0.2.0 cleanup path for Kabuqina by making the current branch a
focused `mainland_cn` product profile for Xiaona, a student academic assistant
for mainland China university users.

The cleanup should reduce product noise before deeper core separation work, but
it must not destroy future reuse. A later branch will target students in
Singapore and Malaysia, so international providers and platform adapters should
remain available in source for `sea` or `global` profiles.

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
policy code, Hermes core metadata, and the bundle script. The next development
step should consolidate this into a product profile contract.

## Product Profiles

Introduce region product profiles:

| Profile | Purpose |
| --- | --- |
| `mainland_cn` | Default for the current branch. Focused on mainland China students, China-friendly LLM providers, China messaging channels, student documents, learning, reminders, and lightweight daily help. |
| `sea` | Reserved for Singapore and Malaysia student branches. Can re-enable international providers and common regional channels without restoring deleted code. |
| `global` | Optional future catch-all for upstream-like experiments or power-user builds. |

The product profile controls the release surface:

- onboarding provider choices;
- Settings provider choices;
- Gateway platform entries;
- capability catalog visibility;
- default toolsets;
- network allowlist defaults;
- runtime bundle drop rules;
- smoke and regression test expectations.

The product profile must not directly delete SDKs, protocol adapters, or source
modules needed by other profiles.

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
- bundle drop candidates.

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
5. Source code may remain for `sea` or `global`.

## Global Student Cut Contract

Some upstream Hermes capabilities are not only unsuitable for `mainland_cn`;
they are also outside any student-focused Xiaona product profile, including
future Singapore and Malaysia builds. These should be marked as
`global_student_cut`.

For `global_student_cut`, the rule is stricter than regional hiding:

1. The item is not visible in any student profile (`mainland_cn` or `sea`).
2. The item is not enabled by default in any student profile.
3. The item is not bundled in student runtimes unless a retained dependency
   proves it is still needed.
4. Source may remain temporarily to reduce migration risk, but it is a valid
   candidate for later physical deletion after tests prove no student path uses
   it.

Do not put international student infrastructure in this bucket just because it
is not useful in mainland China. OpenAI, Google/Gemini, Anthropic, OpenRouter,
Telegram, WhatsApp, and school email style workflows are regional/profile
decisions, not global student cuts.

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

Cut from `mainland_cn` product surfaces:

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
- `nvidia`
- `huggingface`
- `arcee`
- `gmi`
- `ollama-cloud`

Keep the Python `openai` SDK and neutral OpenAI-compatible wire support in
runtime, because DeepSeek, Alibaba, Kimi, and other retained providers rely on
compatible chat-completions behavior. User-facing copy should say "compatible
API" or "custom API" instead of making OpenAI the brand anchor.

Global student provider cuts from first-party onboarding:

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

These are developer, enterprise, aggregator, cloud-infrastructure, or
subscription-identity surfaces rather than student product defaults. If an
advanced student needs one, it should go through `custom` or a power-user path,
not first-party onboarding. Do not put normal OpenAI, Google/Gemini, Anthropic,
OpenRouter, Groq, Mistral, or Hugging Face API providers in this global cut list
until the SEA branch has made its provider decision.

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
- `sms`
- `webhook`
- `api_server`
- `dingtalk`
- `email`

Email is intentionally cut for the current branch. If school email workflows
become a product priority, they should return as a student learning or
assignment-specific feature, not as a generic upstream mail gateway.

Global student gateway cuts:

- `homeassistant`
- `discord_admin`
- `slack`
- `signal`
- `matrix`
- `mattermost`
- `bluebubbles`
- `sms`
- `webhook`
- `api_server`
- `dingtalk`
- `yuanbao`

These are not student-first channels. `telegram`, `whatsapp`, and `email`
should stay available for `sea` evaluation even though they are cut from
`mainland_cn`. Plain `discord` should remain a profile decision until the
Singapore/Malaysia branch decides whether student communities need it; Discord
server administration is globally cut.

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

Global student toolset cuts:

- `rl`
- `homeassistant`
- `discord_admin`
- `spotify`
- `yuanbao`
- `moa`

`delegation` should stay source-available but hidden from all student profiles
unless a concrete Xiaona workflow needs multi-agent execution. It is a
complexity cut, not a physical deletion target yet.

## Plugin Surface

Cut from the `mainland_cn` runtime bundle and catalog:

- `spotify`
- `google_meet`
- `example-dashboard`
- `hermes-achievements`
- `strike-freedom-cockpit`
- non-mainland platform plugins under plugin platform surfaces

Keep source for other profiles where useful.

Do not expose `observability` or `context_engine` as student-facing product
features in `mainland_cn` until there is a concrete Xiaona workflow.

Global student plugin cuts:

- `spotify`
- `google_meet`
- `example-dashboard`
- `hermes-achievements`
- `strike-freedom-cockpit`

These should not appear in any student product profile. Keep `memory`,
`image_gen`, and `context_engine` source-available for future evaluation, but do
not surface them as standalone student product features without a Xiaona
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

Global student skill category cuts:

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

These categories should be absent from both mainland and SEA student catalogs.
`github`, `software-development`, `data-science`, and `research` should remain
profile decisions because student coursework may need coding, repository, data,
or research workflows.

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
- non-mainland plugin directories listed in this design;
- skill directories hidden by the `mainland_cn` profile, if the bundle script
  moves from catalog hiding to runtime source pruning.

Bundle pruning is a second layer. The first correctness layer is the profile
policy that hides and disables the item before runtime copying is considered.

Global student runtime drop candidates:

- `tools/rl_training_tool.py`
- `tools/homeassistant_tool.py`
- `tools/discord_tool.py` admin surface, or the whole file if plain Discord is
  also excluded by the active profile;
- `tools/yuanbao_tools.py`
- global-cut plugin directories;
- global-cut skill directories.

Do not drop provider SDKs or OpenAI-compatible transport libraries under the
global student rule. They are infrastructure for retained providers and future
regional profiles.

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
- `global_student_cut` entries are hidden from both `mainland_cn` and `sea`;
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
- dropped tools are absent from runtime or unavailable through catalog policy;
- `openai` SDK import remains available for compatible providers.

## Non-Goals

- Do not physically delete international provider source code in this cleanup.
- Do not remove OpenAI-compatible protocol support.
- Do not remove source needed by future `sea` or `global` branches.
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

Prefer additive metadata and policy routing over broad deletes. Physical bundle
pruning should happen only after profile policy tests prove the item is not
reachable in the `mainland_cn` release surface.
