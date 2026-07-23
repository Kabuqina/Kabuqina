// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { completedResult, deskFixtureData, needsRevisionResult } from "./deskFixtures";
import type { CheckResult, DeskData } from "./types";

/**
 * Seam between the desk UI and a future real backend. The scene only talks to
 * this interface; swap `createFixtureDeskAdapter` for a Tutor-backed
 * implementation without touching components.
 */
export interface DeskAdapter {
  loadDesk(signal: AbortSignal): Promise<DeskData>;
  /** Persist browser recovery state synchronously before a refresh can unload the page. */
  persistDraft?(stepId: string, answer: string): void;
  saveDraft(stepId: string, answer: string, signal: AbortSignal): Promise<void>;
  checkAnswer(stepId: string, answer: string, signal: AbortSignal): Promise<CheckResult>;
  markCurrentStep?(stepId: string): void;
}

export interface FixtureDeskAdapterOptions {
  latencyMs?: number;
}

function delay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException("The operation was aborted", "AbortError"));
      return;
    }
    const onAbort = () => {
      window.clearTimeout(timer);
      reject(new DOMException("The operation was aborted", "AbortError"));
    };
    const timer = window.setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

/**
 * Deterministic fixture grader, matching the frozen prototype's rule: after
 * stripping whitespace, the answer must contain “未定式” AND either
 * “不是极限” or “不是一个确定” to pass.
 */
export function createFixtureDeskAdapter(options: FixtureDeskAdapterOptions = {}): DeskAdapter {
  const latencyMs = options.latencyMs ?? 650;
  return {
    async loadDesk(signal) {
      await delay(latencyMs, signal);
      return deskFixtureData;
    },
    persistDraft() {
      // The development fixture has no browser recovery store.
    },
    async saveDraft(_stepId, _answer, signal) {
      await delay(latencyMs, signal);
    },
    async checkAnswer(_stepId, answer, signal) {
      await delay(latencyMs, signal);
      const normalized = answer.replace(/\s/g, "");
      const passed =
        normalized.includes("未定式") &&
        (normalized.includes("不是极限") || normalized.includes("不是一个确定"));
      return passed ? completedResult : needsRevisionResult;
    },
  };
}
