// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useState } from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { Maximize2, Minus, Sparkles, X } from "lucide-react";
import { useI18n } from "../lib/i18n";

/**
 * 缩到小娜 + 系统窗口控制。
 *
 * 单独抽出来，是因为窗口控制**只能有一处**，而承载它的那条横条会变：
 * 在 Study / Studio / Chat / Settings 上是 `AppShell` 的产品页眉，其余页面是
 * `WindowTitleBar`。两边渲染同一个组件，不各写一份。
 */
export function WindowControls() {
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

  if (!inApp) {
    // 浏览器里没有窗口可以最小化；不画一排点不动的按钮。
    return null;
  }

  const win = () => getCurrentWindow();

  return (
    <div className="kq-window-controls">
      <button
        type="button"
        onClick={() => void invoke("cmd_show_companion")}
        className="kq-titlebar-companion-btn hermes-titlebar-nodrag"
        title={t("companion.show")}
        aria-label={t("companion.show")}
      >
        <Sparkles className="kq-titlebar-companion-icon" strokeWidth={2} aria-hidden />
      </button>
      <div className="kq-titlebar-divider" aria-hidden />
      <button
        type="button"
        onClick={() => void win().minimize()}
        className="kq-titlebar-control hermes-titlebar-nodrag"
        title={t("shell.minimize")}
        aria-label={t("shell.minimize")}
      >
        <Minus className="h-3.5 w-3.5" strokeWidth={2.25} />
      </button>
      <button
        type="button"
        onClick={() => void win().toggleMaximize()}
        className="kq-titlebar-control hermes-titlebar-nodrag"
        title={isMaximized ? t("shell.restore") : t("shell.maximize")}
        aria-label={isMaximized ? t("shell.restore") : t("shell.maximize")}
      >
        <Maximize2 className="h-3.5 w-3.5" strokeWidth={2.2} />
      </button>
      <button
        type="button"
        // 关闭是收进托盘；真正退出走托盘菜单（close() 会销毁窗口）。
        onClick={() => void win().hide()}
        className="kq-titlebar-control kq-titlebar-control--close hermes-titlebar-nodrag"
        title={t("shell.close")}
        aria-label={t("shell.close")}
      >
        <X className="h-3.5 w-3.5" strokeWidth={2.25} />
      </button>
    </div>
  );
}
