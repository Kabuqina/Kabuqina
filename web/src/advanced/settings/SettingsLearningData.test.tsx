// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../../lib/i18n";
import { SettingsLearningData } from "./SettingsLearningData";

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
vi.mock("../../chat/study/study-api", async (importOriginal) => ({
  ...await importOriginal<typeof import("../../chat/study/study-api")>(),
  cmdStudyDataDelete: mocks.dataDelete,
  cmdStudyDataExport: mocks.dataExport,
  cmdStudyDataImport: mocks.dataImport,
  cmdStudyDataImportFile: mocks.dataImportFile,
  cmdStudyMigrationFailuresExport: mocks.migrationFailures,
  cmdStudyMigrationStatus: mocks.migrationStatus,
}));

afterEach(() => vi.clearAllMocks());

describe("SettingsLearningData", () => {
  it("preflights owner data and explains a non-empty import conflict", async () => {
    const user = userEvent.setup();
    mocks.open.mockResolvedValue("C:\\Users\\X13\\Desktop\\backup.json");
    mocks.dataImportFile.mockResolvedValue({ version: 1, spaces: [{ id: "incoming" }] });
    mocks.dataExport.mockResolvedValue({ bundle: { version: 1, spaces: [{ id: "existing" }] } });
    render(<I18nProvider><SettingsLearningData /></I18nProvider>);

    await user.click(screen.getByRole("button", { name: "从备份导入" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("当前学习数据非空，不能覆盖或合并");
    expect(screen.queryByRole("button", { name: "确认导入" })).not.toBeInTheDocument();
    expect(mocks.dataImport).not.toHaveBeenCalled();
  });

  it("only offers confirmation when owner data is empty", async () => {
    const user = userEvent.setup();
    mocks.open.mockResolvedValue("C:\\Users\\X13\\Desktop\\backup.json");
    mocks.dataImportFile.mockResolvedValue({ version: 1, spaces: [{ id: "incoming" }] });
    mocks.dataExport.mockResolvedValue({ bundle: { version: 1, spaces: [] } });
    render(<I18nProvider><SettingsLearningData /></I18nProvider>);

    await user.click(screen.getByRole("button", { name: "从备份导入" }));
    const confirm = await screen.findByRole("button", { name: "确认导入" });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    await user.click(confirm);
    expect(mocks.dataImport).toHaveBeenCalledTimes(1);
  });

  it("keeps permanent deletion behind the exact confirmation phrase", async () => {
    const user = userEvent.setup();
    render(<I18nProvider><SettingsLearningData /></I18nProvider>);

    const button = screen.getByRole("button", { name: "永久删除全部学习数据" });
    expect(button).toBeDisabled();

    const field = screen.getByLabelText(/DELETE ALL LEARNING DATA/);
    await user.type(field, "delete all learning data");
    expect(button).toBeDisabled();

    await user.clear(field);
    await user.type(field, "DELETE ALL LEARNING DATA");
    expect(button).toBeEnabled();

    await user.click(button);
    expect(mocks.dataDelete).toHaveBeenCalledWith("DELETE ALL LEARNING DATA");
  });
});
