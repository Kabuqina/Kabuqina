// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from "vitest";
import { parseLearnArtifact } from "./learnArtifact";
import type { StudyArtifactDetail } from "./repository";

function detail(kind: string, payload: unknown): StudyArtifactDetail {
  return { artifactId: "artifact-a", kind, title: "Private title", version: 1, status: "active", review: {}, envelope: { payload } };
}

describe("parseLearnArtifact", () => {
  it("keeps only the explicit knowledge-base contract", () => {
    expect(parseLearnArtifact(detail("knowledge_base", {
      concepts: [{ term: "Vector", explanation: "Direction and magnitude", hidden: "not rendered" }, { term: "", explanation: "bad" }],
    }))).toEqual({ kind: "knowledge_base", concepts: [{ term: "Vector", explanation: "Direction and magnitude" }] });
  });

  it("maps resource and tutoring contracts without passing unknown fields through", () => {
    expect(parseLearnArtifact(detail("resource_pack", { resources: [{ title: "Official guide", purpose: "Reference", credibility: "Primary", url: "https://private" }] }))).toEqual({
      kind: "resource_pack", resources: [{ title: "Official guide", purpose: "Reference", credibility: "Primary" }],
    });
    expect(parseLearnArtifact(detail("tutoring_note", { goal: "Understand", hints: ["Draw it"], misconceptions: ["Not a scalar"], next_steps: ["Practise"], prompt: "private" }))).toEqual({
      kind: "tutoring_note", goal: "Understand", hints: ["Draw it"], misconceptions: ["Not a scalar"], nextSteps: ["Practise"],
    });
  });

  it("fails closed for malformed or unrelated payloads", () => {
    expect(parseLearnArtifact(detail("knowledge_base", { concepts: [{ term: "Only term" }] }))).toBeNull();
    expect(parseLearnArtifact(detail("quiz", { concepts: [{ term: "x", explanation: "y" }] }))).toBeNull();
  });
});
