// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { answerConfirm, getConfirmSnapshot } from "../../lib/confirmDialog";
import { I18nProvider } from "../../lib/i18n";
import { SettingsLegacyChannels } from "./SettingsLegacyChannels";

const { invokeMock } = vi.hoisted(() => ({ invokeMock: vi.fn() }));

vi.mock("@tauri-apps/api/core", () => ({
  invoke: invokeMock,
}));

const inventory = {
  contractVersion: "kabuqina.legacy-channel-upgrade/v1",
  sourceHomePath: "C:\\Kabuqina\\kabuqina-home",
  canonicalHomePresent: true,
  legacyHomePresent: false,
  removedEnvKeys: ["DISCORD_BOT_TOKEN"],
  qqLegacyHomeKeys: [],
  exactFilePaths: ["C:\\Kabuqina\\kabuqina-home\\discord_threads.json"],
  protectedDirectoryPaths: [],
  removedConfigPlatforms: [],
  removedChannelPlatforms: [],
  legacyJobs: [],
  legacySessionOrigins: 0,
  totalCleanupItems: 2,
};

const exported = {
  exportId: "a".repeat(64),
  path: "C:\\Kabuqina\\legacy-channel-exports\\export.json",
  exportedFiles: 2,
  skippedOversizeFiles: [],
};

function renderSection() {
  return render(
    <I18nProvider>
      <SettingsLegacyChannels />
    </I18nProvider>,
  );
}

afterEach(() => {
  if (getConfirmSnapshot()) answerConfirm(false);
  invokeMock.mockReset();
});

describe("SettingsLegacyChannels", () => {
  it("requires export and confirmation before cleanup, then refreshes inventory", async () => {
    const user = userEvent.setup();
    let inventoryCalls = 0;
    invokeMock.mockImplementation(async (command: string, args?: unknown) => {
      if (command === "cmd_legacy_channel_inventory") {
        inventoryCalls += 1;
        return inventoryCalls === 1
          ? inventory
          : { ...inventory, removedEnvKeys: [], exactFilePaths: [], totalCleanupItems: 0 };
      }
      if (command === "cmd_legacy_channel_export") return exported;
      if (command === "cmd_legacy_channel_cleanup") {
        expect(args).toEqual({
          exportId: exported.exportId,
          confirmation: "REMOVE_LEGACY_CHANNEL_DATA",
        });
        return {
          removedEnvKeys: 1,
          migratedQqHomeKeys: 0,
          removedFiles: 1,
          removedConfigPlatforms: 0,
          removedChannelPlatforms: 0,
          retainedLegacyJobs: 0,
          retainedLegacySessionOrigins: 0,
          remainingCleanupItems: 0,
        };
      }
      throw new Error(`unexpected command: ${command}`);
    });
    renderSection();

    const cleanupButton = await screen.findByRole("button", { name: "清理列举项" });
    expect(cleanupButton).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "先导出备份" }));
    await screen.findByText("已验证导出 2 个文件。");
    expect(cleanupButton).toBeEnabled();

    await user.click(cleanupButton);
    expect(getConfirmSnapshot()).toMatchObject({
      title: "清理旧渠道数据？",
      tone: "danger",
    });
    await act(async () => answerConfirm(false));
    expect(invokeMock).not.toHaveBeenCalledWith(
      "cmd_legacy_channel_cleanup",
      expect.anything(),
    );
    expect(cleanupButton).toBeEnabled();

    await user.click(cleanupButton);
    await act(async () => answerConfirm(true));

    await waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith("cmd_legacy_channel_cleanup", {
        exportId: exported.exportId,
        confirmation: "REMOVE_LEGACY_CHANNEL_DATA",
      }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent("已清理 2 个列举项");
    await waitFor(() => expect(inventoryCalls).toBe(2));
    expect(cleanupButton).toBeDisabled();
  });

  it("keeps cleanup disabled when export fails", async () => {
    const user = userEvent.setup();
    invokeMock.mockImplementation(async (command: string) => {
      if (command === "cmd_legacy_channel_inventory") return inventory;
      if (command === "cmd_legacy_channel_export") throw new Error("export unavailable");
      throw new Error(`unexpected command: ${command}`);
    });
    renderSection();

    await user.click(await screen.findByRole("button", { name: "先导出备份" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("export unavailable");
    expect(screen.getByRole("button", { name: "清理列举项" })).toBeDisabled();
    expect(invokeMock).not.toHaveBeenCalledWith(
      "cmd_legacy_channel_cleanup",
      expect.anything(),
    );
  });

  it("invalidates the verified export after a TOCTOU rejection", async () => {
    const user = userEvent.setup();
    invokeMock.mockImplementation(async (command: string) => {
      if (command === "cmd_legacy_channel_inventory") return inventory;
      if (command === "cmd_legacy_channel_export") return exported;
      if (command === "cmd_legacy_channel_cleanup") {
        throw new Error("legacy data changed after export; export again before cleanup");
      }
      throw new Error(`unexpected command: ${command}`);
    });
    renderSection();

    await user.click(await screen.findByRole("button", { name: "先导出备份" }));
    const cleanupButton = await screen.findByRole("button", { name: "清理列举项" });
    await waitFor(() => expect(cleanupButton).toBeEnabled());
    await user.click(cleanupButton);
    await act(async () => answerConfirm(true));

    expect(await screen.findByRole("alert")).toHaveTextContent("changed after export");
    expect(screen.queryByText(exported.path)).not.toBeInTheDocument();
    expect(cleanupButton).toBeDisabled();
  });
});
