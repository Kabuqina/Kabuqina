// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../lib/i18n";
import { THEME_MODE_KEY } from "../lib/ui-prefs";
import { AppShell } from "./AppShell";
import { onOpenActivityRequest } from "./activityBridge";
import { cmdActivityRecords } from "./activityApi";

vi.mock("./activityApi", () => ({
  cmdActivityRecords: vi.fn(),
}));

const mockRecords = vi.mocked(cmdActivityRecords);

// 一条「还活着」的学习现场：进行中角标就是靠这种记录点亮的。
const liveRecord = {
  id: "study:tutor:run-1", domain: "study", kind: "tutor", status: "waiting",
  title: "高等数学 · 等待回答", updatedAt: "2026-07-30T08:00:00Z",
  returnTarget: "/study/course-a/learn", fallbackTarget: "/study",
  canResume: true, canRetry: false, targetAvailable: true,
} as const;

function renderShell(initialPath: string) {
  return render(
    <I18nProvider>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/study" element={<p>study surface</p>} />
            <Route path="/chat" element={<p>chat surface</p>} />
            <Route path="/settings" element={<p>settings surface</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </I18nProvider>,
  );
}

beforeEach(() => {
  window.localStorage.setItem(THEME_MODE_KEY, "light");
  // 缺省：没有活着的现场，进行中按钮不该出现。个别用例再覆盖成有活儿。
  mockRecords.mockReset().mockResolvedValue({ items: [], count: 0, limit: 100 });
});

afterEach(() => {
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
  delete document.documentElement.dataset.themeMode;
});

describe("AppShell", () => {
  it("keeps Study as the only first-class destination (Studio has been cut)", () => {
    renderShell("/study");
    // 主界面上右上给的是「去 Chat」的门；「学习」只在 Chat 面上作为回 Study 的门出现。
    expect(screen.getByRole("button", { name: "对话" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "学习" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "创作" })).not.toBeInTheDocument();
  });

  it("keeps the shell around every product surface", async () => {
    const user = userEvent.setup();
    renderShell("/study");
    expect(screen.getByText("study surface")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "对话" }));
    expect(screen.getByText("chat surface")).toBeInTheDocument();
    // 换目的地不等于换外壳：页眉一直在。
    expect(screen.getByRole("button", { name: "学习" })).toBeInTheDocument();
  });

  it("keeps Settings inside the shell and marks its utility entry", () => {
    renderShell("/settings");
    expect(screen.getByText("settings surface")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "设置" })).toHaveAttribute("aria-current", "page");
    expect(document.querySelector(".kq-app-header")).toBeInTheDocument();
  });

  /**
   * 台灯是开关不是三档选择器。回归钉子：副作用一旦写进 state updater，
   * StrictMode 下会跑两次，结果是 DOM 翻了而灯没亮。
   */
  it("toggles the lamp between day and night, and says which it is", async () => {
    const user = userEvent.setup();
    renderShell("/study");
    const lamp = () => screen.getByRole("button", { name: /台灯|开台灯/ });

    expect(lamp()).toHaveAttribute("aria-pressed", "false");
    await user.click(lamp());

    await waitFor(() => expect(lamp()).toHaveAttribute("aria-pressed", "true"));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(window.localStorage.getItem(THEME_MODE_KEY)).toBe("dark");

    await user.click(lamp());
    await waitFor(() => expect(lamp()).toHaveAttribute("aria-pressed", "false"));
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  /**
   * 全窗口只有一条横条：产品面上这条页眉**就是**标题栏，所以它必须是拖拽区，
   * 而里面每个能点的东西都得是 no-drag——否则点导航会变成拖窗口。
   */
  it("is the title bar on product surfaces: draggable, with its controls exempt", () => {
    renderShell("/study");
    const header = document.querySelector(".kq-app-header")!;
    expect(header).toHaveAttribute("data-tauri-drag-region");
    expect(header).toHaveClass("hermes-titlebar-drag");

    for (const group of [".kq-left-cluster", ".kq-brand-lockup", ".kq-utility-nav"]) {
      expect(header.querySelector(group)).toHaveClass("hermes-titlebar-nodrag");
    }
  });

  it("keeps the lamp and chat on the left with the brand centered", () => {
    renderShell("/study");
    const header = document.querySelector(".kq-app-header")!;
    const left = header.querySelector(".kq-left-cluster")!;
    const brand = header.querySelector(".kq-brand-lockup")!;
    const utility = header.querySelector(".kq-utility-nav")!;

    expect(left).toContainElement(screen.getByRole("button", { name: /台灯|开台灯/ }));
    // /study 表面上，左侧第一颗工具钮是「去 Chat」的门。
    expect(left).toContainElement(screen.getByRole("button", { name: "对话" }));
    expect(brand).toHaveTextContent("卡布奇娜");
    expect(screen.queryByRole("button", { name: "创作" })).not.toBeInTheDocument();
    expect(utility).toContainElement(screen.getByRole("button", { name: "设置" }));
  });

  /**
   * v0.5.0 降权：Activity 缩成一个多数时间为空的「接续现场」托盘，不再常驻顶栏。
   * 没有活着的现场时，进行中这颗按钮根本不渲染——零占用。
   */
  it("hides the Activity entry when there is no live study work", async () => {
    renderShell("/study");
    // 等一次拉取落地（缺省 mock 是空的），确认按钮始终没出现。
    await waitFor(() => expect(mockRecords).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: "进行中" })).not.toBeInTheDocument();
  });

  it("surfaces the Activity entry with a count only when work is live", async () => {
    mockRecords.mockResolvedValue({ items: [liveRecord], count: 1, limit: 100 });
    renderShell("/study");

    const entry = await screen.findByRole("button", { name: "进行中" });
    expect(entry).toHaveTextContent("1");
  });

  it("opens the global Activity panel without navigating away from the current surface", async () => {
    mockRecords.mockResolvedValue({ items: [liveRecord], count: 1, limit: 100 });
    const user = userEvent.setup();
    let asked = 0;
    const stop = onOpenActivityRequest(() => { asked += 1; });
    renderShell("/study");

    await user.click(await screen.findByRole("button", { name: "进行中" }));
    expect(asked).toBe(1);
    expect(await screen.findByRole("dialog", { name: "进行中" })).toBeInTheDocument();
    expect(screen.getByText("study surface")).toBeInTheDocument();
    stop();
  });
});
