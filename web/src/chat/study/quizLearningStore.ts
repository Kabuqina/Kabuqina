// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { Quiz } from "./quizStore";
import type { StudyQuizQuestion, StudyQuizQuestionType, StudyQuizResult } from "./study-api";

export type MigrationQuizQuestion =
  | {
      type: "choice";
      prompt: string;
      options: string[];
      answer: number | number[];
      explanation?: string;
      tags?: string[];
      points?: number;
    }
  | {
      type: "short_answer";
      prompt: string;
      accepted: string[];
      explanation?: string;
      tags?: string[];
      points?: number;
    };

export type MigrationQuiz = {
  title: string;
  questions: MigrationQuizQuestion[];
};

export type QuizQuestionRow = {
  itemId: string;
  artifactId: string;
  type: StudyQuizQuestionType;
  prompt: string;
  options: string[];
  multiple: boolean;
  explanation: string;
  tags: string[];
  points: number;
};

export type QuizResponseDraft = {
  selected?: number[];
  text?: string;
  value?: boolean | null;
};

export type QuizSubmitPayload = Record<
  string,
  { selected: number[]; text: string; value: boolean | null }
>;

function cleanText(value: unknown, limit = 800): string {
  return typeof value === "string" ? value.trim().slice(0, limit) : "";
}

function cleanStringList(value: unknown, limit = 300, maxItems = 16): string[] {
  if (!Array.isArray(value)) return [];
  const out: string[] = [];
  const seen = new Set<string>();
  for (const raw of value) {
    const text = cleanText(raw, limit);
    if (!text) continue;
    const key = text.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(text);
    if (out.length >= maxItems) break;
  }
  return out;
}

function cleanIntList(value: unknown): number[] {
  if (!Array.isArray(value)) return [];
  const out: number[] = [];
  for (const raw of value) {
    const n = typeof raw === "number" ? raw : Number(raw);
    if (!Number.isInteger(n)) continue;
    out.push(n);
  }
  return out;
}

function cleanPoints(value: unknown): number | undefined {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return undefined;
  return Math.max(1, Math.min(100, Math.floor(n)));
}

function withOptionalMeta<T extends MigrationQuizQuestion>(
  question: T,
  raw: Record<string, unknown>,
): T {
  const explanation = cleanText(raw.explanation);
  const tags = cleanStringList(raw.tags, 40, 8);
  const points = cleanPoints(raw.points);
  return {
    ...question,
    ...(explanation ? { explanation } : {}),
    ...(tags.length ? { tags } : {}),
    ...(points ? { points } : {}),
  };
}

export function legacyQuizToMigrationQuiz(quiz: Quiz | unknown): MigrationQuiz {
  const source = quiz && typeof quiz === "object" ? (quiz as Record<string, unknown>) : {};
  const title = cleanText(source.title, 120);
  const rawQuestions = Array.isArray(source.questions) ? source.questions : [];
  const questions: MigrationQuizQuestion[] = [];

  for (const raw of rawQuestions) {
    if (!raw || typeof raw !== "object") continue;
    const r = raw as Record<string, unknown>;
    const prompt = cleanText(r.prompt);
    if (!prompt) continue;
    const type = cleanText(r.type, 40);
    if (type === "single" || type === "multiple") {
      const options = cleanStringList(r.options, 300, 26);
      const answers = cleanIntList(r.answerIndices);
      if (options.length < 2 || answers.length === 0) continue;
      questions.push(
        withOptionalMeta(
          {
            type: "choice",
            prompt,
            options,
            answer: type === "single" ? answers[0] : answers,
          },
          r,
        ),
      );
      continue;
    }
    if (type === "short") {
      const accepted = cleanStringList(r.accepted, 200, 16);
      if (!accepted.length) continue;
      questions.push(
        withOptionalMeta(
          {
            type: "short_answer",
            prompt,
            accepted,
          },
          r,
        ),
      );
    }
  }
  return { title, questions };
}

export function backendQuestionsToQuizRows(questions: StudyQuizQuestion[]): QuizQuestionRow[] {
  return (questions || [])
    .map((question) => ({
      itemId: String(question.item_id || ""),
      artifactId: String(question.artifact_id || ""),
      type: question.type,
      prompt: cleanText(question.prompt),
      options: cleanStringList(question.options, 300, 26),
      multiple: Boolean(question.multiple),
      explanation: cleanText(question.explanation),
      tags: cleanStringList(question.tags, 40, 8),
      points: cleanPoints(question.points) || 1,
    }))
    .filter((question) => question.itemId && question.prompt);
}

export function responsesToSubmitPayload(responses: Record<string, QuizResponseDraft>): QuizSubmitPayload {
  const out: QuizSubmitPayload = {};
  for (const [itemId, response] of Object.entries(responses || {})) {
    if (!itemId) continue;
    out[itemId] = {
      selected: cleanIntList(response?.selected),
      text: cleanText(response?.text, 500),
      value: typeof response?.value === "boolean" ? response.value : null,
    };
  }
  return out;
}

export function formatQuizAttemptSummary(
  result: Pick<StudyQuizResult, "score" | "maxScore" | "percent" | "correctCount" | "total">,
  locale: "zh" | "en" = "zh",
): string {
  if (locale === "en") {
    return `Quiz complete: ${result.score}/${result.maxScore} (${result.percent}%, ${result.correctCount}/${result.total} correct).`;
  }
  return `完成测验：${result.score}/${result.maxScore}（${result.percent}%，答对 ${result.correctCount}/${result.total}）。`;
}
