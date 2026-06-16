# Chat Export Formats Design

Date: 2026-06-16

## Goal

Expand the chat export page from JSON and Markdown to include:

- TXT for broadly compatible plain-text archives.
- PDF as a real `.pdf` file generated from an internal HTML print source.

DOCX is intentionally out of scope for this pass. It would need a separate document writer path or a new front-end dependency, while the requested near-term value is covered by TXT and PDF.

## Current Context

The export surface is in `web/src/advanced/Export.tsx`. It fetches selected sessions and messages, builds a text payload through `web/src/chat/chatExport.ts`, asks the user for a save path, and writes via the Tauri command `cmd_write_text_file`.

The Rust path validator in `tauri/src/paths.rs` already allows `.txt`, but the UI and builders do not expose TXT yet. It does not allow `.html` or `.pdf`.

## Recommended Approach

Keep export content assembly in the web shell and add two builders:

- `buildExportText(...)`: plain text with session headings, metadata, speaker labels, timestamps, and attachment names.
- `buildExportHtml(...)`: a self-contained print-oriented HTML document with escaped content, readable typography, page breaks between sessions, and the same dialogue normalization rules as JSON/Markdown.

For PDF, add a Tauri command such as `cmd_write_pdf_from_html(pathStr, html)`. On Windows it should render the HTML into a hidden WebView2/WebView-backed surface and call the platform print-to-PDF capability so the saved result is a real PDF file. The HTML remains an internal source, not a user-visible export format in this pass.

## UI

Extend the export format radio group to:

- JSON
- Markdown
- TXT
- PDF

The default can remain JSON to avoid changing existing behavior. The save dialog should use the matching extension and filter for each format. PDF should save as `kabuqina-chat-export.pdf`.

## File Safety

Keep the existing export-root restriction: Desktop, Documents, or Downloads only. Extend validation carefully:

- Text export command allows only text-like extensions: `.json`, `.md`, `.markdown`, `.txt`.
- PDF export command allows only `.pdf`.
- PDF command should not accept arbitrary filesystem reads, scripts, or URLs. It receives an HTML string from the front-end and writes only to the validated save path.

## Error Handling

If PDF generation fails, the export page should log the error and stop the busy state. A later UI improvement can add a visible toast or inline error, but this pass should not add a new notification system.

If WebView2 print-to-PDF is unavailable in a dev environment, the Rust command should return a clear error string rather than silently writing HTML with a `.pdf` extension.

## Tests

Use test-first changes:

- `web/src/chat/chatExport.test.mjs`
  - TXT includes normalized dialogue, speaker labels, timestamps, and no Hermes branding.
  - HTML escapes user/assistant content and contains print/page-break styling.
  - Default filenames include `.txt` and `.pdf`.
- `web/src/chat/chatUx.test.mjs`
  - Export page imports and uses TXT/HTML/PDF helpers.
  - Format list includes PDF and TXT.
- Rust unit tests in `tauri/src/paths.rs`
  - Text export validation still rejects `.pdf`.
  - PDF export validation accepts `.pdf` in allowed roots and rejects script/text extensions for the PDF command.

Manual verification after implementation:

- Run the focused web export tests.
- Run relevant Rust tests for path validation.
- Run `npm run build` in `web/`.
- In dev app, export a small session as TXT and PDF and open both files.

## Non-Goals

- No DOCX export in this pass.
- No direct HTML export option in this pass.
- No changes to Hermes core or Python policy layers.
- No Chromium/Playwright bundle for PDF generation unless WebView2 print-to-PDF proves unavailable.
