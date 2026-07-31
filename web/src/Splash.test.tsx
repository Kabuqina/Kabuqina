// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { I18nProvider } from "./lib/i18n";
import { Splash } from "./Splash";
import { Wizard } from "./onboarding/Wizard";
import { getNextPathAfterPass } from "./onboarding/flowConfig";

const mocks = vi.hoisted(() => ({
  invoke: vi.fn(),
  waitForReadiness: vi.fn(),
}));

vi.mock("@tauri-apps/api/core", () => ({ invoke: mocks.invoke }));
vi.mock("./chat/kabuqinaReadinessPoll", () => ({
  waitForKabuqinaReadiness: mocks.waitForReadiness,
}));

function destination(name: string) {
  return <div data-testid="destination">{name}</div>;
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  mocks.invoke.mockReset();
  mocks.waitForReadiness.mockReset();
  mocks.waitForReadiness.mockResolvedValue({});
});

describe("startup destination", () => {
  it("opens Study after normal startup when a saved key exists", async () => {
    mocks.invoke.mockResolvedValue(true);
    render(
      <I18nProvider>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route path="/" element={<Splash />} />
            <Route path="/study" element={destination("study")} />
            <Route path="/onboarding/*" element={destination("onboarding")} />
          </Routes>
        </MemoryRouter>
      </I18nProvider>,
    );

    expect(await screen.findByTestId("destination")).toHaveTextContent("study");
    expect(mocks.waitForReadiness).toHaveBeenCalledOnce();
  });

  it("sends first launch without a key to onboarding", async () => {
    mocks.invoke.mockResolvedValue(false);
    render(
      <I18nProvider>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route path="/" element={<Splash />} />
            <Route path="/study" element={destination("study")} />
            <Route path="/onboarding/*" element={destination("onboarding")} />
          </Routes>
        </MemoryRouter>
      </I18nProvider>,
    );

    expect(await screen.findByTestId("destination")).toHaveTextContent("onboarding");
    expect(mocks.waitForReadiness).not.toHaveBeenCalled();
  });

  it("finishes onboarding on Study through the shared completion route", async () => {
    sessionStorage.setItem("kabuqina.onboarding.draft", JSON.stringify({ setupMode: "quick" }));
    render(
      <I18nProvider>
        <MemoryRouter initialEntries={["/onboarding/done"]}>
          <Routes>
            <Route path="/onboarding/*" element={<Wizard />} />
            <Route path="/study" element={destination("study")} />
          </Routes>
        </MemoryRouter>
      </I18nProvider>,
    );

    expect(await screen.findByTestId("destination")).toHaveTextContent("study");
  });

  it("routes the last pass step through onboarding completion", () => {
    expect(getNextPathAfterPass("quick")).toBe("/onboarding/done");
  });
});
