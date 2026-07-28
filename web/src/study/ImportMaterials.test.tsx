// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../lib/i18n";
import { ImportMaterials } from "./ImportMaterials";

const mocks = vi.hoisted(() => ({ open: vi.fn(), prefs: vi.fn(), read: vi.fn() }));
vi.mock("@tauri-apps/plugin-dialog", () => ({ open: mocks.open }));
vi.mock("../chat/study/study-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../chat/study/study-api")>()),
  cmdStudyPreferencesGet: mocks.prefs,
  cmdStudyMaterialRead: mocks.read,
}));

afterEach(() => vi.clearAllMocks());

function seed(preferred: "auto" | "precise" | "math" = "auto") {
  mocks.prefs.mockResolvedValue({
    importReadMode: preferred,
    dailyNewCardLimit: 20,
    dailyReviewCardLimit: 100,
    defaults: { importReadMode: "auto", dailyNewCardLimit: 20, dailyReviewCardLimit: 100 },
  });
  mocks.read.mockResolvedValue({
    preferredMode: preferred,
    requestedMode: preferred,
    effectiveMode: preferred,
    limited: false,
    override: false,
    result: {},
  });
}

function renderImport() {
  const onImported = vi.fn();
  render(
    <I18nProvider>
      <ImportMaterials onClose={vi.fn()} onImported={onImported} />
    </I18nProvider>,
  );
  return { onImported };
}

async function pickTwo(user: ReturnType<typeof userEvent.setup>) {
  mocks.open.mockResolvedValue(["C:\\books\\高等数学.pdf", "C:\\books\\习题集.pdf"]);
  await user.click(screen.getByRole("button", { name: /选文件/ }));
  await screen.findByText("高等数学.pdf");
}

describe("ImportMaterials", () => {
  it("says parsing stays on this machine", async () => {
    seed();
    renderImport();
    expect(await screen.findByText(/解析在你电脑上完成，不为了解析上传/)).toBeInTheDocument();
  });

  it("omits requestedMode so the backend applies the saved preference", async () => {
    const user = userEvent.setup();
    seed("auto");
    const { onImported } = renderImport();
    await pickTwo(user);

    await user.click(screen.getByRole("button", { name: /开始读取/ }));
    await waitFor(() => expect(mocks.read).toHaveBeenCalledTimes(2));
    // 没显式选档就不传——别把默认值在前端复制一份。
    expect(mocks.read.mock.calls[0][0]).toEqual({ pathStr: "C:\\books\\高等数学.pdf" });
    await waitFor(() => expect(onImported).toHaveBeenCalled());
  });

  it("warns before running a heavier read than the preference, and only then overrides", async () => {
    const user = userEvent.setup();
    seed("auto");
    renderImport();
    await pickTwo(user);

    await user.selectOptions(screen.getByRole("combobox"), "math");
    // 先说清代价，再让他确认——不静默跑 CPU 推理。
    expect(screen.getByText(/要在本机跑模型/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /确认并开始/ }));

    await waitFor(() => expect(mocks.read).toHaveBeenCalled());
    expect(mocks.read.mock.calls[0][0]).toMatchObject({ requestedMode: "math", overrideLimit: true });
  });

  it("does not warn or override when the choice is not heavier", async () => {
    const user = userEvent.setup();
    seed("math");
    renderImport();
    await pickTwo(user);

    await user.selectOptions(screen.getByRole("combobox"), "auto");
    expect(screen.queryByText(/要在本机跑模型/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /开始读取/ }));
    await waitFor(() => expect(mocks.read).toHaveBeenCalled());
    expect(mocks.read.mock.calls[0][0]).not.toHaveProperty("overrideLimit");
  });

  it("surfaces when the backend capped the read at the preference", async () => {
    const user = userEvent.setup();
    seed("auto");
    mocks.read.mockResolvedValue({
      preferredMode: "auto",
      requestedMode: "math",
      effectiveMode: "auto",
      limited: true,
      override: false,
      result: {},
    });
    renderImport();
    await pickTwo(user);
    await user.click(screen.getByRole("button", { name: /开始读取/ }));
    expect(await screen.findAllByText(/按你的默认档位/)).not.toHaveLength(0);
  });

  it("keeps already-read files when one fails", async () => {
    const user = userEvent.setup();
    seed();
    mocks.read
      .mockResolvedValueOnce({
        preferredMode: "auto", requestedMode: "auto", effectiveMode: "auto",
        limited: false, override: false, result: {},
      })
      .mockRejectedValueOnce(new Error("boom"));
    renderImport();
    await pickTwo(user);
    await user.click(screen.getByRole("button", { name: /开始读取/ }));

    expect(await screen.findByText(/已读入的那些不受影响/)).toBeInTheDocument();
    expect(screen.getByText("这份没读成功")).toBeInTheDocument();
  });

  it("points at the alignment step once two are in", async () => {
    const user = userEvent.setup();
    seed();
    renderImport();
    await pickTwo(user);
    await user.click(screen.getByRole("button", { name: /开始读取/ }));
    expect(await screen.findByText(/小娜会先提出怎么分课/)).toBeInTheDocument();
  });
});
