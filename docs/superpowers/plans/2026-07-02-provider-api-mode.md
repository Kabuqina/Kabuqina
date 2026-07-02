# Provider API Mode Auto-Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Kabuqina automatically select OpenAI Chat Completions or Anthropic Messages for any saved endpoint, with an advanced explicit override shared by desktop and gateway processes.

**Architecture:** Web owns presentation and avoids OpenAI-only validation when an endpoint is recognizably Anthropic. Rust persists a nullable concrete `api_mode`, validates it, and injects it into both child-process environments. The desktop overlay writes explicit modes to `model.api_mode` and removes stale overrides for Automatic; Hermes core remains the authority for automatic runtime resolution.

**Tech Stack:** React/TypeScript, Node test runner, Tauri 2/Rust/serde, Python 3.11/unittest, Hermes runtime-provider configuration, Windows release smoke.

---

## File map

- Create `web/src/lib/api-mode.ts`: protocol types, endpoint-shape inference, and protocol-aware URL normalization.
- Create `web/src/lib/apiMode.test.mjs`: executable unit contract for the pure TypeScript helpers.
- Modify `web/src/lib/llm-config.ts`: add nullable `apiMode`/`api_mode` fields to preview/save contracts.
- Modify `web/src/lib/validate.ts`: separate local Anthropic validation from the OpenAI `<base>/models` probe.
- Modify `web/src/components/LlmConfigEditor.tsx`: hydrate, render, validate, and save the advanced Automatic/OpenAI/Anthropic choice.
- Modify `web/src/locales/strings.ts`: Chinese and English labels/hints.
- Modify `web/src/onboarding/providerUx.test.mjs`: pin the shared editor wiring and advanced control.
- Modify `tauri/src/secrets.rs`: persist and validate `ProviderConfig.api_mode`, expose it in preview, and resolve it into spawn parameters.
- Modify `tauri/src/python_supervisor.rs`: inject `HERMESDESK_API_MODE` into the desktop child.
- Modify `tauri/src/gateway_supervisor.rs`: inject the same mode into gateway children.
- Modify `tauri/src/lib.rs`: copy the resolved mode into `SpawnConfig`.
- Create `python/tests/test_desktop_llm_config.py`: pin explicit-mode persistence and Automatic stale-mode removal.
- Modify `python/overlays/desktop_llm_config.py`: apply `HERMESDESK_API_MODE` without changing credentials.
- Modify `python/src/desk_server/chat_core.py`: log the resolved desktop runtime mode without secrets.
- Modify `hermes_core/gateway/run.py`: log the resolved gateway runtime mode without secrets.
- Create `hermes_core/tests/gateway/test_runtime_mode_observability.py`: pin gateway runtime-mode logging.
- Modify `python/tests/test_desk_server.py`: pin desktop runtime-mode logging.
- Modify `docs/superpowers/specs/2026-07-02-provider-api-mode-design.md`: retain the factual `<base>/models` correction.
- Modify `docs/superpowers/specs/2026-06-24-consolidate-and-langgraph-replatform-plan.md`: record the final Task 11 Step 2 evidence.

---

### Task 1: Pure Web protocol rules

**Files:**
- Create: `web/src/lib/api-mode.ts`
- Create: `web/src/lib/apiMode.test.mjs`
- Modify: `web/src/lib/llm-config.ts`

- [x] **Step 1: Write the failing helper tests**

Create `web/src/lib/apiMode.test.mjs` using the same TypeScript transpile helper as `providerUx.test.mjs` and assert this contract:

```js
const {
  inferApiMode,
  normalizeApiBaseUrl,
  persistedApiMode,
} = await importTs("./api-mode.ts");

assert.equal(inferApiMode("custom", "https://example.com/v1"), "chat_completions");
assert.equal(inferApiMode("custom", "https://example.com/anthropic/"), "anthropic_messages");
assert.equal(inferApiMode("anthropic", "https://proxy.example.com"), "anthropic_messages");
assert.equal(inferApiMode("custom", "https://api.kimi.com/coding"), "anthropic_messages");
assert.equal(normalizeApiBaseUrl(" https://example.com/anthropic/// "), "https://example.com/anthropic");
assert.equal(persistedApiMode("auto"), null);
assert.equal(persistedApiMode("chat_completions"), "chat_completions");
assert.equal(persistedApiMode("anthropic_messages"), "anthropic_messages");
```

Also update the imported `LlmConfigPreview`/`ProviderSaveConfig` source contract expectation so `apiMode: ApiMode | null` and `api_mode: ApiMode | null` are required.

- [x] **Step 2: Run the helper test and verify RED**

Run:

```powershell
cd web
node --test src/lib/apiMode.test.mjs
```

Expected: FAIL because `api-mode.ts` does not exist.

- [x] **Step 3: Implement the minimal pure helper module**

Create `web/src/lib/api-mode.ts`:

```ts
export type ApiMode = "chat_completions" | "anthropic_messages";
export type ApiModeSelection = "auto" | ApiMode;

export function normalizeApiBaseUrl(url: string): string {
  return url.trim().replace(/\/+$/, "");
}

export function inferApiMode(provider: string, rawBaseUrl: string): ApiMode {
  const providerId = provider.trim().toLowerCase();
  const baseUrl = normalizeApiBaseUrl(rawBaseUrl);
  if (providerId === "anthropic") return "anthropic_messages";
  try {
    const parsed = new URL(baseUrl);
    const host = parsed.hostname.toLowerCase();
    const path = parsed.pathname.replace(/\/+$/, "").toLowerCase();
    if (host === "api.anthropic.com") return "anthropic_messages";
    if (path.endsWith("/anthropic")) return "anthropic_messages";
    if (host === "api.kimi.com" && path.includes("/coding")) return "anthropic_messages";
  } catch {
    // Rust remains the URL trust boundary; invalid URLs are not protocol evidence.
  }
  return "chat_completions";
}

export function effectiveApiMode(
  selection: ApiModeSelection,
  provider: string,
  baseUrl: string,
): ApiMode {
  return selection === "auto" ? inferApiMode(provider, baseUrl) : selection;
}

export function persistedApiMode(selection: ApiModeSelection): ApiMode | null {
  return selection === "auto" ? null : selection;
}
```

Modify `web/src/lib/llm-config.ts`:

```ts
import type { ApiMode } from "./api-mode";

export type LlmConfigPreview = {
  hasSecret: boolean;
  provider: string | null;
  host: string | null;
  model: string | null;
  apiBaseUrl: string | null;
  apiMode: ApiMode | null;
};

export type ProviderSaveConfig = {
  provider: string;
  host: string;
  model: string | null;
  api_base_url: string | null;
  api_mode: ApiMode | null;
};
```

- [x] **Step 4: Run the helper tests and verify GREEN**

Run:

```powershell
cd web
node --test src/lib/apiMode.test.mjs src/onboarding/providerUx.test.mjs
```

Expected: both test files pass.

- [x] **Step 5: Commit the pure Web contract**

```powershell
git add web/src/lib/api-mode.ts web/src/lib/apiMode.test.mjs web/src/lib/llm-config.ts
git commit -m "feat(web): define automatic provider API modes"
```

---

### Task 2: Protocol-aware validation and advanced UI override

**Files:**
- Modify: `web/src/lib/validate.ts`
- Modify: `web/src/components/LlmConfigEditor.tsx`
- Modify: `web/src/locales/strings.ts`
- Modify: `web/src/onboarding/providerUx.test.mjs`

- [ ] **Step 1: Write failing validation and editor contracts**

Extend `apiMode.test.mjs` to import `validate.ts` with a stubbed Tauri invoke and assert that local validation accepts a valid Anthropic URL/key without invoking `<base>/models`, while OpenAI mode still invokes it. Export a pure decision helper so the behavior is testable without React:

```js
const { shouldProbeOpenAiModels } = await importTs("./api-mode.ts");
assert.equal(shouldProbeOpenAiModels("auto", "custom", "https://example.com/anthropic"), false);
assert.equal(shouldProbeOpenAiModels("anthropic_messages", "custom", "https://example.com/v1"), false);
assert.equal(shouldProbeOpenAiModels("chat_completions", "custom", "https://example.com/v1"), true);
assert.equal(shouldProbeOpenAiModels("auto", "custom", "https://example.com/v1"), true);
```

Extend `providerUx.test.mjs` with source assertions that the editor:

```js
assert.match(llmConfigEditorSource, /apiModeSelection/);
assert.match(llmConfigEditorSource, /<details[\s\S]*apiModeAuto[\s\S]*apiModeAnthropic/);
assert.match(llmConfigEditorSource, /api_mode:\s*persistedApiMode\(apiModeSelection\)/);
assert.match(llmConfigEditorSource, /p\.apiMode\s*\?\?\s*"auto"/);
```

- [ ] **Step 2: Run the Web contracts and verify RED**

Run:

```powershell
cd web
node --test src/lib/apiMode.test.mjs src/onboarding/providerUx.test.mjs
```

Expected: FAIL because probe selection and UI wiring do not exist.

- [ ] **Step 3: Implement protocol-aware validation**

Add to `api-mode.ts`:

```ts
export function shouldProbeOpenAiModels(
  selection: ApiModeSelection,
  provider: string,
  baseUrl: string,
): boolean {
  return effectiveApiMode(selection, provider, baseUrl) === "chat_completions";
}
```

Change `validateCustomEndpoint` in `validate.ts` to accept `probeOpenAiModels = true`. Always check non-empty URL/key and require a parseable `https:` URL in the Web layer. Return `{ok: true}` without Tauri invocation when `probeOpenAiModels` is false; Rust still performs authoritative public-host validation at save time. Replace the old `normalizeOpenAiBaseUrl` helper/import with `normalizeApiBaseUrl` from `api-mode.ts` so there is one normalizer.

```ts
export async function validateCustomEndpoint(
  baseUrl: string,
  apiKey: string,
  probeOpenAiModels = true,
): Promise<ValidateResult> {
  const base = normalizeApiBaseUrl(baseUrl);
  // existing empty checks
  try {
    const parsed = new URL(base);
    if (parsed.protocol !== "https:" || !parsed.hostname) {
      return { ok: false, message: translate("validate.unreachable", loc()) };
    }
  } catch {
    return { ok: false, message: translate("validate.unreachable", loc()) };
  }
  if (!probeOpenAiModels) return { ok: true };
  // existing cmd_validate_endpoint(`${base}/models`) branch
}
```

- [ ] **Step 4: Implement editor hydration, advanced control, and save**

In `LlmConfigEditor.tsx`:

```ts
const [apiModeSelection, setApiModeSelection] =
  useState<ApiModeSelection>("auto");

// preview hydration
setApiModeSelection(p.apiMode ?? "auto");

// validation
const providerForMode = selectedProvider !== "custom"
  ? selectedProvider
  : customProviderId.trim() || "custom";
const probeOpenAi = shouldProbeOpenAiModels(apiModeSelection, providerForMode, baseUrl);
const result = await validateEndpointForProvider(
  selectedKnownProvider,
  baseUrl,
  key,
  probeOpenAi,
);

// save payload
api_mode: persistedApiMode(apiModeSelection),
```

Render a collapsed `<details>` block after the model field with a select whose values are `auto`, `chat_completions`, and `anthropic_messages`. Add Chinese/English keys:

```ts
apiModeAdvanced: "高级 API 格式",
apiModeLabel: "API 格式",
apiModeAuto: "自动识别（推荐）",
apiModeOpenAi: "OpenAI Chat Completions",
apiModeAnthropic: "Anthropic Messages",
apiModeHint: "仅在自动识别不正确时手动覆盖。",
```

and equivalent English strings.

Reset the selection to `auto` when changing providers. Add `apiModeSelection` to the validation effect dependencies. Ensure preview fallback objects include `apiMode: null`.

- [ ] **Step 5: Run Web unit, lint, and build gates**

Run:

```powershell
cd web
node --test src/lib/apiMode.test.mjs src/onboarding/providerUx.test.mjs
npm run lint
npm run build
```

Expected: tests, lint, and build all pass; the existing Vite chunk-size warning is allowed.

- [ ] **Step 6: Commit the Web UI behavior**

```powershell
git add web/src/lib/api-mode.ts web/src/lib/apiMode.test.mjs web/src/lib/validate.ts web/src/components/LlmConfigEditor.tsx web/src/locales/strings.ts web/src/onboarding/providerUx.test.mjs
git commit -m "feat(web): auto-detect provider API format"
```

---

### Task 3: Rust persistence and identical child-process propagation

**Files:**
- Modify: `tauri/src/secrets.rs`
- Modify: `tauri/src/python_supervisor.rs`
- Modify: `tauri/src/gateway_supervisor.rs`
- Modify: `tauri/src/lib.rs`

- [ ] **Step 1: Write failing Rust trust-boundary tests**

Add tests inside `tauri/src/secrets.rs`:

```rust
#[test]
fn old_provider_json_defaults_api_mode_to_automatic() {
    let cfg: ProviderConfig = serde_json::from_str(
        r#"{"provider":"custom","host":"api.example.com","model":"m","api_base_url":"https://api.example.com/v1"}"#,
    ).unwrap();
    assert_eq!(cfg.api_mode, None);
}

#[test]
fn save_config_accepts_concrete_api_modes() {
    for mode in ["chat_completions", "anthropic_messages"] {
        let mut cfg = custom_config(Some(mode));
        validate_provider_config_for_save(&mut cfg, "sk-test").unwrap();
        assert_eq!(cfg.api_mode.as_deref(), Some(mode));
    }
}

#[test]
fn save_config_rejects_auto_and_unknown_api_modes() {
    for mode in ["auto", "anthropic", ""] {
        let mut cfg = custom_config(Some(mode));
        assert!(validate_provider_config_for_save(&mut cfg, "sk-test").is_err());
    }
}
```

The helper returns a public HTTPS custom config and avoids duplicating fixtures:

```rust
fn custom_config(api_mode: Option<&str>) -> ProviderConfig {
    ProviderConfig {
        provider: "custom".into(),
        host: "api.example.com".into(),
        model: Some("model".into()),
        api_base_url: Some("https://api.example.com/anthropic".into()),
        api_mode: api_mode.map(str::to_string),
    }
}
```

- [ ] **Step 2: Run Rust tests and verify RED**

Run:

```powershell
cd tauri
$env:TAURI_CONFIG='{"build":{"frontendDist":"../web"},"bundle":{"resources":[]}}'
cargo test secrets
```

Expected: compile/test failure because `ProviderConfig.api_mode` does not exist.

- [ ] **Step 3: Add the validated nullable persistence field**

Add to `ProviderConfig`, `LlmConfigPreview`, and `LlmSpawnParams`:

```rust
#[serde(default)]
pub api_mode: Option<String>,
```

Add one normalization function and call it from both save commands before any write:

```rust
fn normalize_api_mode(raw: Option<&str>) -> Result<Option<String>, String> {
    match raw.map(str::trim) {
        None => Ok(None),
        Some("chat_completions") => Ok(Some("chat_completions".into())),
        Some("anthropic_messages") => Ok(Some("anthropic_messages".into())),
        Some(_) => Err("api_mode must be chat_completions, anthropic_messages, or null".into()),
    }
}
```

Assign `cfg.api_mode = normalize_api_mode(cfg.api_mode.as_deref())?;`. Update all existing `ProviderConfig` and `LlmSpawnParams` literals with `api_mode: None`. Preview returns the saved optional value; `resolve_llm_spawn_params` carries it unchanged.

Update the custom-provider error text from “custom OpenAI-compatible APIs” to protocol-neutral “custom APIs”.

- [ ] **Step 4: Propagate the mode to both child types**

Add to `python_supervisor::SpawnConfig`:

```rust
pub api_mode: Option<String>,
```

In `lib.rs`, set `api_mode: llm.api_mode`. In both `python_supervisor.rs` and `gateway_supervisor.rs`, add:

```rust
.env(
    "HERMESDESK_API_MODE",
    cfg.api_mode.as_deref().unwrap_or(""),
)
```

Do not map a custom Anthropic-compatible supplier to provider `anthropic`; retain its provider id and existing Credential Manager account/environment mapping.

- [ ] **Step 5: Run Rust gates and verify GREEN**

Run:

```powershell
cd tauri
$env:TAURI_CONFIG='{"build":{"frontendDist":"../web"},"bundle":{"resources":[]}}'
cargo test secrets
cargo test gateway
cargo test python_supervisor
```

Expected: all selected tests pass and the crate compiles with every updated struct literal.

- [ ] **Step 6: Commit Rust persistence and propagation**

```powershell
git add tauri/src/secrets.rs tauri/src/python_supervisor.rs tauri/src/gateway_supervisor.rs tauri/src/lib.rs
git commit -m "feat(shell): persist provider API mode"
```

---

### Task 4: Python overlay applies explicit modes and clears stale overrides

**Files:**
- Create: `python/tests/test_desktop_llm_config.py`
- Modify: `python/overlays/desktop_llm_config.py`

- [ ] **Step 1: Write failing overlay tests**

Create `python/tests/test_desktop_llm_config.py`. Patch `sys.modules` with a fake `hermes_cli.config` whose `load_config` returns a mutable config and whose `save_config` captures the result. Reload the overlay for each case and patch environment variables.

Pin these behaviors:

```python
def test_explicit_anthropic_mode_is_persisted(self):
    saved = self.run_install(
        initial={"model": {"provider": "custom", "api_mode": "chat_completions"}},
        env={
            "HERMESDESK_PROVIDER": "custom",
            "HERMESDESK_INFERENCE_PROVIDER": "custom",
            "HERMESDESK_MODEL": "mimo-v2.5",
            "HERMESDESK_API_BASE_URL": "https://example.com/anthropic",
            "HERMESDESK_API_MODE": "anthropic_messages",
        },
    )
    self.assertEqual(saved["model"]["api_mode"], "anthropic_messages")

def test_automatic_removes_stale_explicit_mode(self):
    saved = self.run_install(
        initial={"model": {"provider": "custom", "api_mode": "anthropic_messages"}},
        env={
            "HERMESDESK_PROVIDER": "custom",
            "HERMESDESK_INFERENCE_PROVIDER": "custom",
            "HERMESDESK_MODEL": "model",
            "HERMESDESK_API_BASE_URL": "https://example.com/v1",
            "HERMESDESK_API_MODE": "",
        },
    )
    self.assertNotIn("api_mode", saved["model"])
```

Add cases for explicit `chat_completions`, DeepSeek's special seed path, and invalid environment values falling back to Automatic with a warning. Assert provider/model/base URL/max tokens remain intact.

- [ ] **Step 2: Run overlay tests and verify RED**

Run:

```powershell
cd python
python -m unittest discover -s tests -p "test_desktop_llm_config.py" -v
```

Expected: FAIL because the overlay ignores `HERMESDESK_API_MODE` and leaves stale values.

- [ ] **Step 3: Implement one mode-application helper**

Add:

```python
_VALID_API_MODES = {"chat_completions", "anthropic_messages"}

def _apply_api_mode(model_block: dict, raw_mode: str) -> str | None:
    normalized = raw_mode.strip().lower()
    if not normalized:
        model_block.pop("api_mode", None)
        return None
    if normalized not in _VALID_API_MODES:
        log.warning("invalid HERMESDESK_API_MODE=%r; using automatic detection", raw_mode)
        model_block.pop("api_mode", None)
        return None
    model_block["api_mode"] = normalized
    return normalized
```

Read `HERMESDESK_API_MODE` in `install()`. Call `_apply_api_mode` for the DeepSeek block and the general block before merging/saving. Automatic must remove an old value from the final merged block, not merely omit a new value.

Update the log to include `api_mode=%r`, using `"auto"` when the helper returns `None`. Do not change `secret_store.py`; the same custom-supplier key is passed to whichever transport runtime resolution selects.

- [ ] **Step 4: Run overlay and existing policy tests**

Run:

```powershell
cd python
python -m unittest discover -s tests -p "test_desktop_llm_config.py" -v
python -m unittest discover -s tests -p "test_policy_contract.py" -v
python -m unittest discover -s tests -p "test_gateway_env_loader.py" -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit Python configuration behavior**

```powershell
git add python/overlays/desktop_llm_config.py python/tests/test_desktop_llm_config.py
git commit -m "feat(python): apply provider API mode override"
```

---

### Task 5: Log the resolved mode in desktop and gateway paths

**Files:**
- Modify: `python/src/desk_server/chat_core.py`
- Modify: `python/tests/test_desk_server.py`
- Modify: `hermes_core/gateway/run.py`
- Create: `hermes_core/tests/gateway/test_runtime_mode_observability.py`

- [ ] **Step 1: Write failing observability tests**

In `python/tests/test_desk_server.py`, extend the existing `_desk_chat_build_agent` fixture to capture logs and assert:

```python
with self.assertLogs("desk_server.chat_core", level="INFO") as captured:
    agent = chat_core._desk_chat_build_agent("desk-mode-log", db=object())
self.assertIsNotNone(agent)
joined = "\n".join(captured.output)
self.assertIn("provider=custom", joined)
self.assertIn("model=mimo-v2.5", joined)
self.assertIn("api_mode=anthropic_messages", joined)
self.assertIn("engine=graph", joined)
self.assertNotIn("never-log-me", joined)
```

Create `hermes_core/tests/gateway/test_runtime_mode_observability.py`:

```python
def test_gateway_logs_resolved_mode_without_secret(monkeypatch, caplog):
    monkeypatch.setattr(
        runtime_provider,
        "resolve_runtime_provider",
        lambda **_: {
            "provider": "custom",
            "api_mode": "anthropic_messages",
            "base_url": "https://example.com/anthropic",
            "api_key": "never-log-me",
        },
    )
    with caplog.at_level(logging.INFO, logger="gateway.run"):
        result = gateway_run._resolve_runtime_agent_kwargs()
    assert result["api_mode"] == "anthropic_messages"
    assert "api_mode=anthropic_messages" in caplog.text
    assert "never-log-me" not in caplog.text
```

Use the real module import/monkeypatch pattern from neighboring gateway tests.

- [ ] **Step 2: Run observability tests and verify RED**

Run:

```powershell
cd python
python -m unittest tests.test_desk_server -v
cd ..\hermes_core
python -m pytest tests/gateway/test_runtime_mode_observability.py -o "addopts=" -p no:cacheprovider -q
```

Expected: assertions fail because no resolved-mode log exists.

- [ ] **Step 3: Add secret-free runtime logs**

In `_desk_chat_build_agent`, after runtime resolution and before constructing `AIAgent`, log only safe fields:

```python
log.info(
    "desk agent runtime provider=%s model=%s api_mode=%s engine=%s",
    runtime.get("provider"),
    default_model,
    runtime.get("api_mode"),
    str(agent_section.get("engine") or "loop"),
)
```

In `_resolve_runtime_agent_kwargs`, build the result first and then log:

```python
logger.info(
    "gateway agent runtime provider=%s api_mode=%s",
    result.get("provider"),
    result.get("api_mode"),
)
return result
```

Do not log the API key, full URL, headers, or query data.

- [ ] **Step 4: Run observability and runtime-provider regressions**

Run:

```powershell
cd python
python -m unittest tests.test_desk_server -v
cd ..\hermes_core
python -m pytest tests/gateway/test_runtime_mode_observability.py tests/hermes_cli/test_determine_api_mode_hostname.py tests/hermes_cli/test_runtime_provider_resolution.py -o "addopts=" -p no:cacheprovider -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit observability**

```powershell
git add python/src/desk_server/chat_core.py python/tests/test_desk_server.py hermes_core/gateway/run.py hermes_core/tests/gateway/test_runtime_mode_observability.py
git commit -m "feat(runtime): log selected provider API mode"
```

---

### Task 6: Cross-layer gates, rebuilt release, and final Anthropic smoke

**Files:**
- Modify: `docs/superpowers/specs/2026-07-02-provider-api-mode-design.md`
- Modify: `docs/superpowers/specs/2026-06-24-consolidate-and-langgraph-replatform-plan.md`

- [ ] **Step 1: Run all focused gates from a clean worktree**

Run:

```powershell
git status --short
cd web
node --test src/lib/apiMode.test.mjs src/onboarding/providerUx.test.mjs
npm run lint
npm run build
cd ..\python
python -m unittest discover -s tests -p "test_desktop_llm_config.py" -v
python -m unittest tests.test_desk_server -v
cd ..\hermes_core
python -m pytest tests/gateway/test_runtime_mode_observability.py tests/hermes_cli/test_determine_api_mode_hostname.py tests/hermes_cli/test_runtime_provider_resolution.py -o "addopts=" -p no:cacheprovider -q
cd ..\tauri
$env:TAURI_CONFIG='{"build":{"frontendDist":"../web"},"bundle":{"resources":[]}}'
cargo test secrets
cargo test gateway
cargo test python_supervisor
```

Expected: all focused tests, lint, and build pass. Record exact counts in the Task 11 evidence note.

- [ ] **Step 2: Rebuild the packaged runtime and Tauri release**

Run from repository root:

```powershell
.\python\build_bundle.ps1 -Verify
cd web
npm ci
npm run build
cd ..\tauri
cargo tauri build
```

Expected: bundle verification, Web build, and Tauri release build succeed. Record `BUNDLE_INFO.json`, installer path, size, timestamp, and SHA-256.

- [ ] **Step 3: Run the final real-model smoke with proxy disabled**

In release Settings, select the custom supplier, enter its `/anthropic` base URL, leave API format at Automatic, retain `agent.engine: graph`, and send:

```text
请使用 clock 只读工具查询当前 Asia/Shanghai 时间，并只用一行回答，必须包含工具返回的日期和时间。
```

Then in the same session send:

```text
不要再次调用工具。根据上一轮结果，只回答日期，格式 YYYY-MM-DD。
```

Expected:

- both turns succeed;
- the first turn uses only the read-only `clock` tool;
- the second turn preserves history without another tool call;
- `hermesdesk.log` contains `api_mode=anthropic_messages` and `engine=graph`;
- after starting the configured Gateway profile, its `gateway.log` contains `api_mode=anthropic_messages` from the independent `python -m gateway.run` process;
- no API key appears in either log.

- [ ] **Step 4: Record GO and close Task 11 Step 2**

Update the Task 11 Step 2 note with date, supplier, model, tool, result, desktop session id, desktop log path, gateway profile/log path, resolved mode, build artifact hash, and reviewer. Check Step 2 only when all five scenarios have evidence.

Correct the design document's status to `Implemented` and retain the factual wording that the former failure was the OpenAI-only `<base>/models` probe, not automatic `/v1` mutation.

- [ ] **Step 5: Run document checks and commit evidence**

```powershell
git diff --check
git add docs/superpowers/specs/2026-07-02-provider-api-mode-design.md docs/superpowers/specs/2026-06-24-consolidate-and-langgraph-replatform-plan.md
git commit -m "docs: close graph dual-protocol smoke"
git status --short
```

Expected: documentation commit succeeds and the worktree is clean. Task 11 Step 3 may begin only after this GO is recorded.
