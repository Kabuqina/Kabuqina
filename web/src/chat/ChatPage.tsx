// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { AppScaffold } from "../components/AppScaffold";
import { BootPill } from "../components/BootPill";
import { confirm } from "../lib/confirmDialog";
import { useI18n } from "../lib/i18n";
import { ChatInput } from "./ChatInput";
import { ChatMessageList } from "./ChatMessageList";
import { ChatHistoryDrawer } from "./ChatHistoryDrawer";
import { ChatPaperHeader } from "./ChatPaperHeader";
import {
  armPendingChatSecretGateBypass,
  armPendingOpenReminderSession,
  getDraftPrompt,
  getOpenSessionId,
  isFromOnboarding,
  isOpenReminderSession,
  takePendingOpenReminderSession,
  takePendingChatSecretGateBypass,
} from "../lib/chatLocationState";
import { drainDesktopDeliveries } from "../lib/desktopDeliveryFeed";
import { getAllowChatWithoutApi } from "../lib/apiKeyGate";
import { ShellModal } from "../components/ShellModal";
import { clearDraft } from "../lib/store";
import { useKabuqinaReadiness } from "./hooks/useKabuqinaReadiness";
import { useSessions } from "./hooks/useSessions";
import { persistActiveSessionId, useChatState } from "./hooks/useChatState";
import { useSendMessage } from "./hooks/useSendMessage";
import { useLoadPackageDownloads } from "./hooks/useLoadPackageDownloads";
import { useInFlightTurns } from "./inFlightTurns";
import { type CaptureDonePayload } from "../capture/capture-api";
import { REMINDER_SESSION_ID } from "./reminderSession";
import {
  bindStudyHandoff,
  buildStudyChatPrompt,
  buildStudyNanaPrompt,
  clearPendingStudyHandoff,
  clearSessionStudyHandoff,
  getStudyChatHandoffFromLocation,
  readPendingStudyHandoff,
  readSessionStudyHandoff,
  type StudyChatHandoff,
} from "../lib/studyChatHandoff";


export function ChatPage() {
  const { t, locale } = useI18n();
  const nav = useNavigate();
  const location = useLocation();
  const incomingStudyHandoff = getStudyChatHandoffFromLocation(location.state);
  const [studyHandoff, setStudyHandoff] = useState<StudyChatHandoff | null>(
    () => incomingStudyHandoff ?? readPendingStudyHandoff(),
  );
  const handledStudyHandoffRef = useRef("");
  // True when chat is reached without a model configured. We no longer force
  // unconfigured users back to the wizard (onboarding auto-triggers on first
  // launch and Settings covers config) — instead we keep them on chat with the
  // send button disabled and a "configure model" prompt.
  const [needsModelSetup, setNeedsModelSetup] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);

  const { kabuqinaReady, kabuqinaWarming, bootErr } = useKabuqinaReadiness();
  const inFlightTurns = useInFlightTurns();
  const { sessions, listLoading, loadSessions, deleteSession } = useSessions({
    kabuqinaReady: kabuqinaReady && !kabuqinaWarming,
  });
  const prepareStudyText = useCallback((text: string) => (
    studyHandoff?.version === 2 ? buildStudyNanaPrompt(studyHandoff, text) : text
  ), [studyHandoff]);
  const {
    activeSessionId,
    setActiveSessionId,
    threadModel,
    setThreadModel,
    messages,
    setMessages,
    sendErr,
    setSendErr,
    apiRequiredOpen,
    setApiRequiredOpen,
    onNewChat,
    onPickSession,
    onDeleteSession,
    openReminderSession,
    refreshActiveThread,
    restorePersistedSession,
  } = useChatState({ loadSessions, inFlightTurns });
  const {
    input,
    setInput,
    sending,
    progress,
    pendingInteraction,
    pendingAttachments,
    onAddFiles,
    onAddCaptureAttachment,
    onRemoveAttachment,
    onSend,
    onStopAgent,
    onRespondInteraction,
  } = useSendMessage({
    activeSessionId,
    setActiveSessionId,
    threadModel,
    setThreadModel,
    setMessages,
    loadSessions,
    setApiRequiredOpen,
    setSendErr,
    locale,
    inFlightTurns,
    prepareText: prepareStudyText,
  });
  const loadPackageDownloads = useLoadPackageDownloads(kabuqinaReady && !kabuqinaWarming);

  useEffect(() => {
    if (
      isOpenReminderSession(location.state)
      || isFromOnboarding(location.state)
      || getDraftPrompt(location.state)
      || getStudyChatHandoffFromLocation(location.state)
      || getOpenSessionId(location.state)
    ) {
      return;
    }
    if (!kabuqinaReady || kabuqinaWarming || listLoading || activeSessionId) {
      return;
    }
    restorePersistedSession(sessions);
  }, [activeSessionId, kabuqinaReady, kabuqinaWarming, listLoading, location.state, restorePersistedSession, sessions]);

  useEffect(() => {
    if (!activeSessionId) return;
    setStudyHandoff((current) => (
      current?.sessionId === activeSessionId
        ? current
        : readSessionStudyHandoff(activeSessionId)
    ));
  }, [activeSessionId]);

  useEffect(() => {
    if (
      studyHandoff
      && sessions.some((session) => session.id === studyHandoff.sessionId)
    ) {
      clearPendingStudyHandoff();
    }
  }, [sessions, studyHandoff]);

  useEffect(() => {
    const locationHandoff = getStudyChatHandoffFromLocation(location.state);
    const handoff = locationHandoff ?? readPendingStudyHandoff();
    if (!handoff || listLoading) return;
    const identity = `${handoff.sessionId}:${handoff.createdAt}`;
    if (handledStudyHandoffRef.current === identity) return;
    handledStudyHandoffRef.current = identity;
    bindStudyHandoff(handoff);
    setStudyHandoff(handoff);
    const existing = sessions.some((session) => session.id === handoff.sessionId);
    if (existing) {
      onPickSession(handoff.sessionId);
    } else {
      onNewChat();
      setActiveSessionId(handoff.sessionId);
      persistActiveSessionId(handoff.sessionId);
    }
    const draft = getDraftPrompt(location.state) ?? (handoff.version === 2 ? "" : buildStudyChatPrompt(handoff));
    setInput(draft);
    nav("/chat", { replace: true, state: {} });
  }, [
    listLoading,
    location.state,
    nav,
    onNewChat,
    onPickSession,
    sessions,
    setActiveSessionId,
    setInput,
  ]);


  useEffect(() => {
    const sessionId = getOpenSessionId(location.state);
    if (!sessionId || listLoading) return;
    if (sessions.some((session) => session.id === sessionId)) {
      onPickSession(sessionId);
    }
    nav("/chat", { replace: true, state: {} });
  }, [listLoading, location.state, nav, onPickSession, sessions]);

  useEffect(() => {
    if (isOpenReminderSession(location.state)) {
      armPendingOpenReminderSession();
      nav("/chat", { replace: true, state: {} });
      return;
    }
    if (!takePendingOpenReminderSession()) {
      return;
    }
    if (!kabuqinaReady || kabuqinaWarming) {
      armPendingOpenReminderSession();
      return;
    }
    void openReminderSession(t("cron.reminderLogEmpty"));
  }, [kabuqinaReady, kabuqinaWarming, location.state, nav, openReminderSession, t]);

  useEffect(() => {
    if (isFromOnboarding(location.state)) {
      armPendingChatSecretGateBypass();
      clearDraft();
      // Optional load-package downloads are no longer kicked off here: the desk
      // server self-heals them serially at boot (see load_packages.start_auto_downloads),
      // so onboarding/first-chat is not slowed by ~1GB of concurrent downloads.
      nav("/chat", { replace: true, state: {} });
      return;
    }
    if (takePendingChatSecretGateBypass()) {
      setNeedsModelSetup(false);
      return;
    }
    let cancelled = false;
    const checkConfigured = async () => {
      try {
        if (getAllowChatWithoutApi()) {
          if (!cancelled) setNeedsModelSetup(false);
          return;
        }
        const ok = await invoke<boolean>("cmd_has_secret");
        if (!cancelled) setNeedsModelSetup(!ok);
      } catch {
        if (!cancelled) setNeedsModelSetup(true);
      }
    };
    void checkConfigured();
    return () => {
      cancelled = true;
    };
  }, [nav, location.state]);

  useEffect(() => {
    const draft = getDraftPrompt(location.state);
    if (!draft || getStudyChatHandoffFromLocation(location.state)) return;
    setInput(draft);
    nav("/chat", { replace: true, state: {} });
  }, [location.state, nav, setInput]);

  // Listen for screenshot capture events from the overlay window.
  useEffect(() => {
    const unlisten = listen<CaptureDonePayload>("capture-done", (event) => {
      const { name, mime, data } = event.payload;
      onAddCaptureAttachment({ name, mime, data });
    });
    return () => {
      unlisten.then((fn) => fn());
    };
  }, [onAddCaptureAttachment]);

  // Refresh sidebar + reminder transcript when cron/desktop deliveries arrive.
  useEffect(() => {
    if (!kabuqinaReady || kabuqinaWarming) {
      return;
    }
    let cancelled = false;
    const syncReminderFeed = async (force = false) => {
      const msgs = await drainDesktopDeliveries();
      if (cancelled) {
        return;
      }
      if (!force && msgs.length === 0) {
        return;
      }
      await loadSessions({ silent: true });
      if (activeSessionId === REMINDER_SESSION_ID) {
        await refreshActiveThread();
      }
    };
    void syncReminderFeed(true);
    const unlisten = listen("desktop-delivery", () => {
      void syncReminderFeed(true);
    });
    const handle = window.setInterval(() => {
      void syncReminderFeed(false);
    }, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(handle);
      unlisten.then((fn) => fn());
    };
  }, [activeSessionId, kabuqinaReady, kabuqinaWarming, loadSessions, refreshActiveThread]);

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const ok = await confirm({
      title: t("chat.deleteTitle"),
      message: t("chat.confirmDelete"),
      confirmLabel: t("dialog.delete"),
      cancelLabel: t("dialog.cancel"),
      tone: "danger",
    });
    if (!ok) return;
    try {
      await deleteSession(id);
      await onDeleteSession(id);
      if (studyHandoff?.sessionId === id) {
        clearSessionStudyHandoff(id);
        setStudyHandoff(null);
      }
    } catch (err) {
      console.error(err);
      setSendErr(t("chat.errDelete"));
    }
  };

  const handleNewChat = useCallback(() => {
    // 新对话一律回到自由会话（架构 §8.10）：两种作用域都解掉。
    clearPendingStudyHandoff();
    setStudyHandoff(null);
    onNewChat();
  }, [onNewChat]);

  const handlePickSession = useCallback((id: string) => {
    // 作用域只跟着会话走，绝不猜测（§8.3）。
    setStudyHandoff(readSessionStudyHandoff(id));
    onPickSession(id);
  }, [onPickSession]);

  const returnToStudy = useCallback(() => {
    if (!studyHandoff) return;
    nav(studyHandoff.returnTarget.path || studyHandoff.returnTarget.fallbackPath, {
      state: {
        studyReturn: {
          version: 1,
          stepId: studyHandoff.focusId,
          focus: studyHandoff.returnTarget.focus === "answer" ? "answer" : "notebook",
          ...(studyHandoff.deskSnapshot
            ? { deskSnapshot: studyHandoff.deskSnapshot }
            : {}),
        },
      },
    });
  }, [nav, studyHandoff]);

  if (bootErr) {
    return (
      <AppScaffold surface="chat" className="flex h-full flex-col items-center justify-center px-6 text-center">
        <p className="max-w-md whitespace-pre-wrap text-left text-sm text-[var(--kq-color-muted)]">
          {bootErr}
        </p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="mt-4 text-sm text-sky-600 underline-offset-2 dark:text-sky-400"
        >
          {t("chat.reload")}
        </button>
      </AppScaffold>
    );
  }

  if (!kabuqinaReady || kabuqinaWarming) {
    return (
      <AppScaffold surface="chat" className="flex h-full flex-col items-center justify-center">
        <BootPill />
      </AppScaffold>
    );
  }

  return (
    <AppScaffold surface="chat" className="flex h-full min-h-0 flex-col">
      <ShellModal
        open={apiRequiredOpen}
        onClose={() => setApiRequiredOpen(false)}
        title={t("chat.apiRequiredTitle")}
      >
        <p className="text-sm leading-relaxed text-[var(--kq-color-muted)]">{t("chat.apiRequiredBody")}</p>
        <div className="mt-6 flex flex-wrap justify-end gap-2">
          <button
            type="button"
            className="kq-btn-secondary rounded-[var(--radius-shell-lg)] px-4 py-2 text-sm"
            onClick={() => setApiRequiredOpen(false)}
          >
            {t("chat.apiRequiredClose")}
          </button>
          <button
            type="button"
            className="kq-btn-primary rounded-lg px-4 py-2 text-sm"
            onClick={() => {
              setApiRequiredOpen(false);
              nav("/onboarding/welcome", { replace: true });
            }}
          >
            {t("chat.apiRequiredGoSetup")}
          </button>
        </div>
      </ShellModal>
      <div className="kq-chat-desk">
        <ChatHistoryDrawer
          open={historyOpen}
          sessions={sessions}
          activeSessionId={activeSessionId}
          loading={listLoading}
          onClose={() => setHistoryOpen(false)}
          onNewChat={() => { setHistoryOpen(false); handleNewChat(); }}
          onSelectSession={(id) => { setHistoryOpen(false); handlePickSession(id); }}
          onDeleteSession={handleDelete}
          onOpenScheduledTasks={() => nav("/settings/cron", { state: { cronBackTo: "/chat" } })}
          onOpenWorkspace={() => void invoke("cmd_open_workspace")}
          onExport={() => nav("/export")}
        />

        {/* 单张居中对话纸：没有侧栏，没有并列作用域标签页。 */}
        <section className="kq-chat-paper" aria-label={t("chat.title")}>
          <ChatPaperHeader
            studyHandoff={studyHandoff}
            onOpenHistory={() => setHistoryOpen(true)}
            onReturnStudy={returnToStudy}
          />
          <ChatMessageList
            messages={messages}
            sending={sending}
            sendErr={sendErr}
            progress={progress}
            loadPackageDownloads={loadPackageDownloads}
            pendingInteraction={pendingInteraction}
            onRespondInteraction={onRespondInteraction}
            onOpenLoadPackageSettings={() => nav("/settings/load-packages")}
          />
          <ChatInput
            value={input}
            onChange={setInput}
            onSend={onSend}
            sending={sending}
            pendingAttachments={pendingAttachments}
            onRemoveAttachment={onRemoveAttachment}
            onFilesPicked={onAddFiles}
            onStop={onStopAgent}
            needsModelSetup={needsModelSetup}
            onConfigureModel={() => nav("/settings", { state: { settingsTab: "model" } })}
          />
        </section>

        {/* Report/工作台入口已从 Chat 砍掉（v0.5.0 聚焦 Study）。WorkspacePanel 及其
            PPT 渲染链（pptx/）作为休眠资产保留在树里，产品面不再挂载它。 */}
      </div>
    </AppScaffold>
  );
}
