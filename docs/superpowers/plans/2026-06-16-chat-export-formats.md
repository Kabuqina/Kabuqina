# Chat Export Formats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add TXT export and real PDF export generated from an internal HTML print source.

**Architecture:** Keep dialogue normalization and document builders in `web/src/chat/chatExport.ts`. Wire format selection in `web/src/advanced/Export.tsx`. Add a Rust-side PDF export command boundary in `tauri/src/paths.rs` so file validation remains host-owned.

**Tech Stack:** React/Vite/TypeScript, Node test scripts, Tauri 2 Rust commands, Windows WebView2 print-to-PDF where available.

---

### Task 1: Web Export Builders

**Files:**
- Modify: `web/src/chat/chatExport.ts`
- Modify: `web/src/chat/chatExport.test.mjs`

- [ ] **Step 1: Write failing tests**

Add assertions that import `buildExportText`, `buildExportHtml`, and expanded `defaultExportFilename`. Tests should verify:

```js
assert.match(txt, /卡布奇娜 · 聊天记录/);
assert.match(txt, /用户 · /);
assert.match(txt, /卡布奇娜 · /);
assert.doesNotMatch(txt, /<script>/);

assert.match(html, /<!doctype html>/i);
assert.match(html, /@media print/);
assert.match(html, /page-break-after/);
assert.match(html, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
assert.doesNotMatch(html, /<script>alert/);

assert.equal(defaultExportFilename("text"), "kabuqina-chat-export.txt");
assert.equal(defaultExportFilename("pdf"), "kabuqina-chat-export.pdf");
```

- [ ] **Step 2: Run failing test**

Run: `cd web; node src/chat/chatExport.test.mjs`

Expected: FAIL because `buildExportText` / `buildExportHtml` do not exist and filename format does not include `text` / `pdf`.

- [ ] **Step 3: Implement minimal builders**

In `chatExport.ts`:

```ts
export type ExportFormat = "json" | "markdown" | "text" | "pdf";
```

Add `buildExportText(...)` by reusing `rowsToExportDialogue(...)` and plain line joins. Add `buildExportHtml(...)` with local HTML escaping and print CSS. Use the same title/model/turn metadata as Markdown.

- [ ] **Step 4: Run passing test**

Run: `cd web; node src/chat/chatExport.test.mjs`

Expected: PASS.

### Task 2: Export Page Wiring

**Files:**
- Modify: `web/src/advanced/Export.tsx`
- Modify: `web/src/chat/chatUx.test.mjs`

- [ ] **Step 1: Write failing tests**

Extend `chatUx.test.mjs` checks so `Export.tsx` must import/use `buildExportText`, `buildExportHtml`, and contain `"text"` and `"pdf"` in the format list.

- [ ] **Step 2: Run failing test**

Run: `cd web; node src/chat/chatUx.test.mjs`

Expected: FAIL because the export page only exposes JSON and Markdown.

- [ ] **Step 3: Implement UI wiring**

Update `ExportFormat` usage to come from `chatExport.ts`. Add format labels for JSON, Markdown, TXT, and PDF. For JSON/Markdown/TXT, keep `cmd_write_text_file`. For PDF, build HTML and call:

```ts
await invoke("cmd_write_pdf_from_html", {
  pathStr: filePath,
  html: content,
});
```

- [ ] **Step 4: Run passing test**

Run: `cd web; node src/chat/chatUx.test.mjs`

Expected: PASS.

### Task 3: Rust Export Path Validation and PDF Command Boundary

**Files:**
- Modify: `tauri/src/paths.rs`
- Modify: `tauri/src/lib.rs`
- Modify: `tauri/Cargo.toml` only if compilation requires direct `webview2-com` access.

- [ ] **Step 1: Write failing Rust tests**

Add unit tests proving:

```rust
assert!(validate_text_export_path(&desktop.join("chat.pdf")).is_err());
assert!(validate_pdf_export_path(&desktop.join("chat.pdf")).is_ok());
assert!(validate_pdf_export_path(&desktop.join("chat.txt")).is_err());
```

- [ ] **Step 2: Run failing Rust test**

Run: `cd tauri; cargo test paths::tests::pdf_export_path_validation --lib`

Expected: FAIL because `validate_pdf_export_path` does not exist.

- [ ] **Step 3: Implement validation and command**

Add:

```rust
#[tauri::command]
pub async fn cmd_write_pdf_from_html(
    app: tauri::AppHandle,
    path_str: String,
    html: String,
) -> Result<(), String>
```

The command validates `.pdf` output with the existing root policy, rejects empty HTML, and calls a Windows-only helper. On unsupported platforms, return a clear error.

- [ ] **Step 4: Register the command**

Add `paths::cmd_write_pdf_from_html` to `tauri::generate_handler!` in `tauri/src/lib.rs`.

- [ ] **Step 5: Run passing Rust test**

Run: `cd tauri; cargo test paths::tests::pdf_export_path_validation --lib`

Expected: PASS.

### Task 4: Verification

**Files:**
- Verify all touched files.

- [ ] **Step 1: Run focused web tests**

Run:

```powershell
cd web
node src/chat/chatExport.test.mjs
node src/chat/chatUx.test.mjs
```

Expected: both commands exit 0.

- [ ] **Step 2: Run TypeScript build**

Run: `cd web; npm run build`

Expected: exit 0.

- [ ] **Step 3: Run Rust focused tests**

Run: `cd tauri; cargo test paths::tests --lib`

Expected: exit 0 for path tests.

- [ ] **Step 4: Inspect git diff**

Run: `git diff -- web/src/chat/chatExport.ts web/src/chat/chatExport.test.mjs web/src/advanced/Export.tsx web/src/chat/chatUx.test.mjs tauri/src/paths.rs tauri/src/lib.rs tauri/Cargo.toml`

Expected: only export-format and PDF-command changes.
