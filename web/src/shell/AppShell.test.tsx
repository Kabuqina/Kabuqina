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

vi.mock("./activityApi", () => ({
  cmdActivityRecords: vi.fn().mockResolvedValue({ items: [], count: 0, limit: 100 }),
}));

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
});

afterEach(() => {
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
  delete document.documentElement.dataset.themeMode;
});

describe("AppShell", () => {
  it("marks Study as the current surface (Studio has been cut)", () => {
    renderShell("/study");
    expect(screen.getByRole("button", { name: "学习" })).toHaveAttribute("aria-current", "page");
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

    for (const group of [".kq-brand-cluster", ".kq-primary-nav", ".kq-utility-nav"]) {
      expect(header.querySelector(group)).toHaveClass("hermes-titlebar-nodrag");
    }
  });

  it("keeps the lamp with the brand and only Study in primary navigation", () => {
    renderShell("/study");
    const header = document.querySelector(".kq-app-header")!;
    const brand = header.querySelector(".kq-brand-cluster")!;
    const primary = header.querySelector(".kq-primary-nav")!;
    const utility = header.querySelector(".kq-utility-nav")!;

    expect(brand).toContainElement(screen.getByRole("button", { name: /台灯|开台灯/ }));
    expect(primary).toContainElement(screen.getByRole("button", { name: "学习" }));
    expect(screen.queryByRole("button", { name: "创作" })).not.toBeInTheDocument();
    expect(primary).not.toContainElement(screen.getByRole("button", { name: "对话" }));
    expect(utility).toContainElement(screen.getByRole("button", { name: "对话" }));
    expect(utility).toContainElement(screen.getByRole("button", { name: "进行中" }));
    expect(utility).toContainElement(screen.getByRole("button", { name: "设置" }));
  });

  it("opens the global Activity panel without navigating away from the current surface", async () => {
    const user = userEvent.setup();
    let asked = 0;
    const stop = onOpenActivityRequest(() => { asked += 1; });
    renderShell("/study");

    await user.click(screen.getByRole("button", { name: "进行中" }));
    expect(asked).toBe(1);
    expect(await screen.findByRole("dialog", { name: "进行中" })).toBeInTheDocument();
    expect(screen.getByText("study surface")).toBeInTheDocument();
    stop();
  });
});
