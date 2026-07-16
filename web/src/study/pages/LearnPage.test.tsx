// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../../lib/i18n";
import { StudyDraftProvider, useStudyDrafts } from "../DraftContext";
import { StudyRepositoryError, type StudyArtifactDetail, type StudyRepository } from "../repository";
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

function DetailCacheProbe({ artifactId }: { artifactId: string }) {
  const drafts = useStudyDrafts();
  return <output data-testid="detail-cache">{drafts.details[artifactId]?.status ?? "missing"}</output>;
}

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

  it("renders an unavailable M5 kind in its own section instead of as an empty state", async () => {
    const repository = {
      listDraftPage: vi.fn().mockResolvedValue(emptyDrafts),
      loadLearnHome: vi.fn().mockResolvedValue({
        artifacts: [{ artifact_id: "knowledge-1", kind: "knowledge_base", title: "Active knowledge", status: "active" }],
        knowledgePoints: [],
        unavailableKinds: ["resource_pack"],
      }),
      loadArtifactDetail: vi.fn().mockResolvedValue(detail),
      loadSourceAudit: vi.fn(),
    } as unknown as StudyRepository;
    render(
      <I18nProvider><StudyRepositoryProvider repository={repository}><MemoryRouter>
        <StudyDraftProvider spaceId="space-a"><LearnPage spaceId="space-a" /></StudyDraftProvider>
      </MemoryRouter></StudyRepositoryProvider></I18nProvider>,
    );

    const resources = (await screen.findByRole("heading", { name: "资源包" })).closest("section")!;
    expect(within(resources).getByRole("status")).toHaveTextContent("这一部分暂时无法读取");
    expect(within(resources).queryByText("这一页还没有学习内容")).not.toBeInTheDocument();
    const knowledge = screen.getByRole("heading", { name: "课程知识库" }).closest("section")!;
    expect(within(knowledge).getByRole("button", { name: "Active knowledge" })).toBeInTheDocument();
  });

  it("refreshes active summaries and removes stale raw data after an audit 404", async () => {
    const user = userEvent.setup();
    const loadLearnHome = vi.fn()
      .mockResolvedValueOnce({
        artifacts: [{ artifact_id: "knowledge-1", kind: "knowledge_base", title: "Active knowledge", status: "active" }],
        knowledgePoints: [],
      })
      .mockResolvedValue({ artifacts: [], knowledgePoints: [] });
    const repository = {
      listDraftPage: vi.fn().mockResolvedValue(emptyDrafts),
      loadLearnHome,
      loadArtifactDetail: vi.fn().mockResolvedValue(detail),
      loadSourceAudit: vi.fn().mockRejectedValue(new StudyRepositoryError("not-found")),
    } as unknown as StudyRepository;
    render(
      <I18nProvider><StudyRepositoryProvider repository={repository}><MemoryRouter>
        <StudyDraftProvider spaceId="space-a"><LearnPage spaceId="space-a" /><DetailCacheProbe artifactId="knowledge-1" /></StudyDraftProvider>
      </MemoryRouter></StudyRepositoryProvider></I18nProvider>,
    );

    expect(await screen.findByText("Visible without navigation")).toBeInTheDocument();
    expect(screen.getByTestId("detail-cache")).toHaveTextContent("ready");
    await user.click(screen.getByRole("button", { name: "高级" }));
    await user.click(screen.getByRole("button", { name: "查看原始 JSON" }));
    expect(screen.getByText(/"Immediate concept"/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "查看来源审计" }));

    await waitFor(() => expect(loadLearnHome).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByText(/"Immediate concept"/)).not.toBeInTheDocument());
    expect(screen.getByTestId("detail-cache")).toHaveTextContent("missing");
    expect(screen.queryByRole("button", { name: "Active knowledge" })).not.toBeInTheDocument();
  });
});
