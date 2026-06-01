// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { Maximize2, Minus, Sparkles, X, Zap } from "lucide-react";
import { Toggle } from "./ui/Toggle";
import { useI18n } from "../lib/i18n";
import { cn } from "../lib/cn";
import { useTogglePowerUser } from "../lib/useTogglePowerUser";

/** 与系统关闭/最小化/最大化同一行的顶栏；需 `tauri.conf.json` 中 `decorations: false`。 */
export function WindowTitleBar() {
  const { t } = useI18n();
  const { powerUser, togglePowerUser } = useTogglePowerUser();
  const location = useLocation();
  const inApp = isTauri();
  const [isMaximized, setIsMaximized] = useState(false);

  useEffect(() => {
    if (!inApp) {
      return;
    }
    const win = getCurrentWindow();
    let unlisten: (() => void) | undefined;
    void win.isMaximized().then(setIsMaximized);
    void win
      .onResized(() => {
        void win.isMaximized().then(setIsMaximized);
      })
      .then((u) => {
        unlisten = u;
      });
    return () => {
      unlisten?.();
    };
  }, [inApp]);

  const onMinimize = () => {
    if (!inApp) {
      return;
    }
    void getCurrentWindow().minimize();
  };

  const onToggleMax = () => {
    if (!inApp) {
      return;
    }
    void getCurrentWindow().toggleMaximize();
  };

  const onClose = () => {
    if (!inApp) {
      return;
    }
    // Hide to tray; quitting is via the tray menu (close() destroys the window).
    void getCurrentWindow().hide();
  };

  const onShowCompanion = () => {
    if (!inApp) {
      return;
    }
    void invoke("cmd_show_companion");
  };

  const isChat = location.pathname === "/chat";
  const isSettings = location.pathname === "/settings";
  const isCapabilities = location.pathname === "/capabilities";
  const isWizard = location.pathname.startsWith("/onboarding");
  const settingsLabel = t("chat.openSettings");
  const capabilitiesLabel = t("capabilities.title");
  const navLinkClass = (active: boolean) =>
    cn(
      "kq-titlebar-link hermes-titlebar-nodrag no-underline rounded-lg px-3 py-1 text-sm font-medium transition",
      active && "kq-titlebar-link-active",
    );

  return (
    <div
      className={cn(
        "kq-titlebar hermes-titlebar-drag grid h-9 shrink-0 select-none grid-cols-[1fr_auto_1fr] items-stretch border-b",
        "dark:border-zinc-700 dark:bg-zinc-900/95"
      )}
      data-tauri-drag-region
    >
      <div
        className="col-start-1 flex min-w-0 items-center pl-3 sm:pl-4"
        aria-label={t("brand")}
      >
        <img
          src="/kabuqina_na_48.png"
          alt={t("brand")}
          className="h-5 w-5 shrink-0 object-contain dark:opacity-95"
          width={20}
          height={20}
          decoding="async"
        />
        <span className="kq-titlebar-brand ml-2 truncate text-sm font-semibold dark:text-zinc-200">
          {t("productName")}
        </span>
      </div>

      <div className="kq-titlebar-nav col-start-2 flex items-center justify-center gap-0.5 px-1 sm:gap-1.5">
        <Link
          to="/chat"
          className={navLinkClass(isChat)}
          title={t("chat.title")}
        >
          {t("chat.title")}
        </Link>
        <Link
          to="/onboarding/welcome"
          className={navLinkClass(isWizard)}
          title={t("chat.wizardButton")}
        >
          {t("chat.wizardButton")}
        </Link>
        <Link
          to="/settings"
          className={navLinkClass(isSettings)}
          title={settingsLabel}
        >
          {settingsLabel}
        </Link>
        <Link
          to="/capabilities"
          className={navLinkClass(isCapabilities)}
          title={capabilitiesLabel}
        >
          {capabilitiesLabel}
        </Link>
        <div
          className="kq-titlebar-power hermes-titlebar-nodrag ml-0.5 inline-flex items-center gap-1.5 rounded-lg px-2 py-0.5"
          title={t("settings.powerTitle")}
        >
          <Zap
            className={cn(
              "h-3.5 w-3.5 shrink-0",
              powerUser ? "kq-power-icon" : "text-[var(--kq-color-muted)] dark:text-zinc-500",
            )}
            strokeWidth={2.25}
            aria-hidden
          />
          <span className="hidden text-xs font-medium sm:inline">{t("settings.powerTitle")}</span>
          <Toggle
            tone="kabuqina"
            value={powerUser}
            onChange={(v) => void togglePowerUser(v)}
            aria-label={t("settings.powerTitle")}
          />
        </div>
        {inApp && (
          <>
            <div className="kq-titlebar-divider mx-1 h-4 w-px shrink-0 dark:bg-zinc-700" aria-hidden />
            <button
              type="button"
              onClick={onShowCompanion}
              className="kq-titlebar-companion-btn hermes-titlebar-nodrag"
              title={t("companion.show")}
              aria-label={t("companion.show")}
            >
              <svg width="0" height="0" className="absolute" aria-hidden>
                <defs>
                  <linearGradient id="kq-titlebar-sparkle-grad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#f97316" />
                    <stop offset="48%" stopColor="#fbbf24" />
                    <stop offset="100%" stopColor="#ef4444" />
                  </linearGradient>
                </defs>
              </svg>
              <Sparkles
                className="kq-titlebar-companion-icon"
                stroke="url(#kq-titlebar-sparkle-grad)"
                fill="url(#kq-titlebar-sparkle-grad)"
                fillOpacity={0.42}
                strokeWidth={2.25}
                aria-hidden
              />
            </button>
          </>
        )}
      </div>

      <div className="kq-titlebar-controls col-start-3 flex items-center justify-end gap-0.5 pr-1 sm:gap-1.5">
        {inApp && (
          <>
            <button
              type="button"
              onClick={onMinimize}
              className="kq-titlebar-control hermes-titlebar-nodrag inline-flex h-8 w-8 shrink-0 items-center justify-center rounded transition dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
              title={t("shell.minimize")}
              aria-label={t("shell.minimize")}
            >
              <Minus className="h-3.5 w-3.5" strokeWidth={2.25} />
            </button>
            <button
              type="button"
              onClick={onToggleMax}
              className="kq-titlebar-control hermes-titlebar-nodrag inline-flex h-8 w-8 shrink-0 items-center justify-center rounded transition dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
              title={isMaximized ? t("shell.restore") : t("shell.maximize")}
              aria-label={isMaximized ? t("shell.restore") : t("shell.maximize")}
            >
              <Maximize2 className="h-3.5 w-3.5" strokeWidth={2.2} />
            </button>
            <button
              type="button"
              onClick={onClose}
              className="kq-titlebar-control hermes-titlebar-nodrag inline-flex h-8 w-8 shrink-0 items-center justify-center rounded transition hover:bg-red-500/90 hover:text-white dark:hover:bg-red-600/90"
              title={t("shell.close")}
              aria-label={t("shell.close")}
            >
              <X className="h-3.5 w-3.5" strokeWidth={2.25} />
            </button>
          </>
        )}
      </div>
    </div>
  );
}
