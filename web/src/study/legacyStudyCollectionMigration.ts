// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

export const LEGACY_FLASHCARD_STORAGE_KEY = "kabuqina.study.flashcards.v1";
export const LEGACY_QUIZ_STORAGE_KEY = "kabuqina.study.quiz.v1";

type MigrationStatus = "absent" | "confirmed" | "cleanup-failed" | "failed" | "invalid";

export type LegacyStudyCollectionMigrationResult = {
  changed: boolean;
  retryNeeded: boolean;
  flashcards: MigrationStatus;
  quizzes: MigrationStatus;
};

export type LegacyStudyCollectionMigrators = {
  flashcards: (deck: unknown) => Promise<unknown>;
  quizzes: (quiz: unknown) => Promise<unknown>;
};

const cleanText = (value: unknown, limit: number) => (
  typeof value === "string" ? value.trim().slice(0, limit) : ""
);

function cleanStrings(value: unknown, limit: number, maxItems: number): string[] {
  if (!Array.isArray(value)) return [];
  const strings: string[] = [];
  const seen = new Set<string>();
  for (const candidate of value) {
    const cleaned = cleanText(candidate, limit);
    const key = cleaned.toLocaleLowerCase();
    if (!cleaned || seen.has(key)) continue;
    seen.add(key);
    strings.push(cleaned);
    if (strings.length >= maxItems) break;
  }
  return strings;
}

function flashcardPayload(candidate: unknown): { cards: unknown[] } | null {
  if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) return null;
  const source = candidate as Record<string, unknown>;
  if (!Array.isArray(source.cards)) return null;
  const cards: unknown[] = [];
  for (const item of source.cards) {
    if (!item || typeof item !== "object" || Array.isArray(item)) continue;
    const raw = item as Record<string, unknown>;
    const front = cleanText(raw.front, 600);
    const back = cleanText(raw.back, 600);
    if (!front || !back) continue;
    const hint = cleanText(raw.hint, 600);
    const tags = cleanStrings(raw.tags, 40, 8);
    cards.push({
      front,
      back,
      ...(hint ? { hint } : {}),
      ...(tags.length ? { tags } : {}),
    });
    if (cards.length >= 500) break;
  }
  return source.cards.length > 0 && cards.length === 0 ? null : { cards };
}

function cleanAnswerIndices(value: unknown, optionCount: number): number[] {
  if (!Array.isArray(value)) return [];
  return [...new Set(value.filter(
    (entry): entry is number => typeof entry === "number" && Number.isInteger(entry) && entry >= 0 && entry < optionCount,
  ))];
}

function optionalQuestionMeta(raw: Record<string, unknown>): Record<string, unknown> {
  const explanation = cleanText(raw.explanation, 800);
  const tags = cleanStrings(raw.tags, 40, 6);
  const numericPoints = typeof raw.points === "number" ? raw.points : Number(raw.points);
  const points = Number.isFinite(numericPoints)
    ? Math.max(1, Math.min(100, Math.floor(numericPoints)))
    : undefined;
  return {
    ...(explanation ? { explanation } : {}),
    ...(tags.length ? { tags } : {}),
    ...(points ? { points } : {}),
  };
}

function quizPayload(candidate: unknown): { title: string; questions: unknown[] } | null {
  if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) return null;
  const root = candidate as Record<string, unknown>;
  const source = root.quiz && typeof root.quiz === "object" && !Array.isArray(root.quiz)
    ? root.quiz as Record<string, unknown>
    : root;
  if (!Array.isArray(source.questions)) return null;
  const questions: unknown[] = [];
  for (const item of source.questions) {
    if (!item || typeof item !== "object" || Array.isArray(item)) continue;
    const raw = item as Record<string, unknown>;
    const prompt = cleanText(raw.prompt, 800);
    if (!prompt) continue;
    if (raw.type === "single" || raw.type === "multiple") {
      const options = cleanStrings(raw.options, 300, 8);
      const answers = cleanAnswerIndices(raw.answerIndices, options.length);
      if (options.length < 2 || answers.length === 0) continue;
      questions.push({
        type: "choice",
        prompt,
        options,
        answer: raw.type === "single" ? answers[0] : answers,
        ...optionalQuestionMeta(raw),
      });
    } else if (raw.type === "short") {
      const accepted = cleanStrings(raw.accepted, 200, 8);
      if (!accepted.length) continue;
      questions.push({
        type: "short_answer",
        prompt,
        accepted,
        ...optionalQuestionMeta(raw),
      });
    }
    if (questions.length >= 50) break;
  }
  if (source.questions.length > 0 && questions.length === 0) return null;
  return { title: cleanText(source.title, 120), questions };
}

function browserStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

async function migrateStoredValue(
  storage: Storage | null,
  key: string,
  convert: (candidate: unknown) => unknown | null,
  migrate: (payload: unknown) => Promise<unknown>,
): Promise<MigrationStatus> {
  if (!storage) return "failed";
  let raw: string | null;
  try {
    raw = storage.getItem(key);
  } catch {
    return "failed";
  }
  if (raw === null) return "absent";

  let payload: unknown | null;
  try {
    payload = convert(JSON.parse(raw));
  } catch {
    return "invalid";
  }
  if (!payload) return "invalid";

  try {
    await migrate(payload);
  } catch {
    return "failed";
  }
  try {
    storage.removeItem(key);
    return "confirmed";
  } catch {
    // The backend marker makes a later retry safe; retain the old value for now.
    return "cleanup-failed";
  }
}

export async function migrateLegacyStudyCollections(
  migrators: LegacyStudyCollectionMigrators,
  storage: Storage | null = browserStorage(),
): Promise<LegacyStudyCollectionMigrationResult> {
  // Attempt both independently so one corrupt/failed legacy key cannot strand the other.
  const flashcards = await migrateStoredValue(
    storage,
    LEGACY_FLASHCARD_STORAGE_KEY,
    flashcardPayload,
    migrators.flashcards,
  );
  const quizzes = await migrateStoredValue(
    storage,
    LEGACY_QUIZ_STORAGE_KEY,
    quizPayload,
    migrators.quizzes,
  );
  const statuses = [flashcards, quizzes];
  return {
    changed: statuses.some((status) => status === "confirmed" || status === "cleanup-failed"),
    retryNeeded: statuses.some((status) => status === "failed" || status === "invalid" || status === "cleanup-failed"),
    flashcards,
    quizzes,
  };
}
