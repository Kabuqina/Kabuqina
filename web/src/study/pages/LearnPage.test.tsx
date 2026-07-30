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

function renderPage(home: Awaited<ReturnType<StudyRepository["loadLearnHome"]>>) {
  const repository = { loadLearnHome: vi.fn().mockResolvedValue(home) } as unknown as StudyRepository;
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

  it("compares without scoring and switches to Practice on the same core", async () => {
    const user = userEvent.setup();
    renderPage({ artifacts: [], knowledgePoints: points });
    await screen.findByRole("heading", { name: "极限唯一性" });
    await user.click(screen.getByRole("button", { name: "和教材对一下" }));
    expect(screen.getByRole("region", { name: "教材与我的说法对照" })).toHaveTextContent("这里不判分");
    expect(screen.getByRole("link", { name: "去练习这个知识核" })).toHaveAttribute("href", "/study/space-a/practice");
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
});
