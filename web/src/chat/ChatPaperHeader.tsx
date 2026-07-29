// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useState } from "react";
import { ArrowLeft, Clock3, PanelTopClose, PanelTopOpen } from "lucide-react";
import { useI18n } from "../lib/i18n";
import type { StudioChatHandoff } from "../lib/studioChatHandoff";
import type { StudyChatHandoff } from "../lib/studyChatHandoff";

/**
 * 对话纸的标题行（原型 `ChatPaper.__header`）。
 *
 * 选中一条有来源的会话时，**只显示来源标签和一个返回动作**——不展开课程面板、
 * 项目面板或进度面板。那些属于 Study 和 Studio 自己，Chat 只是横跨两者的交互层。
 *
 * 标题可以暂时收起，但收起不能破坏会话来源。折叠态始终留下恢复入口，
 * 因而 Study / Studio 的精确返回能力不会因为一次界面整理而丢失。
 */
export function ChatPaperHeader({
  studyHandoff,
  studioHandoff,
  onOpenHistory,
  onReturnStudy,
  onReturnStudio,
}: {
  studyHandoff: StudyChatHandoff | null;
  studioHandoff: StudioChatHandoff | null;
  onOpenHistory: () => void;
  onReturnStudy: () => void;
  onReturnStudio: () => void;
}) {
  const { t } = useI18n();
  const [collapsedContextId, setCollapsedContextId] = useState<string | null>(null);
  const bound = studyHandoff
    ? {
        id: `study:${studyHandoff.sessionId}`,
        title: studyHandoff.focusLabel || studyHandoff.spaceTitle,
        origin: studyHandoff.spaceTitle,
        onReturn: onReturnStudy,
        returnLabel: t("chat.returnToStep"),
      }
    : studioHandoff
      ? {
          id: `studio:${studioHandoff.sessionId}`,
          title: studioHandoff.projectTitle,
          origin: t("appShell.studio"),
          onReturn: onReturnStudio,
          returnLabel: t("chat.returnToProject"),
        }
      : null;
  const contextCollapsed = Boolean(bound && collapsedContextId === bound.id);

  return (
    <header className="kq-chat-paper-head">
      <button
        type="button"
        className="kq-chat-history-toggle"
        aria-label={t("chat.historyOpen")}
        title={t("chat.historyOpen")}
        onClick={onOpenHistory}
      >
        <Clock3 aria-hidden size={18} />
      </button>

      {bound && contextCollapsed ? (
        <button
          type="button"
          className="kq-chat-return kq-chat-context-restore"
          aria-expanded="false"
          onClick={() => setCollapsedContextId(null)}
        >
          <PanelTopOpen aria-hidden size={16} />
          {t("chat.contextShow")}
        </button>
      ) : bound ? (
        <>
          <div id="kq-chat-session-context" className="kq-chat-session-title">
            <h1>{bound.title}</h1>
            <span>{bound.origin}</span>
          </div>
          <div className="kq-chat-head-actions">
            <button type="button" className="kq-chat-return" onClick={bound.onReturn}>
              <ArrowLeft aria-hidden size={16} />
              {bound.returnLabel}
            </button>
            <button
              type="button"
              className="kq-chat-context-toggle"
              aria-label={t("chat.contextHide")}
              title={t("chat.contextHide")}
              aria-controls="kq-chat-session-context"
              aria-expanded="true"
              onClick={() => setCollapsedContextId(bound.id)}
            >
              <PanelTopClose aria-hidden size={15} />
            </button>
          </div>
        </>
      ) : null}
    </header>
  );
}
