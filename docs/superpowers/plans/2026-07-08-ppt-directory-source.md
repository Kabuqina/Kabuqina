# PPT Directory Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require folder selection before the code-project and sandtable PPT quick actions continue into the existing PPT generation settings flow.

**Architecture:** Reuse Tauri's existing dialog plugin from the web shell. Keep the existing PPT intent modal and prompt assembly path; only change the base prompt for the two directory-based workflows after a folder is chosen.

**Tech Stack:** React 19, TypeScript, `@tauri-apps/api/core`, `@tauri-apps/plugin-dialog`, existing Node source-level UX tests.

---

### Task 1: Directory Picker Flow

**Files:**
- Modify: `web/src/chat/chatUx.test.mjs`
- Modify: `web/src/chat/WorkspacePanel.tsx`
- Modify: `web/src/locales/strings.ts`

- [ ] **Step 1: Write the failing test**

Add source-level assertions in `web/src/chat/chatUx.test.mjs` that `WorkspacePanel` imports `open` from `@tauri-apps/plugin-dialog`, uses `open({ directory: true, multiple: false })`, includes `材料目录：${folderPath}` and `递归读取`, and routes `workspaceCodeToPpt` / `workspaceSandtableToPpt` through the folder helper while paper/course still open the existing PPT modal directly.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web; npm run test:chat-ux`

Expected before implementation: the test fails because `WorkspacePanel` does not import `open` and the two directory workflows still call `setPptModal({ base })` directly.

- [ ] **Step 3: Write minimal implementation**

In `WorkspacePanel.tsx`, import:

```ts
import { invoke, isTauri } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
```

Add a `pptFolderErr` state. Add a helper that opens the folder picker, returns on cancel, and otherwise calls:

```ts
setPptModal({
  base: buildPptPrompt([
    base,
    `材料目录：${folderPath}`,
    "请把这个目录作为本次任务的材料根目录，递归读取其中所有相关文件，先建立材料索引，再生成 PPT 大纲。",
  ]),
});
```

Route only `codeToPptBase` and `sandtableToPptBase` through that helper. Add `workspaceChoosePptMaterialFolder` to zh/en strings and render `pptFolderErr` under the report action list.

- [ ] **Step 4: Run focused verification**

Run: `cd web; npm run test:chat-ux`

Expected: the chat UX test exits 0.

- [ ] **Step 5: Run build verification**

Run: `cd web; npm run build`

Expected: TypeScript and Vite build exit 0.
