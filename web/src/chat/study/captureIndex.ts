// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { StudyFlashcardsResponse } from "./study-api";

export const STUDY_LEARNING_EVENT = "study-learning-event";

export type CaptureIndexStatus = "idle" | "loading" | "ready" | "unavailable";
type Listener = () => void;
type Fetcher = () => Promise<StudyFlashcardsResponse>;

type CaptureIndexOptions = {
  fetcher?: Fetcher;
  target?: EventTarget | null;
};

function normalizeFront(front: unknown): string {
  return typeof front === "string" ? front.trim().toLowerCase() : "";
}

async function defaultFetcher(): Promise<StudyFlashcardsResponse> {
  const api = await import("./study-api");
  const spaces = await api.cmdStudySpaces();
  return spaces.currentSpaceId
    ? api.cmdStudyFlashcards(spaces.currentSpaceId)
    : { cards: [] };
}

export function createCaptureIndex(options: CaptureIndexOptions = {}) {
  const fetcher = options.fetcher ?? defaultFetcher;
  const target = options.target ?? (typeof window !== "undefined" ? window : null);
  let fronts = new Set<string>();
  let currentStatus: CaptureIndexStatus = "idle";
  let pending: Promise<void> | null = null;
  const listeners = new Set<Listener>();

  const notify = () => {
    for (const listener of listeners) listener();
  };

  const refresh = async () => {
    currentStatus = "loading";
    notify();
    try {
      const response = await fetcher();
      fronts = new Set((response.cards ?? []).map((card) => normalizeFront(card.front)).filter(Boolean));
      currentStatus = "ready";
    } catch {
      fronts = new Set();
      currentStatus = "unavailable";
    }
    notify();
  };

  const initialize = () => {
    if (currentStatus === "ready" || currentStatus === "unavailable") {
      return Promise.resolve();
    }
    if (!pending) {
      pending = refresh().finally(() => {
        pending = null;
      });
    }
    return pending;
  };

  const forceRefresh = () => {
    pending = refresh().finally(() => {
      pending = null;
    });
    return pending;
  };

  target?.addEventListener(STUDY_LEARNING_EVENT, () => {
    void forceRefresh();
  });

  return {
    initialize,
    has(front: string): boolean {
      if (currentStatus === "idle") void initialize();
      const key = normalizeFront(front);
      return Boolean(key && fronts.has(key));
    },
    markCaptured(front: string) {
      const key = normalizeFront(front);
      if (!key) return;
      fronts.add(key);
      if (currentStatus !== "unavailable") currentStatus = "ready";
      notify();
    },
    subscribe(listener: Listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    status(): CaptureIndexStatus {
      return currentStatus;
    },
  };
}

export const captureIndex = createCaptureIndex();
