# Desktop Organize Confirmation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second-confirmation dialog before the desktop organize button triggers file/icon changes.

**Architecture:** Reuse the existing global `ConfirmDialogHost` and `confirm()` promise helper. Gate `ChatPage.handleOrganizeDesktop` before transcript updates and before `runDesktopOrganize(locale)`.

**Tech Stack:** React 19, TypeScript, Tauri invoke bridge, existing source-level Node UX tests.

---

### Task 1: Add Confirmation Gate

**Files:**
- Modify: `web/src/chat/chatUx.test.mjs`
- Modify: `web/src/chat/ChatPage.tsx`
- Modify: `web/src/locales/strings.ts`

- [ ] **Step 1: Write the failing test**

In `web/src/chat/chatUx.test.mjs`, replace the old "should not open a modal confirmation flow" assertion with checks that `handleOrganizeDesktop` calls `confirm()` before it appends chat messages and before `runDesktopOrganize(locale)`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web; npm run test:chat-ux`

Expected before implementation: the test fails because `handleOrganizeDesktop` does not reference `desktopOrganizer.confirmTitle` and does not await `confirm()`.

- [ ] **Step 3: Write minimal implementation**

In `web/src/chat/ChatPage.tsx`, add:

```ts
const ok = await confirm({
  title: t("desktopOrganizer.confirmTitle"),
  message: t("desktopOrganizer.confirmBody"),
  confirmLabel: t("desktopOrganizer.confirmApply"),
  cancelLabel: t("desktopOrganizer.confirmCancel"),
  tone: "warning",
});
if (!ok) return;
```

Place it at the top of `handleOrganizeDesktop`, before `const now = Date.now()`.

In `web/src/locales/strings.ts`, add the four zh/en `desktopOrganizer` keys used above.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web; npm run test:chat-ux`

Expected after implementation: the chat UX test exits 0.

- [ ] **Step 5: Run build verification**

Run: `cd web; npm run build`

Expected: TypeScript and Vite build exit 0.
