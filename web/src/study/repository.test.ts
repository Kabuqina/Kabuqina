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
