// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { invoke } from "@tauri-apps/api/core";

export type StudySpace = {
  space_id: string;
  title: string;
  status: string;
  is_current: boolean;
};

export type StudySpacesResponse = {
  currentSpaceId?: string | null;
  spaces: StudySpace[];
};

export type StudyArtifact = {
  artifact_id: string;
  kind: string;
  title: string;
  version: number;
  status: string;
  review?: { mode?: string; status?: string };
  created_at?: string;
  updated_at?: string;
};

export type StudyDraftsResponse = {
  drafts: StudyArtifact[];
};

export type StudyFlashcard = {
  item_id: string;
  artifact_id: string;
  front: string;
  back: string;
  hint?: string;
  tags?: string[];
  ease?: number;
  intervalDays?: number;
  repetitions?: number;
  lapses?: number;
  createdAt?: string;
  dueAt?: string;
  lastReviewedAt?: string;
};

export type StudyFlashcardsResponse = {
  cards: StudyFlashcard[];
};

export type StudyFlashcardCaptureRequest = {
  front: string;
  back: string;
  hint?: string;
  tags?: string[];
  source?: {
    origin?: string;
    session_id?: string;
    source_label?: string;
    confidence?: string;
    gist?: string;
  };
};

export type StudyCaptureResponse = {
  duplicate: boolean;
  artifact_id?: string;
  item_id: string;
  front?: string;
  dueAt?: string;
};

export type StudyMigrationResponse = {
  migrated: boolean;
  artifact_id?: string;
  cards: number;
  status?: string;
};

export type StudyQuizzesResponse = {
  quizzes: StudyArtifact[];
};

export type StudyQuizQuestionType = "choice" | "true_false" | "short_answer";

export type StudyQuizQuestion = {
  item_id: string;
  artifact_id: string;
  type: StudyQuizQuestionType;
  prompt: string;
  options?: string[];
  multiple?: boolean;
  explanation?: string;
  tags?: string[];
  points?: number;
};

export type StudyQuizQuestionsResponse = {
  questions: StudyQuizQuestion[];
};

export type StudyQuizPerQuestion = {
  item_id: string;
  prompt: string;
  type: StudyQuizQuestionType;
  correct: boolean;
  earned: number;
  points: number;
  answer?: unknown;
  accepted?: string[];
  explanation?: string;
  tags?: string[];
  response?: unknown;
};

export type StudyQuizResult = {
  activity_id?: string;
  score: number;
  maxScore: number;
  percent: number;
  correctCount: number;
  total: number;
  weakTags?: string[];
  perQuestion: StudyQuizPerQuestion[];
};

export type StudyQuizMigrationResponse = {
  migrated: boolean;
  artifact_id?: string;
  questions: number;
  status?: string;
};

export function cmdStudySpaces(): Promise<StudySpacesResponse> {
  return invoke("cmd_study_spaces");
}

export function cmdStudySpaceCreate(title: string): Promise<StudySpacesResponse & { space_id: string }> {
  return invoke("cmd_study_space_create", { title });
}

export function cmdStudySpaceSelect(spaceId: string): Promise<StudySpacesResponse & { space_id: string }> {
  return invoke("cmd_study_space_select", { spaceId });
}

export function cmdStudyDrafts(kind = "flashcard_deck"): Promise<StudyDraftsResponse> {
  return invoke("cmd_study_drafts", { kind });
}

export function cmdStudyArtifactActivate(artifactId: string): Promise<unknown> {
  return invoke("cmd_study_artifact_activate", { artifactId });
}

export function cmdStudyArtifactReject(artifactId: string): Promise<unknown> {
  return invoke("cmd_study_artifact_reject", { artifactId });
}

export function cmdStudyFlashcards(dueOnly = false): Promise<StudyFlashcardsResponse> {
  return invoke("cmd_study_flashcards", { dueOnly });
}

export function cmdStudyFlashcardCapture(payload: StudyFlashcardCaptureRequest): Promise<StudyCaptureResponse> {
  return invoke("cmd_study_flashcard_capture", { body: payload });
}

export function cmdStudyFlashcardReview(itemId: string, grade: string): Promise<StudyFlashcard & { grade: string }> {
  return invoke("cmd_study_flashcard_review", { itemId, grade });
}

export function cmdStudyMigrateFlashcards(deck: unknown): Promise<StudyMigrationResponse> {
  return invoke("cmd_study_migrate_flashcards", { deck });
}

export function cmdStudyQuizzes(): Promise<StudyQuizzesResponse> {
  return invoke("cmd_study_quizzes");
}

export function cmdStudyQuizQuestions(artifactId: string): Promise<StudyQuizQuestionsResponse> {
  return invoke("cmd_study_quiz_questions", { artifactId });
}

export function cmdStudyQuizSubmit(artifactId: string, responses: unknown): Promise<StudyQuizResult> {
  return invoke("cmd_study_quiz_submit", { artifactId, responses });
}

export function cmdStudyMigrateQuizzes(quiz: unknown): Promise<StudyQuizMigrationResponse> {
  return invoke("cmd_study_migrate_quizzes", { quiz });
}
