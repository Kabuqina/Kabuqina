// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { ArrowLeft, Clock3, Link2Off } from "lucide-react";
import { useI18n } from "../lib/i18n";
import type { StudioChatHandoff } from "../lib/studioChatHandoff";
import type { StudyChatHandoff } from "../lib/studyChatHandoff";

/**
 * 对话纸的标题行（原型 `ChatPaper.__header`）。
 *
 * 选中一条有来源的会话时，**只显示来源标签和一个返回动作**——不展开课程面板、
 * 项目面板或进度面板。那些属于 Study 和 Studio 自己，Chat 只是横跨两者的交互层。
 *
 * 解绑留在这里而不是藏起来：架构 §8.10 要求作用域可以被显式解掉，
 * 而"能解绑"这件事只有在绑着的时候说才有意义。
 */
export function ChatPaperHeader({
  studyHandoff,
  studioHandoff,
  onOpenHistory,
  onReturnStudy,
  onReturnStudio,
  onUnbindStudy,
  onUnbindStudio,
}: {
  studyHandoff: StudyChatHandoff | null;
  studioHandoff: StudioChatHandoff | null;
  onOpenHistory: () => void;
  onReturnStudy: () => void;
  onReturnStudio: () => void;
  onUnbindStudy: () => void;
  onUnbindStudio: () => void;
}) {
  const { t } = useI18n();
  const bound = studyHandoff
    ? {
        title: studyHandoff.focusLabel || studyHandoff.spaceTitle,
        origin: studyHandoff.spaceTitle,
        onReturn: onReturnStudy,
        returnLabel: t("chat.returnToStep"),
        onUnbind: onUnbindStudy,
      }
    : studioHandoff
      ? {
          title: studioHandoff.projectTitle,
          origin: t("appShell.studio"),
          onReturn: onReturnStudio,
          returnLabel: t("chat.returnToProject"),
          onUnbind: onUnbindStudio,
        }
      : null;

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
          <div className="kq-chat-session-title">
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
              className="kq-chat-unbind"
              aria-label={t("chat.unbindScope")}
              title={t("chat.unbindScope")}
              onClick={bound.onUnbind}
            >
              <Link2Off aria-hidden size={15} />
            </button>
          </div>
        </>
      ) : null}
    </header>
  );
}
