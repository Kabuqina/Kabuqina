// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useState } from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { Maximize2, Minus, Sparkles, X } from "lucide-react";
import { useI18n } from "../lib/i18n";
import { ART_ASSETS } from "../lib/artAssets";
import { cn } from "../lib/cn";

/** 与系统关闭/最小化/最大化同一行的顶栏；需 `tauri.conf.json` 中 `decorations: false`。 */
export function WindowTitleBar() {
  const { t } = useI18n();
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


  return (
    <div
      className={cn(
        "kq-titlebar hermes-titlebar-drag grid h-9 shrink-0 select-none grid-cols-[1fr_auto_1fr] items-stretch border-b",
        "dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)]"
      )}
      data-tauri-drag-region
    >
      <div
        className="col-start-1 flex min-w-0 items-center gap-2 pl-4"
        aria-label={t("brand")}
      >
        <div
          className="grid h-[22px] w-[22px] shrink-0 place-items-center overflow-hidden"
          style={{ borderRadius: "6px", background: "linear-gradient(135deg, #f5effa, #ebe3f2)", boxShadow: "0 1px 3px rgba(90,74,106,0.12)" }}
        >
          <img
            src={ART_ASSETS.windowIcon}
            alt={t("brand")}
            className="h-[18px] w-[18px] shrink-0 object-contain"
            width={18}
            height={18}
            decoding="async"
          />
        </div>
        <span className="kq-titlebar-brand truncate text-sm font-semibold dark:text-[var(--kq-color-ink)]" style={{ letterSpacing: "0.03em" }}>
          {t("productName")}
        </span>
      </div>

      {/* 产品导航归 AppShell 的全局页眉（架构 §5.1）。这条是**窗口**标题栏：
          品牌、缩到小娜、以及系统窗口控制——不再并列第二套一级目的地。 */}
      <div className="kq-titlebar-nav col-start-2 flex items-center justify-center gap-1 px-1">
        {inApp && (
          <>
            <button
              type="button"
              onClick={onShowCompanion}
              className="kq-titlebar-companion-btn hermes-titlebar-nodrag"
              title={t("companion.show")}
              aria-label={t("companion.show")}
            >
              <Sparkles
                className="kq-titlebar-companion-icon"
                strokeWidth={2}
                aria-hidden
              />
            </button>
          </>
        )}
      </div>

      <div className="kq-titlebar-controls col-start-3 flex items-center justify-end gap-0.5 pr-1">
        {inApp && (
          <>
            <button
              type="button"
              onClick={onMinimize}
              className="kq-titlebar-control hermes-titlebar-nodrag inline-flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-md transition dark:hover:bg-[var(--kq-hover-bg-strong)] dark:hover:text-[var(--kq-color-strong)]"
              title={t("shell.minimize")}
              aria-label={t("shell.minimize")}
            >
              <Minus className="h-3.5 w-3.5" strokeWidth={2.25} />
            </button>
            <button
              type="button"
              onClick={onToggleMax}
              className="kq-titlebar-control hermes-titlebar-nodrag inline-flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-md transition dark:hover:bg-[var(--kq-hover-bg-strong)] dark:hover:text-[var(--kq-color-strong)]"
              title={isMaximized ? t("shell.restore") : t("shell.maximize")}
              aria-label={isMaximized ? t("shell.restore") : t("shell.maximize")}
            >
              <Maximize2 className="h-3.5 w-3.5" strokeWidth={2.2} />
            </button>
            <button
              type="button"
              onClick={onClose}
              className="kq-titlebar-control hermes-titlebar-nodrag inline-flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-md transition hover:bg-red-500/90 hover:text-white dark:hover:bg-red-600/90"
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
