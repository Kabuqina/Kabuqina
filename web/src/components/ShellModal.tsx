// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { ReactNode, useEffect } from "react";
import { createPortal } from "react-dom";
import { cn } from "../lib/cn";

type ShellModalProps = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  /** Wider modals for long option lists (e.g. gateway). */
  size?: "md" | "lg";
};

/**
 * Simple shell dialog (no external UI lib). Mounts to `document.body` to avoid `overflow` clipping.
 */
export function ShellModal({ open, title, onClose, children, size = "md" }: ShellModalProps) {
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
    const h = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);

  if (!open) return null;

  const maxW = size === "lg" ? "max-w-2xl" : "max-w-lg";

  const node = (
    <div
      className="fixed inset-0 z-[100] flex items-end justify-center p-4 sm:items-center sm:p-6"
      role="presentation"
    >
      <button
        type="button"
        className="absolute inset-0 cursor-default bg-black/45 dark:bg-black/60"
        aria-label="Close"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal
        aria-labelledby="shell-modal-title"
        className={cn(
          "relative z-10 flex max-h-[min(85vh,720px)] w-full flex-col overflow-hidden rounded-[var(--radius-shell-lg)] border border-[var(--kq-color-border)] bg-white/95 shadow-[var(--kq-shadow-soft)] backdrop-blur-md dark:border-[var(--kq-color-border)] dark:bg-[var(--kq-glass-bg)]",
          maxW
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex shrink-0 items-start justify-between gap-3 border-b border-[var(--kq-color-border)] px-5 py-3.5 dark:border-[var(--kq-color-border)]">
          <h2 id="shell-modal-title" className="pr-2 text-base font-semibold text-[var(--kq-color-strong)] dark:text-[var(--kq-color-strong)]">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="kq-btn-ghost shrink-0 rounded-md px-2 py-1 text-sm dark:hover:bg-[var(--kq-hover-bg-strong)] dark:hover:text-[var(--kq-color-strong)]"
          >
            ✕
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4 text-sm leading-relaxed text-[var(--kq-color-ink)] dark:text-[var(--kq-color-ink)]">
          {children}
        </div>
      </div>
    </div>
  );

  if (typeof document === "undefined") return null;
  return createPortal(node, document.body);
}
