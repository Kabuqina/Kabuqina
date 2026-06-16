// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { Download, RefreshCw, RotateCcw } from "lucide-react";
import { Section } from "../../components/ui/Section";
import { Button } from "../../components/ui/Button";
import { useI18n } from "../../lib/i18n";
import {
  checkForAppUpdate,
  formatUpdateProgress,
  installAppUpdate,
  relaunchApp,
  type AppUpdate,
  type UpdateDownloadProgress,
} from "../../lib/app-update";

type UpdateState =
  | "idle"
  | "checking"
  | "upToDate"
  | "available"
  | "downloading"
  | "ready"
  | "error";

function errText(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export function SettingsUpdate() {
  const { t } = useI18n();
  const [state, setState] = useState<UpdateState>("idle");
  const [update, setUpdate] = useState<AppUpdate | null>(null);
  const [progress, setProgress] = useState<UpdateDownloadProgress | null>(null);
  const [error, setError] = useState<string | null>(null);

  const checkNow = useCallback(async () => {
    setState("checking");
    setError(null);
    setProgress(null);
    try {
      const next = await checkForAppUpdate();
      setUpdate(next);
      setState(next ? "available" : "upToDate");
    } catch (e) {
      setUpdate(null);
      setError(errText(e));
      setState("error");
    }
  }, []);

  const installNow = useCallback(async () => {
    if (!update) return;
    setState("downloading");
    setError(null);
    setProgress(null);
    try {
      await installAppUpdate(update, setProgress);
      setState("ready");
    } catch (e) {
      setError(errText(e));
      setState("error");
    }
  }, [update]);

  useEffect(() => {
    let disposed = false;
    const unlisten = listen("app-update-check-requested", () => {
      if (!disposed) void checkNow();
    });
    return () => {
      disposed = true;
      void unlisten.then((off) => off());
    };
  }, [checkNow]);

  const busy = state === "checking" || state === "downloading";
  const progressText = formatUpdateProgress(progress);

  return (
    <Section icon={Download} title={t("settings.updateTitle")} desc={t("settings.updateDesc")}>
      <div className="space-y-3">
        <div className="rounded-md border border-[var(--kq-color-border)] bg-white/45 px-3 py-2 text-sm leading-relaxed text-[var(--kq-color-ink)] dark:border-zinc-700 dark:bg-zinc-900/35 dark:text-zinc-300">
          {state === "idle" && t("settings.updateIdle")}
          {state === "checking" && t("settings.updateChecking")}
          {state === "upToDate" && t("settings.updateUpToDate")}
          {state === "available" && update
            ? t("settings.updateAvailable", {
                current: update.currentVersion,
                next: update.version,
              })
            : null}
          {state === "downloading" &&
            t("settings.updateDownloading", { progress: progressText || t("settings.updateProgressUnknown") })}
          {state === "ready" && t("settings.updateReady")}
          {state === "error" && t("settings.updateError")}
        </div>

        {update?.body && state === "available" ? (
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-[var(--kq-color-muted)]">
            {update.body}
          </p>
        ) : null}

        {error ? (
          <p className="text-sm leading-relaxed text-red-600 dark:text-red-400">
            {error}
          </p>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <Button onClick={() => void checkNow()} disabled={busy}>
            <RefreshCw className="h-4 w-4" aria-hidden />
            {state === "checking" ? t("settings.updateCheckingButton") : t("settings.updateCheck")}
          </Button>
          <Button
            variant="secondary"
            onClick={() => void installNow()}
            disabled={!update || busy || state === "ready"}
          >
            <Download className="h-4 w-4" aria-hidden />
            {state === "downloading" ? t("settings.updateInstalling") : t("settings.updateInstall")}
          </Button>
          <Button variant="secondary" onClick={() => void relaunchApp()} disabled={state !== "ready"}>
            <RotateCcw className="h-4 w-4" aria-hidden />
            {t("settings.updateRestart")}
          </Button>
        </div>
      </div>
    </Section>
  );
}
