// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { StudyFlashcard, StudyQuizQuestion, StudyQuizResult } from "../../chat/study/study-api";
import { I18nProvider } from "../../lib/i18n";
import { StudyDraftProvider } from "../DraftContext";
import type { StudyPracticeHome, StudyRepository } from "../repository";
import { StudyRepositoryProvider } from "../repositoryContext";
import { PracticePage } from "./PracticePage";
import { StudyPageOutlet } from "./StudyPageOutlet";
import { StudyIaProvider } from "../StudyIaContext";
import type { StudyIaSink } from "../iaEvents";
import { onStudyNanaRequest } from "../studyNanaRequest";

const card: StudyFlashcard = {
  item_id: "card-1", artifact_id: "deck-1", front: "Front side", back: "Back side",
};

const quiz = {
  artifact_id: "quiz-1", kind: "quiz", title: "Vectors quiz", status: "active",
};

const home: StudyPracticeHome = { cards: [card], dueCards: [card], quizzes: [quiz] };

const result: StudyQuizResult = {
  score: 1, maxScore: 1, percent: 100, correctCount: 1, total: 1, perQuestion: [],
};

function repository(overrides: Partial<StudyRepository> = {}): StudyRepository {
  return {
    seedBuiltinCourse: vi.fn().mockResolvedValue(false),
    migrateLegacyCollections: vi.fn().mockResolvedValue({
      changed: false, retryNeeded: false, flashcards: "absent", quizzes: "absent",
    }),
    listSpaces: vi.fn(), selectSpace: vi.fn(), listDrafts: vi.fn(),
    listDraftPage: vi.fn().mockResolvedValue({ items: [], total: 0, kindCounts: {}, returned: 0, limit: 50, offset: 0, truncated: false }),
    loadLearnHome: vi.fn().mockResolvedValue({ artifacts: [], knowledgePoints: [] }),
    loadArtifactDetail: vi.fn(), loadSourceAudit: vi.fn(), runSemanticReview: vi.fn(),
    loadFlyleaf: vi.fn(), saveFlyleaf: vi.fn(), migrateLegacyContext: vi.fn(), setArtifactStatus: vi.fn(),
    loadPlan: vi.fn(), completePlanItem: vi.fn(), skipPlanItem: vi.fn(),
    loadWrongbook: vi.fn(), loadLatestEvaluation: vi.fn(), loadActivities: vi.fn(),
    loadScratch: vi.fn(), saveScratchPad: vi.fn(), fileScratchNote: vi.fn(),
    loadPracticeHome: vi.fn().mockResolvedValue(home),
    loadQuizQuestions: vi.fn(), reviewFlashcard: vi.fn(), submitQuiz: vi.fn(),
    generatePracticeDraft: vi.fn(), resolvePracticeSource: vi.fn(),
    ...overrides,
  };
}

function renderPage(repo: StudyRepository, entry = "/study/space-b/practice", props: { onDirtyChange?: (dirty: boolean) => void; onNavigateAway?: (to: string) => void } = {}, sink: StudyIaSink = vi.fn()) {
  render(
    <I18nProvider><StudyRepositoryProvider repository={repo}>
      <StudyIaProvider sink={sink}><MemoryRouter initialEntries={[entry]}><StudyDraftProvider spaceId="space-b"><PracticePage spaceId="space-b" {...props} /></StudyDraftProvider></MemoryRouter></StudyIaProvider>
    </StudyRepositoryProvider></I18nProvider>,
  );
}

describe("PracticePage", () => {
  it("does not borrow general exercises when there is no current knowledge core", async () => {
    renderPage(repository({
      loadPracticeHome: vi.fn().mockResolvedValue({
        ...home,
        learningMap: {
          revision: 1,
          outlineStatus: "ready",
          outlineNodes: [],
          knowledgeCores: [],
          exerciseLinks: [],
        },
        location: null,
      }),
    }));

    expect(await screen.findByRole("heading", { name: "先选择要练习的知识核" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Vectors quiz" })).not.toBeInTheDocument();
  });

  it("uses a constrained prepare-practice action for the current core", async () => {
    const user = userEvent.setup();
    const nanaRequest = vi.fn();
    const stopListening = onStudyNanaRequest(nanaRequest);
    renderPage(repository({
      loadPracticeHome: vi.fn().mockResolvedValue({
        ...home,
        learningMap: {
          revision: 1,
          outlineStatus: "ready",
          outlineNodes: [],
          knowledgeCores: [{
            id: "core-1",
            itemId: "card-1",
            artifactId: "deck-1",
            front: "向量定义",
            gist: "大小与方向",
            captured: true,
            outlineNodeId: "section-vector",
            order: 0,
          }],
          exerciseLinks: [],
        },
        location: {
          revision: 1,
          mapRevision: 1,
          page: "practice",
          knowledgeCoreId: "core-1",
          outlineNodeId: "section-vector",
          planItemId: null,
          planOutlineNodeId: "section-vector",
          exerciseId: null,
          exerciseByCore: {},
          stale: false,
          updatedAt: "2026-07-31T00:00:00Z",
        },
      }),
    }));

    await user.click(await screen.findByRole("button", { name: "准备练习" }));
    expect(nanaRequest).toHaveBeenCalledWith(expect.objectContaining({
      page: "practice",
      knowledgeCoreId: "core-1",
      focusLabel: "向量定义",
    }));
    stopListening();
  });

  it("opens only the exercise linked to the shared current knowledge core", async () => {
    const linkedQuestion: StudyQuizQuestion = {
      item_id: "question-core-2",
      artifact_id: "quiz-1",
      type: "short_answer",
      prompt: "Explain the current core",
    };
    const loadQuizQuestions = vi.fn().mockResolvedValue([
      { ...linkedQuestion, item_id: "question-other", prompt: "Unrelated question" },
      linkedQuestion,
    ]);
    renderPage(repository({
      loadPracticeHome: vi.fn().mockResolvedValue({
        ...home,
        learningMap: {
          revision: 3,
          outlineStatus: "ready",
          outlineNodes: [],
          knowledgeCores: [{
            id: "core-2", itemId: "card-2", artifactId: "deck-1",
            front: "Current core", gist: "One idea", captured: true,
            outlineNodeId: "section-2", order: 0,
          }],
          exerciseLinks: [{
            knowledgeCoreId: "core-2", quizArtifactId: "quiz-1",
            exerciseId: "question-core-2", origin: "source", sourceRefs: [], order: 0,
          }],
        },
        location: {
          revision: 1, mapRevision: 3, page: "practice",
          knowledgeCoreId: "core-2", outlineNodeId: "section-2",
          planItemId: "plan-item-2", planOutlineNodeId: "section-2",
          exerciseId: null, exerciseByCore: {}, stale: false,
          updatedAt: "2026-07-31T00:00:00Z",
        },
      }),
      loadQuizQuestions,
    }));

    expect(await screen.findByRole("heading", { name: "Explain the current core" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Unrelated question" })).not.toBeInTheDocument();
    expect(loadQuizQuestions).toHaveBeenCalledWith("space-b", "quiz-1", expect.any(AbortSignal));
  });

  it("reviews a due card with focus-scoped keyboard shortcuts", async () => {
    const user = userEvent.setup();
    const sink = vi.fn();
    const reviewFlashcard = vi.fn().mockResolvedValue({ ...card, grade: "good" });
    renderPage(repository({ reviewFlashcard }), "/study/space-b/practice", {}, sink);

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
    expect(sink).toHaveBeenCalledWith({
      name: "study.review.start", page: "practice", action: "start", count_bucket: "one",
    });
    expect(sink).toHaveBeenCalledWith({
      name: "study.review.complete", page: "practice", action: "complete", count_bucket: "one",
    });
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
      listDraftPage: vi.fn().mockResolvedValue({
        items: [{ artifact_id: "draft-quiz", kind: "quiz", title: "New practice", status: "draft" }],
        total: 1, kindCounts: { quiz: 1 }, returned: 1, limit: 50, offset: 0, truncated: false,
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
        cards: [], dueCards: [], quizzes: [quiz], unavailable: ["cards"],
      }),
    }));

    expect(await screen.findByRole("button", { name: "Vectors quiz" })).toBeEnabled();
    expect(screen.getAllByText("这一部分暂时无法读取，其他练习仍可继续。")).toHaveLength(1);
  });

  it("shows a retryable page error when every home section is unavailable", async () => {
    const user = userEvent.setup();
    const loadPracticeHome = vi.fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(home);
    renderPage(repository({ loadPracticeHome }));

    expect(await screen.findByRole("alert")).toHaveTextContent("这一页暂时无法读取");
    await user.click(screen.getByRole("button", { name: "重试" }));
    expect(await screen.findByRole("button", { name: "Vectors quiz" })).toBeEnabled();
    expect(loadPracticeHome).toHaveBeenCalledTimes(2);
  });

  it("marks answers dirty until submission and protects window unload", async () => {
    const user = userEvent.setup();
    const onDirtyChange = vi.fn();
    renderPage(repository({
      loadQuizQuestions: vi.fn().mockResolvedValue([{
        item_id: "question-1", artifact_id: "quiz-1", type: "choice", prompt: "Pick one", options: ["A", "B"],
      }] satisfies StudyQuizQuestion[]),
      submitQuiz: vi.fn().mockResolvedValue(result),
    }), "/study/space-b/practice", { onDirtyChange });

    await user.click(await screen.findByRole("button", { name: "Vectors quiz" }));
    await user.click(await screen.findByRole("button", { name: "B" }));
    await waitFor(() => expect(onDirtyChange).toHaveBeenLastCalledWith(true));
    const blocked = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(blocked);
    expect(blocked.defaultPrevented).toBe(true);

    await user.click(screen.getByRole("button", { name: "提交并批改" }));
    await screen.findByRole("heading", { name: "本次结果" });
    await waitFor(() => expect(onDirtyChange).toHaveBeenLastCalledWith(false));
    const allowed = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(allowed);
    expect(allowed.defaultPrevented).toBe(false);
  });

  it("remounts the practice controller when the URL space changes", async () => {
    const user = userEvent.setup();
    const loadPracticeHome = vi.fn().mockImplementation(async (spaceId: string) => ({
      cards: [], dueCards: [], quizzes: [{
        artifact_id: `quiz-${spaceId}`, kind: "quiz", title: `Quiz ${spaceId}`, status: "active",
      }],
    }));
    const loadQuizQuestions = vi.fn().mockImplementation(async (_spaceId: string, artifactId: string) => [{
      item_id: `item-${artifactId}`, artifact_id: artifactId, type: "short_answer", prompt: `Question ${artifactId}`,
    }]);
    const repo = repository({ loadPracticeHome, loadQuizQuestions });
    const tree = (spaceId: string) => <I18nProvider><StudyRepositoryProvider repository={repo}>
      <MemoryRouter><StudyDraftProvider spaceId={spaceId}><StudyPageOutlet spaceId={spaceId} page="practice" /></StudyDraftProvider></MemoryRouter>
    </StudyRepositoryProvider></I18nProvider>;
    const view = render(tree("space-a"));

    await user.click(await screen.findByRole("button", { name: "Quiz space-a" }));
    expect(await screen.findByRole("heading", { name: "Question quiz-space-a" })).toBeInTheDocument();
    view.rerender(tree("space-b"));

    expect(await screen.findByRole("button", { name: "Quiz space-b" })).toBeInTheDocument();
    expect(screen.queryByText("Question quiz-space-a")).not.toBeInTheDocument();
    expect(loadPracticeHome).toHaveBeenCalledWith("space-b", expect.any(AbortSignal));
  });
});
