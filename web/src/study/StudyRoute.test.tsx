// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen, waitFor } from "@testing-library/react";
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
    listDrafts: vi.fn().mockResolvedValue([]),
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

describe("StudyRoute", () => {
  it("canonicalizes the root to the current flyleaf", async () => {
    renderRoute("/study");
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/study/space-a/flyleaf"));
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
});
