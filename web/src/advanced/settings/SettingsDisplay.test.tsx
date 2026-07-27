// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../../lib/i18n";
import { SettingsDisplay } from "./SettingsDisplay";

const mocks = vi.hoisted(() => ({ invoke: vi.fn(), open: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: mocks.invoke }));
vi.mock("@tauri-apps/plugin-dialog", () => ({ open: mocks.open }));

afterEach(() => vi.clearAllMocks());

const STATUS = { workspace: "C:\\Users\\X13\\kabuqina-home", hasSecret: true, pythonRunning: true };

function renderDisplay() {
  return render(
    <I18nProvider>
      <SettingsDisplay
        status={STATUS}
        fontSize="medium"
        onSetFontSize={vi.fn()}
        themeMode="system"
        onSetThemeMode={vi.fn()}
        onWorkspaceChanged={vi.fn()}
      />
    </I18nProvider>,
  );
}

describe("SettingsDisplay", () => {
  // v0.5.0 起不再分权限层（owner 2026-07-27）：工作区的全部控件对所有人常驻。
  it("shows the workspace path, folder button and change controls to everyone", () => {
    renderDisplay();
    // 「恢复默认」在这一页出现两次（桌面宠物一个、工作区一个），所以按区块取。
    const workspace = screen.getByText(STATUS.workspace).closest("section");
    expect(workspace).not.toBeNull();
    const inWorkspace = within(workspace as HTMLElement);
    expect(inWorkspace.getByRole("button", { name: "打开文件夹" })).toBeInTheDocument();
    expect(inWorkspace.getByRole("button", { name: /选择工作区/ })).toBeInTheDocument();
    expect(inWorkspace.getByRole("button", { name: /恢复默认/ })).toBeInTheDocument();
  });

  it("no longer renders a power-mode switch", () => {
    renderDisplay();
    expect(screen.queryByText("高级用户")).not.toBeInTheDocument();
  });
});
