// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { FlashcardDeck } from "./flashcardStore";
import type { StudyFlashcard } from "./study-api";

export const STUDY_LEARNING_EVENT = "study-learning-event";

export type MigrationDeck = {
  cards: Array<{ front: string; back: string; hint?: string; tags?: string[] }>;
};

export type ReviewQueueCard = {
  itemId: string;
  artifactId: string;
  front: string;
  back: string;
  hint: string;
  tags: string[];
};

export type ReviewSummary = {
  reviewed: number;
  dueRemaining: number;
};

function cleanText(value: unknown, limit = 600): string {
  return typeof value === "string" ? value.trim().slice(0, limit) : "";
}

function cleanTags(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const out: string[] = [];
  const seen = new Set<string>();
  for (const raw of value) {
    const tag = cleanText(raw, 40);
    if (!tag) continue;
    const key = tag.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(tag);
    if (out.length >= 8) break;
  }
  return out;
}

export function legacyDeckToMigrationDeck(deck: FlashcardDeck | unknown): MigrationDeck {
  const raw = deck && typeof deck === "object" && Array.isArray((deck as { cards?: unknown }).cards)
    ? (deck as { cards: unknown[] }).cards
    : [];
  const cards: MigrationDeck["cards"] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const r = item as Record<string, unknown>;
    const front = cleanText(r.front);
    const back = cleanText(r.back);
    if (!front || !back) continue;
    const hint = cleanText(r.hint);
    const tags = cleanTags(r.tags);
    cards.push({
      front,
      back,
      ...(hint ? { hint } : {}),
      ...(tags.length ? { tags } : {}),
    });
  }
  return { cards };
}

export function backendCardsToQueue(cards: StudyFlashcard[]): ReviewQueueCard[] {
  return (cards || [])
    .map((card) => ({
      itemId: String(card.item_id || ""),
      artifactId: String(card.artifact_id || ""),
      front: cleanText(card.front),
      back: cleanText(card.back),
      hint: cleanText(card.hint),
      tags: cleanTags(card.tags),
    }))
    .filter((card) => card.itemId && card.front && card.back);
}

export function formatReviewSummary(summary: ReviewSummary, locale: "zh" | "en" = "zh"): string {
  if (locale === "en") {
    return `Reviewed ${summary.reviewed} flashcard(s); ${summary.dueRemaining} still due.`;
  }
  return `完成记忆卡片复习 ${summary.reviewed} 张（待复习剩余 ${summary.dueRemaining}）。`;
}
