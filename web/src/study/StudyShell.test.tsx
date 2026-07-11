// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen, waitFor } from "@testing-library/react";
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

function renderShell(repositoryOverrides: Partial<StudyRepository> = {}) {
  const repository: StudyRepository = {
    listSpaces: vi.fn().mockResolvedValue(spaces),
    selectSpace: vi.fn().mockResolvedValue({ ...spaces, currentSpaceId: "space-b" }),
    listDrafts: vi.fn().mockResolvedValue([
      { id: "d1", kind: "flashcard_deck", status: "draft" },
      { id: "d2", kind: "quiz", status: "draft" },
    ]),
    ...repositoryOverrides,
  };
  render(
    <I18nProvider>
      <StudyRepositoryProvider repository={repository}>
        <MemoryRouter initialEntries={["/study/space-a/learn"]}>
          <Location />
          <StudyShell spaces={spaces} spaceId="space-a" page="learn" />
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

  it("keeps route and data when selecting a space fails", async () => {
    const user = userEvent.setup();
    renderShell({ selectSpace: vi.fn().mockRejectedValue(new Error("request_failed")) });
    await user.click(screen.getByRole("button", { name: /Linear Algebra/ }));
    await user.click(screen.getByRole("option", { name: "Physics" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("原学习空间已保留");
    expect(screen.getByTestId("location")).toHaveTextContent("/study/space-a/learn");
    expect(screen.getByRole("heading", { name: "学习" })).toBeInTheDocument();
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
    await user.keyboard("{Escape}");
    await waitFor(() => expect(trigger).toHaveFocus());
  });
});
