# Load Package Agent Paths And Capability Pipelines Design

## Context

Kabuqina has started moving optional large assets into the Capability area. The current implementation can show and download load packages, and capability catalog entries can reference package usage. Two path problems remain:

1. Release builds need a predictable place for bundled read-only load packages.
2. Downloaded packages currently live in product-specific cache paths that the agent cannot reliably discover from its workspace.

There is also a separate but related Docling detail: CodeFormula is not usable just because Nana knows the model path. Docling must receive an `artifacts_path` whose directory layout contains the base Docling artifacts and `ds4sd--CodeFormula`, and math mode must enable formula enrichment.

Capability also needs a deeper product contract. Kabuqina already has a clear generation framework:

```text
Reader -> Material Index -> Planner -> Writer
```

Product capabilities must sit on top of that framework. A capability should not only say which tools and packages it needs; it must also say which framework stage or stages it covers and which pipeline Nana should execute.

## Product Capability Definition

A product capability is not a tool name, parser flag, model package, or UI label. It is a user-facing promise that Kabuqina can execute a class of work.

A capability is valid only when it satisfies all of these conditions:

1. **User goal**: users naturally ask for it as an outcome.
2. **Executable pipeline**: it has at least one concrete pipeline from input to output.
3. **Framework stage mapping**: every pipeline step maps to `reader`, `material_index`, `planner`, `writer`, or a future explicitly named stage.
4. **Status contract**: runtime can explain whether the capability is available, partially available, missing a package, disabled by tool policy, or unsupported for the current input.
5. **Output contract**: the pipeline declares the durable outputs it promises, such as `read_id`, `markdown`, `formulas`, `material_index`, `outline`, or `pptx_path`.

If an entry lacks a pipeline, it is a capability candidate or roadmap item, not an available product capability.

Capabilities are named by user outcome. Tools are named by execution path. Load packages are dependencies. For example:

```text
Product capability: document-math
Pipeline: docling-math-document-read
Tool step: document_read_precise(mode=math)
Dependency: docling-codeformula
Output contract: read_id, markdown, formulas
```

This distinction keeps the product map honest: `document-math` is a cross-document math extraction capability; `pdf_read_precise(mode=math)` is only one PDF-specific execution shortcut inside that capability.

## Goals

1. Use a stable release/runtime directory for bundled read-only load packages.
2. Use a stable app-data directory for user-downloaded writable load packages.
3. Expose installed load package locations to the agent through its workspace.
4. Preserve Docling's actual CodeFormula loading path, not only agent-visible metadata.
5. Keep Settings as the package cache/storage management view while Capability owns product meaning.
6. Support dev without requiring a full bundle rebuild after every source change.
7. Make every product capability declare its Reader / Material Index / Planner / Writer stage coverage.
8. Make every product capability declare at least one executable pipeline.
9. Make capability status derive from pipeline readiness, not only from top-level package/tool declarations.
10. Add shortcut metadata so future product capabilities can declare whether they should surface as chat quick actions, wizards, settings actions, or context-menu entries.

## Non-Goals

- Do not store downloaded packages inside the MSI installation directory; it is not safely writable after install.
- Do not require symlinks or junctions for correctness.
- Do not make the agent manually wire Docling to CodeFormula.
- Do not move document extraction semantics into desktop overlays.
- Do not change the public package IDs in this phase.
- Do not make Material Index responsible for planning or generation decisions.
- Do not fully define every future product capability in this phase.
- Do not implement every frontend shortcut in this phase; only add the metadata shape and enough UI to show shortcut candidates.

## Phase Scope

This phase builds the product capability structure, not the final catalog of every Kabuqina feature.

The implementation should ship:

- Capability schema with `stages`, `pipelines`, pipeline `steps`, package dependencies, output contracts, and shortcut metadata.
- Pipeline-derived availability status.
- Agent prompt summaries that expose ready pipeline invocations.
- Catalog/frontend support for displaying stages, pipelines, package dependencies, and shortcut candidates.
- Seed capabilities that prove the structure works: `document-precise-read`, `document-math`, `voice-local-stt`, `desktop-organizer`, and `student-ppt`.

The implementation should not try to perfect every seed capability. Seed entries are contract examples and migration anchors. Follow-up specs should define each product capability deeply, including quality standards, input support matrix, frontend interaction, and dedicated tests.

## Path Model

Use a three-layer model.

### Bundled Read-Only Layer

Release-bundled package payloads live under the runtime/install payload:

```text
<runtime>/load-packages/<package-id>/
```

For the desktop release this resolves inside the packaged Python/runtime tree. It is read-only from the app's point of view. Dev may populate this layer by syncing runtime sources or by build scripts.

### User Writable Layer

Downloaded package payloads live under app data:

```text
%LOCALAPPDATA%/com.kabuqina.app/load-packages/<package-id>/
```

This becomes the canonical writable package root. Existing package-specific cache roots can be migrated lazily or kept as compatibility fallbacks for one release.

### Agent Visible Layer

Each workspace gets a lightweight package index:

```text
<workspace>/.hermesdesk/load-packages/
  packages.json
  docling-codeformula.json
  local-stt-base-q5_1.json
  docling-codeformula/
    real-path.txt
```

The agent-facing layer is metadata-first. It may also contain Windows junctions to real package directories when junction creation succeeds, but manifests and `real-path.txt` are the correctness mechanism.

## Manifest Shape

`packages.json` contains all known packages:

```json
{
  "version": 1,
  "packages": [
    {
      "id": "docling-codeformula",
      "title": "Docling CodeFormula",
      "status": "installed",
      "realPath": "C:/Users/<user>/AppData/Local/com.kabuqina.app/load-packages/docling-codeformula/ds4sd--CodeFormula",
      "agentPath": ".hermesdesk/load-packages/docling-codeformula",
      "usedByCapabilities": [
        { "id": "student", "title": "Student" }
      ]
    }
  ]
}
```

Per-package JSON files mirror the same fields for easier direct reads. `real-path.txt` contains the absolute payload path for tools that only need a pointer.

## Agent Knowledge

The capability prompt should tell Nana:

- Installed load packages are indexed at `.hermesdesk/load-packages/packages.json`.
- `agentPath` is the workspace-visible pointer.
- `realPath` is the absolute filesystem location when a tool needs it.
- Package manifests are informational for the agent; product tools still own their own runtime wiring.

This distinction matters: Nana can inspect paths and decide which tool or mode to use, but she should not be expected to manually configure internal libraries such as Docling.

## Reader To Writer Framework

Capability definitions should use the existing framework vocabulary:

| Stage | Responsibility | Current examples |
| --- | --- | --- |
| `reader` | Acquire or extract source material. | `pdf_read_precise`, `document_read_precise`, `transcribe_audio`, file reads |
| `material_index` | Build deterministic structured evidence from already-read material. | `material_index_build` |
| `planner` | Decide story, format, outline, workflow sequence, and user confirmation points. | Agent planner guidance, `review_outline` |
| `writer` | Produce final artifacts or durable side effects. | `pptx_write`, file organization helpers |

Each product capability must declare one or more stages:

- Single-stage capabilities are valid. Example: `document-math` is primarily a `reader` capability.
- Multi-stage capabilities must declare the ordered flow. Example: `student-ppt` is `reader -> material_index -> planner -> writer`.
- Capabilities with side effects still use `writer` when they produce durable workspace changes, even when the output is not a document file.
- Load packages attach to the stage that consumes them, not only to the top-level capability.

Current capability stage map:

| Capability | Stages | Notes |
| --- | --- | --- |
| `document-precise-read` | `reader` | Reads PDFs/documents with structured extraction; CodeFormula is optional for math-heavy material. |
| `document-math` | `reader` | Extracts formulas and math notation from supported documents or images. Uses CodeFormula through `mode=math` for document inputs; this is a Reader pipeline, not a manual Docling setup step. |
| `voice-local-stt` | `reader` | Converts audio input into text material for downstream planning or writing. |
| `desktop-organizer` | `reader`, `planner`, `writer` | Reads workspace/file state, plans organization, then applies durable file changes through a helper. |
| `student-ppt` | `reader`, `material_index`, `planner`, `writer` | Reads source material, indexes evidence, plans the deck with review, then writes PPTX. |

## Capability Pipeline Contract

Product capabilities should be executable contracts, not only catalog rows.

Current behavior is only partially structured:

- `capability_registry.py` declares capability IDs, required tools, toolsets, and load packages.
- `capability_status.py` marks a capability available or unavailable from package/toolset state.
- `capability_prompt.py` summarizes capability status to the agent.
- The agent still has to infer the exact tool call, such as using `document_read_precise` with `mode=math`.

Required behavior:

- Each product capability must declare one or more pipelines.
- Each pipeline includes ordered steps.
- Each step includes the framework stage, tool name when applicable, default arguments, required package IDs, and output names.
- If a capability requires a load package, runtime checks package status before that pipeline is advertised as ready.
- Capability status is derived from its pipelines: available when at least one primary pipeline is ready, partial when only fallback or limited-input pipelines are ready, missing_package when every relevant pipeline is blocked by package state, and disabled_toolset when every relevant pipeline is blocked by tool policy.
- When Nana decides to use a product capability, the prompt gives her the concrete pipeline invocation, not just a generic hint.
- Product tools still perform final runtime validation, so stale prompts or deleted packages fail with clear errors.
- Multi-step product workflows declare ordered pipeline steps so the agent can execute the product flow rather than reconstruct it from prose.

For `document-math`, the pipeline contract should be cross-document. PDF is a supported input path, not the capability boundary:

```json
{
  "capabilityId": "document-math",
  "title": "Formula extraction and LaTeX",
  "stages": ["reader"],
  "pipelines": [
    {
      "id": "docling-math-document-read",
      "title": "Docling math document read",
      "primary": true,
      "inputs": ["pdf", "docx", "pptx", "xlsx", "html", "markdown", "image"],
      "statusInputs": {
        "pdf": "available",
        "docx": "available",
        "pptx": "partial",
        "xlsx": "partial",
        "html": "partial",
        "markdown": "partial",
        "image": "partial"
      },
      "steps": [
        {
          "stage": "reader",
          "tool": "document_read_precise",
          "defaultArgs": { "mode": "math" },
          "requiredLoadPackages": ["docling-codeformula"],
          "outputs": ["read_id", "markdown", "formulas"]
        }
      ]
    },
    {
      "id": "docling-math-pdf-read",
      "title": "Docling math PDF read",
      "primary": false,
      "inputs": ["pdf"],
      "steps": [
        {
          "stage": "reader",
          "tool": "pdf_read_precise",
          "defaultArgs": { "mode": "math" },
          "requiredLoadPackages": ["docling-codeformula"],
          "outputs": ["read_id", "markdown", "formulas"]
        }
      ]
    }
  ]
}
```

This means a user request for formula extraction should route to the math pipeline automatically regardless of whether the input is a PDF, slide deck, spreadsheet, image, or other supported document. Nana should not need to separately ask Docling to connect to CodeFormula; the `mode=math` tool path owns that wiring. The tool may still return `partial` or `unsupported_input` for formats where Docling cannot produce reliable formula items yet.

For `student-ppt`, the pipeline contract should include the full framework path:

```json
{
  "capabilityId": "student-ppt",
  "stages": ["reader", "material_index", "planner", "writer"],
  "pipelines": [
    {
      "id": "student-ppt-from-documents",
      "title": "Student PPT from source documents",
      "primary": true,
      "steps": [
        {
          "stage": "reader",
          "tools": ["pdf_read_precise", "document_read_precise"],
          "defaultArgs": { "mode": "auto", "include_content": false },
          "optionalLoadPackages": ["docling-codeformula"],
          "outputs": ["read_id", "markdown", "metadata"]
        },
        {
          "stage": "material_index",
          "tool": "material_index_build",
          "defaultArgs": { "profile": "course_report" },
          "inputs": ["read_id"],
          "outputs": ["material_index"]
        },
        {
          "stage": "planner",
          "kind": "agent_review",
          "requiresUserReview": true,
          "inputs": ["material_index"],
          "outputs": ["outline"]
        },
        {
          "stage": "writer",
          "tool": "pptx_write",
          "defaultArgs": { "template": "course_report" },
          "inputs": ["outline", "material_index"],
          "outputs": ["pptx_path"]
        }
      ]
    }
  ]
}
```

The exact schema can be Python dictionaries in `capability_registry.py` first. It does not need a new runtime engine in the first pass; the immediate requirement is that catalog payloads and agent prompt summaries expose the ordered pipeline clearly enough for Nana to execute it. A later runtime can turn the same schema into guided execution or UI progress.

### Pipeline Schema

Use a conservative schema that can be expressed as plain Python dictionaries:

```python
{
    "id": "docling-math-document-read",
    "title": "Docling math document read",
    "primary": True,
    "stages": ["reader"],
    "inputs": ["pdf", "docx", "pptx"],
    "steps": [
        {
            "id": "read-document-math",
            "stage": "reader",
            "tool": "document_read_precise",
            "default_args": {"mode": "math"},
            "required_load_packages": ["docling-codeformula"],
            "outputs": ["read_id", "markdown", "formulas"],
        }
    ],
}
```

Derived fields:

- Capability `tools` is the unique set of tool names in all pipeline steps, plus explicitly declared helper tools when necessary.
- Capability `requiredLoadPackages` is the unique set of pipeline step `required_load_packages`.
- Capability `optionalLoadPackages` is the unique set of pipeline step `optional_load_packages`.
- Capability `stages` is the ordered unique stage list across pipelines.

The registry may keep compatibility fields while the frontend migrates, but pipeline definitions should become the source of truth.

## Frontend Shortcut Metadata

Some product capabilities should eventually have direct frontend entrypoints. Others should remain background capabilities that Nana uses through chat or other workflows.

Shortcut metadata belongs on the capability because it is product-facing, but it points to a pipeline because the UI must trigger an executable path, not a vague feature label.

Initial schema:

```python
{
    "shortcuts": [
        {
            "id": "extract-formulas",
            "surface": "chat_quick_action",
            "label": "Extract formulas",
            "entry_pipeline": "docling-math-document-read",
            "requires_input": ["document"],
            "visible_when": "pipeline_ready_or_downloadable",
        }
    ]
}
```

Supported `surface` values for this phase:

| Surface | Meaning |
| --- | --- |
| `chat_quick_action` | A compact action near chat or attachments. |
| `wizard` | A guided multi-step frontend flow. |
| `settings_action` | A settings/capability management action. |
| `context_menu` | A future file/material context-menu action. |

This phase only defines and displays shortcut candidates. It does not implement all shortcut surfaces.

Shortcut eligibility guidelines:

1. **High frequency**: users are likely to use it repeatedly.
2. **Clear input**: the frontend can infer or ask for the required file/material without a long conversation.
3. **Small parameter surface**: the UI can expose the necessary choices in one compact action or wizard.

Examples:

| Capability | Shortcut posture |
| --- | --- |
| `document-math` | Candidate for `chat_quick_action` when a document is attached or selected. |
| `student-ppt` | Candidate for a `wizard`, not a single button. |
| `document-precise-read` | Usually background capability; no default shortcut required. |
| `voice-local-stt` | Candidate for microphone/settings surfaces. |
| `desktop-organizer` | Candidate for quick action with preview/confirmation. |

## Docling And CodeFormula

CodeFormula must remain wired through the Python document tooling.

Current behavior:

- `python/src/docling_math_models.py` downloads CodeFormula into a user path.
- It materializes a merged artifact directory under app data.
- The merged directory contains the expected Docling layout, including `ds4sd--CodeFormula`.
- `hermes_core/tools/document_tools.py` resolves this directory for math profile and assigns it to `pipeline_options.artifacts_path`.
- Math profile enables `do_formula_enrichment` and CodeFormula formula extraction.
- After download or delete, the Docling converter cache is invalidated.

Required behavior after this change:

- `docling-codeformula` payloads move to or resolve through the load-package path model.
- `docling_math_models.user_formula_dir()` should resolve the active CodeFormula payload from the load package registry.
- `docling_math_models._materialize_merged_artifacts()` must still create a Docling-compatible merged artifacts root.
- `document_tools` should continue to set `pipeline_options.artifacts_path` to the merged root for `profile="math"`.
- Download/delete must refresh the merged CodeFormula link and invalidate the converter cache.

In short: the agent-visible package path helps Nana understand availability, but Docling "connects" to CodeFormula only through `artifacts_path` plus math-mode pipeline options.

## Package Registry Behavior

The Python load package registry should report:

- `id`
- `title`
- `status`
- `path` or `realPath`
- `agentPath`
- `source`: `bundled`, `downloaded`, `missing`, or `fallback`
- `usedByCapabilities`

Capability registry payloads should report:

- `id`
- `title`
- `stages`
- `tools`
- `requiredToolsets`
- `requiredLoadPackages`
- `optionalLoadPackages`
- `pipelines`
- `status`
- `statusReason`

Resolution order:

1. Downloaded user package.
2. Bundled runtime package.
3. Compatibility fallback path.
4. Missing.

The API should continue to support existing frontend package pages while adding the agent path fields.

## Workspace Index Updates

The workspace index should be refreshed when:

- The Python child starts.
- Workspace changes.
- A package download completes.
- A package is deleted.
- Capability catalog/status is requested and the index is stale.

Refresh failures should be logged but should not make package download fail. If workspace is unavailable, the package APIs should still return real paths and omit `agentPath`.

## Release And Dev

Release:

- Build scripts may place bundled package payloads in `<runtime>/load-packages/<package-id>/`.
- User downloads remain in app data.

Dev:

- `scripts/sync-runtime-sources.ps1` can sync Python source changes.
- Package payloads can still be downloaded into app data without rebundling.
- Tests should use temporary app-data and workspace directories.

## Tests

Python tests:

- Every first-party product capability declares at least one framework stage.
- Every first-party product capability declares at least one pipeline.
- Every pipeline declares at least one step.
- Every pipeline step declares a valid framework stage.
- Every pipeline step declares at least one output.
- Capability pipeline package references are reflected in capability-level load package dependencies.
- `document-math` exposes Reader entrypoints for `document_read_precise` and `pdf_read_precise` with `mode=math`.
- `student-ppt` exposes an ordered `reader -> material_index -> planner -> writer` pipeline.
- Load package status reports `usedByCapabilities` and `agentPath` when workspace is configured.
- Package resolver prefers user package over bundled package.
- Workspace package index writes `packages.json`, per-package JSON, and `real-path.txt`.
- Index refresh failure does not fail package status.
- CodeFormula download path resolves through the load-package registry.
- Math profile returns a merged Docling artifacts path containing `ds4sd--CodeFormula`.
- Download/delete invalidates the Docling converter cache.

Frontend tests:

- Capability page displays framework stages and pipeline/entrypoint summaries.
- Settings load package page displays capability usage and package path metadata.
- Capability page catalog accepts `loadPackages` and package usage.

## Implementation Notes

Likely files:

- `python/src/load_packages.py`
- `python/src/docling_math_models.py`
- `python/src/desk_server/capabilities.py`
- `python/src/capability_prompt.py`
- `python/src/capability_registry.py`
- `python/src/capability_status.py`
- `hermes_core/tools/document_tools.py` only if current path hooks are insufficient
- `web/src/chat/chat-api.ts`
- `web/src/advanced/pages/LoadPackagesPage.tsx`
- `web/src/advanced/pages/CapabilitiesPage.tsx`
- `web/src/locales/strings.ts`

Keep document extraction semantics in `hermes_core/tools/document_tools.py`; keep desktop package path resolution and workspace index writing in `python/src`.

Capability pipeline definitions should start in `python/src/capability_registry.py` because they are Kabuqina first-party product metadata. As planner rules stabilize, workflow semantics that must be shared by web child and gateway child should move into `hermes_core` as shared planner guidance or a core workflow helper, following the repository's core-vs-overlay rules.

## Open Questions

1. Should existing `%LOCALAPPDATA%/com.kabuqina.app/docling-models/ds4sd--CodeFormula` installs be migrated immediately, or should the resolver treat them as a compatibility fallback for one release?
2. Should image-only formula extraction be represented as a partial input under `document-math` until a dedicated image math pipeline exists, or should it stay hidden until implemented?
3. Should workspace junction creation be attempted by default, or should the first implementation use manifests only?
4. Should `path` remain the absolute real path and `agentPath` be additive, or should API names shift to explicit `realPath` plus compatibility `path`?

Recommended first implementation:

- Add `realPath` and `agentPath`, keep `path` as a compatibility alias for `realPath`.
- Use manifests and `real-path.txt` as the guaranteed agent-visible layer.
- Treat old Docling/STT paths as compatibility fallbacks.
- Attempt junctions only after the manifest path is working and tested.
