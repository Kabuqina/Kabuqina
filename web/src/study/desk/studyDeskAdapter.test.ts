// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { beforeEach, describe, expect, it, vi } from "vitest";
import type { StudyQuizResult } from "../../chat/study/study-api";
import type { StudyRepository } from "../repository";
import { STUDY_LEARNING_EVENT } from "../learningEvent";
import { createStudyDeskAdapter } from "./studyDeskAdapter";

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

  it("maps the canonical Study practice source into the desk and restores its local recovery draft", async () => {
    const source = repository();
    const adapter = createStudyDeskAdapter({
      repository: source,
      spaceId: "space-a",
      spaces: [
        { id: "space-a", title: "线性代数", status: "active", isCurrent: true },
        { id: "space-b", title: "物理", status: "active", isCurrent: false },
      ],
    });
    const signal = new AbortController().signal;

    const first = await adapter.loadDesk(signal);
    expect(first.course).toEqual({ name: "线性代数", notebookLabel: "向量检查 · 2 步" });
    expect(first.steps[0]).toMatchObject({
      id: "question-1",
      artifactId: "quiz-1",
      answerKind: "choice",
      options: ["(1, 0)", "(2, 0)"],
      initialDraft: "",
    });
    expect(first.dueCount).toBe(2);

    await adapter.saveDraft("question-1", "[1]", signal);
    adapter.markCurrentStep?.("question-1");
    const restored = await adapter.loadDesk(signal);
    expect(restored.initialStepIndex).toBe(0);
    expect(restored.steps[0].initialDraft).toBe("[1]");
    expect(restored.overview.heading).toContain("继续");
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
      spaces: [{ id: "space-a", title: "线性代数", status: "active", isCurrent: true }],
    });
    const signal = new AbortController().signal;
    const learningEvent = vi.fn();
    window.addEventListener(STUDY_LEARNING_EVENT, learningEvent);

    await adapter.loadDesk(signal);
    await adapter.saveDraft("question-1", "[0]", signal);
    await expect(adapter.checkAnswer("question-1", "[0]", signal)).resolves.toEqual({
      verdict: "completed",
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
    expect(restored.steps[0].initialDraft).toBe("");
    expect(restored.overview.heading).not.toContain("继续");
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
      spaces: [{ id: "space-a", title: "线性代数", status: "active", isCurrent: true }],
    });
    const signal = new AbortController().signal;

    await adapter.loadDesk(signal);
    await adapter.saveDraft("question-1", "[1]", signal);
    await expect(adapter.checkAnswer("question-1", "[1]", signal)).resolves.toMatchObject({
      verdict: "needs_revision",
    });

    const restored = await adapter.loadDesk(signal);
    expect(restored.steps[0].initialDraft).toBe("[1]");
    expect(restored.overview.heading).toContain("继续");
  });

  it("keeps the canonical exercise usable when recovery storage is unavailable", async () => {
    const adapter = createStudyDeskAdapter({
      repository: repository(),
      spaceId: "space-a",
      spaces: [{ id: "space-a", title: "线性代数", status: "active", isCurrent: true }],
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
});
