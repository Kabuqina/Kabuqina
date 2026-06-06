# Load Package Agent Paths Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Kabuqina product capabilities executable by connecting each capability to at least one pipeline, exposing package paths to Nana through the workspace, preserving Docling CodeFormula runtime wiring, and adding shortcut metadata for later feature-specific frontend entrypoints.

**Architecture:** Product capability definitions in `python/src/capability_registry.py` become the source of truth for stages, pipelines, steps, tools, package dependencies, and shortcut candidates. Runtime status in `python/src/capability_status.py` derives availability from pipeline readiness, load package state, and tool policy. Load package resolution and workspace manifests live in `python/src/load_packages.py`, while Docling-specific artifact merging stays in `python/src/docling_math_models.py` and document extraction semantics stay in `hermes_core/tools/document_tools.py`.

**Tech Stack:** Python 3.11-compatible stdlib modules, FastAPI desk routes, existing unittest/pytest tests, React/Vite source-contract tests.

---

## File Structure

- Modify `python/src/capability_registry.py`: add pipeline schema, validation helpers, and derived compatibility fields.
- Modify `python/src/capability_status.py`: compute status from pipeline readiness.
- Modify `python/src/capability_prompt.py`: expose executable pipeline summaries to Nana.
- Modify `python/src/load_packages.py`: add bundled/user/fallback path resolution, `realPath`, `agentPath`, and workspace index refresh.
- Modify `python/src/docling_math_models.py`: resolve CodeFormula through the load-package resolver while preserving merged Docling artifacts.
- Modify `python/src/desk_server/capabilities.py`: include pipeline and package path metadata in the catalog payload.
- Modify `hermes_core/tools/document_tools.py`: keep `mode=math` runtime validation and, if needed, align hints with cross-document `document-math`.
- Modify `python/tests/test_capability_registry.py`: add registry/status/prompt tests.
- Modify `python/tests/test_load_packages.py`: add package path and workspace index tests.
- Modify `python/tests/test_docling_math_models.py`: add CodeFormula resolver tests.
- Modify `hermes_core/tests/tools/test_document_tools.py`: add any cross-document math hint tests.
- Modify `web/src/chat/chat-api.ts`: add pipeline/path metadata types.
- Modify `web/src/advanced/pages/CapabilitiesPage.tsx`: show stages and pipelines.
- Modify `web/src/advanced/pages/LoadPackagesPage.tsx` and/or `web/src/advanced/settings/SettingsLoadPackages.tsx`: show `realPath`, `agentPath`, and capability usage.
- Do not implement every shortcut surface in this plan; only carry shortcut metadata through the catalog and display shortcut candidates.
- Modify `web/src/advanced/capabilitiesPage.test.mjs` and `web/src/advanced/settingsLoadPackages.test.mjs`: source-contract coverage.

---

### Task 1: Capability Pipeline Schema

**Files:**
- Modify: `python/src/capability_registry.py`
- Test: `python/tests/test_capability_registry.py`

- [ ] **Step 1: Write failing tests for mandatory pipelines**

Append these tests to `python/tests/test_capability_registry.py`:

```python
    def test_every_capability_declares_pipeline_steps(self):
        from capability_registry import list_capability_defs

        for capability in list_capability_defs():
            self.assertTrue(capability.get("pipelines"), capability["id"])
            for pipeline in capability["pipelines"]:
                self.assertTrue(pipeline.get("id"), capability["id"])
                self.assertTrue(pipeline.get("steps"), pipeline.get("id"))
                for step in pipeline["steps"]:
                    self.assertIn(step.get("stage"), {"reader", "material_index", "planner", "writer"})
                    self.assertTrue(step.get("outputs"), step)

    def test_document_math_is_cross_document_reader_pipeline(self):
        from capability_registry import get_capability_def

        math = get_capability_def("document-math")
        pipeline_ids = {item["id"] for item in math["pipelines"]}

        self.assertIn("docling-math-document-read", pipeline_ids)
        self.assertIn("docling-math-pdf-read", pipeline_ids)
        primary = next(item for item in math["pipelines"] if item["id"] == "docling-math-document-read")
        self.assertEqual(primary["stages"], ["reader"])
        self.assertIn("pptx", primary["inputs"])
        self.assertEqual(primary["steps"][0]["tool"], "document_read_precise")
        self.assertEqual(primary["steps"][0]["default_args"], {"mode": "math"})
        self.assertIn("docling-codeformula", primary["steps"][0]["required_load_packages"])
        self.assertIn("formulas", primary["steps"][0]["outputs"])

    def test_student_ppt_pipeline_declares_four_layer_flow(self):
        from capability_registry import get_capability_def

        ppt = get_capability_def("student-ppt")
        pipeline = next(item for item in ppt["pipelines"] if item["id"] == "student-ppt-from-documents")
        stages = [step["stage"] for step in pipeline["steps"]]

        self.assertEqual(stages, ["reader", "material_index", "planner", "writer"])

    def test_shortcuts_reference_existing_pipelines(self):
        from capability_registry import list_capability_defs

        allowed_surfaces = {"chat_quick_action", "wizard", "settings_action", "context_menu"}
        for capability in list_capability_defs():
            pipeline_ids = {pipeline["id"] for pipeline in capability.get("pipelines") or []}
            for shortcut in capability.get("shortcuts") or []:
                self.assertIn(shortcut["surface"], allowed_surfaces)
                self.assertIn(shortcut["entry_pipeline"], pipeline_ids)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd python
python -m unittest tests.test_capability_registry -v
cd ..
```

Expected: failures because existing capability definitions do not expose `pipelines`.

- [ ] **Step 3: Implement pipeline definitions and derived fields**

In `python/src/capability_registry.py`, add helpers near the top:

```python
VALID_FRAMEWORK_STAGES = ("reader", "material_index", "planner", "writer")


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _derive_fields(capability: dict[str, Any]) -> dict[str, Any]:
    pipelines = list(capability.get("pipelines") or [])
    stages: list[str] = []
    tools: list[str] = []
    required_packages: list[str] = []
    optional_packages: list[str] = []
    for pipeline in pipelines:
        stages.extend([str(stage) for stage in pipeline.get("stages") or []])
        for step in pipeline.get("steps") or []:
            stage = str(step.get("stage") or "")
            if stage:
                stages.append(stage)
            tool = str(step.get("tool") or "")
            if tool:
                tools.append(tool)
            tools.extend([str(tool) for tool in step.get("tools") or []])
            required_packages.extend([str(pkg) for pkg in step.get("required_load_packages") or []])
            optional_packages.extend([str(pkg) for pkg in step.get("optional_load_packages") or []])
    merged = dict(capability)
    merged["stages"] = _unique(stages)
    merged["tools"] = _unique(list(capability.get("tools") or []) + tools)
    merged["required_load_packages"] = _unique(
        list(capability.get("required_load_packages") or []) + required_packages
    )
    merged["optional_load_packages"] = _unique(
        list(capability.get("optional_load_packages") or []) + optional_packages
    )
    return merged
```

Update `list_capability_defs()` and `get_capability_def()`:

```python
def list_capability_defs() -> list[dict[str, Any]]:
    return [_derive_fields(deepcopy(item)) for item in _CAPABILITIES]


def get_capability_def(capability_id: str) -> dict[str, Any]:
    for item in _CAPABILITIES:
        if item["id"] == capability_id:
            return _derive_fields(deepcopy(item))
    raise KeyError(capability_id)
```

Add `pipelines` to `document-precise-read`, `document-math`, `voice-local-stt`, `desktop-organizer`, and `student-ppt`. Add `shortcuts` only where there is a credible future frontend entrypoint. Use this exact `document-math` shape:

```python
"pipelines": [
    {
        "id": "docling-math-document-read",
        "title": "Docling math document read",
        "primary": True,
        "stages": ["reader"],
        "inputs": ["pdf", "docx", "pptx", "xlsx", "html", "markdown", "image"],
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
    },
    {
        "id": "docling-math-pdf-read",
        "title": "Docling math PDF read",
        "primary": False,
        "stages": ["reader"],
        "inputs": ["pdf"],
        "steps": [
            {
                "id": "read-pdf-math",
                "stage": "reader",
                "tool": "pdf_read_precise",
                "default_args": {"mode": "math"},
                "required_load_packages": ["docling-codeformula"],
                "outputs": ["read_id", "markdown", "formulas"],
            }
        ],
    },
],
"shortcuts": [
    {
        "id": "extract-formulas",
        "surface": "chat_quick_action",
        "label": "Extract formulas",
        "entry_pipeline": "docling-math-document-read",
        "requires_input": ["document"],
        "visible_when": "pipeline_ready_or_downloadable",
    }
],
```

- [ ] **Step 4: Run registry tests**

Run:

```powershell
cd python
python -m unittest tests.test_capability_registry -v
cd ..
```

Expected: all capability registry tests pass.

- [ ] **Step 5: Commit**

```powershell
git add python/src/capability_registry.py python/tests/test_capability_registry.py
git commit -m "feat: add executable capability pipelines"
```

---

### Task 2: Pipeline-Derived Capability Status

**Files:**
- Modify: `python/src/capability_status.py`
- Test: `python/tests/test_capability_registry.py`

- [ ] **Step 1: Write failing status tests**

Append these tests:

```python
    def test_pipeline_missing_package_marks_capability_missing(self):
        from capability_registry import get_capability_def
        from capability_status import build_capability_status

        packages = {
            "docling-codeformula": {
                "id": "docling-codeformula",
                "title": "Docling CodeFormula",
                "downloaded": False,
                "job": None,
            }
        }
        result = build_capability_status(
            get_capability_def("document-math"),
            load_packages=packages,
            enabled_toolsets={"documents"},
        )

        self.assertEqual(result["status"], "missing_package")
        self.assertIn("docling-codeformula", result["statusReason"])

    def test_pipeline_ready_marks_capability_available(self):
        from capability_registry import get_capability_def
        from capability_status import build_capability_status

        packages = {
            "docling-codeformula": {
                "id": "docling-codeformula",
                "title": "Docling CodeFormula",
                "downloaded": True,
                "job": None,
            }
        }
        result = build_capability_status(
            get_capability_def("document-math"),
            load_packages=packages,
            enabled_toolsets={"documents"},
        )

        self.assertEqual(result["status"], "available")
        self.assertTrue(result["pipelines"][0]["ready"])
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd python
python -m unittest tests.test_capability_registry -v
cd ..
```

Expected: failure because `build_capability_status` either does not exist or does not evaluate pipeline readiness.

- [ ] **Step 3: Implement pipeline status**

In `python/src/capability_status.py`, implement or update:

```python
def _package_downloaded(package_id: str, load_packages: dict[str, dict]) -> bool:
    package = load_packages.get(package_id) or {}
    return bool(package.get("downloaded"))


def _step_ready(step: dict, *, load_packages: dict[str, dict], enabled_toolsets: set[str]) -> tuple[bool, str]:
    for package_id in step.get("required_load_packages") or []:
        if not _package_downloaded(str(package_id), load_packages):
            return False, f"missing package: {package_id}"
    return True, ""


def _pipeline_ready(pipeline: dict, *, load_packages: dict[str, dict], enabled_toolsets: set[str]) -> tuple[dict, bool, str]:
    reasons: list[str] = []
    ready = True
    steps = []
    for step in pipeline.get("steps") or []:
        step_ok, reason = _step_ready(step, load_packages=load_packages, enabled_toolsets=enabled_toolsets)
        step_copy = dict(step)
        step_copy["ready"] = step_ok
        if reason:
            step_copy["statusReason"] = reason
            reasons.append(reason)
        steps.append(step_copy)
        ready = ready and step_ok
    pipeline_copy = dict(pipeline)
    pipeline_copy["steps"] = steps
    pipeline_copy["ready"] = ready
    if reasons:
        pipeline_copy["statusReason"] = "; ".join(_dedupe(reasons))
    return pipeline_copy, ready, pipeline_copy.get("statusReason", "")


def build_capability_status(capability: dict, *, load_packages: dict[str, dict], enabled_toolsets: set[str]) -> dict:
    pipelines = []
    ready_count = 0
    reasons: list[str] = []
    for pipeline in capability.get("pipelines") or []:
        evaluated, ready, reason = _pipeline_ready(
            pipeline,
            load_packages=load_packages,
            enabled_toolsets=enabled_toolsets,
        )
        pipelines.append(evaluated)
        ready_count += 1 if ready else 0
        if reason:
            reasons.append(reason)

    result = dict(capability)
    result["pipelines"] = pipelines
    if ready_count:
        result["status"] = "available" if ready_count == len(pipelines) else "partial"
        result["statusReason"] = ""
    elif reasons and all("missing package" in reason for reason in reasons):
        result["status"] = "missing_package"
        result["statusReason"] = "; ".join(_dedupe(reasons))
    else:
        result["status"] = "disabled_toolset" if reasons else "error"
        result["statusReason"] = "; ".join(_dedupe(reasons)) or "no ready pipelines"
    return result
```

Add helper:

```python
def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out
```

- [ ] **Step 4: Run status tests**

Run:

```powershell
cd python
python -m unittest tests.test_capability_registry -v
cd ..
```

Expected: tests pass.

- [ ] **Step 5: Commit**

```powershell
git add python/src/capability_status.py python/tests/test_capability_registry.py
git commit -m "feat: derive capability status from pipelines"
```

---

### Task 3: Agent Prompt Pipeline Summary

**Files:**
- Modify: `python/src/capability_prompt.py`
- Test: `python/tests/test_capability_registry.py`

- [ ] **Step 1: Write failing prompt test**

Append:

```python
    def test_capability_prompt_includes_executable_pipeline(self):
        from capability_prompt import build_capability_prompt_summary

        summary = build_capability_prompt_summary([
            {
                "id": "document-math",
                "title": "Formula extraction and LaTeX",
                "status": "available",
                "pipelines": [
                    {
                        "id": "docling-math-document-read",
                        "ready": True,
                        "steps": [
                            {
                                "stage": "reader",
                                "tool": "document_read_precise",
                                "default_args": {"mode": "math"},
                                "outputs": ["read_id", "markdown", "formulas"],
                            }
                        ],
                    }
                ],
            }
        ])

        self.assertIn("docling-math-document-read", summary)
        self.assertIn("document_read_precise(mode=math)", summary)
        self.assertIn("outputs: read_id, markdown, formulas", summary)
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
cd python
python -m unittest tests.test_capability_registry -v
cd ..
```

Expected: failure because prompt summary does not include pipeline invocation details.

- [ ] **Step 3: Implement pipeline prompt formatting**

In `python/src/capability_prompt.py`, add:

```python
def _format_step(step: dict[str, Any]) -> str:
    tool = str(step.get("tool") or step.get("kind") or "").strip()
    args = step.get("default_args") or {}
    if tool and args:
        arg_text = ", ".join(f"{key}={value}" for key, value in args.items())
        invocation = f"{tool}({arg_text})"
    else:
        invocation = tool or str(step.get("stage") or "step")
    outputs = ", ".join(str(item) for item in step.get("outputs") or [])
    suffix = f" -> outputs: {outputs}" if outputs else ""
    return f"{step.get('stage')}: {invocation}{suffix}"


def _format_ready_pipeline(pipeline: dict[str, Any]) -> str:
    steps = [_format_step(step) for step in pipeline.get("steps") or []]
    return f"{pipeline.get('id')}: " + " | ".join(steps)
```

Update `build_capability_prompt_summary` to append up to two ready pipeline summaries:

```python
        ready_pipelines = [
            _format_ready_pipeline(pipeline)
            for pipeline in item.get("pipelines") or []
            if pipeline.get("ready", item.get("status") == "available")
        ][:2]
        pipeline_suffix = f" Pipelines: {'; '.join(ready_pipelines)}." if ready_pipelines else ""
        lines.append(f"- {title}: {status}.{suffix}{hint_suffix}{pipeline_suffix}")
```

- [ ] **Step 4: Run prompt tests**

Run:

```powershell
cd python
python -m unittest tests.test_capability_registry -v
cd ..
```

Expected: tests pass.

- [ ] **Step 5: Commit**

```powershell
git add python/src/capability_prompt.py python/tests/test_capability_registry.py
git commit -m "feat: include executable pipelines in capability prompt"
```

---

### Task 4: Load Package Path Resolver And Workspace Index

**Files:**
- Modify: `python/src/load_packages.py`
- Test: `python/tests/test_load_packages.py`

- [ ] **Step 1: Write failing path resolver tests**

Append to `python/tests/test_load_packages.py`:

```python
    def test_package_status_prefers_user_path_over_bundled_path(self):
        import os
        import tempfile
        from pathlib import Path
        import load_packages

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            user_payload = root / "data" / "load-packages" / "docling-codeformula" / "ds4sd--CodeFormula"
            bundled_payload = root / "runtime" / "load-packages" / "docling-codeformula" / "ds4sd--CodeFormula"
            user_payload.mkdir(parents=True)
            bundled_payload.mkdir(parents=True)
            (user_payload / "model.safetensors").write_bytes(b"user")
            (bundled_payload / "model.safetensors").write_bytes(b"bundle")

            old_data = os.environ.get("HERMESDESK_DATA_DIR")
            old_bundle = os.environ.get("HERMESDESK_BUNDLE_DIR")
            try:
                os.environ["HERMESDESK_DATA_DIR"] = str(root / "data")
                os.environ["HERMESDESK_BUNDLE_DIR"] = str(root / "runtime")
                status = load_packages.package_status("docling-codeformula")
            finally:
                if old_data is None:
                    os.environ.pop("HERMESDESK_DATA_DIR", None)
                else:
                    os.environ["HERMESDESK_DATA_DIR"] = old_data
                if old_bundle is None:
                    os.environ.pop("HERMESDESK_BUNDLE_DIR", None)
                else:
                    os.environ["HERMESDESK_BUNDLE_DIR"] = old_bundle

        self.assertEqual(status["realPath"], str(user_payload))
        self.assertEqual(status["source"], "downloaded")
        self.assertEqual(status["path"], status["realPath"])

    def test_workspace_index_writes_manifests(self):
        import json
        import os
        import tempfile
        from pathlib import Path
        import load_packages

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workspace = root / "workspace"
            workspace.mkdir()
            payload = root / "data" / "load-packages" / "docling-codeformula" / "ds4sd--CodeFormula"
            payload.mkdir(parents=True)
            (payload / "model.safetensors").write_bytes(b"x")
            old_data = os.environ.get("HERMESDESK_DATA_DIR")
            old_workspace = os.environ.get("HERMESDESK_WORKSPACE")
            try:
                os.environ["HERMESDESK_DATA_DIR"] = str(root / "data")
                os.environ["HERMESDESK_WORKSPACE"] = str(workspace)
                load_packages.refresh_workspace_package_index()
            finally:
                if old_data is None:
                    os.environ.pop("HERMESDESK_DATA_DIR", None)
                else:
                    os.environ["HERMESDESK_DATA_DIR"] = old_data
                if old_workspace is None:
                    os.environ.pop("HERMESDESK_WORKSPACE", None)
                else:
                    os.environ["HERMESDESK_WORKSPACE"] = old_workspace

            index = workspace / ".hermesdesk" / "load-packages" / "packages.json"
            per_package = workspace / ".hermesdesk" / "load-packages" / "docling-codeformula.json"
            real_path = workspace / ".hermesdesk" / "load-packages" / "docling-codeformula" / "real-path.txt"

            self.assertTrue(index.exists())
            self.assertTrue(per_package.exists())
            self.assertEqual(real_path.read_text(encoding="utf-8"), str(payload))
            data = json.loads(index.read_text(encoding="utf-8"))
            self.assertEqual(data["version"], 1)
            self.assertEqual(data["packages"][0]["agentPath"], ".hermesdesk/load-packages/docling-codeformula")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd python
python -m unittest tests.test_load_packages -v
cd ..
```

Expected: failures because `realPath`, `source`, `agentPath`, and workspace index are missing.

- [ ] **Step 3: Implement resolver helpers**

In `python/src/load_packages.py`, add:

```python
def _data_dir() -> Path:
    raw = os.environ.get("HERMESDESK_DATA_DIR")
    if raw:
        return Path(raw)
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "com.kabuqina.app"


def _bundle_dir() -> Optional[Path]:
    raw = os.environ.get("HERMESDESK_BUNDLE_DIR", "").strip()
    return Path(raw) if raw else None


def user_package_root(package_id: str) -> Path:
    return _data_dir() / "load-packages" / package_id


def bundled_package_root(package_id: str) -> Optional[Path]:
    bundle = _bundle_dir()
    if bundle is None:
        return None
    return bundle / "load-packages" / package_id


def resolve_package_payload(package_id: str, payload_folder: str, *, fallback: Optional[Path] = None) -> dict[str, Any]:
    candidates = [
        ("downloaded", user_package_root(package_id) / payload_folder),
    ]
    bundled = bundled_package_root(package_id)
    if bundled is not None:
        candidates.append(("bundled", bundled / payload_folder))
    if fallback is not None:
        candidates.append(("fallback", fallback))
    for source, path in candidates:
        if path.is_dir():
            return {"source": source, "realPath": str(path), "downloaded": True}
    missing = user_package_root(package_id) / payload_folder
    return {"source": "missing", "realPath": str(missing), "downloaded": False}
```

Update package status serialization to include `realPath`, `agentPath`, `source`, and compatibility `path`.

- [ ] **Step 4: Implement workspace index**

Add:

```python
def _workspace_root() -> Optional[Path]:
    raw = os.environ.get("HERMESDESK_WORKSPACE") or os.environ.get("HERMES_WORKSPACE")
    return Path(raw) if raw else None


def refresh_workspace_package_index() -> dict[str, Any]:
    workspace = _workspace_root()
    if workspace is None:
        return {"ok": False, "reason": "workspace_unavailable"}
    root = workspace / ".hermesdesk" / "load-packages"
    root.mkdir(parents=True, exist_ok=True)
    packages = list_packages()
    for package in packages:
        package_id = package["id"]
        package_dir = root / package_id
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "real-path.txt").write_text(str(package.get("realPath") or ""), encoding="utf-8")
        (root / f"{package_id}.json").write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "packages.json").write_text(
        json.dumps({"version": 1, "packages": packages}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"ok": True, "path": str(root)}
```

Import `json` and `os` if missing.

- [ ] **Step 5: Run package tests**

Run:

```powershell
cd python
python -m unittest tests.test_load_packages -v
cd ..
```

Expected: tests pass.

- [ ] **Step 6: Commit**

```powershell
git add python/src/load_packages.py python/tests/test_load_packages.py
git commit -m "feat: expose load package paths to agent workspace"
```

---

### Task 5: CodeFormula Resolver Through Load Packages

**Files:**
- Modify: `python/src/docling_math_models.py`
- Test: `python/tests/test_docling_math_models.py`

- [ ] **Step 1: Write failing CodeFormula resolver test**

Append:

```python
    def test_user_formula_dir_uses_load_package_root(self):
        import os
        import tempfile
        from pathlib import Path
        import docling_math_models as dmm

        with tempfile.TemporaryDirectory() as td:
            data = Path(td) / "data"
            old = os.environ.get("HERMESDESK_DATA_DIR")
            try:
                os.environ["HERMESDESK_DATA_DIR"] = str(data)
                expected = data / "load-packages" / "docling-codeformula" / dmm.CODE_FORMULA_FOLDER
                self.assertEqual(dmm.user_formula_dir(), expected)
            finally:
                if old is None:
                    os.environ.pop("HERMESDESK_DATA_DIR", None)
                else:
                    os.environ["HERMESDESK_DATA_DIR"] = old
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
cd python
python -m unittest tests.test_docling_math_models -v
cd ..
```

Expected: failure if `user_formula_dir()` still resolves under the old `docling-models` path.

- [ ] **Step 3: Update CodeFormula path**

In `python/src/docling_math_models.py`, update `user_formula_dir()`:

```python
def user_formula_dir() -> Path:
    try:
        from load_packages import user_package_root

        return user_package_root("docling-codeformula") / CODE_FORMULA_FOLDER
    except Exception:
        return desktop_data_dir() / "load-packages" / "docling-codeformula" / CODE_FORMULA_FOLDER
```

Keep compatibility fallback in `resolve_docling_artifacts_path()` by checking the old path only if the new path is missing:

```python
def _legacy_formula_dir() -> Path:
    return desktop_data_dir() / "docling-models" / CODE_FORMULA_FOLDER
```

When materializing merged artifacts, prefer `user_formula_dir()` and then `_legacy_formula_dir()`.

- [ ] **Step 4: Run Docling tests**

Run:

```powershell
cd python
python -m unittest tests.test_docling_math_models -v
cd ..
```

Expected: tests pass.

- [ ] **Step 5: Commit**

```powershell
git add python/src/docling_math_models.py python/tests/test_docling_math_models.py
git commit -m "feat: resolve CodeFormula through load package root"
```

---

### Task 6: Desk Capability Catalog Payload

**Files:**
- Modify: `python/src/desk_server/capabilities.py`
- Test: `python/tests/test_desk_server.py` or `python/tests/test_capability_registry.py`

- [ ] **Step 1: Write failing catalog test**

Add a test that calls the existing capability catalog builder and asserts pipeline data survives:

```python
    def test_capability_catalog_includes_pipeline_metadata(self):
        from desk_server.capabilities import build_capabilities_catalog

        catalog = build_capabilities_catalog()
        math = next(item for item in catalog["capabilities"] if item["id"] == "document-math")

        self.assertIn("pipelines", math)
        self.assertTrue(math["pipelines"])
        self.assertIn("stages", math)
        self.assertIn("reader", math["stages"])
        self.assertIn("shortcuts", math)
        self.assertEqual(math["shortcuts"][0]["entryPipeline"], "docling-math-document-read")
```

- [ ] **Step 2: Run desk tests to verify failure**

Run:

```powershell
cd python
python -m unittest tests.test_desk_server -v
cd ..
```

Expected: failure if catalog strips `pipelines` or `stages`.

- [ ] **Step 3: Preserve new fields**

In `python/src/desk_server/capabilities.py`, when converting Python snake_case registry fields to frontend camelCase, map:

```python
"stages": item.get("stages") or [],
"pipelines": _camelize_pipelines(item.get("pipelines") or []),
"shortcuts": _camelize_shortcuts(item.get("shortcuts") or []),
```

Implement:

```python
def _camelize_pipelines(pipelines: list[dict]) -> list[dict]:
    out = []
    for pipeline in pipelines:
        converted = dict(pipeline)
        converted["steps"] = []
        for step in pipeline.get("steps") or []:
            converted_step = dict(step)
            if "default_args" in converted_step:
                converted_step["defaultArgs"] = converted_step.pop("default_args")
            if "required_load_packages" in converted_step:
                converted_step["requiredLoadPackages"] = converted_step.pop("required_load_packages")
            if "optional_load_packages" in converted_step:
                converted_step["optionalLoadPackages"] = converted_step.pop("optional_load_packages")
            converted["steps"].append(converted_step)
        out.append(converted)
    return out


def _camelize_shortcuts(shortcuts: list[dict]) -> list[dict]:
    out = []
    for shortcut in shortcuts:
        converted = dict(shortcut)
        if "entry_pipeline" in converted:
            converted["entryPipeline"] = converted.pop("entry_pipeline")
        if "requires_input" in converted:
            converted["requiresInput"] = converted.pop("requires_input")
        if "visible_when" in converted:
            converted["visibleWhen"] = converted.pop("visible_when")
        out.append(converted)
    return out
```

- [ ] **Step 4: Run desk tests**

Run:

```powershell
cd python
python -m unittest tests.test_desk_server -v
cd ..
```

Expected: tests pass.

- [ ] **Step 5: Commit**

```powershell
git add python/src/desk_server/capabilities.py python/tests/test_desk_server.py
git commit -m "feat: expose capability pipelines in desk catalog"
```

---

### Task 7: Frontend Types And Capability UI

**Files:**
- Modify: `web/src/chat/chat-api.ts`
- Modify: `web/src/advanced/pages/CapabilitiesPage.tsx`
- Test: `web/src/advanced/capabilitiesPage.test.mjs`

- [ ] **Step 1: Write failing source-contract tests**

In `web/src/advanced/capabilitiesPage.test.mjs`, assert the page references pipeline, stage, and shortcut candidate fields:

```javascript
import fs from 'node:fs';
import assert from 'node:assert/strict';

const source = fs.readFileSync(new URL('./pages/CapabilitiesPage.tsx', import.meta.url), 'utf8');
const api = fs.readFileSync(new URL('../chat/chat-api.ts', import.meta.url), 'utf8');

assert.match(api, /pipelines\??:/);
assert.match(api, /stages\??:/);
assert.match(api, /shortcuts\??:/);
assert.match(source, /pipelines/);
assert.match(source, /stages/);
assert.match(source, /defaultArgs/);
assert.match(source, /shortcuts/);
```

- [ ] **Step 2: Run frontend contract test to verify failure**

Run:

```powershell
cd web
node src/advanced/capabilitiesPage.test.mjs
cd ..
```

Expected: failure if types/UI do not reference pipeline fields.

- [ ] **Step 3: Add TypeScript types**

In `web/src/chat/chat-api.ts`, add:

```ts
export type CapabilityPipelineStep = {
  id?: string
  stage: 'reader' | 'material_index' | 'planner' | 'writer'
  tool?: string
  tools?: string[]
  kind?: string
  defaultArgs?: Record<string, unknown>
  inputs?: string[]
  outputs?: string[]
  requiredLoadPackages?: string[]
  optionalLoadPackages?: string[]
  ready?: boolean
  statusReason?: string
}

export type CapabilityPipeline = {
  id: string
  title?: string
  primary?: boolean
  stages?: string[]
  inputs?: string[]
  ready?: boolean
  statusReason?: string
  steps: CapabilityPipelineStep[]
}

export type CapabilityShortcut = {
  id: string
  surface: 'chat_quick_action' | 'wizard' | 'settings_action' | 'context_menu'
  label: string
  entryPipeline: string
  requiresInput?: string[]
  visibleWhen?: string
}
```

Add `stages?: string[]`, `pipelines?: CapabilityPipeline[]`, and `shortcuts?: CapabilityShortcut[]` to the product capability type.

- [ ] **Step 4: Render compact pipeline summaries**

In `CapabilitiesPage.tsx`, add a compact row under each capability:

```tsx
function PipelineSummary({ pipelines }: { pipelines?: CapabilityPipeline[] }) {
  if (!pipelines?.length) return null
  return (
    <div className="capability-pipelines">
      {pipelines.slice(0, 2).map((pipeline) => (
        <div key={pipeline.id} className="capability-pipeline">
          <span>{pipeline.title || pipeline.id}</span>
          <span>{pipeline.steps.map((step) => step.stage).join(' -> ')}</span>
        </div>
      ))}
    </div>
  )
}
```

Use existing local styling conventions; keep it compact and scannable.

Also add a compact shortcut-candidate row. This row is informational only; do not wire button behavior in this plan:

```tsx
function ShortcutSummary({ shortcuts }: { shortcuts?: CapabilityShortcut[] }) {
  if (!shortcuts?.length) return null
  return (
    <div className="capability-shortcuts">
      {shortcuts.map((shortcut) => (
        <span key={shortcut.id} className="capability-shortcut">
          {shortcut.label}
        </span>
      ))}
    </div>
  )
}
```

- [ ] **Step 5: Run frontend test**

Run:

```powershell
cd web
node src/advanced/capabilitiesPage.test.mjs
cd ..
```

Expected: test passes.

- [ ] **Step 6: Commit**

```powershell
git add web/src/chat/chat-api.ts web/src/advanced/pages/CapabilitiesPage.tsx web/src/advanced/capabilitiesPage.test.mjs
git commit -m "feat: show capability pipelines and shortcut candidates"
```

---

### Task 8: Verification

**Files:**
- No new files.

- [ ] **Step 1: Run Python capability/load package tests**

Run:

```powershell
$env:PYTHONPATH='D:\project\Kabuqina\python\src;D:\project\Kabuqina\hermes_core'
python -m unittest tests.test_capability_registry tests.test_load_packages tests.test_docling_math_models -v
```

Expected: all tests pass.

- [ ] **Step 2: Run Hermes document tests**

Run:

```powershell
$env:PYTHONPATH='D:\project\Kabuqina\python\src;D:\project\Kabuqina\hermes_core'
python -m pytest hermes_core/tests/tools/test_document_tools.py hermes_core/tests/tools/test_material_index_tools.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run frontend source-contract tests**

Run:

```powershell
cd web
node src/advanced/capabilitiesPage.test.mjs
node src/advanced/settingsLoadPackages.test.mjs
cd ..
```

Expected: all tests pass.

- [ ] **Step 4: Review catalog payload manually**

Run the desk server tests or inspect a local catalog response. Confirm `document-math` includes:

```json
{
  "id": "document-math",
  "stages": ["reader"],
  "pipelines": [
    {
      "id": "docling-math-document-read",
      "steps": [
        {
          "tool": "document_read_precise",
          "defaultArgs": { "mode": "math" },
          "outputs": ["read_id", "markdown", "formulas"]
        }
      ]
    }
  ]
}
```

- [ ] **Step 5: Commit verification fixes if needed**

If verification required small fixes:

```powershell
git add <changed-files>
git commit -m "test: verify capability pipeline integration"
```

If no fixes were required, do not create an empty commit.
