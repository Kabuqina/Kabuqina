// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  STUDY_IA_AGGREGATE_KEY,
  createStudyIaRecorder,
  getStudyIaEnabled,
  localStudyIaSink,
  serializeStudyIaEvent,
  setStudyIaEnabled,
  studyIaCountBucket,
  type StudyIaEvent,
} from "./iaEvents";

describe("study IA events", () => {
  beforeEach(() => localStorage.clear());

  it("serializes only the finite, content-free schema", () => {
    const events: StudyIaEvent[] = [
      { name: "study.page.view", page: "learn", action: "view" },
      { name: "study.space.switch", action: "switch", success: true },
      { name: "study.resume", page: "plan", action: "resume" },
      { name: "study.wrongbook.open", page: "evaluate", action: "open", success: true, count_bucket: "two_to_five" },
      { name: "study.wrongbook.retry", page: "evaluate", action: "retry" },
      { name: "study.review.start", page: "practice", action: "start", count_bucket: "one" },
      { name: "study.review.complete", page: "practice", action: "complete", count_bucket: "six_plus" },
      { name: "study.draft.reviewed", action: "reviewed", success: false },
    ];

    for (const event of events) expect(serializeStudyIaEvent(event)).toBe(JSON.stringify(event));
    for (const [field, value] of Object.entries({
      space_id: "private-id",
      artifact_id: "private-id",
      title: "private title",
      answer: "private answer",
      source_refs: [{ uri: "private" }],
      prompt: "private prompt",
    })) {
      expect(serializeStudyIaEvent({ ...events[0], [field]: value })).toBeNull();
    }
    expect(serializeStudyIaEvent([])).toBeNull();
    expect(serializeStudyIaEvent({ ...events[0], payload: {} })).toBeNull();
    expect(serializeStudyIaEvent({ name: "study.unknown", action: "view" })).toBeNull();
    expect(serializeStudyIaEvent({ name: "study.page.view", page: "private-page", action: "view" })).toBeNull();
  });

  it("uses bounded count buckets", () => {
    expect([-1, 0, Number.NaN].map(studyIaCountBucket)).toEqual(["zero", "zero", "zero"]);
    expect([1, 2, 5, 6, 100].map(studyIaCountBucket)).toEqual(["one", "two_to_five", "two_to_five", "six_plus", "six_plus"]);
  });

  it("is default-off and erases local aggregates when disabled", () => {
    expect(getStudyIaEnabled()).toBe(false);
    localStudyIaSink({ name: "study.page.view", page: "flyleaf", action: "view" });
    expect(localStorage.getItem(STUDY_IA_AGGREGATE_KEY)).toBeNull();

    setStudyIaEnabled(true);
    localStudyIaSink({ name: "study.page.view", page: "flyleaf", action: "view" });
    localStudyIaSink({ name: "study.page.view", page: "flyleaf", action: "view" });
    const stored = localStorage.getItem(STUDY_IA_AGGREGATE_KEY) ?? "";
    expect(stored).not.toContain("private-title-sentinel");
    expect(Object.values(JSON.parse(stored).counters)).toEqual([2]);

    setStudyIaEnabled(false);
    expect(getStudyIaEnabled()).toBe(false);
    expect(localStorage.getItem(STUDY_IA_AGGREGATE_KEY)).toBeNull();
  });

  it("rejects invalid runtime events before they reach a sink", () => {
    const sink = vi.fn();
    const record = createStudyIaRecorder(sink);
    record({ name: "study.page.view", page: "learn", action: "view", prompt: "private-title-sentinel" } as StudyIaEvent);
    expect(sink).not.toHaveBeenCalled();
  });

  it("deduplicates explicit keys and fails open for sink errors", async () => {
    const sink = vi.fn()
      .mockImplementationOnce(() => { throw new Error("sync"); })
      .mockRejectedValueOnce(new Error("async"));
    const record = createStudyIaRecorder(sink);
    const event: StudyIaEvent = { name: "study.page.view", page: "plan", action: "view" };
    expect(() => record(event, { dedupeKey: "route-1" })).not.toThrow();
    record(event, { dedupeKey: "route-1" });
    record(event, { dedupeKey: "route-2" });
    await Promise.resolve();
    expect(sink).toHaveBeenCalledTimes(2);
  });
});
