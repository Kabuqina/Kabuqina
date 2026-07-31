// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { StudyLearningMap, StudySharedLocation } from "../chat/study/study-api";
import type { StudyRepository } from "./repository";
import { readStudyLocation, selectKnowledgeCore } from "./studyLocation";
import { useStudyLocationSync } from "./studyLocationSync";

const map: StudyLearningMap = {
  revision: 7,
  outlineStatus: "ready",
  outlineNodes: [],
  knowledgeCores: [
    { id: "core-1", itemId: "card-1", artifactId: "deck-1", front: "极限唯一性", gist: "若存在则唯一", captured: true, outlineNodeId: null, order: 0 },
    { id: "core-2", itemId: "card-2", artifactId: "deck-1", front: "无穷小", gist: "趋于零的量", captured: true, outlineNodeId: null, order: 1 },
  ],
  exerciseLinks: [
    { knowledgeCoreId: "core-2", quizArtifactId: "quiz-1", exerciseId: "question-2", origin: "source", sourceRefs: [], order: 0 },
  ],
};

const serverLocation: StudySharedLocation = {
  revision: 3,
  mapRevision: 7,
  page: "practice",
  knowledgeCoreId: "core-2",
  outlineNodeId: null,
  planItemId: "plan-2",
  planOutlineNodeId: null,
  exerciseId: "question-2",
  exerciseByCore: { "core-2": "question-2" },
  stale: false,
  updatedAt: "2026-07-30T08:00:00Z",
};

function Harness({ repository }: { repository: StudyRepository }) {
  useStudyLocationSync(repository, "course-a");
  return null;
}

describe("Study server location sync", () => {
  beforeEach(() => localStorage.clear());

  it("hydrates the local recovery projection from the revisioned server cursor", async () => {
    const repository = {
      loadLearningMap: vi.fn().mockResolvedValue(map),
      loadSharedLocation: vi.fn().mockResolvedValue(serverLocation),
      saveSharedLocation: vi.fn(),
    } as unknown as StudyRepository;
    render(<Harness repository={repository} />);

    await waitFor(() => expect(readStudyLocation("course-a")).toMatchObject({
      page: "practice",
      knowledgeCoreId: "core-2",
      knowledgeCoreTitle: "无穷小",
      exerciseId: "question-2",
      planItemId: "plan-2",
    }));
    expect(repository.saveSharedLocation).not.toHaveBeenCalled();
  });

  it("publishes a local cursor move with server and map revisions", async () => {
    const saveSharedLocation = vi.fn().mockImplementation((input) => Promise.resolve({
      ...serverLocation,
      revision: 4,
      page: input.page,
      knowledgeCoreId: input.knowledgeCoreId,
      planItemId: input.planItemId ?? null,
      exerciseId: input.exerciseId ?? null,
      exerciseByCore: {},
    }));
    const repository = {
      loadLearningMap: vi.fn().mockResolvedValue(map),
      loadSharedLocation: vi.fn().mockResolvedValue(serverLocation),
      saveSharedLocation,
    } as unknown as StudyRepository;
    render(<Harness repository={repository} />);
    await waitFor(() => expect(readStudyLocation("course-a")?.knowledgeCoreId).toBe("core-2"));

    selectKnowledgeCore("course-a", {
      item_id: "core-1", artifact_id: "deck-1", front: "极限唯一性", gist: "若存在则唯一", captured: true,
    }, "learn", { planItemId: "plan-1" });

    await waitFor(() => expect(saveSharedLocation).toHaveBeenCalledWith({
      spaceId: "course-a",
      expectedRevision: 3,
      expectedMapRevision: 7,
      page: "learn",
      knowledgeCoreId: "core-1",
      planItemId: "plan-1",
    }, expect.any(AbortSignal)));
  });
});
