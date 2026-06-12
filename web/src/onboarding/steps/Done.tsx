// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { invoke } from "@tauri-apps/api/core";
import { useI18n } from "../../lib/i18n";
import { clearDraft, useDraft } from "../../lib/store";

export function Done() {
  const { t } = useI18n();
  const nav = useNavigate();
  const draft = useDraft();

  useEffect(() => {
    invoke("cmd_set_personality", { name: draft.personality }).catch(() => {});
  }, [draft.personality]);

  async function openWorkspace() {
    try {
      await invoke("cmd_open_workspace");
    } catch (e) {
      console.error(e);
    }
  }

  function openChat() {
    clearDraft();
    nav("/chat", { replace: true });
  }

  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <h1 className="hd-wizard-title">{t("done.title")}</h1>
      </div>

      <div className="hd-glass-subtle space-y-2 p-5">
        <div className="hd-wizard-label">{t("done.workspaceTitle")}</div>
        <p className="hd-wizard-muted">{t("done.workspaceBody")}</p>
        <button
          onClick={openWorkspace}
          className="hd-link hd-wizard-body underline underline-offset-4"
        >
          {t("done.openFolder")}
        </button>
      </div>

      <button
        onClick={openChat}
        className="kq-btn-primary w-full rounded-[var(--radius-shell-lg)] px-6 py-4 text-base font-medium transition hover:opacity-95"
      >
        {t("done.cta")}
      </button>
    </div>
  );
}
