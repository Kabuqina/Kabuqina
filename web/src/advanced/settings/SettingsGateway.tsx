// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useNavigate } from "react-router-dom";
import { useI18n } from "../../lib/i18n";
import {
  Bot,
  Building2,
  ChevronRight,
  Mail,
  MessageCircle,
  QrCode,
  Send,
} from "lucide-react";
import { Button } from "../../components/ui/Button";
import { Section } from "../../components/ui/Section";
import { Toggle } from "../../components/ui/Toggle";
import type { Status } from "../Settings";
import type { GatewayStatus } from "../../features/gateway/useGatewayStatus";

interface Props {
  gatewayStatus: GatewayStatus;
  autoStartGateway: boolean;
  onToggleAutoStart: (next: boolean) => void;
  onStatusChange: (status: Status | null) => void;
  status: Status | null;
}

function platformLabel(key: string): string {
  const map: Record<string, string> = {
    telegram: "Telegram",
    feishu: "飞书",
    qqbot: "QQ",
    weixin: "微信",
    wecom: "企微",
  };
  return map[key] ?? key;
}

const platformItems = [
  { key: "telegram", label: "Telegram", icon: Send, path: "/settings/telegram" },
  { key: "feishu", label: "飞书", icon: Building2, path: "/settings/feishu" },
  { key: "qq", label: "QQ", icon: Bot, path: "/settings/qq" },
  { key: "weixin", label: "微信", icon: QrCode, path: "/settings/weixin" },
  { key: "wecom", label: "企微", icon: Building2, path: "/settings/wecom" },
  { key: "email", label: "Email", icon: Mail, path: "/settings/email" },
];

export function SettingsGateway({
  gatewayStatus,
  autoStartGateway,
  onToggleAutoStart,
}: Props) {
  const { t } = useI18n();
  const nav = useNavigate();
  const {
    running: gatewayRunning,
    eligible: gatewayEligible,
    diskState: gatewayDiskState,
    diskExit: gatewayDiskExit,
    embedSurvival: gatewayEmbedSurvival,
    startError: gatewayStartError,
    starting: gatewayStarting,
    platforms: gatewayPlatforms,
    start: startGateway,
    stop: stopGateway,
  } = gatewayStatus;

  return (
    <>
      <Section icon={MessageCircle} title={t("settings.gatewayTitle")} desc={t("settings.gatewayLead")}>
        <div className="w-full min-w-0 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-zinc-700 dark:text-zinc-200">{t("settings.gatewayAuto")}</span>
            <Toggle value={autoStartGateway} onChange={(v) => onToggleAutoStart(v)} />
          </div>
          {!gatewayEligible ? (
            <p className="text-xs leading-relaxed text-amber-700/90 dark:text-amber-400/90">
              {t("settings.gatewayNotEligible")}
            </p>
          ) : null}
          {gatewayEligible && !gatewayEmbedSurvival ? (
            <p className="text-xs leading-relaxed text-amber-800/95 dark:text-amber-300/95">
              {t("settings.gatewayEmbedStale")}
            </p>
          ) : null}
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm text-zinc-600 dark:text-zinc-300">
              {gatewayStarting
                ? t("settings.gatewayStatusChecking")
                : gatewayRunning
                  ? t("settings.gatewayStatusRunning")
                  : t("settings.gatewayStatusStopped")}
            </span>
            <div className="flex shrink-0 gap-2">
              <Button
                type="button"
                variant="primary"
                onClick={() => void startGateway()}
                disabled={!gatewayEligible || gatewayStarting}
              >
                {gatewayStarting ? t("settings.gatewayStarting") : t("settings.gatewayStart")}
              </Button>
              <Button type="button" variant="secondary" onClick={() => void stopGateway()} disabled={gatewayStarting}>
                {t("settings.gatewayStop")}
              </Button>
            </div>
          </div>
          {gatewayEligible && gatewayStarting && gatewayPlatforms ? (
            <div className="rounded-[var(--radius-shell-lg)] border border-zinc-200/90 bg-zinc-50/80 px-3 py-2 text-xs dark:border-zinc-700 dark:bg-zinc-900/40">
              <p className="font-medium text-zinc-700 dark:text-zinc-200 mb-1.5">{t("settings.gatewayStartingHint")}</p>
              {Object.entries(gatewayPlatforms).map(([key, p]) => (
                <p key={key} className="flex items-center gap-1.5 mt-0.5 font-mono text-[0.7rem]">
                  <span className={
                    p.state === "connected" ? "text-emerald-600 dark:text-emerald-400" :
                    p.state === "retrying" ? "text-amber-600 dark:text-amber-400" :
                    p.state === "fatal" ? "text-red-600 dark:text-red-400" :
                    "text-zinc-500 dark:text-zinc-400"
                  }>
                    {p.state === "connected" ? "●" : p.state === "retrying" ? "◐" : p.state === "fatal" ? "✕" : "○"}
                  </span>
                  <span className="text-zinc-600 dark:text-zinc-300">{platformLabel(key)}</span>
                  <span className="text-zinc-500 dark:text-zinc-500">
                    {p.state === "connected" ? t("settings.gatewayPlatformConnected") :
                     p.state === "retrying" ? t("settings.gatewayPlatformRetrying") :
                     p.state === "fatal" ? p.error_message ?? t("settings.gatewayPlatformError") :
                     t("settings.gatewayPlatformConnecting")}
                  </span>
                </p>
              ))}
            </div>
          ) : null}
          {gatewayEligible && gatewayStarting && !gatewayPlatforms ? (
            <p className="text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
              {t("settings.gatewayStartingHint")}
            </p>
          ) : null}
          {gatewayStartError ? (
            <p className="text-xs leading-relaxed text-red-700 dark:text-red-400">
              {t("settings.gatewayStartFailed", { msg: gatewayStartError })}
            </p>
          ) : null}
          {gatewayDiskState || gatewayDiskExit ? (
            <div className="rounded-[var(--radius-shell-lg)] border border-zinc-200/90 bg-zinc-50/80 px-3 py-2 text-xs dark:border-zinc-700 dark:bg-zinc-900/40">
              <p className="font-medium text-zinc-700 dark:text-zinc-200">{t("settings.gatewayDiskRecord")}</p>
              {gatewayDiskState ? (
                <p className="mt-1 font-mono text-[0.7rem] text-zinc-600 dark:text-zinc-300">
                  {t("settings.gatewayStateLine", { state: gatewayDiskState })}
                </p>
              ) : null}
              {gatewayDiskExit ? (
                <p className="mt-1 font-mono text-[0.7rem] text-zinc-600 dark:text-zinc-300">
                  {t("settings.gatewayExitLine", { detail: gatewayDiskExit })}
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
      </Section>

      <Section title={t("settings.platformTitle")}>
        <div className="space-y-1">
          {platformItems.map(({ key, label, icon: Icon, path }) => (
            <button
              key={key}
              type="button"
              onClick={() => nav(path)}
              className="gateway-platform-nav kq-btn-secondary flex w-full items-center gap-3 rounded-[var(--radius-shell-lg)] px-3 py-2.5 text-left active:scale-[0.99] dark:text-zinc-100"
            >
              <Icon className="size-4 shrink-0 text-[var(--kq-color-strong)] dark:text-[#D4C5E2]" />
              <span className="flex-1 text-sm font-medium">{label}</span>
              <ChevronRight className="size-4 shrink-0 text-[var(--kq-color-primary)] dark:text-[#D4C5E2]" />
            </button>
          ))}
        </div>
      </Section>
    </>
  );
}
