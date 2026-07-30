// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { beforeEach, describe, expect, it, vi } from "vitest";
import type { StudyQuizResult } from "../../chat/study/study-api";
import type { StudyRepository } from "../repository";
import { STUDY_LEARNING_EVENT } from "../learningEvent";
import { readStudyLocation, selectKnowledgeCore } from "../studyLocation";
import { createStudyDeskAdapter, resolveWrongbookPracticeTarget } from "./studyDeskAdapter";

function repository(overrides: Partial<StudyRepository> = {}): StudyRepository {
  return {
    loadPracticeHome: vi.fn().mockResolvedValue({
      cards: [],
      dueCards: [{ item_id: "due-1" }, { item_id: "due-2" }],
      quizzes: [{
        artifact_id: "quiz-1",
        kind: "quiz",
        title: "向量检查",
        status: "active",
      }],
    }),
    loadLearnHome: vi.fn().mockResolvedValue({
      artifacts: [{
        artifact_id: "material-1",
        kind: "resource_pack",
        title: "向量讲义",
        status: "active",
      }],
      knowledgePoints: [
        { item_id: "core-vector", artifact_id: "deck-1", front: "向量", gist: "有大小和方向的量", captured: true },
        { item_id: "core-length", artifact_id: "deck-1", front: "模长", gist: "向量的长度", captured: true },
      ],
    }),
    loadScratch: vi.fn(), saveScratchPad: vi.fn(), fileScratchNote: vi.fn(),
    loadActivities: vi.fn().mockResolvedValue({
      items: [{
        activity_id: "activity-1",
        activity_type: "quiz.attempt",
        artifact_id: "quiz-1",
        created_at: "2026-07-24T08:00:00Z",
      }],
      count: 1,
      returned: 1,
      limit: 50,
      truncated: false,
    }),
    loadQuizQuestions: vi.fn().mockResolvedValue([
      {
        item_id: "question-1",
        artifact_id: "quiz-1",
        type: "choice",
        prompt: "选择单位向量",
        options: ["(1, 0)", "(2, 0)"],
        tags: ["向量"],
      },
      {
        item_id: "question-2",
        artifact_id: "quiz-1",
        type: "short_answer",
        prompt: "解释长度",
        tags: ["模长"],
      },
    ]),
    submitQuiz: vi.fn(),
    ...overrides,
  } as unknown as StudyRepository;
}

describe("Study desk adapter", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("resolves a wrongbook activity back to its exact question and knowledge core", async () => {
    const source = repository({
      resolvePracticeSource: vi.fn().mockResolvedValue({ artifact_id: "quiz-1", item_ids: ["question-2"] }),
    });

    await expect(resolveWrongbookPracticeTarget(
      source,
      "space-a",
      "attempt-1",
      new AbortController().signal,
    )).resolves.toMatchObject({
      status: "resolved",
      point: { item_id: "core-length" },
      exerciseId: "question-2",
    });
    expect(source.resolvePracticeSource).toHaveBeenCalledWith("space-a", "attempt-1", expect.any(AbortSignal));
  });

  it("does not substitute another knowledge core when a wrongbook question no longer maps", async () => {
    const source = repository({
      resolvePracticeSource: vi.fn().mockResolvedValue({ artifact_id: "quiz-1", item_ids: ["question-2"] }),
      loadLearnHome: vi.fn().mockResolvedValue({
        artifacts: [],
        knowledgePoints: [{ item_id: "core-vector", artifact_id: "deck-1", front: "向量", gist: "大小与方向", captured: true }],
      }),
    });

    await expect(resolveWrongbookPracticeTarget(
      source,
      "space-a",
      "attempt-1",
      new AbortController().signal,
    )).resolves.toEqual({ status: "core_missing" });
  });

  it("maps the canonical Study practice source into the desk and restores its local recovery draft", async () => {
    const source = repository();
    const adapter = createStudyDeskAdapter({
      repository: source,
      spaceId: "space-a",
      spaces: [
        { id: "space-a", title: "线性代数", status: "active", isCurrent: true, kind: "course" as const },
        { id: "space-b", title: "物理", status: "active", isCurrent: false, kind: "course" as const },
      ],
    });
    const signal = new AbortController().signal;

    const first = await adapter.loadDesk(signal);
    expect(first.course).toEqual({ name: "线性代数", notebookLabel: "向量 · 1 题" });
    expect(first.steps[0]).toMatchObject({
      id: "question-1",
      artifactId: "quiz-1",
      answerKind: "choice",
      options: ["(1, 0)", "(2, 0)"],
      initialDraft: "",
    });
    expect(first.dueCount).toBe(2);
    expect(first.materials.items[0]).toMatchObject({ id: "material-1", title: "向量讲义" });
    expect(first.activities[0]).toMatchObject({ id: "activity-1", type: "quiz.attempt" });

    await adapter.saveDraft("question-1", "[1]", signal);
    adapter.markCurrentStep?.("question-1");
    const restored = await adapter.loadDesk(signal);
    expect(restored.initialStepIndex).toBe(0);
    expect(restored.steps[0].initialDraft).toBe("[1]");
    expect(restored.steps[0].initialActivity).toBe("dirty");
    expect(restored.overview.heading).toContain("继续");
  });

  it("uses the shared knowledge-core cursor and never substitutes another core's question", async () => {
    const lengthCore = {
      item_id: "core-length",
      artifact_id: "deck-1",
      front: "模长",
      gist: "向量的长度",
      captured: true as const,
    };
    selectKnowledgeCore("space-a", lengthCore, "learn");
    const adapter = createStudyDeskAdapter({
      repository: repository(),
      spaceId: "space-a",
      spaces: [{ id: "space-a", title: "线性代数", status: "active", isCurrent: true, kind: "course" as const }],
    });

    const desk = await adapter.loadDesk(new AbortController().signal);
    expect(desk.activeKnowledgeCoreIndex).toBe(1);
    expect(desk.steps.map((step) => step.id)).toEqual(["question-2"]);
    expect(readStudyLocation("space-a")).toMatchObject({
      page: "practice",
      knowledgeCoreId: "core-length",
    });
  });

  it("prefers stable core ids and orders active exercises by honest provenance", async () => {
    const source = repository({
      loadPracticeHome: vi.fn().mockResolvedValue({
        cards: [],
        dueCards: [],
        quizzes: [
          { artifact_id: "quiz-adapted", kind: "quiz", title: "改编", status: "active" },
          { artifact_id: "quiz-source", kind: "quiz", title: "原题", status: "active" },
          { artifact_id: "quiz-generated", kind: "quiz", title: "生成", status: "active" },
          { artifact_id: "quiz-legacy", kind: "quiz", title: "旧题", status: "active" },
        ],
      }),
      loadQuizQuestions: vi.fn().mockImplementation((_spaceId: string, artifactId: string) => Promise.resolve({
        "quiz-adapted": [{
          item_id: "adapted-1", artifact_id: artifactId, type: "short_answer", prompt: "改编题",
          knowledge_core_id: "core-vector", origin: "adapted", tags: ["完全不同的旧标签"],
          source_refs: [{ title: "线性代数", locator: "第 18 页" }],
        }],
        "quiz-source": [{
          item_id: "source-1", artifact_id: artifactId, type: "short_answer", prompt: "资料题",
          knowledge_core_id: "core-vector", origin: "source",
          source_refs: [{ title: "线性代数", section: "向量", page: 17 }],
        }],
        "quiz-generated": [
          {
            item_id: "generated-1", artifact_id: artifactId, type: "short_answer", prompt: "补充题",
            knowledge_core_id: "core-vector", origin: "generated",
          },
          {
            item_id: "wrong-core", artifact_id: artifactId, type: "short_answer", prompt: "别的知识核",
            knowledge_core_id: "core-length", origin: "generated", tags: ["向量"],
          },
        ],
        "quiz-legacy": [{
          item_id: "legacy-1", artifact_id: artifactId, type: "short_answer", prompt: "兼容旧题", tags: ["向量"],
        }],
      }[artifactId] ?? [])),
    });
    const adapter = createStudyDeskAdapter({
      repository: source,
      spaceId: "space-a",
      spaces: [{ id: "space-a", title: "线性代数", status: "active", isCurrent: true, kind: "course" as const }],
    });

    const desk = await adapter.loadDesk(new AbortController().signal);

    expect(desk.steps.map((step) => step.id)).toEqual([
      "source-1",
      "adapted-1",
      "generated-1",
      "legacy-1",
    ]);
    expect(desk.steps[0]).toMatchObject({
      origin: "source",
      sourceLabel: "线性代数 · 向量 · 第 17 页",
    });
    expect(desk.steps[1]).toMatchObject({
      origin: "adapted",
      sourceLabel: "线性代数 · 第 18 页",
    });
  });

  it("submits a question to the quiz artifact that actually owns it", async () => {
    const submitQuiz = vi.fn().mockResolvedValue({
      activity_id: "activity-second",
      score: 1,
      maxScore: 1,
      percent: 100,
      correctCount: 1,
      total: 1,
      weakTags: [],
      perQuestion: [{
        item_id: "question-second",
        prompt: "解释向量方向",
        type: "short_answer",
        correct: true,
        earned: 1,
        points: 1,
        explanation: "已经说明方向。",
      }],
    } satisfies StudyQuizResult);
    const source = repository({
      loadPracticeHome: vi.fn().mockResolvedValue({
        cards: [],
        dueCards: [],
        quizzes: [
          { artifact_id: "quiz-first", kind: "quiz", title: "第一份", status: "active" },
          { artifact_id: "quiz-second", kind: "quiz", title: "第二份", status: "active" },
        ],
      }),
      loadQuizQuestions: vi.fn().mockImplementation((_spaceId: string, artifactId: string) => Promise.resolve(
        artifactId === "quiz-second"
          ? [{
            item_id: "question-second",
            artifact_id: "quiz-second",
            type: "short_answer",
            prompt: "解释向量方向",
            knowledge_core_id: "core-vector",
            origin: "generated",
          }]
          : [],
      )),
      submitQuiz,
    });
    const adapter = createStudyDeskAdapter({
      repository: source,
      spaceId: "space-a",
      spaces: [{ id: "space-a", title: "线性代数", status: "active", isCurrent: true, kind: "course" as const }],
    });
    const signal = new AbortController().signal;

    await adapter.loadDesk(signal);
    await adapter.checkAnswer("question-second", "向量有确定方向", signal);

    expect(submitQuiz).toHaveBeenCalledWith(
      "space-a",
      "quiz-second",
      { "question-second": { text: "向量有确定方向" } },
      signal,
      ["question-second"],
    );
  });

  it("keeps an honest empty practice state when the current core has no question", async () => {
    const emptyCore = {
      item_id: "core-empty",
      artifact_id: "deck-1",
      front: "方向角",
      gist: "向量与坐标轴的夹角",
      captured: true as const,
    };
    selectKnowledgeCore("space-a", emptyCore, "practice");
    const source = repository({
      loadLearnHome: vi.fn().mockResolvedValue({ artifacts: [], knowledgePoints: [emptyCore] }),
    });
    const adapter = createStudyDeskAdapter({
      repository: source,
      spaceId: "space-a",
      spaces: [{ id: "space-a", title: "线性代数", status: "active", isCurrent: true, kind: "course" as const }],
    });

    const desk = await adapter.loadDesk(new AbortController().signal);
    expect(desk.steps).toEqual([]);
    expect(desk.overview.body).toContain("还没有可用练习");
    expect(readStudyLocation("space-a")?.knowledgeCoreId).toBe("core-empty");
  });

  it("updates the automatic bookmark when a practice draft changes state", async () => {
    const adapter = createStudyDeskAdapter({
      repository: repository(),
      spaceId: "space-a",
      spaces: [{ id: "space-a", title: "线性代数", status: "active", isCurrent: true, kind: "course" as const }],
    });
    await adapter.loadDesk(new AbortController().signal);

    adapter.markPracticeState?.("question-1", "dirty");
    expect(readStudyLocation("space-a")).toMatchObject({
      knowledgeCoreId: "core-vector",
      exerciseId: "question-1",
      activity: "dirty",
    });
  });

  it("checks and records only the current question through the existing Study repository", async () => {
    const result: StudyQuizResult = {
      activity_id: "activity-1",
      score: 1,
      maxScore: 1,
      percent: 100,
      correctCount: 1,
      total: 1,
      weakTags: [],
      perQuestion: [{
        item_id: "question-1",
        prompt: "选择单位向量",
        type: "choice",
        correct: true,
        earned: 1,
        points: 1,
        explanation: "长度为 1。",
      }],
    };
    const submitQuiz = vi.fn().mockResolvedValue(result);
    const adapter = createStudyDeskAdapter({
      repository: repository({ submitQuiz }),
      spaceId: "space-a",
      spaces: [{ id: "space-a", title: "线性代数", status: "active", isCurrent: true, kind: "course" as const }],
    });
    const signal = new AbortController().signal;
    const learningEvent = vi.fn();
    window.addEventListener(STUDY_LEARNING_EVENT, learningEvent);

    await adapter.loadDesk(signal);
    await adapter.saveDraft("question-1", "[0]", signal);
    await expect(adapter.checkAnswer("question-1", "[0]", signal)).resolves.toEqual({
      verdict: "completed",
      annotationKind: "confirmed",
      goodLabel: "这一点已经说明清楚",
      good: "长度为 1。",
      gap: "",
      next: "",
    });
    expect(submitQuiz).toHaveBeenCalledWith(
      "space-a",
      "quiz-1",
      { "question-1": { selected: [0] } },
      signal,
      ["question-1"],
    );
    expect(learningEvent).toHaveBeenCalledOnce();
    const restored = await adapter.loadDesk(signal);
    expect(restored.steps[0]).toMatchObject({
      initialDraft: "[0]",
      initialActivity: "completed",
      initialCheckResult: {
        verdict: "completed",
        annotationKind: "confirmed",
        good: "长度为 1。",
      },
    });
    expect(restored.overview.heading).toContain("继续");
    window.removeEventListener(STUDY_LEARNING_EVENT, learningEvent);
  });

  it.each([
    {
      label: "incorrect",
      grade: {
        item_id: "question-1",
        prompt: "选择单位向量",
        type: "choice" as const,
        correct: false,
        earned: 0,
        points: 1,
        failure_summary: "这个选项的长度不是 1。",
      },
    },
    {
      label: "ungraded",
      grade: {
        item_id: "question-1",
        prompt: "选择单位向量",
        type: "choice" as const,
        correct: false,
        earned: 0,
        points: 0,
        ungraded: true,
        gradable: false,
        failure_summary: "暂时不能自动判断。",
      },
    },
  ])("keeps the recovery answer after a $label result", async ({ grade }) => {
    const submitQuiz = vi.fn().mockResolvedValue({
      activity_id: `activity-${grade.item_id}`,
      score: 0,
      maxScore: grade.points,
      percent: 0,
      correctCount: 0,
      total: 1,
      weakTags: [],
      perQuestion: [grade],
    } satisfies StudyQuizResult);
    const adapter = createStudyDeskAdapter({
      repository: repository({ submitQuiz }),
      spaceId: "space-a",
      spaces: [{ id: "space-a", title: "线性代数", status: "active", isCurrent: true, kind: "course" as const }],
    });
    const signal = new AbortController().signal;

    await adapter.loadDesk(signal);
    await adapter.saveDraft("question-1", "[1]", signal);
    await expect(adapter.checkAnswer("question-1", "[1]", signal)).resolves.toMatchObject({
      verdict: "needs_revision",
    });

    const restored = await adapter.loadDesk(signal);
    expect(restored.steps[0].initialDraft).toBe("[1]");
    expect(restored.steps[0].initialActivity).toBe("needs_revision");
    expect(restored.steps[0].initialCheckResult).toMatchObject({ verdict: "needs_revision" });
    expect(restored.overview.heading).toContain("继续");
  });

  it("keeps the canonical exercise usable when recovery storage is unavailable", async () => {
    const adapter = createStudyDeskAdapter({
      repository: repository(),
      spaceId: "space-a",
      spaces: [{ id: "space-a", title: "线性代数", status: "active", isCurrent: true, kind: "course" as const }],
    });
    const signal = new AbortController().signal;
    await adapter.loadDesk(signal);
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("storage blocked", "SecurityError");
    });

    expect(() => adapter.markCurrentStep?.("question-1")).not.toThrow();
    await expect(adapter.saveDraft("question-1", "[0]", signal)).rejects.toThrow(
      "draft recovery storage unavailable",
    );
    setItem.mockRestore();
  });

  it("does not restore an answer draft from another course", async () => {
    const source = repository();
    const spaces = [
      { id: "space-a", title: "线性代数", status: "active", isCurrent: true, kind: "course" as const },
      { id: "space-b", title: "大学物理", status: "active", isCurrent: false, kind: "course" as const },
    ];
    const first = createStudyDeskAdapter({ repository: source, spaceId: "space-a", spaces });
    const second = createStudyDeskAdapter({ repository: source, spaceId: "space-b", spaces });
    const signal = new AbortController().signal;

    await first.loadDesk(signal);
    await first.saveDraft("question-1", "只属于课程 A", signal);
    const otherCourse = await second.loadDesk(signal);

    expect(otherCourse.steps[0].initialDraft).toBe("");
  });
});
