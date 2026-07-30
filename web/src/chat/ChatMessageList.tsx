// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useRef, useState } from "react";
import { BookOpen, Check, Pencil, RefreshCw } from "lucide-react";
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
  compact?: boolean;
  emptyLabel?: string;
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

function AgentTextInteractionCard({
  interaction,
  onRespond,
}: {
  interaction: PendingAgentInteraction;
  onRespond?: (action: string, text?: string, data?: Record<string, unknown>) => Promise<void>;
}) {
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    const value = answer.trim();
    if (!onRespond || busy || !value) return;
    setBusy(true);
    try {
      await onRespond("submit", value);
    } finally {
      setBusy(false);
    }
  };
  return (
    <AssistantStreamShell>
      <form
        className="kq-chat-bubble-assistant rounded-2xl rounded-tl-sm px-4 py-3 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg-subtle)]"
        onSubmit={(event) => { event.preventDefault(); void submit(); }}
      >
        <label className="block text-sm font-semibold text-[var(--kq-color-strong)]" htmlFor={`interaction-${interaction.id}`}>
          {interaction.question || "小娜需要你补充一点信息"}
        </label>
        <textarea
          id={`interaction-${interaction.id}`}
          value={answer}
          onChange={(event) => setAnswer(event.currentTarget.value)}
          className="mt-3 min-h-28 w-full rounded-lg border border-[#e8e0ed] bg-white/80 p-3 text-sm text-[var(--kq-color-strong)]"
          placeholder="在这里回答小娜"
          autoFocus
        />
        <div className="mt-3 flex justify-end">
          <button type="submit" disabled={busy || !answer.trim()} className="kq-quick-action rounded-lg px-3 py-2 text-sm">
            {busy ? "正在提交…" : "提交回答"}
          </button>
        </div>
      </form>
    </AssistantStreamShell>
  );
}

function AgentChoiceInteractionCard({
  interaction,
  onRespond,
}: {
  interaction: PendingAgentInteraction;
  onRespond?: (action: string, text?: string, data?: Record<string, unknown>) => Promise<void>;
}) {
  const [otherOpen, setOtherOpen] = useState(false);
  const [other, setOther] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (value: string) => {
    const answer = value.trim();
    if (!onRespond || busy || !answer) return;
    setBusy(true);
    try {
      await onRespond("submit", answer);
    } finally {
      setBusy(false);
    }
  };
  return (
    <AssistantStreamShell>
      <div className="kq-chat-bubble-assistant rounded-2xl rounded-tl-sm px-4 py-3 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg-subtle)]">
        <p className="text-sm font-semibold text-[var(--kq-color-strong)]">{interaction.question || "请选择"}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {interaction.choices.map((choice) => (
            <button key={choice} type="button" disabled={busy} onClick={() => void submit(choice)} className="kq-quick-action rounded-lg px-3 py-2 text-sm">
              {choice}
            </button>
          ))}
          <button type="button" disabled={busy} onClick={() => setOtherOpen(true)} className="kq-quick-action rounded-lg px-3 py-2 text-sm">
            其他回答
          </button>
        </div>
        {otherOpen ? (
          <form className="mt-3" onSubmit={(event) => { event.preventDefault(); void submit(other); }}>
            <label className="sr-only" htmlFor={`interaction-other-${interaction.id}`}>其他回答</label>
            <textarea
              id={`interaction-other-${interaction.id}`}
              value={other}
              onChange={(event) => setOther(event.currentTarget.value)}
              className="min-h-24 w-full rounded-lg border border-[#e8e0ed] bg-white/80 p-3 text-sm text-[var(--kq-color-strong)]"
              autoFocus
            />
            <div className="mt-2 flex justify-end">
              <button type="submit" disabled={busy || !other.trim()} className="kq-quick-action rounded-lg px-3 py-2 text-sm">提交回答</button>
            </div>
          </form>
        ) : null}
      </div>
    </AssistantStreamShell>
  );
}

function EmptyState() {
  return (
    <div className="kq-empty-state flex min-h-0 w-full flex-1 flex-col items-center justify-center px-6 py-3 sm:py-7">
      <div className="relative -translate-y-1">
        <div
          className="pointer-events-none absolute left-1/2 top-1/2 h-40 w-40 -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{ background: "radial-gradient(circle, rgba(232,223,240,0.5) 0%, transparent 70%)" }}
        />
        <img
          src={ART_ASSETS.boot}
          alt="Kabuqina chat hero — cup on gingham coaster"
          className="kq-float relative h-auto w-48 select-none"
          style={{ filter: "drop-shadow(0 6px 20px rgba(90,74,106,0.12))", animation: "kq-float 3.4s ease-in-out infinite" }}
          width={1280}
          height={640}
          decoding="async"
          draggable={false}
        />
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
  compact = false,
  emptyLabel,
}: ChatMessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    requestAnimationFrame(() => {
      if (typeof bottomRef.current?.scrollIntoView === "function") {
        bottomRef.current.scrollIntoView({ behavior: "smooth" });
      }
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
        compact && "kq-chat-scroll--compact",
        isEmpty && "flex min-h-0 flex-col"
      )}
    >
      {isEmpty ? (
        compact ? (
          <div className="kq-chat-compact-empty">
            <p>{emptyLabel || "从此刻卡住的地方开始问。"}</p>
          </div>
        ) : <EmptyState />
      ) : (
        <div className={cn(
          "mx-auto max-w-3xl space-y-5 px-4 py-6 sm:space-y-6 sm:px-5",
          compact && "kq-chat-compact-messages",
        )}>
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
            ) : pendingInteraction.kind === "text" ? (
              <AgentTextInteractionCard interaction={pendingInteraction} onRespond={onRespondInteraction} />
            ) : pendingInteraction.kind === "choice" ? (
              <AgentChoiceInteractionCard interaction={pendingInteraction} onRespond={onRespondInteraction} />
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
