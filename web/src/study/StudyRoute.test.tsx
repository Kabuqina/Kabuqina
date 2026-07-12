// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { act, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../lib/i18n";
import type { StudyRepository } from "./repository";
import { StudyRepositoryProvider } from "./repositoryContext";
import StudyRoute from "./StudyRoute";

const spaces = {
  currentSpaceId: "space-a",
  spaces: [{ id: "space-a", title: "Linear Algebra", status: "active", isCurrent: true }],
};

function Location() {
  return <output data-testid="location">{useLocation().pathname}</output>;
}

function renderRoute(path: string, repositoryOverrides: Partial<StudyRepository> = {}) {
  const repository: StudyRepository = {
    listSpaces: vi.fn().mockResolvedValue(spaces),
    selectSpace: vi.fn().mockResolvedValue(spaces),
    listDrafts: vi.fn().mockResolvedValue({ total: 0, kindCounts: {} }),
    loadFlyleaf: vi.fn().mockResolvedValue({ active: null, draft: null }),
    migrateLegacyContext: vi.fn().mockResolvedValue(false),
    setArtifactStatus: vi.fn().mockResolvedValue(undefined),
    loadPlan: vi.fn().mockResolvedValue({ plan: null, items: [] }),
    completePlanItem: vi.fn(),
    skipPlanItem: vi.fn(),
    loadWrongbook: vi.fn().mockResolvedValue({ weak_points: [], evidence: [], count: 0, returned: 0, limit: 50, truncated: false }),
    loadLatestEvaluation: vi.fn().mockResolvedValue({ evaluation: null }),
    loadActivities: vi.fn().mockResolvedValue({ items: [], count: 0, returned: 0, limit: 50, truncated: false }),
    loadPracticeHome: vi.fn(), loadQuizQuestions: vi.fn(), reviewFlashcard: vi.fn(),
    submitQuiz: vi.fn(), generatePracticeDraft: vi.fn(), resolvePracticeSource: vi.fn(),
    ...repositoryOverrides,
  };
  render(
    <I18nProvider>
      <StudyRepositoryProvider repository={repository}>
        <MemoryRouter initialEntries={[path]}>
          <Location />
          <Routes><Route path="/study/*" element={<StudyRoute />} /></Routes>
        </MemoryRouter>
      </StudyRepositoryProvider>
    </I18nProvider>,
  );
  return repository;
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

describe("StudyRoute", () => {
  it("canonicalizes the root to the current flyleaf", async () => {
    renderRoute("/study");
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/study/space-a/flyleaf"));
  });

  it("canonicalizes a space-only URL to its flyleaf", async () => {
    renderRoute("/study/space-a");
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/study/space-a/flyleaf"));
  });

  it("renders the empty notebook state when no spaces exist", async () => {
    renderRoute("/study", {
      listSpaces: vi.fn().mockResolvedValue({ currentSpaceId: null, spaces: [] }),
    });
    expect(await screen.findByRole("heading", { name: "从一本新笔记开始" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "学习阶段" })).not.toBeInTheDocument();
  });

  it("renders all route-ready placeholder pages", async () => {
    renderRoute("/study/space-a/practice");
    expect(await screen.findByTestId("study-shell")).toHaveTextContent("练习");
  });

  it("shows not-found for an invalid slug without redirecting", async () => {
    renderRoute("/study/space-a/wrong");
    expect(await screen.findByRole("heading")).toHaveTextContent("找不到这个学习页面");
    expect(screen.getByTestId("location")).toHaveTextContent("/study/space-a/wrong");
  });

  it("does not reveal whether an unknown space belongs to someone else", async () => {
    renderRoute("/study/secret-space/learn");
    expect(await screen.findByRole("heading")).toHaveTextContent("无法打开这个学习空间");
  });

  it("retains the active shell and data when a refresh fails", async () => {
    const refresh = deferred<typeof spaces>();
    renderRoute("/study/space-a/learn", {
      listSpaces: vi.fn()
        .mockResolvedValueOnce(spaces)
        .mockImplementationOnce(() => refresh.promise)
        .mockResolvedValueOnce(spaces),
    });
    expect(await screen.findByRole("heading", { name: "学习" })).toBeInTheDocument();

    await act(async () => { window.dispatchEvent(new Event("study-learning-event")); });
    expect(screen.getByTestId("study-shell")).toBeInTheDocument();
    expect(document.querySelector(".kq-study-refresh-status")).toHaveTextContent("正在同步学习空间");

    await act(async () => { refresh.reject(new Error("transport")); });
    expect(await screen.findByRole("alert")).toHaveTextContent("当前内容仍可继续查看");
    expect(screen.getByRole("heading", { name: "学习" })).toBeInTheDocument();
  });
});
