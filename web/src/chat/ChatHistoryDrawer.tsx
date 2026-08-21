// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useRef } from "react";
import { AlarmClock, Download, FolderOpen, ListTodo, Plus, Trash2, X } from "lucide-react";
import { useI18n } from "../lib/i18n";
import { cn } from "../lib/cn";
import type { SessionRow } from "./chat-api";
import { deriveSessionPresentation } from "./sessionPresentation";
import { readSessionStudyHandoff, type StudyChatHandoff } from "../lib/studyChatHandoff";

/**
 * 历史会话抽屉（原型 `SessionHistory`）。
 *
 * Chat 是**刻意极简**的自由对话空间，所以历史不占一条常驻侧栏——它收起来，
 * 需要时才拉开。三类会话（自由 / 课程 / 项目）进同一份列表，**没有并列的作用域
 * 标签页**；来源只用一个低强调标签辨认，用户主动选中某条之后才进入那个作用域。
 *
 * 原来侧栏上那几个工具（定时任务、工作区、整理桌面、导出）没有别处可去，
 * 收进抽屉底部的低强调一栏——换布局不等于砍能力。
 */
export function ChatHistoryDrawer({
  open,
  sessions,
  activeSessionId,
  loading,
  onClose,
  onNewChat,
  onSelectSession,
  onDeleteSession,
  onOpenActivity,
  onOpenScheduledTasks,
  onOpenWorkspace,
  onExport,
}: {
  open: boolean;
  sessions: SessionRow[];
  activeSessionId: string | null;
  loading?: boolean;
  onClose: () => void;
  onNewChat: () => void;
  onSelectSession: (id: string) => void;
  onDeleteSession: (id: string, e: React.MouseEvent) => void;
  onOpenActivity: () => void;
  onOpenScheduledTasks: () => void;
  onOpenWorkspace: () => void;
  onExport: () => void;
}) {
  const { t, locale } = useI18n();
  const panelRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, open]);

  return (
    <>
      {open ? <div className="kq-chat-drawer-scrim" role="presentation" onMouseDown={onClose} /> : null}
      <aside
        ref={panelRef}
        className={cn("kq-chat-drawer", open && "is-open")}
        aria-label={t("chat.historyTitle")}
        aria-hidden={!open}
        inert={!open}
      >
        <header className="kq-chat-drawer-head">
          <h2>{t("chat.historyTitle")}</h2>
          <button ref={closeRef} type="button" aria-label={t("chat.historyClose")} onClick={onClose}>
            <X aria-hidden size={17} />
          </button>
        </header>

        <button type="button" className="kq-chat-drawer-new" onClick={onNewChat}>
          <Plus aria-hidden size={16} />
          {t("chat.newChat")}
        </button>

        <div className="kq-chat-drawer-list">
          {loading && !sessions.length ? (
            <p className="kq-chat-drawer-empty" role="status">{t("chat.historyLoading")}</p>
          ) : null}
          {!loading && !sessions.length ? (
            <p className="kq-chat-drawer-empty">{t("chat.historyEmpty")}</p>
          ) : null}
          {sessions.map((session) => {
            const presentation = deriveSessionPresentation(session, locale);
            const origin = sessionOrigin(session.id, t);
            return (
              <button
                type="button"
                key={session.id}
                className={cn("kq-chat-drawer-row", session.id === activeSessionId && "is-active")}
                aria-current={session.id === activeSessionId ? "true" : undefined}
                onClick={() => onSelectSession(session.id)}
              >
                <strong>{presentation.label}</strong>
                <span>
                  {presentation.group}
                  {/* 来源只是一个低强调标签，不是一个并列的作用域入口。 */}
                  {origin ? <small className="kq-chat-drawer-origin">{origin}</small> : null}
                </span>
                <span
                  className="kq-chat-drawer-delete"
                  role="button"
                  tabIndex={0}
                  aria-label={t("chat.deleteSession")}
                  onClick={(event) => {
                    event.stopPropagation();
                    onDeleteSession(session.id, event);
                  }}
                  onKeyDown={(event) => {
                    if (event.key !== "Enter" && event.key !== " ") return;
                    event.preventDefault();
                    event.stopPropagation();
                    onDeleteSession(session.id, event as unknown as React.MouseEvent);
                  }}
                >
                  <Trash2 aria-hidden size={14} />
                </span>
              </button>
            );
          })}
        </div>

        {/* 原来长在侧栏上的工具：不显眼，但都还在。 */}
        <div className="kq-chat-drawer-tools">
          {/* 进行中搬到这里：横条上不该有第二处会跳数字的东西（设计稿 5）。 */}
          <button type="button" onClick={onOpenActivity}>
            <ListTodo aria-hidden size={15} />{t("appShell.activity")}
          </button>
          <button type="button" onClick={onOpenScheduledTasks}>
            <AlarmClock aria-hidden size={15} />{t("chat.scheduledTasks")}
          </button>
          <button type="button" onClick={onOpenWorkspace}>
            <FolderOpen aria-hidden size={15} />{t("chat.openWorkspace")}
          </button>
          <button type="button" onClick={onExport}>
            <Download aria-hidden size={15} />{t("chat.exportChat")}
          </button>
        </div>
      </aside>
    </>
  );
}

/** 会话的来源短语。绑定是会话自己的真值，绝不猜（架构 §8.3）。 */
function sessionOrigin(sessionId: string, t: (key: string) => string): string | null {
  const study: StudyChatHandoff | null = readSessionStudyHandoff(sessionId);
  if (study) return study.spaceTitle || t("appShell.study");
  return null;
}
