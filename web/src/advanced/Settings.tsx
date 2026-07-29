// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useState, type ComponentType } from "react";
import { useLocation } from "react-router-dom";
import { invoke } from "@tauri-apps/api/core";
import { BookOpen, Cpu, SlidersHorizontal, Wrench } from "lucide-react";
import { AppScaffold } from "../components/AppScaffold";
import { useI18n } from "../lib/i18n";
import { cn } from "../lib/cn";
import { useFontSize, useThemeMode } from "../lib/ui-prefs";
import { SettingsDisplay } from "./settings/SettingsDisplay";
import { SettingsLearningData, SettingsLearningMigrations } from "./settings/SettingsLearningData";
import { SettingsMaterialPrivacy } from "./settings/SettingsMaterialPrivacy";
import { SettingsImportReadMode, SettingsReviewLimits } from "./settings/SettingsStudyPreferences";
import { SettingsStudyImprovementCounts } from "./settings/SettingsStudyImprovementCounts";
import { SettingsSharedPrefs } from "./settings/SettingsSharedPrefs";
import { SettingsLoadPackages } from "./settings/SettingsLoadPackages";
import { SettingsLlmConfig } from "./settings/SettingsLlmConfig";
import { SettingsTokenUsage } from "./settings/SettingsTokenUsage";
import { SettingsUpdate } from "./settings/SettingsUpdate";
import { SettingsLegacyChannels } from "./settings/SettingsLegacyChannels";

export interface Status {
  workspace: string;
  hasSecret: boolean;
  pythonRunning: boolean;
}

type SettingsTab = "general" | "study" | "model" | "advanced";

function isSettingsTab(value: unknown): value is SettingsTab {
  return value === "general" || value === "study" || value === "model" || value === "advanced";
}

export function Settings() {
  const { t } = useI18n();
  const location = useLocation();
  // Allow deep-linking to a specific tab (e.g. chat's "configure model" prompt
  // routes straight to the model config tab).
  const initialTab: SettingsTab = isSettingsTab(
    (location.state as { settingsTab?: unknown } | null)?.settingsTab
  )
    ? ((location.state as { settingsTab: SettingsTab }).settingsTab)
    : "general";
  const [tab, setTab] = useState<SettingsTab>(initialTab);
  const [status, setStatus] = useState<Status | null>(null);
  const { size: fontSize, setSize: setFontSize } = useFontSize();
  const { mode: themeMode, setMode: setThemeMode } = useThemeMode();

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
    { id: "study", label: t("settings.tabStudy"), icon: BookOpen },
    { id: "model", label: t("settings.tabModel"), icon: Cpu },
    { id: "advanced", label: t("settings.tabAdvanced"), icon: Wrench },
  ];

  const statusDots: Array<{ key: string; on: boolean; label: string }> = [
    { key: "py", on: !!status?.pythonRunning, label: t("settings.pyRunning") },
    { key: "secret", on: !!status?.hasSecret, label: t("settings.hasPass") },
  ];

  return (
    <AppScaffold surface="chat" className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-2xl space-y-5 px-[var(--hd-page-pad-x)] py-7 sm:py-9">
        {t("settings.pageLead") && (
          <p className="max-w-xl text-sm leading-relaxed text-[var(--kq-color-muted)]">
            {t("settings.pageLead")}
          </p>
        )}

        {/* Compact health strip — relevant on every tab, so it stays above the tabs. */}
        <div className="hd-setting-card flex flex-wrap gap-x-5 gap-y-2 px-4 py-3 text-sm text-[var(--kq-color-ink)]">
          {statusDots.map((dot) => (
            <div key={dot.key} className="flex items-center gap-2">
              <span className={cn("inline-block h-2 w-2 rounded-full", dot.on ? "bg-emerald-500" : "bg-[var(--kq-color-primary)]/35")} />
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
          className="inline-flex w-full rounded-2xl border border-[var(--kq-color-border)] bg-[var(--kq-color-primary-pale)]/45 p-1 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg-subtle)]"
        >
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              onClick={() => setTab(id)}
              className={cn(
                "flex min-h-[2.25rem] flex-1 items-center justify-center gap-1.5 rounded-xl px-2 py-1.5 text-sm font-medium transition",
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
            <>
              <SettingsDisplay
                status={status}
                fontSize={fontSize}
                onSetFontSize={setFontSize}
                themeMode={themeMode}
                onSetThemeMode={setThemeMode}
                onWorkspaceChanged={refreshStatus}
              />
              <SettingsUpdate />
            </>
          )}

          {tab === "study" && (
            <>
              <SettingsImportReadMode />
              {/* 上限是保护不是成就——不显示连续天数或完成率（账本 B-3 红线）。 */}
              <SettingsReviewLimits />
              {/* 学生导入的是自己的教材：先说清哪些内容离开这台机器，再谈数据搬家。 */}
              <SettingsMaterialPrivacy />
              <SettingsStudyImprovementCounts />
              {/* 学习证据是学生自己的东西，取回、销毁和升级记录集中在学习设置。 */}
              <SettingsLearningData />
              <SettingsLearningMigrations />
            </>
          )}

          {tab === "model" && (
            <>
              <SettingsLlmConfig
                hasSecret={!!status?.hasSecret}
                onCredentialChanged={refreshStatus}
              />
              {/* 只报 token 不折金额——见设置规格 §2.2。 */}
              <SettingsTokenUsage />
            </>
          )}

          {tab === "advanced" && (
            <>
              <SettingsLegacyChannels />
              <SettingsLoadPackages />
              <SettingsSharedPrefs />
            </>
          )}
        </div>
      </div>
      </div>
    </AppScaffold>
  );
}
