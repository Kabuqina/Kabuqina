// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../lib/i18n";
import { StudioChatContextBar } from "./StudioChatContextBar";
import { buildStudioChatHandoff } from "../lib/studioChatHandoff";

const HANDOFF = buildStudioChatHandoff({
  id: "p1",
  title: "极限概念分享",
  brief: "讲给没学过极限的同学",
  sources: [{ title: "教材 §2.3" }],
});

function renderBar() {
  const onReturn = vi.fn();
  const onUnbind = vi.fn();
  render(
    <I18nProvider>
      <StudioChatContextBar handoff={HANDOFF} onReturn={onReturn} onUnbind={onUnbind} />
    </I18nProvider>,
  );
  return { onReturn, onUnbind };
}

describe("StudioChatContextBar", () => {
  it("always names the current scope (架构 §8.3)", () => {
    renderBar();
    expect(screen.getByRole("region", { name: "当前项目对话上下文" })).toBeInTheDocument();
    expect(screen.getByText("极限概念分享")).toBeInTheDocument();
  });

  it("offers a way back to the project", async () => {
    const user = userEvent.setup();
    const { onReturn } = renderBar();
    await user.click(screen.getByRole("button", { name: /回到项目/ }));
    expect(onReturn).toHaveBeenCalled();
  });

  it("lets the student drop the scope and keep chatting", async () => {
    const user = userEvent.setup();
    const { onUnbind } = renderBar();
    await user.click(screen.getByRole("button", { name: "转为普通对话" }));
    expect(onUnbind).toHaveBeenCalled();
  });
});
