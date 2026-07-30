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

  it("previews only safe quiz fields and lets the learner adopt a pending quiz draft", async () => {
    const user = userEvent.setup();
    const draft = {
      artifact_id: "draft-quiz",
      kind: "quiz",
      title: "极限补充题",
      status: "draft",
      review: { mode: "semantic", status: "pending" },
    };
    const detail = {
      artifactId: "draft-quiz",
      kind: "quiz",
      title: "极限补充题",
      version: 1,
      status: "draft",
      review: { mode: "semantic", status: "pending" },
      envelope: {
        payload: {
          questions: [{
            type: "short_answer",
            prompt: "为什么 0/0 不能直接当作极限？",
            answer: "SECRET ANSWER",
            explanation_rubric: { criteria: [{ description: "SECRET RUBRIC" }] },
            knowledge_core_id: "core-limit",
            origin: "generated",
            source_refs: [{ title: "高等数学", section: "2.3 极限", page: 41 }],
          }],
        },
      },
    };
    const listDraftPage = vi.fn().mockResolvedValue({
      items: [draft], total: 1, kindCounts: { quiz: 1 }, returned: 1, limit: 50, offset: 0, truncated: false,
    });
    const loadArtifactDetail = vi.fn().mockResolvedValue(detail);
    const setArtifactStatus = vi.fn().mockResolvedValue(undefined);
    const runSemanticReview = vi.fn();
    const onActivated = vi.fn();
    const repository = {
      listDraftPage,
      loadArtifactDetail,
      setArtifactStatus,
      runSemanticReview,
    } as unknown as StudyRepository;
    render(
      <I18nProvider><StudyRepositoryProvider repository={repository}><MemoryRouter>
        <StudyDraftProvider spaceId="space-a"><DraftInboxButton onActivated={onActivated} /></StudyDraftProvider>
      </MemoryRouter></StudyRepositoryProvider></I18nProvider>,
    );

    await user.click((await screen.findByLabelText("1 个草稿")).closest("button")!);
    await user.click(screen.getByRole("button", { name: /极限补充题/ }));
    expect(await screen.findByRole("heading", { name: "为什么 0/0 不能直接当作极限？" })).toBeInTheDocument();
    expect(screen.getByText("小娜生成")).toBeInTheDocument();
    expect(screen.getByText("高等数学 · 2.3 极限 · 第 41 页")).toBeInTheDocument();
    expect(screen.queryByText("SECRET ANSWER")).not.toBeInTheDocument();
    expect(screen.queryByText("SECRET RUBRIC")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "采用并开始" }));

    await waitFor(() => expect(setArtifactStatus).toHaveBeenCalledWith(
      "space-a", "draft-quiz", "active", expect.any(AbortSignal),
    ));
    expect(runSemanticReview).not.toHaveBeenCalled();
    expect(onActivated).toHaveBeenCalledWith(draft, detail);
    expect(screen.queryByRole("dialog", { name: "草稿箱" })).not.toBeInTheDocument();
  });
});
