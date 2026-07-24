// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../lib/i18n";
import type { StudyChatHandoff } from "../lib/studyChatHandoff";
import { StudyChatContextBar } from "./StudyChatContextBar";

const handoff: StudyChatHandoff = {
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
  returnTarget: {
    path: "/study/space-a/practice",
    fallbackPath: "/study/space-a",
    focus: "answer",
  },
  revision: 1,
  question: "为什么还要继续分析？",
  prompt: "计算极限。",
  createdAt: "2026-07-24T00:00:00.000Z",
};

describe("StudyChatContextBar", () => {
  it("makes the bound course, exact return, and explicit unbind visible", () => {
    const onReturn = vi.fn();
    const onUnbind = vi.fn();
    render(
      <I18nProvider>
        <StudyChatContextBar handoff={handoff} onReturn={onReturn} onUnbind={onUnbind} />
      </I18nProvider>,
    );

    expect(screen.getByText("高等数学 · 练习 · 第 2 步")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "返回这一步" }));
    fireEvent.click(screen.getByRole("button", { name: "转为普通对话" }));
    expect(onReturn).toHaveBeenCalledTimes(1);
    expect(onUnbind).toHaveBeenCalledTimes(1);
  });
});
