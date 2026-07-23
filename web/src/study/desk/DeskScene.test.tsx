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

    expect(await screen.findByRole("heading", { name: "高等数学 · 极限" })).toBeInTheDocument();
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
});
