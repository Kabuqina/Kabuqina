# Generate Report PPT Capability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the student PPT workflow into a real `generate-report-ppt` product capability with structure-template entrypoints and selectable visual masters.

**Architecture:** Keep the existing four-layer pipeline and `pptx_write` Writer as the executable V1 path. Add a stable `visual_master` contract to capability metadata, agent prompts, frontend quick actions, and the Writer schema/result so the current native renderer remains usable while the hybrid visual-master renderer can be swapped in later without changing the product interface.

**Tech Stack:** Python capability registry/status tests, Hermes core document tool schema, React WorkspacePanel prompt UI, existing PPT visual-master assets.

---

### Task 1: Capability Contract

**Files:**
- Modify: `python/src/capability_registry.py`
- Modify: `python/src/capability_status.py`
- Test: `python/tests/test_capability_registry.py`

- [ ] Add `family`, `structure_templates`, `visual_masters`, and three PPT pipeline entrypoints to the student PPT capability.
- [ ] Preserve backward-compatible fields so existing capability page rendering still works.
- [ ] Pass optional product metadata through `build_capability_status`.
- [ ] Test that `student-ppt` exposes three ready pipelines and all visual master ids.

### Task 2: Writer Interface

**Files:**
- Modify: `hermes_core/tools/document_tools.py`
- Modify: `hermes_core/tests/tools/test_document_tools.py`

- [ ] Add optional `visual_master` parameter to `pptx_write`.
- [ ] Include `visual_master` in the schema description and JSON result.
- [ ] Validate known ids by returning the selected id or `default_native`.
- [ ] Test that the parameter is accepted and returned.

### Task 3: Frontend Quick Action Prompt

**Files:**
- Modify: `web/src/chat/WorkspacePanel.tsx`
- Modify: `web/src/chat/chatUx.test.mjs`

- [ ] Add a compact visual-master selector in the PPT quick-action area.
- [ ] Include selected visual master id/name in all three PPT prompts.
- [ ] Tell the agent to call `pptx_write(..., visual_master="<id>")` after outline approval.
- [ ] Extend existing regex tests to cover visual master prompt text and ids.

### Task 4: Verification

**Commands:**
- `cd python; python -m unittest discover -s tests -p "test_capability_registry.py" -v`
- `python -m pytest hermes_core/tests/tools/test_document_tools.py`
- `cd web; npm run test -- --runInBand` or targeted Node tests if available

- [ ] Run Python capability tests.
- [ ] Run document tool tests.
- [ ] Run frontend chat/capability tests or explain any environment limitation.
