// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../../lib/i18n";
import type { StudyRepository } from "../repository";
import { StudyRepositoryProvider } from "../repositoryContext";
import { LearnPage } from "./LearnPage";

const points = [
  { item_id: "core-1", artifact_id: "deck-1", front: "极限唯一性", gist: "极限若存在则唯一", captured: true as const },
  { item_id: "core-2", artifact_id: "deck-1", front: "无穷小", gist: "趋于零的量", captured: true as const },
];

function renderPage(
  home: Awaited<ReturnType<StudyRepository["loadLearnHome"]>>,
  overrides: Partial<StudyRepository> = {},
) {
  const repository = { loadLearnHome: vi.fn().mockResolvedValue(home), ...overrides } as unknown as StudyRepository;
  render(
    <I18nProvider><StudyRepositoryProvider repository={repository}><MemoryRouter>
      <LearnPage spaceId="space-a" />
    </MemoryRouter></StudyRepositoryProvider></I18nProvider>,
  );
  return repository;
}

describe("LearnPage", () => {
  beforeEach(() => localStorage.clear());

  it("shows exactly one knowledge core and preserves each learner draft", async () => {
    const user = userEvent.setup();
    renderPage({ artifacts: [], knowledgePoints: points });

    expect(await screen.findByRole("heading", { name: "极限唯一性" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "无穷小" })).not.toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "我的说法" }), "这是我自己的解释");
    await user.click(screen.getByRole("button", { name: "和教材对一下" }));
    await user.click(screen.getByRole("button", { name: /下一个/ }));
    expect(await screen.findByRole("heading", { name: "无穷小" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "我的说法" })).toHaveValue("");
    await user.click(screen.getByRole("button", { name: /上一个/ }));
    expect(screen.getByRole("textbox", { name: "我的说法" })).toHaveValue("这是我自己的解释");
    expect(screen.getByRole("region", { name: "教材与我的说法对照" })).toBeInTheDocument();
  });

  it("shows the scoped knowledge-core sequence as a compact selectable index", async () => {
    const user = userEvent.setup();
    renderPage({ artifacts: [], knowledgePoints: points });

    const index = await screen.findByRole("navigation", { name: "这一节的知识点" });
    const first = screen.getByRole("button", { name: "极限唯一性" });
    const second = screen.getByRole("button", { name: "无穷小" });
    expect(index).toContainElement(first);
    expect(index).toContainElement(second);
    expect(first).toHaveAttribute("aria-current", "step");

    await user.click(second);
    expect(second).toHaveAttribute("aria-current", "step");
    expect(await screen.findByRole("heading", { name: "无穷小" })).toBeInTheDocument();
  });

  it("keeps previous and next navigation inside the active plan outline range", async () => {
    renderPage({
      artifacts: [],
      knowledgePoints: points,
      learningMap: {
        revision: 4,
        outlineStatus: "ready",
        outlineNodes: [
          { id: "section-a", parentId: null, title: "A", order: 0, depth: 1, origin: "extracted", sourceRef: {}, locator: "§A" },
          { id: "section-b", parentId: null, title: "B", order: 1, depth: 1, origin: "extracted", sourceRef: {}, locator: "§B" },
        ],
        knowledgeCores: [
          { id: "core-1", itemId: "card-1", artifactId: "deck-1", front: "极限唯一性", gist: "极限若存在则唯一", captured: true, outlineNodeId: "section-a", order: 0 },
          { id: "core-2", itemId: "card-2", artifactId: "deck-1", front: "无穷小", gist: "趋于零的量", captured: true, outlineNodeId: "section-b", order: 1 },
        ],
        exerciseLinks: [],
      },
      location: {
        revision: 1, mapRevision: 4, page: "learn", knowledgeCoreId: "core-1",
        outlineNodeId: "section-a", planItemId: "plan-a", planOutlineNodeId: "section-a",
        exerciseId: null, exerciseByCore: {}, stale: false,
        updatedAt: "2026-07-31T00:00:00Z",
      },
    });

    expect(await screen.findByRole("heading", { name: "极限唯一性" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /下一个/ })).toBeDisabled();
    expect(screen.queryByRole("heading", { name: "无穷小" })).not.toBeInTheDocument();
  });

  it("compares without scoring and switches to Practice on the same core", async () => {
    const user = userEvent.setup();
    renderPage({ artifacts: [], knowledgePoints: points });
    await screen.findByRole("heading", { name: "极限唯一性" });
    await user.click(screen.getByRole("button", { name: "和教材对一下" }));
    expect(screen.getByRole("region", { name: "教材与我的说法对照" })).toHaveTextContent("这里不判分");
    expect(screen.getByRole("link", { name: "去练习这个知识核" })).toHaveAttribute("href", "/study/space-a/notebook?mode=practice");
    await user.click(screen.getByRole("link", { name: "去练习这个知识核" }));
    expect(JSON.parse(localStorage.getItem("kabuqina.study.location.v1:space-a")!)).toMatchObject({
      page: "practice",
      knowledgeCoreId: "core-1",
    });
  });

  it("keeps an empty learner explanation empty when comparison is opened", async () => {
    const user = userEvent.setup();
    renderPage({ artifacts: [], knowledgePoints: points });
    await screen.findByRole("heading", { name: "极限唯一性" });
    await user.click(screen.getByRole("button", { name: "和教材对一下" }));

    const comparison = screen.getByRole("region", { name: "教材与我的说法对照" });
    expect(comparison).not.toHaveTextContent("还没有写下自己的说法");
    expect(screen.getByRole("textbox", { name: "我的说法" })).toHaveValue("");
  });

  it("does not carry a learner explanation into another course with the same core id", async () => {
    const user = userEvent.setup();
    const repository = { loadLearnHome: vi.fn().mockResolvedValue({ artifacts: [], knowledgePoints: points }) } as unknown as StudyRepository;
    const tree = (spaceId: string) => (
      <I18nProvider><StudyRepositoryProvider repository={repository}><MemoryRouter>
        <LearnPage spaceId={spaceId} />
      </MemoryRouter></StudyRepositoryProvider></I18nProvider>
    );
    const view = render(tree("space-a"));

    expect(await screen.findByRole("heading", { name: "极限唯一性" })).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "我的说法" }), "只属于课程 A");
    view.rerender(tree("space-b"));

    expect(await screen.findByRole("textbox", { name: "我的说法" })).toHaveValue("");
    expect(localStorage.getItem("kabuqina.study.learn-draft.v1:space-a:core-1")).toContain("只属于课程 A");
    expect(localStorage.getItem("kabuqina.study.learn-draft.v1:space-b:core-1")).toBeNull();
  });

  it("keeps a missing knowledge-core projection honest", async () => {
    renderPage({ artifacts: [], knowledgePoints: [], unavailable: ["knowledgePoints"] });
    expect(await screen.findByText(/知识核暂时无法读取/)).toBeInTheDocument();
    expect(screen.queryByText("课程知识库")).not.toBeInTheDocument();
  });

  it("shows a running compiler state instead of an empty knowledge-core message", async () => {
    renderPage({
      artifacts: [],
      knowledgePoints: [],
      location: {
        revision: 1, mapRevision: 1, page: "learn", knowledgeCoreId: null,
        outlineNodeId: "section-a", planItemId: "plan-a", planOutlineNodeId: "section-a",
        exerciseId: null, exerciseByCore: {}, stale: false,
        updatedAt: "2026-07-31T00:00:00Z",
      },
    }, {
      listKnowledgeCoreCompilations: vi.fn().mockResolvedValue([{
        runId: "run-1",
        spaceId: "space-a",
        outlineNodeId: "section-a",
        planItemId: "plan-a",
        trigger: "start_learning",
        status: "generating",
        sourceFingerprint: "source",
        policyVersion: "v1",
        draftArtifactId: null,
        reasonCode: null,
        sourceWindows: [],
        createdAt: "2026-07-31T00:00:00Z",
        updatedAt: "2026-07-31T00:00:00Z",
      }]),
    });

    expect(await screen.findByRole("heading", { name: "正在准备学习内容" })).toBeInTheDocument();
    expect(screen.queryByText(/还没有知识核/)).not.toBeInTheDocument();
  });

  it("starts knowledge-core preparation on the learning page without opening chat", async () => {
    localStorage.setItem("kabuqina.study.location.v1:space-a", JSON.stringify({
      version: 1,
      courseId: "space-a",
      page: "plan",
      planItemId: "plan-a",
      planItemTitle: "学习极限",
      outlineNodeId: "section-a",
      exerciseByCore: {},
      updatedAt: "2026-08-03T00:00:00Z",
    }));
    const createKnowledgeCoreCompilation = vi.fn().mockResolvedValue({
      runId: "run-1",
      spaceId: "space-a",
      outlineNodeId: "section-a",
      planItemId: "plan-a",
      trigger: "start_learning",
      status: "queued",
      sourceFingerprint: "source",
      policyVersion: "v1",
      draftArtifactId: null,
      reasonCode: null,
      sourceWindows: [],
      createdAt: "2026-08-03T00:00:00Z",
      updatedAt: "2026-08-03T00:00:00Z",
    });
    renderPage({
      artifacts: [],
      knowledgePoints: [],
      learningMap: {
        revision: 4,
        outlineStatus: "ready",
        outlineNodes: [{
          id: "section-a", parentId: null, title: "极限", order: 0, depth: 1,
          origin: "extracted", sourceRef: { artifact_id: "source-1", page: 1 }, locator: "第一章",
        }],
        knowledgeCores: [],
        exerciseLinks: [],
      },
    }, {
      listKnowledgeCoreCompilations: vi.fn().mockResolvedValue([]),
      createKnowledgeCoreCompilation,
    });

    await screen.findByRole("heading", { name: "正在准备学习内容" });
    expect(createKnowledgeCoreCompilation).toHaveBeenCalledWith(expect.objectContaining({
      spaceId: "space-a",
      outlineNodeId: "section-a",
      planItemId: "plan-a",
      trigger: "start_learning",
      expectedMapRevision: 4,
      priority: 10,
    }), expect.any(AbortSignal));
  });

  it("keeps a compiler-status failure local instead of inventing an empty core state", async () => {
    renderPage({
      artifacts: [],
      knowledgePoints: [],
      location: {
        revision: 1, mapRevision: 1, page: "learn", knowledgeCoreId: null,
        outlineNodeId: "section-a", planItemId: "plan-a", planOutlineNodeId: "section-a",
        exerciseId: null, exerciseByCore: {}, stale: false,
        updatedAt: "2026-07-31T00:00:00Z",
      },
    }, {
      listKnowledgeCoreCompilations: vi.fn().mockRejectedValue(new Error("offline")),
    });

    expect(await screen.findByRole("alert")).toHaveTextContent("知识核整理状态暂时无法读取");
    expect(screen.queryByRole("heading", { name: "这一节还没有采用的知识核" })).not.toBeInTheDocument();
  });
});
