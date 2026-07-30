// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { beforeEach, describe, expect, it } from "vitest";
import {
  bindStudyHandoff,
  buildStudyChatPrompt,
  buildStudyNanaPrompt,
  clearSessionStudyHandoff,
  getStudyReturnState,
  parseStudyChatHandoff,
  persistPendingStudyHandoff,
  readPendingStudyHandoff,
  readSessionStudyHandoff,
  resolveStudyChatSessionId,
  type StudyChatHandoffV1,
  type StudyChatHandoffV2,
} from "./studyChatHandoff";

function fixture(overrides: Partial<StudyChatHandoffV1> = {}): StudyChatHandoffV1 {
  return {
    version: 1,
    mode: "study",
    sessionId: "session-a",
    spaceId: "space-a",
    spaceTitle: "高等数学",
    focusKind: "quiz_step",
    focusId: "question-2",
    focusLabel: "练习 · 第 2 步",
    intent: "explain",
    originSurface: "study_desk",
    returnTarget: {
      path: "/study/space-a/practice",
      fallbackPath: "/study/space-a",
      focus: "answer",
    },
    revision: 1,
    question: "为什么 0/0 不是答案？",
    prompt: "计算这个极限。",
    answer: "直接代入是 0/0。",
    feedback: "还需要说明未定式。",
    deskSnapshot: {
      activity: "needs_revision",
      answer: "直接代入是 0/0。",
      checkResult: {
        verdict: "needs_revision",
        goodLabel: "已经完成作答",
        good: "答案已保留。",
        gap: "还需要说明未定式。",
        next: "继续修改。",
      },
    },
    createdAt: "2026-07-24T00:00:00.000Z",
    ...overrides,
  };
}

describe("study Chat handoff contract", () => {
  beforeEach(() => window.localStorage.clear());

  it("validates a versioned Study handoff and rejects unsafe return paths", () => {
    expect(parseStudyChatHandoff(fixture())).toMatchObject({
      sessionId: "session-a",
      returnTarget: { path: "/study/space-a/practice" },
    });
    expect(parseStudyChatHandoff(fixture({
      returnTarget: { path: "/settings", fallbackPath: "/study/space-a", focus: "answer" },
    }))).toBeNull();
  });

  it("binds context to one explicit session and supports explicit unbind", () => {
    bindStudyHandoff(fixture());
    expect(readSessionStudyHandoff("session-a")?.spaceId).toBe("space-a");
    expect(readSessionStudyHandoff("session-b")).toBeNull();
    clearSessionStudyHandoff("session-a");
    expect(readSessionStudyHandoff("session-a")).toBeNull();
  });

  it("keeps an unsent handoff recoverable until Chat confirms a real session", () => {
    persistPendingStudyHandoff(fixture());
    bindStudyHandoff(fixture());
    expect(readPendingStudyHandoff()?.sessionId).toBe("session-a");
    expect(readSessionStudyHandoff("session-a")?.spaceId).toBe("space-a");
  });

  it("reuses one session for the same course focus without conflating another focus", () => {
    const first = resolveStudyChatSessionId("space-a", "question-2");
    expect(resolveStudyChatSessionId("space-a", "question-2")).toBe(first);
    expect(resolveStudyChatSessionId("space-a", "question-3")).not.toBe(first);
  });

  it("builds a visible prompt from the learner-approved context", () => {
    const prompt = buildStudyChatPrompt(fixture());
    expect(prompt).toContain("我的当前答案：直接代入是 0/0。");
    expect(prompt).toContain("我的问题：为什么 0/0 不是答案？");
    expect(prompt).toContain("不要直接替我改写答案");
  });

  it("parses a page-discriminated v2 handoff and keeps the learner input separate", () => {
    const handoff: StudyChatHandoffV2 = {
      version: 2,
      mode: "study",
      sessionId: "session-v2",
      spaceId: "space-a",
      spaceTitle: "高等数学",
      focusKind: "learn",
      focusId: "core-1",
      focusLabel: "极限唯一性",
      intent: "collaborate",
      originSurface: "study_desk",
      returnTarget: { path: "/study/space-a/learn", fallbackPath: "/study/space-a/flyleaf", focus: "learner-draft" },
      revision: 1,
      nanaContext: {
        schemaVersion: 1,
        course: { id: "space-a", title: "高等数学" },
        origin: { page: "learn", route: "/study/space-a/learn", focusId: "core-1", knowledgeCoreId: "core-1", revision: 1 },
        returnTarget: { path: "/study/space-a/learn", fallbackPath: "/study/space-a/flyleaf", focus: "learner-draft", revision: 1 },
        pageContext: { kind: "learn", knowledgeCore: { id: "core-1", title: "极限唯一性", keyStatement: "极限若存在则唯一" }, learnerDraft: "我的说法", comparisonStage: "drafted" },
        sourceRefs: [{ id: "source-1", title: "教材 2.3", excerpt: "极限若存在则唯一" }],
      },
      createdAt: "2026-07-29T08:00:00.000Z",
    };
    expect(parseStudyChatHandoff(handoff)).toEqual(handoff);
    const prompt = buildStudyNanaPrompt(handoff, "给我一个反例，先别讲完");
    expect(prompt).toContain("不得代写 learnerDraft");
    expect(prompt).toContain("给我一个反例，先别讲完");
    expect(prompt).toContain('"kind":"learn"');
  });

  it("fails closed when a v2 origin page disagrees with its page context", () => {
    const invalid = {
      version: 2, mode: "study", sessionId: "s", spaceId: "space-a", spaceTitle: "课程",
      focusKind: "learn", focusId: "core-1", focusLabel: "核心", intent: "collaborate",
      originSurface: "study_desk", returnTarget: { path: "/study/space-a/learn", fallbackPath: "/study/space-a/flyleaf", focus: "draft" },
      revision: 1, createdAt: "2026-07-29T08:00:00.000Z",
      nanaContext: {
        schemaVersion: 1, course: { id: "space-a", title: "课程" },
        origin: { page: "learn", route: "/study/space-a/learn", focusId: "core-1", revision: 1 },
        returnTarget: { path: "/study/space-a/learn", fallbackPath: "/study/space-a/flyleaf", focus: "draft", revision: 1 },
        pageContext: { kind: "plan" }, sourceRefs: [],
      },
    };
    expect(parseStudyChatHandoff(invalid)).toBeNull();
  });

  it("fails closed when a v2 context crosses courses or return targets", () => {
    const valid = {
      version: 2, mode: "study", sessionId: "s", spaceId: "space-a", spaceTitle: "课程 A",
      focusKind: "plan", focusId: "plan:space-a", focusLabel: "当前计划", intent: "collaborate",
      originSurface: "study_desk", returnTarget: { path: "/study/space-a/plan", fallbackPath: "/study/space-a/flyleaf", focus: "plan:space-a" },
      revision: 1, createdAt: "2026-07-29T08:00:00.000Z",
      nanaContext: {
        schemaVersion: 1, course: { id: "space-b", title: "课程 A" },
        origin: { page: "plan", route: "/study/space-a/plan", focusId: "plan:space-a", revision: 1 },
        returnTarget: { path: "/study/space-a/plan", fallbackPath: "/study/space-a/flyleaf", focus: "plan:space-a", revision: 1 },
        pageContext: { kind: "plan" }, sourceRefs: [],
      },
    };
    expect(parseStudyChatHandoff(valid)).toBeNull();
    valid.nanaContext.course.id = "space-a";
    valid.nanaContext.returnTarget.path = "/study/space-a/learn";
    expect(parseStudyChatHandoff(valid)).toBeNull();
  });

  it("parses exact-return focus state and rejects malformed state", () => {
    expect(getStudyReturnState({
      studyReturn: {
        version: 1,
        stepId: "question-2",
        focus: "answer",
        deskSnapshot: fixture().deskSnapshot,
      },
    })).toEqual({
      version: 1,
      stepId: "question-2",
      focus: "answer",
      deskSnapshot: fixture().deskSnapshot,
    });
    expect(getStudyReturnState({
      studyReturn: { version: 1, stepId: "", focus: "answer" },
    })).toBeNull();
  });
});
