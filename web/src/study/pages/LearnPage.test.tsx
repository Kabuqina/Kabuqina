// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../../lib/i18n";
import { StudyDraftProvider } from "../DraftContext";
import type { StudyArtifactDetail, StudyRepository } from "../repository";
import { StudyRepositoryProvider } from "../repositoryContext";
import { LearnPage } from "./LearnPage";

const emptyDrafts = { items: [], total: 0, kindCounts: {}, returned: 0, limit: 50, offset: 0, truncated: false };
const detail = {
  artifactId: "knowledge-1",
  kind: "knowledge_base",
  title: "Active knowledge",
  version: 1,
  status: "active",
  review: { mode: "deterministic", status: "passed" },
  envelope: { payload: { concepts: [{ term: "Immediate concept", explanation: "Visible without navigation" }] } },
} as StudyArtifactDetail;

describe("LearnPage", () => {
  it("reloads active M5 content immediately after an inline draft activation", async () => {
    const user = userEvent.setup();
    const listDraftPage = vi.fn()
      .mockResolvedValueOnce({
        ...emptyDrafts,
        items: [{ artifact_id: "knowledge-1", kind: "knowledge_base", title: "Draft knowledge", status: "draft", review: { mode: "deterministic", status: "passed" } }],
        total: 1,
        returned: 1,
        kindCounts: { knowledge_base: 1 },
      })
      .mockResolvedValue(emptyDrafts);
    const loadLearnHome = vi.fn()
      .mockResolvedValueOnce({ artifacts: [], knowledgePoints: [] })
      .mockResolvedValue({
        artifacts: [{ artifact_id: "knowledge-1", kind: "knowledge_base", title: "Active knowledge", status: "active" }],
        knowledgePoints: [],
      });
    const repository = {
      listDraftPage,
      loadLearnHome,
      loadArtifactDetail: vi.fn().mockResolvedValue(detail),
      setArtifactStatus: vi.fn().mockResolvedValue(undefined),
      loadSourceAudit: vi.fn(),
      runSemanticReview: vi.fn(),
    } as unknown as StudyRepository;

    render(
      <I18nProvider><StudyRepositoryProvider repository={repository}><MemoryRouter>
        <StudyDraftProvider spaceId="space-a"><LearnPage spaceId="space-a" /></StudyDraftProvider>
      </MemoryRouter></StudyRepositoryProvider></I18nProvider>,
    );

    await user.click(await screen.findByRole("button", { name: "Draft knowledge" }));
    await user.click(await screen.findByRole("button", { name: "落墨" }));

    await waitFor(() => expect(loadLearnHome).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole("button", { name: "Active knowledge" })).toBeInTheDocument();
    expect(await screen.findByText("Visible without navigation")).toBeInTheDocument();
  });
});
