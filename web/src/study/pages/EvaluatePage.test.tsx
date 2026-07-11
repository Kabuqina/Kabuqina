// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../../lib/i18n";
import type { StudyRepository } from "../repository";
import { StudyRepositoryProvider } from "../repositoryContext";
import { EvaluatePage } from "./EvaluatePage";

function repository(overrides: Partial<StudyRepository> = {}): StudyRepository {
  return {
    listSpaces: vi.fn(), selectSpace: vi.fn(), listDrafts: vi.fn(),
    loadFlyleaf: vi.fn(), migrateLegacyContext: vi.fn(), setArtifactStatus: vi.fn(),
    loadPlan: vi.fn(), completePlanItem: vi.fn(), skipPlanItem: vi.fn(),
    loadWrongbook: vi.fn().mockResolvedValue({
      weak_points: [], evidence: [], count: 0, returned: 0, limit: 50, truncated: false,
    }),
    loadLatestEvaluation: vi.fn().mockResolvedValue({ evaluation: null }),
    loadActivities: vi.fn().mockResolvedValue({
      items: [], count: 0, returned: 0, limit: 50, truncated: false,
    }),
    ...overrides,
  };
}

function renderPage(repo: StudyRepository) {
  render(
    <I18nProvider><StudyRepositoryProvider repository={repo}>
      <MemoryRouter><EvaluatePage spaceId="space-b" /></MemoryRouter>
    </StudyRepositoryProvider></I18nProvider>,
  );
}

describe("EvaluatePage", () => {
  it("renders bounded evidence, evaluation, and content-minimized activity", async () => {
    renderPage(repository({
      loadWrongbook: vi.fn().mockResolvedValue({
        weak_points: ["vectors"],
        evidence: [{
          activity_id: "activity-opaque", artifact_id: "quiz-1", activity_type: "quiz.attempt",
          created_at: "2026-07-11T10:00:00Z", score: 1, max_score: 3, percent: 33,
          weak_tags: ["vectors"], response: "SECRET ANSWER",
        }],
        count: 2, returned: 1, limit: 1, truncated: true,
      }),
      loadLatestEvaluation: vi.fn().mockResolvedValue({ evaluation: {
        artifact_id: "evaluation-1", title: "Weekly note",
        observations: ["Needs steadier vector work"], weak_points: ["vectors"],
        suggestions: ["Retry one problem"], evidence_refs: [],
      } }),
      loadActivities: vi.fn().mockResolvedValue({
        items: [{
          activity_id: "log-1", activity_type: "learning_plan.item.complete",
          artifact_id: "plan-1", item_id: "item-1", created_at: "2026-07-11T11:00:00Z",
          detail: { answer: "SECRET DETAIL" },
        }],
        count: 1, returned: 1, limit: 50, truncated: false,
      }),
    }));

    expect(await screen.findByText("1 / 3 · 33%")).toBeInTheDocument();
    expect(screen.getByText("Needs steadier vector work")).toBeInTheDocument();
    expect(screen.getByText("学习活动：learning_plan.item.complete")).toBeInTheDocument();
    expect(screen.queryByText(/SECRET/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "再试一次" })).toHaveAttribute(
      "href", "/study/space-b/practice?source=wrongbook&activityId=activity-opaque",
    );
    expect(screen.getByRole("link", { name: "再试一次" }).getAttribute("href")).not.toContain("vectors");
  });

  it("degrades a failed section without hiding successful sections", async () => {
    renderPage(repository({
      loadWrongbook: vi.fn().mockRejectedValue(new Error("offline")),
      loadLatestEvaluation: vi.fn().mockResolvedValue({ evaluation: {
        artifact_id: "evaluation-1", title: "Still visible",
        observations: ["Visible note"], weak_points: [], suggestions: [], evidence_refs: [],
      } }),
    }));

    expect(await screen.findByRole("alert")).toHaveTextContent("暂时无法读取");
    expect(await screen.findByText("Visible note")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "学习日志" })).toBeInTheDocument();
  });

  it("shows evaluation weak points even when there are no quiz attempts", async () => {
    renderPage(repository({
      loadWrongbook: vi.fn().mockResolvedValue({
        weak_points: ["vector decomposition"], evidence: [],
        count: 0, returned: 0, limit: 50, truncated: false,
      }),
    }));

    expect(await screen.findByText("vector decomposition")).toBeInTheDocument();
    expect(screen.queryByText(/错题本是空的/)).not.toBeInTheDocument();
  });

  it("renders three honest empty states and focuses the page heading", async () => {
    renderPage(repository());
    expect(await screen.findByText(/错题本是空的/)).toBeInTheDocument();
    expect(screen.getByText("还没有生效的评估记录。")).toBeInTheDocument();
    expect(screen.getByText("还没有学习活动。")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "评估" })).toHaveFocus();
  });
});
