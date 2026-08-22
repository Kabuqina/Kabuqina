// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useState } from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { useI18n } from "../lib/i18n";
import { ART_ASSETS } from "../lib/artAssets";
import { PixelGlyph } from "./voxel/PixelGlyph";

/**
 * 缩到小娜 + 系统窗口控制。
 *
 * 单独抽出来，是因为窗口控制**只能有一处**，而承载它的那条横条会变：
 * 在 Study / Studio / Chat / Settings 上是 `AppShell` 的产品页眉，其余页面是
 * `WindowTitleBar`。两边渲染同一个组件，不各写一份。
 *
 * 字形是 16 网格上的平面像素件（`PixelGlyph`），不是 lucide 也不做等轴：产品页眉上
 * 满是体素方块，lucide 那几根发丝摆在旁边太轻；而窗口控制是系统 chrome，
 * 立体化又会和内容争视觉——所以走「同样的硬边、留在正面」。
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
        {/* 使用设计导出的 kq-cup，按 28px 展示；按钮只提供点击语义，不再画额外底板。 */}
        <img className="kq-titlebar-companion-icon" src={ART_ASSETS.companionButton} alt="" />
      </button>
      <div className="kq-titlebar-divider" aria-hidden />
      <button
        type="button"
        onClick={() => void win().minimize()}
        className="kq-titlebar-control hermes-titlebar-nodrag"
        title={t("shell.minimize")}
        aria-label={t("shell.minimize")}
      >
        <PixelGlyph name="minimize" size={11} />
      </button>
      <button
        type="button"
        onClick={() => void win().toggleMaximize()}
        className="kq-titlebar-control hermes-titlebar-nodrag"
        title={isMaximized ? t("shell.restore") : t("shell.maximize")}
        aria-label={isMaximized ? t("shell.restore") : t("shell.maximize")}
      >
        <PixelGlyph name="maximize" size={11} />
      </button>
      <button
        type="button"
        // 关闭是收进托盘；真正退出走托盘菜单（close() 会销毁窗口）。
        onClick={() => void win().hide()}
        className="kq-titlebar-control kq-titlebar-control--close hermes-titlebar-nodrag"
        title={t("shell.close")}
        aria-label={t("shell.close")}
      >
        <PixelGlyph name="close" size={11} />
      </button>
    </div>
  );
}
