// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { StudyFlashcard, StudyQuizQuestion, StudyQuizResult } from "../../chat/study/study-api";
import { I18nProvider } from "../../lib/i18n";
import type { StudyPracticeHome, StudyRepository } from "../repository";
import { StudyRepositoryProvider } from "../repositoryContext";
import { PracticePage } from "./PracticePage";

const card: StudyFlashcard = {
  item_id: "card-1", artifact_id: "deck-1", front: "Front side", back: "Back side",
};

const quiz = {
  artifact_id: "quiz-1", kind: "quiz", title: "Vectors quiz", status: "active",
};

const home: StudyPracticeHome = { cards: [card], dueCards: [card], quizzes: [quiz], drafts: [] };

const result: StudyQuizResult = {
  score: 1, maxScore: 1, percent: 100, correctCount: 1, total: 1, perQuestion: [],
};

function repository(overrides: Partial<StudyRepository> = {}): StudyRepository {
  return {
    listSpaces: vi.fn(), selectSpace: vi.fn(), listDrafts: vi.fn(),
    loadFlyleaf: vi.fn(), migrateLegacyContext: vi.fn(), setArtifactStatus: vi.fn(),
    loadPlan: vi.fn(), completePlanItem: vi.fn(), skipPlanItem: vi.fn(),
    loadWrongbook: vi.fn(), loadLatestEvaluation: vi.fn(), loadActivities: vi.fn(),
    loadPracticeHome: vi.fn().mockResolvedValue(home),
    loadQuizQuestions: vi.fn(), reviewFlashcard: vi.fn(), submitQuiz: vi.fn(),
    generatePracticeDraft: vi.fn(), resolvePracticeSource: vi.fn(),
    ...overrides,
  };
}

function renderPage(repo: StudyRepository, entry = "/study/space-b/practice") {
  render(
    <I18nProvider><StudyRepositoryProvider repository={repo}>
      <MemoryRouter initialEntries={[entry]}><PracticePage spaceId="space-b" /></MemoryRouter>
    </StudyRepositoryProvider></I18nProvider>,
  );
}

describe("PracticePage", () => {
  it("reviews a due card with focus-scoped keyboard shortcuts", async () => {
    const user = userEvent.setup();
    const reviewFlashcard = vi.fn().mockResolvedValue({ ...card, grade: "good" });
    renderPage(repository({ reviewFlashcard }));

    await user.click(await screen.findByRole("button", { name: "开始复习" }));
    const surface = screen.getByText("Front side").closest("article");
    expect(surface).not.toBeNull();
    surface!.focus();
    fireEvent.keyDown(surface!, { key: " " });
    expect(screen.getByText("Back side")).toBeInTheDocument();
    fireEvent.keyDown(surface!, { key: "3", repeat: true });
    expect(reviewFlashcard).not.toHaveBeenCalled();
    fireEvent.keyDown(surface!, { key: "3" });

    await waitFor(() => expect(reviewFlashcard).toHaveBeenCalledWith(
      "space-b", "card-1", "good", expect.any(AbortSignal),
    ));
  });

  it("submits a normal quiz only through the URL-scoped repository", async () => {
    const user = userEvent.setup();
    const questions: StudyQuizQuestion[] = [{
      item_id: "question-1", artifact_id: "quiz-1", type: "choice", prompt: "Pick one", options: ["A", "B"],
    }];
    const loadQuizQuestions = vi.fn().mockResolvedValue(questions);
    const submitQuiz = vi.fn().mockResolvedValue(result);
    renderPage(repository({ loadQuizQuestions, submitQuiz }));

    await user.click(await screen.findByRole("button", { name: "Vectors quiz" }));
    await user.click(await screen.findByRole("button", { name: "B" }));
    await user.click(screen.getByRole("button", { name: "提交并批改" }));

    await waitFor(() => expect(submitQuiz).toHaveBeenCalledWith(
      "space-b", "quiz-1", { "question-1": { selected: [1] } }, expect.any(AbortSignal),
    ));
    expect(await screen.findByRole("heading", { name: "本次结果" })).toBeInTheDocument();
  });

  it("restores a wrongbook source in the same space and focuses its first failed item", async () => {
    const questions: StudyQuizQuestion[] = [
      { item_id: "ok", artifact_id: "quiz-1", type: "short_answer", prompt: "Earlier question" },
      { item_id: "failed", artifact_id: "quiz-1", type: "short_answer", prompt: "Retry this question" },
    ];
    const resolvePracticeSource = vi.fn().mockResolvedValue({ artifact_id: "quiz-1", item_ids: ["failed"] });
    const loadQuizQuestions = vi.fn().mockResolvedValue(questions);
    renderPage(repository({ resolvePracticeSource, loadQuizQuestions }), "/study/space-b/practice?source=wrongbook&activityId=opaque-activity");

    expect(await screen.findByRole("heading", { name: "Retry this question" })).toBeInTheDocument();
    expect(resolvePracticeSource).toHaveBeenCalledWith("space-b", "opaque-activity", expect.any(AbortSignal));
    expect(loadQuizQuestions).toHaveBeenCalledWith("space-b", "quiz-1", expect.any(AbortSignal));
  });

  it("creates a reviewable transcription draft without activating it", async () => {
    const user = userEvent.setup();
    const codeQuestion: StudyQuizQuestion[] = [{
      item_id: "code-1", artifact_id: "quiz-1", type: "code", prompt: "Write a function", language: "python", starter: "def f():\n  pass",
    }];
    const generatePracticeDraft = vi.fn().mockResolvedValue({
      generated: true, artifact_id: "draft-1", status: "draft", practice_kind: "transcribe", source_item_id: "code-1",
    });
    const setArtifactStatus = vi.fn();
    renderPage(repository({
      loadQuizQuestions: vi.fn().mockResolvedValue(codeQuestion), generatePracticeDraft, setArtifactStatus,
    }));

    await user.click(await screen.findByRole("button", { name: "Vectors quiz" }));
    await user.click(await screen.findByRole("button", { name: "生成临摹" }));

    await waitFor(() => expect(generatePracticeDraft).toHaveBeenCalledWith(
      "space-b", "quiz-1", "code-1", "transcribe", expect.any(AbortSignal),
    ));
    expect(await screen.findByText(/已生成待审核练习/)).toBeInTheDocument();
    expect(setArtifactStatus).not.toHaveBeenCalled();
  });

  it("keeps an unsupported generated practice honest and offers only the chat handoff", async () => {
    const user = userEvent.setup();
    const codeQuestion: StudyQuizQuestion[] = [{
      item_id: "code-1", artifact_id: "quiz-1", type: "code", prompt: "Write a function", language: "python", starter: "pass",
    }];
    renderPage(repository({
      loadQuizQuestions: vi.fn().mockResolvedValue(codeQuestion),
      generatePracticeDraft: vi.fn().mockResolvedValue({ generated: false, source_item_id: "code-1", fallback: "model_draft_required" }),
    }));

    await user.click(await screen.findByRole("button", { name: "Vectors quiz" }));
    await user.click(await screen.findByRole("button", { name: "生成变式" }));

    expect(await screen.findByText(/暂时不能自动生成练习草稿/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "返回聊天" })).toHaveAttribute("href", "/chat");
    expect(screen.queryByText("Write a function")).not.toBeInTheDocument();
  });

  it("activates a quiz draft in the URL space, then re-reads and opens its questions", async () => {
    const user = userEvent.setup();
    const setArtifactStatus = vi.fn().mockResolvedValue(undefined);
    const loadQuizQuestions = vi.fn().mockResolvedValue([
      { item_id: "draft-question", artifact_id: "draft-quiz", type: "short_answer", prompt: "Fresh draft question" },
    ] satisfies StudyQuizQuestion[]);
    renderPage(repository({
      loadPracticeHome: vi.fn().mockResolvedValue({
        ...home,
        drafts: [{ artifact_id: "draft-quiz", kind: "quiz", title: "New practice", status: "draft" }],
      }),
      setArtifactStatus,
      loadQuizQuestions,
    }));

    await user.click(await screen.findByRole("button", { name: "落墨" }));
    expect(await screen.findByRole("heading", { name: "Fresh draft question" })).toBeInTheDocument();
    expect(setArtifactStatus).toHaveBeenCalledWith("space-b", "draft-quiz", "active", expect.any(AbortSignal));
    expect(loadQuizQuestions).toHaveBeenCalledWith("space-b", "draft-quiz", expect.any(AbortSignal));
  });

  it("keeps ready quizzes reachable when other home sections are unavailable", async () => {
    renderPage(repository({
      loadPracticeHome: vi.fn().mockResolvedValue({
        cards: [], dueCards: [], quizzes: [quiz], drafts: [], unavailable: ["cards", "drafts"],
      }),
    }));

    expect(await screen.findByRole("button", { name: "Vectors quiz" })).toBeEnabled();
    expect(screen.getAllByText("这一部分暂时无法读取，其他练习仍可继续。")).toHaveLength(2);
  });
});
