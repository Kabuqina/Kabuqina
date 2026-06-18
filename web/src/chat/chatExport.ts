// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { Locale } from "../lib/i18n-core";
import type { MessageRow, SessionRow } from "./chat-api";
import { parseDeskUserContent } from "./deskUserContent";

export type ExportDialogueTurn = {
  role: "user" | "assistant";
  speaker: string;
  text: string;
  attachments?: { name: string; mime: string }[];
  timestamp?: number;
};

export type ExportLabels = {
  productName: string;
  userLabel: string;
  documentTitle: string;
};

export type ExportFormat = "json" | "markdown" | "text" | "pdf";

export function exportLabelsForLocale(locale: Locale): ExportLabels {
  if (locale === "en") {
    return {
      productName: "Kabuqina",
      userLabel: "You",
      documentTitle: "Kabuqina · Chat history",
    };
  }
  return {
    productName: "卡布奇娜",
    userLabel: "用户",
    documentTitle: "卡布奇娜 · 聊天记录",
  };
}

function contentToString(content: unknown): string {
  if (content == null) {
    return "";
  }
  if (typeof content === "string") {
    return content;
  }
  if (Array.isArray(content)) {
    return content
      .map((c) => {
        if (typeof c === "string") {
          return c;
        }
        if (c && typeof c === "object" && "text" in c) {
          return String((c as { text?: unknown }).text ?? "");
        }
        return "";
      })
      .filter(Boolean)
      .join("\n");
  }
  if (typeof content === "object" && "text" in (content as object)) {
    return String((content as { text?: unknown }).text);
  }
  try {
    return JSON.stringify(content);
  } catch {
    return String(content);
  }
}

function tsToLocale(ts?: number, locale: Locale = "zh"): string {
  if (ts == null) {
    return "";
  }
  const ms = ts > 1e12 ? ts : ts * 1000;
  return new Date(ms).toLocaleString(locale === "en" ? "en-US" : "zh-CN");
}

/** Normalize DB rows into user ↔ main-agent dialogue (same rules as chat history UI). */
export function rowsToExportDialogue(rows: MessageRow[], labels: ExportLabels): ExportDialogueTurn[] {
  const out: ExportDialogueTurn[] = [];
  for (const m of rows) {
    const role = m.role;
    if (role === "session_meta" || role === "tool" || role === "system") {
      continue;
    }
    if (role !== "user" && role !== "assistant") {
      continue;
    }

    if (role === "user") {
      const parsed = parseDeskUserContent(m.content);
      if (!parsed.text && !parsed.attachments?.length) {
        continue;
      }
      const attachmentLines =
        parsed.attachments?.map((att) => `📎 ${att.name}`).join("\n") ?? "";
      const text = [parsed.text, attachmentLines].filter(Boolean).join("\n");
      out.push({
        role: "user",
        speaker: labels.userLabel,
        text,
        attachments: parsed.attachments?.map(({ name, mime }) => ({ name, mime })),
        timestamp: m.timestamp,
      });
      continue;
    }

    const text = contentToString(m.content).trim();
    if (!text) {
      continue;
    }
    out.push({
      role: "assistant",
      speaker: labels.productName,
      text,
      timestamp: m.timestamp,
    });
  }
  return out;
}

function sessionToMarkdown(
  session: SessionRow,
  dialogue: ExportDialogueTurn[],
  labels: ExportLabels,
  locale: Locale,
): string {
  const title = session.title?.trim() || session.preview?.trim() || session.id.slice(0, 8);
  const lines: string[] = [];
  lines.push(`# ${labels.documentTitle}`);
  lines.push("");
  lines.push(`## ${title}`);
  lines.push("");
  lines.push(
    `> **Session:** \`${session.id}\`  ` +
      `| **Model:** ${session.model || "—"}  ` +
      `| **Turns:** ${dialogue.length}`,
  );
  lines.push("");

  for (const turn of dialogue) {
    const timeLabel = tsToLocale(turn.timestamp, locale);
    const tsStr = timeLabel ? ` · ${timeLabel}` : "";
    const icon = turn.role === "user" ? "👤" : "🤖";
    lines.push(`### ${icon} ${turn.speaker}${tsStr}`);
    lines.push("");
    lines.push(turn.text);
    lines.push("");
  }

  lines.push("---");
  lines.push("");
  return lines.join("\n");
}

function sessionTitle(session: SessionRow): string {
  return session.title?.trim() || session.preview?.trim() || session.id.slice(0, 8);
}

function sessionToText(
  session: SessionRow,
  dialogue: ExportDialogueTurn[],
  labels: ExportLabels,
  locale: Locale,
): string {
  const title = sessionTitle(session);
  const lines: string[] = [];
  lines.push(labels.documentTitle);
  lines.push("=".repeat(labels.documentTitle.length));
  lines.push("");
  lines.push(title);
  lines.push("-".repeat(title.length));
  lines.push("");
  lines.push(`Session: ${session.id}`);
  lines.push(`Model: ${session.model || "-"}`);
  lines.push(`Turns: ${dialogue.length}`);
  lines.push("");

  for (const turn of dialogue) {
    const timeLabel = tsToLocale(turn.timestamp, locale);
    const tsStr = timeLabel ? ` · ${timeLabel}` : "";
    lines.push(`${turn.speaker}${tsStr}`);
    lines.push("-".repeat(`${turn.speaker}${tsStr}`.length));
    lines.push(turn.text);
    lines.push("");
  }

  return lines.join("\n");
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * Renders an assistant turn's Markdown (headings, tables, code, LaTeX) to HTML.
 * Supplied at runtime from the browser bundle; when absent (e.g. the Node test),
 * callers fall back to escaped pre-wrapped text.
 */
export type ExportMarkdownRenderer = (text: string) => string;

type MetaLabels = { session: string; model: string; turns: string };

function metaLabelsForLocale(locale: Locale): MetaLabels {
  if (locale === "en") {
    return { session: "Session", model: "Model", turns: "Turns" };
  }
  return { session: "会话", model: "模型", turns: "对话轮次" };
}

function sessionToHtml(
  session: SessionRow,
  dialogue: ExportDialogueTurn[],
  locale: Locale,
  renderMarkdown?: ExportMarkdownRenderer,
): string {
  const title = sessionTitle(session);
  const ml = metaLabelsForLocale(locale);
  const turns = dialogue
    .map((turn) => {
      const timeLabel = tsToLocale(turn.timestamp, locale);
      const roleClass = turn.role === "user" ? "turn-user" : "turn-assistant";
      const whenHtml = timeLabel
        ? `<span class="when">${escapeHtml(timeLabel)}</span>`
        : "";
      // User turns stay verbatim (they hold raw paths/snippets that must not be
      // reinterpreted as Markdown); assistant turns get full Markdown rendering.
      const textBlock =
        turn.role === "assistant" && renderMarkdown
          ? `<div class="turn-text md">${renderMarkdown(turn.text)}</div>`
          : `<div class="turn-text">${escapeHtml(turn.text)}</div>`;
      return [
        `<article class="turn ${roleClass}">`,
        `<h3><span class="who">${escapeHtml(turn.speaker)}</span>${whenHtml}</h3>`,
        textBlock,
        `</article>`,
      ].join("\n");
    })
    .join("\n");

  const metaItem = (label: string, value: string) =>
    `<span class="meta-item"><span class="meta-key">${escapeHtml(label)}</span>${value}</span>`;
  return [
    `<section class="session">`,
    `<h2>${escapeHtml(title)}</h2>`,
    `<p class="session-meta">`,
    metaItem(ml.session, `<code>${escapeHtml(session.id)}</code>`),
    metaItem(ml.model, escapeHtml(session.model || "—")),
    metaItem(ml.turns, String(dialogue.length)),
    `</p>`,
    turns,
    `</section>`,
  ].join("\n");
}

export function buildExportMarkdown(
  sessions: SessionRow[],
  messagesBySession: Map<string, MessageRow[]>,
  labels: ExportLabels,
  locale: Locale,
): string {
  const parts: string[] = [];
  for (const session of sessions) {
    const rows = messagesBySession.get(session.id) ?? [];
    const dialogue = rowsToExportDialogue(rows, labels);
    if (dialogue.length === 0) {
      continue;
    }
    parts.push(sessionToMarkdown(session, dialogue, labels, locale));
  }
  return parts.join("\n\n<div style=\"page-break-after: always;\"></div>\n\n");
}

export function buildExportText(
  sessions: SessionRow[],
  messagesBySession: Map<string, MessageRow[]>,
  labels: ExportLabels,
  locale: Locale,
): string {
  const parts: string[] = [];
  for (const session of sessions) {
    const rows = messagesBySession.get(session.id) ?? [];
    const dialogue = rowsToExportDialogue(rows, labels);
    if (dialogue.length === 0) {
      continue;
    }
    parts.push(sessionToText(session, dialogue, labels, locale));
  }
  return parts.join("\n\n\f\n\n");
}

export type BuildExportHtmlOptions = {
  /** Renders assistant Markdown to HTML; omit to fall back to escaped text. */
  renderMarkdown?: ExportMarkdownRenderer;
  /** Extra CSS appended to the document (e.g. the syntax-highlight theme). */
  extraCss?: string;
};

export function buildExportHtml(
  sessions: SessionRow[],
  messagesBySession: Map<string, MessageRow[]>,
  labels: ExportLabels,
  locale: Locale,
  options: BuildExportHtmlOptions = {},
): string {
  const { renderMarkdown, extraCss } = options;
  const body = sessions
    .map((session) => {
      const rows = messagesBySession.get(session.id) ?? [];
      const dialogue = rowsToExportDialogue(rows, labels);
      return dialogue.length === 0
        ? ""
        : sessionToHtml(session, dialogue, locale, renderMarkdown);
    })
    .filter(Boolean)
    .join("\n");

  return `<!doctype html>
<html lang="${locale === "en" ? "en" : "zh-CN"}">
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(labels.documentTitle)}</title>
  <style>
    /* A4 with real page margins on every printed page (Chromium honors this via
       prefer_css_page_size); without it the content prints edge-to-edge. */
    @page { size: A4; margin: 18mm 16mm; }
    :root { color: #18181b; background: #ffffff; font-family: "Segoe UI", "Microsoft YaHei", sans-serif; }
    * { box-sizing: border-box; }
    body { margin: 0; padding: 32px; line-height: 1.6; }
    main { max-width: 820px; margin: 0 auto; }
    h1 { margin: 0 0 22px; padding-bottom: 12px; border-bottom: 2px solid #ede9fe; font-size: 26px; color: #4c1d95; }
    h2 { margin: 6px 0 10px; font-size: 20px; color: #18181b; }
    h3 { margin: 0 0 8px; font-size: 14px; color: #52525b; }
    code { font-family: Consolas, "Courier New", monospace; }
    .session { page-break-after: always; padding-bottom: 8px; }
    .session:last-child { page-break-after: auto; }
    .session-meta { display: flex; flex-wrap: wrap; gap: 6px 16px; margin: 0 0 8px; padding: 9px 14px;
      background: #faf8ff; border: 1px solid #ede9fe; border-radius: 8px; color: #52525b; font-size: 12px; }
    .session-meta .meta-key { color: #71717a; margin-right: 6px; }
    .session-meta code { color: #3f3f46; }
    .turn { padding: 14px 0 16px 16px; border-left: 3px solid transparent; }
    .turn + .turn { border-top: 1px solid #ececf0; }
    .turn-user { border-left-color: #a3e635; }
    .turn-assistant { border-left-color: #c4b5fd; }
    .turn > h3 { display: flex; align-items: baseline; gap: 8px; margin: 0 0 7px; font-size: 13px; font-weight: 600; break-after: avoid; }
    .turn > h3 .who { font-size: 14px; }
    .turn > h3 .when { font-weight: 400; font-size: 11px; color: #a1a1aa; }
    .turn-user > h3 .who { color: #4d7c0f; }
    .turn-assistant > h3 .who { color: #6d28d9; }
    .turn-text { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 14px; }
    /* Rendered Markdown (assistant turns). */
    .md { white-space: normal; overflow-wrap: anywhere; font-size: 14px; }
    .md > :first-child { margin-top: 0; }
    .md > :last-child { margin-bottom: 0; }
    .md h1, .md h2, .md h3, .md h4 { margin: 16px 0 8px; line-height: 1.3; color: #18181b; }
    .md h1 { font-size: 20px; }
    .md h2 { font-size: 17px; }
    .md h3 { font-size: 15px; color: #18181b; }
    .md h4 { font-size: 14px; }
    .md p { margin: 8px 0; }
    .md ul, .md ol { margin: 8px 0; padding-left: 24px; }
    .md li { margin: 3px 0; }
    .md a { color: #2563eb; text-decoration: underline; }
    .md hr { border: none; border-top: 1px solid #e4e4e7; margin: 18px 0; }
    .md blockquote { margin: 10px 0; padding: 2px 14px; border-left: 3px solid #c4b5fd; color: #52525b; }
    .md code { background: #f4f4f5; padding: 1px 5px; border-radius: 4px; font-size: 0.9em; }
    .md pre { background: #f6f8fa; border: 1px solid #e4e4e7; border-radius: 8px; padding: 12px 14px; overflow-x: auto; line-height: 1.45; margin: 12px 0; }
    .md pre code { background: none; padding: 0; font-size: 12.5px; }
    .md table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 13px; }
    .md th, .md td { border: 1px solid #d4d4d8; padding: 6px 10px; text-align: left; vertical-align: top; }
    .md th { background: #f4f4f5; font-weight: 600; }
    .md img { max-width: 100%; }
    .md .katex-display { display: block; margin: 12px 0; overflow-x: auto; text-align: center; }
    .md math { font-size: 1.05em; }
    @media print {
      body { padding: 0; }
      .session { page-break-after: always; }
      .md pre, .md table { break-inside: avoid; }
    }
  </style>
  <style>${extraCss ?? ""}</style>
</head>
<body>
  <main>
    <h1>${escapeHtml(labels.documentTitle)}</h1>
    ${body}
  </main>
</body>
</html>`;
}

export type ExportJsonPayload = {
  exported_at: string;
  app: string;
  locale: Locale;
  sessions: Array<{
    id: string;
    title: string;
    model: string;
    dialogue: ExportDialogueTurn[];
  }>;
};

export function buildExportJson(
  sessions: SessionRow[],
  messagesBySession: Map<string, MessageRow[]>,
  labels: ExportLabels,
  locale: Locale,
): string {
  const payload: ExportJsonPayload = {
    exported_at: new Date().toISOString(),
    app: labels.productName,
    locale,
    sessions: [],
  };

  for (const session of sessions) {
    const rows = messagesBySession.get(session.id) ?? [];
    const dialogue = rowsToExportDialogue(rows, labels);
    if (dialogue.length === 0) {
      continue;
    }
    payload.sessions.push({
      id: session.id,
      title: sessionTitle(session),
      model: session.model?.trim() || "",
      dialogue,
    });
  }

  return JSON.stringify(payload, null, 2);
}

export function defaultExportFilename(format: ExportFormat): string {
  if (format === "json") {
    return "kabuqina-chat-export.json";
  }
  if (format === "markdown") {
    return "kabuqina-chat-export.md";
  }
  if (format === "text") {
    return "kabuqina-chat-export.txt";
  }
  return "kabuqina-chat-export.pdf";
}
