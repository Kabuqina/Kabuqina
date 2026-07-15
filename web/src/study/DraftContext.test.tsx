// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { StudyDraftProvider, useStudyDrafts } from "./DraftContext";
import type { StudyDraftPage, StudyRepository } from "./repository";
import { StudyRepositoryProvider } from "./repositoryContext";

const empty: StudyDraftPage = { items: [], total: 0, kindCounts: {}, returned: 0, limit: 50, offset: 0, truncated: false };

function Probe() {
  const drafts = useStudyDrafts();
  const data = drafts.snapshot.status === "ready" ? drafts.snapshot.data : drafts.snapshot.status === "loading" ? drafts.snapshot.previous : undefined;
  return <><output data-testid="draft-items">{data?.items.map((item) => item.title).join(",") ?? "loading"}</output><button type="button" onClick={drafts.loadMore}>load more</button><button type="button" onClick={() => { void drafts.activate("draft-a"); }}>activate</button></>;
}

describe("StudyDraftProvider", () => {
  it("aborts an older list refresh when a mutation requests a newer snapshot", async () => {
    const user = userEvent.setup();
    let resolveOld!: (page: StudyDraftPage) => void;
    const listDraftPage = vi.fn()
      .mockImplementationOnce(() => new Promise<StudyDraftPage>((resolve) => { resolveOld = resolve; }))
      .mockResolvedValue(empty);
    const repository = {
      listDraftPage,
      setArtifactStatus: vi.fn().mockResolvedValue(undefined),
    } as unknown as StudyRepository;
    render(<StudyRepositoryProvider repository={repository}><StudyDraftProvider spaceId="space-a"><Probe /></StudyDraftProvider></StudyRepositoryProvider>);

    await user.click(screen.getByRole("button", { name: "activate" }));
    await waitFor(() => expect(listDraftPage).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.getByTestId("draft-items")).not.toHaveTextContent("loading"));

    await act(async () => resolveOld({ ...empty, items: [{ artifact_id: "draft-a", kind: "quiz", title: "STALE", status: "draft" }], total: 1, returned: 1 }));
    expect(screen.queryByText("STALE")).not.toBeInTheDocument();
  });

  it("cancels an in-flight load-more before a mutation refresh replaces page one", async () => {
    const user = userEvent.setup();
    let resolveLoadMore!: (page: StudyDraftPage) => void;
    const firstPage = {
      ...empty,
      items: [{ artifact_id: "draft-a", kind: "quiz", title: "Current draft", status: "draft" }],
      total: 2,
      returned: 1,
      truncated: true,
    };
    const listDraftPage = vi.fn()
      .mockResolvedValueOnce(firstPage)
      .mockImplementationOnce(() => new Promise<StudyDraftPage>((resolve) => { resolveLoadMore = resolve; }))
      .mockResolvedValueOnce(empty);
    const repository = {
      listDraftPage,
      setArtifactStatus: vi.fn().mockResolvedValue(undefined),
    } as unknown as StudyRepository;
    render(<StudyRepositoryProvider repository={repository}><StudyDraftProvider spaceId="space-a"><Probe /></StudyDraftProvider></StudyRepositoryProvider>);

    expect(await screen.findByText("Current draft")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "load more" }));
    await waitFor(() => expect(listDraftPage).toHaveBeenCalledTimes(2));
    await user.click(screen.getByRole("button", { name: "activate" }));
    await waitFor(() => expect(listDraftPage).toHaveBeenCalledTimes(3));
    await waitFor(() => expect(screen.getByTestId("draft-items")).toHaveTextContent(/^$/));

    await act(async () => resolveLoadMore({
      ...empty,
      items: [{ artifact_id: "stale", kind: "quiz", title: "STALE PAGE", status: "draft" }],
      total: 2,
      returned: 1,
    }));
    expect(screen.queryByText("STALE PAGE")).not.toBeInTheDocument();
  });
});
