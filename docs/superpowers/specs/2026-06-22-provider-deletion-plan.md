# Provider Deletion Plan (set-D global student cut)

Date: 2026-06-22

Execution of the **deferred provider deletion** from the v0.3.0 slim plan
(`2026-06-19-v0.3.0-slim-and-focus-plan.md`, "set D — Deferred"). Deletion was
held until the provider/credential code was de-tangled from the shared
`hermes_cli/auth.py` — that prerequisite (the `providers/` extraction) is now far
enough along to delete cut providers at file/entry level.

## Is the cut still authoritative? (verified 2026-06-22)

Yes — it is encoded in **shipping code**, not just a plan doc:
`python/src/product_profile_policy.py` → `GLOBAL_STUDENT_CUT` (a `frozenset`) lists
the exact targets, with a comment: *"Provider deletion is deferred to v0.3.x;
this constant is the target list and the contract the 'absent from both profiles'
tests assert against."* No newer spec revises it; no provider had been deleted
before this campaign.

Keep each deleted provider **in `GLOBAL_STUDENT_CUT`** — it becomes the enforced
"stays absent" invariant (`python/tests/test_product_profile.py`). Do **not**
remove names from that frozenset when you delete the source.

## Target list + tiers

15 providers. Tiered by deletion difficulty (arcee proved tier 1):

| Tier | Providers | Shape | How |
|---|---|---|---|
| **1 — pure config** | `gmi`, `nvidia`, `kilo`, `vercel`, `opencode`, `azure-foundry` | `api_key`, standard `openai_chat` transport, **no** bespoke api_mode/adapter, **nothing in `run_agent.py`** | same recipe as arcee; safe to batch |
| **2 — config + minor special-case** | `opencode-go` (has an `anthropic_messages` branch in `runtime_provider.py`), `ollama-cloud` (`fetch_ollama_cloud_models` live discovery) | a couple of extra provider-specific branches | one at a time; remove the special branches too |
| **3 — invasive (hot path / bespoke auth)** | `bedrock` (`bedrock_converse` api_mode, boto3, `agent/bedrock_adapter.py` 1260 lines, `providers/transports/bedrock.py`), `openai-codex` (`codex_responses` api_mode), `copilot-acp` + `github-copilot` (`external_process`, `hermes_cli/copilot_auth.py`), `google-gemini-cli` + `qwen-oauth` (`oauth_external`) | dedicated api_mode/adapter/transport/OAuth, with branches threaded through **`run_agent.py`** (the 14k-line hot path) | careful, one per branch+commit; **requires a `scripts/dev.ps1` runtime smoke** (live chat) before trusting — unit tests pass while a missed hot-path branch breaks a live conversation |

**Do not start a tier-3 deletion as a "warm-up".** (An earlier read mistakenly
called `bedrock` the most independent target; it is the opposite — its boto3
path has bespoke `bedrock_converse` handling in `run_agent.py` init / request /
stream / client-rebuild.) Clear tiers 1–2 first; do tier 3 only when a runtime
smoke is available.

## Progress

- [x] **`arcee`** — done, commit `e7914833`. 12 files, 269 deletions. Established
  the tier-1 recipe below.
- [ ] Tier 1 remaining: `gmi`, `nvidia`, `kilo`, `vercel`, `opencode`,
  `azure-foundry`.
- [ ] Tier 2: `opencode-go`, `ollama-cloud`.
- [ ] Tier 3: `bedrock`, `openai-codex`, `copilot-acp`, `github-copilot`,
  `google-gemini-cli`, `qwen-oauth`.

Prerequisite extraction slices already landed (so tier-3 OAuth resolvers are
less entangled): `providers/auth_store.py` (`1820c1dc`),
`providers/api_key_auth.py` (`b77c159f`), `providers/oauth_helpers.py`
(`f35bbd9b`). See `2026-06-21-large-file-split-plan.md`.

## Tier-1 removal recipe (the arcee pattern)

**First: inventory.** `rg -i "<provider-id>"` across the repo, excluding
`__pycache__`, `dist/runtime`, `target/*/runtime`, `_staging_portable`,
`.claude/worktrees`, and `website/`. Every hit is either a touchpoint below or a
"leave" item. The provider id and its aliases (e.g. `arcee`, `arcee-ai`,
`arceeai`) and its model-vendor slug (e.g. `trinity`) all need sweeping.

Touchpoints (each is a small dict/list/alias entry — pure removal):

1. `hermes_core/hermes_cli/auth.py` — `PROVIDER_REGISTRY[...]` entry + the alias
   map inside `resolve_provider`.
2. `hermes_core/hermes_cli/providers.py` — `HERMES_OVERLAYS[...]`, the alias
   dict, and the hardcoded `_PROVIDER_LABELS` dict **only if** the provider is
   listed there (api_key providers usually get their label from the registry
   `name`, so often nothing to do here).
3. `hermes_core/hermes_cli/config.py` — the `*_API_KEY` / `*_BASE_URL` env-var
   schema blocks.
4. `hermes_core/hermes_cli/models.py` — curated model tuples, any "featured"
   model list, the `_PROVIDER_MODELS` catalog block, the `ProviderEntry(...)`
   row, and the alias map.
5. `hermes_core/hermes_cli/model_switch.py` — `ModelIdentity` entries (if the
   provider has named-model identities, e.g. `trinity`).
6. `hermes_core/hermes_cli/model_normalize.py` — vendor-slug maps and the
   `_MATCHING_PREFIX_STRIP_PROVIDERS` set.
7. `hermes_core/providers/model_metadata.py` — the provider-name list, the
   `_PROVIDER_PREFIXES` alias list, the context-length map (keyed by model
   slug), and the `_URL_TO_PROVIDER` host map.
8. `hermes_core/trajectory_compressor.py` — the `base_url_host_matches(...)`
   provider-detection branch.
9. **`python/src/secret_store.py`** — the provider→env-var map. **Easy to miss**
   (it lives under `python/src`, not `hermes_core`); the repo-wide `rg` is what
   catches it.
10. `hermes_core/.env.example`, `hermes_core/cli-config.yaml.example` — example
    entries.
11. Delete the dedicated `hermes_core/tests/hermes_cli/test_<provider>_provider.py`
    (`git rm`).

**Leave alone:** `GLOBAL_STUDENT_CUT` (the contract), `RELEASE_*.md`
(historical changelog), and `hermes_core/website/docs/**` (the website is a
separate slim-plan deletion).

## Verification (per deletion)

1. `rg -i "<provider-id>"` over source again → only `GLOBAL_STUDENT_CUT`,
   `RELEASE_*.md`, and `website/` should remain.
2. Cold import (catches a removed-entry that some module still indexes):
   `auth`, `providers`, `models`, `model_metadata`, `runtime_provider`,
   `run_agent`. (`trajectory_compressor` needs the optional `fire` dep — skip it
   locally.) Assert the id is gone from `PROVIDER_REGISTRY` and
   `HERMES_OVERLAYS`, and that `resolve_provider("<alias>")` now raises
   `AuthError("Unknown provider …")` — that raise is the correct post-deletion
   behavior, not a regression.
3. Cut-contract test: `python -m pytest python/tests/test_product_profile.py`.
4. Provider/model surface (run from `hermes_core/`, see the test-env note below):
   `tests/agent/test_provider_package_split.py tests/kabuqina/test_compat_imports.py
   tests/hermes_cli/test_models.py tests/hermes_cli/test_model_validation.py
   tests/hermes_cli/test_runtime_provider_resolution.py tests/agent/test_model_metadata.py`.

Test-env on this Windows box (see memory `running-tests-windows-dev`): use system
Python with
`TZ=UTC LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 python -m pytest -o "addopts=" -p no:cacheprovider -n 4 …`;
GBK-locale / `prompt_toolkit` / Windows-permission failures are pre-existing
environmental noise, not your deletion.

## Tier-3 extra steps (when you get there)

Beyond the tier-1 touchpoints, each tier-3 provider also needs:
- its api_mode removed from `_VALID_API_MODES` (`runtime_provider.py`) and the
  api_mode set in `run_agent.py`, plus the provider's dispatch block in
  `runtime_provider.resolve_runtime_provider` and the `run_agent.py` branches
  (init, request, stream, client-rebuild);
- its dedicated module(s) deleted (`agent/bedrock_adapter.py`,
  `providers/transports/bedrock.py` + the `agent.transports`/`providers.transports`
  registry+alias, `hermes_cli/copilot_auth.py`, etc.);
- the transport-alias assertions in `tests/agent/test_provider_package_split.py`
  updated (they assert `agent.transports.bedrock is providers.transports.bedrock`);
- dependency pruning (`pyproject.toml` extras, e.g. `[bedrock]` → `boto3`);
- **a `scripts/dev.ps1` runtime smoke** (live chat) — required for hot-path
  changes.

## Non-goals

- Don't remove names from `GLOBAL_STUDENT_CUT` (it's the absence contract).
- Don't edit historical `RELEASE_*.md` changelogs.
- Don't touch `run_agent.py` for tier-3 without a runtime smoke available.
