// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useState } from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../../lib/i18n";
import { answerConfirm, getConfirmSnapshot } from "../../lib/confirmDialog";
import { SettingsLlmConfig } from "./SettingsLlmConfig";

const { invokeMock } = vi.hoisted(() => ({ invokeMock: vi.fn() }));

vi.mock("@tauri-apps/api/core", () => ({
  invoke: invokeMock,
}));

vi.mock("../../components/LlmConfigEditor", () => ({
  LlmConfigEditor: () => <div data-testid="llm-config-editor" />,
}));

function Harness() {
  const [hasSecret, setHasSecret] = useState(true);
  return (
    <I18nProvider>
      <SettingsLlmConfig
        hasSecret={hasSecret}
        onCredentialChanged={() => setHasSecret(false)}
      />
    </I18nProvider>
  );
}

afterEach(() => {
  if (getConfirmSnapshot()) answerConfirm(false);
  invokeMock.mockReset();
});

describe("SettingsLlmConfig credential clearing", () => {
  it("requires confirmation, invokes clear, and refreshes the configured state", async () => {
    const user = userEvent.setup();
    invokeMock.mockResolvedValue(undefined);
    render(<Harness />);

    const clearButton = screen.getByRole("button", { name: "清除已保存凭据" });
    await user.click(clearButton);
    expect(getConfirmSnapshot()).toMatchObject({
      title: "清除已保存的 API Key？",
      tone: "danger",
    });

    await act(async () => answerConfirm(false));
    expect(invokeMock).not.toHaveBeenCalled();

    await user.click(clearButton);
    await act(async () => answerConfirm(true));

    await waitFor(() => expect(invokeMock).toHaveBeenCalledWith("cmd_clear_secret"));
    expect(screen.queryByRole("button", { name: "清除已保存凭据" })).not.toBeInTheDocument();
    expect(screen.getByText("凭据已清除，本机助手正在重启。")).toBeVisible();
  });

  it("keeps the clear action available when the command fails", async () => {
    const user = userEvent.setup();
    invokeMock.mockRejectedValue(new Error("vault unavailable"));
    render(<Harness />);

    await user.click(screen.getByRole("button", { name: "清除已保存凭据" }));
    await act(async () => answerConfirm(true));

    expect(await screen.findByRole("alert")).toHaveTextContent("vault unavailable");
    expect(screen.getByRole("button", { name: "清除已保存凭据" })).toBeEnabled();
  });
});
