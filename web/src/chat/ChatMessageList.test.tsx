// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../lib/i18n";
import { ChatMessageList } from "./ChatMessageList";

const messages = [{ id: "user-1", role: "user" as const, text: "请安排计划" }];

describe("ChatMessageList agent interactions", () => {
  it("renders an answer field for an open-ended clarification", async () => {
    const user = userEvent.setup();
    const respond = vi.fn().mockResolvedValue(undefined);
    render(<I18nProvider><ChatMessageList
      messages={messages}
      pendingInteraction={{
        id: "question-1",
        sessionId: "session-1",
        kind: "text",
        question: "你的学习目标和时间安排是怎样的？",
        choices: [],
      }}
      onRespondInteraction={respond}
    /></I18nProvider>);

    await user.type(screen.getByRole("textbox", { name: "你的学习目标和时间安排是怎样的？" }), "每天半小时，先打好基础");
    await user.click(screen.getByRole("button", { name: "提交回答" }));

    expect(respond).toHaveBeenCalledWith("submit", "每天半小时，先打好基础");
  });

  it("renders the supplied choices and a free-form alternative", async () => {
    const user = userEvent.setup();
    const respond = vi.fn().mockResolvedValue(undefined);
    render(<I18nProvider><ChatMessageList
      messages={messages}
      pendingInteraction={{
        id: "question-2",
        sessionId: "session-1",
        kind: "choice",
        question: "你更希望先学哪部分？",
        choices: ["基础语法", "面向对象"],
      }}
      onRespondInteraction={respond}
    /></I18nProvider>);

    await user.click(screen.getByRole("button", { name: "面向对象" }));
    expect(respond).toHaveBeenCalledWith("submit", "面向对象");
  });
});
