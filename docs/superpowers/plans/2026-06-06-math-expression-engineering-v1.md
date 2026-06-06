# Math Expression Engineering V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the three D-class math-expression-engineering capabilities from candidate metadata to real V1 product capabilities.

**Architecture:** Add deterministic V1 math expression tools in `hermes_core/tools/math_expression_tools.py`, register them in a dedicated `math` toolset, and update Kabuqina capability metadata to point at real tool-backed pipelines. V1 intentionally avoids new load packages and avoids CAS/proof claims.

**Tech Stack:** Python stdlib (`ast`, `html`, `json`, `re`, `tempfile`, `pathlib`), Hermes tool registry, Kabuqina capability registry/status tests, focused web source checks.

---

### Task 1: Add Math Expression Tool Tests

**Files:**
- Create: `hermes_core/tests/tools/test_math_expression_tools.py`

- [ ] **Step 1: Write failing tests**

Create tests for:

```python
def test_cleanup_normalizes_ocr_and_reports_variables():
    from tools.math_expression_tools import math_expression_cleanup
    result = json.loads(math_expression_cleanup("E = m c ^ 2"))
    assert result["ok"] is True
    assert result["clean_latex"] == "E = m c^{2}"
    assert any(row["name"] == "E" for row in result["variable_table"])
```

```python
def test_formula_to_code_supports_python_numpy_cpp17():
    from tools.math_expression_tools import math_formula_to_code
    py = json.loads(math_formula_to_code("E = mc^2", "python"))
    npy = json.loads(math_formula_to_code("E = mc^2", "numpy"))
    cpp = json.loads(math_formula_to_code("E = mc^2", "cpp17"))
    assert "def compute_energy" in py["code"]
    assert "np.asarray" in npy["code"]
    assert "#include <cmath>" in cpp["code"]
    assert "std::pow" in cpp["code"]
```

```python
def test_code_to_math_formula_writes_html_and_pdf_warning(tmp_path):
    from tools.math_expression_tools import code_to_math_formula
    result = json.loads(code_to_math_formula("def energy(m, c):\n    return m * c ** 2", "python", str(tmp_path)))
    assert result["ok"] is True
    assert "E = m c^{2}" in result["latex"]
    assert Path(result["html_path"]).exists()
    assert result["pdf_path"] == ""
    assert any("PDF" in warning for warning in result["warnings"])
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest hermes_core/tests/tools/test_math_expression_tools.py -q
```

Expected: FAIL because `tools.math_expression_tools` does not exist.

### Task 2: Implement V1 Tools

**Files:**
- Create: `hermes_core/tools/math_expression_tools.py`
- Modify: `hermes_core/toolsets.py`

- [ ] **Step 1: Implement deterministic V1 functions**

Implement:

- `math_expression_cleanup(expression, source_kind="auto")`
- `math_formula_to_code(formula, language="python")`
- `code_to_math_formula(code, language="auto", output_dir="")`

Each handler returns a JSON string and registers with `registry.register()` under toolset `math`.

- [ ] **Step 2: Add `math` toolset**

Add toolset:

```python
"math": {
    "description": "Math expression engineering: formula cleanup, formula-to-code, and code-to-formula reports",
    "tools": ["math_expression_cleanup", "math_formula_to_code", "code_to_math_formula"],
    "includes": [],
}
```

- [ ] **Step 3: Run tool tests and verify GREEN**

Run:

```powershell
python -m pytest hermes_core/tests/tools/test_math_expression_tools.py -q
```

Expected: PASS.

### Task 3: Upgrade Capability Registry

**Files:**
- Modify: `python/tests/test_capability_registry.py`
- Modify: `python/src/capability_registry.py`
- Modify: `python/src/capability_status.py`
- Modify: `python/src/capability_prompt.py`

- [ ] **Step 1: Write failing tests**

Update tests so the three math capabilities:

- have no `lifecycle=candidate`
- require toolset `math`
- reference real tools
- become `available` when `enabled_toolsets={"math"}`
- appear in the agent prompt with ready pipelines

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
cd python; python -m unittest tests.test_capability_registry -v; cd ..
```

Expected: FAIL because registry still marks them as candidate.

- [ ] **Step 3: Implement registry/status/prompt upgrade**

Remove candidate short-circuit for these capabilities by removing `lifecycle="candidate"` from their definitions. Replace candidate step kinds with real tools:

- `math_expression_cleanup`
- `math_formula_to_code`
- `code_to_math_formula`

Keep PDF as same-HTML export with warning when no backend is present.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```powershell
cd python; python -m unittest tests.test_capability_registry tests.test_desk_server -v; cd ..
```

Expected: PASS.

### Task 4: Frontend Source Checks

**Files:**
- Modify: `web/src/advanced/capabilitiesPage.test.mjs`

- [ ] **Step 1: Keep candidate display support**

Do not remove candidate UI support; future roadmap entries may still use it.

- [ ] **Step 2: Verify source checks and build**

Run:

```powershell
node web\src\advanced\capabilitiesPage.test.mjs
cd web; npm run build; cd ..
```

Expected: PASS. Vite may still warn about large chunks.

### Task 5: Focused End-to-End Verification

**Files:**
- Read-only verification of touched files.

- [ ] **Step 1: Run full focused test set**

```powershell
python -m pytest hermes_core/tests/tools/test_math_expression_tools.py hermes_core/tests/tools/test_registry.py -q
cd python; python -m unittest tests.test_capability_registry tests.test_desk_server -v; cd ..
node web\src\advanced\capabilitiesPage.test.mjs
cd web; npm run build; cd ..
```

- [ ] **Step 2: Confirm no new load package dependency**

```powershell
rg -n "math-expression-cleanup|math-formula-to-code|code-to-math-formula|math_expression_cleanup|math_formula_to_code|code_to_math_formula|docling-codeformula|candidate" python\src hermes_core\tools hermes_core\toolsets.py python\tests hermes_core\tests\tools
```

Expected: D-class capabilities use the `math` toolset and do not require any new load package.
