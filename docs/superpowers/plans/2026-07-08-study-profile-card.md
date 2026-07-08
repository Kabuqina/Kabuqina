# Study Profile Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the STUDY learning context form into an edit modal and show a compact learning profile summary card above the learning actions.

**Architecture:** Keep persistence in `studyStore` unchanged. Update `StudySection` presentation only: derive summary rows from current `StudyContext`, render the summary card first, and open `ShellModal` for the existing full editor.

**Tech Stack:** React, TypeScript, Tailwind utility classes, lucide-react, existing source-level chat UX tests.

---

### Task 1: Lock Desired UI Shape With Tests

**Files:**
- Modify: `web/src/chat/chatUx.test.mjs`

- [ ] **Step 1: Write the failing test**

Add assertions that `StudySection` imports `ShellModal`, renders `kq-study-profile-card` before `STUDY_ACTIONS.map`, gates the full field list behind `profileEditorOpen`, and has zh/en locale strings for the new card labels.

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:chat-ux` from `web/`

Expected: FAIL because the current implementation still renders the 12-field form inline and has no learning profile card strings.

### Task 2: Implement Summary Card And Editor Modal

**Files:**
- Modify: `web/src/chat/study/StudySection.tsx`
- Modify: `web/src/locales/strings.ts`

- [ ] **Step 1: Add presentation state**

Add `profileEditorOpen` state to `StudySection` and import `ShellModal` plus an edit icon.

- [ ] **Step 2: Add summary rows**

Derive up to four rows from `course`, `goal`, `profileSummary`, and `currentStage`, trimming empty values. Use localized field labels already present in the component.

- [ ] **Step 3: Move full editor into modal**

Render the existing `fields.map` textarea editor inside `ShellModal`, preserving save, saved/failed status, and clear behavior.

- [ ] **Step 4: Add localized card strings**

Add zh/en strings for `studyContextCardTitle`, `studyContextEdit`, `studyContextEmpty`, and `studyContextClose`.

- [ ] **Step 5: Run test to verify it passes**

Run: `npm run test:chat-ux` from `web/`

Expected: PASS.

### Task 3: Verify Build

**Files:**
- Verify only.

- [ ] **Step 1: Run frontend build**

Run: `npm run build` from `web/`

Expected: PASS with TypeScript compile and Vite build success.

- [ ] **Step 2: Check whitespace**

Run: `git diff --check` from the repository root.

Expected: exit 0, allowing repository line-ending warnings if Git reports existing CRLF conversions.
