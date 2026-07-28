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
import { Wizard } from "./onboarding/Wizard";
import { Settings } from "./advanced/Settings";
import { Export } from "./advanced/Export";
import { Splash } from "./Splash";
import { ChatPage } from "./chat/ChatPage";
import { LoadPackagesPage } from "./advanced/pages/LoadPackagesPage";
import { LegacyPlatformTombstonePage } from "./advanced/pages/PlatformRouteGuard";
import { ScheduledTasksPage } from "./advanced/pages/ScheduledTasks";
import { OverlayWindow } from "./capture/OverlayWindow";
import { CompanionWindow } from "./companion/CompanionWindow";
import { BrandSvgPreview } from "./components/brand/BrandSvgPreview";
import { BootPill } from "./components/BootPill";
import { applyFontSize, applyTheme, watchSystemTheme } from "./lib/ui-prefs";
import "./index.css";

applyFontSize();
applyTheme();
// 「跟随系统」在所有页面都要成立，不只是设置页。
watchSystemTheme();

const StudyRoute = lazy(() => import("./study/StudyRoute"));
const StudioRoute = lazy(() => import("./studio/StudioRoute"));
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

function MainWindowContent() {
  const location = useLocation();
  const deskOwnsChrome = /^\/study\/[^/]+\/practice\/?$/.test(location.pathname);
  return (
    <div className="flex h-full min-h-0 flex-col">
      {deskOwnsChrome ? null : <WindowTitleBar />}
      <div className="min-h-0 flex-1 overflow-hidden">
        <Routes>
          <Route path="/" element={<Splash />} />
          <Route path="/onboarding/*" element={<Wizard />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/settings/load-packages" element={<LoadPackagesPage />} />
          <Route path="/export" element={<Export />} />
          {/* 移动端 Bot 与邮件渠道的产品面已移除（CTL-C08）；旧 v0.4 深链接只进墓碑页解释升级。 */}
          <Route path="/settings/qq" element={<LegacyPlatformTombstonePage platform="QQ Bot" />} />
          <Route path="/settings/weixin" element={<LegacyPlatformTombstonePage platform="微信 Bot" />} />
          <Route path="/settings/dingtalk" element={<LegacyPlatformTombstonePage platform="钉钉 Bot" />} />
          <Route path="/settings/email" element={<LegacyPlatformTombstonePage platform="Email" />} />
          <Route path="/settings/telegram" element={<LegacyPlatformTombstonePage platform="Telegram" />} />
          <Route path="/settings/whatsapp" element={<LegacyPlatformTombstonePage platform="WhatsApp" />} />
          <Route path="/settings/feishu" element={<LegacyPlatformTombstonePage platform="Feishu / Lark" />} />
          <Route path="/settings/wecom" element={<LegacyPlatformTombstonePage platform="WeCom" />} />
          <Route path="/settings/cron" element={<ScheduledTasksPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route
            path="/study/*"
            element={<Suspense fallback={<BootPill />}><StudyRoute /></Suspense>}
          />
          <Route
            path="/studio/*"
            element={<Suspense fallback={<BootPill />}><StudioRoute /></Suspense>}
          />
          {DeskScenePreview ? (
            <Route
              path="/__dev/desk"
              element={<Suspense fallback={<BootPill />}><DeskScenePreview /></Suspense>}
            />
          ) : null}
          <Route path="/brand-svg-preview" element={<BrandSvgPreview />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
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
      <OverlayWindow />
    </React.StrictMode>,
  );
} else if (windowLabel === "companion") {
  document.documentElement.classList.add("kq-companion-window");
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <I18nProvider>
        <CompanionWindow />
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
