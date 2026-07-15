// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../lib/i18n";
import { answerConfirm, getConfirmSnapshot } from "../lib/confirmDialog";
import type { StudyRepository } from "./repository";
import { StudyRepositoryProvider } from "./repositoryContext";
import { StudyShell } from "./StudyShell";

const spaces = {
  currentSpaceId: "space-a",
  spaces: [
    { id: "space-a", title: "Linear Algebra", status: "active", isCurrent: true },
    { id: "space-b", title: "Physics", status: "active", isCurrent: false },
  ],
};

function Location() { return <output data-testid="location">{useLocation().pathname}</output>; }

function makeRepository(repositoryOverrides: Partial<StudyRepository> = {}): StudyRepository {
  return {
    listSpaces: vi.fn().mockResolvedValue(spaces),
    selectSpace: vi.fn().mockResolvedValue({ ...spaces, currentSpaceId: "space-b" }),
    listDrafts: vi.fn().mockResolvedValue({
      total: 2,
      kindCounts: { flashcard_deck: 1, quiz: 1 },
    }),
    listDraftPage: vi.fn().mockResolvedValue({
      items: [
        { artifact_id: "draft-deck", kind: "flashcard_deck", title: "Deck draft", status: "draft" },
        { artifact_id: "draft-quiz", kind: "quiz", title: "Quiz draft", status: "draft" },
      ], total: 2, kindCounts: { flashcard_deck: 1, quiz: 1 }, returned: 2, limit: 50, offset: 0, truncated: false,
    }),
    loadLearnHome: vi.fn().mockResolvedValue({ artifacts: [], knowledgePoints: [] }),
    loadArtifactDetail: vi.fn(), loadSourceAudit: vi.fn(), runSemanticReview: vi.fn(),
    loadFlyleaf: vi.fn(),
    migrateLegacyContext: vi.fn(),
    setArtifactStatus: vi.fn(),
    loadPlan: vi.fn(),
    completePlanItem: vi.fn(),
    skipPlanItem: vi.fn(),
    loadWrongbook: vi.fn(),
    loadLatestEvaluation: vi.fn(),
    loadActivities: vi.fn(),
    loadPracticeHome: vi.fn(), loadQuizQuestions: vi.fn(), reviewFlashcard: vi.fn(),
    submitQuiz: vi.fn(), generatePracticeDraft: vi.fn(), resolvePracticeSource: vi.fn(),
    ...repositoryOverrides,
  };
}

function renderShell(
  repositoryOverrides: Partial<StudyRepository> = {},
  { spaceId = "space-a", page = "learn" }: {
    spaceId?: string;
    page?: "flyleaf" | "plan" | "learn" | "practice" | "evaluate";
  } = {},
) {
  const repository = makeRepository(repositoryOverrides);
  render(
    <I18nProvider>
      <StudyRepositoryProvider repository={repository}>
        <MemoryRouter initialEntries={[`/study/${spaceId}/${page}`]}>
          <Location />
          <StudyShell spaces={spaces} spaceId={spaceId} page={page} />
        </MemoryRouter>
      </StudyRepositoryProvider>
    </I18nProvider>,
  );
  return repository;
}

afterEach(() => {
  if (getConfirmSnapshot()) answerConfirm(false);
  vi.unstubAllGlobals();
});

describe("StudyShell", () => {
  it("renders lifecycle links and privacy-bounded cross-kind draft counts", async () => {
    const user = userEvent.setup();
    renderShell();
    expect(screen.getByRole("navigation", { name: "学习阶段" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "学习" })).toHaveAttribute("aria-current", "page");
    const drafts = await screen.findByLabelText("2 个草稿");
    await user.click(drafts.closest("button")!);
    const popover = screen.getByRole("dialog", { name: "草稿箱" });
    expect(popover).toHaveTextContent("Deck draft");
    expect(popover).toHaveTextContent("Quiz draft");
    expect(popover).not.toHaveTextContent("private");
  });

  it("uses the URL space for drafts when it differs from the backend current space", async () => {
    const listDraftPage = vi.fn().mockResolvedValue({
      items: [{ artifact_id: "draft-quiz", kind: "quiz", title: "Quiz draft", status: "draft" }],
      total: 1, kindCounts: { quiz: 1 }, returned: 1, limit: 50, offset: 0, truncated: false,
    });
    renderShell({ listDraftPage }, { spaceId: "space-b" });

    await screen.findByLabelText("1 个草稿");
    expect(listDraftPage).toHaveBeenCalledWith("space-b", 50, 0, expect.any(AbortSignal));
  });

  it("remounts the provider subtree before rendering a different URL space", async () => {
    const user = userEvent.setup();
    const repository = makeRepository({
      listDraftPage: vi.fn().mockResolvedValue({ items: [], total: 0, kindCounts: {}, returned: 0, limit: 50, offset: 0, truncated: false }),
      loadLearnHome: vi.fn().mockImplementation((spaceId: string) => spaceId === "space-a"
        ? Promise.resolve({ artifacts: [{ artifact_id: "artifact-a", kind: "knowledge_base", title: "A knowledge", status: "active" }], knowledgePoints: [] })
        : new Promise(() => undefined)),
      loadArtifactDetail: vi.fn().mockResolvedValue({ artifactId: "artifact-a", kind: "knowledge_base", title: "A knowledge", version: 1, status: "active", review: {}, envelope: { payload: { concepts: [{ term: "A TERM", explanation: "A PRIVATE BODY" }] } } }),
    });
    function Harness() {
      const [spaceId, setSpaceId] = useState("space-a");
      return <MemoryRouter><button type="button" onClick={() => setSpaceId("space-b")}>test switch</button><StudyRepositoryProvider repository={repository}><StudyShell spaces={spaces} spaceId={spaceId} page="learn" /></StudyRepositoryProvider></MemoryRouter>;
    }
    render(<I18nProvider><Harness /></I18nProvider>);

    expect(await screen.findByText("A PRIVATE BODY")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "test switch" }));
    expect(screen.queryByText("A PRIVATE BODY")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "学习" })).toBeInTheDocument();
  });

  it("keeps route and data when selecting a space fails", async () => {
    const user = userEvent.setup();
    renderShell({ selectSpace: vi.fn().mockRejectedValue(new Error("request_failed")) });
    await user.click(screen.getByRole("button", { name: /Linear Algebra/ }));
    await user.click(screen.getByRole("option", { name: "Physics" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("原学习空间已保留");
    expect(screen.getByTestId("location")).toHaveTextContent("/study/space-a/learn");
    expect(screen.getByRole("heading", { name: "学习" })).toBeInTheDocument();
  });

  it("moves to the selected space while preserving the current lifecycle page", async () => {
    const user = userEvent.setup();
    const repository = renderShell();
    await user.click(screen.getByRole("button", { name: /Linear Algebra/ }));
    await user.click(screen.getByRole("option", { name: "Physics" }));
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/study/space-b/learn"));
    expect(repository.selectSpace).toHaveBeenCalledWith("space-b", expect.any(AbortSignal));
  });

  it("uses a modal presentation in a narrow container and restores trigger focus on Escape", async () => {
    class NarrowResizeObserver {
      constructor(private callback: ResizeObserverCallback) {}
      observe() { this.callback([{ contentRect: { width: 480 } } as ResizeObserverEntry], this as unknown as ResizeObserver); }
      disconnect() {}
      unobserve() {}
    }
    vi.stubGlobal("ResizeObserver", NarrowResizeObserver);
    const user = userEvent.setup();
    renderShell();
    const trigger = screen.getByRole("button", { name: /Linear Algebra/ });
    await user.click(trigger);
    const modal = screen.getByRole("dialog", { name: "切换学习空间" });
    expect(modal).toHaveAttribute("aria-modal", "true");
    expect(modal.parentElement).toBe(document.body);
    expect(modal.closest(".kq-study-topbar")).toBeNull();
    expect(screen.getByRole("option", { name: "Linear Algebra" })).toBeDisabled();
    const close = screen.getByRole("button", { name: "取消" });
    expect(close).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("option", { name: "Physics" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: "开新本" })).toHaveFocus();
    await user.tab();
    expect(close).toHaveFocus();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("closes wide popovers when a pointer starts outside", async () => {
    const user = userEvent.setup();
    renderShell();

    await user.click(screen.getByRole("button", { name: /Linear Algebra/ }));
    expect(screen.getByRole("listbox", { name: "切换学习空间" })).toBeInTheDocument();
    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole("listbox", { name: "切换学习空间" })).not.toBeInTheDocument();

    const drafts = await screen.findByLabelText("2 个草稿");
    await user.click(drafts.closest("button")!);
    expect(screen.getByRole("dialog", { name: "草稿箱" })).toBeInTheDocument();
    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole("dialog", { name: "草稿箱" })).not.toBeInTheDocument();
  });

  it("requires confirmation before a dirty practice changes space or lifecycle page", async () => {
    const user = userEvent.setup();
    const repository = renderShell({
      loadPracticeHome: vi.fn().mockResolvedValue({
        cards: [], dueCards: [], quizzes: [{
          artifact_id: "quiz-1", kind: "quiz", title: "Vectors quiz", status: "active",
        }],
      }),
      loadQuizQuestions: vi.fn().mockResolvedValue([{
        item_id: "question-1", artifact_id: "quiz-1", type: "choice", prompt: "Pick one", options: ["A", "B"],
      }]),
    }, { page: "practice" });
    await user.click(await screen.findByRole("button", { name: "Vectors quiz" }));
    await user.click(await screen.findByRole("button", { name: "B" }));

    await user.click(screen.getByRole("button", { name: /Linear Algebra/ }));
    await user.click(screen.getByRole("option", { name: "Physics" }));
    expect(getConfirmSnapshot()?.title).toBe("放弃未提交的答案？");
    await act(async () => answerConfirm(false));
    expect(repository.selectSpace).not.toHaveBeenCalled();
    expect(screen.getByTestId("location")).toHaveTextContent("/study/space-a/practice");

    await user.click(screen.getByRole("link", { name: "评估" }));
    expect(getConfirmSnapshot()?.message).toContain("清除尚未提交的答案");
    await act(async () => answerConfirm(true));
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/study/space-a/evaluate"));
  });
});
