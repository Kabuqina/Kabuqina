// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useMemo } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Maximize2, PanelLeftOpen, PanelRightOpen } from "lucide-react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { AppScaffold } from "../components/AppScaffold";
import { BootPill } from "../components/BootPill";
import { confirm } from "../lib/confirmDialog";
import { useI18n } from "../lib/i18n";
import { ChatInput } from "./ChatInput";
import { ChatMessageList } from "./ChatMessageList";
import { ChatSidebar } from "./ChatSidebar";
import { WorkspacePanel, type WorkspaceActivity, type WorkspaceItem } from "./WorkspacePanel";
import { runDesktopOrganize } from "./desktop-organizer-api";
import {
  armPendingChatSecretGateBypass,
  armPendingOpenReminderSession,
  getDraftPrompt,
  isFromOnboarding,
  isOpenReminderSession,
  takePendingOpenReminderSession,
  takePendingChatSecretGateBypass,
} from "../lib/chatLocationState";
import { drainDesktopDeliveries } from "../lib/desktopDeliveryFeed";
import { getAllowChatWithoutApi } from "../lib/apiKeyGate";
import { ShellModal } from "../components/ShellModal";
import { clearDraft } from "../lib/store";
import { useHermesReadiness } from "./hooks/useHermesReadiness";
import { useSessions } from "./hooks/useSessions";
import { useChatState } from "./hooks/useChatState";
import { useSendMessage } from "./hooks/useSendMessage";
import { useLoadPackageDownloads } from "./hooks/useLoadPackageDownloads";
import { useWorkbenchLayout } from "./hooks/useWorkbenchLayout";
import { useInFlightTurns } from "./inFlightTurns";
import { type CaptureDonePayload } from "../capture/capture-api";
import type { AgentProgressState } from "./hooks/useAgentProgress";
import type { DeskAttachmentPayload, UiMsg } from "./chat-api";
import { REMINDER_SESSION_ID } from "./reminderSession";

type WorkspaceState = {
  goal: string | null;
  materials: WorkspaceItem[];
  outputs: WorkspaceItem[];
  activeTool: string | null;
  activity: WorkspaceActivity[];
};

const FILE_PATH_RE = /[A-Za-z]:\\[^\r\n`"'<>|]*?\.(?:docx?|xlsx?|pptx?|pdf|md|txt|csv|png|jpe?g|gif|webp|zip|json|html?|py|ts|tsx|js|jsx)\b/gi;
const ATTACHMENT_LINE_RE = /^📎\s*(.+)$/gm;

function compactText(text: string, max = 120): string {
  const oneLine = text.replace(/\s+/g, " ").trim();
  return oneLine.length > max ? `${oneLine.slice(0, max - 3)}...` : oneLine;
}

function fileLabel(pathOrName: string): string {
  return pathOrName.split(/[\\/]/).pop()?.trim() || pathOrName.trim();
}

function pushUnique(items: WorkspaceItem[], seen: Set<string>, item: WorkspaceItem) {
  const key = `${item.label}\n${item.detail ?? ""}`.toLocaleLowerCase();
  if (seen.has(key)) return;
  seen.add(key);
  items.push(item);
}

function extractPaths(text: string): string[] {
  return Array.from(text.matchAll(FILE_PATH_RE), (m) => m[0].trim());
}

function extractAttachmentNames(text: string): string[] {
  return Array.from(text.matchAll(ATTACHMENT_LINE_RE), (m) => m[1]?.trim()).filter(
    (name): name is string => Boolean(name),
  );
}

function buildWorkspaceState(
  messages: UiMsg[],
  pendingAttachments: DeskAttachmentPayload[],
  progress: AgentProgressState | null,
): WorkspaceState {
  const materialSeen = new Set<string>();
  const outputSeen = new Set<string>();
  const materials: WorkspaceItem[] = [];
  const outputs: WorkspaceItem[] = [];

  for (const att of pendingAttachments) {
    pushUnique(materials, materialSeen, {
      id: `pending-${att.name}`,
      label: att.name,
      detail: att.mime || "pending",
    });
  }

  for (const message of messages) {
    if (message.role === "user") {
      for (const att of message.attachments ?? []) {
        pushUnique(materials, materialSeen, {
          id: `sent-attachment-${att.name}`,
          label: att.name,
          detail: att.mime || "attached",
        });
      }
      for (const name of extractAttachmentNames(message.text)) {
        pushUnique(materials, materialSeen, {
          id: `sent-attachment-${name}`,
          label: name,
          detail: "attached",
        });
      }
      for (const path of extractPaths(message.text)) {
        pushUnique(materials, materialSeen, {
          id: `material-${path}`,
          label: fileLabel(path),
          detail: path,
        });
      }
    } else {
      for (const path of extractPaths(message.text)) {
        pushUnique(outputs, outputSeen, {
          id: `output-${path}`,
          label: fileLabel(path),
          detail: path,
        });
      }
    }
  }

  for (const step of progress?.steps ?? []) {
    if (!step.preview) continue;
    for (const path of extractPaths(step.preview)) {
      pushUnique(outputs, outputSeen, {
        id: `progress-output-${step.seq}-${path}`,
        label: fileLabel(path),
        detail: path,
      });
    }
  }

  const latestUser = [...messages].reverse().find((m) => m.role === "user");
  const goal = latestUser
    ? compactText(
        latestUser.text
          .split(/\r?\n/)
          .find((line) => {
            const trimmed = line.trim();
            return trimmed && !trimmed.startsWith("📎");
          }) || latestUser.text,
      )
    : null;

  const runningStep = progress ? [...progress.steps].reverse().find((step) => step.running) : undefined;
  const activeTool = progress?.current_tool ?? runningStep?.tool ?? null;
  const activity =
    progress?.steps.slice(-4).map((step) => ({
      id: `activity-${step.seq}`,
      label: step.tool,
      detail: step.preview ? compactText(step.preview, 56) : undefined,
      running: step.running,
    })) ?? [];

  return { goal, materials: materials.slice(0, 8), outputs: outputs.slice(-8), activeTool, activity };
}

export function ChatPage() {
  const { t, locale } = useI18n();
  const nav = useNavigate();
  const location = useLocation();
  const workbench = useWorkbenchLayout();

  const { hermesReady, hermesWarming, bootErr } = useHermesReadiness();
  const inFlightTurns = useInFlightTurns();
  const { sessions, listLoading, loadSessions, deleteSession } = useSessions({
    hermesReady: hermesReady && !hermesWarming,
  });
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
  });
  const loadPackageDownloads = useLoadPackageDownloads(hermesReady && !hermesWarming);
  const workspace = useMemo(
    () => buildWorkspaceState(messages, pendingAttachments, progress),
    [messages, pendingAttachments, progress],
  );

  useEffect(() => {
    if (isOpenReminderSession(location.state)) {
      armPendingOpenReminderSession();
      nav("/chat", { replace: true, state: {} });
      return;
    }
    if (!takePendingOpenReminderSession()) {
      return;
    }
    if (!hermesReady || hermesWarming) {
      armPendingOpenReminderSession();
      return;
    }
    void openReminderSession(t("cron.reminderLogEmpty"));
  }, [hermesReady, hermesWarming, location.state, nav, openReminderSession, t]);

  useEffect(() => {
    if (isFromOnboarding(location.state)) {
      armPendingChatSecretGateBypass();
      clearDraft();
      nav("/chat", { replace: true, state: {} });
      return;
    }
    if (takePendingChatSecretGateBypass()) {
      return;
    }
    const gate = async () => {
      try {
        if (getAllowChatWithoutApi()) return;
        const ok = await invoke<boolean>("cmd_has_secret");
        if (ok) return;
        nav("/onboarding/welcome", { replace: true });
      } catch {
        nav("/onboarding/welcome", { replace: true });
      }
    };
    void gate();
  }, [nav, location.state]);

  useEffect(() => {
    const draft = getDraftPrompt(location.state);
    if (!draft) return;
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
    if (!hermesReady || hermesWarming) {
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
  }, [activeSessionId, hermesReady, hermesWarming, loadSessions, refreshActiveThread]);

  const handleOrganizeDesktop = useCallback(async () => {
    const now = Date.now();
    const pendingId = `desktop-organizer-assistant-${now}`;

    setMessages((prev) => [
      ...prev,
      {
        id: `desktop-organizer-user-${now}`,
        role: "user" as const,
        text: t("desktopOrganizer.userAction"),
        timestamp: now / 1000,
      },
      {
        id: pendingId,
        role: "assistant" as const,
        text: t("desktopOrganizer.running"),
        timestamp: now / 1000,
      },
    ]);

    try {
      const result = await runDesktopOrganize(locale);
      setMessages((prev) =>
        prev.map((message) =>
          message.id === pendingId
            ? {
                ...message,
                text: result.message || t("desktopOrganizer.doneOneClick", { count: result.movedCount }),
              }
            : message,
        ),
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e || "");
      setMessages((prev) =>
        prev.map((message) =>
          message.id === pendingId
            ? {
                ...message,
                text: t("desktopOrganizer.runFailed", { msg }),
              }
            : message,
        ),
      );
    }
  }, [locale, setMessages, t]);

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
    } catch (err) {
      console.error(err);
      setSendErr(t("chat.errDelete"));
    }
  };

  const openLeftRail = () => {
    if (workbench.focusMode && workbench.leftOpen) {
      workbench.toggleFocusMode();
      return;
    }
    workbench.toggleLeft();
  };

  const openWorkspace = () => {
    if (workbench.focusMode && workbench.rightOpen) {
      workbench.toggleFocusMode();
      return;
    }
    workbench.toggleRight();
  };

  if (bootErr) {
    return (
      <AppScaffold surface="chat" className="flex h-full flex-col items-center justify-center px-6 text-center">
        <p className="max-w-md whitespace-pre-wrap text-left text-sm text-zinc-600 dark:text-zinc-400">
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

  if (!hermesReady || hermesWarming) {
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
        <p className="text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">{t("chat.apiRequiredBody")}</p>
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
      <div className="flex min-h-0 flex-1">
        {workbench.showLeftRail && (
          <ChatSidebar
            sessions={sessions}
            activeSessionId={activeSessionId}
            loading={listLoading}
            collapsed={!workbench.leftOpen || workbench.isNarrow}
            onToggleCollapsed={workbench.toggleLeft}
            onNewChat={onNewChat}
            onOpenScheduledTasks={() => nav("/settings/cron", { state: { cronBackTo: "/chat" } })}
            onOpenWorkspace={() => void invoke("cmd_open_workspace")}
            onOrganizeDesktop={handleOrganizeDesktop}
            onExport={() => nav("/export")}
            onSelectSession={onPickSession}
            onDeleteSession={handleDelete}
          />
        )}
        <main className="flex min-w-0 flex-1 flex-col">
          <div className="kq-chat-topbar flex h-11 shrink-0 items-center justify-between border-b px-3">
            <div className="flex min-w-0 items-center gap-2">
              {!workbench.showLeftRail && (
                <button
                  type="button"
                  onClick={openLeftRail}
                  className="kq-soft-icon-btn inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg px-0 transition"
                  aria-label={t("chat.leftRailExpand")}
                  title={t("chat.leftRailExpand")}
                >
                  <PanelLeftOpen className="h-4 w-4" />
                </button>
              )}
            </div>
            <div className="flex items-center gap-1">
              {!workbench.showRightPanel && (
                <button
                  type="button"
                  onClick={openWorkspace}
                  className="kq-soft-icon-btn inline-flex h-8 w-8 items-center justify-center rounded-lg px-0 transition"
                  aria-label={t("chat.workspaceExpand")}
                  title={t("chat.workspaceExpand")}
                >
                  <PanelRightOpen className="h-4 w-4" />
                </button>
              )}
              <button
                type="button"
                onClick={workbench.toggleFocusMode}
                className="kq-soft-icon-btn inline-flex h-8 w-8 items-center justify-center rounded-lg px-0 transition"
                aria-label={workbench.focusMode ? t("chat.focusExit") : t("chat.focusEnter")}
                title={workbench.focusMode ? t("chat.focusExit") : t("chat.focusEnter")}
              >
                <Maximize2 className="h-4 w-4" />
              </button>
            </div>
          </div>
          <ChatMessageList
            messages={messages}
          sending={sending}
          sendErr={sendErr}
          progress={progress}
          loadPackageDownloads={loadPackageDownloads}
          pendingInteraction={pendingInteraction}
          onRespondInteraction={onRespondInteraction}
          onPickSuggestion={setInput}
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
          />
        </main>
        {workbench.showRightPanel && (
          <WorkspacePanel
            onCollapse={workbench.toggleRight}
            onStartPrompt={setInput}
            goal={workspace.goal}
            materials={workspace.materials}
            outputs={workspace.outputs}
            activeTool={workspace.activeTool}
            activity={workspace.activity}
          />
        )}
      </div>
    </AppScaffold>
  );
}
