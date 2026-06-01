// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import { AlertTriangle } from "lucide-react";
import { answerConfirm, getConfirmSnapshot, subscribeConfirm } from "../lib/confirmDialog";
import { useI18n } from "../lib/i18n";
import { cn } from "../lib/cn";

export function ConfirmDialogHost() {
  const { t } = useI18n();
  const request = useSyncExternalStore(subscribeConfirm, getConfirmSnapshot, getConfirmSnapshot);
  const open = request !== null;

  useEffect(() => {
    if (!open) return;
    const body = document.body;
    const prev = body.style.overflow;
    body.style.overflow = "hidden";
    return () => {
      body.style.overflow = prev;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") answerConfirm(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (!open || !request) return null;

  const confirmLabel = request.confirmLabel || t("dialog.confirm");
  const cancelLabel = request.cancelLabel || t("dialog.cancel");
  const isWarning = request.tone === "warning";
  const isDanger = request.tone === "danger";

  const node = (
    <div
      className="fixed inset-0 z-[110] flex items-end justify-center p-4 sm:items-center sm:p-6"
      role="presentation"
    >
      <button
        type="button"
        className="absolute inset-0 cursor-default bg-black/40 backdrop-blur-[2px] dark:bg-black/55"
        aria-label={cancelLabel}
        onClick={() => answerConfirm(false)}
      />
      <div
        role="alertdialog"
        aria-modal
        aria-labelledby="kq-confirm-title"
        aria-describedby="kq-confirm-message"
        className="kq-confirm-dialog relative z-10 flex w-full max-w-md flex-col overflow-hidden border border-[var(--kq-color-border)] bg-white/96 shadow-[var(--kq-shadow-soft)] backdrop-blur-md dark:border-zinc-700 dark:bg-zinc-950"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3 border-b border-[var(--kq-color-border)] px-5 py-4 dark:border-zinc-800">
          <div
            className={cn(
              "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--radius-shell-lg)]",
              isDanger
                ? "bg-rose-50 text-rose-600 dark:bg-rose-950/40 dark:text-rose-300"
                : isWarning
                  ? "bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-300"
                  : "bg-[#f3edf6] text-[var(--kq-color-strong)] dark:bg-zinc-800 dark:text-zinc-200",
            )}
          >
            <AlertTriangle className="h-4 w-4" strokeWidth={2.25} aria-hidden />
          </div>
          <div className="min-w-0 flex-1">
            <h2
              id="kq-confirm-title"
              className="text-base font-semibold leading-snug text-[var(--kq-color-strong)] dark:text-zinc-100"
            >
              {request.title}
            </h2>
            <p
              id="kq-confirm-message"
              className="mt-2 text-sm leading-relaxed text-[var(--kq-color-ink)]/88 dark:text-zinc-300"
            >
              {request.message}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap justify-end gap-2 px-5 py-4">
          <button
            type="button"
            className="kq-confirm-btn-secondary rounded-[var(--radius-shell-lg)] border border-[var(--kq-color-border)] px-4 py-2 text-sm font-medium text-[var(--kq-color-ink)] transition hover:bg-[#f5f0f7] dark:border-zinc-600 dark:text-zinc-200 dark:hover:bg-zinc-900"
            onClick={() => answerConfirm(false)}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            className={cn(
              "rounded-[var(--radius-shell-lg)] px-4 py-2 text-sm font-medium text-white transition hover:brightness-[1.03] active:scale-[0.99]",
              isDanger
                ? "bg-gradient-to-br from-rose-600 to-rose-700 dark:from-rose-500 dark:to-rose-600"
                : isWarning
                  ? "bg-gradient-to-br from-amber-600 to-amber-700 dark:from-amber-500 dark:to-amber-600"
                  : "kq-btn-primary",
            )}
            onClick={() => answerConfirm(true)}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );

  if (typeof document === "undefined") return null;
  return createPortal(node, document.body);
}
