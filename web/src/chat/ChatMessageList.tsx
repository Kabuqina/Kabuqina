// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useRef, useState } from "react";
import { AlarmClock, BookOpen, Check, FolderOpen, PenLine, Pencil, RefreshCw } from "lucide-react";
import { useI18n } from "../lib/i18n";
import type { LoadPackageStatus, PendingAgentInteraction, UiMsg } from "./chat-api";
import { AgentProgress } from "./AgentProgress";
import { ChatMessage } from "./ChatMessage";
import { OutlineReviewModal } from "./OutlineReviewModal";
import { AssistantAvatar } from "../components/AssistantAvatar";
import { ART_ASSETS } from "../lib/artAssets";
import { cn } from "../lib/cn";
import { shouldDisplayAgentProgress, type AgentProgressState } from "./hooks/useAgentProgress";
import { formatBytes, packageTitle } from "../advanced/settings/loadPackageUi";
import { hasVisibleAssistantStreamText } from "./inFlightTurnUtils";

interface ChatMessageListProps {
  messages: UiMsg[];
  sending?: boolean;
  sendErr?: string | null;
  progress?: AgentProgressState | null;
  loadPackageDownloads?: LoadPackageStatus[];
  pendingInteraction?: PendingAgentInteraction | null;
  onRespondInteraction?: (action: string, text?: string, data?: Record<string, unknown>) => Promise<void>;
  onOpenLoadPackageSettings?: () => void;
  onPickSuggestion?: (prompt: string) => void;
}

function AssistantStreamShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 justify-start">
      <AssistantAvatar labeled={false} />
      <div className="kq-chat-assistant-column">{children}</div>
    </div>
  );
}

function TypingIndicator() {
  const { t } = useI18n();
  return (
    <AssistantStreamShell>
      <div className="kq-chat-bubble-assistant rounded-2xl rounded-tl-sm px-4 py-3 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg-subtle)]">
        <p className="mb-2 text-xs text-[var(--kq-color-muted)]">
          {t("chat.typingStatus")}…
        </p>
        <div className="flex h-4 items-center gap-1" aria-hidden>
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--kq-color-primary)] dark:bg-[var(--kq-hover-bg-strong)]" style={{ animationDelay: "0ms" }} />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--kq-color-primary)] dark:bg-[var(--kq-hover-bg-strong)]" style={{ animationDelay: "150ms" }} />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--kq-color-primary)] dark:bg-[var(--kq-hover-bg-strong)]" style={{ animationDelay: "300ms" }} />
        </div>
      </div>
    </AssistantStreamShell>
  );
}

function loadPackagePhaseLabel(phase: string | undefined, t: (path: string) => string): string {
  if (!phase) return "";
  const key = `settings.loadPackagePhase.${phase}`;
  const value = t(key);
  return value === key ? phase : value;
}

function LoadPackageDownloadProgress({
  packages,
  onOpenSettings,
}: {
  packages: LoadPackageStatus[];
  onOpenSettings?: () => void;
}) {
  const { t } = useI18n();
  if (packages.length === 0) return null;
  const loadPackageFinished = packages.every((pkg) => pkg.job?.status !== "running");
  const hasError = packages.some((pkg) => pkg.job?.status === "error");
  return (
    <AssistantStreamShell>
      <div className="kq-chat-bubble-assistant rounded-2xl rounded-tl-sm px-4 py-3 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg-subtle)]">
        <p className="mb-3 text-xs font-medium text-[var(--kq-color-strong)] dark:text-[var(--kq-color-strong)]">
          {loadPackageFinished
            ? hasError
              ? t("settings.loadPackageFailed")
              : t("settings.loadPackageFinished")
            : t("settings.loadPackageChatTitle")}
        </p>
        <div className="space-y-3">
          {packages.map((pkg) => {
            const job = pkg.job;
            const total = job?.totalBytes || pkg.sizeMb * 1024 * 1024;
            const downloaded = job?.downloadedBytes || (job?.status === "done" ? total : 0);
            const percent = job?.percent ?? (total ? Math.floor(downloaded * 100 / total) : 0);
            return (
              <div key={pkg.id}>
                <div className="flex items-center justify-between gap-3 text-xs text-[var(--kq-color-muted)] dark:text-[var(--kq-color-muted)]">
                  <span className="truncate">{packageTitle(pkg, t)}</span>
                  <span>{percent}%</span>
                </div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[var(--kq-hover-bg-strong)]">
                  <div
                    className="h-full rounded-full bg-[var(--kq-color-primary)] transition-[width]"
                    style={{ width: `${Math.max(4, Math.min(100, percent))}%` }}
                  />
                </div>
                <p className="mt-1 text-xs text-[var(--kq-color-muted)] dark:text-[var(--kq-color-muted)]">
                  {loadPackagePhaseLabel(job?.phase, t)} · {formatBytes(downloaded)} / {formatBytes(total)}
                </p>
                {job?.status === "error" && job.error ? (
                  <p className="mt-1 text-xs text-red-600 dark:text-red-400">{job.error}</p>
                ) : null}
              </div>
            );
          })}
        </div>
        {onOpenSettings ? (
          <button
            type="button"
            onClick={onOpenSettings}
            className="mt-3 text-xs font-medium text-sky-700 underline-offset-2 hover:underline dark:text-sky-300"
          >
            {t("settings.loadPackageChatOpenSettings")}
          </button>
        ) : null}
      </div>
    </AssistantStreamShell>
  );
}

function PptxRenderCard({
  interaction,
  onRespond,
}: {
  interaction: PendingAgentInteraction;
  onRespond?: (action: string, text?: string, data?: Record<string, unknown>) => Promise<void>;
}) {
  const [status, setStatus] = useState<"rendering" | "done" | "error">("rendering");
  const [errMsg, setErrMsg] = useState("");
  const startedRef = useRef(false);
  const respondedRef = useRef(false);

  useEffect(() => {
    // Render exactly once per interaction; the agent turn is blocked waiting on
    // a response and will hit the 300s interaction timeout if we never reply.
    //
    // We MUST NOT abort the reply on effect cleanup: under React StrictMode the
    // effect runs mount -> cleanup -> mount, and `startedRef` (preserved across
    // the simulated remount) makes the second mount a no-op. A `cancelled` flag
    // set by the first cleanup would then suppress the only reply, leaving the
    // agent to time out (`pptx_render_cancelled`). So once a render starts we
    // always report its outcome exactly once, guarded by `respondedRef`.
    if (startedRef.current || !onRespond) return;
    startedRef.current = true;
    (async () => {
      try {
        const { renderDeckToBase64 } = await import("./pptx/renderDeck");
        const deck = (interaction.artifact?.deck ?? {}) as import("./pptx/renderDeck").DeckSpec;
        const { base64, slideCount, audit } = await renderDeckToBase64(deck);
        if (respondedRef.current) return;
        respondedRef.current = true;
        await onRespond("rendered", "", { pptx_base64: base64, slide_count: slideCount, pptx_render_audit: audit });
        setStatus("done");
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setErrMsg(msg);
        setStatus("error");
        if (respondedRef.current) return;
        respondedRef.current = true;
        try {
          await onRespond("error", `PptxGenJS 渲染失败：${msg}`, {});
        } catch {
          /* ignore secondary failure */
        }
      }
    })();
  }, [interaction.id, interaction.artifact, onRespond]);

  return (
    <AssistantStreamShell>
      <div className="kq-chat-bubble-assistant rounded-2xl rounded-tl-sm px-4 py-3 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg-subtle)]">
        <div className="flex items-center gap-2 text-sm font-semibold text-[var(--kq-color-strong)] dark:text-[var(--kq-color-strong)]">
          <BookOpen className="h-4 w-4" aria-hidden />
          {interaction.question || "正在生成 PPT…"}
        </div>
        {status === "rendering" ? (
          <p className="mt-2 text-xs text-[var(--kq-color-muted)] dark:text-[var(--kq-color-muted)]">
            正在用 PptxGenJS 渲染演示文稿，请稍候…
          </p>
        ) : null}
        {status === "done" ? (
          <p className="mt-2 text-xs text-emerald-600 dark:text-emerald-400">演示文稿已生成，正在保存到工作区。</p>
        ) : null}
        {status === "error" ? (
          <p className="mt-2 text-xs text-red-600 dark:text-red-400">PptxGenJS 渲染失败：{errMsg}</p>
        ) : null}
      </div>
    </AssistantStreamShell>
  );
}

function AgentInteractionCard({
  interaction,
  onRespond,
}: {
  interaction: PendingAgentInteraction;
  onRespond?: (action: string, text?: string, data?: Record<string, unknown>) => Promise<void>;
}) {
  const [refineOpen, setRefineOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [draft, setDraft] = useState(interaction.artifact?.content || "");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (action: string, text = draft, data?: Record<string, unknown>) => {
    if (!onRespond || busy) return;
    setBusy(true);
    try {
      await onRespond(action, text, data);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <AssistantStreamShell>
        <div className="kq-chat-bubble-assistant rounded-2xl rounded-tl-sm px-4 py-3 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg-subtle)]">
          <div className="text-sm font-semibold text-[var(--kq-color-strong)] dark:text-[var(--kq-color-strong)]">
            {interaction.question || "请确认"}
          </div>
          {interaction.artifact?.content ? (
            <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap rounded-lg border border-[#e8e0ed] bg-white/70 p-3 text-sm leading-relaxed text-zinc-800 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)] dark:text-[var(--kq-color-strong)]">
              {interaction.artifact.content}
            </pre>
          ) : null}
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" disabled={busy} onClick={() => submit("approve", draft)} className="kq-quick-action inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm">
              <Check className="h-4 w-4" aria-hidden />
              通过
            </button>
            <button type="button" disabled={busy} onClick={() => setRefineOpen(true)} className="kq-quick-action inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm">
              <RefreshCw className="h-4 w-4" aria-hidden />
              补充要求
            </button>
            <button type="button" disabled={busy} onClick={() => setEditOpen(true)} className="kq-quick-action inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm">
              <Pencil className="h-4 w-4" aria-hidden />
              自行编辑
            </button>
          </div>
        </div>
      </AssistantStreamShell>

      {refineOpen ? (
        <div className="fixed inset-0 z-[120] flex items-end justify-center bg-black/30 p-4 sm:items-center" role="presentation">
          <div className="w-full max-w-lg rounded-xl bg-white p-4 shadow-xl dark:bg-[var(--kq-glass-bg)]">
            <h3 className="text-base font-semibold text-[var(--kq-color-strong)]">补充要求</h3>
            <textarea value={note} onChange={(e) => setNote(e.target.value)} className="mt-3 h-32 w-full rounded-lg border border-zinc-300 p-3 text-sm dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)] dark:text-[var(--kq-color-strong)]" autoFocus />
            <div className="mt-3 flex justify-end gap-2">
              <button type="button" onClick={() => setRefineOpen(false)} className="rounded-lg px-3 py-2 text-sm text-[var(--kq-color-ink)]">取消</button>
              <button type="button" onClick={() => submit("refine", note, { outline: draft })} className="kq-quick-action rounded-lg px-3 py-2 text-sm">重新生成</button>
            </div>
          </div>
        </div>
      ) : null}

      {editOpen ? (
        <div className="fixed inset-0 z-[120] flex items-end justify-center bg-black/30 p-4 sm:items-center" role="presentation">
          <div className="w-full max-w-2xl rounded-xl bg-white p-4 shadow-xl dark:bg-[var(--kq-glass-bg)]">
            <h3 className="text-base font-semibold text-[var(--kq-color-strong)]">自行编辑</h3>
            <textarea value={draft} onChange={(e) => setDraft(e.target.value)} className="mt-3 h-80 w-full rounded-lg border border-zinc-300 p-3 font-mono text-sm dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)] dark:text-[var(--kq-color-strong)]" autoFocus />
            <div className="mt-3 flex justify-end gap-2">
              <button type="button" onClick={() => setEditOpen(false)} className="rounded-lg px-3 py-2 text-sm text-[var(--kq-color-ink)]">取消</button>
              <button type="button" onClick={() => submit("edit", draft)} className="kq-quick-action rounded-lg px-3 py-2 text-sm">保存并生成</button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

function EmptyState({
  onPickSuggestion,
}: {
  onPickSuggestion?: (prompt: string) => void;
}) {
  const { t, locale } = useI18n();
  const brand = t("brand");
  const productName = t("productName");
  const greeting = t("chat.greeting", { name: brand });
  const greetingParts = greeting.split(brand);
  const actions =
    locale === "zh"
      ? [
          { label: "陪我复习一会儿", prompt: "陪我复习一会儿，帮我把今天要学的内容拆成小步骤。", icon: BookOpen, iconClass: "kq-color-icon-book" },
          { label: "整理思路", prompt: "帮我整理一下现在脑子里的想法，先列出重点和下一步。", icon: FolderOpen, iconClass: "kq-color-icon-folder" },
          { label: "提醒我休息", prompt: "提醒我 30 分钟后休息一下", icon: AlarmClock, iconClass: "kq-color-icon-alarm" },
          { label: "写一段消息", prompt: "帮我把这段话写得更自然：", icon: PenLine, iconClass: "kq-color-icon-pen" },
        ]
      : [
          { label: "Study with me", prompt: "Study with me for a while and split this into small steps.", icon: BookOpen, iconClass: "kq-color-icon-book" },
          { label: "Organize thoughts", prompt: "Help me organize my current thoughts into priorities and next steps.", icon: FolderOpen, iconClass: "kq-color-icon-folder" },
          { label: "Set a reminder", prompt: "Remind me to take a break in 30 minutes", icon: AlarmClock, iconClass: "kq-color-icon-alarm" },
          { label: "Write a message", prompt: "Make this message sound more natural:", icon: PenLine, iconClass: "kq-color-icon-pen" },
        ];
  return (
    <div className="kq-empty-state flex min-h-0 w-full flex-1 flex-col items-center justify-center px-6 py-3 sm:py-7">
      <div className="flex w-full max-w-xl -translate-y-1 flex-col items-center text-center">
        <div className="kq-empty-hero mb-2 flex flex-col items-center sm:mb-3">
          {/* Mascot with soft glow */}
          <div className="relative mb-1.5">
            <div
              className="pointer-events-none absolute left-1/2 top-1/2 h-40 w-40 -translate-x-1/2 -translate-y-1/2 rounded-full"
              style={{ background: "radial-gradient(circle, rgba(232,223,240,0.5) 0%, transparent 70%)" }}
            />
            <img
              src={ART_ASSETS.boot}
              alt="Kabuqina chat hero — cup on gingham coaster"
              className="kq-float relative w-48 h-auto select-none"
              style={{ filter: "drop-shadow(0 6px 20px rgba(90,74,106,0.12))", animation: "kq-float 3.4s ease-in-out infinite" }}
              width={1280}
              height={640}
              decoding="async"
              draggable={false}
            />
          </div>
          <h1 className="kq-empty-title">{productName}</h1>
          <div className="mt-2.5 flex items-center gap-2.5 text-sm text-[var(--kq-color-muted)]">
            <span className="kq-hero-line" aria-hidden />
            <span className="kq-hero-heart text-xs" aria-hidden>♡</span>
            <span style={{ letterSpacing: "0.02em" }}>
              {locale === "zh" ? "慢慢来，小娜陪你整理思路" : `${greetingParts[0]}${brand}${greetingParts[1]}`}
            </span>
            <span className="kq-hero-line" aria-hidden />
          </div>
        </div>
        <div
          className="mt-7 grid w-full gap-2.5"
          style={{ gridTemplateColumns: "1fr 1fr", maxWidth: "380px" }}
          aria-label={t("chat.emptyActionsLabel")}
        >
          {actions.map((action, i) => {
            const Icon = action.icon;
            return (
              <button
                key={action.label}
                type="button"
                onClick={() => {
                  if ("prompt" in action && action.prompt) {
                    onPickSuggestion?.(action.prompt);
                  }
                }}
                className={cn(
                  "kq-empty-action kq-fade-up inline-flex h-auto min-w-0 items-center justify-center gap-2 rounded-xl border px-3.5 py-2.5 text-sm font-medium",
                  "text-[var(--kq-color-ink)] active:scale-[0.99]",
                  "dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)] dark:text-[var(--kq-color-ink)]",
                  "dark:hover:border-sky-700 dark:hover:bg-sky-950/40 dark:hover:text-sky-100"
                )}
                style={{ animationDelay: `${i * 0.06}s`, animationFillMode: "both" }}
              >
                <Icon
                  className={cn("h-[15px] w-[15px] shrink-0", action.iconClass)}
                  strokeWidth={2.25}
                  aria-hidden
                />
                <span>{action.label}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function ChatMessageList({
  messages,
  sending = false,
  sendErr,
  progress,
  loadPackageDownloads = [],
  pendingInteraction,
  onRespondInteraction,
  onOpenLoadPackageSettings,
  onPickSuggestion,
}: ChatMessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    requestAnimationFrame(() => {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    });
  }, [messages, sending, progress?.nextSeq, progress?.status, pendingInteraction?.id]);

  const isEmpty = messages.length === 0 && !sendErr;
  const pendingAssistant = messages.find((m) => m.id === "pending-assistant");
  const completedMessages = messages.filter((m) => m.id !== "pending-assistant");
  const pendingVisibleText = hasVisibleAssistantStreamText(pendingAssistant?.text ?? "");
  const showAgentProgress = shouldDisplayAgentProgress(progress);

  return (
    <div
      className={cn(
        "kq-chat-scroll min-h-0 flex-1 overflow-y-auto",
        isEmpty && "flex min-h-0 flex-col"
      )}
    >
      {isEmpty ? (
        <EmptyState onPickSuggestion={onPickSuggestion} />
      ) : (
        <div className="mx-auto max-w-3xl space-y-5 px-4 py-6 sm:space-y-6 sm:px-5">
          {completedMessages.map((m) => (
            <ChatMessage
              key={m.id}
              role={m.role}
              text={m.text}
              attachments={m.attachments}
              model={m.model}
              timestamp={m.timestamp}
              streaming={false}
            />
          ))}
          {showAgentProgress && (
            <AssistantStreamShell>
              <AgentProgress progress={progress ?? null} />
            </AssistantStreamShell>
          )}
          <LoadPackageDownloadProgress packages={loadPackageDownloads} onOpenSettings={onOpenLoadPackageSettings} />
          {pendingInteraction ? (
            pendingInteraction.kind === "pptx_render" ? (
              <PptxRenderCard key={pendingInteraction.id} interaction={pendingInteraction} onRespond={onRespondInteraction} />
            ) : pendingInteraction.kind === "outline_review" ? (
              <>
                <AssistantStreamShell>
                  <div className="kq-chat-bubble-assistant rounded-2xl rounded-tl-sm px-4 py-3 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg-subtle)]">
                    <div className="text-sm font-semibold text-[var(--kq-color-strong)] dark:text-[var(--kq-color-strong)]">
                      {pendingInteraction.question || "请审阅 PPT 大纲"}
                    </div>
                    <p className="mt-2 text-xs text-[var(--kq-color-muted)]">
                      已弹出审阅窗口，请在窗口中确认或修改后继续生成。
                    </p>
                  </div>
                </AssistantStreamShell>
                <OutlineReviewModal interaction={pendingInteraction} onRespond={onRespondInteraction} />
              </>
            ) : (
              <AgentInteractionCard interaction={pendingInteraction} onRespond={onRespondInteraction} />
            )
          ) : null}
          {pendingAssistant && pendingVisibleText && (
            <ChatMessage
              key={pendingAssistant.id}
              role={pendingAssistant.role}
              text={pendingAssistant.text}
              attachments={pendingAssistant.attachments}
              model={pendingAssistant.model}
              timestamp={pendingAssistant.timestamp}
              streaming={sending}
            />
          )}
          {sending && !showAgentProgress && !pendingVisibleText && <TypingIndicator />}
          {sendErr && (
            <div className="hd-semantic-error rounded-[var(--radius-shell-lg)] px-3 py-2 text-sm">
              {sendErr}
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}
