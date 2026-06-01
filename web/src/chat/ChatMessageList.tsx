// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useRef, useState } from "react";
import { AlarmClock, BookOpen, Check, FolderOpen, PenLine, Pencil, RefreshCw } from "lucide-react";
import { useI18n } from "../lib/i18n";
import type { PendingAgentInteraction, UiMsg } from "./chat-api";
import { AgentProgress } from "./AgentProgress";
import { ChatMessage } from "./ChatMessage";
import { AssistantAvatar } from "../components/AssistantAvatar";
import { cn } from "../lib/cn";
import type { AgentProgressState } from "./hooks/useAgentProgress";

interface ChatMessageListProps {
  messages: UiMsg[];
  sending?: boolean;
  sendErr?: string | null;
  progress?: AgentProgressState | null;
  pendingInteraction?: PendingAgentInteraction | null;
  onRespondInteraction?: (action: string, text?: string, data?: Record<string, unknown>) => Promise<void>;
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
      <div className="kq-chat-bubble-assistant rounded-2xl rounded-tl-sm px-4 py-3 dark:border-zinc-700/80 dark:bg-zinc-800/90">
        <p className="mb-2 text-xs text-zinc-400 dark:text-zinc-500">
          {t("chat.typingStatus")}…
        </p>
        <div className="flex h-4 items-center gap-1" aria-hidden>
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--kq-color-primary)] dark:bg-zinc-600" style={{ animationDelay: "0ms" }} />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--kq-color-primary)] dark:bg-zinc-600" style={{ animationDelay: "150ms" }} />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--kq-color-primary)] dark:bg-zinc-600" style={{ animationDelay: "300ms" }} />
        </div>
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
        <div className="kq-chat-bubble-assistant rounded-2xl rounded-tl-sm px-4 py-3 dark:border-zinc-700/80 dark:bg-zinc-800/90">
          <div className="text-sm font-semibold text-[var(--kq-color-strong)] dark:text-zinc-100">
            {interaction.question || "请确认"}
          </div>
          {interaction.artifact?.content ? (
            <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap rounded-lg border border-[#e8e0ed] bg-white/70 p-3 text-sm leading-relaxed text-zinc-800 dark:border-zinc-700 dark:bg-zinc-950/40 dark:text-zinc-100">
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
          <div className="w-full max-w-lg rounded-xl bg-white p-4 shadow-xl dark:bg-zinc-900">
            <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">补充要求</h3>
            <textarea value={note} onChange={(e) => setNote(e.target.value)} className="mt-3 h-32 w-full rounded-lg border border-zinc-300 p-3 text-sm dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100" autoFocus />
            <div className="mt-3 flex justify-end gap-2">
              <button type="button" onClick={() => setRefineOpen(false)} className="rounded-lg px-3 py-2 text-sm text-zinc-600 dark:text-zinc-300">取消</button>
              <button type="button" onClick={() => submit("refine", note, { outline: draft })} className="kq-quick-action rounded-lg px-3 py-2 text-sm">重新生成</button>
            </div>
          </div>
        </div>
      ) : null}

      {editOpen ? (
        <div className="fixed inset-0 z-[120] flex items-end justify-center bg-black/30 p-4 sm:items-center" role="presentation">
          <div className="w-full max-w-2xl rounded-xl bg-white p-4 shadow-xl dark:bg-zinc-900">
            <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">自行编辑</h3>
            <textarea value={draft} onChange={(e) => setDraft(e.target.value)} className="mt-3 h-80 w-full rounded-lg border border-zinc-300 p-3 font-mono text-sm dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100" autoFocus />
            <div className="mt-3 flex justify-end gap-2">
              <button type="button" onClick={() => setEditOpen(false)} className="rounded-lg px-3 py-2 text-sm text-zinc-600 dark:text-zinc-300">取消</button>
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
  const wordmarkBase =
    locale === "zh" ? "/kabuqina_logo_chinese" : "/kabuqina_logo_english";
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
    <div className="kq-empty-state flex min-h-0 w-full flex-1 flex-col items-center justify-center px-6 py-8 sm:py-10">
      <div className="flex w-full max-w-3xl -translate-y-1 flex-col items-center text-center">
        <div className="kq-empty-hero mb-7 flex flex-col items-center sm:mb-8">
          <picture className="sr-only">
            <source type="image/avif" srcSet={`${wordmarkBase}.avif`} />
            <source type="image/webp" srcSet={`${wordmarkBase}.webp`} />
            <img src={`${wordmarkBase}.webp`} alt={productName} width={260} height={80} decoding="async" />
          </picture>
          <h1 className="kq-empty-title">{productName}</h1>
          <p className="kq-empty-subtitle mt-4 text-base sm:text-lg">
            <span className="kq-hero-line" aria-hidden />
            <span className="kq-hero-heart" aria-hidden>♡</span>
            <span>{locale === "zh" ? "慢慢来，小娜陪你整理思路" : `${greetingParts[0]}${brand}${greetingParts[1]}`}</span>
            <span className="kq-hero-line" aria-hidden />
          </p>
          <img
            src="/kabuqina_boot.svg"
            alt="Kabuqina chat hero — cup on gingham coaster"
            className="w-64 h-auto select-none"
            width={1280}
            height={640}
            decoding="async"
            draggable={false}
          />
        </div>
        <div
          className="mt-3 grid w-full max-w-2xl grid-cols-[repeat(auto-fit,minmax(10.5rem,1fr))] gap-2 justify-items-stretch sm:max-w-3xl"
          aria-label={t("chat.emptyActionsLabel")}
        >
          {actions.map((action) => {
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
                  "kq-empty-action inline-flex h-10 min-w-0 items-center justify-center gap-2 rounded-xl px-3 text-sm font-medium transition",
                  "text-[var(--kq-color-ink)] active:scale-[0.99]",
                  "dark:border-zinc-700 dark:bg-zinc-900/70 dark:text-zinc-200",
                  "dark:hover:border-sky-700 dark:hover:bg-sky-950/40 dark:hover:text-sky-100"
                )}
              >
                <Icon
                  className={cn("kq-empty-action-icon h-4 w-4 shrink-0", action.iconClass)}
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
  pendingInteraction,
  onRespondInteraction,
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
  const pendingVisibleText = !!pendingAssistant?.text.trim().replace(/^[.…]+$/, "");

  return (
    <div
      className={cn(
        "kq-chat-scroll min-h-0 flex-1 overflow-y-auto dark:bg-[#0F172A]",
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
          {progress?.running && (
            <AssistantStreamShell>
              <AgentProgress progress={progress} />
            </AssistantStreamShell>
          )}
          {pendingInteraction ? (
            <AgentInteractionCard interaction={pendingInteraction} onRespond={onRespondInteraction} />
          ) : null}
          {pendingAssistant && (
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
          {sending && !progress?.running && !pendingVisibleText && <TypingIndicator />}
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
