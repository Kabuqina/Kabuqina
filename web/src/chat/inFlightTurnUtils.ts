import type { MessageRow, UiMsg } from "./chat-api";
import type { AgentProgressState } from "./hooks/useAgentProgress";

export type InFlightStatus = "running" | "reconnecting" | "finalizing" | "failed";

export type InFlightTurn = {
  sessionId: string;
  requestId: string;
  startedAt: number;
  userMsg: UiMsg;
  pendingAssistant: UiMsg;
  streamedText: string;
  status: InFlightStatus;
  progress: AgentProgressState | null;
};

export function messageContentToString(content: unknown): string {
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
        if (c && typeof c === "object" && "content" in c) {
          return messageContentToString((c as { content?: unknown }).content);
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

function attachmentKey(msg: UiMsg): string {
  return (msg.attachments ?? [])
    .map((a) => `${a.name}\0${a.mime}`)
    .sort()
    .join("\n");
}

function sameUserMessage(a: UiMsg, b: UiMsg): boolean {
  if (a.role !== "user" || b.role !== "user" || a.text !== b.text) {
    return false;
  }
  const aAttachments = attachmentKey(a);
  const bAttachments = attachmentKey(b);
  if (!aAttachments || !bAttachments) {
    return true;
  }
  return aAttachments === bAttachments;
}

export function latestAssistantText(rows: MessageRow[]): string {
  for (let i = rows.length - 1; i >= 0; i--) {
    const row = rows[i];
    if (row.role !== "assistant") {
      continue;
    }
    const text = messageContentToString(row.content).trim();
    if (text) {
      return text;
    }
  }
  return "";
}

export function mergeInFlightMessages(
  dbMessages: UiMsg[],
  turn: InFlightTurn | null | undefined,
): { messages: UiMsg[]; clearTurn: boolean } {
  if (!turn) {
    return { messages: dbMessages, clearTurn: false };
  }

  let userIndex = -1;
  for (let i = dbMessages.length - 1; i >= 0; i--) {
    if (sameUserMessage(dbMessages[i], turn.userMsg)) {
      userIndex = i;
      break;
    }
  }

  if (userIndex >= 0) {
    const hasFinalAssistant = dbMessages
      .slice(userIndex + 1)
      .some((m) => m.role === "assistant" && m.text.trim());
    if (hasFinalAssistant) {
      return { messages: dbMessages, clearTurn: true };
    }
  }

  const merged = [...dbMessages];
  if (userIndex < 0) {
    merged.push(turn.userMsg);
  }
  if (turn.status !== "failed") {
    merged.push(turn.pendingAssistant);
  }
  return { messages: merged, clearTurn: false };
}
