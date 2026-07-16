// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

export const LEGACY_STUDY_CONTEXT_STORAGE_KEY = "kabuqina.study.context.v1";
const LEGACY_FIELD_LIMIT = 800;
const LEGACY_FIELDS = [
  "course",
  "goal",
  "profileSummary",
  "weakPoints",
  "preferences",
  "progressNotes",
  "assessmentEvidence",
  "currentStage",
  "generatedResources",
  "tutoringNotes",
  "evaluationSummary",
  "nextAdjustment",
] as const;

export type LegacyStudyContext = Record<(typeof LEGACY_FIELDS)[number], string>;

function browserStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function readLegacyStudyContext(storage: Storage | null = browserStorage()): LegacyStudyContext | null {
  try {
    const parsed = JSON.parse(storage?.getItem(LEGACY_STUDY_CONTEXT_STORAGE_KEY) ?? "null") as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return null;
    const raw = parsed as Record<string, unknown>;
    const context = Object.fromEntries(LEGACY_FIELDS.map((field) => [
      field,
      typeof raw[field] === "string" ? raw[field].trim().slice(0, LEGACY_FIELD_LIMIT) : "",
    ])) as LegacyStudyContext;
    return Object.values(context).some(Boolean) ? context : null;
  } catch {
    return null;
  }
}

export async function migrateLegacyStudyContext(
  migrate: (context: LegacyStudyContext) => Promise<unknown>,
  storage: Storage | null = browserStorage(),
): Promise<boolean> {
  const context = readLegacyStudyContext(storage);
  if (!context) return false;
  await migrate(context);
  try {
    storage?.removeItem(LEGACY_STUDY_CONTEXT_STORAGE_KEY);
  } catch {
    // The backend marker makes a later retry idempotent; storage cleanup is best effort.
  }
  return true;
}
