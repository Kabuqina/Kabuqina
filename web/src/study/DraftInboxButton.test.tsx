// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../lib/i18n";
import { DraftInboxButton } from "./DraftInboxButton";
import { StudyDraftProvider } from "./DraftContext";
import type { StudyRepository } from "./repository";
import { StudyRepositoryProvider } from "./repositoryContext";

describe("DraftInboxButton", () => {
  it("owns pagination and restores trigger focus after Escape", async () => {
    const user = userEvent.setup();
    const listDraftPage = vi.fn()
      .mockResolvedValueOnce({
        items: [{ artifact_id: "draft-1", kind: "quiz", title: "First draft", status: "draft" }],
        total: 2,
        kindCounts: { quiz: 2 },
        returned: 1,
        limit: 50,
        offset: 0,
        truncated: true,
      })
      .mockResolvedValueOnce({
        items: [{ artifact_id: "draft-2", kind: "quiz", title: "Second draft", status: "draft" }],
        total: 2,
        kindCounts: { quiz: 2 },
        returned: 1,
        limit: 50,
        offset: 1,
        truncated: false,
      });
    const repository = { listDraftPage } as unknown as StudyRepository;
    render(
      <I18nProvider><StudyRepositoryProvider repository={repository}><MemoryRouter>
        <StudyDraftProvider spaceId="space-a"><DraftInboxButton /></StudyDraftProvider>
      </MemoryRouter></StudyRepositoryProvider></I18nProvider>,
    );

    const trigger = (await screen.findByLabelText("2 个草稿")).closest("button")!;
    await user.click(trigger);
    expect(screen.getByRole("dialog", { name: "草稿箱" })).toHaveTextContent("First draft");
    await user.click(screen.getByRole("button", { name: "加载更多" }));
    expect(await screen.findByText("Second draft")).toBeInTheDocument();
    expect(listDraftPage).toHaveBeenLastCalledWith("space-a", 50, 1, expect.any(AbortSignal));

    await user.keyboard("{Escape}");
    await waitFor(() => expect(trigger).toHaveFocus());
    expect(screen.queryByRole("dialog", { name: "草稿箱" })).not.toBeInTheDocument();
  });
});
