// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../lib/i18n";
import { ART_ASSETS } from "../lib/artAssets";
import { THEME_MODE_KEY } from "../lib/ui-prefs";
import { AppShell } from "./AppShell";
import { requestOpenActivity } from "./activityBridge";
import { cmdActivityRecords } from "./activityApi";

vi.mock("./activityApi", () => ({
  cmdActivityRecords: vi.fn(),
}));

const mockRecords = vi.mocked(cmdActivityRecords);

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
  // 面板打开时会去拉一次记录，给它一个空结果。
  mockRecords.mockReset().mockResolvedValue({ items: [], count: 0, limit: 100 });
});

afterEach(() => {
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
  delete document.documentElement.dataset.themeMode;
});

describe("AppShell", () => {
  it("keeps both destinations on the bar and marks the current one", () => {
    renderShell("/study");
    // 设计稿 5：自习与对话始终都在，当前那个是木头上的一小片纸。
    expect(screen.getByRole("button", { name: "学习" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: "对话" })).not.toHaveAttribute("aria-current");
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

  it("swaps the wordmark for its night ink when the lamp goes on", async () => {
    const user = userEvent.setup();
    renderShell("/study");
    const wordmark = () => document.querySelector("img.kq-brand-name")!;
    // 字标的墨色是烘在图里的，所以换的是文件——套 filter 会把注册字形的边缘弄脏。
    expect(wordmark()).toHaveAttribute("src", ART_ASSETS.wordmark);

    await user.click(screen.getByRole("button", { name: /台灯|开台灯/ }));
    await waitFor(() => expect(wordmark()).toHaveAttribute("src", ART_ASSETS.wordmarkNight));
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
    expect(left).toContainElement(screen.getByRole("button", { name: "学习" }));
    expect(left).toContainElement(screen.getByRole("button", { name: "对话" }));
    // 正中那件是注册字标的位图（alt 是「卡布Qi娜」，不是产品名「卡布奇娜」），
    // 不是用系统字体拼出来的文字——拼出来的 Qi 字面和墨色都对不上注册字形。
    expect(brand.querySelector("img.kq-brand-name")).toHaveAttribute("alt", "卡布Qi娜");
    expect(brand).not.toHaveTextContent("卡布");
    expect(screen.queryByRole("button", { name: "创作" })).not.toBeInTheDocument();
    expect(utility).toContainElement(screen.getByRole("button", { name: "设置" }));
  });

  /**
   * 设计稿 5：横条上不该有第二处会跳数字的东西，所以「进行中」连同它的计数角标
   * 从横条撤走，入口搬进 Chat 的抽屉。面板本身仍然由外壳持有。
   */
  it("no longer carries the Activity entry on the bar", () => {
    renderShell("/study");
    expect(screen.queryByRole("button", { name: "进行中" })).not.toBeInTheDocument();
  });

  it("still owns the Activity panel, opened through the shared bridge", async () => {
    renderShell("/study");
    // 抽屉里那颗按钮走的就是这条桥。
    requestOpenActivity();
    expect(await screen.findByRole("dialog", { name: "进行中" })).toBeInTheDocument();
    expect(screen.getByText("study surface")).toBeInTheDocument();
  });
});
