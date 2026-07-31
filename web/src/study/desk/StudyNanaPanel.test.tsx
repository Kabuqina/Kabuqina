// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../../lib/i18n";
import type { StudyChatHandoffV2 } from "../../lib/studyChatHandoff";
import { StudyNanaPanel } from "./StudyNanaPanel";

const handoff: StudyChatHandoffV2 = {
  version: 2,
  mode: "study",
  sessionId: "study-session",
  spaceId: "course-1",
  spaceTitle: "Python 高级程序设计",
  focusKind: "learn",
  focusId: "core-1",
  focusLabel: "生成器",
  intent: "collaborate",
  originSurface: "study_desk",
  returnTarget: { path: "/study/course-1/learn", fallbackPath: "/study/course-1", focus: "core-1" },
  revision: 1,
  nanaContext: {
    schemaVersion: 1,
    course: { id: "course-1", title: "Python 高级程序设计" },
    origin: { page: "learn", route: "/study/course-1/learn", focusId: "core-1", revision: 1 },
    returnTarget: { path: "/study/course-1/learn", fallbackPath: "/study/course-1", focus: "core-1", revision: 1 },
    pageContext: { kind: "learn" },
    sourceRefs: [],
  },
  createdAt: "2026-07-30T00:00:00Z",
};

describe("StudyNanaPanel", () => {
  beforeEach(() => window.localStorage.clear());

  it("shares the scoped transcript while keeping hidden context out of sight", async () => {
    const user = userEvent.setup();
    const onOpenFull = vi.fn();
    render(
      <I18nProvider>
        <StudyNanaPanel
          handoff={handoff}
          onClose={() => undefined}
          onOpenFull={onOpenFull}
          loadMessages={async () => ({
            messages: [
              { role: "user", content: "【Study 协作原则】\n隐藏上下文\n【用户本次输入】\n我卡在 yield。" },
              { role: "assistant", content: "先看它暂停和恢复的位置。" },
            ],
          })}
        />
      </I18nProvider>,
    );

    expect(await screen.findByText("我卡在 yield。")).toBeInTheDocument();
    expect(screen.queryByText(/隐藏上下文/)).not.toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "发送消息" }), "给我一个反例，但先别直接解释完");
    expect(screen.getByRole("textbox", { name: "发送消息" })).toHaveValue("给我一个反例，但先别直接解释完");
    await user.click(screen.getByRole("button", { name: /在完整 Chat 中打开/ }));
    expect(onOpenFull).toHaveBeenCalledWith(handoff, "给我一个反例，但先别直接解释完");
  });

  it("prefills a scoped preparation request when Plan opens a missing knowledge core", async () => {
    render(
      <I18nProvider>
        <StudyNanaPanel
          handoff={{ ...handoff, focusKind: "plan", focusId: "chapter-6", focusLabel: "第6章：定义函数" }}
          initialPrompt="请基于知识源，为“第6章：定义函数”整理知识核草稿。"
          onClose={() => undefined}
          onOpenFull={() => undefined}
          loadMessages={async () => ({ messages: [] })}
        />
      </I18nProvider>,
    );

    expect(await screen.findByRole("textbox", { name: "发送消息" })).toHaveValue(
      "请基于知识源，为“第6章：定义函数”整理知识核草稿。",
    );
  });
});
