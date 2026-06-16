// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Check, ChevronDown, ChevronUp, Copy, Volume2 } from "lucide-react";
import { useI18n } from "../lib/i18n";
import { cn } from "../lib/cn";
import { AssistantAvatar } from "../components/AssistantAvatar";
import { cmdTtsSpeak, type DeskAttachmentPayload } from "./chat-api";

const ChatMarkdown = lazy(() => import("./ChatMarkdown"));

function base64ToBlob(b64: string, mimeType: string): Blob {
  const byteChars = atob(b64);
  const byteArrays: BlobPart[] = [];
  for (let offset = 0; offset < byteChars.length; offset += 512) {
    const slice = byteChars.slice(offset, offset + 512);
    const byteNumbers = new Array(slice.length);
    for (let i = 0; i < slice.length; i++) {
      byteNumbers[i] = slice.charCodeAt(i);
    }
    byteArrays.push(new Uint8Array(byteNumbers));
  }
  return new Blob(byteArrays, { type: mimeType });
}

export interface ChatMessageProps {
  role: "user" | "assistant";
  text: string;
  attachments?: DeskAttachmentPayload[];
  model?: string;
  /** Unix seconds or ms (see `MessageRow.timestamp`) */
  timestamp?: number;
  streaming?: boolean;
}

function toMillis(ts: number): number {
  if (!Number.isFinite(ts)) {
    return Date.now();
  }
  return ts > 1e12 ? ts : ts * 1000;
}

function formatChatTime(ts: number, locale: "zh" | "en"): string {
  return new Date(toMillis(ts)).toLocaleString(locale === "en" ? "en-US" : "zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function copyToClipboard(s: string): Promise<void> {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    return navigator.clipboard.writeText(s);
  }
  return new Promise((resolve, reject) => {
    try {
      const ta = document.createElement("textarea");
      ta.value = s;
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      resolve();
    } catch (e) {
      reject(e);
    }
  });
}

/** 可复制的正文中不能只有占位的一两个省略号。 */
function canCopyAssistantText(raw: string): boolean {
  const t = raw.trim();
  if (!t) {
    return false;
  }
  if (t === "…" || t === "..." || t === "\u2026" || t === "\u22ef") {
    return false;
  }
  return true;
}

/**
 * 底栏内复制：带「复制」文字 + 图标，始终渲染（无内容时 disabled），避免小图标/占位逻辑导致「完全看不到」。
 */
function MessageCopyButton({ text }: { text: string }) {
  const { t } = useI18n();
  const [done, setDone] = useState(false);
  const canCopy = canCopyAssistantText(text);

  const onCopy = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (!canCopyAssistantText(text)) {
        return;
      }
      void copyToClipboard(text).then(() => {
        setDone(true);
        window.setTimeout(() => setDone(false), 1800);
      });
    },
    [text]
  );

  return (
    <div className="group relative inline-flex max-w-full shrink-0">
      <button
        type="button"
        disabled={!canCopy}
        onClick={onCopy}
        title={!canCopy ? t("chat.copy") : done ? t("chat.copied") : t("chat.copy")}
        className={cn(
          "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[12px] font-medium",
          "text-[var(--kq-color-muted)]",
          "transition",
          canCopy
            ? "hover:bg-[var(--kq-hover-bg)] hover:text-[var(--kq-color-strong)] active:scale-[0.98]"
            : "cursor-not-allowed opacity-40"
        )}
        aria-label={done ? t("chat.copied") : t("chat.copy")}
      >
        {done ? (
          <Check className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" strokeWidth={2.5} />
        ) : (
          <Copy className="h-3.5 w-3.5" strokeWidth={2.25} />
        )}
        <span className="select-none whitespace-nowrap">{done ? t("chat.copied") : t("chat.copy")}</span>
      </button>
      {canCopy && (
        <span
          className={cn(
            "pointer-events-none absolute bottom-full right-0 z-30 mb-1.5 hidden rounded-lg bg-zinc-800 px-2.5 py-1.5",
            "text-xs font-medium text-white shadow-md",
            "sm:group-hover:block",
            "dark:bg-zinc-600"
          )}
          role="tooltip"
        >
          {t("chat.copy")}
        </span>
      )}
    </div>
  );
}

function SpeakButton({ text }: { text: string }) {
  const { t } = useI18n();
  const [speaking, setSpeaking] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);
  // Generation counter to discard stale TTS responses when the user toggles
  // off (or starts a new request) while a previous cmdTtsSpeak is still
  // in-flight. Without this, the in-flight result would create an Audio
  // after the user clicked stop and start playing again.
  const genRef = useRef(0);

  const canSpeak = text.trim().length > 0;

  const stop = useCallback(() => {
    genRef.current += 1;
    if (audioRef.current) {
      try {
        audioRef.current.pause();
        audioRef.current.src = "";
      } catch {
        /* ignore */
      }
      audioRef.current = null;
    }
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current);
      urlRef.current = null;
    }
    setSpeaking(false);
  }, []);

  const handleSpeak = useCallback(async () => {
    if (speaking) {
      stop();
      return;
    }
    if (!canSpeak) return;

    const myGen = ++genRef.current;
    setSpeaking(true);
    let url: string | null = null;
    try {
      const b64 = await cmdTtsSpeak(text);
      if (genRef.current !== myGen) return;
      const blob = base64ToBlob(b64, "audio/mpeg");
      url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      urlRef.current = url;
      audio.onended = () => {
        if (genRef.current !== myGen) return;
        setSpeaking(false);
        if (urlRef.current === url && url) {
          URL.revokeObjectURL(url);
          urlRef.current = null;
        }
        audioRef.current = null;
      };
      audio.onerror = () => {
        if (genRef.current !== myGen) return;
        setSpeaking(false);
        if (urlRef.current === url && url) {
          URL.revokeObjectURL(url);
          urlRef.current = null;
        }
        audioRef.current = null;
      };
      await audio.play();
      if (genRef.current !== myGen) {
        try {
          audio.pause();
          audio.src = "";
        } catch {
          /* ignore */
        }
        if (urlRef.current === url && url) {
          URL.revokeObjectURL(url);
          urlRef.current = null;
        }
      }
    } catch (e) {
      if (genRef.current === myGen) {
        setSpeaking(false);
        if (url) URL.revokeObjectURL(url);
      }
      console.error("TTS speak failed:", e);
    }
  }, [text, speaking, canSpeak, stop]);

  useEffect(() => {
    return () => {
      genRef.current += 1;
      if (audioRef.current) {
        try {
          audioRef.current.pause();
          audioRef.current.src = "";
        } catch {
          /* ignore */
        }
        audioRef.current = null;
      }
      if (urlRef.current) {
        URL.revokeObjectURL(urlRef.current);
        urlRef.current = null;
      }
    };
  }, []);

  return (
    <div className="group relative inline-flex max-w-full shrink-0">
      <button
        type="button"
        disabled={!canSpeak}
        onClick={handleSpeak}
        title={speaking ? t("chat.speaking") : t("chat.speak")}
        className={cn(
          "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[12px] font-medium",
          "text-[var(--kq-color-muted)]",
          "transition",
          canSpeak
            ? "hover:bg-[var(--kq-hover-bg)] hover:text-[var(--kq-color-strong)] active:scale-[0.98]"
            : "cursor-not-allowed opacity-40"
        )}
        aria-label={speaking ? t("chat.speaking") : t("chat.speak")}
      >
        <Volume2
          className={cn(
            "h-3.5 w-3.5 transition",
            speaking ? "text-sky-600 dark:text-sky-400" : ""
          )}
          strokeWidth={2.25}
        />
        <span className="select-none whitespace-nowrap">
          {speaking ? t("chat.speaking") : t("chat.speak")}
        </span>
      </button>
    </div>
  );
}

function AssistantMessageFooter({
  text,
  model,
  timeStr,
}: {
  text: string;
  model?: string;
  timeStr: string | null;
}) {
  const { t } = useI18n();
  const name = t("brand");
  return (
    <div
      className={cn(
        "mt-2 flex w-full min-w-0 flex-wrap items-center gap-2 border-t border-[var(--kq-glass-border)] pt-1.5 text-[11px]",
        timeStr ? "justify-between" : "justify-end"
      )}
    >
      {timeStr ? (
        <span className="shrink-0 font-mono text-[11px] tabular-nums text-[var(--kq-color-muted)]">
          {timeStr}
        </span>
      ) : null}
      <div className="flex min-w-0 max-w-full flex-wrap items-center justify-end gap-x-1 gap-y-1 font-mono text-[var(--kq-color-muted)] sm:gap-x-1.5">
        <span className="shrink-0 min-w-0 break-all sm:break-normal">
          {model?.trim() ? `${name}(${model.trim()})` : name}
        </span>
        <span className="text-[var(--kq-color-muted)]/50" aria-hidden>
          ·
        </span>
        <SpeakButton text={text} />
        <span className="text-[var(--kq-color-muted)]/50" aria-hidden>
          ·
        </span>
        <MessageCopyButton text={text} />
      </div>
    </div>
  );
}

function UserImageAttachments({ attachments = [] }: { attachments?: DeskAttachmentPayload[] }) {
  const imageAttachments = attachments.filter((att) => att.mime.startsWith("image/") && att.data);
  if (imageAttachments.length === 0) {
    return null;
  }
  return (
    <div className="kq-user-image-grid mt-2 grid gap-2">
      {imageAttachments.map((att, index) => (
        <figure key={`${att.name}-${index}`} className="kq-user-image-preview overflow-hidden">
          <img
            src={`data:${att.mime};base64,${att.data}`}
            alt={att.name}
            className="block max-h-72 w-full object-contain"
            loading="lazy"
          />
          <figcaption className="truncate px-2 py-1 text-[11px] text-[var(--kq-color-muted)]">
            {att.name}
          </figcaption>
        </figure>
      ))}
    </div>
  );
}

export function ChatMessage({ role, text, attachments, model, timestamp, streaming = false }: ChatMessageProps) {
  const { t, locale } = useI18n();
  const [collapsed, setCollapsed] = useState(false);
  const isUser = role === "user";

  useEffect(() => {
    if (!streaming) {
      setCollapsed(false);
    }
  }, [streaming]);
  const hasTime = timestamp != null && Number.isFinite(timestamp);
  const timeStr = hasTime ? formatChatTime(timestamp, locale) : null;

  return (
    <div className={cn("flex items-start gap-3", isUser ? "justify-end" : "justify-start")}>
      {!isUser && <AssistantAvatar />}
      <div
        className={cn(
          "kq-chat-assistant-column min-w-0 px-4 py-2.5",
          isUser
            ? "max-w-[min(100%,var(--kq-chat-column-max))] kq-chat-bubble-user"
            : "kq-chat-bubble-assistant"
        )}
        style={isUser
          ? { borderRadius: "18px 18px 4px 18px" }
          : { borderRadius: "4px 18px 18px 18px" }
        }
      >
        {isUser ? (
          <>
            {text.trim() ? (
              <p className="whitespace-pre-wrap break-words text-sm leading-[1.6] [overflow-wrap:anywhere]">
                {text}
              </p>
            ) : null}
            <UserImageAttachments attachments={attachments} />
            {timeStr && (
              <div className="mt-1.5 text-right text-[11px] font-mono tabular-nums text-[var(--kq-color-muted)] dark:text-sky-200/70">
                {timeStr}
              </div>
            )}
          </>
        ) : (
          <>
            {streaming ? (
              <div className="relative min-w-0">
                {collapsed ? (
                  <button
                    type="button"
                    onClick={() => setCollapsed(false)}
                    className="flex w-full items-center gap-2 rounded-lg py-1 text-sm text-[var(--kq-color-muted)] transition hover:bg-[var(--kq-hover-bg)]"
                  >
                    <span className="text-base">✨</span>
                    <span className="truncate">{t("chat.streamingWorking")}…</span>
                    <ChevronDown className="ml-auto h-4 w-4 shrink-0" strokeWidth={2.25} />
                  </button>
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={() => setCollapsed(true)}
                      className="absolute -right-1.5 -top-1.5 z-10 inline-flex items-center rounded-md p-1 text-[var(--kq-color-muted)] transition hover:bg-[var(--kq-hover-bg)] hover:text-[var(--kq-color-strong)]"
                      aria-label={t("chat.collapse")}
                      title={t("chat.collapse")}
                    >
                      <ChevronUp className="h-3.5 w-3.5" strokeWidth={2.5} />
                    </button>
                    <p className="whitespace-pre-wrap break-words pr-5 text-sm leading-[1.6] text-[var(--kq-color-ink)] [overflow-wrap:anywhere]">
                      {text}
                    </p>
                  </>
                )}
              </div>
            ) : (
              <Suspense fallback={<div className="text-sm text-[var(--kq-color-muted)] italic">...</div>}>
                <ChatMarkdown text={text} />
              </Suspense>
            )}
            <AssistantMessageFooter text={text} model={model} timeStr={timeStr} />
          </>
        )}
      </div>
    </div>
  );
}
