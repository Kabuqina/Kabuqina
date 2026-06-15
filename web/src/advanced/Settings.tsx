// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useState, type ComponentType } from "react";
import { useNavigate } from "react-router-dom";
import { invoke } from "@tauri-apps/api/core";
import { Cpu, Server, SlidersHorizontal, Wrench } from "lucide-react";
import { AppScaffold } from "../components/AppScaffold";
import { BackButton } from "../components/ui/BackButton";
import { useI18n } from "../lib/i18n";
import { cn } from "../lib/cn";
import { useTogglePowerUser } from "../lib/useTogglePowerUser";
import { useFontSize, useThemeMode } from "../lib/ui-prefs";
import { useGatewayStatus } from "../features/gateway/useGatewayStatus";
import { SettingsGateway } from "./settings/SettingsGateway";
import { SettingsDisplay } from "./settings/SettingsDisplay";
import { SettingsSharedPrefs } from "./settings/SettingsSharedPrefs";
import { SettingsLoadPackages } from "./settings/SettingsLoadPackages";
import { SettingsLlmConfig } from "./settings/SettingsLlmConfig";

export interface Status {
  workspace: string;
  hasSecret: boolean;
  pythonRunning: boolean;
}

type SettingsTab = "general" | "model" | "gateway" | "advanced";

export function Settings() {
  const { t } = useI18n();
  const nav = useNavigate();
  const [tab, setTab] = useState<SettingsTab>("general");
  const [status, setStatus] = useState<Status | null>(null);
  const { powerUser, togglePowerUser } = useTogglePowerUser();
  const { size: fontSize, setSize: setFontSize } = useFontSize();
  const { mode: themeMode, setMode: setThemeMode } = useThemeMode();
  const gatewayStatus = useGatewayStatus();

  const refreshStatus = useCallback(async () => {
    const [workspace, hasSecret, pyStat] = await Promise.all([
      invoke<string>("cmd_workspace_path"),
      invoke<boolean>("cmd_has_secret"),
      invoke<{ running: boolean }>("cmd_python_status"),
    ]);
    setStatus({ workspace, hasSecret, pythonRunning: pyStat.running });
  }, []);

  useEffect(() => {
    void refreshStatus().catch(console.error);
  }, [refreshStatus]);

  const tabs: Array<{ id: SettingsTab; label: string; icon: ComponentType<{ className?: string }> }> = [
    { id: "general", label: t("settings.tabGeneral"), icon: SlidersHorizontal },
    { id: "model", label: t("settings.tabModel"), icon: Cpu },
    { id: "gateway", label: t("settings.tabGateway"), icon: Server },
    { id: "advanced", label: t("settings.tabAdvanced"), icon: Wrench },
  ];

  const statusDots: Array<{ key: string; on: boolean; label: string }> = [
    { key: "py", on: !!status?.pythonRunning, label: t("settings.pyRunning") },
    { key: "secret", on: !!status?.hasSecret, label: t("settings.hasPass") },
    { key: "gateway", on: gatewayStatus.running, label: t("settings.gatewayShort") },
  ];

  return (
    <AppScaffold className="h-full overflow-y-auto">
      <div className="mx-auto max-w-2xl space-y-5 px-[var(--hd-page-pad-x)] py-8 sm:py-10">
        <div>
          <BackButton onClick={() => nav("/chat")}>
            {t("settings.back")}
          </BackButton>
          <h1 className="hd-page-title">{t("settings.title")}</h1>
          {t("settings.pageLead") && (
            <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-[var(--kq-color-muted)]">
              {t("settings.pageLead")}
            </p>
          )}
        </div>

        {/* Compact health strip — relevant on every tab, so it stays above the tabs. */}
        <div className="hd-glass-subtle flex flex-wrap gap-x-5 gap-y-2 px-4 py-3 text-sm text-[var(--kq-color-ink)]">
          {statusDots.map((dot) => (
            <div key={dot.key} className="flex items-center gap-2">
              <span className={cn("inline-block h-2 w-2 rounded-full", dot.on ? "bg-emerald-500" : "bg-zinc-300 dark:bg-zinc-600")} />
              <span>{dot.label}</span>
              <span className="font-medium text-[var(--kq-color-strong)]">
                {dot.on ? t("settings.yes") : t("settings.no")}
              </span>
            </div>
          ))}
        </div>

        {/* Category tabs keep each view short instead of one long scroll. */}
        <div
          role="tablist"
          className="inline-flex w-full rounded-[var(--radius-shell-lg)] border border-[var(--kq-color-border)] bg-[var(--kq-color-primary-pale)]/45 p-0.5 dark:border-zinc-700 dark:bg-zinc-800/50"
        >
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              onClick={() => setTab(id)}
              className={cn(
                "flex min-h-[2.25rem] flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-sm font-medium transition",
                "active:scale-[0.98]",
                tab === id ? "hd-btn-segment-active shadow-sm" : "hd-btn-segment-idle",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </div>

        <div className="space-y-5">
          {tab === "general" && (
            <SettingsDisplay
              status={status}
              powerUser={powerUser}
              onTogglePowerUser={togglePowerUser}
              fontSize={fontSize}
              onSetFontSize={setFontSize}
              themeMode={themeMode}
              onSetThemeMode={setThemeMode}
              onWorkspaceChanged={refreshStatus}
            />
          )}

          {tab === "model" && <SettingsLlmConfig />}

          {tab === "gateway" && (
            <SettingsGateway
              gatewayStatus={gatewayStatus}
              onStatusChange={setStatus}
              status={status}
            />
          )}

          {tab === "advanced" && (
            <>
              <SettingsLoadPackages />
              <SettingsSharedPrefs />
            </>
          )}
        </div>
      </div>
    </AppScaffold>
  );
}
