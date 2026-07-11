// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../../lib/i18n";
import {
  STUDY_CONTEXT_STORAGE_KEY,
  emptyStudyContext,
  saveStudyContext,
} from "../../chat/study/studyStore";
import type { StudyRepository } from "../repository";
import { StudyRepositoryProvider } from "../repositoryContext";
import { FlyleafPage } from "./FlyleafPage";

function repository(overrides: Partial<StudyRepository> = {}): StudyRepository {
  return {
    listSpaces: vi.fn(),
    selectSpace: vi.fn(),
    listDrafts: vi.fn(),
    loadFlyleaf: vi.fn().mockResolvedValue({ active: null, draft: null }),
    migrateLegacyContext: vi.fn().mockResolvedValue(false),
    setArtifactStatus: vi.fn().mockResolvedValue(undefined),
    loadPlan: vi.fn(),
    completePlanItem: vi.fn(),
    skipPlanItem: vi.fn(),
    loadWrongbook: vi.fn(),
    loadLatestEvaluation: vi.fn(),
    loadActivities: vi.fn(),
    ...overrides,
  };
}

function renderPage(repo: StudyRepository) {
  render(
    <I18nProvider>
      <StudyRepositoryProvider repository={repo}>
        <MemoryRouter><FlyleafPage spaceId="space-b" /></MemoryRouter>
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
      loadFlyleaf: vi.fn()
        .mockResolvedValueOnce({
          active: { ...active, payload: { ...active.payload, weak_points: ["SECRET WEAKNESS"] } },
          draft,
        })
        .mockResolvedValue({ active: { ...draft, status: "active" }, draft: null }),
      setArtifactStatus,
    });
    renderPage(repo);

    expect(await screen.findByRole("heading", { name: "我的学习设定" })).toBeInTheDocument();
    expect(screen.getByText("Draft physics")).toBeInTheDocument();
    expect(screen.queryByText("SECRET WEAKNESS")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "落墨" }));
    expect(setArtifactStatus).toHaveBeenCalledWith(
      "space-b", "draft-state", "active", expect.any(AbortSignal),
    );
    await waitFor(() => expect(screen.queryByText("小娜拟了一版扉页")).not.toBeInTheDocument());
  });

  it("keeps legacy local storage when migration fails", async () => {
    saveStudyContext({ ...emptyStudyContext(), course: "Legacy calculus" });
    const migrateLegacyContext = vi.fn().mockRejectedValue(new Error("offline"));
    renderPage(repository({ migrateLegacyContext }));

    expect(await screen.findByRole("alert")).toHaveTextContent("原数据仍完整保留");
    expect(migrateLegacyContext).toHaveBeenCalledWith(
      "space-b",
      expect.objectContaining({ course: "Legacy calculus" }),
      expect.any(AbortSignal),
    );
    expect(window.localStorage.getItem(STUDY_CONTEXT_STORAGE_KEY)).toContain("Legacy calculus");
  });

  it("migrates legacy context into the URL space and refreshes the active state", async () => {
    saveStudyContext({ ...emptyStudyContext(), course: "Legacy physics" });
    const migrateLegacyContext = vi.fn().mockResolvedValue(true);
    const loadFlyleaf = vi.fn()
      .mockResolvedValueOnce({ active: null, draft: null })
      .mockResolvedValue({ active: { ...active, payload: { ...active.payload, course: "Legacy physics" } }, draft: null });
    renderPage(repository({ migrateLegacyContext, loadFlyleaf }));

    expect(await screen.findByText("Legacy physics")).toBeInTheDocument();
    expect(migrateLegacyContext).toHaveBeenCalledWith(
      "space-b", expect.objectContaining({ course: "Legacy physics" }), expect.any(AbortSignal),
    );
  });

  it("erases a pencil draft through the scoped artifact mutation", async () => {
    const user = userEvent.setup();
    const draft = { ...active, artifact_id: "draft-state", status: "draft" };
    const setArtifactStatus = vi.fn().mockResolvedValue(undefined);
    const loadFlyleaf = vi.fn()
      .mockResolvedValueOnce({ active: null, draft })
      .mockResolvedValue({ active: null, draft: null });
    renderPage(repository({ loadFlyleaf, setArtifactStatus }));

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
