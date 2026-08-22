// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import React, { lazy, Suspense, useEffect } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { WindowTitleBar } from "./components/WindowTitleBar";
import { ApprovalDialogHost } from "./components/ApprovalDialogHost";
import { ConfirmDialogHost } from "./components/ConfirmDialogHost";
import { DesktopDeliveryNotifier } from "./components/DesktopDeliveryNotifier";
import { DesktopDeliveryPoller } from "./components/DesktopDeliveryPoller";
import { I18nProvider } from "./lib/i18n";
import { BootPill } from "./components/BootPill";
import { applyFontSize, applyTheme, watchSystemTheme } from "./lib/ui-prefs";
import "./index.css";

applyFontSize();
applyTheme();
// 「跟随系统」在所有页面都要成立，不只是设置页。
watchSystemTheme();

const AppShell = lazy(async () => ({ default: (await import("./shell/AppShell")).AppShell }));
const Splash = lazy(async () => ({ default: (await import("./Splash")).Splash }));
const Wizard = lazy(async () => ({ default: (await import("./onboarding/Wizard")).Wizard }));
const Export = lazy(async () => ({ default: (await import("./advanced/Export")).Export }));
const ChatPage = lazy(async () => ({ default: (await import("./chat/ChatPage")).ChatPage }));
const Settings = lazy(async () => ({ default: (await import("./advanced/Settings")).Settings }));
const LegacyPlatformTombstonePage = lazy(async () => ({ default: (await import("./advanced/pages/PlatformRouteGuard")).LegacyPlatformTombstonePage }));
const ScheduledTasksPage = lazy(async () => ({ default: (await import("./advanced/pages/ScheduledTasks")).ScheduledTasksPage }));
const OverlayWindow = lazy(async () => ({ default: (await import("./capture/OverlayWindow")).OverlayWindow }));
const CompanionWindow = lazy(async () => ({ default: (await import("./companion/CompanionWindow")).CompanionWindow }));
const BrandSvgPreview = lazy(async () => ({ default: (await import("./components/brand/BrandSvgPreview")).BrandSvgPreview }));
const StudyRoute = lazy(() => import("./study/StudyRoute"));
const DeskScenePreview = import.meta.env.DEV
  ? lazy(() => import("./study/desk/DeskScenePreview"))
  : null;
const isStandaloneDeskPreview =
  import.meta.env.DEV && window.location.pathname === "/__dev/desk";

// --- Capture-overlay window: render the bare overlay, no shell chrome ---
const windowLabel = (() => {
  try {
    return getCurrentWindow().label;
  } catch {
    return null;
  }
})();

const MAIN_WINDOW_REVEAL_DELAY_MS = 48;

function revealMainWindowAfterShellPaint() {
  let win: ReturnType<typeof getCurrentWindow>;
  try {
    win = getCurrentWindow();
  } catch {
    return;
  }

  let timeoutId: number | undefined;
  window.requestAnimationFrame(() => {
    window.requestAnimationFrame(() => {
      timeoutId = window.setTimeout(() => {
        void win.show();
      }, MAIN_WINDOW_REVEAL_DELAY_MS);
    });
  });

  return () => {
    if (timeoutId !== undefined) {
      window.clearTimeout(timeoutId);
    }
  };
}

const SHELL_SURFACES = ["/study", "/chat", "/settings", "/onboarding", "/export"];

function MainWindowContent() {
  const location = useLocation();
  // AppShell 覆盖所有产品页与辅助流程，那条横条就是窗口标题栏，窗口控制长在它右端；
  // 只有启动页与独立预览页使用较矮的 WindowTitleBar。全窗口始终只有一条。
  const shellOwnsTitleBar = SHELL_SURFACES.some(
    (path) => location.pathname === path || location.pathname.startsWith(`${path}/`),
  );
  return (
    <div className="flex h-full min-h-0 flex-col">
      {shellOwnsTitleBar ? null : <WindowTitleBar />}
      <div className="min-h-0 flex-1 overflow-hidden">
        <Suspense fallback={<BootPill />}>
          <Routes>
          <Route path="/" element={<Splash />} />
          {/* 移动端 Bot 与邮件渠道的产品面已移除（CTL-C08）；旧 v0.4 深链接只进墓碑页解释升级。 */}
          {/* 产品页与辅助流程共用全局外壳：台灯与学习/对话站在横条最左，
              品牌在正中，设置与窗口控制在右侧工具区；各页面不再自己画一条顶栏（架构 §5.1）。 */}
          <Route element={<AppShell />}>
            <Route path="/onboarding/*" element={<Wizard />} />
            <Route path="/export" element={<Export />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/settings/load-packages" element={<Navigate to="/settings" replace state={{ settingsTab: "advanced" }} />} />
            <Route path="/settings/qq" element={<LegacyPlatformTombstonePage platform="QQ Bot" />} />
            <Route path="/settings/weixin" element={<LegacyPlatformTombstonePage platform="微信 Bot" />} />
            <Route path="/settings/dingtalk" element={<LegacyPlatformTombstonePage platform="钉钉 Bot" />} />
            <Route path="/settings/email" element={<LegacyPlatformTombstonePage platform="Email" />} />
            <Route path="/settings/telegram" element={<LegacyPlatformTombstonePage platform="Telegram" />} />
            <Route path="/settings/whatsapp" element={<LegacyPlatformTombstonePage platform="WhatsApp" />} />
            <Route path="/settings/feishu" element={<LegacyPlatformTombstonePage platform="Feishu / Lark" />} />
            <Route path="/settings/wecom" element={<LegacyPlatformTombstonePage platform="WeCom" />} />
            <Route path="/settings/cron" element={<ScheduledTasksPage />} />
            <Route
              path="/study/*"
              element={<Suspense fallback={<BootPill />}><StudyRoute /></Suspense>}
            />
            {/* Studio 已从产品中砍掉（聚焦 Study）：/studio 重定向到 /study，
                旧链接不至于落到空白路由。 */}
            <Route path="/studio/*" element={<Navigate to="/study" replace />} />
          </Route>
          {DeskScenePreview ? (
            <Route
              path="/__dev/desk"
              element={<Suspense fallback={<BootPill />}><DeskScenePreview /></Suspense>}
            />
          ) : null}
          <Route path="/brand-svg-preview" element={<BrandSvgPreview />} />
          <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
        <DesktopDeliveryNotifier />
        <ApprovalDialogHost />
        <ConfirmDialogHost />
        <DesktopDeliveryPoller />
      </div>
    </div>
  );
}

function MainWindowShell() {
  useEffect(() => revealMainWindowAfterShellPaint(), []);

  return (
    <I18nProvider>
      <BrowserRouter>
        <MainWindowContent />
      </BrowserRouter>
    </I18nProvider>
  );
}

if (windowLabel === "capture-overlay") {
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <Suspense fallback={<BootPill />}><OverlayWindow /></Suspense>
    </React.StrictMode>,
  );
} else if (windowLabel === "companion") {
  document.documentElement.classList.add("kq-companion-window");
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <I18nProvider>
        <Suspense fallback={<BootPill />}><CompanionWindow /></Suspense>
      </I18nProvider>
    </React.StrictMode>,
  );
} else if (isStandaloneDeskPreview && DeskScenePreview) {
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <I18nProvider>
        <Suspense fallback={<BootPill />}>
          <DeskScenePreview />
        </Suspense>
      </I18nProvider>
    </React.StrictMode>,
  );
} else {
  // --- Main window: normal app shell ---
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <MainWindowShell />
    </React.StrictMode>,
  );
}
