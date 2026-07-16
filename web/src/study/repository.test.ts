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

  it("loads only flyleaf active state from the requested URL space", async () => {
    const studentState = vi.fn().mockResolvedValue({
      state: { artifact_id: "active", status: "active", payload: { course: "Physics" } },
    });
    const repository = createStudyRepository({ studentState });

    await expect(repository.loadFlyleaf("space-b", new AbortController().signal)).resolves.toMatchObject({
      active: { artifact_id: "active" },
    });
    expect(studentState).toHaveBeenCalledWith("space-b");
  });

  it("loads bounded M5 summaries and knowledge points independently", async () => {
    const activeM5Summaries = vi.fn().mockImplementation(async (_spaceId: string, kind: string) => ({
      items: kind === "knowledge_base"
        ? [{ artifact_id: "kb", kind: "knowledge_base", title: "KB", status: "active" }]
        : [],
      count: kind === "knowledge_base" ? 1 : 0,
      counts: {}, kind_counts: {}, returned: kind === "knowledge_base" ? 1 : 0,
      limit: 100, offset: 0, truncated: false,
    }));
    const knowledgePoints = vi.fn().mockRejectedValue({ status: null, code: "desk_transport_error", detail: "private" });
    const repository = createStudyRepository({ activeM5Summaries, knowledgePoints });

    await expect(repository.loadLearnHome("space-b", new AbortController().signal)).resolves.toEqual({
      artifacts: [{ artifact_id: "kb", kind: "knowledge_base", title: "KB", status: "active" }],
      knowledgePoints: [], unavailable: ["knowledgePoints"],
    });
    expect(activeM5Summaries.mock.calls).toEqual([
      ["space-b", "knowledge_base"],
      ["space-b", "resource_pack"],
      ["space-b", "tutoring_note"],
    ]);
    expect(knowledgePoints).toHaveBeenCalledWith("space-b");
  });

  it("reports the exact M5 kind whose bounded query is unavailable", async () => {
    const activeM5Summaries = vi.fn().mockImplementation(async (_spaceId: string, kind: string) => {
      if (kind === "resource_pack") throw new Error("offline");
      return {
        items: kind === "knowledge_base"
          ? [{ artifact_id: "kb", kind: "knowledge_base", title: "KB", status: "active" }]
          : [],
        count: kind === "knowledge_base" ? 1 : 0,
        counts: {}, kind_counts: {}, returned: kind === "knowledge_base" ? 1 : 0,
        limit: 100, offset: 0, truncated: false,
      };
    });
    const repository = createStudyRepository({
      activeM5Summaries,
      knowledgePoints: vi.fn().mockResolvedValue({ items: [] }),
    });

    await expect(repository.loadLearnHome("space-b", new AbortController().signal)).resolves.toEqual({
      artifacts: [{ artifact_id: "kb", kind: "knowledge_base", title: "KB", status: "active" }],
      knowledgePoints: [],
      unavailableKinds: ["resource_pack"],
    });
  });

  it("uses the explicit URL space for M5 detail, audit, and review", async () => {
    const artifactDetail = vi.fn().mockResolvedValue({ artifact: {
      artifact_id: "m5-a", kind: "knowledge_base", title: "Title", version: 1, status: "draft", review: { mode: "semantic", status: "pending" }, envelope: { payload: {} },
    } });
    const artifactSourceAudit = vi.fn().mockResolvedValue({ artifact_id: "m5-a", source_refs: [{ origin: "safe" }] });
    const artifactSemanticReview = vi.fn().mockResolvedValue({ artifact_id: "m5-a", status: "passed", reviewed: true });
    const repository = createStudyRepository({ artifactDetail, artifactSourceAudit, artifactSemanticReview });
    const signal = new AbortController().signal;

    await expect(repository.loadArtifactDetail("space-b", "m5-a", signal)).resolves.toMatchObject({ artifactId: "m5-a", kind: "knowledge_base" });
    await expect(repository.loadSourceAudit("space-b", "m5-a", signal)).resolves.toEqual([{ origin: "safe" }]);
    await expect(repository.runSemanticReview("space-b", "m5-a", signal)).resolves.toBe("passed");
    expect(artifactDetail).toHaveBeenCalledWith("space-b", "m5-a");
    expect(artifactSourceAudit).toHaveBeenCalledWith("space-b", "m5-a");
    expect(artifactSemanticReview).toHaveBeenCalledWith("space-b", "m5-a");
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
    const practiceSource = vi.fn().mockResolvedValue({
      source: { artifact_id: "quiz-1", item_ids: ["item-1"] },
    });
    const repository = createStudyRepository({ flashcards, quizzes, practiceSource });
    const signal = new AbortController().signal;

    await expect(repository.loadPracticeHome("space-b", signal)).resolves.toMatchObject({
      dueCards: [{ item_id: "card-due" }],
    });
    await expect(repository.resolvePracticeSource("space-b", "activity-1", signal)).resolves.toEqual({
      artifact_id: "quiz-1", item_ids: ["item-1"],
    });
    expect(flashcards).toHaveBeenNthCalledWith(1, "space-b", false);
    expect(flashcards).toHaveBeenNthCalledWith(2, "space-b", true);
    expect(quizzes).toHaveBeenCalledWith("space-b");
    expect(practiceSource).toHaveBeenCalledWith("space-b", "activity-1");
  });

  it("degrades only unavailable practice sections instead of hiding ready quizzes", async () => {
    const repository = createStudyRepository({
      flashcards: vi.fn().mockRejectedValue(new Error("offline")),
      quizzes: vi.fn().mockResolvedValue({ quizzes: [{
        artifact_id: "quiz-ready", kind: "quiz", title: "Ready", status: "active",
      }] }),
    });

    await expect(repository.loadPracticeHome("space-b", new AbortController().signal)).resolves.toEqual({
      cards: [], dueCards: [], quizzes: [{ artifact_id: "quiz-ready", kind: "quiz", title: "Ready", status: "active" }],
      unavailable: ["cards"],
    });
  });

  it("rejects when every practice section is unavailable so the page can retry", async () => {
    const unavailable = vi.fn().mockRejectedValue({
      status: null, code: "desk_transport_error", detail: "private",
    });
    const repository = createStudyRepository({
      flashcards: unavailable,
      quizzes: unavailable,
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
