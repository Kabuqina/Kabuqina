// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useState } from "react";
import { ArrowLeft, BookOpen, Clock3, PanelLeftOpen, PanelTopClose, PanelTopOpen } from "lucide-react";
import { useI18n } from "../lib/i18n";
import type { StudyChatHandoff } from "../lib/studyChatHandoff";

/**
 * 这段对话是什么时候的——原来界面上完全看不出来。今天的显示为「今天 HH:MM」，
 * 更早的显示日期。时间戳解析不了就不渲染，不猜。
 */
function formatStarted(
  createdAt: string | undefined,
  t: (key: string, vars?: Record<string, string>) => string,
): { iso: string; label: string } | null {
  if (!createdAt) return null;
  const at = new Date(createdAt);
  if (Number.isNaN(at.getTime())) return null;
  const time = at.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false });
  const now = new Date();
  const sameDay = at.getFullYear() === now.getFullYear()
    && at.getMonth() === now.getMonth()
    && at.getDate() === now.getDate();
  const label = sameDay
    ? t("chat.startedToday", { time })
    : `${at.toLocaleDateString(undefined, { month: "2-digit", day: "2-digit" })} ${time}`;
  return { iso: at.toISOString(), label };
}

/**
 * 对话纸的标题行（原型 `ChatPaper.__header`）。
 *
 * 选中一条有来源的会话时，**只显示来源标签和一个返回动作**——不展开课程面板
 * 或进度面板。那属于 Study 自己，Chat 只是横跨其上的交互层。
 *
 * 标题可以暂时收起，但收起不能破坏会话来源。折叠态始终留下恢复入口，
 * 因而 Study 的精确返回能力不会因为一次界面整理而丢失。
 */
export function ChatPaperHeader({
  studyHandoff,
  onOpenHistory,
  onReturnStudy,
}: {
  studyHandoff: StudyChatHandoff | null;
  onOpenHistory: () => void;
  onReturnStudy: () => void;
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
        startedAt: formatStarted(studyHandoff.createdAt, t),
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
        <PanelLeftOpen aria-hidden size={18} />
      </button>

      {bound ? (
        <>
          {/* 第一行的元信息：课程名做成薄纸标签（manila 三件套）+ 这段对话的时间。
              标题不再挤在这一行——它在第二行独占一行。 */}
          <div className="kq-chat-head-meta" hidden={contextCollapsed}>
            <span className="kq-chat-course-tag">
              <BookOpen aria-hidden size={12} />
              {bound.origin}
            </span>
            {bound.startedAt ? (
              <time className="kq-chat-head-time" dateTime={bound.startedAt.iso}>
                <Clock3 aria-hidden size={12} />
                {bound.startedAt.label}
              </time>
            ) : null}
          </div>
          <div className="kq-chat-head-actions">
            {contextCollapsed ? null : (
              <button type="button" className="kq-chat-return" onClick={bound.onReturn}>
                <ArrowLeft aria-hidden size={16} />
                {bound.returnLabel}
              </button>
            )}
            {/* 一个开关，不是两个按钮：收起/展开都用这颗，位置固定在最右、始终纯图标。
                原来收起态换成了左侧一颗带文字的按钮，控件会跳位、繁简也不一致。 */}
            <button
              type="button"
              className="kq-chat-context-toggle"
              aria-label={contextCollapsed ? t("chat.contextShow") : t("chat.contextHide")}
              title={contextCollapsed ? t("chat.contextShow") : t("chat.contextHide")}
              aria-controls="kq-chat-session-context"
              aria-expanded={!contextCollapsed}
              onClick={() => setCollapsedContextId(contextCollapsed ? null : bound.id)}
            >
              {contextCollapsed
                ? <PanelTopOpen aria-hidden size={15} />
                : <PanelTopClose aria-hidden size={15} />}
            </button>
          </div>
          {/* 第二行：标题独占一行，不再省略号截断。 */}
          <h1 id="kq-chat-session-context" className="kq-chat-session-title" hidden={contextCollapsed}>
            {bound.title}
          </h1>
        </>
      ) : null}
    </header>
  );
}
