// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { CalendarClock, Download, MessageSquare, Terminal } from "lucide-react";
import { cn } from "../lib/cn";
import { useI18n } from "../lib/i18n";

export const APPROVAL_EVENT = "hermes-approval-request";

export type ApprovalRequest = {
  id: string;
  kind: "shell" | "messaging" | "cron" | string;
  reason?: string | null;
  command?: string | null;
  cwd?: string | null;
  target?: string | null;
  contentPreview?: string | null;
  schedule?: string | null;
  description?: string | null;
  deliveryTarget?: string | null;
  modelId?: string | null;
  sizeMb?: number | null;
  packageId?: string | null;
  packageTitle?: string | null;
};

function kindMeta(kind: string) {
  switch (kind) {
    case "messaging":
      return { icon: MessageSquare, accent: "text-sky-600 dark:text-sky-400" };
    case "cron":
      return { icon: CalendarClock, accent: "text-violet-600 dark:text-violet-400" };
    case "model_download":
      return { icon: Download, accent: "text-sky-600 dark:text-sky-400" };
    default:
      return { icon: Terminal, accent: "text-amber-600 dark:text-amber-400" };
  }
}

function ApprovalCard({
  request,
  onRespond,
}: {
  request: ApprovalRequest;
  onRespond: (allowed: boolean) => void;
}) {
  const { t } = useI18n();
  const { icon: Icon, accent } = kindMeta(request.kind);
  const modelDownloadName =
    request.packageTitle?.trim() || request.modelId?.trim() || t("approval.modelDownloadFallback");

  const title =
    request.kind === "model_download"
      ? t("approval.modelDownloadTitle", { name: modelDownloadName })
      : request.kind === "messaging"
        ? t("approval.messagingTitle")
        : request.kind === "cron"
          ? t("approval.cronTitle")
          : t("approval.shellTitle");

  const hint =
    request.kind === "model_download"
      ? t("approval.modelDownloadHint", { name: modelDownloadName, size: String(request.sizeMb ?? 500) })
      : request.kind === "cron"
        ? t("approval.cronHint")
        : request.kind === "messaging"
          ? t("approval.messagingHint")
          : t("approval.shellHint");

  const allowLabel =
    request.kind === "model_download"
      ? t("approval.modelDownloadAllow")
      : request.kind === "cron"
        ? t("approval.allow")
        : t("approval.allowOnce");

  const isModelDownload = request.kind === "model_download";

  return (
    <div
      role="dialog"
      aria-modal
      aria-labelledby={`approval-title-${request.id}`}
      className={cn(
        "relative z-10 flex w-full flex-col overflow-hidden rounded-[var(--radius-shell-lg)] border border-[var(--kq-color-border)] bg-white/95 shadow-[var(--kq-shadow-soft)] backdrop-blur-md dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)]",
        isModelDownload ? "max-w-md" : "max-w-lg",
      )}
      onClick={(e) => e.stopPropagation()}
    >
      <div className="flex items-start gap-3 border-b border-[var(--kq-color-border)] px-5 py-4 dark:border-[var(--kq-color-border)]">
        <div className={cn("mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--radius-shell-lg)] bg-amber-50 dark:bg-amber-950/40", accent)}>
          <Icon className="h-4 w-4" strokeWidth={2.2} aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <h2 id={`approval-title-${request.id}`} className="text-base font-semibold text-[var(--kq-color-strong)] dark:text-[var(--kq-color-strong)]">
            {title}
          </h2>
          <p className="mt-1 text-sm leading-relaxed text-[var(--kq-color-muted)] dark:text-[var(--kq-color-muted)]">{hint}</p>
        </div>
      </div>

      <div className="space-y-3 px-5 py-4 text-sm leading-relaxed text-[var(--kq-color-ink)] dark:text-[var(--kq-color-ink)]">
        {request.reason ? (
          <p className="rounded-[var(--radius-shell-lg)] border border-amber-200/80 bg-amber-50/70 px-3 py-2 text-amber-950 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-100">
            {request.reason}
          </p>
        ) : null}

        {request.modelId ? (
          <div>
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-[var(--kq-color-muted)] dark:text-[var(--kq-color-muted)]">
              {t("approval.modelId")}
            </p>
            <p className="break-all rounded-[var(--radius-shell-lg)] border border-zinc-200/80 bg-zinc-50 px-3 py-2 font-mono text-[12px] text-zinc-700 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)] dark:text-[var(--kq-color-ink)]">
              {request.modelId}
            </p>
          </div>
        ) : null}

        {request.sizeMb ? (
          <div>
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-[var(--kq-color-muted)] dark:text-[var(--kq-color-muted)]">
              {t("approval.modelSize")}
            </p>
            <p className="rounded-[var(--radius-shell-lg)] border border-zinc-200/80 bg-zinc-50 px-3 py-2 text-zinc-700 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)] dark:text-[var(--kq-color-ink)]">
              {t("approval.modelDownloadSize", { size: String(request.sizeMb) })}
            </p>
          </div>
        ) : null}

        {request.command ? (
          <div>
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-[var(--kq-color-muted)] dark:text-[var(--kq-color-muted)]">
              {t("approval.command")}
            </p>
            <pre className="max-h-40 overflow-auto rounded-[var(--radius-shell-lg)] border border-zinc-200/80 bg-zinc-50 px-3 py-2 font-mono text-[12px] leading-5 text-zinc-800 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)] dark:text-[var(--kq-color-ink)]">
              {request.command}
            </pre>
          </div>
        ) : null}

        {request.cwd ? (
          <div>
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-[var(--kq-color-muted)] dark:text-[var(--kq-color-muted)]">
              {t("approval.folder")}
            </p>
            <p className="break-all rounded-[var(--radius-shell-lg)] border border-zinc-200/80 bg-zinc-50 px-3 py-2 font-mono text-[12px] text-zinc-700 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)] dark:text-[var(--kq-color-ink)]">
              {request.cwd}
            </p>
          </div>
        ) : null}

        {request.target ? (
          <div>
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-[var(--kq-color-muted)] dark:text-[var(--kq-color-muted)]">
              {t("approval.target")}
            </p>
            <p className="break-all rounded-[var(--radius-shell-lg)] border border-zinc-200/80 bg-zinc-50 px-3 py-2 text-zinc-700 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)] dark:text-[var(--kq-color-ink)]">
              {request.target}
            </p>
          </div>
        ) : null}

        {request.contentPreview ? (
          <div>
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-[var(--kq-color-muted)] dark:text-[var(--kq-color-muted)]">
              {t("approval.preview")}
            </p>
            <p className="whitespace-pre-wrap rounded-[var(--radius-shell-lg)] border border-zinc-200/80 bg-zinc-50 px-3 py-2 text-zinc-700 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)] dark:text-[var(--kq-color-ink)]">
              {request.contentPreview}
            </p>
          </div>
        ) : null}

        {request.description ? (
          <div>
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-[var(--kq-color-muted)] dark:text-[var(--kq-color-muted)]">
              {t("approval.task")}
            </p>
            <p className="whitespace-pre-wrap rounded-[var(--radius-shell-lg)] border border-zinc-200/80 bg-zinc-50 px-3 py-2 text-zinc-700 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)] dark:text-[var(--kq-color-ink)]">
              {request.description}
            </p>
          </div>
        ) : null}

        {request.schedule ? (
          <div>
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-[var(--kq-color-muted)] dark:text-[var(--kq-color-muted)]">
              {t("approval.schedule")}
            </p>
            <p className="rounded-[var(--radius-shell-lg)] border border-zinc-200/80 bg-zinc-50 px-3 py-2 font-mono text-[12px] text-zinc-700 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)] dark:text-[var(--kq-color-ink)]">
              {request.schedule}
            </p>
          </div>
        ) : null}

        {request.deliveryTarget ? (
          <div>
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-[var(--kq-color-muted)] dark:text-[var(--kq-color-muted)]">
              {t("approval.delivery")}
            </p>
            <p className="rounded-[var(--radius-shell-lg)] border border-zinc-200/80 bg-zinc-50 px-3 py-2 text-zinc-700 dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)] dark:text-[var(--kq-color-ink)]">
              {request.deliveryTarget === "desktop" ? t("approval.deliveryDesktop") : request.deliveryTarget}
            </p>
          </div>
        ) : null}
      </div>

      <div className="flex flex-wrap justify-end gap-2 border-t border-[var(--kq-color-border)] px-5 py-4 dark:border-[var(--kq-color-border)]">
        <button
          type="button"
          className="rounded-[var(--radius-shell-lg)] border border-zinc-300/90 px-4 py-2 text-sm font-medium text-zinc-700 transition hover:bg-zinc-50 dark:border-[var(--kq-color-border)] dark:text-[var(--kq-color-ink)] dark:hover:bg-[var(--kq-hover-bg-strong)]"
          onClick={() => onRespond(false)}
        >
          {t("approval.deny")}
        </button>
        <button
          type="button"
          className="rounded-[var(--radius-shell-lg)] bg-[var(--kq-color-strong)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 dark:bg-[var(--kq-color-primary-light)] dark:text-[var(--kq-color-surface)]"
          onClick={() => onRespond(true)}
        >
          {allowLabel}
        </button>
      </div>
    </div>
  );
}

export function ApprovalDialogHost() {
  const [queue, setQueue] = useState<ApprovalRequest[]>([]);
  const active = queue[0] ?? null;

  useEffect(() => {
    const unlisten = listen<ApprovalRequest>(APPROVAL_EVENT, ({ payload }) => {
      setQueue((prev) => [...prev, payload]);
    });
    return () => {
      void unlisten.then((fn) => fn());
    };
  }, []);

  const respond = useCallback(async (allowed: boolean) => {
    if (!active) return;
    try {
      await invoke("cmd_respond_approval", { id: active.id, allowed });
    } catch (error) {
      console.error("cmd_respond_approval failed:", error);
    } finally {
      setQueue((prev) => prev.filter((item) => item.id !== active.id));
    }
  }, [active]);

  useEffect(() => {
    if (!active) return;
    const body = document.body;
    const prev = body.style.overflow;
    body.style.overflow = "hidden";
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        void respond(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [active, respond]);

  if (!active || typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed inset-0 z-[110] flex items-end justify-center p-4 sm:items-center sm:p-6" role="presentation">
      <div className="absolute inset-0 bg-black/45 dark:bg-black/60" aria-hidden />
      <ApprovalCard request={active} onRespond={(allowed) => void respond(allowed)} />
    </div>,
    document.body,
  );
}
