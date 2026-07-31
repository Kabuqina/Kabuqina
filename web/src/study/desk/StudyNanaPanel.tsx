// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { ArrowUpRight, Send, Square, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChatMessageList } from "../../chat/ChatMessageList";
import {
  cmdGetSessionMessages,
  parseDeskUserContent,
  type MessageRow,
  type UiMsg,
} from "../../chat/chat-api";
import { useSendMessage } from "../../chat/hooks/useSendMessage";
import { messageContentToString } from "../../chat/inFlightTurnUtils";
import { useI18n } from "../../lib/i18n";
import {
  bindStudyHandoff,
  buildStudyNanaPrompt,
  STUDY_NANA_STARTERS,
  visibleStudyUserInput,
  type StudyChatHandoffV2,
} from "../../lib/studyChatHandoff";

type LoadMessages = (sessionId: string) => Promise<{ messages: MessageRow[] }>;
const STUDY_NANA_DRAFT_PREFIX = "kabuqina.study.nana-draft.v1";

function draftKey(sessionId: string): string {
  return `${STUDY_NANA_DRAFT_PREFIX}:${sessionId}`;
}

function readDraft(sessionId: string): string {
  try {
    return window.localStorage.getItem(draftKey(sessionId)) ?? "";
  } catch {
    return "";
  }
}

function writeDraft(sessionId: string, value: string): void {
  try {
    if (value) window.localStorage.setItem(draftKey(sessionId), value);
    else window.localStorage.removeItem(draftKey(sessionId));
  } catch {
    // A draft is convenience state; storage failure must not block tutoring.
  }
}

function rowsToMessages(rows: MessageRow[]): UiMsg[] {
  return rows.flatMap((row, index) => {
    if (row.role !== "user" && row.role !== "assistant") return [];
    const parsed = row.role === "user" ? parseDeskUserContent(row.content) : null;
    const value = row.role === "user"
      ? visibleStudyUserInput(parsed?.text ?? "")
      : messageContentToString(row.content).trim();
    if (!value && !parsed?.attachments?.length) return [];
    return [{
      id: `study-panel-${index}`,
      role: row.role,
      text: value,
      ...(parsed?.attachments?.length ? { attachments: parsed.attachments } : {}),
      ...(typeof row.timestamp === "number" ? { timestamp: row.timestamp } : {}),
    } satisfies UiMsg];
  });
}

export function StudyNanaPanel({
  handoff,
  loading = false,
  contextError = false,
  initialPrompt = "",
  autoSend = false,
  onClose,
  onOpenFull,
  loadMessages = cmdGetSessionMessages,
}: {
  handoff: StudyChatHandoffV2 | null;
  loading?: boolean;
  contextError?: boolean;
  initialPrompt?: string;
  autoSend?: boolean;
  onClose: () => void;
  onOpenFull: (handoff: StudyChatHandoffV2, draft: string) => void;
  loadMessages?: LoadMessages;
}) {
  const { locale } = useI18n();
  const [activeSessionId, setActiveSessionId] = useState<string | null>(handoff?.sessionId ?? null);
  const [threadModel, setThreadModel] = useState("");
  const [messages, setMessages] = useState<UiMsg[]>([]);
  const [sendErr, setSendErr] = useState<string | null>(null);
  const [needsModelSetup, setNeedsModelSetup] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const autoSendKeyRef = useRef("");
  const loadSessions = useCallback(async () => undefined, []);
  const prepareText = useCallback(
    (value: string) => handoff ? buildStudyNanaPrompt(handoff, value) : value,
    [handoff],
  );
  const {
    input,
    setInput,
    sending,
    progress,
    pendingInteraction,
    onSend,
    onStopAgent,
    onRespondInteraction,
  } = useSendMessage({
    activeSessionId,
    setActiveSessionId,
    threadModel,
    setThreadModel,
    setMessages,
    loadSessions,
    setApiRequiredOpen: setNeedsModelSetup,
    setSendErr,
    locale,
    prepareText,
  });

  useEffect(() => {
    if (!handoff) return;
    bindStudyHandoff(handoff);
    setActiveSessionId(handoff.sessionId);
    setInput(autoSend ? initialPrompt : readDraft(handoff.sessionId) || initialPrompt);
    setHistoryLoading(true);
    let alive = true;
    void loadMessages(handoff.sessionId)
      .then((response) => {
        if (alive) setMessages(rowsToMessages(response.messages ?? []));
      })
      .catch(() => {
        // A new scoped session legitimately has no stored transcript yet.
        if (alive) setMessages([]);
      })
      .finally(() => {
        if (alive) setHistoryLoading(false);
      });
    return () => { alive = false; };
  }, [autoSend, handoff, initialPrompt, loadMessages, setInput]);

  useEffect(() => {
    const prompt = initialPrompt.trim();
    if (!autoSend || !handoff || loading || historyLoading || sending || !prompt || input.trim() !== prompt) return;
    const key = `${handoff.sessionId}:${prompt}`;
    if (autoSendKeyRef.current === key) return;
    autoSendKeyRef.current = key;
    void onSend();
  }, [autoSend, handoff, historyLoading, initialPrompt, input, loading, onSend, sending]);

  useEffect(() => {
    if (handoff) writeDraft(handoff.sessionId, input);
  }, [handoff, input]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const starters = useMemo(
    () => handoff ? STUDY_NANA_STARTERS[handoff.nanaContext.origin.page] : [],
    [handoff],
  );

  return (
    <aside className="kq-study-side-panel kq-study-nana-panel" aria-label="Study 小娜聊天框">
      <header className="kq-study-side-panel__header">
        <div>
          <span className="kq-study-side-panel__eyebrow">Study</span>
          <h2>问小娜</h2>
        </div>
        <button type="button" className="kq-study-side-panel__close" aria-label="关闭聊天框" onClick={onClose}>
          <X aria-hidden />
        </button>
      </header>

      <p className="kq-study-nana-scope">
        {handoff ? `${handoff.spaceTitle} · ${handoff.focusLabel}` : "正在拿起当前这一页…"}
      </p>

      {loading || historyLoading ? <p className="kq-study-side-panel__status" role="status">正在接上这本本子的对话…</p> : null}
      {contextError ? (
        <p className="kq-study-side-panel__alert" role="alert">
          当前页面内容暂时没有读到。为了不猜测，小娜不会自动发送问题；你仍可以在完整 Chat 中继续。
        </p>
      ) : null}

      {handoff && !messages.length && !sending ? (
        <div className="kq-study-nana-starters" aria-label="可以这样问">
          {starters.map((starter) => (
            <button type="button" key={starter} onClick={() => setInput(starter)}>{starter}</button>
          ))}
        </div>
      ) : null}

      <ChatMessageList
        compact
        emptyLabel="带着当前这一页问，不必重新交代本子和位置。"
        messages={messages}
        sending={sending}
        sendErr={sendErr}
        progress={progress}
        pendingInteraction={pendingInteraction}
        onRespondInteraction={onRespondInteraction}
      />

      {needsModelSetup ? (
        <p className="kq-study-side-panel__alert" role="alert">请先在设置中配置模型，再继续这次本子对话。</p>
      ) : null}

      <form
        className="kq-study-nana-composer"
        onSubmit={(event) => {
          event.preventDefault();
          void onSend();
        }}
      >
        <textarea
          aria-label="发送消息"
          value={input}
          maxLength={4000}
          disabled={!handoff || loading}
          onChange={(event) => setInput(event.currentTarget.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void onSend();
            }
          }}
          placeholder="继续问这一页…"
        />
        {sending ? (
          <button type="button" aria-label="停止回答" onClick={() => void onStopAgent()}><Square aria-hidden /></button>
        ) : (
          <button type="submit" aria-label="发送" disabled={!handoff || !input.trim()}><Send aria-hidden /></button>
        )}
      </form>

      <button
        className="kq-study-open-full-chat"
        type="button"
        disabled={!handoff}
        onClick={() => handoff && onOpenFull(handoff, input)}
      >
        在完整 Chat 中打开
        <ArrowUpRight aria-hidden />
      </button>
    </aside>
  );
}

export default StudyNanaPanel;
