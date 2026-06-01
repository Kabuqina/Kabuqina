// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
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
import { TelegramPage } from "./advanced/pages/TelegramPage";
import { FeishuPage } from "./advanced/pages/FeishuPage";
import { CapabilitiesPage } from "./advanced/pages/CapabilitiesPage";
import { QqPage } from "./advanced/pages/QqPage";
import { WeixinPage } from "./advanced/pages/WeixinPage";
import { DingTalkPage } from "./advanced/pages/DingTalkPage";
import { WeComPage } from "./advanced/pages/WeComPage";
import { EmailPage } from "./advanced/pages/EmailPage";
import { ScheduledTasksPage } from "./advanced/pages/ScheduledTasks";
import { OverlayWindow } from "./capture/OverlayWindow";
import { CompanionWindow } from "./companion/CompanionWindow";
import { BrandSvgPreview } from "./components/brand/BrandSvgPreview";
import { applyFontSize } from "./lib/ui-prefs";
import "./index.css";

applyFontSize();

// --- Capture-overlay window: render the bare overlay, no shell chrome ---
const windowLabel = (() => {
  try {
    return getCurrentWindow().label;
  } catch {
    return null;
  }
})();

function showMainWindowWhenReady() {
  const win = getCurrentWindow();
  window.requestAnimationFrame(() => {
    window.requestAnimationFrame(() => {
      void win.show();
    });
  });
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
} else {
  // --- Main window: normal app shell ---
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <I18nProvider>
        <BrowserRouter>
          <div className="flex h-full min-h-0 flex-col">
            <WindowTitleBar />
            <div className="min-h-0 flex-1 overflow-hidden">
              <Routes>
                <Route path="/" element={<Splash />} />
                <Route path="/onboarding/*" element={<Wizard />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/capabilities" element={<CapabilitiesPage />} />
                <Route path="/export" element={<Export />} />
                <Route path="/settings/telegram" element={<TelegramPage />} />
                <Route path="/settings/feishu" element={<FeishuPage />} />
                <Route path="/settings/qq" element={<QqPage />} />
                <Route path="/settings/weixin" element={<WeixinPage />} />
                <Route path="/settings/dingtalk" element={<DingTalkPage />} />
                <Route path="/settings/wecom" element={<WeComPage />} />
                <Route path="/settings/email" element={<EmailPage />} />
                <Route path="/settings/cron" element={<ScheduledTasksPage />} />
                <Route path="/chat" element={<ChatPage />} />
                <Route path="/brand-svg-preview" element={<BrandSvgPreview />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
              <DesktopDeliveryNotifier />
              <ApprovalDialogHost />
              <ConfirmDialogHost />
              <DesktopDeliveryPoller />
            </div>
          </div>
        </BrowserRouter>
      </I18nProvider>
    </React.StrictMode>,
  );
  showMainWindowWhenReady();
}
