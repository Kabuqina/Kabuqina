// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

export type ConfirmTone = "warning" | "danger" | "default";

export type ConfirmRequest = {
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel: string;
  tone: ConfirmTone;
};

let pending: ConfirmRequest | null = null;
let resolver: ((value: boolean) => void) | null = null;
const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((cb) => cb());
}

export function subscribeConfirm(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getConfirmSnapshot(): ConfirmRequest | null {
  return pending;
}

export function confirm(options: {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: ConfirmTone;
}): Promise<boolean> {
  if (pending) {
    return Promise.resolve(false);
  }
  return new Promise((resolve) => {
    pending = {
      title: options.title,
      message: options.message,
      confirmLabel: options.confirmLabel ?? "",
      cancelLabel: options.cancelLabel ?? "",
      tone: options.tone ?? "default",
    };
    resolver = resolve;
    notify();
  });
}

export function answerConfirm(ok: boolean): void {
  resolver?.(ok);
  resolver = null;
  pending = null;
  notify();
}
