// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useMemo } from "react";
import type { StudyPageSlug } from "../routeModel";
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

const LIFECYCLE_PAGES: StudyPageSlug[] = ["flyleaf", "plan", "learn", "practice", "evaluate"];

/** `?page=` 让书桌承载五页的排版可以逐页看；`?fail=1` 看练习数据打不开时的降级。 */
function readPageParam(): StudyPageSlug {
  if (typeof window === "undefined") return "practice";
  const value = new URLSearchParams(window.location.search).get("page");
  return LIFECYCLE_PAGES.includes(value as StudyPageSlug) ? (value as StudyPageSlug) : "practice";
}

function readFailParam(): boolean {
  if (typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).get("fail") === "1";
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

function createFixtureDeskAdapter(latencyMs = 650, fail = false): DeskAdapter {
  return {
    async loadDesk(signal) {
      await delay(latencyMs, signal);
      // 复刻真实情形：一门还没出题的课，`loadDesk` 会抛 `no active quiz`。
      if (fail) throw new Error("study desk: no active quiz");
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
  const page = useMemo(readPageParam, []);
  const fail = useMemo(readFailParam, []);
  const adapter = useMemo(() => createFixtureDeskAdapter(650, fail), [fail]);
  const initialSnapshot = useMemo(() => snapshotFor(readFixtureParam()), []);
  const bookstandFallback = useMemo(() => ({
    ...deskFixtureData.bookstand,
    currentTitle: deskFixtureData.course.name,
  }), []);
  return (
    <DeskScene
      adapter={adapter}
      initialSnapshot={initialSnapshot}
      currentPage={page}
      bookstandFallback={bookstandFallback}
      pageBody={page === "practice" ? undefined : (
        <section className="kd-overview-copy">
          <p className="kd-page-kicker">开发预览</p>
          <h2>{page}</h2>
          <p>生产里这里是 StudyPageOutlet 铺进来的那一页。</p>
        </section>
      )}
    />
  );
}
