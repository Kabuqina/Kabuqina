// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// STUDY module — self-test quiz generation, taking, and grading.
//
// Like flashcardStore, this file owns all quiz logic with no React/Tauri
// imports so the contract is unit-testable in isolation (see ./quizStore.test.mjs).
// Quizzes are produced by the agent via a bounded prompt and pasted back by the
// student; parseQuiz validates that untrusted structure hard (answer indices in
// range, options present, sizes clamped) and drops anything malformed rather
// than trusting it. Grading is pure and deterministic.

export const QUIZ_STORAGE_KEY = "kabuqina.study.quiz.v1";
export const QUIZ_EVENT = "kabuqina-study-quiz";

export const QUIZ_TEXT_LIMIT = 800;
export const QUIZ_OPTION_LIMIT = 300;
export const QUIZ_ACCEPTED_LIMIT = 200;
export const QUIZ_TAG_LIMIT = 40;
export const QUIZ_MAX_OPTIONS = 8;
export const QUIZ_MIN_OPTIONS = 2;
export const QUIZ_MAX_ACCEPTED = 8;
export const QUIZ_MAX_TAGS = 6;
export const QUIZ_MAX_QUESTIONS = 50;
export const QUIZ_MAX_POINTS = 100;

export type QuestionType = "single" | "multiple" | "short";

export type QuizQuestion = {
  id: string;
  type: QuestionType;
  prompt: string;
  options: string[];
  answerIndices: number[];
  accepted: string[];
  explanation: string;
  tags: string[];
  points: number;
};

export type Quiz = {
  version: 1;
  title: string;
  questions: QuizQuestion[];
};

export type QuizResponse = {
  selected: number[];
  text: string;
};

export type QuizState = {
  version: 1;
  quiz: Quiz;
  responses: Record<string, QuizResponse>;
  submitted: boolean;
};

export type QuestionResult = {
  id: string;
  type: QuestionType;
  correct: boolean;
  earned: number;
  points: number;
};

export type QuizResult = {
  total: number;
  correctCount: number;
  score: number;
  maxScore: number;
  percent: number;
  perQuestion: QuestionResult[];
  weakTags: string[];
};

// ---------------------------------------------------------------------------
// Sanitization helpers
// ---------------------------------------------------------------------------

function stripControlChars(value: string): string {
  let out = "";
  for (let i = 0; i < value.length; i += 1) {
    const code = value.charCodeAt(i);
    const isC0 = code <= 0x1f && code !== 0x09 && code !== 0x0a && code !== 0x0d;
    const isC1 = code >= 0x7f && code <= 0x9f;
    if (isC0 || isC1) continue;
    out += value[i];
  }
  return out;
}

function cleanText(value: unknown, limit = QUIZ_TEXT_LIMIT): string {
  if (typeof value !== "string") return "";
  return stripControlChars(value).trim().slice(0, limit);
}

function cleanStringList(value: unknown, itemLimit: number, maxItems: number): string[] {
  if (!Array.isArray(value)) return [];
  const out: string[] = [];
  for (const raw of value) {
    const item = cleanText(raw, itemLimit);
    if (!item) continue;
    out.push(item);
    if (out.length >= maxItems) break;
  }
  return out;
}

function cleanTags(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of value) {
    const tag = cleanText(raw, QUIZ_TAG_LIMIT);
    if (!tag) continue;
    const key = tag.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(tag);
    if (out.length >= QUIZ_MAX_TAGS) break;
  }
  return out;
}

function makeId(): string {
  try {
    const c = (globalThis as { crypto?: { randomUUID?: () => string } }).crypto;
    if (c && typeof c.randomUUID === "function") return c.randomUUID();
  } catch {
    // fall through
  }
  return `q-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function toInt(value: unknown, fallback: number): number {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? Math.floor(n) : fallback;
}

function uniqueInts(value: unknown, maxExclusive: number): number[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<number>();
  for (const raw of value) {
    const n = typeof raw === "number" ? raw : Number(raw);
    if (!Number.isInteger(n)) continue;
    if (n < 0 || n >= maxExclusive) continue; // out-of-range indices dropped
    seen.add(n);
  }
  return [...seen].sort((a, b) => a - b);
}

/** Normalize a short answer for comparison: lowercase, collapse and trim
 * whitespace, and strip surrounding punctuation/symbols. */
export function normalizeShortAnswer(value: string): string {
  const collapsed = stripControlChars(String(value)).toLowerCase().replace(/\s+/g, " ").trim();
  return collapsed.replace(/^[\s\p{P}\p{S}]+|[\s\p{P}\p{S}]+$/gu, "");
}

// ---------------------------------------------------------------------------
// Question / quiz normalization (tolerant of untrusted input)
// ---------------------------------------------------------------------------

function resolveType(raw: unknown, hasOptions: boolean, answerCount: number): QuestionType {
  const t = typeof raw === "string" ? raw.trim().toLowerCase() : "";
  if (t === "single" || t === "multiple" || t === "short") return t;
  if (!hasOptions) return "short";
  return answerCount > 1 ? "multiple" : "single";
}

/** Coerce one untrusted record into a valid QuizQuestion, or null if unusable. */
export function normalizeQuestion(raw: unknown): QuizQuestion | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const prompt = cleanText(r.prompt ?? r.question);
  if (!prompt) return null;

  const options = cleanStringList(r.options, QUIZ_OPTION_LIMIT, QUIZ_MAX_OPTIONS);
  const rawAnswer = r.answerIndices ?? r.answer ?? r.correct;
  const answerIndices = uniqueInts(rawAnswer, options.length);
  const accepted = cleanStringList(r.accepted ?? r.answers, QUIZ_ACCEPTED_LIMIT, QUIZ_MAX_ACCEPTED);

  const type = resolveType(r.type, options.length >= QUIZ_MIN_OPTIONS, answerIndices.length);

  if (type === "short") {
    if (!accepted.length) return null; // no way to grade
    return {
      id: cleanId(r.id),
      type,
      prompt,
      options: [],
      answerIndices: [],
      accepted,
      explanation: cleanText(r.explanation),
      tags: cleanTags(r.tags),
      points: clampPoints(r.points),
    };
  }

  // choice question
  if (options.length < QUIZ_MIN_OPTIONS) return null; // not enough options to choose from
  if (!answerIndices.length) return null; // no valid correct answer in range
  const finalAnswers = type === "single" ? [answerIndices[0]] : answerIndices;
  return {
    id: cleanId(r.id),
    type,
    prompt,
    options,
    answerIndices: finalAnswers,
    accepted: [],
    explanation: cleanText(r.explanation),
    tags: cleanTags(r.tags),
    points: clampPoints(r.points),
  };
}

function cleanId(value: unknown): string {
  return typeof value === "string" && value.trim() ? value.trim().slice(0, 64) : makeId();
}

function clampPoints(value: unknown): number {
  const n = toInt(value, 1);
  if (n < 1) return 1;
  if (n > QUIZ_MAX_POINTS) return QUIZ_MAX_POINTS;
  return n;
}

export function normalizeQuiz(value: unknown): Quiz {
  const title = cleanText(
    value && typeof value === "object" ? (value as { title?: unknown }).title : "",
    120,
  );
  const rawQuestions = (() => {
    if (Array.isArray(value)) return value;
    if (
      value &&
      typeof value === "object" &&
      Array.isArray((value as { questions?: unknown }).questions)
    ) {
      return (value as { questions: unknown[] }).questions;
    }
    return [];
  })();

  const questions: QuizQuestion[] = [];
  const seenIds = new Set<string>();
  for (const raw of rawQuestions) {
    const q = normalizeQuestion(raw);
    if (!q) continue;
    if (seenIds.has(q.id)) q.id = makeId();
    seenIds.add(q.id);
    questions.push(q);
    if (questions.length >= QUIZ_MAX_QUESTIONS) break;
  }
  return { version: 1, title, questions };
}

export function emptyQuiz(): Quiz {
  return { version: 1, title: "", questions: [] };
}

// ---------------------------------------------------------------------------
// Tolerant parsing
// ---------------------------------------------------------------------------

function extractJsonPayload(text: string): string {
  const fence = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fence && fence[1].trim()) return fence[1].trim();
  const firstArray = text.indexOf("[");
  const firstObject = text.indexOf("{");
  const starts = [firstArray, firstObject].filter((i) => i >= 0);
  if (!starts.length) return text.trim();
  const start = Math.min(...starts);
  const end = Math.max(text.lastIndexOf("]"), text.lastIndexOf("}"));
  if (end > start) return text.slice(start, end + 1).trim();
  return text.trim();
}

/** Parse a quiz from untrusted text (agent output or paste). Returns an empty
 * quiz on any malformed input rather than throwing. */
export function parseQuiz(text: unknown): Quiz {
  if (typeof text !== "string" || !text.trim()) return emptyQuiz();
  try {
    return normalizeQuiz(JSON.parse(extractJsonPayload(text)));
  } catch {
    return emptyQuiz();
  }
}

// ---------------------------------------------------------------------------
// Grading (pure, deterministic)
// ---------------------------------------------------------------------------

function sameIndexSet(a: number[], b: number[]): boolean {
  if (a.length !== b.length) return false;
  const setB = new Set(b);
  return a.every((n) => setB.has(n));
}

export function emptyResponse(): QuizResponse {
  return { selected: [], text: "" };
}

/** Grade a single question against a response. All-or-nothing per question. */
export function gradeQuestion(question: QuizQuestion, response: QuizResponse | undefined): boolean {
  const res = response ?? emptyResponse();
  if (question.type === "short") {
    const answer = normalizeShortAnswer(res.text ?? "");
    if (!answer) return false;
    return question.accepted.some((a) => normalizeShortAnswer(a) === answer);
  }
  // choice questions: selection must exactly equal the correct index set, and
  // out-of-range selections never count.
  const selected = uniqueInts(res.selected, question.options.length);
  if (!selected.length) return false;
  return sameIndexSet(selected, question.answerIndices);
}

export function gradeQuiz(quiz: Quiz, responses: Record<string, QuizResponse>): QuizResult {
  const perQuestion: QuestionResult[] = [];
  const weak = new Set<string>();
  let score = 0;
  let maxScore = 0;
  let correctCount = 0;

  for (const question of quiz.questions) {
    const correct = gradeQuestion(question, responses[question.id]);
    maxScore += question.points;
    if (correct) {
      score += question.points;
      correctCount += 1;
    } else {
      for (const tag of question.tags) weak.add(tag);
    }
    perQuestion.push({
      id: question.id,
      type: question.type,
      correct,
      earned: correct ? question.points : 0,
      points: question.points,
    });
  }

  const percent = maxScore > 0 ? Math.round((score / maxScore) * 100) : 0;
  return {
    total: quiz.questions.length,
    correctCount,
    score,
    maxScore,
    percent,
    perQuestion,
    weakTags: [...weak].slice(0, QUIZ_MAX_TAGS),
  };
}

/** One-line, plain-text summary suitable for writing back into the study
 * context (assessment evidence / weak points). */
export function formatQuizResultForContext(quiz: Quiz, result: QuizResult): string {
  const stamp = new Date().toISOString().slice(0, 10);
  const title = quiz.title ? `《${quiz.title}》` : "自测";
  const base = `【${stamp}】${title}得分 ${result.score}/${result.maxScore}（${result.percent}%，答对 ${result.correctCount}/${result.total}）。`;
  const weak = result.weakTags.length ? `薄弱点：${result.weakTags.join("、")}。` : "";
  return `${base}${weak}`.slice(0, QUIZ_TEXT_LIMIT);
}

// ---------------------------------------------------------------------------
// Persistence (guarded, mirrors studyStore/flashcardStore)
// ---------------------------------------------------------------------------

function normalizeResponses(
  value: unknown,
  quiz: Quiz,
): Record<string, QuizResponse> {
  const out: Record<string, QuizResponse> = {};
  if (!value || typeof value !== "object") return out;
  const ids = new Set(quiz.questions.map((q) => q.id));
  const optionsById = new Map(quiz.questions.map((q) => [q.id, q.options.length] as const));
  for (const [id, raw] of Object.entries(value as Record<string, unknown>)) {
    if (!ids.has(id) || !raw || typeof raw !== "object") continue;
    const r = raw as Record<string, unknown>;
    out[id] = {
      selected: uniqueInts(r.selected, optionsById.get(id) ?? 0),
      text: cleanText(r.text, QUIZ_ACCEPTED_LIMIT),
    };
  }
  return out;
}

export function normalizeQuizState(value: unknown): QuizState {
  const quiz = normalizeQuiz(
    value && typeof value === "object" ? (value as { quiz?: unknown }).quiz : undefined,
  );
  const responses = normalizeResponses(
    value && typeof value === "object" ? (value as { responses?: unknown }).responses : undefined,
    quiz,
  );
  const submitted = Boolean(
    value && typeof value === "object" && (value as { submitted?: unknown }).submitted,
  );
  return { version: 1, quiz, responses, submitted };
}

export function emptyQuizState(): QuizState {
  return { version: 1, quiz: emptyQuiz(), responses: {}, submitted: false };
}

function storageAvailable(): Storage | null {
  if (typeof window === "undefined" || !window.localStorage) return null;
  return window.localStorage;
}

export function loadQuizState(): QuizState {
  const storage = storageAvailable();
  if (!storage) return emptyQuizState();
  try {
    const raw = storage.getItem(QUIZ_STORAGE_KEY);
    return raw ? normalizeQuizState(JSON.parse(raw)) : emptyQuizState();
  } catch {
    return emptyQuizState();
  }
}

function emitQuizChanged() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(QUIZ_EVENT));
}

export function saveQuizState(state: QuizState): QuizState {
  const normalized = normalizeQuizState(state);
  const storage = storageAvailable();
  if (storage) {
    try {
      storage.setItem(QUIZ_STORAGE_KEY, JSON.stringify(normalized));
    } catch {
      // localStorage may be unavailable or full in restricted webviews.
    }
  }
  emitQuizChanged();
  return normalized;
}

export function clearQuizState(): QuizState {
  const storage = storageAvailable();
  if (storage) {
    try {
      storage.removeItem(QUIZ_STORAGE_KEY);
    } catch {
      // ignore
    }
  }
  emitQuizChanged();
  return emptyQuizState();
}
