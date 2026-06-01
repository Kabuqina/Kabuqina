// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { startTransition, useCallback, useRef, useState } from "react";
import {
  cmdGetSessionMessages,
  cmdGetSessions,
  parseDeskUserContent,
  type MessageRow,
  type SessionRow,
  type UiMsg,
} from "../chat-api";
import { REMINDER_SESSION_ID } from "../reminderSession";
import type { LoadSessionsOptions } from "./useSessions";

const LAST_SESSION_KEY = "hermesdesk.shell.chat.lastSessionId";

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

function rowsToUiMessages(rows: MessageRow[], sessionModel: string): UiMsg[] {
  const out: UiMsg[] = [];
  let n = 0;
  const mdl = sessionModel.trim();
  for (const m of rows) {
    const role = m.role;
    if (role === "session_meta" || role === "tool") {
      continue;
    }
    if (role !== "user" && role !== "assistant" && role !== "system") {
      continue;
    }
    let text: string;
    let attachments: UiMsg["attachments"];
    if (role === "user") {
      const parsed = parseDeskUserContent(m.content);
      text = parsed.text;
      attachments = parsed.attachments;
      if (!text && !attachments?.length) {
        continue;
      }
    } else {
      text = contentToString(m.content).trim();
      if (!text) {
        continue;
      }
    }
    if (role === "system") {
      out.push({
        id: `s-${n++}`,
        role: "assistant",
        text: `_(system)_\n${text || "—"}`,
        timestamp: typeof m.timestamp === "number" ? m.timestamp : undefined,
        model: mdl || undefined,
      });
      continue;
    }
    out.push({
      id: `m-${n++}`,
      role: role as "user" | "assistant",
      text: text || "",
      attachments,
      timestamp: typeof m.timestamp === "number" ? m.timestamp : undefined,
      model: role === "assistant" && mdl ? mdl : undefined,
    });
  }
  return out;
}

function persistSession(id: string | null) {
  if (typeof window === "undefined" || !window.localStorage) {
    return;
  }
  if (id) {
    window.localStorage.setItem(LAST_SESSION_KEY, id);
  } else {
    window.localStorage.removeItem(LAST_SESSION_KEY);
  }
}

export function useChatState({
  loadSessions,
}: {
  loadSessions: (options?: LoadSessionsOptions) => Promise<void>;
}) {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [threadModel, setThreadModel] = useState("");
  const [messages, setMessages] = useState<UiMsg[]>([]);
  const [apiRequiredOpen, setApiRequiredOpen] = useState(false);
  const [sendErr, setSendErr] = useState<string | null>(null);
  const loadSeqRef = useRef(0);

  const loadThread = useCallback(
    async (sid: string) => {
      const seq = ++loadSeqRef.current;
      setSendErr(null);
      setActiveSessionId(sid);
      persistSession(sid);
      try {
        const [r, list] = await Promise.all([
          cmdGetSessionMessages(sid),
          cmdGetSessions(100, 0, "hermesdesk"),
        ]);
        if (seq !== loadSeqRef.current) {
          return;
        }
        const row = (list.sessions ?? []).find((s: SessionRow) => s.id === sid);
        const m = (row?.model ?? "").trim();
        startTransition(() => {
          setThreadModel(m);
          setMessages(rowsToUiMessages(r.messages ?? [], m));
        });
        void loadSessions({ silent: true });
      } catch (e) {
        if (seq !== loadSeqRef.current) {
          return;
        }
        console.error(e);
        setMessages([]);
        setThreadModel("");
        setActiveSessionId(null);
        persistSession(null);
      }
    },
    [loadSessions]
  );

  const onNewChat = useCallback(() => {
    loadSeqRef.current += 1;
    setActiveSessionId(null);
    setThreadModel("");
    setMessages([]);
    setSendErr(null);
    persistSession(null);
  }, []);

  const onPickSession = useCallback(
    (id: string) => {
      if (id === activeSessionId) {
        return;
      }
      void loadThread(id);
    },
    [activeSessionId, loadThread]
  );

  const onDeleteSession = useCallback(
    async (id: string) => {
      if (activeSessionId === id) {
        onNewChat();
      }
      await loadSessions();
    },
    [activeSessionId, onNewChat, loadSessions]
  );

  const refreshActiveThread = useCallback(async () => {
    if (!activeSessionId) {
      return;
    }
    await loadThread(activeSessionId);
  }, [activeSessionId, loadThread]);

  const openReminderSession = useCallback(async (emptyHint?: string) => {
    try {
      const list = await cmdGetSessions(100, 0, "hermesdesk");
      const exists = (list.sessions ?? []).some((s: SessionRow) => s.id === REMINDER_SESSION_ID);
      if (exists) {
        await loadThread(REMINDER_SESSION_ID);
        return;
      }
    } catch (e) {
      console.error(e);
    }
    loadSeqRef.current += 1;
    setSendErr(null);
    setActiveSessionId(REMINDER_SESSION_ID);
    persistSession(REMINDER_SESSION_ID);
    setThreadModel("");
    setMessages(
      emptyHint
        ? [
            {
              id: "reminder-log-empty",
              role: "assistant" as const,
              text: emptyHint,
              timestamp: Date.now() / 1000,
            },
          ]
        : [],
    );
  }, [loadThread]);

  return {
    activeSessionId,
    setActiveSessionId,
    threadModel,
    setThreadModel,
    messages,
    setMessages,
    sendErr,
    setSendErr,
    apiRequiredOpen,
    setApiRequiredOpen,
    onNewChat,
    onPickSession,
    onDeleteSession,
    refreshActiveThread,
    openReminderSession,
  } as const;
}
