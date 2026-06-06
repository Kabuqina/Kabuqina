// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { invoke } from "@tauri-apps/api/core";
import { Activity, ArrowDown, ArrowUp } from "lucide-react";
import { AppScaffold } from "../components/AppScaffold";
import { BackButton } from "../components/ui/BackButton";
import { Section } from "../components/ui/Section";
import { useI18n } from "../lib/i18n";
import { useTogglePowerUser } from "../lib/useTogglePowerUser";
import { useFontSize, useThemeMode } from "../lib/ui-prefs";
import { useGatewayStatus } from "../features/gateway/useGatewayStatus";
import { SettingsGateway } from "./settings/SettingsGateway";
import { SettingsDisplay } from "./settings/SettingsDisplay";
import { SettingsSharedPrefs } from "./settings/SettingsSharedPrefs";
import { SettingsLoadPackages } from "./settings/SettingsLoadPackages";

export interface Status {
  workspace: string;
  hasSecret: boolean;
  pythonRunning: boolean;
}

export function Settings() {
  const { t } = useI18n();
  const nav = useNavigate();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const { powerUser, togglePowerUser } = useTogglePowerUser();
  const { size: fontSize, setSize: setFontSize } = useFontSize();
  const { mode: themeMode, setMode: setThemeMode } = useThemeMode();
  const [autoStartGateway, setAutoStartGateway] = useState(false);
  const gatewayStatus = useGatewayStatus();

  useEffect(() => {
    (async () => {
      const [workspace, hasSecret, pyStat] = await Promise.all([
        invoke<string>("cmd_workspace_path"),
        invoke<boolean>("cmd_has_secret"),
        invoke<{ running: boolean }>("cmd_python_status"),
      ]);
      setStatus({ workspace, hasSecret, pythonRunning: pyStat.running });
      try {
        const ag = await invoke<boolean>("cmd_get_auto_start_gateway");
        setAutoStartGateway(!!ag);
      } catch {
        /* optional */
      }
    })().catch(console.error);
  }, []);

  async function toggleAutoStartGateway(next: boolean) {
    try {
      await invoke("cmd_set_auto_start_gateway", { enabled: next });
      setAutoStartGateway(next);
    } catch (e) {
      console.error(e);
    }
  }

  return (
    <AppScaffold className="h-full overflow-y-auto" ref={scrollRef}>
      <div className="mx-auto max-w-2xl space-y-5 px-[var(--hd-page-pad-x)] py-8 sm:py-10">
        <div>
          <BackButton onClick={() => nav("/chat")}>
            {t("settings.back")}
          </BackButton>
          <h1 className="hd-page-title">{t("settings.title")}</h1>
          {t("settings.pageLead") && (
            <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-[var(--kq-color-muted)] dark:text-zinc-400">
              {t("settings.pageLead")}
            </p>
          )}
        </div>

        <Section icon={Activity} title={t("settings.status")}>
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-[var(--kq-color-ink)] dark:text-zinc-300">
            <div className="flex items-center gap-2">
              <span className={`inline-block h-2 w-2 rounded-full ${status?.pythonRunning ? "bg-emerald-500" : "bg-zinc-300 dark:bg-zinc-600"}`} />
              <span>{t("settings.pyRunning")}</span>
              <span className="font-medium text-[var(--kq-color-strong)] dark:text-zinc-100">
                {status?.pythonRunning ? t("settings.yes") : t("settings.no")}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className={`inline-block h-2 w-2 rounded-full ${status?.hasSecret ? "bg-emerald-500" : "bg-zinc-300 dark:bg-zinc-600"}`} />
              <span>{t("settings.hasPass")}</span>
              <span className="font-medium text-[var(--kq-color-strong)] dark:text-zinc-100">
                {status?.hasSecret ? t("settings.yes") : t("settings.no")}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className={`inline-block h-2 w-2 rounded-full ${gatewayStatus.running ? "bg-emerald-500" : "bg-zinc-300 dark:bg-zinc-600"}`} />
              <span>{t("settings.gatewayShort")}</span>
              <span className="font-medium text-[var(--kq-color-strong)] dark:text-zinc-100">
                {gatewayStatus.running ? t("settings.yes") : t("settings.no")}
              </span>
            </div>
          </div>
        </Section>

        <SettingsGateway
          gatewayStatus={gatewayStatus}
          autoStartGateway={autoStartGateway}
          onToggleAutoStart={toggleAutoStartGateway}
          onStatusChange={setStatus}
          status={status}
        />

        <SettingsDisplay
          status={status}
          powerUser={powerUser}
          onTogglePowerUser={togglePowerUser}
          fontSize={fontSize}
          onSetFontSize={setFontSize}
          themeMode={themeMode}
          onSetThemeMode={setThemeMode}
        />

        <SettingsLoadPackages />

        <SettingsSharedPrefs />
      </div>

      {/* Floating scroll buttons */}
      <div className="pointer-events-none fixed bottom-6 right-6 z-50 flex flex-col gap-2">
        <button
          type="button"
          onClick={() => scrollRef.current?.scrollTo({ top: 0, behavior: "smooth" })}
          className="pointer-events-auto flex h-10 w-10 items-center justify-center rounded-full border border-[var(--kq-color-border)] bg-white/90 text-[var(--kq-color-muted)] shadow-[var(--kq-shadow-card)] backdrop-blur transition hover:bg-white hover:text-[var(--kq-color-strong)] dark:bg-zinc-800/90 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
          aria-label={t("settings.scrollTop")}
          title={t("settings.scrollTop")}
        >
          <ArrowUp className="h-5 w-5" />
        </button>
        <button
          type="button"
          onClick={() =>
            scrollRef.current?.scrollTo({
              top: scrollRef.current.scrollHeight,
              behavior: "smooth",
            })
          }
          className="pointer-events-auto flex h-10 w-10 items-center justify-center rounded-full border border-[var(--kq-color-border)] bg-white/90 text-[var(--kq-color-muted)] shadow-[var(--kq-shadow-card)] backdrop-blur transition hover:bg-white hover:text-[var(--kq-color-strong)] dark:bg-zinc-800/90 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
          aria-label={t("settings.scrollBottom")}
          title={t("settings.scrollBottom")}
        >
          <ArrowDown className="h-5 w-5" />
        </button>
      </div>
    </AppScaffold>
  );
}
