// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { ArrowLeft, Link2Off } from "lucide-react";
import { useI18n } from "../lib/i18n";
import type { StudioChatHandoff } from "../lib/studioChatHandoff";

/**
 * 项目作用域条。与课程作用域条同族同形——学生不该需要学两套"我现在在哪"的读法。
 * 架构 §8.3：Chat 永远显示当前作用域，所以这条在绑定时必须可见，且能一键解绑。
 */
export function StudioChatContextBar({
  handoff,
  onReturn,
  onUnbind,
}: {
  handoff: StudioChatHandoff;
  onReturn: () => void;
  onUnbind: () => void;
}) {
  const { t } = useI18n();
  return (
    <section className="kq-study-chat-context" aria-label={t("chat.studioContextLabel")}>
      <div className="kq-study-chat-context-copy">
        <strong>{handoff.projectTitle}</strong>
        <span>{t("chat.studioContextBound")}</span>
      </div>
      <div className="kq-study-chat-context-actions">
        <button type="button" className="kq-study-chat-return" onClick={onReturn}>
          <ArrowLeft aria-hidden />
          {t("chat.studioReturn")}
        </button>
        <button
          type="button"
          className="kq-soft-icon-btn"
          onClick={onUnbind}
          title={t("chat.studioUnbind")}
          aria-label={t("chat.studioUnbind")}
        >
          <Link2Off aria-hidden />
        </button>
      </div>
    </section>
  );
}
