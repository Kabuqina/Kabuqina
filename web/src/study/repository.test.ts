// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it, vi } from "vitest";
import { createStudyRepository, normalizeRepositoryError } from "./repository";

const spacesResponse = {
  currentSpaceId: "space-a",
  spaces: [{ space_id: "space-a", title: "Linear Algebra", status: "active", is_current: true }],
};

describe("StudyRepository", () => {
  it("maps spaces and requests the draft summary for the requested space", async () => {
    const draftSummary = vi.fn().mockResolvedValue({
      items: [
        { artifact_id: "d1", kind: "flashcard_deck", title: "private", version: 1, status: "draft" },
        { artifact_id: "d2", kind: "quiz", title: "private", version: 1, status: "draft" },
      ],
      count: 2,
      counts: { active: 0, archived: 0, draft: 2, rejected: 0 },
      kind_counts: { flashcard_deck: 1, quiz: 1 },
      returned: 2,
      limit: 100,
      offset: 0,
      truncated: false,
    });
    const repository = createStudyRepository({
      spaces: vi.fn().mockResolvedValue(spacesResponse),
      selectSpace: vi.fn().mockResolvedValue(spacesResponse),
      draftSummary,
    });
    const signal = new AbortController().signal;

    await expect(repository.listSpaces(signal)).resolves.toEqual({
      currentSpaceId: "space-a",
      spaces: [{ id: "space-a", title: "Linear Algebra", status: "active", isCurrent: true }],
    });
    await expect(repository.listDrafts("space-b", signal)).resolves.toEqual({
      total: 2,
      kindCounts: { flashcard_deck: 1, quiz: 1 },
    });
    expect(draftSummary).toHaveBeenCalledWith("space-b");
  });

  it("does not commit a result after cancellation", async () => {
    let resolve!: (value: typeof spacesResponse) => void;
    const repository = createStudyRepository({
      spaces: () => new Promise((done) => { resolve = done; }),
      selectSpace: vi.fn(),
      draftSummary: vi.fn(),
    });
    const controller = new AbortController();
    const pending = repository.listSpaces(controller.signal);
    controller.abort();
    resolve(spacesResponse);
    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
  });

  it("loads flyleaf active and draft state from the requested URL space", async () => {
    const studentState = vi.fn().mockResolvedValue({
      state: { artifact_id: "active", status: "active", payload: { course: "Physics" } },
    });
    const studentDraftSummary = vi.fn().mockResolvedValue({
      items: [{ artifact_id: "draft", kind: "student_state", title: "Draft", status: "draft" }],
      count: 1,
      counts: { draft: 1 },
      kind_counts: { student_state: 1 },
      returned: 1,
      limit: 1,
      offset: 0,
      truncated: false,
    });
    const artifactDetail = vi.fn().mockResolvedValue({
      artifact: {
        artifact_id: "draft",
        kind: "student_state",
        title: "Draft",
        version: 1,
        status: "draft",
        envelope: { payload: { course: "Draft physics" } },
      },
    });
    const repository = createStudyRepository({ studentState, studentDraftSummary, artifactDetail });

    await expect(repository.loadFlyleaf("space-b", new AbortController().signal)).resolves.toMatchObject({
      active: { artifact_id: "active" },
      draft: { artifact_id: "draft", payload: { course: "Draft physics" } },
    });
    expect(studentState).toHaveBeenCalledWith("space-b");
    expect(studentDraftSummary).toHaveBeenCalledWith("space-b");
    expect(artifactDetail).toHaveBeenCalledWith("space-b", "draft");
  });

  it("selects the newest active plan and scopes its item query", async () => {
    const learningPlans = vi.fn().mockResolvedValue({ plans: [
      { artifact_id: "older", kind: "learning_plan", title: "Old", status: "active", updated_at: "2026-01-01" },
      { artifact_id: "newer", kind: "learning_plan", title: "New", status: "active", updated_at: "2026-02-01" },
    ] });
    const planItems = vi.fn().mockResolvedValue({ items: [{ item_id: "next" }] });
    const repository = createStudyRepository({ learningPlans, planItems });

    await expect(repository.loadPlan("space-b", new AbortController().signal)).resolves.toMatchObject({
      plan: { artifact_id: "newer" },
      items: [{ item_id: "next" }],
    });
    expect(planItems).toHaveBeenCalledWith("space-b", "newer");
  });

  it("uses the server-bounded evaluation projection without a detail round trip", async () => {
    const evaluations = vi.fn().mockResolvedValue({ evaluations: [{
      artifact_id: "evaluation-newest",
      title: "Bounded evaluation",
      observations: ["Keep practising"],
      weak_points: ["vectors"],
      suggestions: ["Retry"],
      evidence_refs: [],
    }] });
    const repository = createStudyRepository({ evaluations });

    await expect(
      repository.loadLatestEvaluation("space-b", new AbortController().signal),
    ).resolves.toMatchObject({ evaluation: { artifact_id: "evaluation-newest" } });
    expect(evaluations).toHaveBeenCalledWith("space-b");
  });

  it("loads practice data and retry sources from the requested URL space", async () => {
    const flashcards = vi.fn()
      .mockResolvedValueOnce({ cards: [{ item_id: "card-all", front: "all", back: "a" }] })
      .mockResolvedValueOnce({ cards: [{ item_id: "card-due", front: "due", back: "d" }] });
    const quizzes = vi.fn().mockResolvedValue({ quizzes: [{
      artifact_id: "quiz-1", kind: "quiz", title: "Private title", status: "active",
    }] });
    const practiceDrafts = vi.fn().mockResolvedValue({
      items: [{ artifact_id: "draft-1", kind: "quiz", title: "Draft", status: "draft" }],
      count: 1, counts: { draft: 1 }, kind_counts: { quiz: 1 },
      returned: 1, limit: 50, offset: 0, truncated: false,
    });
    const practiceSource = vi.fn().mockResolvedValue({
      source: { artifact_id: "quiz-1", item_ids: ["item-1"] },
    });
    const repository = createStudyRepository({ flashcards, quizzes, practiceDrafts, practiceSource });
    const signal = new AbortController().signal;

    await expect(repository.loadPracticeHome("space-b", signal)).resolves.toMatchObject({
      dueCards: [{ item_id: "card-due" }],
      drafts: [{ artifact_id: "draft-1" }],
    });
    await expect(repository.resolvePracticeSource("space-b", "activity-1", signal)).resolves.toEqual({
      artifact_id: "quiz-1", item_ids: ["item-1"],
    });
    expect(flashcards).toHaveBeenNthCalledWith(1, "space-b", false);
    expect(flashcards).toHaveBeenNthCalledWith(2, "space-b", true);
    expect(quizzes).toHaveBeenCalledWith("space-b");
    expect(practiceDrafts).toHaveBeenCalledWith("space-b");
    expect(practiceSource).toHaveBeenCalledWith("space-b", "activity-1");
  });

  it("degrades only unavailable practice sections instead of hiding ready quizzes", async () => {
    const repository = createStudyRepository({
      flashcards: vi.fn().mockRejectedValue(new Error("offline")),
      quizzes: vi.fn().mockResolvedValue({ quizzes: [{
        artifact_id: "quiz-ready", kind: "quiz", title: "Ready", status: "active",
      }] }),
      practiceDrafts: vi.fn().mockRejectedValue(new Error("offline")),
    });

    await expect(repository.loadPracticeHome("space-b", new AbortController().signal)).resolves.toEqual({
      cards: [], dueCards: [], quizzes: [{ artifact_id: "quiz-ready", kind: "quiz", title: "Ready", status: "active" }], drafts: [],
      unavailable: ["cards", "drafts"],
    });
  });

  it("rejects when every practice section is unavailable so the page can retry", async () => {
    const unavailable = vi.fn().mockRejectedValue({
      status: null, code: "desk_transport_error", detail: "private",
    });
    const repository = createStudyRepository({
      flashcards: unavailable,
      quizzes: unavailable,
      practiceDrafts: unavailable,
    });

    await expect(repository.loadPracticeHome("space-b", new AbortController().signal)).rejects.toMatchObject({
      code: "unavailable",
    });
  });

  it("maps only stable error prefixes", () => {
    expect(normalizeRepositoryError("invalid study id").code).toBe("invalid");
    expect(normalizeRepositoryError("space_not_found: hidden detail").code).toBe("not-found");
    expect(normalizeRepositoryError("study_conflict: hidden detail").code).toBe("conflict");
    expect(normalizeRepositoryError("Hermes is not ready yet. Wait.").code).toBe("unavailable");
    expect(normalizeRepositoryError("request_failed: arbitrary prose").code).toBe("unknown");
  });

  it("maps the structured desk bridge contract by code and status", () => {
    expect(normalizeRepositoryError({ status: 400, code: "study_invalid_request", detail: "private" }).code).toBe("invalid");
    expect(normalizeRepositoryError({ status: 404, code: "study_not_found", detail: "private" }).code).toBe("not-found");
    expect(normalizeRepositoryError({ status: 409, code: "study_conflict", detail: "private" }).code).toBe("conflict");
    expect(normalizeRepositoryError({ status: null, code: "desk_transport_error", detail: "private" }).code).toBe("unavailable");
    expect(normalizeRepositoryError({ status: 503, code: "study_internal_error", detail: "private" }).code).toBe("unknown");
  });
});
