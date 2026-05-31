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
      title: session.title?.trim() || session.preview?.trim() || session.id.slice(0, 8),
      model: session.model?.trim() || "",
      dialogue,
    });
  }

  return JSON.stringify(payload, null, 2);
}

export function defaultExportFilename(format: "json" | "markdown"): string {
  return format === "json" ? "kabuqina-chat-export.json" : "kabuqina-chat-export.md";
}
