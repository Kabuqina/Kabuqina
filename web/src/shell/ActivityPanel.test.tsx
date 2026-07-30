// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ActivityPanel } from "./ActivityPanel";

describe("ActivityPanel", () => {
  it("renders real cross-domain records and returns through bounded targets", async () => {
    const user = userEvent.setup();
    const onReturn = vi.fn();
    render(<ActivityPanel
      open
      onClose={vi.fn()}
      onReturn={onReturn}
      load={vi.fn().mockResolvedValue({
        items: [
          {
            id: "study:tutor:run-1", domain: "study", kind: "tutor", status: "waiting",
            title: "高等数学 · 等待回答", updatedAt: "2026-07-30T08:00:00Z",
            returnTarget: "/study/course-a/learn", fallbackTarget: "/study",
            canResume: true, canRetry: false, targetAvailable: true,
          },
          {
            id: "studio:project:p-1", domain: "studio", kind: "project_scene", status: "recoverable",
            title: "课程讲义", updatedAt: "2026-07-30T07:00:00Z",
            returnTarget: "/studio/p-1", fallbackTarget: "/studio",
            canResume: false, canRetry: false, targetAvailable: true,
          },
        ],
        count: 2,
        limit: 100,
      })}
    />);

    expect(await screen.findByText("高等数学 · 等待回答")).toBeInTheDocument();
    expect(screen.getByText("课程讲义")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "继续" }));
    expect(onReturn).toHaveBeenCalledWith("/study/course-a/learn");
  });

  it("does not expose backend details when the projection fails", async () => {
    render(<ActivityPanel
      open
      onClose={vi.fn()}
      onReturn={vi.fn()}
      load={vi.fn().mockRejectedValue(new Error("private owner_id and sqlite path"))}
    />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("暂时没有读到进行中的现场");
    expect(alert).not.toHaveTextContent("owner_id");
    expect(alert).not.toHaveTextContent("sqlite");
  });
});
