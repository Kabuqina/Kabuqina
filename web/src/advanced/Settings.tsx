// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useState, type ComponentType } from "react";
import { useLocation } from "react-router-dom";
import { invoke } from "@tauri-apps/api/core";
import { BookOpen, Cpu, Package, SlidersHorizontal } from "lucide-react";
import { AppScaffold } from "../components/AppScaffold";
import { useI18n } from "../lib/i18n";
import { cn } from "../lib/cn";
import { useFontSize, useThemeMode } from "../lib/ui-prefs";
import { SettingsDisplay } from "./settings/SettingsDisplay";
import { SettingsImportReadMode, SettingsReviewLimits } from "./settings/SettingsStudyPreferences";
import { SettingsSharedPrefs } from "./settings/SettingsSharedPrefs";
import { SettingsLoadPackages } from "./settings/SettingsLoadPackages";
import { SettingsLlmConfig } from "./settings/SettingsLlmConfig";
import { SettingsTokenUsage } from "./settings/SettingsTokenUsage";

export interface Status {
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
    const [hasSecret, pyStat] = await Promise.all([
      invoke<boolean>("cmd_has_secret"),
      invoke<{ running: boolean }>("cmd_python_status"),
    ]);
    setStatus({ hasSecret, pythonRunning: pyStat.running });
  }, []);

  useEffect(() => {
    void refreshStatus().catch(console.error);
  }, [refreshStatus]);

  const tabs: Array<{ id: SettingsTab; label: string; icon: ComponentType<{ className?: string }> }> = [
    { id: "general", label: t("settings.tabGeneral"), icon: SlidersHorizontal },
    { id: "study", label: t("settings.tabStudy"), icon: BookOpen },
    { id: "model", label: t("settings.tabModel"), icon: Cpu },
    { id: "advanced", label: t("settings.tabAdvanced"), icon: Package },
  ];

  // 芯片报的是状态本身，所以两个状态各有自己的说法，而不是一句问句配「是/否」。
  const pyOn = !!status?.pythonRunning;
  const secretOn = !!status?.hasSecret;
  const statusDots: Array<{ key: string; on: boolean; label: string }> = [
    { key: "py", on: pyOn, label: t(pyOn ? "settings.pyRunningOn" : "settings.pyRunningOff") },
    { key: "secret", on: secretOn, label: t(secretOn ? "settings.hasPassOn" : "settings.hasPassOff") },
  ];

  return (
    <AppScaffold surface="chat" className="flex h-full min-h-0 flex-col">
      {/* 设置和 Chat 一样是桌上的一张纸：同宽、同圆角、同叠纸投影、同抽屉脸（4a）。 */}
      <div className="kq-chat-desk">
        <div className="kq-drawer-face" aria-hidden />
        <section className="kq-chat-paper kq-settings-paper">
          {/* 纸质页眉：标题 + 健康芯片 + 一句说明，接着是下划线式标签页。
              健康状态原来是标签页上方一条绿点「是/否」，像调试输出。 */}
          <header className="kq-set-head">
            <div className="kq-set-head-row">
              <h1>{t("settings.title")}</h1>
              {statusDots.map((dot) => (
                <span
                  key={dot.key}
                  className={cn("kq-chip", dot.on ? "kq-chip--success" : "kq-chip--neutral")}
                >
                  <span className="kq-set-health-dot" aria-hidden />
                  {dot.label}
                </span>
              ))}
              {t("settings.pageLead") && (
                <span className="kq-set-head-lead">{t("settings.pageLead")}</span>
              )}
            </div>

            {/* 下划线式标签页：不再是一条药丸分段条压在暖纸上。 */}
            <div role="tablist" className="kq-set-tabs">
              {tabs.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={tab === id}
                  onClick={() => setTab(id)}
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </button>
              ))}
            </div>
          </header>

        <div className="kq-set-body">
        <div>
          {tab === "general" && (
            <>
              <SettingsDisplay
                fontSize={fontSize}
                onSetFontSize={setFontSize}
                themeMode={themeMode}
                onSetThemeMode={setThemeMode}
              />
              <SettingsSharedPrefs />
            </>
          )}

          {tab === "study" && (
            <>
              <SettingsImportReadMode />
              <SettingsReviewLimits />
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
            <SettingsLoadPackages />
          )}
        </div>
        </div>
        </section>
      </div>
    </AppScaffold>
  );
}
