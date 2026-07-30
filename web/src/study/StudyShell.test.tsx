// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StrictMode, useState } from "react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../lib/i18n";
import { answerConfirm, getConfirmSnapshot } from "../lib/confirmDialog";
import { readPendingStudyHandoff } from "../lib/studyChatHandoff";
import type { StudyRepository } from "./repository";
import { StudyRepositoryProvider } from "./repositoryContext";
import { StudyShell } from "./StudyShell";
import { StudyIaProvider } from "./StudyIaContext";
import type { StudyIaSink } from "./iaEvents";
import { readStudyLocation } from "./studyLocation";

const spaces = {
  currentSpaceId: "space-a",
  spaces: [
    { id: "space-a", title: "Linear Algebra", status: "active", isCurrent: true, kind: "course" as const },
    { id: "space-b", title: "Physics", status: "active", isCurrent: false, kind: "course" as const },
  ],
};

const vectorCore = {
  item_id: "core-vectors",
  artifact_id: "knowledge-vectors",
  front: "vectors",
  gist: "A vector has direction and magnitude.",
  captured: true as const,
};

function Location() {
  const location = useLocation();
  return (
    <>
      <output data-testid="location">{location.pathname}</output>
      <output data-testid="location-state">{JSON.stringify(location.state)}</output>
    </>
  );
}

function makeRepository(repositoryOverrides: Partial<StudyRepository> = {}): StudyRepository {
  return {
    seedBuiltinCourse: vi.fn().mockResolvedValue(false),
    migrateLegacyCollections: vi.fn().mockResolvedValue({
      changed: false, retryNeeded: false, flashcards: "absent", quizzes: "absent",
    }),
    listSpaces: vi.fn().mockResolvedValue(spaces),
    selectSpace: vi.fn().mockResolvedValue({ ...spaces, currentSpaceId: "space-b" }),
    listDrafts: vi.fn().mockResolvedValue({
      total: 2,
      kindCounts: { flashcard_deck: 1, quiz: 1 },
    }),
    listDraftPage: vi.fn().mockResolvedValue({
      items: [
        { artifact_id: "draft-deck", kind: "flashcard_deck", title: "Deck draft", status: "draft" },
        { artifact_id: "draft-quiz", kind: "quiz", title: "Quiz draft", status: "draft" },
      ], total: 2, kindCounts: { flashcard_deck: 1, quiz: 1 }, returned: 2, limit: 50, offset: 0, truncated: false,
    }),
    loadLearnHome: vi.fn().mockResolvedValue({ artifacts: [], knowledgePoints: [vectorCore] }),
    loadArtifactDetail: vi.fn(), loadSourceAudit: vi.fn(), runSemanticReview: vi.fn(),
    loadFlyleaf: vi.fn(), saveFlyleaf: vi.fn(),
    migrateLegacyContext: vi.fn(),
    setArtifactStatus: vi.fn(),
    loadPlan: vi.fn(),
    completePlanItem: vi.fn(),
    skipPlanItem: vi.fn(),
    loadWrongbook: vi.fn(),
    loadLatestEvaluation: vi.fn(),
    loadActivities: vi.fn(),
    loadScratch: vi.fn(), saveScratchPad: vi.fn(), fileScratchNote: vi.fn(),
    loadPracticeHome: vi.fn(), loadQuizQuestions: vi.fn(), reviewFlashcard: vi.fn(),
    submitQuiz: vi.fn(), generatePracticeDraft: vi.fn(), resolvePracticeSource: vi.fn(),
    ...repositoryOverrides,
  };
}

function renderShell(
  repositoryOverrides: Partial<StudyRepository> = {},
  { spaceId = "space-a", page = "learn" }: {
    spaceId?: string;
    page?: "flyleaf" | "plan" | "learn" | "practice" | "evaluate";
  } = {},
  sink: StudyIaSink = vi.fn(),
  strict = false,
) {
  const repository = makeRepository(repositoryOverrides);
  const tree = (
    <I18nProvider>
      <StudyRepositoryProvider repository={repository}>
        <StudyIaProvider sink={sink}>
          <MemoryRouter initialEntries={[`/study/${spaceId}/${page}`]}>
            <Location />
            <StudyShell spaces={spaces} spaceId={spaceId} page={page} />
          </MemoryRouter>
        </StudyIaProvider>
      </StudyRepositoryProvider>
    </I18nProvider>
  );
  render(strict ? <StrictMode>{tree}</StrictMode> : tree);
  return repository;
}

beforeEach(() => localStorage.clear());

afterEach(() => {
  if (getConfirmSnapshot()) answerConfirm(false);
  vi.unstubAllGlobals();
});

describe("StudyShell", () => {
  it("records one content-free page view for the routed lifecycle page", async () => {
    const sink = vi.fn();
    renderShell({}, { page: "learn" }, sink, true);
    await waitFor(() => expect(sink).toHaveBeenCalledWith({ name: "study.page.view", page: "learn", action: "view" }));
    expect(sink).toHaveBeenCalledTimes(1);
  });

  it("puts every lifecycle page in one notebook, with the course books on its edge", async () => {
    renderShell();
    // 五个分页共用同一本本子：翻页不换世界。
    const tabs = await screen.findByRole("navigation", { name: "笔记本分页" });
    expect(tabs).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "学习" })).toHaveAttribute("aria-current", "page");
    // 换课＝换一本本子：课程名长在书立的标签上，不在一个下拉里。
    const bookend = screen.getByRole("navigation", { name: /课程/ });
    expect(bookend.querySelector('[aria-current="page"]')).toHaveTextContent("Linear Algebra");
    expect(bookend).toHaveTextContent("Physics");
  });

  it("keeps the drafts inbox reachable and privacy-bounded after the IA move", async () => {
    const user = userEvent.setup();
    renderShell();
    const drafts = await screen.findByLabelText("2 个草稿");
    await user.click(drafts.closest("button")!);
    const popover = screen.getByRole("dialog", { name: "草稿箱" });
    expect(popover).toHaveTextContent("Deck draft");
    expect(popover).toHaveTextContent("Quiz draft");
    expect(popover).not.toHaveTextContent("private");
  });

  it("adopts a practice draft and enters its exact knowledge core and question", async () => {
    const user = userEvent.setup();
    const draft = {
      artifact_id: "draft-vector-quiz",
      kind: "quiz",
      title: "向量补充练习",
      status: "draft",
      review: { mode: "semantic", status: "pending" },
    };
    const loadQuizQuestions = vi.fn().mockResolvedValue([{
      item_id: "draft-vector-quiz-0000",
      artifact_id: "draft-vector-quiz",
      type: "short_answer",
      prompt: "为什么向量既有大小又有方向？",
      knowledge_core_id: "core-vectors",
      origin: "generated",
    }]);
    const setArtifactStatus = vi.fn().mockResolvedValue(undefined);
    const repository = makeRepository({
      listDraftPage: vi.fn().mockResolvedValue({
        items: [draft], total: 1, kindCounts: { quiz: 1 }, returned: 1, limit: 50, offset: 0, truncated: false,
      }),
      loadArtifactDetail: vi.fn().mockResolvedValue({
        artifactId: "draft-vector-quiz",
        kind: "quiz",
        title: "向量补充练习",
        version: 1,
        status: "draft",
        review: { mode: "semantic", status: "pending" },
        envelope: {
          payload: {
            questions: [{
              type: "short_answer",
              prompt: "为什么向量既有大小又有方向？",
              answer: "PRIVATE ANSWER",
              knowledge_core_id: "core-vectors",
              origin: "generated",
            }],
          },
        },
      }),
      setArtifactStatus,
      loadQuizQuestions,
      loadLearnHome: vi.fn().mockResolvedValue({ artifacts: [], knowledgePoints: [vectorCore] }),
    });
    function RoutedStudyShell() {
      const location = useLocation();
      const page = location.pathname.split("/").at(-1) as "learn" | "practice";
      return (
        <>
          <Location />
          <StudyShell spaces={spaces} spaceId="space-a" page={page} />
        </>
      );
    }
    render(
      <I18nProvider>
        <StudyRepositoryProvider repository={repository}>
          <StudyIaProvider sink={vi.fn()}>
            <MemoryRouter initialEntries={["/study/space-a/learn"]}>
              <RoutedStudyShell />
            </MemoryRouter>
          </StudyIaProvider>
        </StudyRepositoryProvider>
      </I18nProvider>,
    );

    await user.click((await screen.findByLabelText("1 个草稿")).closest("button")!);
    await user.click(screen.getByRole("button", { name: /向量补充练习/ }));
    await user.click(await screen.findByRole("button", { name: "采用并开始" }));

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/study/space-a/practice"));
    expect(setArtifactStatus).toHaveBeenCalledWith(
      "space-a", "draft-vector-quiz", "active", expect.any(AbortSignal),
    );
    expect(loadQuizQuestions).toHaveBeenCalledWith(
      "space-a", "draft-vector-quiz", expect.any(AbortSignal),
    );
    await waitFor(() => expect(readStudyLocation("space-a")).toMatchObject({
        page: "practice",
        knowledgeCoreId: "core-vectors",
        exerciseId: "draft-vector-quiz-0000",
        exerciseByCore: { "core-vectors": "draft-vector-quiz-0000" },
      }));
  });

  it("uses the URL space for drafts when it differs from the backend current space", async () => {
    const listDraftPage = vi.fn().mockResolvedValue({
      items: [{ artifact_id: "draft-quiz", kind: "quiz", title: "Quiz draft", status: "draft" }],
      total: 1, kindCounts: { quiz: 1 }, returned: 1, limit: 50, offset: 0, truncated: false,
    });
    renderShell({ listDraftPage }, { spaceId: "space-b" });

    await screen.findByLabelText("1 个草稿");
    expect(listDraftPage).toHaveBeenCalledWith("space-b", 50, 0, expect.any(AbortSignal));
  });

  it("remounts the provider subtree before rendering a different URL space", async () => {
    const user = userEvent.setup();
    const repository = makeRepository({
      listDraftPage: vi.fn().mockResolvedValue({ items: [], total: 0, kindCounts: {}, returned: 0, limit: 50, offset: 0, truncated: false }),
      loadLearnHome: vi.fn().mockImplementation((spaceId: string) => spaceId === "space-a"
        ? Promise.resolve({ artifacts: [], knowledgePoints: [{ ...vectorCore, item_id: "core-a", front: "A TERM", gist: "A PRIVATE BODY" }] })
        : new Promise(() => undefined)),
      loadArtifactDetail: vi.fn().mockResolvedValue({ artifactId: "artifact-a", kind: "knowledge_base", title: "A knowledge", version: 1, status: "active", review: {}, envelope: { payload: { concepts: [{ term: "A TERM", explanation: "A PRIVATE BODY" }] } } }),
    });
    function Harness() {
      const [spaceId, setSpaceId] = useState("space-a");
      return <MemoryRouter><button type="button" onClick={() => setSpaceId("space-b")}>test switch</button><StudyRepositoryProvider repository={repository}><StudyShell spaces={spaces} spaceId={spaceId} page="learn" /></StudyRepositoryProvider></MemoryRouter>;
    }
    render(<I18nProvider><Harness /></I18nProvider>);

    expect(await screen.findByText("A PRIVATE BODY")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "test switch" }));
    expect(screen.queryByText("A PRIVATE BODY")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "学习" })).toBeInTheDocument();
  });

  it("ignores a late response from the course that was just closed", async () => {
    const user = userEvent.setup();
    let resolveOldCourse!: (value: { artifacts: never[]; knowledgePoints: Array<typeof vectorCore> }) => void;
    const oldCourse = new Promise<{ artifacts: never[]; knowledgePoints: Array<typeof vectorCore> }>((resolve) => {
      resolveOldCourse = resolve;
    });
    const repository = makeRepository({
      listDraftPage: vi.fn().mockResolvedValue({ items: [], total: 0, kindCounts: {}, returned: 0, limit: 50, offset: 0, truncated: false }),
      loadLearnHome: vi.fn().mockImplementation((spaceId: string) => spaceId === "space-a"
        ? oldCourse
        : Promise.resolve({
          artifacts: [],
          knowledgePoints: [{ ...vectorCore, item_id: "core-b", front: "B TERM", gist: "B COURSE BODY" }],
        })),
    });
    function Harness() {
      const [spaceId, setSpaceId] = useState("space-a");
      return (
        <MemoryRouter>
          <button type="button" onClick={() => setSpaceId("space-b")}>close course A</button>
          <StudyRepositoryProvider repository={repository}>
            <StudyShell spaces={spaces} spaceId={spaceId} page="learn" />
          </StudyRepositoryProvider>
        </MemoryRouter>
      );
    }
    render(<I18nProvider><Harness /></I18nProvider>);

    await waitFor(() => expect(repository.loadLearnHome).toHaveBeenCalledWith("space-a", expect.any(AbortSignal)));
    await user.click(screen.getByRole("button", { name: "close course A" }));
    expect(await screen.findByText("B COURSE BODY")).toBeInTheDocument();

    await act(async () => resolveOldCourse({
      artifacts: [],
      knowledgePoints: [{ ...vectorCore, item_id: "core-a", front: "A TERM", gist: "A COURSE BODY" }],
    }));
    expect(screen.queryByText("A COURSE BODY")).not.toBeInTheDocument();
    expect(screen.getByText("B COURSE BODY")).toBeInTheDocument();
  });

  it("keeps route and data when selecting a space fails", async () => {
    const user = userEvent.setup();
    const sink = vi.fn();
    renderShell({ selectSpace: vi.fn().mockRejectedValue(new Error("request_failed")) }, {}, sink);
    await user.click(await screen.findByRole("button", { name: /Physics/ }));
    // 换课失败：路由与当前这本都不动。
    await waitFor(() => expect(sink).toHaveBeenCalledWith({ name: "study.space.switch", action: "switch", success: false }));
    expect(screen.getByTestId("location")).toHaveTextContent("/study/space-a/learn");
    expect(screen.getByRole("region", { name: "学习" })).toBeInTheDocument();
  });

  it("moves to the selected space while preserving the current lifecycle page", async () => {
    const user = userEvent.setup();
    const sink = vi.fn();
    const repository = renderShell({}, {}, sink);
    await user.click(await screen.findByRole("button", { name: /Physics/ }));
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/study/space-b/learn"));
    expect(repository.selectSpace).toHaveBeenCalledWith("space-b", expect.any(AbortSignal));
    expect(sink).toHaveBeenCalledWith({ name: "study.space.switch", action: "switch", success: true });
  });

  /**
   * 杂记本不是课程：它不站在课程那一排里，也不该出现在任何“选一门课”的地方。
   * 这条钉住的是分组，不是样式。
   */
  it("keeps the scratch book out of the course group", async () => {
    const user = userEvent.setup();
    const withScratch = {
      currentSpaceId: "space-a",
      spaces: [
        ...spaces.spaces,
        { id: "scratch-1", title: "杂记本", status: "active", isCurrent: false, kind: "scratch" as const },
      ],
    };
    const repository = makeRepository();
    render(
      <I18nProvider>
        <StudyRepositoryProvider repository={repository}>
          <MemoryRouter initialEntries={["/study/space-a/learn"]}>
            <StudyShell spaces={withScratch} spaceId="space-a" page="learn" />
          </MemoryRouter>
        </StudyRepositoryProvider>
      </I18nProvider>,
    );
    const bookend = await screen.findByRole("navigation", { name: /课程/ });
    const pills = [...bookend.querySelectorAll("button")].map((b) => b.textContent?.trim());
    // 顺序：课程们 → 开新本 → （推到最右的）杂记本。
    expect(pills).toEqual(["Linear Algebra", "Physics", "开新本", "杂记本"]);
    expect(bookend.querySelector(".kd-book-pill--scratch")).toHaveTextContent("杂记本");
    await user.click(screen.getByRole("button", { name: "杂记本" }));
    // 打开留白不等于切换当前课程；currentSpaceId 仍由最后一本课程拥有。
    expect(repository.selectSpace).not.toHaveBeenCalled();
  });

  it("switches course books straight from the bookend, with the current one inert", async () => {
    const user = userEvent.setup();
    const repository = renderShell();
    const bookend = await screen.findByRole("navigation", { name: /课程/ });
    const current = screen.getByRole("button", { name: /Linear Algebra/ });
    // 当前这本与纸面连成一体，点它不该再发一次切换请求。
    expect(current).toHaveAttribute("aria-current", "page");
    await user.click(current);
    expect(repository.selectSpace).not.toHaveBeenCalled();
    // 「开新本」跟课程标签在同一条边上。
    expect(bookend).toHaveTextContent("开新本");
  });

  it("requires confirmation before a dirty practice changes space or lifecycle page", async () => {
    const user = userEvent.setup();
    const repository = renderShell({
      loadPracticeHome: vi.fn().mockResolvedValue({
        cards: [], dueCards: [], quizzes: [{
          artifact_id: "quiz-1", kind: "quiz", title: "Vectors quiz", status: "active",
        }],
      }),
      loadQuizQuestions: vi.fn().mockResolvedValue([{
        item_id: "question-1", artifact_id: "quiz-1", type: "choice", prompt: "Pick one", options: ["A", "B"], tags: ["vectors"],
      }]),
    }, { page: "practice" });
    await user.click(await screen.findByRole("button", { name: /继续这一步/ }));
    await user.click(screen.getByRole("button", { name: "开始作答" }));
    await user.click(await screen.findByRole("button", { name: "B" }));

    await user.click(screen.getByRole("button", { name: /Physics/ }));
    expect(getConfirmSnapshot()?.title).toBe("离开当前练习？");
    await act(async () => answerConfirm(false));
    expect(repository.selectSpace).not.toHaveBeenCalled();
    expect(screen.getByTestId("location")).toHaveTextContent("/study/space-a/practice");

    await user.click(screen.getByRole("button", { name: "评估" }));
    expect(getConfirmSnapshot()?.message).toContain("尚未完成的答案");
    await act(async () => answerConfirm(true));
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/study/space-a/evaluate"));
  });

  it("opens a reviewed course Chat handoff instead of a bare route jump", async () => {
    renderShell({
      loadPracticeHome: vi.fn().mockResolvedValue({
        cards: [],
        dueCards: [],
        quizzes: [{
          artifact_id: "quiz-1", kind: "quiz", title: "Vectors quiz", status: "active",
        }],
      }),
      loadQuizQuestions: vi.fn().mockResolvedValue([{
        item_id: "question-1",
        artifact_id: "quiz-1",
        type: "short_answer",
        prompt: "Explain the vector length",
        tags: ["vectors"],
      }]),
    }, { page: "practice" });

    fireEvent.click(await screen.findByRole("button", { name: "碰杯问小娜" }));
    expect(await screen.findByRole("heading", { name: "问小娜" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("发送消息"), {
      target: { value: "先提示我应该检查哪个定义。" },
    });
    fireEvent.click(screen.getByRole("button", { name: "在完整 Chat 中打开" }));

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/chat"));
    const locationState = JSON.parse(screen.getByTestId("location-state").textContent || "{}");
    expect(locationState.studyHandoff).toMatchObject({
      version: 2,
      spaceId: "space-a",
      spaceTitle: "Linear Algebra",
      focusId: "question-1",
      focusKind: "practice",
      returnTarget: { path: "/study/space-a/practice", focus: "answer" },
      nanaContext: {
        origin: { page: "practice", knowledgeCoreId: "core-vectors", exerciseId: "question-1" },
        pageContext: {
          kind: "practice",
          knowledgeCore: { id: "core-vectors", title: "vectors" },
          exercise: { id: "question-1", prompt: "Explain the vector length" },
        },
      },
    });
    expect(locationState.draftPrompt).toBe("先提示我应该检查哪个定义。");
    expect(readPendingStudyHandoff()).toMatchObject({
      spaceId: "space-a",
      focusId: "question-1",
    });
  });
});
