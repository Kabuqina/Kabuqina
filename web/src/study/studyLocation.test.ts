// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { beforeEach, describe, expect, it, vi } from "vitest";
import type { StudyKnowledgePoint } from "../chat/study/study-api";
import {
  readStudyLocation,
  resolveKnowledgeCore,
  selectKnowledgeCore,
  studyContinueMeta,
  studyContinueTitle,
  switchStudyMode,
  updateStudyExercise,
  updateStudyPracticeState,
} from "./studyLocation";

const points: StudyKnowledgePoint[] = [
  { item_id: "core-1", artifact_id: "deck-1", front: "极限唯一性", gist: "极限若存在则唯一", captured: true },
  { item_id: "core-2", artifact_id: "deck-1", front: "无穷小", gist: "趋于零的量", captured: true },
];

describe("Study location", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.useRealTimers();
  });

  it("keeps one knowledge-core cursor while switching between learn and practice", () => {
    selectKnowledgeCore("course-a", points[1], "learn");
    switchStudyMode("course-a", "practice");
    expect(readStudyLocation("course-a")).toMatchObject({
      page: "practice",
      knowledgeCoreId: "core-2",
      knowledgeCoreTitle: "无穷小",
    });
  });

  it("remembers the most recent exercise independently for each core", () => {
    updateStudyExercise("course-a", points[0], "exercise-a");
    updateStudyExercise("course-a", points[1], "exercise-b");
    selectKnowledgeCore("course-a", points[0], "practice");
    expect(readStudyLocation("course-a")).toMatchObject({
      knowledgeCoreId: "core-1",
      exerciseId: "exercise-a",
      exerciseByCore: { "core-1": "exercise-a", "core-2": "exercise-b" },
    });
  });

  it("keeps course bookmarks and per-core exercises strictly isolated", () => {
    updateStudyExercise("course-a", points[0], "exercise-a");
    updateStudyPracticeState("course-a", points[0], "exercise-a", "needs_revision");
    updateStudyExercise("course-b", points[1], "exercise-b");

    expect(readStudyLocation("course-a")).toMatchObject({
      courseId: "course-a",
      knowledgeCoreId: "core-1",
      exerciseId: "exercise-a",
      activity: "needs_revision",
      exerciseByCore: { "core-1": "exercise-a" },
    });
    expect(readStudyLocation("course-b")).toMatchObject({
      courseId: "course-b",
      knowledgeCoreId: "core-2",
      exerciseId: "exercise-b",
      activity: "ready",
      exerciseByCore: { "core-2": "exercise-b" },
    });
  });

  it("starts a new course at its first core but degrades a stale core to the plan", () => {
    selectKnowledgeCore("course-a", points[1], "learn");
    expect(resolveKnowledgeCore("course-b", points)).toEqual({ point: points[0], index: 0, recovered: false });
    expect(resolveKnowledgeCore("course-a", [points[0]])).toBeNull();
    expect(readStudyLocation("course-a")).toMatchObject({
      page: "plan",
      exerciseByCore: {},
    });
    expect(readStudyLocation("course-a")?.knowledgeCoreId).toBeUndefined();
  });

  it("projects answer and check state into the single continue bookmark", () => {
    selectKnowledgeCore("course-a", points[0], "learn", { outlineLabel: "第一章 · 极限" });
    updateStudyPracticeState("course-a", points[0], "exercise-a", "dirty");
    const draft = readStudyLocation("course-a");
    expect(draft).not.toBeNull();
    expect(studyContinueTitle(draft!)).toBe("极限唯一性 · 草稿");
    expect(studyContinueMeta(draft!)).toBe("第一章 · 极限 · 练习 · 草稿未检查");

    updateStudyPracticeState("course-a", points[0], "exercise-a", "needs_revision");
    expect(readStudyLocation("course-a")).toMatchObject({
      page: "practice",
      knowledgeCoreId: "core-1",
      exerciseId: "exercise-a",
      activity: "needs_revision",
    });
  });

  it("preserves the plan range while learn and practice share the core", () => {
    selectKnowledgeCore("course-a", points[1], "learn", {
      outlineLabel: "第二章 · 无穷小",
      outlineNodeId: "section-small",
      planItemId: "plan-2",
    });
    switchStudyMode("course-a", "practice");
    selectKnowledgeCore("course-a", points[1], "practice");
    expect(readStudyLocation("course-a")).toMatchObject({
      knowledgeCoreId: "core-2",
      outlineLabel: "第二章 · 无穷小",
      outlineNodeId: "section-small",
      planItemId: "plan-2",
    });
  });

  it("does not publish a second location change when the cursor is unchanged", () => {
    const onChange = vi.fn();
    window.addEventListener("kabuqina-study-location-change", onChange);
    const first = selectKnowledgeCore("course-a", points[0], "learn");
    const second = selectKnowledgeCore("course-a", points[0], "learn");
    window.removeEventListener("kabuqina-study-location-change", onChange);

    expect(second).toEqual(first);
    expect(onChange).toHaveBeenCalledTimes(1);
  });
});
