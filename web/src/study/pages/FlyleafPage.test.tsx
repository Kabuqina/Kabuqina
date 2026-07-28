// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../../lib/i18n";
import {
  LEGACY_STUDY_CONTEXT_STORAGE_KEY,
} from "../legacyStudyContextMigration";
import type { StudyRepository } from "../repository";
import { StudyRepositoryProvider } from "../repositoryContext";
import { StudyDraftProvider } from "../DraftContext";
import { FlyleafPage } from "./FlyleafPage";

function repository(overrides: Partial<StudyRepository> = {}): StudyRepository {
  return {
    seedBuiltinCourse: vi.fn().mockResolvedValue(false),
    migrateLegacyCollections: vi.fn().mockResolvedValue({
      changed: false, retryNeeded: false, flashcards: "absent", quizzes: "absent",
    }),
    listSpaces: vi.fn(),
    selectSpace: vi.fn(),
    listDrafts: vi.fn(),
    listDraftPage: vi.fn().mockResolvedValue({ items: [], total: 0, kindCounts: {}, returned: 0, limit: 50, offset: 0, truncated: false }),
    loadLearnHome: vi.fn().mockResolvedValue({ artifacts: [], knowledgePoints: [] }),
    loadArtifactDetail: vi.fn(), loadSourceAudit: vi.fn(), runSemanticReview: vi.fn(),
    loadFlyleaf: vi.fn().mockResolvedValue({ active: null, draft: null }),
    migrateLegacyContext: vi.fn().mockResolvedValue(false),
    setArtifactStatus: vi.fn().mockResolvedValue(undefined),
    loadPlan: vi.fn(),
    completePlanItem: vi.fn(),
    skipPlanItem: vi.fn(),
    loadWrongbook: vi.fn(),
    loadLatestEvaluation: vi.fn(),
    loadActivities: vi.fn(),
    loadScratch: vi.fn(), saveScratchPad: vi.fn(), fileScratchNote: vi.fn(),
    loadPracticeHome: vi.fn(), loadQuizQuestions: vi.fn(), reviewFlashcard: vi.fn(),
    submitQuiz: vi.fn(), generatePracticeDraft: vi.fn(), resolvePracticeSource: vi.fn(),
    ...overrides,
  };
}

function renderPage(repo: StudyRepository) {
  render(
    <I18nProvider>
      <StudyRepositoryProvider repository={repo}>
        <MemoryRouter><StudyDraftProvider spaceId="space-b"><FlyleafPage spaceId="space-b" /></StudyDraftProvider></MemoryRouter>
      </StudyRepositoryProvider>
    </I18nProvider>,
  );
}

const active = {
  artifact_id: "active-state",
  status: "active",
  payload: {
    course: "Physics",
    goals: ["Pass the exam"],
    preferences: { examples: "code first" },
    constraints: ["30 minutes"],
    progress_notes: [],
    current_stage: "Vectors",
    next_adjustment: "More practice",
  },
};

afterEach(() => window.localStorage.clear());

function saveLegacyStudyContext(values: Record<string, string>) {
  window.localStorage.setItem(LEGACY_STUDY_CONTEXT_STORAGE_KEY, JSON.stringify(values));
}

describe("FlyleafPage", () => {
  it("renders active ink and pencil draft without leaking weak points", async () => {
    const user = userEvent.setup();
    const setArtifactStatus = vi.fn().mockResolvedValue(undefined);
    const draft = {
      ...active,
      artifact_id: "draft-state",
      status: "draft",
      payload: { ...active.payload, course: "Draft physics" },
    };
    const repo = repository({
      loadFlyleaf: vi.fn().mockResolvedValue({ active: { ...active, payload: { ...active.payload, weak_points: ["SECRET WEAKNESS"] } } }),
      listDraftPage: vi.fn()
        .mockResolvedValueOnce({ items: [{ artifact_id: "draft-state", kind: "student_state", title: "Draft", status: "draft" }], total: 1, kindCounts: { student_state: 1 }, returned: 1, limit: 50, offset: 0, truncated: false })
        .mockResolvedValue({ items: [], total: 0, kindCounts: {}, returned: 0, limit: 50, offset: 0, truncated: false }),
      loadArtifactDetail: vi.fn().mockResolvedValue({ artifactId: "draft-state", kind: "student_state", title: "Draft", version: 1, status: "draft", review: {}, envelope: { payload: draft.payload } }),
      setArtifactStatus,
    });
    renderPage(repo);

    expect(await screen.findByRole("heading", { name: "我的学习设定" })).toBeInTheDocument();
    expect(await screen.findByText("Draft physics")).toBeInTheDocument();
    expect(screen.queryByText("SECRET WEAKNESS")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "落墨" }));
    expect(setArtifactStatus).toHaveBeenCalledWith(
      "space-b", "draft-state", "active", expect.any(AbortSignal),
    );
    await waitFor(() => expect(screen.queryByText("小娜拟了一版扉页")).not.toBeInTheDocument());
  });

  it("keeps legacy local storage when migration fails", async () => {
    saveLegacyStudyContext({ course: "Legacy calculus" });
    const migrateLegacyContext = vi.fn().mockRejectedValue(new Error("offline"));
    renderPage(repository({ migrateLegacyContext }));

    expect(await screen.findByRole("alert")).toHaveTextContent("原数据仍完整保留");
    expect(migrateLegacyContext).toHaveBeenCalledWith(
      "space-b",
      expect.objectContaining({ course: "Legacy calculus" }),
      expect.any(AbortSignal),
    );
    expect(window.localStorage.getItem(LEGACY_STUDY_CONTEXT_STORAGE_KEY)).toContain("Legacy calculus");
  });

  it("migrates legacy context into the URL space and refreshes the active state", async () => {
    saveLegacyStudyContext({ course: "Legacy physics" });
    const migrateLegacyContext = vi.fn().mockResolvedValue(true);
    const loadFlyleaf = vi.fn()
      .mockResolvedValueOnce({ active: null })
      .mockResolvedValue({ active: { ...active, payload: { ...active.payload, course: "Legacy physics" } } });
    renderPage(repository({ migrateLegacyContext, loadFlyleaf }));

    expect(await screen.findByText("Legacy physics")).toBeInTheDocument();
    expect(migrateLegacyContext).toHaveBeenCalledWith(
      "space-b", expect.objectContaining({ course: "Legacy physics" }), expect.any(AbortSignal),
    );
    expect(window.localStorage.getItem(LEGACY_STUDY_CONTEXT_STORAGE_KEY)).toBeNull();
  });

  it("erases a pencil draft through the scoped artifact mutation", async () => {
    const user = userEvent.setup();
    const draft = { ...active, artifact_id: "draft-state", status: "draft" };
    const setArtifactStatus = vi.fn().mockResolvedValue(undefined);
    renderPage(repository({
      loadFlyleaf: vi.fn().mockResolvedValue({ active: null }),
      listDraftPage: vi.fn()
        .mockResolvedValueOnce({ items: [{ artifact_id: "draft-state", kind: "student_state", title: "Draft", status: "draft" }], total: 1, kindCounts: { student_state: 1 }, returned: 1, limit: 50, offset: 0, truncated: false })
        .mockResolvedValue({ items: [], total: 0, kindCounts: {}, returned: 0, limit: 50, offset: 0, truncated: false }),
      loadArtifactDetail: vi.fn().mockResolvedValue({ artifactId: "draft-state", kind: "student_state", title: "Draft", version: 1, status: "draft", review: {}, envelope: { payload: draft.payload } }),
      setArtifactStatus,
    }));

    await user.click(await screen.findByRole("button", { name: "擦掉" }));
    expect(setArtifactStatus).toHaveBeenCalledWith(
      "space-b", "draft-state", "rejected", expect.any(AbortSignal),
    );
    await waitFor(() => expect(screen.queryByText("小娜拟了一版扉页")).not.toBeInTheDocument());
  });

  it("shows an honest empty state and focuses the page heading", async () => {
    renderPage(repository());
    expect(await screen.findByRole("heading", { name: "这张扉页还是空白" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "扉页" })).toHaveFocus();
    expect(screen.getByRole("link", { name: "问小娜" })).toHaveAttribute("href", "/chat");
  });
});
