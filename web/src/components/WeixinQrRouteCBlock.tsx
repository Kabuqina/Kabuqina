// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { confirm } from "../lib/confirmDialog";
import { useI18n } from "../lib/i18n";
import { cn } from "../lib/cn";
import { StatusBanner } from "./ui/StatusBanner";
import { PlatformButton } from "./ui/PlatformButton";

export type WeixinQrProgress = {
  phase?: string;
  liteapp_url?: string | null;
  message?: string | null;
};

export type WeixinQrResult = {
  ok?: boolean;
  account_id?: string;
  user_id?: string | null;
  error?: string;
};

export type WeixinQrStatusPayload = {
  running: boolean;
  progress: WeixinQrProgress | null;
  result: WeixinQrResult | null;
};

export type WeixinEnvSnapshot = {
  configured: boolean;
  /** Non-empty ``WEIXIN_ACCOUNT_ID`` in kabuqina-home/.env */
  hasAccountId?: boolean;
  /** Non-empty ``WEIXIN_TOKEN`` in kabuqina-home/.env */
  hasToken?: boolean;
  accountIdHint?: string | null;
};

type Props = {
  className?: string;
  /** After credentials are written to `.env` (restart may still be in progress). */
  onSuccess?: (payload: { accountId: string }) => void;
  /** When embedded Hermes restarts successfully, report new running flag. */
  onHermesRunningChange?: (running: boolean) => void;
};

function ipcErr(e: unknown): string {
  if (typeof e === "string") return e;
  if (e && typeof e === "object" && "message" in e) return String((e as Error).message);
  return String(e);
}

export function WeixinQrRouteCBlock({ className, onSuccess, onHermesRunningChange }: Props) {
  const { t } = useI18n();
  const [weixinEnv, setWeixinEnv] = useState<WeixinEnvSnapshot | null>(null);
  const [weixinPolling, setWeixinPolling] = useState(false);
  const [weixinView, setWeixinView] = useState<WeixinQrStatusPayload | null>(null);
  const [weixinRestarted, setWeixinRestarted] = useState(false);
  const [weixinInlineErr, setWeixinInlineErr] = useState<string | null>(null);
  const [restartBusy, setRestartBusy] = useState(false);
  const [restartErr, setRestartErr] = useState<string | null>(null);
  const [removing, setRemoving] = useState(false);
  const weixinExitStreak = useRef(0);
  const onSuccessRef = useRef(onSuccess);
  onSuccessRef.current = onSuccess;
  const onHermesRef = useRef(onHermesRunningChange);
  onHermesRef.current = onHermesRunningChange;

  const refreshWeixinEnv = useCallback(async () => {
    try {
      const snap = await invoke<WeixinEnvSnapshot>("cmd_weixin_env_status");
      setWeixinEnv(snap);
    } catch {
      setWeixinEnv(null);
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
    try { await invoke("cmd_weixin_env_remove"); void refreshWeixinEnv(); }
    catch { void refreshWeixinEnv(); }
    finally { setRemoving(false); }
  }

  useEffect(() => {
    void refreshWeixinEnv();
  }, [refreshWeixinEnv]);

  useEffect(() => {
    if (!weixinPolling) return;
    let cancelled = false;

    const tick = async () => {
      try {
        const s = await invoke<WeixinQrStatusPayload>("cmd_weixin_qr_status");
        if (cancelled) return;
        setWeixinView(s);
        if (s.running) {
          weixinExitStreak.current = 0;
          return;
        }
        const r = s.result;
        if (r && typeof r.ok === "boolean") {
          weixinExitStreak.current = 0;
          setWeixinPolling(false);
          if (r.ok) {
            if (r.account_id) {
              onSuccessRef.current?.({ accountId: String(r.account_id) });
            }
            setRestartErr(null);
            try {
              await invoke<number>("cmd_restart_embedded_hermes");
              if (!cancelled) {
                setWeixinRestarted(true);
                const pyStat = await invoke<{ running: boolean }>("cmd_python_status");
                onHermesRef.current?.(pyStat.running);
                void refreshWeixinEnv();
              }
            } catch (e) {
              console.error(e);
              if (!cancelled) {
                setWeixinRestarted(false);
                setRestartErr(t("settings.weixinRestartFailed", { msg: ipcErr(e) }));
              }
            }
          }
          return;
        }
        weixinExitStreak.current += 1;
        if (weixinExitStreak.current >= 8) {
          setWeixinPolling(false);
          setWeixinInlineErr(
            t("settings.weixinError", { msg: "process exited without result file" })
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
  }, [weixinPolling, t, refreshWeixinEnv]);

  const weixinPhaseLabel = useCallback(
    (phase: string | undefined) => {
      switch (phase) {
        case "starting":
          return t("settings.weixinPhaseStarting");
        case "connecting":
          return t("settings.weixinPhaseConnecting");
        case "waiting_scan":
          return t("settings.weixinPhaseWaiting");
        case "done":
          return t("settings.weixinPhaseDone");
        case "error":
          return t("settings.weixinPhaseError");
        default:
          return phase ?? "…";
      }
    },
    [t]
  );

  async function startWeixinQr() {
    setWeixinInlineErr(null);
    setRestartErr(null);
    setWeixinRestarted(false);
    setWeixinView(null);
    weixinExitStreak.current = 0;
    try {
      await invoke("cmd_weixin_qr_start");
      setWeixinPolling(true);
    } catch (e) {
      const raw = e instanceof Error ? e.message : String(e);
      setWeixinInlineErr(
        raw.includes("weixin_qr_worker.py")
          ? t("settings.weixinWorkerMissing")
          : t("settings.weixinError", { msg: raw })
      );
    }
  }

  async function cancelWeixinQr() {
    try {
      await invoke("cmd_weixin_qr_cancel");
    } catch (e) {
      console.error(e);
    }
    setWeixinPolling(false);
    weixinExitStreak.current = 0;
  }

  async function manualRestartAssistant() {
    setRestartErr(null);
    setRestartBusy(true);
    try {
      await invoke<number>("cmd_restart_embedded_hermes");
      setWeixinRestarted(true);
      const pyStat = await invoke<{ running: boolean }>("cmd_python_status");
      onHermesRunningChange?.(pyStat.running);
      void refreshWeixinEnv();
    } catch (e) {
      console.error(e);
      setRestartErr(t("settings.weixinRestartFailed", { msg: ipcErr(e) }));
    } finally {
      setRestartBusy(false);
    }
  }

  const weixinPartial =
    weixinEnv &&
    !weixinEnv.configured &&
    ((weixinEnv.hasAccountId ?? false) || (weixinEnv.hasToken ?? false));
  const weixinPartialMissing: string[] = [];
  if (weixinPartial && weixinEnv) {
    if (!(weixinEnv.hasAccountId ?? false)) weixinPartialMissing.push("WEIXIN_ACCOUNT_ID");
    if (!(weixinEnv.hasToken ?? false)) weixinPartialMissing.push("WEIXIN_TOKEN");
  }

  return (
    <div className={cn("w-full min-w-0 space-y-3", className)}>
      {weixinEnv?.configured ? (
        <StatusBanner variant="success" title={t("settings.weixinAlreadyTitle")}>
          <p>{t("settings.weixinAlreadyLead")}</p>
          {weixinEnv.accountIdHint ? (
            <p className="mt-1 font-mono">{t("settings.weixinAccountHint", { hint: weixinEnv.accountIdHint })}</p>
          ) : null}
        </StatusBanner>
      ) : null}
      {weixinPartial && weixinEnv ? (
        <StatusBanner variant="warning" title={t("settings.weixinPartialTitle")}>
          {t("settings.weixinPartialLead", { missing: weixinPartialMissing.join("、") })}
        </StatusBanner>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <PlatformButton onClick={() => void startWeixinQr()} disabled={weixinPolling}>
          {weixinEnv?.configured ? t("settings.weixinRescan") : t("settings.weixinStart")}
        </PlatformButton>
        {weixinEnv?.configured ? (
          <PlatformButton variant="danger" onClick={() => void handleRemove()} disabled={removing}>
            {removing ? "…" : t("settings.removePlatformConfig")}
          </PlatformButton>
        ) : null}
        <PlatformButton onClick={() => void cancelWeixinQr()} disabled={!weixinPolling}>
          {t("settings.weixinCancel")}
        </PlatformButton>
      </div>
      {weixinInlineErr ? (
        <StatusBanner variant="error" title={weixinInlineErr} />
      ) : null}
      {weixinView?.progress?.phase ? (
        <p className="text-sm text-[var(--kq-color-ink)]">{weixinPhaseLabel(weixinView.progress.phase)}</p>
      ) : null}
      {weixinView?.progress?.liteapp_url ? (
        <div className="space-y-1">
          <a
            href={weixinView.progress.liteapp_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block max-w-full break-all text-sm font-medium text-[var(--kq-color-strong)] underline-offset-2 hover:underline dark:text-[var(--kq-color-primary-light)]"
          >
            {t("settings.weixinOpenLink")}
          </a>
          <p className="break-all font-mono text-xs text-[var(--kq-color-muted)]">
            {weixinView.progress.liteapp_url}
          </p>
          <p className="text-xs leading-relaxed text-[var(--kq-color-muted)]">{t("settings.weixinAfterScanHint")}</p>
        </div>
      ) : null}
      {weixinView?.progress?.message ? (
        <p className="text-sm text-red-600 dark:text-red-400">{weixinView.progress.message}</p>
      ) : null}
      {weixinView?.result?.ok === true ? (
        <div className="space-y-2 text-sm text-[var(--kq-color-ink)]">
          <p>{weixinRestarted ? t("settings.weixinSuccessDone") : t("settings.weixinSuccess")}</p>
          {weixinView.result.account_id ? (
            <p className="font-mono text-xs text-zinc-500">account_id: {weixinView.result.account_id}</p>
          ) : null}
          {!weixinRestarted ? (
            <PlatformButton
              disabled={restartBusy}
              onClick={() => void manualRestartAssistant()}
            >
              {restartBusy ? t("settings.weixinRestartBusy") : t("settings.weixinRestart")}
            </PlatformButton>
          ) : null}
          {restartErr ? <p className="text-sm text-red-600 dark:text-red-400">{restartErr}</p> : null}
        </div>
      ) : null}
      {weixinView?.result && weixinView.result.ok === false ? (
        <p className="text-sm text-red-600 dark:text-red-400">
          {t("settings.weixinError", { msg: weixinView.result.error ?? "unknown" })}
        </p>
      ) : null}
    </div>
  );
}
