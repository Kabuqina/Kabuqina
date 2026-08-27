// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from "vitest";
import { isLegacyPageSlug, isSurfaceSlug, legacyToCanonical, parseStudyPath, studyPath } from "./routeModel";

describe("study route model", () => {
  it.each([
    ["/study", { kind: "root" }],
    ["/study/space-a", { kind: "space", spaceId: "space-a" }],
    ["/study/space-a/notebook", { kind: "surface", spaceId: "space-a", surface: "notebook" }],
    ["/study/space-a/cards", { kind: "surface", spaceId: "space-a", surface: "cards" }],
    ["/study/space-a/bookend", { kind: "surface", spaceId: "space-a", surface: "bookend" }],
    ["/study/space-a/flyleaf", { kind: "legacy", spaceId: "space-a", page: "flyleaf" }],
    ["/study/space-a/learn", { kind: "legacy", spaceId: "space-a", page: "learn" }],
    ["/study/space-a/practice", { kind: "legacy", spaceId: "space-a", page: "practice" }],
    ["/study/space-a/plan", { kind: "legacy", spaceId: "space-a", page: "plan" }],
    ["/study/space-a/evaluate", { kind: "legacy", spaceId: "space-a", page: "evaluate" }],
    ["/study/space-a/wrong", { kind: "not-found", spaceId: "space-a" }],
    ["/study/100%", { kind: "not-found" }],
    ["/study/%zz/notebook", { kind: "not-found" }],
  ])("parses %s", (path, expected) => {
    expect(parseStudyPath(path)).toEqual(expected);
  });

  it("encodes space ids in canonical surface paths", () => {
    expect(studyPath("math notes", "notebook")).toBe("/study/math%20notes/notebook");
  });

  it("maps legacy slugs to canonical surfaces with search params", () => {
    expect(studyPath("space-a", "flyleaf")).toBe("/study/space-a/notebook?view=flyleaf");
    expect(studyPath("space-a", "plan")).toBe("/study/space-a/bookend?view=plan");
    expect(studyPath("space-a", "learn")).toBe("/study/space-a/notebook?mode=learn");
    expect(studyPath("space-a", "practice")).toBe("/study/space-a/notebook?mode=practice");
    expect(studyPath("space-a", "evaluate")).toBe("/study/space-a/bookend?view=evaluate");
  });

  it("preserves extra search params when mapping legacy slugs", () => {
    expect(studyPath("space-a", "practice", "?source=wrongbook")).toBe(
      "/study/space-a/notebook?mode=practice&source=wrongbook",
    );
  });

  it("defaults to the notebook surface", () => {
    expect(studyPath("space-a")).toBe("/study/space-a/notebook");
  });

  it("classifies slugs correctly", () => {
    expect(isSurfaceSlug("notebook")).toBe(true);
    expect(isSurfaceSlug("learn")).toBe(false);
    expect(isLegacyPageSlug("learn")).toBe(true);
    expect(isLegacyPageSlug("notebook")).toBe(false);
  });

  it("exposes legacy redirect targets", () => {
    expect(legacyToCanonical("space-a", "flyleaf")).toEqual({
      pathname: "/study/space-a/notebook",
      search: "?view=flyleaf",
    });
  });
});
