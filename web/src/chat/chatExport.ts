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

function sessionToHtml(
  session: SessionRow,
  dialogue: ExportDialogueTurn[],
  locale: Locale,
): string {
  const title = sessionTitle(session);
  const turns = dialogue
    .map((turn) => {
      const timeLabel = tsToLocale(turn.timestamp, locale);
      const meta = timeLabel ? `${turn.speaker} · ${timeLabel}` : turn.speaker;
      const roleClass = turn.role === "user" ? "turn-user" : "turn-assistant";
      return [
        `<article class="turn ${roleClass}">`,
        `<h3>${escapeHtml(meta)}</h3>`,
        `<div class="turn-text">${escapeHtml(turn.text)}</div>`,
        `</article>`,
      ].join("\n");
    })
    .join("\n");

  return [
    `<section class="session">`,
    `<h2>${escapeHtml(title)}</h2>`,
    `<p class="session-meta"><strong>Session:</strong> <code>${escapeHtml(session.id)}</code> <span>|</span> <strong>Model:</strong> ${escapeHtml(session.model || "-")} <span>|</span> <strong>Turns:</strong> ${dialogue.length}</p>`,
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

export function buildExportHtml(
  sessions: SessionRow[],
  messagesBySession: Map<string, MessageRow[]>,
  labels: ExportLabels,
  locale: Locale,
): string {
  const body = sessions
    .map((session) => {
      const rows = messagesBySession.get(session.id) ?? [];
      const dialogue = rowsToExportDialogue(rows, labels);
      return dialogue.length === 0 ? "" : sessionToHtml(session, dialogue, locale);
    })
    .filter(Boolean)
    .join("\n");

  return `<!doctype html>
<html lang="${locale === "en" ? "en" : "zh-CN"}">
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(labels.documentTitle)}</title>
  <style>
    :root { color: #18181b; background: #ffffff; font-family: "Segoe UI", "Microsoft YaHei", sans-serif; }
    body { margin: 0; padding: 32px; line-height: 1.55; }
    main { max-width: 820px; margin: 0 auto; }
    h1 { margin: 0 0 28px; font-size: 28px; }
    h2 { margin: 0 0 8px; font-size: 22px; }
    h3 { margin: 0 0 8px; font-size: 14px; color: #52525b; }
    code { font-family: Consolas, "Courier New", monospace; }
    .session { page-break-after: always; padding-bottom: 24px; }
    .session:last-child { page-break-after: auto; }
    .session-meta { margin: 0 0 18px; color: #52525b; font-size: 13px; }
    .turn { border-top: 1px solid #e4e4e7; padding: 16px 0; }
    .turn-text { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 14px; }
    .turn-user h3 { color: #365314; }
    .turn-assistant h3 { color: #4c1d95; }
    @media print {
      body { padding: 0; }
      .session { page-break-after: always; }
      .turn { break-inside: avoid; }
    }
  </style>
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
