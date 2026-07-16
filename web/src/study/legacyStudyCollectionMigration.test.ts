// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  LEGACY_FLASHCARD_STORAGE_KEY,
  LEGACY_QUIZ_STORAGE_KEY,
  migrateLegacyStudyCollections,
} from "./legacyStudyCollectionMigration";

describe("legacy study collection migration adapter", () => {
  beforeEach(() => localStorage.clear());

  it("migrates old profile deck and quiz samples, then clears confirmed keys", async () => {
    localStorage.setItem(LEGACY_FLASHCARD_STORAGE_KEY, JSON.stringify({
      version: 1,
      cards: [{ front: "  Vector  ", back: "Magnitude", hint: "Length", tags: ["math", "math"] }],
    }));
    localStorage.setItem(LEGACY_QUIZ_STORAGE_KEY, JSON.stringify({
      version: 1,
      quiz: {
        version: 1,
        title: "  Legacy vectors  ",
        questions: [{
          id: "q1",
          type: "single",
          prompt: "Magnitude?",
          options: ["Length", "Angle"],
          answerIndices: [0],
          accepted: [],
          explanation: "Norm",
          tags: ["vector"],
          points: 2,
        }],
      },
      responses: { q1: { selected: [1], text: "private learner response" } },
      submitted: true,
    }));
    const flashcards = vi.fn().mockResolvedValue({ migrated: false, cards: 0 });
    const quizzes = vi.fn().mockResolvedValue({ migrated: true, questions: 1 });

    await expect(migrateLegacyStudyCollections({ flashcards, quizzes })).resolves.toMatchObject({
      changed: true,
      retryNeeded: false,
      flashcards: "confirmed",
      quizzes: "confirmed",
    });
    expect(flashcards).toHaveBeenCalledWith({
      cards: [{ front: "Vector", back: "Magnitude", hint: "Length", tags: ["math"] }],
    });
    expect(quizzes).toHaveBeenCalledWith({
      title: "Legacy vectors",
      questions: [{
        type: "choice",
        prompt: "Magnitude?",
        options: ["Length", "Angle"],
        answer: 0,
        explanation: "Norm",
        tags: ["vector"],
        points: 2,
      }],
    });
    expect(JSON.stringify(quizzes.mock.calls)).not.toContain("private learner response");
    expect(localStorage.getItem(LEGACY_FLASHCARD_STORAGE_KEY)).toBeNull();
    expect(localStorage.getItem(LEGACY_QUIZ_STORAGE_KEY)).toBeNull();
  });

  it("attempts keys independently and retains the failed value byte-for-byte", async () => {
    const flashcardRaw = JSON.stringify({ version: 1, cards: [{ front: "F", back: "B" }] });
    const quizRaw = JSON.stringify({ version: 1, quiz: { title: "Q", questions: [] } });
    localStorage.setItem(LEGACY_FLASHCARD_STORAGE_KEY, flashcardRaw);
    localStorage.setItem(LEGACY_QUIZ_STORAGE_KEY, quizRaw);

    const result = await migrateLegacyStudyCollections({
      flashcards: vi.fn().mockRejectedValue(new Error("offline")),
      quizzes: vi.fn().mockResolvedValue({ migrated: false }),
    });

    expect(result).toMatchObject({ changed: true, retryNeeded: true, flashcards: "failed", quizzes: "confirmed" });
    expect(localStorage.getItem(LEGACY_FLASHCARD_STORAGE_KEY)).toBe(flashcardRaw);
    expect(localStorage.getItem(LEGACY_QUIZ_STORAGE_KEY)).toBeNull();
  });

  it("preserves duplicate option positions and their old answer indexes", async () => {
    localStorage.setItem(LEGACY_QUIZ_STORAGE_KEY, JSON.stringify({
      version: 1,
      quiz: {
        version: 1,
        title: "Repeated options",
        questions: [{
          id: "q-duplicate",
          type: "single",
          prompt: "Choose the second A",
          options: ["A", "A", "B"],
          answerIndices: [1],
          accepted: [],
          explanation: "The duplicate position is intentional.",
          tags: [],
          points: 1,
        }],
      },
      responses: {},
      submitted: false,
    }));
    const quizzes = vi.fn().mockResolvedValue({ migrated: true, questions: 1 });

    await expect(migrateLegacyStudyCollections({ flashcards: vi.fn(), quizzes })).resolves.toMatchObject({
      changed: true,
      retryNeeded: false,
      quizzes: "confirmed",
    });
    expect(quizzes).toHaveBeenCalledWith({
      title: "Repeated options",
      questions: [{
        type: "choice",
        prompt: "Choose the second A",
        options: ["A", "A", "B"],
        answer: 1,
        explanation: "The duplicate position is intentional.",
        points: 1,
      }],
    });
    expect(localStorage.getItem(LEGACY_QUIZ_STORAGE_KEY)).toBeNull();
  });

  it("preserves malformed non-empty data instead of confirming an empty migration", async () => {
    const raw = JSON.stringify({ version: 1, cards: [{ front: "missing back" }] });
    localStorage.setItem(LEGACY_FLASHCARD_STORAGE_KEY, raw);
    const flashcards = vi.fn();

    await expect(migrateLegacyStudyCollections({ flashcards, quizzes: vi.fn() })).resolves.toMatchObject({
      changed: false,
      retryNeeded: true,
      flashcards: "invalid",
    });
    expect(flashcards).not.toHaveBeenCalled();
    expect(localStorage.getItem(LEGACY_FLASHCARD_STORAGE_KEY)).toBe(raw);
  });

  it("requests a later retry when browser storage is temporarily unavailable", async () => {
    const flashcards = vi.fn();
    const quizzes = vi.fn();
    await expect(migrateLegacyStudyCollections({ flashcards, quizzes }, null)).resolves.toMatchObject({
      changed: false,
      retryNeeded: true,
      flashcards: "failed",
      quizzes: "failed",
    });
    expect(flashcards).not.toHaveBeenCalled();
    expect(quizzes).not.toHaveBeenCalled();
  });
});
