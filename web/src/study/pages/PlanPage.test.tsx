// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../../lib/i18n";
import type { StudyPlanItem } from "../../chat/study/study-api";
import type { StudyRepository } from "../repository";
import { StudyRepositoryProvider } from "../repositoryContext";
import { PlanPage } from "./PlanPage";
import { StudyIaProvider } from "../StudyIaContext";
import { StudyDraftProvider } from "../DraftContext";
import type { StudyIaSink } from "../iaEvents";

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
    completedAt: "", skippedAt: "", note: "", createdAt: "2026-07-11T00:00:00Z",
    ...overrides,
  };
}

const plan = {
  artifact_id: "plan-1", kind: "learning_plan", title: "Physics plan", status: "active",
  updated_at: "2026-07-11T00:00:00Z",
};

describe("PlanPage", () => {
  it("starts an open action at the current knowledge core and creates the continue bookmark", async () => {
    const user = userEvent.setup();
    localStorage.clear();
    renderPage(repository({
      loadLearnHome: vi.fn().mockResolvedValue({ artifacts: [], knowledgePoints: [{
        item_id: "core-1", artifact_id: "deck-1", front: "向量定义", gist: "大小与方向", captured: true,
      }] }),
      loadPlan: vi.fn().mockResolvedValue({
      plan,
      items: [
        item({ item_id: "done", title: "Done", status: "completed" }),
        item({ item_id: "next", title: "Next task", taskIndex: 1, order: 2 }),
      ],
      }),
    }));

    const action = (await screen.findByRole("heading", { name: "Next task" })).closest("li")!;
    await user.click(within(action).getByRole("button", { name: "开始" }));
    expect(localStorage.getItem("kabuqina.study.location.v1:space-b")).toContain('"planItemId":"next"');
    expect(screen.getByRole("status", { name: "current route" })).toHaveTextContent("/study/space-b/learn");
  });

  it("opens practice and preserves the source-outline binding for a practice action", async () => {
    const user = userEvent.setup();
    localStorage.clear();
    renderPage(repository({
      loadLearnHome: vi.fn().mockResolvedValue({ artifacts: [], knowledgePoints: [{
        item_id: "core-1", artifact_id: "deck-1", front: "向量定义", gist: "大小与方向", captured: true,
      }] }),
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

    const outlineActions = await screen.findByRole("region", { name: "1.1 向量的行动" });
    expect(within(outlineActions).getByRole("heading", { name: "做一道向量题" })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: "做一道向量题" })).toHaveLength(1);
    const action = (await screen.findByRole("heading", { name: "做一道向量题" })).closest("li")!;
    expect(within(action).getByText("练习")).toBeInTheDocument();
    await user.click(within(action).getByRole("button", { name: "开始" }));

    expect(screen.getByRole("status", { name: "current route" })).toHaveTextContent("/study/space-b/practice");
    expect(JSON.parse(localStorage.getItem("kabuqina.study.location.v1:space-b")!)).toMatchObject({
      page: "practice",
      planItemId: "practice-next",
      outlineNodeId: "section-vector",
      knowledgeCoreId: "core-1",
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
    await waitFor(() => expect(screen.getByText("已完成")).toBeInTheDocument());
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
    await waitFor(() => expect(screen.getByText("已跳过")).toBeInTheDocument());
    expect(skipPlanItem).toHaveBeenCalledWith("space-b", "next", expect.any(AbortSignal));
    expect(completePlanItem).not.toHaveBeenCalled();
  });

  it("renders an honest empty state", async () => {
    renderPage(repository());
    expect(await screen.findByRole("heading", { name: "还没有生效的学习计划" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "问小娜" })).toBeEnabled();
  });

  it("shows a generated plan draft on the plan page and activates it after review", async () => {
    const user = userEvent.setup();
    const runSemanticReview = vi.fn().mockResolvedValue("passed");
    const setArtifactStatus = vi.fn().mockResolvedValue(undefined);
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
      runSemanticReview,
      setArtifactStatus,
    }));

    expect(await screen.findByRole("heading", { name: "小娜推荐学习计划" })).toBeInTheDocument();
    expect(screen.queryByText("范围与下一行动")).not.toBeInTheDocument();
    expect(screen.queryByText("小娜拟的计划 · 待确认")).not.toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "理解变量" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "检查并采用" }));

    await waitFor(() => expect(runSemanticReview).toHaveBeenCalledWith("space-b", "draft-plan", expect.any(AbortSignal)));
    await waitFor(() => expect(setArtifactStatus).toHaveBeenCalledWith("space-b", "draft-plan", "active", expect.any(AbortSignal)));
  });
});
