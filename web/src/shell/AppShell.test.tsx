// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { I18nProvider } from "../lib/i18n";
import { THEME_MODE_KEY } from "../lib/ui-prefs";
import { AppShell } from "./AppShell";
import { onOpenActivityRequest } from "./activityBridge";

function renderShell(initialPath: string) {
  return render(
    <I18nProvider>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/study" element={<p>study surface</p>} />
            <Route path="/studio" element={<p>studio surface</p>} />
            <Route path="/chat" element={<p>chat surface</p>} />
          </Route>
          <Route path="/settings" element={<p>settings surface</p>} />
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
  it("marks the current surface so Study and Studio read as the two destinations", () => {
    renderShell("/studio");
    expect(screen.getByRole("button", { name: "创作" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: "课程" })).not.toHaveAttribute("aria-current");
  });

  it("keeps the shell around every product surface", async () => {
    const user = userEvent.setup();
    renderShell("/study");
    expect(screen.getByText("study surface")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "对话" }));
    expect(screen.getByText("chat surface")).toBeInTheDocument();
    // 换目的地不等于换外壳：页眉一直在。
    expect(screen.getByRole("button", { name: "课程" })).toBeInTheDocument();
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

  it("asks the current surface to open Activity instead of navigating away from it", async () => {
    const user = userEvent.setup();
    let asked = 0;
    const stop = onOpenActivityRequest(() => { asked += 1; });
    renderShell("/study");

    await user.click(screen.getByRole("button", { name: "动态" }));
    expect(asked).toBe(1);
    expect(screen.getByText("study surface")).toBeInTheDocument();
    stop();
  });
});
