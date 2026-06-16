// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useRef, useState } from "react";
import { isTauri } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import { ArrowUp, Crop, FolderOpen, Paperclip, Square, X } from "lucide-react";
import { useI18n } from "../lib/i18n";
import { cn } from "../lib/cn";
import { captureFullscreen, showCaptureOverlay } from "../capture/capture-api";
import type { DeskAttachmentPayload } from "./chat-api";
import { VoiceButton } from "./VoiceButton";
import { useVoiceRecorder } from "./hooks/useVoiceRecorder";

export interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  sending?: boolean;
  placeholder?: string;
  /** Files queued for the next message (images render as thumbnails). */
  pendingAttachments: DeskAttachmentPayload[];
  onRemoveAttachment: (index: number) => void;
  onFilesPicked: (files: FileList | null) => void;
  onStop?: () => void;
  /** When true, the model isn't configured yet — block sending and prompt setup. */
  needsModelSetup?: boolean;
  /** Open the initialization flow so the user can configure a model. */
  onConfigureModel?: () => void;
}

export function ChatInput({
  value,
  onChange,
  onSend,
  sending = false,
  placeholder,
  pendingAttachments,
  onRemoveAttachment,
  onFilesPicked,
  onStop,
  needsModelSetup = false,
  onConfigureModel,
}: ChatInputProps) {
  const { t } = useI18n();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [previewSrc, setPreviewSrc] = useState<string | null>(null);

  const [voiceErr, setVoiceErr] = useState<string | null>(null);
  const [pathPickerErr, setPathPickerErr] = useState<string | null>(null);
  const [screenshotErr, setScreenshotErr] = useState<string | null>(null);
  const [pathMenuOpen, setPathMenuOpen] = useState(false);
  const [screenshotMenuOpen, setScreenshotMenuOpen] = useState(false);
  const [pathMenuPos, setPathMenuPos] = useState<{ bottom: number; left: number } | null>(null);
  const [screenshotMenuPos, setScreenshotMenuPos] = useState<{ bottom: number; left: number } | null>(null);
  const pathBtnRef = useRef<HTMLButtonElement>(null);
  const screenshotBtnRef = useRef<HTMLButtonElement>(null);
  const [needsModelDownload, setNeedsModelDownload] = useState(false);
  const errTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pathErrTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const screenshotErrTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const syncTextareaHeight = useCallback(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 280)}px`;
    ta.style.overflowY = ta.scrollHeight > 280 ? "auto" : "hidden";
  }, []);

  useEffect(() => {
    const frame = requestAnimationFrame(syncTextareaHeight);
    return () => cancelAnimationFrame(frame);
  }, [syncTextareaHeight, value, pendingAttachments.length]);

  const handleVoiceErr = useCallback(
    (err: string) => {
      // The Python backend returns ``error: "stt_model_missing"`` when the
      // GGML file isn't on disk yet (first launch). Surface that as the
      // download confirm banner instead of a generic red error.
      if (err.includes("stt_model_missing") || err.includes("STT_MODEL_MISSING")) {
        setVoiceErr(null);
        setNeedsModelDownload(true);
        return;
      }
      const display = err.includes("no_stt_provider") ? t("chat.voiceNoProvider") : err;
      setVoiceErr(display);
      if (errTimerRef.current) clearTimeout(errTimerRef.current);
      errTimerRef.current = setTimeout(() => setVoiceErr(null), 5000);
    },
    [t]
  );

  const handleTranscript = useCallback(
    (text: string) => {
      onChange(value ? `${value} ${text}` : text);
    },
    [value, onChange]
  );

  const {
    recorderState,
    durationMs,
    mimeTypeSupported,
    start,
    stop,
    isLocalModelReady,
    downloadLocalModel,
  } = useVoiceRecorder({
    onTranscript: handleTranscript,
    onError: handleVoiceErr,
  });

  const handleMicPress = useCallback(async () => {
    if (recorderState === "recording") {
      stop();
      return;
    }
    if (recorderState !== "idle") return;
    setVoiceErr(null);
    // Probe local model: if not on disk and no banner shown yet, prompt
    // the user before pulling 60 MB. The check is a single Tauri RT call,
    // not a network round-trip.
    const ready = await isLocalModelReady();
    if (!ready) {
      setNeedsModelDownload(true);
      return;
    }
    void start();
  }, [recorderState, isLocalModelReady, start, stop]);

  const handleConfirmDownload = useCallback(async () => {
    setNeedsModelDownload(false);
    const ok = await downloadLocalModel();
    if (ok) {
      void start();
    }
  }, [downloadLocalModel, start]);

  const handleCancelDownload = useCallback(() => {
    setNeedsModelDownload(false);
  }, []);

  useEffect(() => {
    return () => {
      if (errTimerRef.current) clearTimeout(errTimerRef.current);
      if (pathErrTimerRef.current) clearTimeout(pathErrTimerRef.current);
      if (screenshotErrTimerRef.current) clearTimeout(screenshotErrTimerRef.current);
    };
  }, []);

  useEffect(() => {
    if (!pathMenuOpen && !screenshotMenuOpen && !previewSrc) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setPathMenuOpen(false);
        setScreenshotMenuOpen(false);
        setPreviewSrc(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pathMenuOpen, screenshotMenuOpen, previewSrc]);

  const flashPathPickerErr = useCallback((msg: string) => {
    setPathPickerErr(msg);
    if (pathErrTimerRef.current) clearTimeout(pathErrTimerRef.current);
    pathErrTimerRef.current = setTimeout(() => setPathPickerErr(null), 4000);
  }, []);

  const flashScreenshotErr = useCallback((msg: string) => {
    setScreenshotErr(msg);
    if (screenshotErrTimerRef.current) clearTimeout(screenshotErrTimerRef.current);
    screenshotErrTimerRef.current = setTimeout(() => setScreenshotErr(null), 4000);
  }, []);

  const insertPathIntoPrompt = useCallback(
    (path: string) => {
      const ta = textareaRef.current;
      if (!ta) {
        onChange(value ? `${value}${/\s$/.test(value) ? "" : " "}${path}` : path);
        return;
      }
      const start = ta.selectionStart;
      const end = ta.selectionEnd;
      const before = value.slice(0, start);
      const after = value.slice(end);
      const needsSpace = before.length > 0 && !/\s$/.test(before);
      const insert = `${needsSpace ? " " : ""}${path}`;
      const next = `${before}${insert}${after}`;
      onChange(next);
      requestAnimationFrame(() => {
        ta.focus();
        const pos = start + insert.length;
        ta.setSelectionRange(pos, pos);
      });
    },
    [value, onChange]
  );

  const handlePickPath = useCallback(
    async (kind: "folder" | "file") => {
      setPathMenuOpen(false);
      if (!isTauri()) {
        flashPathPickerErr(t("chat.insertPathNeedsApp"));
        return;
      }
      try {
        const selected = await open({
          directory: kind === "folder",
          multiple: false,
          title: kind === "folder" ? t("chat.insertPathFolder") : t("chat.insertPathFile"),
        });
        if (selected == null) return;
        const p = typeof selected === "string" ? selected : selected[0];
        if (p) insertPathIntoPrompt(p);
      } catch {
        flashPathPickerErr(t("chat.insertPathFailed"));
      }
    },
    [flashPathPickerErr, insertPathIntoPrompt, t]
  );

  const handleScreenshotAction = useCallback(
    async (mode: "region" | "fullscreen") => {
      setScreenshotMenuOpen(false);
      if (!isTauri()) {
        flashScreenshotErr(t("chat.insertPathNeedsApp"));
        return;
      }
      try {
        if (mode === "region") {
          await showCaptureOverlay();
        } else {
          await captureFullscreen();
        }
      } catch {
        flashScreenshotErr(t("chat.screenshotFailed"));
      }
    },
    [flashScreenshotErr, t]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (!sending && !needsModelSetup) {
          const canSend = value.trim() || pendingAttachments.length > 0;
          if (canSend) {
            onSend();
          }
        }
      }
    },
    [onSend, sending, needsModelSetup, value, pendingAttachments.length]
  );

  const canSend = !sending && !needsModelSetup && (value.trim() || pendingAttachments.length > 0);

  return (
    <div className="kq-input-area shrink-0">
      <div className="kq-input-container">
      <div
        className={cn(
          "kq-composer mx-auto max-w-[var(--kq-chat-column-max)]",
          "dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg-subtle)]"
        )}
      >
        {pendingAttachments.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 border-b border-zinc-100 px-3 py-2 dark:border-[var(--kq-color-border)]">
            {pendingAttachments.map((att, i) => {
              const isImage = att.mime.startsWith("image/");
              if (isImage) {
                const src = `data:${att.mime};base64,${att.data}`;
                return (
                  <div
                    key={`${att.name}-${i}`}
                    className="group relative h-16 w-16 overflow-hidden rounded-lg border border-zinc-200 bg-zinc-50 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg-subtle)]"
                  >
                    <button
                      type="button"
                      onClick={() => setPreviewSrc(src)}
                      className="block h-full w-full"
                      title={t("chat.previewImage")}
                      aria-label={t("chat.previewImage")}
                    >
                      <img
                        src={src}
                        alt={att.name}
                        className="h-full w-full object-cover transition group-hover:brightness-95"
                      />
                    </button>
                    <button
                      type="button"
                      disabled={sending}
                      onClick={() => onRemoveAttachment(i)}
                      className="absolute right-0.5 top-0.5 rounded-full bg-black/55 p-0.5 text-white opacity-0 transition group-hover:opacity-100 hover:bg-black/75 disabled:opacity-40"
                      aria-label={t("chat.removeAttachment")}
                    >
                      <X className="h-3 w-3" strokeWidth={2.5} />
                    </button>
                  </div>
                );
              }
              return (
                <span
                  key={`${att.name}-${i}`}
                  className="inline-flex max-w-[min(100%,14rem)] items-center gap-1 rounded-full bg-zinc-100 pl-2.5 pr-1.5 py-0.5 text-[11px] text-zinc-600 dark:bg-[var(--kq-glass-bg-subtle)] dark:text-[var(--kq-color-ink)]"
                >
                  <span className="truncate" title={att.name}>
                    {att.name}
                  </span>
                  <button
                    type="button"
                    disabled={sending}
                    onClick={() => onRemoveAttachment(i)}
                    className="shrink-0 rounded-full p-0.5 text-zinc-400 hover:text-zinc-700 disabled:opacity-40 dark:hover:text-[var(--kq-color-strong)]"
                    aria-label={t("chat.removeAttachment")}
                  >
                    <X className="h-3 w-3" strokeWidth={2.5} />
                  </button>
                </span>
              );
            })}
          </div>
        )}

          <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            requestAnimationFrame(syncTextareaHeight);
          }}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder={placeholder ?? t("chat.placeholder")}
          disabled={sending}
          className="max-h-[220px] min-h-[44px] w-full resize-none overflow-hidden bg-transparent px-4 pb-1 pt-3 text-[14.5px] leading-relaxed text-[var(--kq-color-ink)] placeholder:text-[var(--kq-color-muted)] outline-none transition focus:ring-0 disabled:opacity-50 dark:text-[var(--kq-color-strong)] dark:placeholder:text-[var(--kq-color-muted)]"
        />

        <div className="flex items-center justify-between gap-2 px-2 pb-2 pt-0.5">
          <div className="flex items-center gap-1 overflow-visible">
            <div className="relative">
              <button
                type="button"
                disabled={sending}
                onClick={() => {
                  if (sending) return;
                  setScreenshotMenuOpen(false);
                  if (pathMenuOpen) {
                    setPathMenuOpen(false);
                  } else {
                    if (pathBtnRef.current) {
                      const rect = pathBtnRef.current.getBoundingClientRect();
                      setPathMenuPos({ bottom: window.innerHeight - rect.top + 4, left: rect.left });
                    }
                    setPathMenuOpen(true);
                  }
                }}
                ref={pathBtnRef}
                className="kq-soft-icon-btn group relative flex h-[34px] w-[34px] items-center justify-center rounded-lg transition active:scale-[0.98] dark:text-[var(--kq-color-muted)] dark:hover:bg-[var(--kq-hover-bg-strong)] disabled:cursor-not-allowed disabled:opacity-40"
                aria-label={t("chat.insertPath")}
                aria-expanded={pathMenuOpen}
                aria-haspopup="menu"
              >
                <FolderOpen className="h-[17px] w-[17px]" strokeWidth={2} />
                <span className="pointer-events-none absolute -bottom-9 left-1/2 z-20 -translate-x-1/2 whitespace-nowrap rounded-lg bg-white/80 px-3 py-1.5 text-xs font-medium text-zinc-600 opacity-0 shadow-md ring-1 ring-zinc-200/60 backdrop-blur-sm transition-opacity group-hover:opacity-100 dark:bg-[var(--kq-glass-bg)] dark:text-[var(--kq-color-ink)] dark:ring-[var(--kq-color-border)]">
                  {t("chat.insertPathHint")}
                </span>
              </button>
            </div>
            <input
              ref={fileRef}
              type="file"
              className="hidden"
              accept="image/*,text/*,.csv,.c,.cpp,.cs,.css,.doc,.docx,.go,.h,.hpp,.html,.java,.js,.jsx,.json,.log,.md,.pdf,.ppt,.pptx,.ps1,.py,.rs,.sh,.ts,.tsx,.xml,.yaml,.yml,application/vnd.ms-powerpoint,application/vnd.openxmlformats-officedocument.presentationml.presentation"
              multiple
              onChange={(e) => {
                onFilesPicked(e.target.files);
                e.target.value = "";
              }}
            />
            <button
              type="button"
              disabled={sending}
              onClick={() => fileRef.current?.click()}
              className="kq-soft-icon-btn group relative flex h-[34px] w-[34px] items-center justify-center rounded-lg transition active:scale-[0.98] dark:text-[var(--kq-color-muted)] dark:hover:bg-[var(--kq-hover-bg-strong)] disabled:cursor-not-allowed disabled:opacity-40"
              aria-label={t("chat.attach")}
            >
              <Paperclip className="h-[17px] w-[17px]" />
              {/* Tooltip */}
              <span className="pointer-events-none absolute -bottom-9 left-1/2 z-20 -translate-x-1/2 whitespace-nowrap rounded-lg bg-white/80 px-3 py-1.5 text-xs font-medium text-zinc-600 opacity-0 shadow-md ring-1 ring-zinc-200/60 backdrop-blur-sm transition-opacity group-hover:opacity-100 dark:bg-[var(--kq-glass-bg)] dark:text-[var(--kq-color-ink)] dark:ring-[var(--kq-color-border)]">
                {t("chat.attachHint")}
              </span>
            </button>
            <div className="relative">
              <button
                type="button"
                disabled={sending}
                onClick={() => {
                  if (sending) return;
                  setPathMenuOpen(false);
                  if (screenshotMenuOpen) {
                    setScreenshotMenuOpen(false);
                  } else {
                    if (screenshotBtnRef.current) {
                      const rect = screenshotBtnRef.current.getBoundingClientRect();
                      setScreenshotMenuPos({ bottom: window.innerHeight - rect.top + 4, left: rect.left });
                    }
                    setScreenshotMenuOpen(true);
                  }
                }}
                ref={screenshotBtnRef}
                className="kq-soft-icon-btn group relative flex h-[34px] w-[34px] items-center justify-center rounded-lg transition active:scale-[0.98] dark:text-[var(--kq-color-muted)] dark:hover:bg-[var(--kq-hover-bg-strong)] disabled:cursor-not-allowed disabled:opacity-40"
                aria-label={t("chat.screenshot")}
                aria-expanded={screenshotMenuOpen}
                aria-haspopup="menu"
              >
                <Crop className="h-[17px] w-[17px]" strokeWidth={2} />
                <span className="pointer-events-none absolute -bottom-9 left-1/2 z-20 -translate-x-1/2 whitespace-nowrap rounded-lg bg-white/80 px-3 py-1.5 text-xs font-medium text-zinc-600 opacity-0 shadow-md ring-1 ring-zinc-200/60 backdrop-blur-sm transition-opacity group-hover:opacity-100 dark:bg-[var(--kq-glass-bg)] dark:text-[var(--kq-color-ink)] dark:ring-[var(--kq-color-border)]">
                  {t("chat.screenshotHint")}
                </span>
              </button>
            </div>
            {mimeTypeSupported && (
              <VoiceButton
                state={recorderState}
                durationMs={durationMs}
                disabled={sending}
                onPress={() => void handleMicPress()}
              />
            )}
          </div>

          <div className="flex items-center gap-2">
            {sending && onStop && (
              <button
                type="button"
                onClick={() => void onStop()}
                className={cn(
                  "flex h-[34px] w-[34px] flex-shrink-0 items-center justify-center rounded-lg border border-zinc-200 bg-white",
                  "text-zinc-600 shadow-sm transition active:scale-[0.98]",
                  "hover:border-red-200/90 hover:bg-red-50/90 hover:text-red-600",
                  "dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)] dark:text-[var(--kq-color-ink)]",
                  "dark:hover:border-red-900/50 dark:hover:bg-red-950/30 dark:hover:text-red-400"
                )}
                title={t("chat.stop")}
                aria-label={t("chat.stop")}
              >
                <Square className="h-3.5 w-3.5 fill-current" />
              </button>
            )}
            <button
              type="button"
              onClick={() => void onSend()}
              disabled={!canSend}
              className="kq-send-button flex h-[34px] w-[34px] flex-shrink-0 items-center justify-center rounded-full text-white transition active:scale-[0.98] disabled:cursor-not-allowed disabled:shadow-none"
              title={needsModelSetup ? t("chat.needModelSetup") : sending ? t("chat.sending") : t("chat.send")}
              aria-label={needsModelSetup ? t("chat.needModelSetup") : sending ? t("chat.sending") : t("chat.send")}
            >
              <ArrowUp className="h-[17px] w-[17px]" strokeWidth={2.25} />
            </button>
          </div>
        </div>
      </div>
      {/* Fixed menus rendered outside composer to escape its stacking context */}
      {pathMenuOpen && pathMenuPos && (
        <>
          <div
            role="presentation"
            className="fixed inset-0 z-[200]"
            onClick={() => setPathMenuOpen(false)}
          />
          <div
            role="menu"
            className="fixed z-[210] min-w-[10.5rem] overflow-hidden rounded-lg border border-zinc-200/95 bg-white py-1 shadow-lg dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)]"
            style={{ bottom: pathMenuPos.bottom, left: pathMenuPos.left }}
          >
            <button
              type="button"
              role="menuitem"
              className="block w-full px-3 py-2 text-left text-sm text-zinc-700 transition hover:bg-zinc-100 dark:text-[var(--kq-color-ink)] dark:hover:bg-[var(--kq-hover-bg-strong)]"
              onClick={() => void handlePickPath("folder")}
            >
              {t("chat.insertPathFolder")}
            </button>
            <button
              type="button"
              role="menuitem"
              className="block w-full px-3 py-2 text-left text-sm text-zinc-700 transition hover:bg-zinc-100 dark:text-[var(--kq-color-ink)] dark:hover:bg-[var(--kq-hover-bg-strong)]"
              onClick={() => void handlePickPath("file")}
            >
              {t("chat.insertPathFile")}
            </button>
          </div>
        </>
      )}
      {screenshotMenuOpen && screenshotMenuPos && (
        <>
          <div
            role="presentation"
            className="fixed inset-0 z-[200]"
            onClick={() => setScreenshotMenuOpen(false)}
          />
          <div
            role="menu"
            className="fixed z-[210] min-w-[10.5rem] overflow-hidden rounded-lg border border-zinc-200/95 bg-white py-1 shadow-lg dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)]"
            style={{ bottom: screenshotMenuPos.bottom, left: screenshotMenuPos.left }}
          >
            <button
              type="button"
              role="menuitem"
              className="block w-full px-3 py-2 text-left text-sm text-zinc-700 transition hover:bg-zinc-100 dark:text-[var(--kq-color-ink)] dark:hover:bg-[var(--kq-hover-bg-strong)]"
              onClick={() => void handleScreenshotAction("region")}
            >
              {t("chat.screenshotRegion")}
            </button>
            <button
              type="button"
              role="menuitem"
              className="block w-full px-3 py-2 text-left text-sm text-zinc-700 transition hover:bg-zinc-100 dark:text-[var(--kq-color-ink)] dark:hover:bg-[var(--kq-hover-bg-strong)]"
              onClick={() => void handleScreenshotAction("fullscreen")}
            >
              {t("chat.screenshotFullscreen")}
            </button>
          </div>
        </>
      )}
      {needsModelSetup && (
        <div className="mx-auto mt-1.5 flex max-w-[var(--kq-chat-column-max)] flex-wrap items-center justify-between gap-2 rounded-md border border-amber-200 bg-amber-50/70 px-3 py-2 text-xs text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-100">
          <span className="leading-relaxed">{t("chat.needModelSetup")}</span>
          {onConfigureModel && (
            <button
              type="button"
              onClick={onConfigureModel}
              className="shrink-0 rounded bg-amber-600 px-2 py-1 font-medium text-white shadow-sm transition hover:opacity-90"
            >
              {t("chat.apiRequiredGoSetup")}
            </button>
          )}
        </div>
      )}
      {needsModelDownload && (
        <div className="mx-auto mt-1.5 flex max-w-[var(--kq-chat-column-max)] flex-wrap items-center justify-between gap-2 rounded-md border border-sky-200 bg-sky-50/70 px-3 py-2 text-xs text-sky-900 dark:border-sky-900/40 dark:bg-sky-950/30 dark:text-sky-100">
          <span className="leading-relaxed">{t("chat.voiceModelConfirm")}</span>
          <span className="flex shrink-0 items-center gap-1.5">
            <button
              type="button"
              onClick={handleCancelDownload}
              className="rounded px-2 py-1 text-zinc-600 transition hover:bg-zinc-200/60 dark:text-[var(--kq-color-ink)] dark:hover:bg-[var(--kq-hover-bg-strong)]"
            >
              {t("chat.voiceModelCancel")}
            </button>
            <button
              type="button"
              onClick={() => void handleConfirmDownload()}
              className="kq-btn-primary rounded px-2 py-1 font-medium text-white shadow-sm transition hover:opacity-90"
            >
              {t("chat.voiceModelDownload")}
            </button>
          </span>
        </div>
      )}
      {voiceErr && (
        <p className="mx-auto mt-1.5 max-w-[var(--kq-chat-column-max)] text-xs text-red-500 dark:text-red-400">
          {voiceErr}
        </p>
      )}
      {pathPickerErr && (
        <p className="mx-auto mt-1.5 max-w-[var(--kq-chat-column-max)] text-xs text-amber-700 dark:text-amber-400">
          {pathPickerErr}
        </p>
      )}
      {screenshotErr && (
        <p className="mx-auto mt-1.5 max-w-[var(--kq-chat-column-max)] text-xs text-amber-700 dark:text-amber-400">
          {screenshotErr}
        </p>
      )}
      </div>
      {previewSrc && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 p-6 backdrop-blur-sm"
          onClick={() => setPreviewSrc(null)}
        >
          <img
            src={previewSrc}
            alt=""
            className="max-h-full max-w-full rounded-lg object-contain shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          />
          <button
            type="button"
            onClick={() => setPreviewSrc(null)}
            className="absolute right-4 top-4 rounded-full bg-black/55 p-2 text-white transition hover:bg-black/75"
            aria-label={t("chat.closePreview")}
          >
            <X className="h-5 w-5" strokeWidth={2.5} />
          </button>
        </div>
      )}
    </div>
  );
}
