# Provider API Mode Auto-Detection Design

**Date:** 2026-07-02  
**Status:** Proposed for implementation  
**Scope:** Kabuqina desktop and gateway LLM routing

## Context

Task 11's release smoke proved the graph engine on an OpenAI-compatible
`chat_completions` endpoint, but the desktop could not exercise
`anthropic_messages`. The custom-provider form always treated addresses as
OpenAI-compatible endpoints, probed `<base>/models` with OpenAI assumptions,
stored the key as an OpenAI-compatible credential, and gave users no protocol control.
An Anthropic-compatible Mimo endpoint ending in `/anthropic` was consequently
rejected with a misleading 404 even though Hermes core already supports both
wire protocols.

Protocol is not a supplier identity. Many suppliers expose both OpenAI Chat
Completions and Anthropic Messages endpoints, so Kabuqina must not encode a
one-provider/one-protocol table.

## Goals

- Select `chat_completions` or `anthropic_messages` automatically for ordinary
  users.
- Keep an advanced explicit override for ambiguous or non-standard endpoints.
- Preserve existing saved providers and OpenAI-compatible behavior.
- Apply the same decision in the desktop Python child and every independent
  gateway profile process.
- Keep API keys in Windows Credential Manager and never duplicate plaintext
  keys into settings files.
- Complete Task 11's remaining `anthropic_messages` graph smoke using a
  read-only tool.

## Non-goals

- Maintaining a continually updated supplier-to-protocol compatibility table.
- Probing protocols by sending a paid model request.
- Changing Hermes core transport semantics or the graph engine.
- Adding provider-specific Mimo behavior.
- Removing the explicit legacy-loop rollback during this change.

## Product behavior

The normal provider form remains simple. Kabuqina infers the protocol from the
saved provider and endpoint. An advanced “API format” control offers:

- **Automatic (default)**
- **OpenAI Chat Completions**
- **Anthropic Messages**

The control is a fallback, not a required setup step. Existing configurations
without an API-mode field behave as Automatic.

Automatic selection uses deterministic local evidence only:

1. an explicit advanced override, when present;
2. the endpoint shape and existing Hermes provider metadata;
3. `chat_completions` as the compatibility default.

Recognized Anthropic endpoint shapes include the existing Hermes rules such as
an address ending in `/anthropic`, `api.anthropic.com`, and known coding
endpoints already classified by Hermes. The desktop must reuse or mirror these
rules with contract tests so Web validation and Python runtime selection cannot
silently disagree.

No live model request is used for discovery. HTTP errors such as 401 and 404 do
not reliably identify a protocol, and probing could consume quota or trigger
rate limits.

## Persistence contract

`ProviderConfig` gains an optional `api_mode` field:

```text
null | "chat_completions" | "anthropic_messages"
```

`null` represents Automatic. The string `auto` is a UI sentinel only and is not
written to disk or passed into Hermes, whose persisted runtime values are the
two concrete protocol names.

Rust validates the field at the trust boundary. Unknown or blank explicit
values are rejected rather than silently changing transport. Older
`settings.json` files deserialize with `api_mode = null`.

The non-secret preview command returns the optional mode so Settings can reopen
without losing an override. Saving a provider updates its mode atomically with
provider, host, model, and base URL; the credential remains in Credential
Manager.

## URL normalization and validation

Normalization becomes protocol-aware:

- Explicit `chat_completions` keeps the current OpenAI-compatible trailing-slash
  normalization and cheap `<base>/models` endpoint validation.
- Explicit `anthropic_messages` preserves the supplied base path (apart from
  whitespace and a trailing slash) and never appends `/v1`.
- Automatic preserves a URL recognized as Anthropic-compatible; otherwise it
  retains the current OpenAI-compatible trailing-slash normalization and
  validation for backward compatibility.

The OpenAI `/models` validation request is not used for an explicitly or
automatically recognized Anthropic endpoint. For that path, Kabuqina validates
URL syntax, HTTPS/public-host policy, host agreement, and credential presence,
then lets the first user-requested conversation provide the real authentication
result. This avoids the false 404 observed during the release smoke.

## Runtime data flow

```text
Settings UI
  -> ProviderSaveConfig.api_mode
  -> Rust ProviderConfig.api_mode + Credential Manager key
  -> LlmSpawnParams.api_mode
  -> HERMESDESK_API_MODE (empty for Automatic)
  -> desktop_llm_config overlay
  -> config.yaml model.api_mode (explicit modes only)
  -> Hermes runtime provider resolution

Host config.yaml
  -> copied into profiles/<platform>/config.yaml
  -> independent python -m gateway.run
  -> same model.api_mode and endpoint decision
```

For Automatic, the overlay removes a stale `model.api_mode` left by a previous
explicit selection. For an explicit mode, it writes the validated value beside
`model.provider`, `model.default`, and `model.base_url`.

Gateway spawn receives the optional mode for observability and copies the host
configuration into the profile before launch. The profile therefore resolves
the same protocol without sharing memory with the desktop child.

## Credential routing

Protocol selection does not rename, copy, or persist the API key. A custom
supplier credential remains associated with that saved supplier entry. The
runtime passes the resolved credential to the selected transport; choosing
Anthropic Messages does not require treating the supplier as Anthropic Inc.

Child launch continues to strip inherited provider keys before injecting only
the selected credential. Logs may record provider, endpoint host, model, and
resolved API mode, but never the key or authenticated URL query data.

## Error handling

- Invalid explicit modes fail at save time with a user-facing validation error.
- Automatic ambiguity falls back to `chat_completions`, preserving current
  behavior.
- Authentication and provider errors remain in the selected transport; Kabuqina
  must not retry the same real turn through the other protocol because a tool or
  model-side action may already have occurred.
- Settings explains that the advanced override is intended for endpoints that
  Automatic misclassifies.
- Runtime logs record the resolved mode once per agent construction or request
  boundary so release smoke can prove which transport ran.

## Testing

### Web

- Automatic is the default for old previews.
- Advanced overrides serialize to the two exact runtime strings.
- Anthropic and recognized Automatic URLs are not rewritten with `/v1`.
- OpenAI URLs retain existing normalization.
- Anthropic-mode save skips the OpenAI `/models` probe without skipping local
  URL and credential validation.

### Rust

- Old provider JSON deserializes with no mode.
- Only the two explicit values or null are accepted.
- Preview/save round-trip the mode without exposing the secret.
- Desktop and gateway spawn configurations receive the same optional mode.
- Existing OpenAI custom-provider and key-environment tests remain green.

### Python

- Explicit mode is written to `model.api_mode`.
- Automatic removes a stale explicit value.
- Endpoint, provider, model, max-token, and reasoning fields remain intact.
- Web child and copied gateway profile resolve the same mode.

### Release smoke

With `agent.engine: graph`, configure an Anthropic-compatible supplier endpoint
in Automatic mode, then run the same two-turn read-only `clock` test used for
`chat_completions`. Record date, supplier, model, resolved mode, tool, result,
desktop log path, and gateway profile log path. Step 2 closes only when logs
prove `anthropic_messages` rather than inferring it from the URL or UI label.

## Rollout and compatibility

This change is additive. Missing `api_mode` means Automatic, and existing
OpenAI-compatible custom providers keep their normalization and transport.
No settings migration or config-version bump is required. The Task 11 default
engine flip remains blocked until the final Anthropic Messages smoke passes and
GO is recorded.
