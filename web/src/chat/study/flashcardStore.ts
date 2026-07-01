// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// STUDY module — spaced-repetition flashcards.
//
// This file owns all flashcard logic: validation, persistence, the scheduling
// algorithm, and tolerant parsing of card batches emitted by the agent. It has
// no React or Tauri imports so the contract stays unit-testable in isolation
// (see ./flashcardStore.test.mjs), mirroring ./studyStore.
//
// The scheduler is an SM-2 variant driven by four Anki-style review grades. All
// scheduling functions are pure and take an injected `now` (epoch ms) so tests
// are deterministic. Time is tracked in whole days, which suits a study planner
// rather than a sub-minute drill app.
//
// Every input path (stored JSON, pasted text, agent output) is treated as
// untrusted: sizes are clamped, strings are length-capped and control-char
// stripped, and malformed records are dropped rather than trusted.

export const FLASHCARD_STORAGE_KEY = "kabuqina.study.flashcards.v1";
export const FLASHCARD_EVENT = "kabuqina-study-flashcards";

// Bounds. Kept small enough to stay well within localStorage quotas and to
// bound render/parse cost even against adversarial input.
export const FLASHCARD_TEXT_LIMIT = 600;
export const FLASHCARD_TAG_LIMIT = 40;
export const FLASHCARD_MAX_TAGS = 8;
export const FLASHCARD_MAX_CARDS = 500;
export const FLASHCARD_MAX_IMPORT = 100;
export const FLASHCARD_MAX_INTERVAL_DAYS = 365;

export const MIN_EASE = 1.3;
export const DEFAULT_EASE = 2.5;
export const MATURE_INTERVAL_DAYS = 21;

const DAY_MS = 86_400_000;

export type ReviewGrade = "again" | "hard" | "good" | "easy";

const EASE_DELTA: Record<ReviewGrade, number> = {
  again: -0.2,
  hard: -0.15,
  good: 0,
  easy: 0.15,
};

export type Flashcard = {
  id: string;
  front: string;
  back: string;
  hint: string;
  tags: string[];
  ease: number;
  intervalDays: number;
  repetitions: number;
  lapses: number;
  createdAt: string;
  dueAt: string;
  lastReviewedAt: string;
};

export type FlashcardDeck = {
  version: 1;
  cards: Flashcard[];
};

export type DeckStats = {
  total: number;
  due: number;
  fresh: number;
  learning: number;
  mature: number;
};

export function emptyDeck(): FlashcardDeck {
  return { version: 1, cards: [] };
}

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

function cleanText(value: unknown, limit = FLASHCARD_TEXT_LIMIT): string {
  if (typeof value !== "string") return "";
  // Drop C0/C1 control characters (keeping tab and newline) via a pure
  // codepoint scan, then trim and length-cap.
  const stripped = stripControlChars(value);
  return stripped.trim().slice(0, limit);
}

function cleanTags(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of value) {
    const tag = cleanText(raw, FLASHCARD_TAG_LIMIT);
    if (!tag) continue;
    const key = tag.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(tag);
    if (out.length >= FLASHCARD_MAX_TAGS) break;
  }
  return out;
}

function makeId(): string {
  try {
    const c = (globalThis as { crypto?: { randomUUID?: () => string } }).crypto;
    if (c && typeof c.randomUUID === "function") return c.randomUUID();
  } catch {
    // fall through to non-crypto id
  }
  return `card-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function toFiniteNumber(value: unknown, fallback: number): number {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function clamp(value: number, min: number, max: number): number {
  if (value < min) return min;
  if (value > max) return max;
  return value;
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

function toIso(value: unknown, fallbackMs: number): string {
  if (typeof value === "string") {
    const parsed = Date.parse(value);
    if (Number.isFinite(parsed)) return new Date(parsed).toISOString();
  }
  return new Date(fallbackMs).toISOString();
}

/**
 * Coerce an untrusted record into a valid Flashcard, or return null when it has
 * no usable front/back. `now` seeds timestamps for freshly imported cards.
 */
export function normalizeCard(raw: unknown, now: number = Date.now()): Flashcard | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const front = cleanText(r.front);
  const back = cleanText(r.back);
  if (!front || !back) return null;

  const ease = round2(clamp(toFiniteNumber(r.ease, DEFAULT_EASE), MIN_EASE, 5));
  const repetitions = clamp(Math.floor(toFiniteNumber(r.repetitions, 0)), 0, 100_000);
  const lapses = clamp(Math.floor(toFiniteNumber(r.lapses, 0)), 0, 100_000);
  const intervalDays = clamp(
    Math.round(toFiniteNumber(r.intervalDays, 0)),
    0,
    FLASHCARD_MAX_INTERVAL_DAYS,
  );

  return {
    id: typeof r.id === "string" && r.id.trim() ? r.id.trim().slice(0, 64) : makeId(),
    front,
    back,
    hint: cleanText(r.hint),
    tags: cleanTags(r.tags),
    ease,
    intervalDays,
    repetitions,
    lapses,
    createdAt: toIso(r.createdAt, now),
    dueAt: toIso(r.dueAt, now),
    lastReviewedAt: typeof r.lastReviewedAt === "string" ? toIso(r.lastReviewedAt, now) : "",
  } satisfies Flashcard;
}

export function normalizeDeck(value: unknown, now: number = Date.now()): FlashcardDeck {
  const rawCards = (() => {
    if (Array.isArray(value)) return value;
    if (value && typeof value === "object" && Array.isArray((value as { cards?: unknown }).cards)) {
      return (value as { cards: unknown[] }).cards;
    }
    return [];
  })();

  const cards: Flashcard[] = [];
  const seenIds = new Set<string>();
  for (const raw of rawCards) {
    const card = normalizeCard(raw, now);
    if (!card) continue;
    // Guard against duplicate ids from corrupt storage.
    if (seenIds.has(card.id)) card.id = makeId();
    seenIds.add(card.id);
    cards.push(card);
    if (cards.length >= FLASHCARD_MAX_CARDS) break;
  }
  return { version: 1, cards };
}

// ---------------------------------------------------------------------------
// Scheduling (pure, deterministic)
// ---------------------------------------------------------------------------

/**
 * Apply one review to a card and return the updated card. The interval schedule
 * is deterministic and documented so tests can assert exact values:
 *
 *   again -> reset to a 1-day interval, +1 lapse, ease down 0.20
 *   otherwise the interval graduates by how many successful reps precede it:
 *     first success:  hard 1d / good 2d / easy 4d
 *     second success: hard 4d / good 6d / easy 8d
 *     later:          round(prevInterval * factor), factor = hard 1.2,
 *                     good ease, easy ease*1.3
 *
 * Ease is clamped to [MIN_EASE, 5]; interval to [1, FLASHCARD_MAX_INTERVAL_DAYS].
 */
export function reviewCard(
  card: Flashcard,
  grade: ReviewGrade,
  now: number = Date.now(),
): Flashcard {
  if (!EASE_DELTA[grade as ReviewGrade] && grade !== "good") {
    // Unknown grade: treat conservatively as "again" so bad input never
    // silently promotes a card.
    grade = "again";
  }
  const ease = round2(clamp(card.ease + EASE_DELTA[grade], MIN_EASE, 5));

  let repetitions: number;
  let intervalDays: number;
  let lapses = card.lapses;

  if (grade === "again") {
    repetitions = 0;
    intervalDays = 1;
    lapses = card.lapses + 1;
  } else {
    repetitions = card.repetitions + 1;
    if (card.repetitions <= 0) {
      intervalDays = grade === "easy" ? 4 : grade === "hard" ? 1 : 2;
    } else if (card.repetitions === 1) {
      intervalDays = grade === "easy" ? 8 : grade === "hard" ? 4 : 6;
    } else {
      const prev = Math.max(1, card.intervalDays);
      const factor = grade === "hard" ? 1.2 : grade === "easy" ? ease * 1.3 : ease;
      intervalDays = Math.round(prev * factor);
    }
  }

  intervalDays = clamp(intervalDays, 1, FLASHCARD_MAX_INTERVAL_DAYS);
  return {
    ...card,
    ease,
    repetitions,
    intervalDays,
    lapses,
    lastReviewedAt: new Date(now).toISOString(),
    dueAt: new Date(now + intervalDays * DAY_MS).toISOString(),
  };
}

function isDue(card: Flashcard, now: number): boolean {
  const due = Date.parse(card.dueAt);
  if (!Number.isFinite(due)) return true;
  return due <= now;
}

function isFresh(card: Flashcard): boolean {
  return card.repetitions <= 0 && !card.lastReviewedAt;
}

/** Cards ready to review now, freshest (never-seen) first, then by due time. */
export function dueCards(deck: FlashcardDeck, now: number = Date.now()): Flashcard[] {
  return deck.cards
    .filter((card) => isDue(card, now))
    .sort((a, b) => {
      const af = isFresh(a) ? 0 : 1;
      const bf = isFresh(b) ? 0 : 1;
      if (af !== bf) return af - bf;
      return Date.parse(a.dueAt) - Date.parse(b.dueAt);
    });
}

export function deckStats(deck: FlashcardDeck, now: number = Date.now()): DeckStats {
  let due = 0;
  let fresh = 0;
  let learning = 0;
  let mature = 0;
  for (const card of deck.cards) {
    if (isDue(card, now)) due += 1;
    if (isFresh(card)) fresh += 1;
    else if (card.intervalDays >= MATURE_INTERVAL_DAYS) mature += 1;
    else learning += 1;
  }
  return { total: deck.cards.length, due, fresh, learning, mature };
}

/**
 * Merge freshly imported cards into a deck, de-duplicating by normalized front
 * text (case/whitespace-insensitive) and capping the deck at FLASHCARD_MAX_CARDS.
 * Existing cards keep their scheduling state; duplicates in the import are
 * skipped so a re-run of generation does not reset progress.
 */
export function upsertCards(
  deck: FlashcardDeck,
  incoming: Flashcard[],
  now: number = Date.now(),
): FlashcardDeck {
  const byFront = new Set(deck.cards.map((c) => c.front.trim().toLowerCase()));
  const cards = [...deck.cards];
  for (const raw of incoming) {
    if (cards.length >= FLASHCARD_MAX_CARDS) break;
    const card = normalizeCard(raw, now);
    if (!card) continue;
    const key = card.front.trim().toLowerCase();
    if (byFront.has(key)) continue;
    byFront.add(key);
    cards.push(card);
  }
  return { version: 1, cards };
}

// ---------------------------------------------------------------------------
// Tolerant parsing of agent / pasted card batches
// ---------------------------------------------------------------------------

function extractJsonPayload(text: string): string {
  // Prefer a fenced ```json block; fall back to the first {...} or [...] span.
  const fence = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fence && fence[1].trim()) return fence[1].trim();
  const firstArray = text.indexOf("[");
  const firstObject = text.indexOf("{");
  const starts = [firstArray, firstObject].filter((i) => i >= 0);
  if (!starts.length) return text.trim();
  const start = Math.min(...starts);
  const lastArray = text.lastIndexOf("]");
  const lastObject = text.lastIndexOf("}");
  const end = Math.max(lastArray, lastObject);
  if (end > start) return text.slice(start, end + 1).trim();
  return text.trim();
}

/**
 * Parse a batch of cards from untrusted text (agent output or paste). Accepts a
 * JSON array of {front, back, hint?, tags?} or an object with a `cards` array.
 * Returns normalized new cards (capped at FLASHCARD_MAX_IMPORT); returns [] on
 * any malformed input rather than throwing.
 */
export function parseFlashcards(text: unknown, now: number = Date.now()): Flashcard[] {
  if (typeof text !== "string" || !text.trim()) return [];
  let parsed: unknown;
  try {
    parsed = JSON.parse(extractJsonPayload(text));
  } catch {
    return [];
  }
  const list = Array.isArray(parsed)
    ? parsed
    : parsed && typeof parsed === "object" && Array.isArray((parsed as { cards?: unknown }).cards)
      ? (parsed as { cards: unknown[] }).cards
      : [];
  const out: Flashcard[] = [];
  for (const raw of list) {
    const card = normalizeCard(raw, now);
    if (!card) continue;
    out.push(card);
    if (out.length >= FLASHCARD_MAX_IMPORT) break;
  }
  return out;
}

// ---------------------------------------------------------------------------
// Persistence (guarded, mirrors studyStore)
// ---------------------------------------------------------------------------

function storageAvailable(): Storage | null {
  if (typeof window === "undefined" || !window.localStorage) return null;
  return window.localStorage;
}

export function loadDeck(): FlashcardDeck {
  const storage = storageAvailable();
  if (!storage) return emptyDeck();
  try {
    const raw = storage.getItem(FLASHCARD_STORAGE_KEY);
    return raw ? normalizeDeck(JSON.parse(raw)) : emptyDeck();
  } catch {
    return emptyDeck();
  }
}

function emitDeckChanged() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(FLASHCARD_EVENT));
}

export function saveDeck(deck: FlashcardDeck): FlashcardDeck {
  const normalized = normalizeDeck(deck);
  const storage = storageAvailable();
  if (storage) {
    try {
      storage.setItem(FLASHCARD_STORAGE_KEY, JSON.stringify(normalized));
    } catch {
      // localStorage may be unavailable or full in restricted webviews.
    }
  }
  emitDeckChanged();
  return normalized;
}

export function clearDeck(): FlashcardDeck {
  const storage = storageAvailable();
  if (storage) {
    try {
      storage.removeItem(FLASHCARD_STORAGE_KEY);
    } catch {
      // ignore
    }
  }
  emitDeckChanged();
  return emptyDeck();
}
