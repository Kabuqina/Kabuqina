// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import React, { useEffect } from "react";
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
import { ResourceDetailPage } from "./study/ResourceDetailPage";
import { KnowledgeConceptPage } from "./study/KnowledgeConceptPage";
import { KnowledgeGraphPage } from "./study/KnowledgeGraphPage";
import { FeishuPage } from "./advanced/pages/FeishuPage";
import { CapabilitiesPage } from "./advanced/pages/CapabilitiesPage";
import { LoadPackagesPage } from "./advanced/pages/LoadPackagesPage";
import { QqPage } from "./advanced/pages/QqPage";
import { WeixinPage } from "./advanced/pages/WeixinPage";
import { WeComPage } from "./advanced/pages/WeComPage";
// DingTalkPage / EmailPage routes are cut from the mainland_cn product surface
// (v0.3.0). Source kept under advanced/pages for the future sea profile.
import { ScheduledTasksPage } from "./advanced/pages/ScheduledTasks";
import { OverlayWindow } from "./capture/OverlayWindow";
import { CompanionWindow } from "./companion/CompanionWindow";
import { BrandSvgPreview } from "./components/brand/BrandSvgPreview";
import { applyFontSize, applyTheme } from "./lib/ui-prefs";
import "./index.css";

applyFontSize();
applyTheme();

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

function MainWindowShell() {
  useEffect(() => revealMainWindowAfterShellPaint(), []);

  return (
    <I18nProvider>
      <BrowserRouter>
        <div className="flex h-full min-h-0 flex-col">
          <WindowTitleBar />
          <div className="min-h-0 flex-1 overflow-hidden">
            <Routes>
              <Route path="/" element={<Splash />} />
              <Route path="/onboarding/*" element={<Wizard />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/settings/load-packages" element={<LoadPackagesPage />} />
              <Route path="/capabilities" element={<CapabilitiesPage />} />
              <Route path="/export" element={<Export />} />
              <Route path="/settings/feishu" element={<FeishuPage />} />
              <Route path="/settings/qq" element={<QqPage />} />
              <Route path="/settings/weixin" element={<WeixinPage />} />
              <Route path="/settings/wecom" element={<WeComPage />} />
              <Route path="/settings/cron" element={<ScheduledTasksPage />} />
              <Route path="/chat" element={<ChatPage />} />
              <Route path="/study/resources/:artifactId" element={<ResourceDetailPage />} />
              <Route path="/study/knowledge-graph" element={<KnowledgeGraphPage />} />
              <Route path="/study/knowledge/:artifactId/:conceptIndex" element={<KnowledgeConceptPage />} />
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
} else {
  // --- Main window: normal app shell ---
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <MainWindowShell />
    </React.StrictMode>,
  );
}
