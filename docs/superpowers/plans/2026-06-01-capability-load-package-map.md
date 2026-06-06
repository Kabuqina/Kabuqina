# Capability Load Package Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current skills/tools/plugins capability page into a product capability map, with load packages shown as dependencies and reflected in Nana's self-knowledge.

**Architecture:** Add a first-party product capability registry in `python/src/`, compute runtime status from existing tool policy and load-package state, then extend the existing `/api/hermesdesk/capabilities` payload. The React capability page gains a new default "Product capabilities" tab, while Settings load-package management remains the storage/cache view and links packages back to the capabilities that use them.

**Tech Stack:** Python policy modules and FastAPI routes under `python/src/`, Tauri command proxies in `tauri/src/`, React/Vite UI in `web/src/`, existing `unittest` and Node source-contract tests.

---

## Current Context

The existing capability page is implemented in `web/src/advanced/pages/CapabilitiesPage.tsx` and currently exposes `skills`, `tools`, and `plugins`. The backend catalog comes from `python/src/desk_server/capabilities.py` via `python/src/desk_server/routes/capabilities_routes.py` and the Tauri proxy in `tauri/src/capabilities.rs`.

The existing load-package registry is implemented in `python/src/load_packages.py`; it already knows how to report status, sources, jobs, download, and delete for `docling-codeformula` and `local-stt-base-q5_1`. The Tauri/web API lives in `tauri/src/chat.rs` and `web/src/chat/chat-api.ts`.

The implementation should keep these boundaries:

- Product capabilities say what Nana can do.
- Tools and toolsets say how the agent executes a capability.
- Load packages say which large local assets are present, missing, downloading, or removable.
- Skills and plugins remain extension sources, not the primary shape of first-party product features.

## File Structure

- Create `python/src/capability_registry.py`: static first-party capability definitions and schema helpers.
- Create `python/src/capability_status.py`: runtime status computation from `load_packages`, `tool_policy`, and environment.
- Modify `python/src/desk_server/capabilities.py`: include `capabilities` and `loadPackages` in the existing catalog payload.
- Modify `python/src/load_packages.py`: expose reverse usage metadata, so load packages can say which capabilities use them.
- Modify `python/src/desk_server/routes/capabilities_routes.py`: no new route is required; keep `/api/hermesdesk/capabilities` as the single catalog endpoint.
- Modify `web/src/chat/chat-api.ts`: add types for product capabilities and package dependencies.
- Modify `web/src/advanced/pages/CapabilitiesPage.tsx`: add `capabilities` tab, dependency badges, and load-package actions.
- Modify or create `web/src/advanced/capabilitiesUx.test.mjs`: source-contract tests for the new tab and package dependency UI.
- Modify `web/src/advanced/settings/SettingsLoadPackages.tsx` or `web/src/advanced/pages/LoadPackagesPage.tsx`: show "used by" capability names for each load package.
- Modify `web/src/advanced/settingsLoadPackages.test.mjs`: assert load packages expose capability usage.
- Create `python/src/capability_prompt.py`: compact agent-facing capability summary.
- Modify `python/src/desk_server/chat_core.py`: inject the summary into desktop chat requests at the desktop integration layer.
- Create `python/tests/test_capability_registry.py`: Python unit tests for registry and status behavior.

## Data Contracts

Backend `ProductCapability` payload:

```json
{
  "id": "document-math",
  "title": "Formula extraction and LaTeX",
  "description": "Extract formulas from PDFs, images, and screenshots.",
  "category": "documents",
  "status": "missing_package",
  "statusReason": "docling-codeformula is not installed",
  "agentHint": "Use when the user asks for formula recognition, math extraction, or LaTeX cleanup.",
  "tools": ["pdf_read_precise", "document_read_precise"],
  "requiredToolsets": ["file", "vision"],
  "requiredLoadPackages": [
    {
      "id": "docling-codeformula",
      "title": "Docling CodeFormula",
      "downloaded": false,
      "sizeMb": 500,
      "job": null
    }
  ],
  "optionalLoadPackages": [],
  "roles": ["default", "advanced", "power"],
  "risk": "low",
  "source": "builtin",
  "trust": "official"
}
```

Valid product capability statuses:

```text
available
missing_package
downloading
package_error
disabled_toolset
requires_power_user
unsupported_platform
error
```

Initial first-party capabilities:

```text
document-precise-read  -> precise PDF/document reading, no optional user package required
document-math          -> formula extraction, requires docling-codeformula
voice-local-stt        -> local speech recognition, requires local-stt-base-q5_1
desktop-organizer      -> desktop organization helper, no load package
student-ppt            -> student report PPT workflow, depends on document reading and document tools
```

---

### Task 1: Python Registry Schema

**Files:**
- Create: `python/src/capability_registry.py`
- Test: `python/tests/test_capability_registry.py`

- [ ] **Step 1: Write the failing registry test**

Add this test file:

```python
# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


class CapabilityRegistryTests(unittest.TestCase):
    def test_first_party_capabilities_are_registered(self):
        from capability_registry import list_capability_defs

        ids = {item["id"] for item in list_capability_defs()}

        self.assertIn("document-precise-read", ids)
        self.assertIn("document-math", ids)
        self.assertIn("voice-local-stt", ids)
        self.assertIn("desktop-organizer", ids)
        self.assertIn("student-ppt", ids)

    def test_load_package_dependencies_are_declared_on_capabilities(self):
        from capability_registry import get_capability_def

        math = get_capability_def("document-math")
        voice = get_capability_def("voice-local-stt")

        self.assertEqual(math["required_load_packages"], ["docling-codeformula"])
        self.assertEqual(voice["required_load_packages"], ["local-stt-base-q5_1"])
        self.assertEqual(math["source"], "builtin")
        self.assertEqual(math["trust"], "official")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
cd python
python -m unittest tests.test_capability_registry -v
cd ..
```

Expected: import failure for `capability_registry`.

- [ ] **Step 3: Implement the registry**

Create `python/src/capability_registry.py`:

```python
# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""First-party product capability definitions for Kabuqina Desktop."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

VALID_CAPABILITY_STATUSES = (
    "available",
    "missing_package",
    "downloading",
    "package_error",
    "disabled_toolset",
    "requires_power_user",
    "unsupported_platform",
    "error",
)

_CAPABILITIES: tuple[dict[str, Any], ...] = (
    {
        "id": "document-precise-read",
        "title": "Precise document reading",
        "description": "Read PDFs and documents with layout, tables, OCR hints, and structured extraction.",
        "category": "documents",
        "agent_hint": "Use for PDF, Word, and document understanding tasks that need structure beyond plain text.",
        "tools": ["pdf_read_precise", "document_read_precise"],
        "required_toolsets": ["file"],
        "required_load_packages": [],
        "optional_load_packages": ["docling-codeformula"],
        "roles": ["default", "advanced", "power"],
        "risk": "low",
        "source": "builtin",
        "trust": "official",
    },
    {
        "id": "document-math",
        "title": "Formula extraction and LaTeX",
        "description": "Extract formulas from PDFs, images, and screenshots with Docling CodeFormula.",
        "category": "documents",
        "agent_hint": "Use when the user asks for formula recognition, math extraction, or LaTeX cleanup.",
        "tools": ["pdf_read_precise", "document_read_precise"],
        "required_toolsets": ["file", "vision"],
        "required_load_packages": ["docling-codeformula"],
        "optional_load_packages": [],
        "roles": ["default", "advanced", "power"],
        "risk": "low",
        "source": "builtin",
        "trust": "official",
    },
    {
        "id": "voice-local-stt",
        "title": "Local speech recognition",
        "description": "Transcribe microphone input locally with whisper.cpp.",
        "category": "voice",
        "agent_hint": "Use for local voice input when the user has downloaded the STT model.",
        "tools": ["transcribe_audio"],
        "required_toolsets": ["tts"],
        "required_load_packages": ["local-stt-base-q5_1"],
        "optional_load_packages": [],
        "roles": ["default", "advanced", "power"],
        "risk": "low",
        "source": "builtin",
        "trust": "official",
    },
    {
        "id": "desktop-organizer",
        "title": "Desktop organization",
        "description": "Organize desktop files through the built-in desktop organizer workflow.",
        "category": "workspace",
        "agent_hint": "Use when the user asks Nana to clean or organize desktop files.",
        "tools": ["run_builtin_helper"],
        "required_toolsets": ["file"],
        "required_load_packages": [],
        "optional_load_packages": [],
        "roles": ["default", "advanced", "power"],
        "risk": "medium",
        "source": "builtin",
        "trust": "official",
    },
    {
        "id": "student-ppt",
        "title": "Student report PPT workflow",
        "description": "Build structured course, paper, and code-defense PPT workflows from source material.",
        "category": "documents",
        "agent_hint": "Use for course reports, paper presentations, and code-defense slide generation.",
        "tools": ["material_index_build", "review_outline", "pptx_write"],
        "required_toolsets": ["file"],
        "required_load_packages": [],
        "optional_load_packages": ["docling-codeformula"],
        "roles": ["default", "advanced", "power"],
        "risk": "medium",
        "source": "builtin",
        "trust": "official",
    },
)


def list_capability_defs() -> list[dict[str, Any]]:
    return [deepcopy(item) for item in _CAPABILITIES]


def get_capability_def(capability_id: str) -> dict[str, Any]:
    for item in _CAPABILITIES:
        if item["id"] == capability_id:
            return deepcopy(item)
    raise KeyError(capability_id)
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```powershell
cd python
python -m unittest tests.test_capability_registry -v
cd ..
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add python/src/capability_registry.py python/tests/test_capability_registry.py
git commit -m "feat: add product capability registry"
```

---

### Task 2: Capability Runtime Status

**Files:**
- Create: `python/src/capability_status.py`
- Modify: `python/tests/test_capability_registry.py`

- [ ] **Step 1: Add failing status tests**

Append to `CapabilityRegistryTests`:

```python
    def test_missing_required_package_marks_capability_missing(self):
        from capability_registry import get_capability_def
        from capability_status import build_capability_status

        packages = {
            "docling-codeformula": {
                "id": "docling-codeformula",
                "title": "Docling CodeFormula",
                "downloaded": False,
                "sizeMb": 500,
                "job": None,
            }
        }

        status = build_capability_status(get_capability_def("document-math"), packages)

        self.assertEqual(status["status"], "missing_package")
        self.assertEqual(status["requiredLoadPackages"][0]["id"], "docling-codeformula")

    def test_running_required_package_marks_capability_downloading(self):
        from capability_registry import get_capability_def
        from capability_status import build_capability_status

        packages = {
            "docling-codeformula": {
                "id": "docling-codeformula",
                "title": "Docling CodeFormula",
                "downloaded": False,
                "sizeMb": 500,
                "job": {"status": "running", "phase": "downloading", "percent": 12},
            }
        }

        status = build_capability_status(get_capability_def("document-math"), packages)

        self.assertEqual(status["status"], "downloading")

    def test_downloaded_required_package_marks_capability_available(self):
        from capability_registry import get_capability_def
        from capability_status import build_capability_status

        packages = {
            "docling-codeformula": {
                "id": "docling-codeformula",
                "title": "Docling CodeFormula",
                "downloaded": True,
                "sizeMb": 500,
                "job": None,
            }
        }

        status = build_capability_status(get_capability_def("document-math"), packages)

        self.assertEqual(status["status"], "available")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
cd python
python -m unittest tests.test_capability_registry -v
cd ..
```

Expected: import failure for `capability_status`.

- [ ] **Step 3: Implement status computation**

Create `python/src/capability_status.py`:

```python
# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Runtime status computation for first-party product capabilities."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _camel_package(package: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(package.get("id") or ""),
        "title": str(package.get("title") or package.get("id") or ""),
        "description": str(package.get("description") or ""),
        "feature": str(package.get("feature") or ""),
        "modelId": str(package.get("modelId") or package.get("model_id") or ""),
        "sizeMb": int(package.get("sizeMb") or package.get("size_mb") or 0),
        "downloaded": bool(package.get("downloaded")),
        "size": int(package.get("size") or 0),
        "path": str(package.get("path") or ""),
        "sources": deepcopy(package.get("sources") or []),
        "job": deepcopy(package.get("job")),
    }


def _resolve_packages(ids: list[str], packages_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    resolved = []
    for package_id in ids:
        package = packages_by_id.get(package_id)
        if package is None:
            package = {"id": package_id, "title": package_id, "downloaded": False}
        resolved.append(_camel_package(package))
    return resolved


def _status_for_required_packages(packages: list[dict[str, Any]]) -> tuple[str, str]:
    for package in packages:
        job = package.get("job")
        if isinstance(job, dict):
            if job.get("status") == "running":
                return "downloading", f"{package['id']} is downloading"
            if job.get("status") == "error":
                return "package_error", str(job.get("error") or f"{package['id']} download failed")
    for package in packages:
        if not package.get("downloaded"):
            return "missing_package", f"{package['id']} is not installed"
    return "available", ""


def build_capability_status(
    definition: dict[str, Any],
    packages_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    required = _resolve_packages(list(definition.get("required_load_packages") or []), packages_by_id)
    optional = _resolve_packages(list(definition.get("optional_load_packages") or []), packages_by_id)
    status, reason = _status_for_required_packages(required)

    return {
        "id": definition["id"],
        "title": definition["title"],
        "description": definition["description"],
        "category": definition["category"],
        "status": status,
        "statusReason": reason,
        "agentHint": definition["agent_hint"],
        "tools": list(definition.get("tools") or []),
        "requiredToolsets": list(definition.get("required_toolsets") or []),
        "requiredLoadPackages": required,
        "optionalLoadPackages": optional,
        "roles": list(definition.get("roles") or []),
        "risk": definition.get("risk", "low"),
        "source": definition.get("source", "builtin"),
        "trust": definition.get("trust", "official"),
    }


def build_all_capability_statuses(
    definitions: list[dict[str, Any]],
    packages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    packages_by_id = {str(item.get("id")): item for item in packages}
    return [build_capability_status(definition, packages_by_id) for definition in definitions]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```powershell
cd python
python -m unittest tests.test_capability_registry -v
cd ..
```

Expected: all capability registry tests pass.

- [ ] **Step 5: Commit**

```powershell
git add python/src/capability_status.py python/tests/test_capability_registry.py
git commit -m "feat: compute product capability status"
```

---

### Task 3: Backend Catalog Integration

**Files:**
- Modify: `python/src/desk_server/capabilities.py`
- Modify: `python/src/load_packages.py`
- Modify: `python/tests/test_capability_registry.py`

- [ ] **Step 1: Add failing backend payload tests**

Append to `CapabilityRegistryTests`:

```python
    def test_backend_catalog_includes_product_capabilities_and_load_packages(self):
        import os
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from desk_server.capabilities import _build_desk_catalog_payload_unlocked

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "appdata"
            workspace = Path(tmp) / "workspace"
            data_dir.mkdir()
            workspace.mkdir()
            with patch.dict(
                os.environ,
                {
                    "HERMESDESK_DATA_DIR": str(data_dir),
                    "HERMESDESK_WORKSPACE": str(workspace),
                },
                clear=False,
            ):
                payload = _build_desk_catalog_payload_unlocked()

        capability_ids = {item["id"] for item in payload["capabilities"]}
        package_ids = {item["id"] for item in payload["loadPackages"]}

        self.assertIn("document-math", capability_ids)
        self.assertIn("voice-local-stt", capability_ids)
        self.assertIn("docling-codeformula", package_ids)
        self.assertIn("local-stt-base-q5_1", package_ids)

    def test_load_packages_include_used_by_capabilities(self):
        import os
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        import load_packages

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "appdata"
            workspace = Path(tmp) / "workspace"
            data_dir.mkdir()
            workspace.mkdir()
            with patch.dict(
                os.environ,
                {
                    "HERMESDESK_DATA_DIR": str(data_dir),
                    "HERMESDESK_WORKSPACE": str(workspace),
                },
                clear=False,
            ):
                packages = load_packages.list_load_packages()

        formula = next(item for item in packages if item["id"] == "docling-codeformula")
        used_by = {item["id"] for item in formula["usedByCapabilities"]}

        self.assertIn("document-math", used_by)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd python
python -m unittest tests.test_capability_registry -v
cd ..
```

Expected: missing `capabilities`, `loadPackages`, or `usedByCapabilities` fields.

- [ ] **Step 3: Add reverse load-package usage**

Modify `python/src/load_packages.py` by adding helper functions after `_packages()`:

```python
def _package_capability_usage() -> dict[str, list[dict[str, str]]]:
    try:
        from capability_registry import list_capability_defs
    except ImportError:
        return {}

    usage: dict[str, list[dict[str, str]]] = {}
    for capability in list_capability_defs():
        for package_id in list(capability.get("required_load_packages") or []) + list(capability.get("optional_load_packages") or []):
            usage.setdefault(package_id, []).append({
                "id": str(capability["id"]),
                "title": str(capability["title"]),
            })
    return usage
```

Then in `LoadPackage.status()`, add this field:

```python
            "usedByCapabilities": _package_capability_usage().get(self.id, []),
```

- [ ] **Step 4: Extend backend capability payload**

Modify `python/src/desk_server/capabilities.py` imports in `_build_desk_catalog_payload_unlocked()` scope:

```python
def _build_desk_catalog_payload_unlocked() -> Dict[str, Any]:
    from capability_registry import list_capability_defs
    from capability_status import build_all_capability_statuses
    from load_packages import list_load_packages

    policy = _capability_policy()
    load_packages = list_load_packages()
    product_capabilities = build_all_capability_statuses(
        list_capability_defs(),
        load_packages,
    )
    return {
        "role": policy.role,
        "capabilities": product_capabilities,
        "loadPackages": load_packages,
        "skills": _desk_catalog_skills(policy),
        "toolsets": _desk_catalog_toolsets(policy),
        "plugins": _desk_catalog_plugins(policy),
    }
```

- [ ] **Step 5: Run Python tests**

Run:

```powershell
cd python
python -m unittest tests.test_capability_registry tests.test_load_packages -v
cd ..
```

Expected: all selected tests pass. If `test_load_packages.py` expects older source URLs, update only those expected URL strings to match the current source registry in `python/src/load_packages.py`; do not change package behavior in this task.

- [ ] **Step 6: Commit**

```powershell
git add python/src/desk_server/capabilities.py python/src/load_packages.py python/tests/test_capability_registry.py python/tests/test_load_packages.py
git commit -m "feat: expose product capabilities in desktop catalog"
```

---

### Task 4: Web Types and Capability Tab

**Files:**
- Modify: `web/src/chat/chat-api.ts`
- Modify: `web/src/advanced/pages/CapabilitiesPage.tsx`
- Create: `web/src/advanced/capabilitiesUx.test.mjs`
- Modify: `web/package.json`

- [ ] **Step 1: Write the failing web source-contract test**

Create `web/src/advanced/capabilitiesUx.test.mjs`:

```javascript
/* global URL */
import assert from "node:assert/strict";
import fs from "node:fs";

const pageSource = fs.readFileSync(new URL("./pages/CapabilitiesPage.tsx", import.meta.url), "utf8");
const chatApiSource = fs.readFileSync(new URL("../chat/chat-api.ts", import.meta.url), "utf8");
const packageJson = JSON.parse(fs.readFileSync(new URL("../../package.json", import.meta.url), "utf8"));

assert.match(
  chatApiSource,
  /ProductCapabilityStatus[\s\S]*requiredLoadPackages[\s\S]*optionalLoadPackages/,
  "Chat API types should model product capabilities and their load-package dependencies.",
);

assert.match(
  pageSource,
  /type Tab = "capabilities" \| "skills" \| "tools" \| "plugins"/,
  "Capabilities page should add product capabilities as the first tab.",
);

assert.match(
  pageSource,
  /CapabilityProductRow[\s\S]*requiredLoadPackages[\s\S]*cmdLoadPackageDownload/,
  "Product capability rows should show load-package dependencies and trigger downloads.",
);

assert.match(
  pageSource,
  /status === "missing_package"[\s\S]*status === "downloading"[\s\S]*status === "available"/,
  "Product capability UI should distinguish missing, downloading, and available states.",
);

assert.equal(
  packageJson.scripts["test:capabilities-ux"],
  "node src/advanced/capabilitiesUx.test.mjs",
  "Package scripts should expose the capabilities UX source-contract test.",
);
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
cd web
node src/advanced/capabilitiesUx.test.mjs
cd ..
```

Expected: assertions fail because types/tab/UI do not exist.

- [ ] **Step 3: Add web API types**

Modify `web/src/chat/chat-api.ts` after `LoadPackageStatus`:

```ts
export type ProductCapabilityStatus =
  | "available"
  | "missing_package"
  | "downloading"
  | "package_error"
  | "disabled_toolset"
  | "requires_power_user"
  | "unsupported_platform"
  | "error";

export type ProductCapability = {
  id: string;
  title: string;
  description: string;
  category: string;
  status: ProductCapabilityStatus;
  statusReason: string;
  agentHint: string;
  tools: string[];
  requiredToolsets: string[];
  requiredLoadPackages: LoadPackageStatus[];
  optionalLoadPackages: LoadPackageStatus[];
  roles: Array<"default" | "advanced" | "power">;
  risk: "low" | "medium" | "high" | string;
  source: string;
  trust: string;
};
```

- [ ] **Step 4: Add capabilities to the page catalog type**

Modify `web/src/advanced/pages/CapabilitiesPage.tsx` imports:

```ts
import {
  cmdLoadPackageDownload,
  type LoadPackageStatus,
  type ProductCapability,
} from "../../chat/chat-api";
```

Modify local types:

```ts
type Tab = "capabilities" | "skills" | "tools" | "plugins";

type CapabilityCatalog = {
  role: Role;
  capabilities: ProductCapability[];
  loadPackages?: LoadPackageStatus[];
  skills: SkillItem[];
  toolsets: ToolsetItem[];
  plugins: PluginItem[];
};
```

Set default tab:

```ts
const [activeTab, setActiveTab] = useState<Tab>("capabilities");
```

Extend tabs:

```ts
const TABS: Array<{ id: Tab; icon: typeof Package }> = [
  { id: "capabilities", icon: Boxes },
  { id: "skills", icon: Package },
  { id: "tools", icon: Wrench },
  { id: "plugins", icon: Plug },
];
```

- [ ] **Step 5: Add product capability row component**

Add this component in `CapabilitiesPage.tsx` before `CapabilityRow`:

```tsx
function CapabilityProductRow({
  item,
  active,
  busyPackageId,
  onClick,
  onDownloadPackage,
}: {
  item: ProductCapability;
  active: boolean;
  busyPackageId: string | null;
  onClick: () => void;
  onDownloadPackage: (pkg: LoadPackageStatus) => void;
}) {
  const { t } = useI18n();
  const missing = item.requiredLoadPackages.find((pkg) => !pkg.downloaded);
  const running = item.requiredLoadPackages.find((pkg) => pkg.job?.status === "running");
  const status = item.status;

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full rounded-[var(--radius-shell-lg)] border p-4 text-left shadow-[var(--shadow-shell)] transition active:scale-[0.99]",
        active
          ? "border-[var(--kq-color-primary-light)] bg-[var(--hd-info-bg)]"
          : "hd-glass-subtle border-[var(--kq-color-border)] hover:border-[var(--kq-color-primary-light)]",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="hd-card-title">{item.title}</span>
            <Badge tone={status === "available" ? "green" : status === "downloading" ? "blue" : "amber"}>
              {status === "available"
                ? t("capabilities.status.available")
                : status === "downloading"
                  ? t("capabilities.status.downloading")
                  : t("capabilities.status.missingPackage")}
            </Badge>
          </div>
          <p className="hd-body mt-1 line-clamp-2">{item.description}</p>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {item.requiredLoadPackages.map((pkg) => (
              <Badge key={pkg.id} tone={pkg.downloaded ? "green" : "amber"}>
                {pkg.title || pkg.id} · {pkg.downloaded ? t("settings.loadPackageInstalled") : `${pkg.sizeMb} MB`}
              </Badge>
            ))}
          </div>
        </div>
        {missing ? (
          <Button
            size="sm"
            onClick={(event) => {
              event.stopPropagation();
              onDownloadPackage(missing);
            }}
            disabled={!!busyPackageId || !!running}
          >
            <Package className="h-3.5 w-3.5" />
            {busyPackageId === missing.id || running ? t("settings.loadPackageWorking") : t("settings.loadPackageDownload")}
          </Button>
        ) : null}
      </div>
    </button>
  );
}
```

- [ ] **Step 6: Wire product rows into list rendering**

In `CapabilitiesPage`, add state:

```ts
const [busyPackageId, setBusyPackageId] = useState<string | null>(null);
```

Add handler:

```ts
async function downloadCapabilityPackage(pkg: LoadPackageStatus) {
  setBusyPackageId(pkg.id);
  setError(null);
  try {
    await cmdLoadPackageDownload(pkg.id);
    await loadCatalog();
  } catch (err) {
    setError(String(err));
  } finally {
    setBusyPackageId(null);
  }
}
```

Update item selection and rendering so `activeTab === "capabilities"` uses `catalog.capabilities`. The selected union can add:

```ts
| { tab: "capabilities"; item: ProductCapability }
```

In the grid render:

```tsx
{activeTab === "capabilities"
  ? (items as ProductCapability[]).map((item) => (
      <CapabilityProductRow
        key={item.id}
        item={item}
        active={selected?.item.name === item.id || selected?.item.id === item.id}
        busyPackageId={busyPackageId}
        onClick={() => setSelected({ tab: "capabilities", item })}
        onDownloadPackage={downloadCapabilityPackage}
      />
    ))
  : items.map((item) => (
      <CapabilityRow
        key={item.name}
        item={item}
        active={selected?.item.name === item.name}
        onClick={() => openItem(item)}
      />
    ))}
```

- [ ] **Step 7: Add script**

Modify `web/package.json` scripts:

```json
"test:capabilities-ux": "node src/advanced/capabilitiesUx.test.mjs"
```

- [ ] **Step 8: Run web tests**

Run:

```powershell
cd web
npm run test:capabilities-ux
npx tsc --noEmit
cd ..
```

Expected: both pass.

- [ ] **Step 9: Commit**

```powershell
git add web/src/chat/chat-api.ts web/src/advanced/pages/CapabilitiesPage.tsx web/src/advanced/capabilitiesUx.test.mjs web/package.json
git commit -m "feat: show product capabilities in capability page"
```

---

### Task 5: Load Package Page Shows Capability Usage

**Files:**
- Modify: `web/src/advanced/pages/LoadPackagesPage.tsx`
- Modify: `web/src/advanced/settingsLoadPackages.test.mjs`
- Modify: `web/src/locales/strings.ts`

- [ ] **Step 1: Add failing source-contract assertions**

Append to `web/src/advanced/settingsLoadPackages.test.mjs`:

```javascript
assert.match(
  loadPackagesPageSource,
  /usedByCapabilities[\s\S]*settings\.loadPackageUsedBy/,
  "The load-package page should show which product capabilities use each package.",
);
assert.match(stringsSource, /loadPackageUsedBy/);
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd web
npm run test:settings-load-packages
cd ..
```

Expected: missing `usedByCapabilities` rendering/string.

- [ ] **Step 3: Add web type field**

Modify `web/src/chat/chat-api.ts` `LoadPackageStatus`:

```ts
usedByCapabilities?: Array<{ id: string; title: string }>;
```

- [ ] **Step 4: Render usage in load-package page**

In `web/src/advanced/pages/LoadPackagesPage.tsx`, inside each package card, render:

```tsx
{pkg.usedByCapabilities?.length ? (
  <p className="mt-2 text-xs text-[var(--kq-color-muted)] dark:text-zinc-500">
    {t("settings.loadPackageUsedBy", {
      names: pkg.usedByCapabilities.map((item) => item.title || item.id).join("、"),
    })}
  </p>
) : null}
```

- [ ] **Step 5: Add localized strings**

Modify `web/src/locales/strings.ts`:

```ts
loadPackageUsedBy: "用于：{names}",
```

and the English equivalent:

```ts
loadPackageUsedBy: "Used by: {names}",
```

- [ ] **Step 6: Run tests**

Run:

```powershell
cd web
npm run test:settings-load-packages
npx tsc --noEmit
cd ..
```

Expected: both pass.

- [ ] **Step 7: Commit**

```powershell
git add web/src/chat/chat-api.ts web/src/advanced/pages/LoadPackagesPage.tsx web/src/advanced/settingsLoadPackages.test.mjs web/src/locales/strings.ts
git commit -m "feat: link load packages to product capabilities"
```

---

### Task 6: Agent Capability Self-Knowledge

**Files:**
- Create: `python/src/capability_prompt.py`
- Modify: `python/src/desk_server/chat_core.py`
- Create or Modify: `python/tests/test_desk_server.py`

- [ ] **Step 1: Write failing prompt summary test**

Add to `python/tests/test_capability_registry.py`:

```python
    def test_agent_summary_mentions_available_and_missing_capabilities(self):
        from capability_prompt import build_capability_prompt_summary

        capabilities = [
            {
                "id": "document-precise-read",
                "title": "Precise document reading",
                "status": "available",
                "agentHint": "Use for structured document reading.",
                "requiredLoadPackages": [],
            },
            {
                "id": "document-math",
                "title": "Formula extraction and LaTeX",
                "status": "missing_package",
                "agentHint": "Use for math extraction.",
                "requiredLoadPackages": [{"id": "docling-codeformula", "title": "Docling CodeFormula"}],
            },
        ]

        summary = build_capability_prompt_summary(capabilities)

        self.assertIn("Precise document reading: available", summary)
        self.assertIn("Formula extraction and LaTeX: missing_package", summary)
        self.assertIn("docling-codeformula", summary)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd python
python -m unittest tests.test_capability_registry -v
cd ..
```

Expected: import failure for `capability_prompt`.

- [ ] **Step 3: Implement prompt summary**

Create `python/src/capability_prompt.py`:

```python
# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Compact agent-facing summary of Nana's current product capabilities."""

from __future__ import annotations

from typing import Any


def build_capability_prompt_summary(capabilities: list[dict[str, Any]]) -> str:
    lines = ["Current Kabuqina product capabilities:"]
    for item in capabilities:
        status = str(item.get("status") or "error")
        title = str(item.get("title") or item.get("id") or "unknown")
        hint = str(item.get("agentHint") or "").strip()
        packages = [
            str(pkg.get("id") or pkg.get("title") or "")
            for pkg in item.get("requiredLoadPackages") or []
            if not pkg.get("downloaded", status == "available")
        ]
        suffix = f" Missing package(s): {', '.join(packages)}." if packages else ""
        hint_suffix = f" {hint}" if hint else ""
        lines.append(f"- {title}: {status}.{suffix}{hint_suffix}")
    return "\n".join(lines)
```

- [ ] **Step 4: Inject summary at desktop chat boundary**

In `python/src/desk_server/chat_core.py`, find the message/request construction path before sending to Hermes. Add a helper import and append the summary to the desktop system/developer context in the same style as existing desktop prompt additions:

```python
from capability_prompt import build_capability_prompt_summary
from desk_server.capabilities import get_desk_catalog_payload_cached


def current_capability_prompt_summary() -> str:
    payload = get_desk_catalog_payload_cached()
    return build_capability_prompt_summary(list(payload.get("capabilities") or []))
```

Then include `current_capability_prompt_summary()` in the desktop-only prompt material. Keep this integration inside `python/src/` because it reflects desktop installation state; do not move it into `hermes_core`.

- [ ] **Step 5: Add route/core test for summary hook**

Add a small test in `python/tests/test_desk_server.py` that imports `current_capability_prompt_summary()` and asserts it returns a string containing `Current Kabuqina product capabilities`.

```python
def test_capability_prompt_summary_available():
    from desk_server.chat_core import current_capability_prompt_summary

    summary = current_capability_prompt_summary()

    assert "Current Kabuqina product capabilities" in summary
```

- [ ] **Step 6: Run tests**

Run:

```powershell
cd python
python -m unittest tests.test_capability_registry tests.test_desk_server -v
cd ..
```

Expected: selected tests pass.

- [ ] **Step 7: Commit**

```powershell
git add python/src/capability_prompt.py python/src/desk_server/chat_core.py python/tests/test_capability_registry.py python/tests/test_desk_server.py
git commit -m "feat: summarize product capabilities for Nana"
```

---

### Task 7: Localization and Visual Polish

**Files:**
- Modify: `web/src/locales/strings.ts`
- Modify: `web/src/advanced/pages/CapabilitiesPage.tsx`
- Modify: `web/src/advanced/capabilitiesUx.test.mjs`

- [ ] **Step 1: Add failing localization assertions**

Append to `web/src/advanced/capabilitiesUx.test.mjs`:

```javascript
const stringsSource = fs.readFileSync(new URL("../locales/strings.ts", import.meta.url), "utf8");

assert.match(stringsSource, /capabilities:[\s\S]*status:[\s\S]*available/);
assert.match(stringsSource, /missingPackage/);
assert.match(stringsSource, /productCapabilities/);
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd web
npm run test:capabilities-ux
cd ..
```

Expected: missing strings.

- [ ] **Step 3: Add strings**

Modify `web/src/locales/strings.ts` under `capabilities`:

```ts
productCapabilities: "产品能力",
status: {
  available: "可用",
  missingPackage: "缺少加载包",
  downloading: "下载中",
  packageError: "加载包错误",
  disabledToolset: "工具未启用",
  requiresPowerUser: "需要高级用户",
  unsupportedPlatform: "当前平台不支持",
  error: "不可用",
},
```

English:

```ts
productCapabilities: "Product capabilities",
status: {
  available: "Available",
  missingPackage: "Missing package",
  downloading: "Downloading",
  packageError: "Package error",
  disabledToolset: "Toolset disabled",
  requiresPowerUser: "Power user required",
  unsupportedPlatform: "Unsupported platform",
  error: "Unavailable",
},
```

- [ ] **Step 4: Use product capability string in tab**

In `CapabilitiesPage.tsx`, when rendering tab text, special-case:

```tsx
{id === "capabilities" ? t("capabilities.productCapabilities") : t(`capabilities.${id}`)}
```

- [ ] **Step 5: Run web validation**

Run:

```powershell
cd web
npm run test:capabilities-ux
npm run lint
npm run build
cd ..
```

Expected: commands pass. Existing unrelated source-contract failures should be fixed in their owning files before completing this task.

- [ ] **Step 6: Commit**

```powershell
git add web/src/locales/strings.ts web/src/advanced/pages/CapabilitiesPage.tsx web/src/advanced/capabilitiesUx.test.mjs
git commit -m "feat: polish product capability UI labels"
```

---

### Task 8: Full Verification and Docs

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/safety.md`
- Modify: `DECISIONS.md`

- [ ] **Step 1: Document the capability/load-package boundary**

Add to `docs/architecture.md`:

```markdown
## Product Capability Map

Kabuqina separates product capabilities from their implementation resources:

- Capability: user- and agent-facing description of what Nana can do.
- Tool/toolset: executable implementation path used by the agent.
- Load package: large local resource required by one or more capabilities.
- Skill/plugin: extension source that can contribute capability implementations.

Capabilities declare required and optional load packages. The load-package registry owns download, delete, progress, paths, and source URLs. Capability status is computed from the registry at runtime.
```

- [ ] **Step 2: Document the safety rule**

Add to `docs/safety.md`:

```markdown
## Capability Dependencies

Agent prompts may summarize available and missing capabilities, but tool execution must still enforce dependency checks server-side. A missing package must produce a stable error and a user-facing download path; the model must not infer availability from the prompt alone.
```

- [ ] **Step 3: Record the product decision**

Add to `DECISIONS.md`:

```markdown
## 2026-06-01 — Product capabilities vs load packages

First-party features such as formula extraction, local STT, CodeT5-style code intelligence, and Latexify-style conversion are modeled as product capabilities. Large model weights and runtime assets are modeled as load packages. Capabilities reference load packages; load packages do not encode product semantics.
```

- [ ] **Step 4: Run full selected verification**

Run:

```powershell
cd python
python -m unittest tests.test_capability_registry tests.test_load_packages tests.test_policy_contract tests.test_desk_server -v
cd ..
cd web
npm run test:capabilities-ux
npm run test:settings-load-packages
npm run lint
npm run build
cd ..
```

Expected: all commands pass.

- [ ] **Step 5: Commit**

```powershell
git add docs/architecture.md docs/safety.md DECISIONS.md
git commit -m "docs: record capability and load-package architecture"
```

---

## Future Capability Onboarding Template

Use this template for CodeT5, Latexify, or similar first-party product additions.

```text
1. Add load package in python/src/load_packages.py if the capability needs a large local model.
2. Add product capability in python/src/capability_registry.py.
3. Add or expose the agent tool in hermes_core if both web and gateway children should share it.
4. Add desktop-only download/path/wiring under python/src when the behavior depends on Windows or local data directories.
5. Add tests in python/tests/test_capability_registry.py and the relevant tool tests.
6. Verify the capability page shows status, dependencies, and download action.
7. Verify Nana's capability prompt summary reports available/missing state correctly.
```

For CodeT5:

```text
Capability id: code-intelligence
Required load package: codet5-base or codet5-large
Tools: code_explain, code_summarize, code_generate_tests
Likely location: hermes_core/tools for shared semantics, python/src for local model paths
```

For Latexify:

```text
Capability id: image-to-latex
Required load package: latexify-model
Optional load package: docling-codeformula
Tools: image_to_latex, latex_clean
Likely location: hermes_core/tools for tool contract, python/src for model cache and Windows runtime details
```

## Self-Review

- Spec coverage: The plan covers registry, status computation, backend catalog, capability page UI, load-package reverse usage, agent self-knowledge, localization, docs, and verification.
- Placeholder scan: No placeholder task remains; each task names exact files, expected tests, and implementation snippets.
- Type consistency: Python uses snake_case definitions internally and emits camelCase fields for web payloads. Web types use `ProductCapability`, `LoadPackageStatus`, `requiredLoadPackages`, and `optionalLoadPackages` consistently.
