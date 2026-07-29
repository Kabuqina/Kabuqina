// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DeskAdapter } from "./deskAdapter";
import { completedResult, deskFixtureData, needsRevisionResult } from "./deskFixtures";
import DeskScene from "./DeskScene";

function createAdapter(overrides: Partial<DeskAdapter> = {}): DeskAdapter {
  return {
    loadDesk: vi.fn().mockResolvedValue(deskFixtureData),
    saveDraft: vi.fn().mockResolvedValue(undefined),
    checkAnswer: vi.fn().mockResolvedValue(needsRevisionResult),
    ...overrides,
  };
}

describe("DeskScene FE-01 preview", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("keeps density and activity independent through resume, writing, and feedback", async () => {
    const adapter = createAdapter();
    const onDirtyChange = vi.fn();
    const { container } = render(
      <DeskScene adapter={adapter} onDirtyChange={onDirtyChange} />,
    );

    const pageTabs = await screen.findByRole("navigation", { name: "笔记本分页" });
    const bookmark = screen.getByRole("button", { name: /继续：练习 3 · 第 2 步/ });
    expect(pageTabs.parentElement).toBe(bookmark.parentElement);
    expect(screen.queryByRole("heading", { name: "高等数学 · 极限" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /制作 \/ 成果/ })).not.toBeInTheDocument();
    const root = container.querySelector(".kq-desk");
    expect(root).toHaveAttribute("data-density", "overview");

    fireEvent.click(screen.getByRole("button", { name: /继续这一步/ }));
    expect(root).toHaveAttribute("data-density", "focused");
    expect(screen.getByRole("heading", { name: "解释为什么不能直接代入" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "继续作答" }));
    const answer = screen.getByRole("textbox", { name: /我的答案/ });
    expect(answer).not.toHaveAttribute("readonly");

    fireEvent.change(answer, { target: { value: "代入得到 0/0。" } });
    fireEvent.click(screen.getByRole("button", { name: "检查这一步" }));

    expect(await screen.findByRole("heading", { name: "页边批注 · 需要修改" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "修改答案" })).toBeInTheDocument();
    expect(root).toHaveAttribute("data-density", "focused");
    expect(adapter.saveDraft).toHaveBeenCalledWith(
      "ex3-step2",
      "代入得到 0/0。",
      expect.any(AbortSignal),
    );
    expect(adapter.checkAnswer).toHaveBeenCalledWith(
      "ex3-step2",
      "代入得到 0/0。",
      expect.any(AbortSignal),
    );
    await waitFor(() => expect(onDirtyChange).toHaveBeenLastCalledWith(true));
    const blocked = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(blocked);
    expect(blocked.defaultPrevented).toBe(true);
  });

  it("supports deterministic completed-state capture and advances to the next step", async () => {
    const user = userEvent.setup();
    render(
      <DeskScene
        adapter={createAdapter()}
        initialSnapshot={{
          density: "focused",
          activity: "completed",
          answer: "代入后得到 0/0。0/0 是未定式，不是极限值，所以还需要继续分析并做等价变形。",
          checkResult: completedResult,
        }}
      />,
    );

    expect(await screen.findByRole("heading", { name: "页边批注 · 本步完成" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "继续下一步" }));

    expect(screen.getByText("练习 3 · 第 3 步")).toBeInTheDocument();
    expect(screen.getByText("尚未开始")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("textbox", { name: /我的答案/ })).toHaveValue(""));
  });

  it("persists recovery input immediately and protects a dirty window unload", async () => {
    const persistDraft = vi.fn();
    const adapter = createAdapter({ persistDraft });
    render(<DeskScene adapter={adapter} />);

    fireEvent.click(await screen.findByRole("button", { name: /继续这一步/ }));
    fireEvent.click(screen.getByRole("button", { name: "继续作答" }));
    fireEvent.change(screen.getByRole("textbox", { name: /我的答案/ }), {
      target: { value: "刷新前也要保留" },
    });

    expect(persistDraft).toHaveBeenCalledWith("ex3-step2", "刷新前也要保留");
    const blocked = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(blocked);
    expect(blocked.defaultPrevented).toBe(true);
  });

  it("reviews the current answer and feedback before starting one course Chat", async () => {
    const onStartCourseChat = vi.fn();
    render(
      <DeskScene
        adapter={createAdapter()}
        initialSnapshot={{
          density: "focused",
          activity: "needs_revision",
          answer: "代入得到 0/0。",
          checkResult: needsRevisionResult,
        }}
        onStartCourseChat={onStartCourseChat}
      />,
    );

    await screen.findByRole("heading", { name: "页边批注 · 需要修改" });
    fireEvent.click(screen.getByRole("button", { name: /让小娜陪我补这一步/ }));
    expect(screen.getByRole("heading", { name: "结合当前这一步问小娜" })).toBeInTheDocument();
    expect(screen.getByText("代入得到 0/0。")).toBeInTheDocument();
    const question = screen.getByLabelText("我卡在哪里？");
    fireEvent.change(question, { target: { value: "为什么未定式还要继续分析？" } });
    fireEvent.click(screen.getByRole("button", { name: "开始提问" }));

    expect(onStartCourseChat).toHaveBeenCalledWith(expect.objectContaining({
      focusId: "ex3-step2",
      answer: "代入得到 0/0。",
      question: "为什么未定式还要继续分析？",
      activity: "needs_revision",
      checkResult: needsRevisionResult,
    }));
  });

  it("restores the exact step, answer, feedback, and answer focus after Chat", async () => {
    render(
      <DeskScene
        adapter={createAdapter()}
        returnFocus={{
          version: 1,
          stepId: "ex3-step2",
          focus: "answer",
          deskSnapshot: {
            activity: "needs_revision",
            answer: "原答案仍然在这里。",
            checkResult: needsRevisionResult,
          },
        }}
      />,
    );

    expect(await screen.findByRole("heading", { name: "页边批注 · 需要修改" })).toBeInTheDocument();
    const answer = screen.getByRole("textbox", { name: /我的答案/ });
    expect(answer).toHaveValue("原答案仍然在这里。");
    await waitFor(() => expect(answer).toHaveFocus());
  });

  it("falls back to the safe overview when the returned step no longer exists", async () => {
    const { container } = render(
      <DeskScene
        adapter={createAdapter()}
        returnFocus={{
          version: 1,
          stepId: "removed-step",
          focus: "answer",
          deskSnapshot: {
            activity: "dirty",
            answer: "不应恢复到别的题目",
          },
        }}
      />,
    );

    expect(await screen.findByRole("heading", { name: "从“0/0 是什么”继续" })).toBeInTheDocument();
    expect(container.querySelector(".kq-desk")).toHaveAttribute("data-density", "overview");
    expect(screen.queryByDisplayValue("不应恢复到别的题目")).not.toBeInTheDocument();
  });

  it("reviews due cards through the canonical adapter and returns to the desk", async () => {
    const reviewCard = vi.fn().mockResolvedValue(deskFixtureData.dueCards[0]);
    render(<DeskScene adapter={createAdapter({ reviewCard })} />);
    await screen.findByRole("button", { name: "开始复习" });
    fireEvent.click(screen.getByRole("button", { name: "开始复习" }));
    expect(screen.getByRole("heading", { name: "极限卡片 1" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /显示答案/ }));
    fireEvent.click(screen.getByRole("button", { name: /掌握/ }));
    await waitFor(() => expect(reviewCard).toHaveBeenCalledWith(
      "card-1",
      "good",
      expect.any(AbortSignal),
    ));
    expect(await screen.findByRole("heading", { name: "极限卡片 2" })).toBeInTheDocument();
  });
});
