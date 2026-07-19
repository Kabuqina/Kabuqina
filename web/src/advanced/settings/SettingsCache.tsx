// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Trash2 } from "lucide-react";
import { Button } from "../../components/ui/Button";
import { Section } from "../../components/ui/Section";
import { StatusBanner } from "../../components/ui/StatusBanner";
import { confirm } from "../../lib/confirmDialog";
import { useI18n } from "../../lib/i18n";
import { clearVolatileBrowserCache } from "./cacheCleanup";

type Feedback = { variant: "success" | "error"; message: string } | null;

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function SettingsCache() {
  const { t } = useI18n();
  const [clearing, setClearing] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);

  async function clearCache() {
    const accepted = await confirm({
      title: t("settings.cacheConfirmTitle"),
      message: t("settings.cacheConfirmMessage"),
      confirmLabel: t("settings.cacheConfirmAction"),
      tone: "danger",
    });
    if (!accepted) return;

    setClearing(true);
    setFeedback(null);
    try {
      // Clear durable STUDY history through the trusted desktop backend first.
      // Browser-side state is removed only after that owner-scoped operation succeeds.
      await invoke("cmd_study_cache_clear");
      const browserResult = await clearVolatileBrowserCache();
      if (browserResult.errors.length > 0) {
        throw new Error(browserResult.errors.join("; "));
      }
      setFeedback({ variant: "success", message: t("settings.cacheSuccess") });
    } catch (error) {
      setFeedback({
        variant: "error",
        message: t("settings.cacheFailed", { message: errorText(error) }),
      });
    } finally {
      setClearing(false);
    }
  }

  return (
    <Section icon={Trash2} title={t("settings.cacheTitle")} desc={t("settings.cacheDesc")}>
      <div className="space-y-3">
        <p className="text-xs leading-relaxed text-[var(--kq-color-muted)]">
          {t("settings.cacheKeep")}
        </p>
        <Button variant="secondary" onClick={() => void clearCache()} disabled={clearing}>
          {clearing ? t("settings.cacheClearing") : t("settings.cacheButton")}
        </Button>
        {feedback ? <StatusBanner variant={feedback.variant} title={feedback.message} /> : null}
      </div>
    </Section>
  );
}
