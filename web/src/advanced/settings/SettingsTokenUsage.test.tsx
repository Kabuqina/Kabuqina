// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../../lib/i18n";
import { SettingsTokenUsage } from "./SettingsTokenUsage";
import type { StudyTokenUsageResponse } from "../../chat/study/study-api";

const mocks = vi.hoisted(() => ({ usage: vi.fn() }));
vi.mock("../../chat/study/study-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../chat/study/study-api")>()),
  cmdStudyTokenUsage: mocks.usage,
}));

afterEach(() => vi.clearAllMocks());

const metrics = (over: Partial<StudyTokenUsageResponse["totals"]> = {}) => ({
  inputTokens: 0,
  outputTokens: 0,
  totalTokens: 0,
  succeededAttempts: 0,
  inputMeasuredAttempts: 0,
  outputMeasuredAttempts: 0,
  incomplete: false,
  ...over,
});

const RESPONSE: StudyTokenUsageResponse = {
  window: "week",
  startsAt: "2026-07-20T00:00:00Z",
  endsAt: "2026-07-27T00:00:00Z",
  totals: metrics({
    inputTokens: 120_000,
    outputTokens: 34_500,
    totalTokens: 154_500,
    succeededAttempts: 42,
    inputMeasuredAttempts: 42,
    outputMeasuredAttempts: 42,
  }),
  courses: [
    {
      ...metrics({ inputTokens: 100_000, outputTokens: 30_000, totalTokens: 130_000, succeededAttempts: 30 }),
      spaceId: "math",
      title: "高等数学",
      models: [
        {
          ...metrics({ inputTokens: 100_000, outputTokens: 30_000, totalTokens: 130_000, succeededAttempts: 30 }),
          providerId: "deepseek",
          modelId: "deepseek-v4-flash",
        },
      ],
    },
  ],
};

function renderUsage() {
  render(
    <I18nProvider>
      <SettingsTokenUsage />
    </I18nProvider>,
  );
}

describe("SettingsTokenUsage", () => {
  it("reports tokens and never converts them to money", async () => {
    mocks.usage.mockResolvedValue(RESPONSE);
    renderUsage();

    expect(await screen.findByText("154,500")).toBeInTheDocument();
    expect(screen.getByText("高等数学")).toBeInTheDocument();
    expect(screen.getByText("deepseek-v4-flash")).toBeInTheDocument();
    // owner 定：只报 token，不折算金额。
    expect(screen.queryByText(/[¥$]|元|美元|费用|花费/)).not.toBeInTheDocument();
  });

  it("switches the window and asks the backend again", async () => {
    const user = userEvent.setup();
    mocks.usage.mockResolvedValue(RESPONSE);
    renderUsage();
    await screen.findByText("154,500");
    expect(mocks.usage).toHaveBeenCalledWith("week");

    await user.click(screen.getByRole("tab", { name: "本月" }));
    await waitFor(() => expect(mocks.usage).toHaveBeenCalledWith("month"));
  });

  it("says the number is a floor when some calls did not report counts", async () => {
    mocks.usage.mockResolvedValue({
      ...RESPONSE,
      totals: { ...RESPONSE.totals, incomplete: true, inputMeasuredAttempts: 40 },
    });
    renderUsage();
    // 默默少报和报假精度是同一种不诚实。
    expect(await screen.findByText(/实际用量的下限/)).toBeInTheDocument();
  });

  it("stays quiet about the floor when every call reported", async () => {
    mocks.usage.mockResolvedValue(RESPONSE);
    renderUsage();
    await screen.findByText("154,500");
    expect(screen.queryByText(/实际用量的下限/)).not.toBeInTheDocument();
  });

  it("shows an empty period instead of a zero that looks like a total", async () => {
    mocks.usage.mockResolvedValue({ ...RESPONSE, totals: metrics(), courses: [] });
    renderUsage();
    expect(await screen.findByText("这段时间还没有用量。")).toBeInTheDocument();
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("degrades to a plain notice when usage cannot be read", async () => {
    mocks.usage.mockRejectedValue(new Error("no backend"));
    renderUsage();
    expect(await screen.findByText("现在读不到用量数据。")).toBeInTheDocument();
  });
});
