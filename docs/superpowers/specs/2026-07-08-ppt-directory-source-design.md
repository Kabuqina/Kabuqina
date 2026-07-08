# PPT Directory Source Design

## Goal

The REPORT launchpad actions "Code project -> PPT" and "Sandtable review -> PPT" should ask the user to choose a folder before creating the PPT prompt, because both workflows operate on a directory of materials rather than a single pasted document.

## Current Behavior

`web/src/chat/WorkspacePanel.tsx` renders four PPT actions. All four currently call `setPptModal({ base })` directly, then `PptIntentModal` collects goal/emphasis and appends the shared PPT flow and visual-master rules.

`web/src/chat/ChatInput.tsx` already uses `@tauri-apps/plugin-dialog` with `open({ directory: true })` to let users choose folders. The same Tauri dialog API can be reused in `WorkspacePanel`.

## Design

Only these two REPORT actions get the folder-pick step:

- `workspaceCodeToPpt`
- `workspaceSandtableToPpt`

When clicked, `WorkspacePanel` opens the native folder picker. If the user cancels, no modal opens and no prompt is inserted. If the user selects a folder, `WorkspacePanel` opens the existing `PptIntentModal` with a base prompt that includes:

- the original workflow instruction,
- `材料目录：<selected path>`,
- a rule telling the agent to treat that folder as the material root and recursively read all relevant files before building the material index.

The paper and course PPT actions remain unchanged because they commonly start from uploaded files, pasted content, or single documents.

## Error Behavior

If the folder picker is unavailable outside the desktop app, show the existing localized desktop-only message in the REPORT section. If the picker throws, show the existing localized file-picker failure message.

## Files

- `web/src/chat/WorkspacePanel.tsx`: import `isTauri` and dialog `open`, add the folder-pick helper, route the two actions through it, and render a small error line.
- `web/src/locales/strings.ts`: add a specific folder-picker dialog title for PPT materials.
- `web/src/chat/chatUx.test.mjs`: update source-level regression checks for the new folder-pick flow.

## Testing

Run `npm run test:chat-ux` and `npm run build` from `web/`.
