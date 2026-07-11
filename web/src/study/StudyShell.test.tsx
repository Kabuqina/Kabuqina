// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../lib/i18n";
import type { StudyRepository } from "./repository";
import { StudyRepositoryProvider } from "./repositoryContext";
import { StudyShell } from "./StudyShell";

const spaces = {
  currentSpaceId: "space-a",
  spaces: [
    { id: "space-a", title: "Linear Algebra", status: "active", isCurrent: true },
    { id: "space-b", title: "Physics", status: "active", isCurrent: false },
  ],
};

function Location() { return <output data-testid="location">{useLocation().pathname}</output>; }

function renderShell(
  repositoryOverrides: Partial<StudyRepository> = {},
  { spaceId = "space-a", page = "learn" }: {
    spaceId?: string;
    page?: "flyleaf" | "plan" | "learn" | "practice" | "evaluate";
  } = {},
) {
  const repository: StudyRepository = {
    listSpaces: vi.fn().mockResolvedValue(spaces),
    selectSpace: vi.fn().mockResolvedValue({ ...spaces, currentSpaceId: "space-b" }),
    listDrafts: vi.fn().mockResolvedValue({
      total: 2,
      kindCounts: { flashcard_deck: 1, quiz: 1 },
    }),
    loadFlyleaf: vi.fn(),
    migrateLegacyContext: vi.fn(),
    setArtifactStatus: vi.fn(),
    loadPlan: vi.fn(),
    completePlanItem: vi.fn(),
    skipPlanItem: vi.fn(),
    loadWrongbook: vi.fn(),
    loadLatestEvaluation: vi.fn(),
    loadActivities: vi.fn(),
    ...repositoryOverrides,
  };
  render(
    <I18nProvider>
      <StudyRepositoryProvider repository={repository}>
        <MemoryRouter initialEntries={[`/study/${spaceId}/${page}`]}>
          <Location />
          <StudyShell spaces={spaces} spaceId={spaceId} page={page} />
        </MemoryRouter>
      </StudyRepositoryProvider>
    </I18nProvider>,
  );
  return repository;
}

afterEach(() => vi.unstubAllGlobals());

describe("StudyShell", () => {
  it("renders lifecycle links and privacy-bounded cross-kind draft counts", async () => {
    const user = userEvent.setup();
    renderShell();
    expect(screen.getByRole("navigation", { name: "学习阶段" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "学习" })).toHaveAttribute("aria-current", "page");
    const drafts = await screen.findByLabelText("2 个草稿");
    await user.click(drafts.closest("button")!);
    const popover = screen.getByRole("dialog", { name: "草稿箱" });
    expect(popover).toHaveTextContent("flashcard deck");
    expect(popover).toHaveTextContent("quiz");
    expect(popover).not.toHaveTextContent("private");
  });

  it("uses the URL space for drafts when it differs from the backend current space", async () => {
    const listDrafts = vi.fn().mockResolvedValue({
      total: 1,
      kindCounts: { quiz: 1 },
    });
    renderShell({ listDrafts }, { spaceId: "space-b" });

    await screen.findByLabelText("1 个草稿");
    expect(listDrafts).toHaveBeenCalledWith("space-b", expect.any(AbortSignal));
  });

  it("keeps route and data when selecting a space fails", async () => {
    const user = userEvent.setup();
    renderShell({ selectSpace: vi.fn().mockRejectedValue(new Error("request_failed")) });
    await user.click(screen.getByRole("button", { name: /Linear Algebra/ }));
    await user.click(screen.getByRole("option", { name: "Physics" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("原学习空间已保留");
    expect(screen.getByTestId("location")).toHaveTextContent("/study/space-a/learn");
    expect(screen.getByRole("heading", { name: "学习" })).toBeInTheDocument();
  });

  it("moves to the selected space while preserving the current lifecycle page", async () => {
    const user = userEvent.setup();
    const repository = renderShell();
    await user.click(screen.getByRole("button", { name: /Linear Algebra/ }));
    await user.click(screen.getByRole("option", { name: "Physics" }));
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/study/space-b/learn"));
    expect(repository.selectSpace).toHaveBeenCalledWith("space-b", expect.any(AbortSignal));
  });

  it("uses a modal presentation in a narrow container and restores trigger focus on Escape", async () => {
    class NarrowResizeObserver {
      constructor(private callback: ResizeObserverCallback) {}
      observe() { this.callback([{ contentRect: { width: 480 } } as ResizeObserverEntry], this as unknown as ResizeObserver); }
      disconnect() {}
      unobserve() {}
    }
    vi.stubGlobal("ResizeObserver", NarrowResizeObserver);
    const user = userEvent.setup();
    renderShell();
    const trigger = screen.getByRole("button", { name: /Linear Algebra/ });
    await user.click(trigger);
    expect(screen.getByRole("dialog", { name: "切换学习空间" })).toHaveAttribute("aria-modal", "true");
    const close = screen.getByRole("button", { name: "取消" });
    expect(close).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("option", { name: "Physics" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: "开新本" })).toHaveFocus();
    await user.tab();
    expect(close).toHaveFocus();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("closes wide popovers when a pointer starts outside", async () => {
    const user = userEvent.setup();
    renderShell();

    await user.click(screen.getByRole("button", { name: /Linear Algebra/ }));
    expect(screen.getByRole("listbox", { name: "切换学习空间" })).toBeInTheDocument();
    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole("listbox", { name: "切换学习空间" })).not.toBeInTheDocument();

    const drafts = await screen.findByLabelText("2 个草稿");
    await user.click(drafts.closest("button")!);
    expect(screen.getByRole("dialog", { name: "草稿箱" })).toBeInTheDocument();
    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole("dialog", { name: "草稿箱" })).not.toBeInTheDocument();
  });
});
