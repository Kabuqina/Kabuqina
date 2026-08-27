// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../../lib/i18n";
import type { StudyRepository } from "../repository";
import { StudyRepositoryProvider } from "../repositoryContext";
import { EvaluatePage } from "./EvaluatePage";
import { StudyIaProvider } from "../StudyIaContext";
import type { StudyIaSink } from "../iaEvents";

function repository(overrides: Partial<StudyRepository> = {}): StudyRepository {
  return {
    seedBuiltinCourse: vi.fn().mockResolvedValue(false),
    migrateLegacyCollections: vi.fn().mockResolvedValue({
      changed: false, retryNeeded: false, flashcards: "absent", quizzes: "absent",
    }),
    listSpaces: vi.fn(), selectSpace: vi.fn(), listDrafts: vi.fn(),
    listDraftPage: vi.fn().mockResolvedValue({ items: [], total: 0, kindCounts: {}, returned: 0, limit: 50, offset: 0, truncated: false }),
    loadLearnHome: vi.fn().mockResolvedValue({ artifacts: [], knowledgePoints: [] }),
    loadArtifactDetail: vi.fn(), loadSourceAudit: vi.fn(), runSemanticReview: vi.fn(),
    loadFlyleaf: vi.fn(), saveFlyleaf: vi.fn(), migrateLegacyContext: vi.fn(), setArtifactStatus: vi.fn(),
    loadPlan: vi.fn(), completePlanItem: vi.fn(), skipPlanItem: vi.fn(),
    loadWrongbook: vi.fn().mockResolvedValue({
      weak_points: [], evidence: [], count: 0, returned: 0, limit: 50, truncated: false,
    }),
    loadLatestEvaluation: vi.fn().mockResolvedValue({ evaluation: null }),
    loadScratch: vi.fn(), saveScratchPad: vi.fn(), fileScratchNote: vi.fn(),
    loadActivities: vi.fn().mockResolvedValue({
      items: [], count: 0, returned: 0, limit: 50, truncated: false,
    }),
    loadPracticeHome: vi.fn(), loadQuizQuestions: vi.fn(), reviewFlashcard: vi.fn(),
    submitQuiz: vi.fn(), generatePracticeDraft: vi.fn(), resolvePracticeSource: vi.fn(),
    ...overrides,
  };
}

function renderPage(repo: StudyRepository, sink: StudyIaSink = vi.fn()) {
  function LocationProbe() {
    return <output aria-label="current route">{useLocation().pathname}</output>;
  }
  render(
    <I18nProvider><StudyRepositoryProvider repository={repo}>
      <StudyIaProvider sink={sink}><MemoryRouter><EvaluatePage spaceId="space-b" /><LocationProbe /></MemoryRouter></StudyIaProvider>
    </StudyRepositoryProvider></I18nProvider>,
  );
}

describe("EvaluatePage", () => {
  it("does not count automatic learning-event revalidation as another wrongbook open", async () => {
    const sink = vi.fn();
    const loadWrongbook = vi.fn().mockResolvedValue({
      weak_points: [], evidence: [], count: 0, returned: 0, limit: 50, truncated: false,
    });
    renderPage(repository({ loadWrongbook }), sink);
    await waitFor(() => expect(loadWrongbook).toHaveBeenCalledTimes(1));
    window.dispatchEvent(new Event("study-learning-event"));
    await waitFor(() => expect(loadWrongbook).toHaveBeenCalledTimes(2));
    expect(sink.mock.calls.filter(([event]) => event.name === "study.wrongbook.open")).toHaveLength(1);
  });

  it("renders bounded evidence and evaluation without duplicating the Activity log", async () => {
    const user = userEvent.setup();
    const sink = vi.fn();
    const loadActivities = vi.fn().mockResolvedValue({
      items: [{ activity_id: "log-1", activity_type: "learning_plan.item.complete", created_at: "2026-07-11T11:00:00Z" }],
      count: 1, returned: 1, limit: 50, truncated: false,
    });
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
        suggestions: ["Retry one problem"], evidence_refs: [{ activity_id: "activity-opaque" }],
      } }),
      loadActivities,
    }), sink);

    expect(await screen.findByText("1 / 3 · 33%")).toBeInTheDocument();
    expect(screen.getByText("Needs steadier vector work")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "学习日志" })).not.toBeInTheDocument();
    expect(loadActivities).not.toHaveBeenCalled();
    expect(screen.queryByText(/SECRET/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "再试一次" })).toHaveAttribute(
      "href", "/study/space-b/notebook?mode=practice&source=wrongbook&activityId=activity-opaque",
    );
    expect(screen.getByRole("link", { name: "再试一次" }).getAttribute("href")).not.toContain("vectors");
    await waitFor(() => expect(sink).toHaveBeenCalledWith({
      name: "study.wrongbook.open", page: "evaluate", action: "open", success: true, count_bucket: "two_to_five",
    }));
    await user.click(screen.getByRole("link", { name: "再试一次" }));
    expect(sink).toHaveBeenCalledWith({ name: "study.wrongbook.retry", page: "evaluate", action: "retry" });
  });

  it("degrades a failed section without hiding successful sections", async () => {
    const sink = vi.fn();
    renderPage(repository({
      loadWrongbook: vi.fn().mockRejectedValue(new Error("offline")),
      loadLatestEvaluation: vi.fn().mockResolvedValue({ evaluation: {
        artifact_id: "evaluation-1", title: "Still visible",
        observations: ["Visible note"], weak_points: [], suggestions: [], evidence_refs: [{ origin: "legacy", key: "context" }],
      } }),
    }), sink);

    expect(await screen.findByRole("alert")).toHaveTextContent("暂时无法读取");
    expect(await screen.findByText("Visible note")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "学习日志" })).not.toBeInTheDocument();
    expect(sink).toHaveBeenCalledWith({
      name: "study.wrongbook.open", page: "evaluate", action: "open", success: false, count_bucket: "zero",
    });
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

  it("returns to a referenced knowledge core and preserves the source outline binding", async () => {
    const user = userEvent.setup();
    localStorage.clear();
    renderPage(repository({
      loadLearnHome: vi.fn().mockResolvedValue({ artifacts: [], knowledgePoints: [{
        item_id: "core-vector", artifact_id: "deck-1", front: "向量", gist: "大小与方向", captured: true,
      }] }),
      loadLatestEvaluation: vi.fn().mockResolvedValue({ evaluation: {
        artifact_id: "evaluation-1", title: "向量回访",
        observations: ["需要重新解释方向"], weak_points: ["vectors"], suggestions: ["回学习"],
        evidence_refs: [{ knowledge_core_id: "core-vector", outline_node_id: "section-vector" }],
      } }),
    }));

    await user.click(await screen.findByRole("button", { name: "回学习" }));
    await waitFor(() => expect(screen.getByRole("status", { name: "current route" })).toHaveTextContent("/study/space-b/notebook"));
    expect(JSON.parse(localStorage.getItem("kabuqina.study.location.v1:space-b")!)).toMatchObject({
      page: "learn",
      knowledgeCoreId: "core-vector",
      outlineNodeId: "section-vector",
    });
  });

  it("does not present an evaluation conclusion as reliable when it has no evidence refs", async () => {
    renderPage(repository({
      loadLatestEvaluation: vi.fn().mockResolvedValue({ evaluation: {
        artifact_id: "evaluation-legacy", title: "无依据旧评估",
        observations: ["不应展示的总体结论"], weak_points: [], suggestions: ["不应执行的建议"], evidence_refs: [],
      } }),
    }));

    expect(await screen.findByText("这条评估还没有可追溯证据，暂不用于调整。")).toBeInTheDocument();
    expect(screen.queryByText("不应展示的总体结论")).not.toBeInTheDocument();
    expect(screen.queryByText("不应执行的建议")).not.toBeInTheDocument();
  });

  it("degrades a removed knowledge-core return target to the course plan", async () => {
    const user = userEvent.setup();
    localStorage.clear();
    renderPage(repository({
      loadLearnHome: vi.fn().mockResolvedValue({ artifacts: [], knowledgePoints: [] }),
      loadLatestEvaluation: vi.fn().mockResolvedValue({ evaluation: {
        artifact_id: "evaluation-stale", title: "旧回访",
        observations: ["旧证据仍可说明当时的情况"], weak_points: [], suggestions: ["回看"],
        evidence_refs: [{ knowledge_core_id: "removed-core" }],
      } }),
    }));

    await user.click(await screen.findByRole("button", { name: "回学习" }));
    await waitFor(() => expect(screen.getByRole("status", { name: "current route" })).toHaveTextContent("/study/space-b/bookend"));
    expect(localStorage.getItem("kabuqina.study.location.v1:space-b")).toBeNull();
  });

  it("merges the zero-evidence regions into one actionable page empty state", async () => {
    renderPage(repository());
    expect(await screen.findByRole("heading", { name: "还没有可以评估的练习证据" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "去练习" })).toHaveAttribute("href", "/study/space-b/notebook?mode=practice");
    expect(screen.getByRole("link", { name: "回到学习" })).toHaveAttribute("href", "/study/space-b/notebook?mode=learn");
    expect(screen.queryByText(/错题本是空的/)).not.toBeInTheDocument();
    expect(screen.queryByText("还没有生效的评估记录。")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "评估" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "评估" })).toHaveFocus();
  });
});
