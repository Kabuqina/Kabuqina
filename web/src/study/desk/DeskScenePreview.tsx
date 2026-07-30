// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useMemo, useState } from "react";
import type { MessageRow } from "../../chat/chat-api";
import type { StudyMaterialReaderResponse } from "../../chat/study/study-api";
import type { StudyChatHandoffV2 } from "../../lib/studyChatHandoff";
import type { StudyPageSlug } from "../routeModel";
import type { DeskAdapter } from "./deskAdapter";
import type { StudyRepository, StudySpaceSummary } from "../repository";
import { StudyRepositoryProvider } from "../repositoryContext";
import { ScratchDesk } from "../ScratchDesk";
import { completedResult, deskFixtureData, needsRevisionResult } from "./deskFixtures";
import DeskScene, { type DeskSceneProps } from "./DeskScene";
import { StudyMaterialReader } from "./StudyMaterialReader";
import { StudyNanaPanel } from "./StudyNanaPanel";

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

function readScratchParam(): boolean {
  if (typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).get("scratch") === "1";
}

function readFailParam(): boolean {
  if (typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).get("fail") === "1";
}

function readPanelParam(): "nana" | "reader" | null {
  if (typeof window === "undefined") return null;
  const value = new URLSearchParams(window.location.search).get("panel");
  return value === "nana" || value === "reader" ? value : null;
}

function readBookmarkParam(): "draft" | "revision" | "completed" | null {
  if (typeof window === "undefined") return null;
  const value = new URLSearchParams(window.location.search).get("bookmark");
  return value === "draft" || value === "revision" || value === "completed" ? value : null;
}

function nanaPreviewHandoff(page: StudyPageSlug): StudyChatHandoffV2 {
  const nanaPage = page === "flyleaf" || page === "plan" || page === "learn" || page === "practice" || page === "evaluate"
    ? page
    : "learn";
  return {
    version: 2,
    mode: "study",
    sessionId: `preview-${nanaPage}`,
    spaceId: "fixture-calculus",
    spaceTitle: "高等数学",
    focusKind: nanaPage,
    focusId: "limit-core",
    focusLabel: nanaPage === "practice" ? "极限与未定式 · 当前练习" : "极限与未定式",
    intent: "collaborate",
    originSurface: "study_desk",
    returnTarget: { path: `/study/fixture-calculus/${nanaPage}`, fallbackPath: "/study/fixture-calculus", focus: "limit-core" },
    revision: 1,
    nanaContext: {
      schemaVersion: 1,
      course: { id: "fixture-calculus", title: "高等数学" },
      origin: { page: nanaPage, route: `/study/fixture-calculus/${nanaPage}`, focusId: "limit-core", revision: 1 },
      returnTarget: { path: `/study/fixture-calculus/${nanaPage}`, fallbackPath: "/study/fixture-calculus", focus: "limit-core", revision: 1 },
      pageContext: { kind: nanaPage },
      sourceRefs: [{ id: "calculus-textbook", title: "高等数学教材" }],
    },
    createdAt: "2026-07-30T09:00:00+08:00",
  };
}

const PREVIEW_MESSAGES: MessageRow[] = [
  { role: "user", content: "为什么 0/0 不能直接当作极限值？" },
  { role: "assistant", content: "先别急着算。0/0 只说明原式在这里没有给出唯一结果；我们先比较两个会得到不同极限的例子。" },
];

const PREVIEW_READER: StudyMaterialReaderResponse = {
  artifactId: "calculus-textbook",
  title: "高等数学教材",
  filename: "高等数学.pdf",
  suffix: ".pdf",
  totalPages: 342,
  pageStart: 42,
  pageEnd: 47,
  content: "<!-- page:42 -->\n## 1.6 极限存在准则\n\n夹逼准则把一个难以直接处理的函数放在两个具有相同极限的函数之间。\n\n<!-- page:43 -->\n### 两个重要极限\n\n本节只呈现原教材内容；学习页仍停留在当前知识核。",
  outline: [
    { id: "chapter-1", title: "第一章 函数、极限与连续", level: 1, page: 1, children: [
      { id: "section-1-6", title: "1.6 极限存在准则", level: 2, page: 42 },
      { id: "section-1-7", title: "1.7 无穷小的比较", level: 2, page: 48 },
    ] },
    { id: "chapter-2", title: "第二章 导数与微分", level: 1, page: 65 },
  ],
  textQuality: "sufficient",
  warning: "",
};

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

/** 杂记本的后端还不存在（账本 B-12），所以预览用一份固定页面看排版与物性。 */
function scratchPreviewRepository(): StudyRepository {
  return {
    loadScratch: async () => ({
      pad: "",
      notes: [
        { id: "s1", text: "读到一句：数学里的等号，是在说两个不同的写法，指的是同一个东西。", origin: "来自对话 · 昨天" },
      ],
    }),
    saveScratchPad: async () => undefined,
    fileScratchNote: async () => undefined,
  } as unknown as StudyRepository;
}

const SCRATCH_PREVIEW_SPACES: StudySpaceSummary[] = [
  { id: "fixture-calculus", title: "高等数学", status: "active", isCurrent: false, kind: "course" },
  { id: "fixture-physics", title: "大学物理", status: "active", isCurrent: false, kind: "course" },
  { id: "fixture-scratch", title: "杂记本", status: "active", isCurrent: true, kind: "scratch" },
];

export default function DeskScenePreview() {
  const page = useMemo(readPageParam, []);
  const scratch = useMemo(readScratchParam, []);
  const fail = useMemo(readFailParam, []);
  const adapter = useMemo(() => createFixtureDeskAdapter(650, fail), [fail]);
  const initialSnapshot = useMemo(() => snapshotFor(readFixtureParam()), []);
  const bookmark = useMemo(readBookmarkParam, []);
  const [panel, setPanel] = useState<"nana" | "reader" | null>(() => readPanelParam());
  const handoff = useMemo(() => nanaPreviewHandoff(page), [page]);
  const bookstandFallback = useMemo(() => ({
    ...deskFixtureData.bookstand,
    currentTitle: deskFixtureData.course.name,
  }), []);
  if (scratch) {
    return (
      <StudyRepositoryProvider repository={scratchPreviewRepository()}>
        <ScratchDesk
          spaceId="fixture-scratch"
          spaces={SCRATCH_PREVIEW_SPACES}
          onSelectSpace={() => undefined}
          onNewBook={() => undefined}
          onAskNana={() => undefined}
        />
      </StudyRepositoryProvider>
    );
  }

  return (
    <>
      <DeskScene
        adapter={adapter}
        initialSnapshot={initialSnapshot}
        currentPage={page}
        continueTitle={bookmark === "revision"
          ? "0/0 是什么 · 待修改"
          : bookmark === "draft"
            ? "0/0 是什么 · 草稿"
            : bookmark === "completed"
              ? "0/0 是什么"
              : undefined}
        continueMeta={bookmark === "revision"
          ? "第一章 · 极限 · 练习 · 待修改"
          : bookmark === "draft"
            ? "第一章 · 极限 · 练习 · 草稿未检查"
            : bookmark === "completed"
              ? "第一章 · 极限 · 练习 · 已完成"
              : undefined}
        bookstandFallback={bookstandFallback}
        onAskPage={() => setPanel("nana")}
        onOpenMaterials={() => setPanel("reader")}
        pageBody={page === "practice" ? undefined : (
          <section className="kd-overview-copy">
            <p className="kd-page-kicker">开发预览</p>
            <h2>{page}</h2>
            <p>生产里这里是 StudyPageOutlet 铺进来的那一页。</p>
          </section>
        )}
      />
      {panel === "nana" ? (
        <StudyNanaPanel
          handoff={handoff}
          onClose={() => setPanel(null)}
          onOpenFull={() => undefined}
          loadMessages={async () => ({ messages: PREVIEW_MESSAGES })}
        />
      ) : null}
      {panel === "reader" ? (
        <StudyMaterialReader
          spaceId="fixture-calculus"
          artifactId="calculus-textbook"
          initialPage={42}
          onClose={() => setPanel(null)}
          readMaterial={async (_spaceId, _artifactId, pageStart, pageEnd) => {
            const start = pageStart ?? 42;
            return {
              ...PREVIEW_READER,
              pageStart: start,
              pageEnd: pageEnd ?? start + 5,
              content: `<!-- page:${start} -->\n## ${start === 42 ? "1.6 极限存在准则" : `教材第 ${start} 页`}\n\n这是从原文件中读取的正文预览。Study 仍保留在左边，可以随时对照。`,
            };
          }}
        />
      ) : null}
    </>
  );
}
