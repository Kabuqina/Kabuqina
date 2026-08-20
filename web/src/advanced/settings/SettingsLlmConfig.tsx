// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Key, Loader2, Trash2 } from "lucide-react";
import { LlmConfigEditor } from "../../components/LlmConfigEditor";
import { Button } from "../../components/ui/Button";
import { Section } from "../../components/ui/Section";
import { confirm } from "../../lib/confirmDialog";
import { useI18n } from "../../lib/i18n";

type Props = {
  hasSecret: boolean;
  onCredentialChanged: () => void | Promise<void>;
};

export function SettingsLlmConfig({ hasSecret, onCredentialChanged }: Props) {
  const { t } = useI18n();
  const [clearing, setClearing] = useState(false);
  const [cleared, setCleared] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSaved() {
    setCleared(false);
    setError(null);
    try {
      await onCredentialChanged();
    } catch (cause) {
      console.error("Failed to refresh credential status after save", cause);
    }
  }

  async function handleClear() {
    const approved = await confirm({
      title: t("settings.llmConfigClearTitle"),
      message: t("settings.llmConfigClearAsk"),
      confirmLabel: t("settings.llmConfigClear"),
      cancelLabel: t("dialog.cancel"),
      tone: "danger",
    });
    if (!approved) return;

    setClearing(true);
    setCleared(false);
    setError(null);
    try {
      await invoke("cmd_clear_secret");
      setCleared(true);
      try {
        await onCredentialChanged();
      } catch (cause) {
        console.error("Failed to refresh credential status after clear", cause);
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : String(cause);
      setError(t("settings.llmConfigClearFailed", { msg: message }));
    } finally {
      setClearing(false);
    }
  }

  return (
    <Section icon={Key} title={t("settings.llmConfigTitle")} desc={t("settings.llmConfigDesc")}>
      <LlmConfigEditor
        key={hasSecret ? "secret-present" : "secret-missing"}
        mode="settings"
        onSaved={handleSaved}
      />
      {hasSecret && !cleared ? (
        <div className="mt-5 border-t border-[var(--kq-color-border)] pt-4">
          <Button
            type="button"
            variant="secondary"
            disabled={clearing}
            onClick={() => void handleClear()}
            className="text-[var(--danger)] hover:opacity-80"
          >
            {clearing ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Trash2 className="h-4 w-4" aria-hidden />
            )}
            {clearing ? t("settings.llmConfigClearing") : t("settings.llmConfigClear")}
          </Button>
        </div>
      ) : null}
      {cleared ? (
        <p className="mt-3 text-sm text-[var(--success)]">
          {t("settings.llmConfigCleared")}
        </p>
      ) : null}
      {error ? (
        <p className="mt-3 text-sm text-[var(--danger)]" role="alert">
          {error}
        </p>
      ) : null}
    </Section>
  );
}
