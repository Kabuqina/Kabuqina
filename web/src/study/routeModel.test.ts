// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from "vitest";
import { parseStudyPath, studyPath } from "./routeModel";

describe("study route model", () => {
  it.each([
    ["/study", { kind: "root" }],
    ["/study/space-a", { kind: "space", spaceId: "space-a" }],
    ["/study/space-a/learn", { kind: "page", spaceId: "space-a", page: "learn" }],
    ["/study/space-a/wrong", { kind: "not-found", spaceId: "space-a" }],
  ])("parses %s", (path, expected) => {
    expect(parseStudyPath(path)).toEqual(expected);
  });

  it("encodes space ids in canonical paths", () => {
    expect(studyPath("math notes", "plan")).toBe("/study/math%20notes/plan");
  });
});
