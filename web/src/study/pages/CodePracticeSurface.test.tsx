// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from "vitest";
import { transcriptionDiffRange } from "./CodePracticeSurface";

describe("transcriptionDiffRange", () => {
  it("marks only the changed learner span and has a 20k bounded linear scan", () => {
    expect(transcriptionDiffRange("print('ok')", "print('no')")).toEqual({ from: 7, to: 9 });
    expect(transcriptionDiffRange("same", "same")).toBeNull();
    expect(transcriptionDiffRange("a".repeat(20_010), "a".repeat(20_000))).toBeNull();
  });
});
