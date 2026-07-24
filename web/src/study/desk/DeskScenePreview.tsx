// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useMemo } from "react";
import type { DeskAdapter } from "./deskAdapter";
import { completedResult, deskFixtureData, needsRevisionResult } from "./deskFixtures";
import DeskScene, { type DeskSceneProps } from "./DeskScene";

const COMPLETED_FIXTURE_ANSWER =
  "代入后得到 0/0。0/0 是未定式，不是极限值，所以还需要继续分析并做等价变形。";

type FixtureId = "d0" | "n0" | "a1" | "f0" | "f1";

function readFixtureParam(): FixtureId | null {
  if (typeof window === "undefined") return null;
  const value = new URLSearchParams(window.location.search).get("fixture");
  return value === "d0" || value === "n0" || value === "a1" || value === "f0" || value === "f1"
    ? value
    : null;
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

function createFixtureDeskAdapter(latencyMs = 650): DeskAdapter {
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
        normalized.includes("未定式")
        && (normalized.includes("不是极限") || normalized.includes("不是一个确定"));
      return passed ? completedResult : needsRevisionResult;
    },
    async reviewCard(_itemId, _grade, signal) {
      await delay(latencyMs, signal);
      return deskFixtureData.dueCards[0];
    },
    async loadActivities(signal) {
      await delay(latencyMs, signal);
      return deskFixtureData.activities;
    },
  };
}

function snapshotFor(fixture: FixtureId | null): DeskSceneProps["initialSnapshot"] {
  if (fixture === null || fixture === "d0") return { density: "overview" };
  if (fixture === "a1") return { density: "focused", activity: "dirty" };
  if (fixture === "f0") {
    return {
      density: "focused",
      activity: "needs_revision",
      checkResult: needsRevisionResult,
    };
  }
  if (fixture === "f1") {
    return {
      density: "focused",
      activity: "completed",
      answer: COMPLETED_FIXTURE_ANSWER,
      checkResult: completedResult,
    };
  }
  return { density: "focused" };
}

export default function DeskScenePreview() {
  const adapter = useMemo(() => createFixtureDeskAdapter(), []);
  const initialSnapshot = useMemo(() => snapshotFor(readFixtureParam()), []);
  return <DeskScene adapter={adapter} initialSnapshot={initialSnapshot} />;
}
