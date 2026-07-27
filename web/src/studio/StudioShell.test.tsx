// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../lib/i18n";
import { StudioShell } from "./StudioShell";
import type { StudioProject } from "./studio-api";

afterEach(() => vi.clearAllMocks());

const PROJECT: StudioProject = {
  id: "p1",
  title: "极限概念分享",
  brief: "讲给没学过极限的同学",
  stage: "brief",
  createdAt: "2026-07-27T00:00:00Z",
  updatedAt: "2026-07-27T00:00:00Z",
  sources: [
    {
      id: "s1",
      kind: "study_artifact",
      title: "教材 §2.3 极限的运算法则",
      origin: "高等数学 · 第 23 页",
      excerpt: "若分子与分母的极限同时为 0…",
      createdAt: "2026-07-27T00:00:00Z",
      revision: 1,
      returnTarget: "/study/math/plan",
      fallbackTarget: "/study/math",
    },
  ],
};

function renderShell(projects: StudioProject[], overrides: Partial<Parameters<typeof StudioShell>[0]> = {}) {
  const props = {
    projects,
    currentProjectId: projects[0]?.id ?? null,
    onSelectProject: vi.fn(),
    onCreateProject: vi.fn(),
    onSaveBrief: vi.fn(),
    busy: false,
    ...overrides,
  };
  render(
    <I18nProvider>
      <MemoryRouter>
        <StudioShell {...props} />
      </MemoryRouter>
    </I18nProvider>,
  );
  return props;
}

describe("StudioShell", () => {
  it("lays out the three Studio regions (架构 §3.3)", () => {
    renderShell([PROJECT]);
    expect(screen.getByRole("navigation", { name: "项目册" })).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "来源" })).toBeInTheDocument();
  });

  it("opens a project on its brief, not on an export format", () => {
    renderShell([PROJECT]);
    const main = within(screen.getByRole("main"));
    expect(main.getByRole("heading", { name: "要讲给谁" })).toBeInTheDocument();
    expect(main.getByDisplayValue(PROJECT.brief)).toBeInTheDocument();
    // 项目从表达目标开始，不从文件格式开始——所以工作面里不该有任何选格式的**控件**。
    // （文案里出现"幻灯"是在说"形式之后再选"，那正是这一条，不算违反。）
    const formatControl = main
      .queryAllByRole("button")
      .find((button) => /PPT|幻灯|slides|导出|格式/i.test(button.textContent ?? ""));
    expect(formatControl).toBeUndefined();
    expect(main.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("keeps the brief save button inert until the text actually changes", async () => {
    const user = userEvent.setup();
    const props = renderShell([PROJECT]);
    const save = screen.getByRole("button", { name: "记下来" });
    expect(save).toBeDisabled();

    await user.type(screen.getByDisplayValue(PROJECT.brief), "，让他明白 0/0 不是一个数");
    expect(save).toBeEnabled();
    await user.click(save);
    expect(props.onSaveBrief).toHaveBeenCalledWith("p1", expect.stringContaining("0/0"));
  });

  it("shows gathered sources as traceable read-only snapshots", () => {
    renderShell([PROJECT]);
    const sources = within(screen.getByRole("complementary", { name: "来源" }));
    expect(sources.getByText("教材 §2.3 极限的运算法则")).toBeInTheDocument();
    expect(sources.getByText("高等数学 · 第 23 页")).toBeInTheDocument();
  });

  it("explains the empty state instead of showing an empty canvas", () => {
    renderShell([], { currentProjectId: null });
    expect(screen.getByRole("heading", { name: "还没有项目" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /新建项目/ }).length).toBeGreaterThan(0);
    // 右栏在没有项目时也不该谎报有素材。
    expect(screen.getByText(/还没有取来的素材/)).toBeInTheDocument();
  });
});
