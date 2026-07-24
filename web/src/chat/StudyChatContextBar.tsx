// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { ArrowLeft, Link2Off } from "lucide-react";
import { useI18n } from "../lib/i18n";
import type { StudyChatHandoff } from "../lib/studyChatHandoff";

export function StudyChatContextBar({
  handoff,
  onReturn,
  onUnbind,
}: {
  handoff: StudyChatHandoff;
  onReturn: () => void;
  onUnbind: () => void;
}) {
  const { t } = useI18n();
  return (
    <section className="kq-study-chat-context" aria-label={t("chat.studyContextLabel")}>
      <div className="kq-study-chat-context-copy">
        <strong>{handoff.spaceTitle} · {handoff.focusLabel}</strong>
        <span>{t("chat.studyContextBound")}</span>
      </div>
      <div className="kq-study-chat-context-actions">
        <button type="button" className="kq-study-chat-return" onClick={onReturn}>
          <ArrowLeft aria-hidden />
          {t("chat.studyReturn")}
        </button>
        <button
          type="button"
          className="kq-soft-icon-btn"
          onClick={onUnbind}
          title={t("chat.studyUnbind")}
          aria-label={t("chat.studyUnbind")}
        >
          <Link2Off aria-hidden />
        </button>
      </div>
    </section>
  );
}
