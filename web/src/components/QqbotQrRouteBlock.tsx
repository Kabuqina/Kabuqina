// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { confirm } from "../lib/confirmDialog";
import { useI18n } from "../lib/i18n";
import { cn } from "../lib/cn";
import { StatusBanner } from "./ui/StatusBanner";
import { PlatformButton } from "./ui/PlatformButton";

export type QqbotQrProgress = {
  phase?: string;
  qr_url?: string | null;
  message?: string | null;
};

export type QqbotQrResult = {
  ok?: boolean;
  app_id?: string;
  user_openid?: string | null;
  error?: string;
};

export type QqbotQrStatusPayload = {
  running: boolean;
  progress: QqbotQrProgress | null;
  result: QqbotQrResult | null;
};

export type QqEnvSnapshot = {
  configured: boolean;
  hasAppId?: boolean;
  hasClientSecret?: boolean;
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

export function QqbotQrRouteBlock({ className, onSuccess, onHermesRunningChange }: Props) {
  const { t } = useI18n();
  const [qqEnv, setQqEnv] = useState<QqEnvSnapshot | null>(null);
  const [qqPolling, setQqPolling] = useState(false);
  const [qqView, setQqView] = useState<QqbotQrStatusPayload | null>(null);
  const [qqRestarted, setQqRestarted] = useState(false);
  const [qqInlineErr, setQqInlineErr] = useState<string | null>(null);
  const [restartBusy, setRestartBusy] = useState(false);
  const [restartErr, setRestartErr] = useState<string | null>(null);
  const [removing, setRemoving] = useState(false);
  const qqExitStreak = useRef(0);
  const onSuccessRef = useRef(onSuccess);
  onSuccessRef.current = onSuccess;
  const onHermesRef = useRef(onHermesRunningChange);
  onHermesRef.current = onHermesRunningChange;

  const refreshQqEnv = useCallback(async () => {
    try {
      const snap = await invoke<QqEnvSnapshot>("cmd_qq_env_status");
      setQqEnv(snap);
    } catch {
      setQqEnv(null);
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
    try { await invoke("cmd_qq_env_remove"); void refreshQqEnv(); }
    catch { void refreshQqEnv(); }
    finally { setRemoving(false); }
  }

  useEffect(() => {
    void refreshQqEnv();
  }, [refreshQqEnv]);

  useEffect(() => {
    if (!qqPolling) return;
    let cancelled = false;

    const tick = async () => {
      try {
        const s = await invoke<QqbotQrStatusPayload>("cmd_qqbot_qr_status");
        if (cancelled) return;
        setQqView(s);
        if (s.running) {
          qqExitStreak.current = 0;
          return;
        }
        const r = s.result;
        if (r && typeof r.ok === "boolean") {
          qqExitStreak.current = 0;
          setQqPolling(false);
          if (r.ok) {
            if (r.app_id) {
              onSuccessRef.current?.({ appId: String(r.app_id) });
            }
            setRestartErr(null);
            try {
              await invoke<number>("cmd_restart_embedded_hermes");
              if (!cancelled) {
                setQqRestarted(true);
                const pyStat = await invoke<{ running: boolean }>("cmd_python_status");
                onHermesRef.current?.(pyStat.running);
                void refreshQqEnv();
              }
            } catch (e) {
              console.error(e);
              if (!cancelled) {
                setQqRestarted(false);
                setRestartErr(t("settings.qqRestartFailed", { msg: ipcErr(e) }));
              }
            }
          }
          return;
        }
        qqExitStreak.current += 1;
        if (qqExitStreak.current >= 30) {
          setQqPolling(false);
          setQqInlineErr(
            t("settings.qqError", { msg: "process exited without result file" })
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
  }, [qqPolling, t, refreshQqEnv]);

  const qqPhaseLabel = useCallback(
    (phase: string | undefined) => {
      switch (phase) {
        case "starting":
          return t("settings.qqPhaseStarting");
        case "connecting":
          return t("settings.qqPhaseConnecting");
        case "waiting_scan":
          return t("settings.qqPhaseWaiting");
        case "scanned":
          return t("settings.qqPhaseScanned");
        case "done":
          return t("settings.qqPhaseDone");
        case "error":
          return t("settings.qqPhaseError");
        default:
          return phase ?? "…";
      }
    },
    [t]
  );

  async function startQqbotQr() {
    setQqInlineErr(null);
    setRestartErr(null);
    setQqRestarted(false);
    setQqView(null);
    qqExitStreak.current = 0;
    try {
      await invoke("cmd_qqbot_qr_start");
      setQqPolling(true);
    } catch (e) {
      const raw = e instanceof Error ? e.message : String(e);
      setQqInlineErr(
        raw.includes("qqbot_qr_worker.py")
          ? t("settings.qqWorkerMissing")
          : t("settings.qqError", { msg: raw })
      );
    }
  }

  async function cancelQqbotQr() {
    try {
      await invoke("cmd_qqbot_qr_cancel");
    } catch (e) {
      console.error(e);
    }
    setQqPolling(false);
    qqExitStreak.current = 0;
  }

  async function manualRestartAssistant() {
    setRestartErr(null);
    setRestartBusy(true);
    try {
      await invoke<number>("cmd_restart_embedded_hermes");
      setQqRestarted(true);
      const pyStat = await invoke<{ running: boolean }>("cmd_python_status");
      onHermesRunningChange?.(pyStat.running);
      void refreshQqEnv();
    } catch (e) {
      console.error(e);
      setRestartErr(t("settings.qqRestartFailed", { msg: ipcErr(e) }));
    } finally {
      setRestartBusy(false);
    }
  }

  const qqPartial =
    qqEnv &&
    !qqEnv.configured &&
    ((qqEnv.hasAppId ?? false) || (qqEnv.hasClientSecret ?? false));
  const qqPartialMissing: string[] = [];
  if (qqPartial && qqEnv) {
    if (!(qqEnv.hasAppId ?? false)) qqPartialMissing.push("QQ_APP_ID");
    if (!(qqEnv.hasClientSecret ?? false)) qqPartialMissing.push("QQ_CLIENT_SECRET");
  }

  return (
    <div className={cn("w-full min-w-0 space-y-3", className)}>
      {qqEnv?.configured ? (
        <StatusBanner variant="success" title={t("settings.qqAlreadyTitle")}>
          <p>{t("settings.qqAlreadyLead")}</p>
          {qqEnv.appIdHint ? (
            <p className="mt-1 font-mono">{t("settings.qqAppIdHint", { hint: qqEnv.appIdHint })}</p>
          ) : null}
        </StatusBanner>
      ) : null}
      {qqPartial && qqEnv ? (
        <StatusBanner variant="warning" title={t("settings.qqPartialTitle")}>
          {t("settings.qqPartialLead", { missing: qqPartialMissing.join("、") })}
        </StatusBanner>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <PlatformButton onClick={() => void startQqbotQr()} disabled={qqPolling}>
          {qqEnv?.configured ? t("settings.qqRescan") : t("settings.qqStart")}
        </PlatformButton>
        {qqEnv?.configured ? (
          <PlatformButton variant="danger" onClick={() => void handleRemove()} disabled={removing}>
            {removing ? "…" : t("settings.removePlatformConfig")}
          </PlatformButton>
        ) : null}
        <PlatformButton onClick={() => void cancelQqbotQr()} disabled={!qqPolling}>
          {t("settings.qqCancel")}
        </PlatformButton>
      </div>
      {qqInlineErr ? (
        <StatusBanner variant="error" title={qqInlineErr} />
      ) : null}
      {qqView?.progress?.phase ? (
        <p className="text-sm text-zinc-600 dark:text-zinc-300">{qqPhaseLabel(qqView.progress.phase)}</p>
      ) : null}
      {qqView?.progress?.qr_url ? (
        <div className="space-y-1">
          <a
            href={qqView.progress.qr_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block max-w-full break-all text-sm font-medium text-[var(--kq-color-strong)] underline-offset-2 hover:underline dark:text-[#D4C5E2]"
          >
            {t("settings.qqOpenLink")}
          </a>
          <p className="break-all font-mono text-xs text-zinc-500 dark:text-zinc-500">
            {qqView.progress.qr_url}
          </p>
          <p className="text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">{t("settings.qqAfterScanHint")}</p>
        </div>
      ) : null}
      {qqView?.progress?.message ? (
        <p className="text-sm text-red-600 dark:text-red-400">{qqView.progress.message}</p>
      ) : null}
      {qqView?.result?.ok === true ? (
        <div className="space-y-2 text-sm text-zinc-600 dark:text-zinc-300">
          <p>{qqRestarted ? t("settings.qqSuccessDone") : t("settings.qqSuccess")}</p>
          {qqView.result.app_id ? (
            <p className="font-mono text-xs text-zinc-500">App ID: {qqView.result.app_id}</p>
          ) : null}
          {!qqRestarted ? (
            <PlatformButton
              disabled={restartBusy}
              onClick={() => void manualRestartAssistant()}
            >
              {restartBusy ? t("settings.qqRestartBusy") : t("settings.qqRestart")}
            </PlatformButton>
          ) : null}
          {restartErr ? <StatusBanner variant="error" title={restartErr} /> : null}
        </div>
      ) : null}
      {qqView?.result && qqView.result.ok === false ? (
        <StatusBanner variant="error" title={t("settings.qqError", { msg: qqView.result.error ?? "unknown" })} />
      ) : null}
    </div>
  );
}
