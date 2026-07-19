// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { EvaluationPayload, StudentStatePayload } from "./study-api";
import { emptyStudyContext, normalizeStudyContext, type StudyContext } from "./studyStore";

export const LEGACY_CONTEXT_MIGRATION_REF = {
  origin: "legacy_local_storage",
  key: "kabuqina.study.context.v1",
};

function cleanText(value: unknown, limit = 800): string {
  return typeof value === "string" ? value.trim().slice(0, limit) : "";
}

function lines(value: unknown): string[] {
  const text = cleanText(value);
  if (!text) return [];
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of text.replaceAll("；", "\n").replaceAll(";", "\n").split(/\r?\n/)) {
    const item = raw.trim().replace(/^[-\s]+/, "");
    const key = item.toLocaleLowerCase();
    if (!item || seen.has(key)) continue;
    seen.add(key);
    result.push(item);
    if (result.length >= 24) break;
  }
  return result;
}

function joined(value: unknown): string {
  if (!Array.isArray(value)) return "";
  return value.filter((item): item is string => typeof item === "string" && Boolean(item.trim())).join("\n");
}

export function studyContextToStudentState(context: StudyContext): StudentStatePayload {
  const normalized = normalizeStudyContext(context);
  return {
    course: normalized.course,
    goals: lines(normalized.goal),
    preferences: {
      ...(normalized.profileSummary ? { profile_summary: normalized.profileSummary } : {}),
      ...(normalized.preferences ? { study_preferences: normalized.preferences } : {}),
    },
    constraints: [],
    progress_notes: [...lines(normalized.progressNotes), ...lines(normalized.generatedResources)]
      .filter((item, index, all) => all.findIndex((candidate) => candidate.toLocaleLowerCase() === item.toLocaleLowerCase()) === index)
      .slice(0, 24),
    current_stage: normalized.currentStage,
    next_adjustment: normalized.nextAdjustment,
  };
}

export function studyContextToEvaluation(context: StudyContext): EvaluationPayload | null {
  const normalized = normalizeStudyContext(context);
  const observations = [
    ...lines(normalized.evaluationSummary),
    ...lines(normalized.assessmentEvidence),
    ...lines(normalized.tutoringNotes),
  ].filter((item, index, all) => all.findIndex((candidate) => candidate.toLocaleLowerCase() === item.toLocaleLowerCase()) === index);
  const weakPoints = lines(normalized.weakPoints);
  const suggestions = lines(normalized.nextAdjustment);
  if (!observations.length && !weakPoints.length && !suggestions.length) return null;
  return {
    observations: observations.length ? observations : ["Learner-provided study context."],
    weak_points: weakPoints,
    suggestions,
    evidence_refs: [LEGACY_CONTEXT_MIGRATION_REF],
  };
}

export function backendPayloadsToStudyContext(
  state?: StudentStatePayload | null,
  evaluation?: EvaluationPayload | null,
): StudyContext {
  const preferences = state?.preferences || {};
  const observations = joined(evaluation?.observations);
  return normalizeStudyContext({
    ...emptyStudyContext(),
    course: state?.course || "",
    goal: joined(state?.goals),
    profileSummary: preferences.profile_summary || "",
    preferences: preferences.study_preferences || "",
    progressNotes: joined(state?.progress_notes),
    currentStage: state?.current_stage || "",
    weakPoints: joined(evaluation?.weak_points),
    evaluationSummary: observations,
    nextAdjustment: state?.next_adjustment || joined(evaluation?.suggestions),
  });
}
