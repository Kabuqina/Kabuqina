# Math Expression Engineering Capabilities Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register the D-class math-expression-engineering capabilities as candidate product capabilities without advertising them as executable.

**Architecture:** Reuse the existing first-party capability registry and status payload. Add candidate lifecycle support in `capability_status.py`, add three registry entries with non-executable roadmap pipelines, and teach the frontend status badge about `candidate`.

**Tech Stack:** Python unittest, existing Kabuqina capability registry/status modules, React/Vite TypeScript source, existing Node static source checks.

---

### Task 1: Backend Candidate Status Contract

**Files:**
- Modify: `python/tests/test_capability_registry.py`
- Modify: `python/src/capability_registry.py`
- Modify: `python/src/capability_status.py`
- Modify: `python/src/capability_prompt.py`

- [ ] **Step 1: Write the failing tests**

Add tests asserting:

```python
def test_math_expression_capabilities_are_registered_as_candidates(self):
    from capability_registry import get_capability_def, list_capability_defs

    ids = {item["id"] for item in list_capability_defs()}

    self.assertIn("math-expression-cleanup", ids)
    self.assertIn("math-formula-to-code", ids)
    self.assertIn("code-to-math-formula", ids)
    for capability_id in [
        "math-expression-cleanup",
        "math-formula-to-code",
        "code-to-math-formula",
    ]:
        capability = get_capability_def(capability_id)
        self.assertEqual(capability["family"], "math-expression-engineering")
        self.assertEqual(capability["lifecycle"], "candidate")
        self.assertTrue(capability["pipelines"])
```

```python
def test_candidate_capability_is_not_marked_available(self):
    from capability_registry import get_capability_def
    from capability_status import build_capability_status

    status = build_capability_status(
        get_capability_def("math-expression-cleanup"),
        load_packages={},
        enabled_toolsets={"documents", "file"},
    )

    self.assertEqual(status["status"], "candidate")
    self.assertFalse(status["pipelines"][0]["ready"])
    self.assertEqual(status["lifecycle"], "candidate")
```

```python
def test_agent_summary_warns_candidate_capabilities_are_not_executable(self):
    from capability_prompt import build_capability_prompt_summary

    summary = build_capability_prompt_summary([
        {
            "id": "math-expression-cleanup",
            "title": "Math expression cleanup",
            "status": "candidate",
            "agentHint": "Candidate only.",
            "requiredLoadPackages": [],
            "pipelines": [],
        }
    ])

    self.assertIn("Math expression cleanup: candidate", summary)
    self.assertIn("not yet executable", summary)
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
cd python; python -m unittest tests.test_capability_registry -v; cd ..
```

Expected: FAIL because the new capability IDs and candidate status support do not exist.

- [ ] **Step 3: Implement minimal backend support**

Add `candidate` to valid statuses, add `lifecycle` and `family` passthrough fields to status payloads, short-circuit candidate definitions/pipelines to `status="candidate"` and `ready=False`, and add the three math capability definitions from the spec.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```powershell
cd python; python -m unittest tests.test_capability_registry -v; cd ..
```

Expected: PASS.

### Task 2: Frontend Candidate Status Display

**Files:**
- Modify: `web/src/advanced/capabilitiesPage.test.mjs`
- Modify: `web/src/advanced/pages/CapabilitiesPage.tsx`
- Modify: `web/src/locales/strings.ts`

- [ ] **Step 1: Write the failing source checks**

Update `capabilitiesPage.test.mjs` to expect `candidate` in the product status union, Chinese strings, and English strings.

- [ ] **Step 2: Run source check and verify RED**

Run:

```powershell
node web\src\advanced\capabilitiesPage.test.mjs
```

Expected: FAIL because `candidate` is not yet typed or translated.

- [ ] **Step 3: Implement minimal frontend support**

Add `"candidate"` to `ProductStatus`, map it to a neutral or blue badge tone, and add Chinese/English labels.

- [ ] **Step 4: Run source check and verify GREEN**

Run:

```powershell
node web\src\advanced\capabilitiesPage.test.mjs
```

Expected: PASS.

### Task 3: Focused Verification

**Files:**
- Read-only verification of touched files.

- [ ] **Step 1: Run backend registry tests**

```powershell
cd python; python -m unittest tests.test_capability_registry -v; cd ..
```

- [ ] **Step 2: Run frontend source check**

```powershell
node web\src\advanced\capabilitiesPage.test.mjs
```

- [ ] **Step 3: Confirm no code claims the candidate capabilities are available**

```powershell
rg -n "math-expression-cleanup|math-formula-to-code|code-to-math-formula|candidate|not yet executable" python\src python\tests web\src docs\superpowers\specs docs\superpowers\plans
```

Expected: candidate capability definitions exist, tests cover them, and prompt/status wording prevents executable claims.
