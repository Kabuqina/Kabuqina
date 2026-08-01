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
    const markPracticeState = vi.fn();
    const adapter = createAdapter({ markPracticeState });
    const onDirtyChange = vi.fn();
    const { container } = render(
      <DeskScene
        adapter={adapter}
        continueTitle="解释为什么不能直接代入"
        continueMeta="极限 · 练习"
        onDirtyChange={onDirtyChange}
      />,
    );

    const pageTabs = await screen.findByRole("navigation", { name: "笔记本分页" });
    const bookmark = screen.getByRole("button", { name: /继续：解释为什么不能直接代入/ });
    expect(pageTabs.parentElement).toBe(bookmark.parentElement);
    expect(bookmark).toHaveTextContent("继续");
    expect(bookmark).not.toHaveTextContent("解释为什么不能直接代入");
    expect(bookmark).not.toHaveTextContent("极限 · 练习");
    expect(screen.queryByRole("heading", { name: "高等数学 · 极限" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /制作 \/ 成果/ })).not.toBeInTheDocument();
    const root = container.querySelector(".kq-desk");
    expect(root).toHaveAttribute("data-density", "overview");

    fireEvent.click(screen.getByRole("button", { name: /继续这一步/ }));
    expect(root).toHaveAttribute("data-density", "focused");
    expect(screen.getByRole("heading", { name: deskFixtureData.steps[0].prompt })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "解释为什么不能直接代入" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "继续作答" }));
    const answer = screen.getByRole("textbox", { name: /我的答案/ });
    expect(answer).not.toHaveAttribute("readonly");

    fireEvent.change(answer, { target: { value: "代入得到 0/0。" } });
    fireEvent.click(screen.getByRole("button", { name: "检查这一步" }));

    expect(await screen.findByRole("complementary", { name: "小娜批注：还差一步" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存答案" })).toBeInTheDocument();
    expect(answer).not.toHaveAttribute("readonly");
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
    expect(markPracticeState).toHaveBeenCalledWith("ex3-step2", "dirty");
    expect(markPracticeState).toHaveBeenCalledWith("ex3-step2", "checking");
    expect(markPracticeState).toHaveBeenCalledWith("ex3-step2", "needs_revision", needsRevisionResult);
    fireEvent.change(answer, { target: { value: "0/0 是未定式，所以还要继续分析。" } });
    expect(screen.getByRole("complementary", { name: "小娜批注：还差一步" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "保存答案" }));
    expect(await screen.findByRole("button", { name: "检查这一步" })).toBeInTheDocument();
    expect(adapter.saveDraft).toHaveBeenLastCalledWith(
      "ex3-step2",
      "0/0 是未定式，所以还要继续分析。",
      expect.any(AbortSignal),
    );
    await waitFor(() => expect(onDirtyChange).toHaveBeenLastCalledWith(true));
    const blocked = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(blocked);
    expect(blocked.defaultPrevented).toBe(true);
  });

  it("shows a bounded recovery notice inside the notebook", async () => {
    render(<DeskScene adapter={createAdapter()} pageNotice="已回到这条证据对应的知识核和题目。" />);
    expect((await screen.findByText("已回到这条证据对应的知识核和题目。")).closest('[role="status"]')).not.toBeNull();
  });

  it("keeps a blank non-interactive bookmark when no content is associated", async () => {
    const { container } = render(<DeskScene adapter={createAdapter()} />);

    await screen.findByRole("navigation", { name: "笔记本分页" });
    expect(container.querySelector(".kd-bookmark-button.is-empty")).not.toBeNull();
    expect(screen.queryByRole("button", { name: /^继续：/ })).not.toBeInTheDocument();
  });

  it("labels a plan-level bookmark as a start instead of pretending learning already began", async () => {
    render(
      <DeskScene
        adapter={createAdapter()}
        currentPage="plan"
        continueTitle="阅读《迭代器与生成器》讲义"
        continueMeta="阶段一：迭代与惰性求值 · 计划"
        continueLabel="从这里开始"
      />,
    );

    const bookmark = await screen.findByRole("button", {
      name: /从这里开始：阅读《迭代器与生成器》讲义/,
    });
    expect(bookmark).toHaveTextContent("开始");
    expect(bookmark).not.toHaveTextContent("阅读《迭代器与生成器》讲义");
  });

  it("keeps load failures private and retries the same notebook", async () => {
    const loadDesk = vi.fn()
      .mockRejectedValueOnce(new Error("private space_id=space-secret artifact_id=artifact-secret"))
      .mockResolvedValueOnce(deskFixtureData);
    render(<DeskScene adapter={createAdapter({ loadDesk })} />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("这本笔记本暂时没有打开");
    expect(alert).not.toHaveTextContent("space-secret");
    expect(alert).not.toHaveTextContent("artifact-secret");

    fireEvent.click(screen.getByRole("button", { name: "再试一次" }));
    expect(await screen.findByRole("navigation", { name: "笔记本分页" })).toBeInTheDocument();
    expect(loadDesk).toHaveBeenCalledTimes(2);
  });

  it("opens a material spine through the reader callback instead of the old work folder", async () => {
    const onOpenMaterials = vi.fn();
    render(<DeskScene adapter={createAdapter()} onOpenMaterials={onOpenMaterials} />);

    await screen.findByRole("navigation", { name: "笔记本分页" });
    fireEvent.click(screen.getByRole("button", { name: "教材 §2.3" }));

    expect(onOpenMaterials).toHaveBeenCalledWith("material-1");
    expect(screen.queryByRole("heading", { name: /制作/ })).not.toBeInTheDocument();
  });

  it("keeps the answer label singular and reveals only one concise clue", async () => {
    render(
      <DeskScene
        adapter={createAdapter()}
        initialSnapshot={{ density: "focused", activity: "dirty" }}
      />,
    );

    await screen.findByRole("heading", { name: deskFixtureData.steps[0].prompt });
    expect(screen.getByText("我的答案")).toBeInTheDocument();
    expect(screen.queryByText("我的草稿")).not.toBeInTheDocument();
    expect(screen.queryByText(/完成标准/)).not.toBeInTheDocument();

    const hintSummary = screen.getByText("提示", { selector: "summary" });
    fireEvent.click(hintSummary);
    expect(screen.getByText(deskFixtureData.steps[0].referenceHint)).toBeInTheDocument();
    expect(screen.queryByText("直接代入得到未定式时，先识别结构，再选择等价变形。")).not.toBeInTheDocument();
  });

  it("shows the intrinsic exercise origin and its bounded material locator", async () => {
    const sourcedData = {
      ...deskFixtureData,
      steps: deskFixtureData.steps.map((step, index) => index === 0 ? {
        ...step,
        origin: "source" as const,
        sourceLabel: "《高等数学》 · 2.3 极限 · 第 41 页",
      } : step),
    };
    render(
      <DeskScene
        adapter={createAdapter({ loadDesk: vi.fn().mockResolvedValue(sourcedData) })}
        initialSnapshot={{ density: "focused" }}
      />,
    );

    expect(await screen.findByText("资料原题")).toBeInTheDocument();
    expect(screen.getByText("《高等数学》 · 2.3 极限 · 第 41 页")).toBeInTheDocument();
  });

  it("uses one stable knowledge-source rail while desk data is loading", async () => {
    let resolveDesk!: (data: typeof deskFixtureData) => void;
    const pendingDesk = new Promise<typeof deskFixtureData>((resolve) => {
      resolveDesk = resolve;
    });
    render(
      <DeskScene
        adapter={createAdapter({ loadDesk: vi.fn().mockReturnValue(pendingDesk) })}
        currentPage="learn"
        pageBody={<div>学习页正文</div>}
        bookstandFallback={{ ...deskFixtureData.bookstand, currentTitle: deskFixtureData.course.name }}
      />,
    );

    const sourceRail = screen.getByRole("heading", { name: "知识源" }).closest("section");
    expect(sourceRail).toHaveAttribute("aria-busy", "true");
    expect(screen.getByText("正在整理知识源…")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "添加知识源" })).not.toBeInTheDocument();
    expect(screen.queryByText("参考资料")).not.toBeInTheDocument();

    resolveDesk(deskFixtureData);

    expect(await screen.findByRole("button", { name: "教材 §2.3" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "知识源" }).closest("section")).not.toHaveAttribute("aria-busy");
    expect(screen.queryByText("正在整理知识源…")).not.toBeInTheDocument();
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

    expect(await screen.findByRole("complementary", { name: "小娜批注：这一点已经说明清楚" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "继续下一步" }));

    expect(screen.getAllByText("练习 3 · 第 3 步").length).toBeGreaterThan(0);
    expect(screen.getByText("这一步还没有草稿")).toBeInTheDocument();
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

  it("restores the exact checked state and Nana annotation after the desk reloads", async () => {
    const restoredData = {
      ...deskFixtureData,
      initialStepIndex: 0,
      steps: deskFixtureData.steps.map((step, index) => index === 0 ? {
        ...step,
        initialDraft: "刷新后仍保留的答案。",
        initialActivity: "needs_revision" as const,
        initialCheckResult: needsRevisionResult,
      } : step),
    };
    render(<DeskScene adapter={createAdapter({ loadDesk: vi.fn().mockResolvedValue(restoredData) })} />);

    await userEvent.click(await screen.findByRole("button", { name: /继续这一步/ }));
    expect(screen.getByRole("textbox", { name: /我的答案/ })).toHaveValue("刷新后仍保留的答案。");
    expect(screen.getByRole("complementary", { name: "小娜批注：还差一步" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存答案" })).toBeInTheDocument();
  });

  it("moves between questions without moving the knowledge core or losing either question state", async () => {
    const persistDraft = vi.fn();
    const markCurrentStep = vi.fn();
    const sameCoreData = {
      ...deskFixtureData,
      knowledgeCores: [{
        item_id: "core-limit",
        artifact_id: "deck-limit",
        front: "0/0 是什么",
        gist: "未定式不是极限值",
        captured: true as const,
      }],
    };
    render(
      <DeskScene
        adapter={createAdapter({ loadDesk: vi.fn().mockResolvedValue(sameCoreData), persistDraft, markCurrentStep })}
        initialSnapshot={{
          density: "focused",
          activity: "needs_revision",
          answer: "第一题正在修改的答案。",
          checkResult: needsRevisionResult,
        }}
      />,
    );

    expect(await screen.findByRole("complementary", { name: "小娜批注：还差一步" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "当前知识核题目导航" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "下一题" }));
    expect(await screen.findByRole("heading", { name: deskFixtureData.steps[1].prompt })).toBeInTheDocument();
    expect(screen.getByText("0/0 是什么")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "上一题" }));
    expect(await screen.findByRole("heading", { name: deskFixtureData.steps[0].prompt })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /我的答案/ })).toHaveValue("第一题正在修改的答案。");
    expect(screen.getByRole("complementary", { name: "小娜批注：还差一步" })).toBeInTheDocument();
    expect(persistDraft).toHaveBeenCalledWith("ex3-step2", "第一题正在修改的答案。");
    expect(markCurrentStep).toHaveBeenCalledWith(deskFixtureData.steps[1].id);
  });

  it("opens the side Nana conversation from the cup with the current answer and feedback", async () => {
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

    await screen.findByRole("complementary", { name: "小娜批注：还差一步" });
    expect(screen.queryByRole("button", { name: /小娜陪我补这一步/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "碰杯问小娜" }));

    expect(onStartCourseChat).toHaveBeenCalledWith(expect.objectContaining({
      focusId: "ex3-step2",
      answer: "代入得到 0/0。",
      question: "",
      activity: "needs_revision",
      checkResult: needsRevisionResult,
    }));
    expect(screen.getByRole("complementary", { name: "小娜批注：还差一步" })).toBeInTheDocument();
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

    expect(await screen.findByRole("complementary", { name: "小娜批注：还差一步" })).toBeInTheDocument();
    const answer = screen.getByRole("textbox", { name: /我的答案/ });
    expect(answer).toHaveValue("原答案仍然在这里。");
    await waitFor(() => expect(answer).toHaveFocus());
  });

  it("shows only Nana's selected annotation", async () => {
    render(
      <DeskScene
        adapter={createAdapter()}
        initialSnapshot={{
          density: "focused",
          activity: "needs_revision",
          answer: "先保留这一步。",
          checkResult: {
            ...needsRevisionResult,
            annotationKind: "next_step",
          },
        }}
      />,
    );

    expect(await screen.findByRole("complementary", { name: "小娜批注：接下来试试" })).toBeInTheDocument();
    expect(screen.getByText(needsRevisionResult.next)).toBeInTheDocument();
    expect(screen.queryByText(needsRevisionResult.good)).not.toBeInTheDocument();
    expect(screen.queryByText(needsRevisionResult.gap)).not.toBeInTheDocument();
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
    expect(screen.getByRole("button", { name: /想起来了/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /没想起来/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /这张太简单了，别再常来/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /困难|掌握|轻松|再来/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /想起来了/ }));
    await waitFor(() => expect(reviewCard).toHaveBeenCalledWith(
      "card-1",
      "good",
      expect.any(AbortSignal),
    ));
    expect(await screen.findByRole("heading", { name: "极限卡片 2" })).toBeInTheDocument();
  });
});
