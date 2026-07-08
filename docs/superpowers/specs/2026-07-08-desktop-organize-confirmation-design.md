# Desktop Organize Confirmation Design

## Goal

When the user presses the chat sidebar's "Organize desktop" action, Kabuqina must ask for a second confirmation before any desktop organizing side effect starts.

## Current Behavior

`web/src/chat/ChatSidebar.tsx` calls `ChatPage.handleOrganizeDesktop`. That handler immediately appends a visible user/assistant pair to the chat transcript and calls `runDesktopOrganize(locale)`, which invokes `cmd_desktop_organize_run`.

The app already mounts `ConfirmDialogHost` in `web/src/main.tsx`, and `ChatPage` already imports the shared `confirm()` helper for session deletion. This is the right integration point.

## Design

`ChatPage.handleOrganizeDesktop` will call `confirm()` before it writes chat messages or invokes the Tauri command. The dialog uses the existing in-app confirmation host with warning tone. If the user cancels, the handler returns immediately with no transcript change and no desktop command.

The dialog copy should make the side effect plain: Kabuqina will organize top-level desktop files and align desktop icons after confirmation, while shortcuts, folders, hidden files, and system files remain skipped according to the existing Rust organizer rules.

## Files

- `web/src/chat/ChatPage.tsx`: gate `handleOrganizeDesktop` behind the shared confirm dialog.
- `web/src/locales/strings.ts`: add zh/en confirm title/body/confirm/cancel labels under `desktopOrganizer`.
- `web/src/chat/chatUx.test.mjs`: update source-level regression assertions so the desktop action must confirm before invoking `cmd_desktop_organize_run`.

## Testing

Run `npm run test:chat-ux` from `web/` and then `npm run build` from `web/`.
