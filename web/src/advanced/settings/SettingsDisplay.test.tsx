// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../../lib/i18n";
import { SettingsDisplay } from "./SettingsDisplay";

const mocks = vi.hoisted(() => ({ invoke: vi.fn(), open: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: mocks.invoke }));
vi.mock("@tauri-apps/plugin-dialog", () => ({ open: mocks.open }));

afterEach(() => vi.clearAllMocks());

function renderDisplay() {
  return render(
    <I18nProvider>
      <SettingsDisplay
        fontSize="medium"
        onSetFontSize={vi.fn()}
        themeMode="system"
        onSetThemeMode={vi.fn()}
      />
    </I18nProvider>,
  );
}

describe("SettingsDisplay", () => {
  /** 这一面只管「看起来怎么样」：字体、主题、语言、桌面宠物外观。 */
  it("carries the four appearance sections", () => {
    renderDisplay();
    for (const title of ["界面字体", "外观主题", "显示语言", "桌面宠物外观"]) {
      expect(screen.getByText(title)).toBeInTheDocument();
    }
  });

  /**
   * MVP 简化时工作区整块从设置页撤走了（`d10127d9`），不是搬到别的标签页——
   * 现在整个 `advanced/` 下都没有第二处入口。钉住它不会悄悄回来。
   */
  it("no longer carries the workspace block", () => {
    renderDisplay();
    expect(screen.queryByRole("button", { name: "打开文件夹" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /选择工作区/ })).not.toBeInTheDocument();
  });

  it("no longer renders a power-mode switch", () => {
    renderDisplay();
    expect(screen.queryByText("高级用户")).not.toBeInTheDocument();
  });
});
