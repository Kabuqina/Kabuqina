// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  LEGACY_STUDY_CONTEXT_STORAGE_KEY,
  migrateLegacyStudyContext,
  readLegacyStudyContext,
} from "./legacyStudyContextMigration";

describe("legacy study context migration adapter", () => {
  beforeEach(() => localStorage.clear());

  it("normalizes a bounded old-version sample", () => {
    localStorage.setItem(LEGACY_STUDY_CONTEXT_STORAGE_KEY, JSON.stringify({
      course: `  Calculus ${"x".repeat(900)}  `,
      goal: "Pass",
      ignored: "not forwarded",
    }));
    const context = readLegacyStudyContext();
    expect(context?.course).toHaveLength(800);
    expect(context?.goal).toBe("Pass");
    expect(context).not.toHaveProperty("ignored");
  });

  it("clears the old key only after confirmed migration", async () => {
    localStorage.setItem(LEGACY_STUDY_CONTEXT_STORAGE_KEY, JSON.stringify({ course: "Physics" }));
    const migrate = vi.fn().mockResolvedValue(false);
    await expect(migrateLegacyStudyContext(migrate)).resolves.toBe(true);
    expect(migrate).toHaveBeenCalledWith(expect.objectContaining({ course: "Physics" }));
    expect(localStorage.getItem(LEGACY_STUDY_CONTEXT_STORAGE_KEY)).toBeNull();
  });

  it("retains the old key byte-for-byte when migration fails", async () => {
    const raw = JSON.stringify({ course: "Legacy calculus", goal: "Pass" });
    localStorage.setItem(LEGACY_STUDY_CONTEXT_STORAGE_KEY, raw);
    await expect(migrateLegacyStudyContext(vi.fn().mockRejectedValue(new Error("offline")))).rejects.toThrow("offline");
    expect(localStorage.getItem(LEGACY_STUDY_CONTEXT_STORAGE_KEY)).toBe(raw);
  });
});
