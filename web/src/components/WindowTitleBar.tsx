// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useI18n } from "../lib/i18n";
import { ART_ASSETS } from "../lib/artAssets";
import { cn } from "../lib/cn";
import { WindowControls } from "./WindowControls";

/**
 * 非产品页面（引导、导出、启动页）的窗口标题栏；需 `tauri.conf.json` 中
 * `decorations: false`。
 *
 * Study / Studio / Chat / Settings **不用这条**——这些面上，窗口控制长在 `AppShell`
 * 的产品页眉右端，全窗口只有一条横条。
 */
export function WindowTitleBar() {
  const { t } = useI18n();

  return (
    <div
      className={cn(
        "kq-titlebar hermes-titlebar-drag grid h-9 shrink-0 select-none grid-cols-[1fr_auto] items-stretch border-b",
        "dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)]",
      )}
      data-tauri-drag-region
    >
      <div className="col-start-1 flex min-w-0 items-center gap-2 pl-4" aria-label={t("brand")}>
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
        <span
          className="kq-titlebar-brand truncate text-sm font-semibold dark:text-[var(--kq-color-ink)]"
          style={{ letterSpacing: "0.03em" }}
        >
          {t("productName")}
        </span>
      </div>

      <div className="col-start-2 flex items-center justify-end">
        <WindowControls />
      </div>
    </div>
  );
}
