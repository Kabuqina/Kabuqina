// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { StudyArtifactDetail, StudyM5Kind } from "./repository";

export type KnowledgeBaseContent = {
  kind: "knowledge_base";
  concepts: Array<{ term: string; explanation: string }>;
};

export type ResourcePackContent = {
  kind: "resource_pack";
  resources: Array<{ title: string; purpose: string; credibility?: string }>;
};

export type TutoringNoteContent = {
  kind: "tutoring_note";
  goal: string;
  hints: string[];
  misconceptions: string[];
  nextSteps: string[];
};

export type LearnArtifactContent = KnowledgeBaseContent | ResourcePackContent | TutoringNoteContent;

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function textList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map(text).filter(Boolean);
}

function payload(detail: StudyArtifactDetail): Record<string, unknown> | null {
  const value = detail.envelope.payload;
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function kind(detail: StudyArtifactDetail): StudyM5Kind | null {
  return detail.kind === "knowledge_base" || detail.kind === "resource_pack" || detail.kind === "tutoring_note"
    ? detail.kind
    : null;
}

/** Map one explicit artifact detail into the small, render-safe M5 contract. */
export function parseLearnArtifact(detail: StudyArtifactDetail): LearnArtifactContent | null {
  const content = payload(detail);
  const artifactKind = kind(detail);
  if (!content || !artifactKind) return null;
  if (artifactKind === "knowledge_base") {
    const concepts = Array.isArray(content.concepts)
      ? content.concepts.flatMap((value) => {
        if (!value || typeof value !== "object" || Array.isArray(value)) return [];
        const record = value as Record<string, unknown>;
        const term = text(record.term);
        const explanation = text(record.explanation);
        return term && explanation ? [{ term, explanation }] : [];
      })
      : [];
    return concepts.length ? { kind: artifactKind, concepts } : null;
  }
  if (artifactKind === "resource_pack") {
    const resources = Array.isArray(content.resources)
      ? content.resources.flatMap((value) => {
        if (!value || typeof value !== "object" || Array.isArray(value)) return [];
        const record = value as Record<string, unknown>;
        const title = text(record.title);
        const purpose = text(record.purpose);
        const credibility = text(record.credibility);
        return title && purpose ? [{ title, purpose, ...(credibility ? { credibility } : {}) }] : [];
      })
      : [];
    return resources.length ? { kind: artifactKind, resources } : null;
  }
  const goal = text(content.goal);
  const hints = textList(content.hints);
  if (!goal || !hints.length) return null;
  return {
    kind: artifactKind,
    goal,
    hints,
    misconceptions: textList(content.misconceptions),
    nextSteps: textList(content.next_steps),
  };
}
