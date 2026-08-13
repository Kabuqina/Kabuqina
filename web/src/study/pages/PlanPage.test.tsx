// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../../lib/i18n";
import type { KnowledgeCoreCompilationRun, StudyPlanItem } from "../../chat/study/study-api";
import type { StudyRepository } from "../repository";
import { StudyRepositoryProvider } from "../repositoryContext";
import { PlanPage } from "./PlanPage";
import { StudyIaProvider } from "../StudyIaContext";
import { StudyDraftProvider } from "../DraftContext";
import type { StudyIaSink } from "../iaEvents";
import { onStudyNanaRequest } from "../studyNanaRequest";
import { onStudyDraftRequest } from "../studyDraftRequest";

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
    loadPlan: vi.fn().mockResolvedValue({ plan: null, items: [] }),
    completePlanItem: vi.fn(), skipPlanItem: vi.fn(), loadWrongbook: vi.fn(),
    loadLatestEvaluation: vi.fn(), loadActivities: vi.fn(),
    loadScratch: vi.fn(), saveScratchPad: vi.fn(), fileScratchNote: vi.fn(),
    loadPracticeHome: vi.fn(), loadQuizQuestions: vi.fn(), reviewFlashcard: vi.fn(),
    submitQuiz: vi.fn(), generatePracticeDraft: vi.fn(), resolvePracticeSource: vi.fn(),
    ...overrides,
  };
}

function LocationProbe() {
  return <output aria-label="current route">{useLocation().pathname}</output>;
}

function renderPage(repo: StudyRepository, sink: StudyIaSink = vi.fn()) {
  render(
    <I18nProvider><StudyRepositoryProvider repository={repo}>
      <StudyIaProvider sink={sink}><MemoryRouter><StudyDraftProvider spaceId="space-b"><PlanPage spaceId="space-b" /><LocationProbe /></StudyDraftProvider></MemoryRouter></StudyIaProvider>
    </StudyRepositoryProvider></I18nProvider>,
  );
}

function item(overrides: Partial<StudyPlanItem>): StudyPlanItem {
  return {
    item_id: "item-1", artifact_id: "plan-1", phaseIndex: 0, phaseTitle: "Phase one",
    taskIndex: 0, title: "Read", order: 1, done_when: "Explain it", status: "open",
    outlineNodeId: "section-vector",
    completedAt: "", skippedAt: "", note: "", createdAt: "2026-07-11T00:00:00Z",
    ...overrides,
  };
}

const plan = {
  artifact_id: "plan-1", kind: "learning_plan", title: "Physics plan", status: "active",
  updated_at: "2026-07-11T00:00:00Z",
};

const emptyMap = {
  revision: 3,
  outlineStatus: "ready" as const,
  outlineNodes: [],
  knowledgeCores: [],
  exerciseLinks: [],
};

function compilation(
  overrides: Partial<KnowledgeCoreCompilationRun> = {},
): KnowledgeCoreCompilationRun {
  return {
    runId: "run-1",
    spaceId: "space-b",
    outlineNodeId: "section-vector",
    planItemId: "vector",
    trigger: "start_learning",
    status: "queued",
    sourceFingerprint: "source-1",
    policyVersion: "v1",
    draftArtifactId: null,
    reasonCode: null,
    sourceWindows: [],
    createdAt: "2026-07-31T00:00:00Z",
    updatedAt: "2026-07-31T00:00:00Z",
    ...overrides,
  };
}

describe("PlanPage", () => {
  it("keeps plan actions inside the source directory without a separate current-plan summary", async () => {
    renderPage(repository({
      loadPlan: vi.fn().mockResolvedValue({
        plan,
        items: [
          item({ item_id: "done", title: "已学内容", status: "completed" }),
          item({ item_id: "next", title: "理解向量", order: 2, outlineNodeId: "section-vector" }),
          item({ item_id: "skipped", title: "暂不学习", order: 3, status: "skipped" }),
        ],
        outline: [{ id: "section-vector", title: "向量", level: 2, children: [] }],
      }),
    }));

    expect(await screen.findByRole("heading", { name: "计划安排" })).toBeInTheDocument();
    expect(screen.queryByText("当前计划")).not.toBeInTheDocument();
    expect(screen.queryByText("Physics plan")).not.toBeInTheDocument();
    const nextItem = screen.getByRole("heading", { name: "理解向量" }).closest("li");
    expect(nextItem).not.toBeNull();
    expect(within(nextItem as HTMLElement).getByRole("button", { name: "开始学习" })).toBeEnabled();
    expect(screen.queryByRole("progressbar", { name: "计划完成进度" })).not.toBeInTheDocument();
  });

  it("puts a start action directly on every open directory item", async () => {
    renderPage(repository({
      loadPlan: vi.fn().mockResolvedValue({
        plan,
        items: [
          item({ item_id: "first", title: "第一项", outlineNodeId: "section-vector" }),
          item({ item_id: "later", title: "稍后学习", order: 2, outlineNodeId: "section-vector" }),
        ],
        outline: [{ id: "section-vector", title: "向量", level: 2, children: [] }],
      }),
    }));

    const laterItem = (await screen.findByRole("heading", { name: "稍后学习" })).closest("li");
    expect(laterItem).not.toBeNull();
    expect(within(laterItem as HTMLElement).getByRole("button", { name: "开始学习" })).toBeEnabled();
    expect(screen.getByRole("status", { name: "current route" })).toHaveTextContent("/");
  });

  it("starts an open action at the current knowledge core and creates the continue bookmark", async () => {
    const user = userEvent.setup();
    localStorage.clear();
    renderPage(repository({
      loadLearnHome: vi.fn().mockResolvedValue({
        artifacts: [],
        knowledgePoints: [{
          item_id: "core-1", artifact_id: "deck-1", front: "向量定义", gist: "大小与方向", captured: true,
        }],
        learningMap: {
          revision: 1,
          outlineStatus: "ready",
          outlineNodes: [],
          knowledgeCores: [{
            id: "core-1", itemId: "card-1", artifactId: "deck-1", front: "向量定义",
            gist: "大小与方向", captured: true, outlineNodeId: "section-vector", order: 0,
          }],
          exerciseLinks: [],
        },
      }),
      loadPlan: vi.fn().mockResolvedValue({
      plan,
      items: [
        item({ item_id: "done", title: "Done", status: "completed" }),
        item({ item_id: "next", title: "Next task", taskIndex: 1, order: 2, outlineNodeId: "section-vector" }),
      ],
      outline: [{ id: "section-vector", title: "向量", level: 2, children: [] }],
      }),
    }));

    await screen.findByRole("heading", { name: "Next task" });
    await user.click(screen.getByRole("button", { name: "开始学习" }));
    await waitFor(() => {
      expect(localStorage.getItem("kabuqina.study.location.v1:space-b")).toContain('"planItemId":"next"');
      expect(screen.getByRole("status", { name: "current route" })).toHaveTextContent("/study/space-b/learn");
    });
  });

  it("shows the server-owned current action instead of treating the first open item as progress", async () => {
    renderPage(repository({
      loadPlan: vi.fn().mockResolvedValue({
        plan,
        items: [
          item({ item_id: "first", title: "First open task" }),
          item({ item_id: "active", title: "Actual current task", taskIndex: 1, order: 2 }),
        ],
        location: {
          revision: 2, mapRevision: 1, page: "learn", knowledgeCoreId: "core-1",
          outlineNodeId: "section-vector", planItemId: "active", exerciseId: null,
          planOutlineNodeId: "section-vector", exerciseByCore: {}, stale: false,
          updatedAt: "2026-07-31T00:00:00Z",
        },
      }),
    }));

    const action = (await screen.findByRole("heading", { name: "Actual current task" })).closest("li")!;
    expect(action).toHaveTextContent("正在进行");
    expect(screen.queryByText("材料来源目录尚未整理完成时，只显示已确认的行动阶段；不会把行动名称伪装成教材目录。")).not.toBeInTheDocument();
    expect(screen.queryByText("下一行动")).not.toBeInTheDocument();
    expect(document.querySelector(".kq-study-plan-summary")).toBeNull();
  });

  it("enters the learning page without requiring the plan page to inspect knowledge cores", async () => {
    const user = userEvent.setup();
    renderPage(repository({
      loadLearnHome: vi.fn().mockResolvedValue({
        artifacts: [],
        knowledgePoints: [{
          item_id: "core-other", artifact_id: "deck-1", front: "矩阵", gist: "线性变换", captured: true,
        }],
        learningMap: {
          revision: 1,
          outlineStatus: "ready",
          outlineNodes: [],
          knowledgeCores: [{
            id: "core-other", itemId: "card-other", artifactId: "deck-1", front: "矩阵",
            gist: "线性变换", captured: true, outlineNodeId: "section-matrix", order: 0,
          }],
          exerciseLinks: [],
        },
      }),
      loadPlan: vi.fn().mockResolvedValue({
        plan,
        outline: [{ id: "section-vector", title: "向量", level: 2, children: [] }],
        items: [item({ item_id: "vector", title: "学习向量", outlineNodeId: "section-vector" })],
      }),
    }));

    await user.click(await screen.findByRole("button", { name: "开始学习" }));
    expect(screen.getByRole("status", { name: "current route" })).toHaveTextContent("/study/space-b/learn");
    expect(screen.queryByText(/知识核/)).not.toBeInTheDocument();
  });

  it("does not expose legacy directory-binding repair as a learner task", async () => {
    localStorage.clear();
    const user = userEvent.setup();
    const nanaRequest = vi.fn();
    const stopListening = onStudyNanaRequest(nanaRequest);
    renderPage(repository({
      loadPlan: vi.fn().mockResolvedValue({
        plan,
        items: [item({ item_id: "legacy", title: "旧计划行动", outlineNodeId: undefined })],
        outline: [{ id: "section-vector", title: "向量", level: 2, children: [] }],
        learningMap: emptyMap,
      }),
      loadLearnHome: vi.fn().mockResolvedValue({ artifacts: [], knowledgePoints: [], learningMap: emptyMap }),
    }));

    expect(await screen.findByRole("heading", { name: "计划安排" })).toBeInTheDocument();
    expect(screen.queryByText(/关联目录/)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "旧计划行动" })).not.toBeInTheDocument();
    expect(nanaRequest).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "学习" }));
    expect(screen.getByRole("status", { name: "current route" })).toHaveTextContent("/study/space-b/learn");
    expect(JSON.parse(localStorage.getItem("kabuqina.study.location.v1:space-b")!)).toMatchObject({
      page: "plan",
      outlineLabel: "向量",
      outlineNodeId: "section-vector",
    });
    expect(JSON.parse(localStorage.getItem("kabuqina.study.location.v1:space-b")!)).not.toHaveProperty("planItemId");
    stopListening();
  });

  it("leaves knowledge-core compilation to the learning page", async () => {
    const user = userEvent.setup();
    const createKnowledgeCoreCompilation = vi.fn().mockResolvedValue(compilation());
    const nanaRequest = vi.fn();
    const stopListening = onStudyNanaRequest(nanaRequest);
    renderPage(repository({
      loadPlan: vi.fn().mockResolvedValue({
        plan,
        items: [item({ item_id: "vector", title: "学习向量", outlineNodeId: "section-vector" })],
        outline: [{ id: "section-vector", title: "向量", level: 2, children: [] }],
        learningMap: emptyMap,
      }),
      loadLearnHome: vi.fn().mockResolvedValue({
        artifacts: [],
        knowledgePoints: [],
        learningMap: emptyMap,
      }),
      listKnowledgeCoreCompilations: vi.fn().mockResolvedValue([]),
      createKnowledgeCoreCompilation,
    }));

    await user.click(await screen.findByRole("button", { name: "开始学习" }));
    expect(screen.getByRole("status", { name: "current route" })).toHaveTextContent("/study/space-b/learn");
    expect(createKnowledgeCoreCompilation).not.toHaveBeenCalled();
    expect(nanaRequest).not.toHaveBeenCalled();
    stopListening();
  });

  it("does not expose a running compiler state on the plan page", async () => {
    const createKnowledgeCoreCompilation = vi.fn();
    renderPage(repository({
      loadPlan: vi.fn().mockResolvedValue({
        plan,
        items: [item({ item_id: "vector", title: "学习向量", outlineNodeId: "section-vector" })],
        outline: [{ id: "section-vector", title: "向量", level: 2, children: [] }],
        learningMap: emptyMap,
      }),
      listKnowledgeCoreCompilations: vi.fn().mockResolvedValue([compilation({ status: "generating" })]),
      createKnowledgeCoreCompilation,
    }));

    expect(await screen.findByRole("button", { name: "开始学习" })).toBeEnabled();
    expect(screen.queryByText(/正在准备/)).not.toBeInTheDocument();
    expect(createKnowledgeCoreCompilation).not.toHaveBeenCalled();
  });

  it("does not put compiler cancellation controls in the plan directory", async () => {
    const cancelKnowledgeCoreCompilation = vi.fn().mockResolvedValue(
      compilation({ status: "cancelled" }),
    );
    renderPage(repository({
      loadPlan: vi.fn().mockResolvedValue({
        plan,
        items: [item({ item_id: "vector", title: "学习向量", outlineNodeId: "section-vector" })],
        outline: [{ id: "section-vector", title: "向量", level: 2, children: [] }],
        learningMap: emptyMap,
      }),
      listKnowledgeCoreCompilations: vi.fn().mockResolvedValue([compilation({ status: "generating" })]),
      cancelKnowledgeCoreCompilation,
    }));

    expect(await screen.findByRole("button", { name: "开始学习" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "取消准备" })).not.toBeInTheDocument();
    expect(cancelKnowledgeCoreCompilation).not.toHaveBeenCalled();
  });

  it("does not put compiler restart controls in the plan directory", async () => {
    const createKnowledgeCoreCompilation = vi.fn().mockResolvedValue(compilation({ runId: "run-2" }));
    renderPage(repository({
      loadPlan: vi.fn().mockResolvedValue({
        plan,
        items: [item({ item_id: "vector", title: "学习向量", outlineNodeId: "section-vector" })],
        outline: [{ id: "section-vector", title: "向量", level: 2, children: [] }],
        learningMap: emptyMap,
      }),
      listKnowledgeCoreCompilations: vi.fn().mockResolvedValue([compilation({ status: "cancelled" })]),
      createKnowledgeCoreCompilation,
    }));

    expect(await screen.findByRole("button", { name: "开始学习" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "重新准备" })).not.toBeInTheDocument();
    expect(createKnowledgeCoreCompilation).not.toHaveBeenCalled();
  });

  it("does not open generated knowledge-core drafts from the plan directory", async () => {
    const draftRequest = vi.fn();
    const stopListening = onStudyDraftRequest(draftRequest);
    renderPage(repository({
      loadPlan: vi.fn().mockResolvedValue({
        plan,
        items: [item({ item_id: "vector", title: "学习向量", outlineNodeId: "section-vector" })],
        outline: [{ id: "section-vector", title: "向量", level: 2, children: [] }],
        learningMap: emptyMap,
      }),
      listKnowledgeCoreCompilations: vi.fn().mockResolvedValue([
        compilation({ status: "draft_ready", draftArtifactId: "deck-draft-1" }),
      ]),
    }));

    expect(await screen.findByRole("button", { name: "开始学习" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "查看知识核草稿" })).not.toBeInTheDocument();
    expect(draftRequest).not.toHaveBeenCalled();
    stopListening();
  });

  it("leaves compiler recovery on the learning page", async () => {
    const retryKnowledgeCoreCompilation = vi.fn().mockResolvedValue(
      compilation({ status: "queued", reasonCode: null }),
    );
    renderPage(repository({
      loadPlan: vi.fn().mockResolvedValue({
        plan,
        items: [item({ item_id: "vector", title: "学习向量", outlineNodeId: "section-vector" })],
        outline: [{ id: "section-vector", title: "向量", level: 2, children: [] }],
        learningMap: emptyMap,
      }),
      listKnowledgeCoreCompilations: vi.fn().mockResolvedValue([
        compilation({ status: "needs_source", reasonCode: "source_text_unavailable" }),
      ]),
      retryKnowledgeCoreCompilation,
    }));

    expect(await screen.findByRole("button", { name: "开始学习" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "再试一次" })).not.toBeInTheDocument();
    expect(retryKnowledgeCoreCompilation).not.toHaveBeenCalled();
  });

  it("opens learning first even when a later plan action is practice", async () => {
    const user = userEvent.setup();
    localStorage.clear();
    renderPage(repository({
      loadLearnHome: vi.fn().mockResolvedValue({
        artifacts: [],
        knowledgePoints: [{
          item_id: "core-1", artifact_id: "deck-1", front: "向量定义", gist: "大小与方向", captured: true,
        }],
        learningMap: {
          revision: 1,
          outlineStatus: "ready",
          outlineNodes: [],
          knowledgeCores: [{
            id: "core-1", itemId: "card-1", artifactId: "deck-1", front: "向量定义",
            gist: "大小与方向", captured: true, outlineNodeId: "section-vector", order: 0,
          }],
          exerciseLinks: [],
        },
      }),
      loadPlan: vi.fn().mockResolvedValue({
        plan,
        outline: [{
          id: "section-vector", title: "1.1 向量", level: 2, page: 12, children: [],
          sourceArtifactId: "book-1", sourceTitle: "线性代数", sourcePath: "第一章 › 1.1 向量",
        }],
        outlineSourceArtifactId: "book-1",
        outlineSourceTitle: "线性代数",
        structureStatus: "reliable",
        items: [item({
          item_id: "practice-next",
          title: "做一道向量题",
          mode: "practice",
          outlineNodeId: "section-vector",
        })],
      }),
    }));

    const outlineActions = await screen.findByRole("region", { name: "1.1 向量的学习安排" });
    expect(within(outlineActions).getByRole("heading", { name: "做一道向量题" })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: "做一道向量题" })).toHaveLength(1);
    const action = (await screen.findByRole("heading", { name: "做一道向量题" })).closest("li")!;
    expect(within(action).getByText("练习")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "开始学习" }));

    await waitFor(() => {
      expect(screen.getByRole("status", { name: "current route" })).toHaveTextContent("/study/space-b/learn");
    });
    expect(JSON.parse(localStorage.getItem("kabuqina.study.location.v1:space-b")!)).toMatchObject({
      page: "plan",
      planItemId: "practice-next",
      outlineNodeId: "section-vector",
    });
  });

  it("completes one item through the URL-scoped repository and patches its state", async () => {
    const user = userEvent.setup();
    const open = item({ item_id: "next", title: "Next task" });
    const completed = { ...open, status: "completed" as const, completedAt: "2026-07-11T01:00:00Z" };
    const loadPlan = vi.fn()
      .mockResolvedValueOnce({ plan, items: [open] })
      .mockResolvedValue({ plan, items: [completed] });
    const completePlanItem = vi.fn().mockResolvedValue(completed);
    renderPage(repository({ loadPlan, completePlanItem }));

    await user.click(await screen.findByRole("button", { name: "完成" }));
    expect(completePlanItem).toHaveBeenCalledWith("space-b", "next", expect.any(AbortSignal));
    await waitFor(() => {
      const item = screen.getByRole("heading", { name: "Next task" }).closest("li");
      expect(item).not.toBeNull();
      expect(within(item as HTMLElement).getAllByText("已完成")).not.toHaveLength(0);
    });
  });

  it("keeps the open item when a mutation fails", async () => {
    const user = userEvent.setup();
    const open = item({ item_id: "next", title: "Next task" });
    renderPage(repository({
      loadPlan: vi.fn().mockResolvedValue({ plan, items: [open] }),
      skipPlanItem: vi.fn().mockRejectedValue(new Error("conflict")),
    }));

    await user.click(await screen.findByRole("button", { name: "跳过" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("当前状态已保留");
    expect(screen.getByRole("button", { name: "完成" })).toBeEnabled();
  });

  it("keeps skip distinct from completion", async () => {
    const user = userEvent.setup();
    const open = item({ item_id: "next", title: "Next task" });
    const skipped = { ...open, status: "skipped" as const, skippedAt: "2026-07-11T01:00:00Z" };
    const completePlanItem = vi.fn();
    const skipPlanItem = vi.fn().mockResolvedValue(skipped);
    renderPage(repository({
      loadPlan: vi.fn()
        .mockResolvedValueOnce({ plan, items: [open] })
        .mockResolvedValue({ plan, items: [skipped] }),
      completePlanItem,
      skipPlanItem,
    }));

    await user.click(await screen.findByRole("button", { name: "跳过" }));
    await waitFor(() => {
      const item = screen.getByRole("heading", { name: "Next task" }).closest("li");
      expect(item).not.toBeNull();
      expect(within(item as HTMLElement).getAllByText("已跳过")).not.toHaveLength(0);
    });
    expect(skipPlanItem).toHaveBeenCalledWith("space-b", "next", expect.any(AbortSignal));
    expect(completePlanItem).not.toHaveBeenCalled();
  });

  it("surfaces a newer plan draft while a legacy plan is active", async () => {
    const user = userEvent.setup();
    const draftRequest = vi.fn();
    const stopListening = onStudyDraftRequest(draftRequest);
    renderPage(repository({
      loadPlan: vi.fn().mockResolvedValue({
        plan,
        items: [item({ item_id: "legacy", title: "旧计划行动" })],
      }),
      listDraftPage: vi.fn().mockResolvedValue({
        items: [{
          artifact_id: "bound-plan-draft",
          kind: "learning_plan",
          title: "目录绑定版学习计划",
          status: "draft",
        }],
        total: 1,
        kindCounts: { learning_plan: 1 },
        returned: 1,
        limit: 50,
        offset: 0,
        truncated: false,
      }),
    }));

    expect(await screen.findByText("有一份新的学习计划草稿")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "查看并采用" }));
    expect(draftRequest).toHaveBeenCalledWith({
      spaceId: "space-b",
      artifactId: "bound-plan-draft",
    });
    stopListening();
  });

  it("renders an honest empty state", async () => {
    const nanaRequest = vi.fn();
    const stopListening = onStudyNanaRequest(nanaRequest);
    const user = userEvent.setup();
    renderPage(repository({
      loadLearnHome: vi.fn().mockResolvedValue({
        artifacts: [{ artifact_id: "source-1", kind: "resource_pack", title: "Python.pdf", status: "active" }],
        knowledgePoints: [],
      }),
    }));
    expect(await screen.findByRole("heading", { name: "还没有学习计划" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "+ 学习计划" }));
    expect(nanaRequest).toHaveBeenCalledWith(expect.objectContaining({
      spaceId: "space-b",
      page: "plan",
      focusId: "new-learning-plan:source-1",
      selectedSource: { id: "source-1", title: "Python.pdf" },
      autoSend: true,
    }));
    stopListening();
  });

  it("retains the active plan when its action projection is temporarily unavailable", async () => {
    const loadPlan = vi.fn().mockResolvedValue({
      plan,
      items: [],
      unavailable: ["items"],
      outline: [],
      outlineSourceArtifactId: "",
      outlineSourceTitle: "",
      structureStatus: "unknown",
    });
    renderPage(repository({ loadPlan }));

    expect(await screen.findByRole("alert")).toHaveTextContent("行动进度暂时无法读取");
    expect(screen.queryByText("当前计划")).not.toBeInTheDocument();
    expect(screen.queryByText("这份计划里的行动已经处理完")).not.toBeInTheDocument();
    expect(screen.queryByText(/0 项完成/)).not.toBeInTheDocument();
  });

  it("does not couple plan-directory readability to compiler status", async () => {
    renderPage(repository({
      loadPlan: vi.fn().mockResolvedValue({
        plan,
        items: [item({ item_id: "learn-vector", title: "理解向量", outlineNodeId: "section-vector" })],
        outline: [{ id: "section-vector", title: "向量", level: 1, children: [] }],
        outlineSourceArtifactId: "source-1",
        outlineSourceTitle: "线性代数",
        structureStatus: "reliable",
        learningMap: emptyMap,
      }),
      listKnowledgeCoreCompilations: vi.fn().mockRejectedValue(new Error("offline")),
    }));

    expect(await screen.findByRole("heading", { name: "理解向量" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "开始学习" })).toBeEnabled();
    expect(screen.queryByText(/知识核准备状态/)).not.toBeInTheDocument();
  });

  it("asks the learner to choose one file when several knowledge sources exist", async () => {
    const nanaRequest = vi.fn();
    const stopListening = onStudyNanaRequest(nanaRequest);
    const user = userEvent.setup();
    renderPage(repository({
      loadLearnHome: vi.fn().mockResolvedValue({
        artifacts: [
          { artifact_id: "source-a", kind: "resource_pack", title: "教材.pdf", status: "active" },
          { artifact_id: "source-b", kind: "resource_pack", title: "讲义.pdf", status: "active" },
        ],
        knowledgePoints: [],
      }),
    }));

    await user.click(await screen.findByRole("button", { name: "+ 学习计划" }));
    expect(await screen.findByRole("heading", { name: "选择生成计划的知识源" })).toBeInTheDocument();
    expect(nanaRequest).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "讲义.pdf" }));
    expect(nanaRequest).toHaveBeenCalledWith(expect.objectContaining({
      selectedSource: { id: "source-b", title: "讲义.pdf" },
      autoSend: true,
    }));
    stopListening();
  });

  it("never flashes a draft before the canonical active-plan request resolves", async () => {
    let resolvePlan!: (value: unknown) => void;
    const loadPlan = vi.fn().mockReturnValue(new Promise((resolve) => { resolvePlan = resolve; }));
    const listDraftPage = vi.fn().mockResolvedValue({
      items: [{ artifact_id: "stale-draft", kind: "learning_plan", title: "不该闪现的草稿", status: "draft" }],
      total: 1, kindCounts: { learning_plan: 1 }, returned: 1, limit: 50, offset: 0, truncated: false,
    });
    renderPage(repository({ loadPlan, listDraftPage }));

    await waitFor(() => expect(listDraftPage).toHaveBeenCalled());
    expect(screen.queryByRole("heading", { name: "不该闪现的草稿" })).not.toBeInTheDocument();
    resolvePlan({
      plan,
      items: [item({ item_id: "formal-task", title: "正式计划行动", phaseTitle: "第一阶段" })],
      outline: [],
      outlineSourceArtifactId: "",
      outlineSourceTitle: "",
      structureStatus: "reliable",
    });
    expect(await screen.findByRole("heading", { name: "正式计划行动" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "不该闪现的草稿" })).not.toBeInTheDocument();
  });

  it("offers material import before plan generation when the course has no source", async () => {
    const user = userEvent.setup();
    const importButton = document.createElement("button");
    importButton.setAttribute("aria-label", "添加知识源");
    const imported = vi.fn();
    importButton.addEventListener("click", imported);
    document.body.appendChild(importButton);
    renderPage(repository({
      loadPlan: vi.fn().mockResolvedValue({
        plan: null,
        items: [],
        hasKnowledgeSources: false,
        outline: [],
        outlineSourceArtifactId: "",
        outlineSourceTitle: "",
        structureStatus: "unknown",
      }),
    }));

    expect(await screen.findByRole("heading", { name: "先放入知识源" })).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "添加知识源" })[1]);
    expect(imported).toHaveBeenCalledTimes(1);
    importButton.remove();
  });

  it("offers upload when plan creation finds no knowledge-source files", async () => {
    const user = userEvent.setup();
    const importButton = document.createElement("button");
    importButton.setAttribute("aria-label", "添加知识源");
    const imported = vi.fn();
    importButton.addEventListener("click", imported);
    document.body.appendChild(importButton);
    renderPage(repository({
      loadPlan: vi.fn().mockResolvedValue({
        plan: null,
        items: [],
        hasKnowledgeSources: true,
        outline: [],
        outlineSourceArtifactId: "",
        outlineSourceTitle: "",
        structureStatus: "unknown",
      }),
      loadLearnHome: vi.fn().mockResolvedValue({ artifacts: [], knowledgePoints: [] }),
    }));

    await user.click(await screen.findByRole("button", { name: "+ 学习计划" }));
    expect(await screen.findByRole("heading", { name: "知识源里还没有文件" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "上传资料" }));
    expect(imported).toHaveBeenCalledTimes(1);
    importButton.remove();
  });

  it("shows the draft as the plan until adoption, then replaces it with the active plan", async () => {
    const user = userEvent.setup();
    localStorage.clear();
    let finishActivation!: () => void;
    const setArtifactStatus = vi.fn().mockReturnValue(new Promise<void>((resolve) => { finishActivation = resolve; }));
    const loadPlan = vi.fn()
      .mockResolvedValueOnce({
        plan: null,
        items: [],
        outline: [],
        outlineSourceArtifactId: "",
        outlineSourceTitle: "",
        structureStatus: "reliable",
      })
      .mockResolvedValue({
        plan,
        items: [item({ item_id: "active-task", title: "理解变量", phaseTitle: "第一阶段", outlineNodeId: "section-variables" })],
        outline: [{ id: "section-variables", title: "变量", level: 2, children: [] }],
        outlineSourceArtifactId: "",
        outlineSourceTitle: "",
        structureStatus: "reliable",
      });
    renderPage(repository({
      listDraftPage: vi.fn().mockResolvedValue({
        items: [{ artifact_id: "draft-plan", kind: "learning_plan", title: "Python 学习计划", status: "draft", review: { mode: "semantic", status: "pending" } }],
        total: 1, kindCounts: { learning_plan: 1 }, returned: 1, limit: 50, offset: 0, truncated: false,
      }),
      loadArtifactDetail: vi.fn().mockResolvedValue({
        artifactId: "draft-plan", kind: "learning_plan", title: "Python 学习计划", version: 1, status: "draft",
        review: { mode: "semantic", status: "pending" },
        envelope: { payload: { phases: [{ title: "第一阶段", tasks: [{ title: "理解变量", done_when: "能解释赋值" }] }] } },
      }),
      loadPlan,
      setArtifactStatus,
    }));

    expect(await screen.findByRole("heading", { name: "Python 学习计划" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "理解变量" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "学习" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "采用计划" }));
    expect(await screen.findByText("正在采用学习计划…")).toBeInTheDocument();
    expect(screen.queryByText("这份计划尚未生效。确认后才会成为正式计划。")).not.toBeInTheDocument();
    finishActivation();
    await waitFor(() => expect(setArtifactStatus).toHaveBeenCalledWith(
      "space-b",
      "draft-plan",
      "active",
      expect.any(AbortSignal),
    ));
    await waitFor(() => expect(screen.getByRole("button", { name: "开始学习" })).toBeEnabled());
    await waitFor(() => expect(JSON.parse(localStorage.getItem("kabuqina.study.location.v1:space-b")!)).toMatchObject({
      page: "plan",
      planItemId: "active-task",
      planItemTitle: "理解变量",
      outlineLabel: "第一阶段",
    }));
    expect(screen.queryByText("正在进行")).not.toBeInTheDocument();
    expect(screen.queryByText("这份计划尚未生效。确认后才会成为正式计划。")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "采用计划" })).not.toBeInTheDocument();
  });
});
