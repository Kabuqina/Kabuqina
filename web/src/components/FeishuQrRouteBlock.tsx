// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { confirm } from "../lib/confirmDialog";
import { useI18n } from "../lib/i18n";
import { cn } from "../lib/cn";
import { StatusBanner } from "./ui/StatusBanner";
import { PlatformButton } from "./ui/PlatformButton";

export type FeishuQrProgress = {
  phase?: string;
  qr_url?: string | null;
  message?: string | null;
};

export type FeishuQrResult = {
  ok?: boolean;
  app_id?: string;
  domain?: string;
  open_id?: string | null;
  bot_name?: string | null;
  error?: string;
};

export type FeishuQrStatusPayload = {
  running: boolean;
  progress: FeishuQrProgress | null;
  result: FeishuQrResult | null;
};

export type FeishuEnvSnapshot = {
  configured: boolean;
  hasAppId?: boolean;
  hasAppSecret?: boolean;
  appIdHint?: string | null;
};

type Props = {
  className?: string;
  onSuccess?: (payload: { appId: string }) => void;
  onHermesRunningChange?: (running: boolean) => void;
};



function ipcErr(e: unknown): string {
  if (typeof e === "string") return e;
  if (e && typeof e === "object" && "message" in e) return String((e as Error).message);
  return String(e);
}

export function FeishuQrRouteBlock({ className, onSuccess, onHermesRunningChange }: Props) {
  const { t } = useI18n();
  const [feishuEnv, setFeishuEnv] = useState<FeishuEnvSnapshot | null>(null);
  const [polling, setPolling] = useState(false);
  const [view, setView] = useState<FeishuQrStatusPayload | null>(null);
  const [restarted, setRestarted] = useState(false);
  const [inlineErr, setInlineErr] = useState<string | null>(null);
  const [restartBusy, setRestartBusy] = useState(false);
  const [restartErr, setRestartErr] = useState<string | null>(null);
  const [removing, setRemoving] = useState(false);
  const exitStreak = useRef(0);
  const onSuccessRef = useRef(onSuccess);
  onSuccessRef.current = onSuccess;
  const onHermesRef = useRef(onHermesRunningChange);
  onHermesRef.current = onHermesRunningChange;

  const refreshFeishuEnv = useCallback(async () => {
    try {
      const snap = await invoke<FeishuEnvSnapshot>("cmd_feishu_env_status");
      setFeishuEnv(snap);
    } catch {
      setFeishuEnv(null);
    }
  }, []);

  async function handleRemove() {
    const ok = await confirm({
      title: t("settings.removeConfigAskTitle"),
      message: t("settings.removeConfigAsk"),
      confirmLabel: t("dialog.remove"),
      cancelLabel: t("dialog.cancel"),
      tone: "warning",
    });
    if (!ok) return;
    setRemoving(true);
    try { await invoke("cmd_feishu_env_remove"); void refreshFeishuEnv(); }
    catch { void refreshFeishuEnv(); }
    finally { setRemoving(false); }
  }

  useEffect(() => {
    void refreshFeishuEnv();
  }, [refreshFeishuEnv]);

  useEffect(() => {
    if (!polling) return;
    let cancelled = false;

    const tick = async () => {
      try {
        const s = await invoke<FeishuQrStatusPayload>("cmd_feishu_qr_status");
        if (cancelled) return;
        setView(s);
        if (s.running) {
          exitStreak.current = 0;
          return;
        }
        const r = s.result;
        if (r && typeof r.ok === "boolean") {
          exitStreak.current = 0;
          setPolling(false);
          if (r.ok) {
            if (r.app_id) {
              onSuccessRef.current?.({ appId: String(r.app_id) });
            }
            setRestartErr(null);
            try {
              await invoke<number>("cmd_restart_embedded_hermes");
              if (!cancelled) {
                setRestarted(true);
                const pyStat = await invoke<{ running: boolean }>("cmd_python_status");
                onHermesRef.current?.(pyStat.running);
                void refreshFeishuEnv();
              }
            } catch (e) {
              console.error(e);
              if (!cancelled) {
                setRestarted(false);
                setRestartErr(t("settings.feishuRestartFailed", { msg: ipcErr(e) }));
              }
            }
          }
          return;
        }
        exitStreak.current += 1;
        if (exitStreak.current >= 8) {
          setPolling(false);
          setInlineErr(
            t("settings.feishuError", { msg: "process exited without result file" })
          );
        }
      } catch (e) {
        console.error(e);
      }
    };

    void tick();
    const id = window.setInterval(() => void tick(), 1000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [polling, t, refreshFeishuEnv]);

  const phaseLabel = useCallback(
    (phase: string | undefined) => {
      switch (phase) {
        case "starting":
          return t("settings.feishuPhaseStarting");
        case "connecting":
          return t("settings.feishuPhaseConnecting");
        case "waiting_scan":
          return t("settings.feishuPhaseWaiting");
        case "done":
          return t("settings.feishuPhaseDone");
        case "error":
          return t("settings.feishuPhaseError");
        default:
          return phase ?? "…";
      }
    },
    [t]
  );

  async function startFeishuQr() {
    setInlineErr(null);
    setRestartErr(null);
    setRestarted(false);
    setView(null);
    exitStreak.current = 0;
    try {
      await invoke("cmd_feishu_qr_start");
      setPolling(true);
    } catch (e) {
      const raw = e instanceof Error ? e.message : String(e);
      setInlineErr(
        raw.includes("feishu_qr_worker.py")
          ? t("settings.feishuWorkerMissing")
          : t("settings.feishuError", { msg: raw })
      );
    }
  }

  async function cancelFeishuQr() {
    try {
      await invoke("cmd_feishu_qr_cancel");
    } catch (e) {
      console.error(e);
    }
    setPolling(false);
    exitStreak.current = 0;
  }

  async function manualRestartAssistant() {
    setRestartErr(null);
    setRestartBusy(true);
    try {
      await invoke<number>("cmd_restart_embedded_hermes");
      setRestarted(true);
      const pyStat = await invoke<{ running: boolean }>("cmd_python_status");
      onHermesRunningChange?.(pyStat.running);
      void refreshFeishuEnv();
    } catch (e) {
      console.error(e);
      setRestartErr(t("settings.feishuRestartFailed", { msg: ipcErr(e) }));
    } finally {
      setRestartBusy(false);
    }
  }

  const partial =
    feishuEnv &&
    !feishuEnv.configured &&
    ((feishuEnv.hasAppId ?? false) || (feishuEnv.hasAppSecret ?? false));
  const partialMissing: string[] = [];
  if (partial && feishuEnv) {
    if (!(feishuEnv.hasAppId ?? false)) partialMissing.push("FEISHU_APP_ID");
    if (!(feishuEnv.hasAppSecret ?? false)) partialMissing.push("FEISHU_APP_SECRET");
  }

  return (
    <div className={cn("w-full min-w-0 space-y-3", className)}>
      {feishuEnv?.configured ? (
        <StatusBanner variant="success" title={t("settings.feishuAlreadyTitle")}>
          <p>{t("settings.feishuAlreadyLead")}</p>
          {feishuEnv.appIdHint ? (
            <p className="mt-1 font-mono">{t("settings.feishuAppIdHint", { hint: feishuEnv.appIdHint })}</p>
          ) : null}
          {view?.result?.bot_name ? (
            <p className="mt-1">{t("settings.feishuBotName", { name: view.result.bot_name })}</p>
          ) : null}
        </StatusBanner>
      ) : null}
      {partial && feishuEnv ? (
        <StatusBanner variant="warning" title={t("settings.feishuPartialTitle")}>
          {t("settings.feishuPartialLead", { missing: partialMissing.join("、") })}
        </StatusBanner>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <PlatformButton onClick={() => void startFeishuQr()} disabled={polling}>
          {feishuEnv?.configured ? t("settings.feishuRescan") : t("settings.feishuStart")}
        </PlatformButton>
        {feishuEnv?.configured ? (
          <PlatformButton variant="danger" onClick={() => void handleRemove()} disabled={removing}>
            {removing ? "…" : t("settings.removePlatformConfig")}
          </PlatformButton>
        ) : null}
        <PlatformButton onClick={() => void cancelFeishuQr()} disabled={!polling}>
          {t("settings.feishuCancel")}
        </PlatformButton>
      </div>
      {inlineErr ? (
        <StatusBanner variant="error" title={inlineErr} />
      ) : null}
      {view?.progress?.phase ? (
        <p className="text-sm text-[var(--kq-color-ink)]">{phaseLabel(view.progress.phase)}</p>
      ) : null}
      {view?.progress?.qr_url ? (
        <div className="space-y-1">
          <a
            href={view.progress.qr_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block max-w-full break-all text-sm font-medium text-[var(--kq-color-strong)] underline-offset-2 hover:underline dark:text-[var(--kq-color-primary-light)]"
          >
            {t("settings.feishuOpenLink")}
          </a>
          <p className="break-all font-mono text-xs text-[var(--kq-color-muted)]">
            {view.progress.qr_url}
          </p>
          <p className="text-xs leading-relaxed text-[var(--kq-color-muted)]">{t("settings.feishuAfterScanHint")}</p>
        </div>
      ) : null}
      {view?.progress?.message ? (
        <p className="text-sm text-red-600 dark:text-red-400">{view.progress.message}</p>
      ) : null}
      {view?.result?.ok === true ? (
        <div className="space-y-2 text-sm text-[var(--kq-color-ink)]">
          <p>{restarted ? t("settings.feishuSuccessDone") : t("settings.feishuSuccess")}</p>
          {view.result.app_id ? (
            <p className="font-mono text-xs text-zinc-500">App ID: {view.result.app_id}</p>
          ) : null}
          {!restarted ? (
            <PlatformButton
              disabled={restartBusy}
              onClick={() => void manualRestartAssistant()}
            >
              {restartBusy ? t("settings.feishuRestartBusy") : t("settings.feishuRestart")}
            </PlatformButton>
          ) : null}
          {restartErr ? <StatusBanner variant="error" title={restartErr} /> : null}
        </div>
      ) : null}
      {view?.result && view.result.ok === false ? (
        <StatusBanner variant="error" title={t("settings.feishuError", { msg: view.result.error ?? "unknown" })} />
      ) : null}
    </div>
  );
}
