// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../lib/i18n";
import type { StudyChatHandoff } from "../lib/studyChatHandoff";
import { ChatPaperHeader } from "./ChatPaperHeader";

const studyHandoff: StudyChatHandoff = {
  version: 1,
  mode: "study",
  sessionId: "session-a",
  spaceId: "space-a",
  spaceTitle: "高等数学",
  focusKind: "quiz_step",
  focusId: "question-2",
  focusLabel: "练习 · 第 2 步",
  intent: "explain",
  originSurface: "study_desk",
  returnTarget: { path: "/study/space-a/practice", fallbackPath: "/study/space-a", focus: "answer" },
  revision: 1,
  question: "为什么还要继续分析？",
  prompt: "计算极限。",
  createdAt: "2026-07-24T00:00:00.000Z",
};

function renderHeader(props: Partial<Parameters<typeof ChatPaperHeader>[0]> = {}) {
  const handlers = {
    onOpenHistory: vi.fn(),
    onReturnStudy: vi.fn(),
  };
  render(
    <I18nProvider>
      <ChatPaperHeader
        studyHandoff={null}
        {...handlers}
        {...props}
      />
    </I18nProvider>,
  );
  return handlers;
}

describe("ChatPaperHeader", () => {
  /**
   * 从全局入口进来是**自由会话**：标题行上除了历史入口什么都没有，
   * 不预先摆一个作用域出来（架构 §8.10）。
   */
  it("shows nothing but the history entry for a free conversation", () => {
    renderHeader();
    expect(screen.getByRole("button", { name: "打开历史会话" })).toBeInTheDocument();
    expect(screen.queryByRole("heading")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /返回/ })).not.toBeInTheDocument();
  });

  it("names the bound course and restores its heading after a reversible hide", () => {
    const handlers = renderHeader({ studyHandoff });
    expect(screen.getByRole("heading", { name: "练习 · 第 2 步" })).toBeInTheDocument();
    expect(screen.getByText("高等数学")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "返回这一步" }));
    expect(handlers.onReturnStudy).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "隐藏上下文标题" }));
    expect(screen.queryByRole("heading", { name: "练习 · 第 2 步" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "显示上下文标题" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "显示上下文标题" }));
    expect(screen.getByRole("heading", { name: "练习 · 第 2 步" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "返回这一步" })).toBeInTheDocument();
  });

  /**
   * 选中有来源的会话时只给来源标签和一个返回动作——课程、项目、进度面板
   * 都不在 Chat 里展开（原型 AGENTS）。
   */
  it("does not expand a course, project, or progress panel", () => {
    renderHeader({ studyHandoff });
    const head = document.querySelector(".kq-chat-paper-head")!;
    // 标题行上只有：历史、标题+来源、返回、可逆隐藏。
    expect(head.querySelectorAll("button")).toHaveLength(3);
  });
});
