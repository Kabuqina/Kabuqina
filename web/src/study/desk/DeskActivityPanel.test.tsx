// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { StudyChatHandoff } from "../../lib/studyChatHandoff";
import { bindStudyHandoff } from "../../lib/studyChatHandoff";
import { DeskActivityPanel } from "./DeskActivityPanel";

const getSessions = vi.hoisted(() => vi.fn());
vi.mock("../../chat/chat-api", () => ({
  cmdGetKabuqinaSessions: getSessions,
}));

function handoff(sessionId: string, spaceId: string): StudyChatHandoff {
  return {
    version: 1,
    mode: "study",
    sessionId,
    spaceId,
    spaceTitle: "高等数学",
    focusKind: "quiz_step",
    focusId: "step-1",
    focusLabel: "第 1 步",
    intent: "explain",
    originSurface: "study_desk",
    returnTarget: {
      path: `/study/${spaceId}/practice`,
      fallbackPath: `/study/${spaceId}`,
      focus: "answer",
    },
    revision: 1,
    question: "为什么？",
    prompt: "解释这一步",
    createdAt: "2026-07-24T00:00:00Z",
  };
}

describe("DeskActivityPanel", () => {
  beforeEach(() => localStorage.clear());

  it("shows real Study activity and only Chat sessions bound to this course", async () => {
    bindStudyHandoff(handoff("session-a", "space-a"));
    bindStudyHandoff(handoff("session-b", "space-b"));
    getSessions.mockResolvedValue({
      sessions: [
        { id: "session-a", title: "极限提问", message_count: 4 },
        { id: "session-b", title: "物理提问", message_count: 2 },
        { id: "ordinary", title: "普通聊天", message_count: 8 },
      ],
      total: 3,
    });
    const onOpenChatSession = vi.fn();
    render(
      <DeskActivityPanel
        activities={[{
          id: "activity-a",
          type: "quiz.attempt",
          createdAt: "2026-07-24T08:00:00Z",
        }]}
        spaceId="space-a"
        onOpenChatSession={onOpenChatSession}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("完成了一次练习检查")).toBeInTheDocument();
    const courseChat = await screen.findByRole("button", { name: /极限提问/ });
    expect(screen.queryByText("物理提问")).not.toBeInTheDocument();
    expect(screen.queryByText("普通聊天")).not.toBeInTheDocument();
    fireEvent.click(courseChat);
    expect(onOpenChatSession).toHaveBeenCalledWith("session-a");
  });

  it("offers an explicit retry when the Chat read model is unavailable", async () => {
    getSessions.mockRejectedValue(new Error("offline"));
    render(
      <DeskActivityPanel
        activities={[]}
        spaceId="space-a"
        onClose={vi.fn()}
      />,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("本子对话暂时无法读取");
    fireEvent.click(screen.getByRole("button", { name: "重试" }));
    expect(getSessions).toHaveBeenCalledTimes(2);
  });
});
