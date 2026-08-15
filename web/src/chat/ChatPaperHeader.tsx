// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useState } from "react";
import { ArrowLeft, Clock3, PanelTopClose, PanelTopOpen } from "lucide-react";
import { useI18n } from "../lib/i18n";
import type { StudyChatHandoff } from "../lib/studyChatHandoff";

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

      {bound ? (
        <>
          {/* 收起时留在 DOM 里只加 hidden：位置不塌、aria-controls 始终指向真实元素。 */}
          <div id="kq-chat-session-context" className="kq-chat-session-title" hidden={contextCollapsed}>
            <h1>{bound.title}</h1>
            <span>{bound.origin}</span>
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
        </>
      ) : null}
    </header>
  );
}
