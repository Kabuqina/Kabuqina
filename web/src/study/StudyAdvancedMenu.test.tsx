// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../lib/i18n";
import { StudyAdvancedMenu } from "./StudyAdvancedMenu";

const mocks = vi.hoisted(() => ({
  open: vi.fn(),
  save: vi.fn(),
  invoke: vi.fn(),
  dataDelete: vi.fn(),
  dataExport: vi.fn(),
  dataImport: vi.fn(),
  dataImportFile: vi.fn(),
  migrationFailures: vi.fn(),
  migrationStatus: vi.fn(),
}));

vi.mock("@tauri-apps/plugin-dialog", () => ({ open: mocks.open, save: mocks.save }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: mocks.invoke }));
vi.mock("../chat/study/study-api", async (importOriginal) => ({
  ...await importOriginal<typeof import("../chat/study/study-api")>(),
  cmdStudyDataDelete: mocks.dataDelete,
  cmdStudyDataExport: mocks.dataExport,
  cmdStudyDataImport: mocks.dataImport,
  cmdStudyDataImportFile: mocks.dataImportFile,
  cmdStudyMigrationFailuresExport: mocks.migrationFailures,
  cmdStudyMigrationStatus: mocks.migrationStatus,
}));

afterEach(() => vi.clearAllMocks());

describe("StudyAdvancedMenu", () => {
  it("traps focus, closes on Escape, and restores the trigger", async () => {
    const user = userEvent.setup();
    render(<I18nProvider><StudyAdvancedMenu onOwnerDataReset={vi.fn()} /></I18nProvider>);
    const trigger = screen.getByRole("button", { name: "学习数据" });
    await user.click(trigger);
    const close = screen.getByRole("button", { name: "关闭" });
    expect(close).toHaveFocus();

    await user.tab({ shift: true });
    expect(screen.getByLabelText(/DELETE ALL LEARNING DATA/)).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "学习数据" })).not.toBeInTheDocument();
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("preflights owner data and explains a non-empty import conflict", async () => {
    const user = userEvent.setup();
    mocks.open.mockResolvedValue("C:\\Users\\X13\\Desktop\\backup.json");
    mocks.dataImportFile.mockResolvedValue({ version: 1, spaces: [{ id: "incoming" }] });
    mocks.dataExport.mockResolvedValue({ bundle: { version: 1, spaces: [{ id: "existing" }] } });
    render(<I18nProvider><StudyAdvancedMenu onOwnerDataReset={vi.fn()} /></I18nProvider>);

    await user.click(screen.getByRole("button", { name: "学习数据" }));
    await user.click(screen.getByRole("button", { name: "从备份导入" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("当前学习数据非空，不能覆盖或合并");
    expect(screen.queryByRole("button", { name: "确认导入" })).not.toBeInTheDocument();
    expect(mocks.dataImport).not.toHaveBeenCalled();
  });
});
