// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../../lib/i18n";
import type { StudyPlanItem } from "../../chat/study/study-api";
import type { StudyRepository } from "../repository";
import { StudyRepositoryProvider } from "../repositoryContext";
import { PlanPage } from "./PlanPage";

function repository(overrides: Partial<StudyRepository> = {}): StudyRepository {
  return {
    listSpaces: vi.fn(), selectSpace: vi.fn(), listDrafts: vi.fn(),
    loadFlyleaf: vi.fn(), migrateLegacyContext: vi.fn(), setArtifactStatus: vi.fn(),
    loadPlan: vi.fn().mockResolvedValue({ plan: null, items: [] }),
    completePlanItem: vi.fn(), skipPlanItem: vi.fn(), loadWrongbook: vi.fn(),
    loadLatestEvaluation: vi.fn(), loadActivities: vi.fn(), ...overrides,
  };
}

function renderPage(repo: StudyRepository) {
  render(
    <I18nProvider><StudyRepositoryProvider repository={repo}>
      <MemoryRouter><PlanPage spaceId="space-b" /></MemoryRouter>
    </StudyRepositoryProvider></I18nProvider>,
  );
}

function item(overrides: Partial<StudyPlanItem>): StudyPlanItem {
  return {
    item_id: "item-1", artifact_id: "plan-1", phaseIndex: 0, phaseTitle: "Phase one",
    taskIndex: 0, title: "Read", order: 1, done_when: "Explain it", status: "open",
    completedAt: "", skippedAt: "", note: "", createdAt: "2026-07-11T00:00:00Z",
    ...overrides,
  };
}

const plan = {
  artifact_id: "plan-1", kind: "learning_plan", title: "Physics plan", status: "active",
  updated_at: "2026-07-11T00:00:00Z",
};

describe("PlanPage", () => {
  it("uses the first open item as the only resume bookmark and focuses it", async () => {
    const user = userEvent.setup();
    renderPage(repository({ loadPlan: vi.fn().mockResolvedValue({
      plan,
      items: [
        item({ item_id: "done", title: "Done", status: "completed" }),
        item({ item_id: "next", title: "Next task", taskIndex: 1, order: 2 }),
      ],
    }) }));

    await user.click(await screen.findByRole("button", { name: /继续上次/ }));
    expect(screen.getByRole("heading", { name: "Next task" }).closest("li")).toHaveFocus();
  });

  it("completes one item through the URL-scoped repository and patches its state", async () => {
    const user = userEvent.setup();
    const open = item({ item_id: "next", title: "Next task" });
    const completed = { ...open, status: "completed" as const, completedAt: "2026-07-11T01:00:00Z" };
    const loadPlan = vi.fn()
      .mockResolvedValueOnce({ plan, items: [open] })
      .mockResolvedValue({ plan, items: [completed] });
    const completePlanItem = vi.fn().mockResolvedValue(completed);
    renderPage(repository({ loadPlan, completePlanItem }));

    await user.click(await screen.findByRole("button", { name: "完成" }));
    expect(completePlanItem).toHaveBeenCalledWith("space-b", "next", expect.any(AbortSignal));
    await waitFor(() => expect(screen.getByText("已完成")).toBeInTheDocument());
  });

  it("keeps the open item when a mutation fails", async () => {
    const user = userEvent.setup();
    const open = item({ item_id: "next", title: "Next task" });
    renderPage(repository({
      loadPlan: vi.fn().mockResolvedValue({ plan, items: [open] }),
      skipPlanItem: vi.fn().mockRejectedValue(new Error("conflict")),
    }));

    await user.click(await screen.findByRole("button", { name: "跳过" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("当前状态已保留");
    expect(screen.getByRole("button", { name: "完成" })).toBeEnabled();
  });

  it("renders an honest empty state", async () => {
    renderPage(repository());
    expect(await screen.findByRole("heading", { name: "还没有生效的学习计划" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "问小娜" })).toHaveAttribute("href", "/chat");
  });
});
