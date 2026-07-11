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

export type StudyArtifactSummary = Pick<
  StudyArtifact,
  "artifact_id" | "kind" | "title" | "status" | "review" | "updated_at"
>;

export type StudyDraftsResponse = {
  items: StudyArtifactSummary[];
  count: number;
  counts: Record<string, number>;
  kind_counts: Record<string, number>;
  returned: number;
  limit: number;
  offset: number;
  truncated: boolean;
};

export type StudyArtifactDetailResponse = {
  artifact: StudyArtifact & { envelope: Record<string, unknown> };
};

export type StudyWrongbookEvidence = {
  activity_id: string;
  artifact_id: string;
  activity_type: "quiz.attempt";
  created_at: string;
  score: number;
  max_score: number;
  percent: number;
  weak_tags: string[];
};

export type StudyWrongbookResponse = {
  weak_points: string[];
  evidence: StudyWrongbookEvidence[];
  count: number;
  returned: number;
  limit: number;
  truncated: boolean;
};

export type StudyLearningBundle = {
  version: 1;
  spaces?: unknown[];
  artifacts?: unknown[];
  items?: unknown[];
  activities?: unknown[];
  migrations?: unknown[];
};

export type StudyMigrationRecord = {
  migration_key: string;
  status: "done" | "failed";
  detail: Record<string, unknown>;
  created_at: string;
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

export type StudyQuizQuestionType = "choice" | "true_false" | "short_answer" | "code" | "derivation";

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
  language?: string;
  mode?: string;
  starter?: string;
  target_code?: string;
  variant_of?: string;
  steps?: Array<{ expr?: string; justification?: string; cloze?: boolean }>;
  target_steps?: Array<{ expr?: string; justification?: string }>;
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

export type StudyPracticeResponse = {
  generated: boolean;
  artifact_id?: string;
  status?: "draft";
  practice_kind?: "transcribe" | "variant";
  source_item_id: string;
  self_checked?: boolean;
  fallback?: "model_draft_required";
  reason?: string;
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

export function cmdStudyDrafts(kind?: string, limit = 50, offset = 0): Promise<StudyDraftsResponse> {
  return invoke("cmd_study_drafts", { kind, limit, offset });
}

export function cmdStudyArtifactSummaries(filters: {
  spaceId?: string;
  kind?: string;
  status?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<StudyDraftsResponse> {
  return invoke("cmd_study_artifact_summaries", filters);
}

export function cmdStudyArtifactDetail(artifactId: string): Promise<StudyArtifactDetailResponse> {
  return invoke("cmd_study_artifact_detail", { artifactId });
}

export function cmdStudyArtifactStatus(
  artifactId: string,
  status: "active" | "rejected" | "archived",
): Promise<{ artifact_id: string; status: string }> {
  return invoke("cmd_study_artifact_status", { artifactId, status });
}

export function cmdStudyWrongbook(limit = 50): Promise<StudyWrongbookResponse> {
  return invoke("cmd_study_wrongbook", { limit });
}

export function cmdStudyDataExport(): Promise<{ bundle: StudyLearningBundle }> {
  return invoke("cmd_study_data_export");
}

export function cmdStudyDataImport(bundle: StudyLearningBundle): Promise<{ imported: Record<string, number> }> {
  return invoke("cmd_study_data_import", { bundle });
}

export function cmdStudyDataDelete(confirm: string): Promise<{ deleted: boolean; counts: Record<string, number> }> {
  return invoke("cmd_study_data_delete", { confirm });
}

export function cmdStudyMigrationStatus(): Promise<{ migrations: StudyMigrationRecord[]; count: number }> {
  return invoke("cmd_study_migration_status");
}

export function cmdStudyMigrationFailuresExport(): Promise<{
  version: 1;
  failures: StudyMigrationRecord[];
  count: number;
}> {
  return invoke("cmd_study_migration_failures_export");
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

export function cmdStudyQuizGeneratePractice(
  artifactId: string,
  itemId: string,
  practiceKind: "transcribe" | "variant",
): Promise<StudyPracticeResponse> {
  return invoke("cmd_study_quiz_generate_practice", { artifactId, itemId, practiceKind });
}

export function cmdStudyMigrateQuizzes(quiz: unknown): Promise<StudyQuizMigrationResponse> {
  return invoke("cmd_study_migrate_quizzes", { quiz });
}

export type StudyBuiltinCourseResponse = {
  seeded: boolean;
  reason?: string;
  space_id?: string;
  title?: string;
  artifacts?: Array<{ artifact_id: string; kind: string; materialized: number }>;
  materials?: { written?: number; skipped?: number | string; path?: string };
};

export function cmdStudyMigrateBuiltinCourse(): Promise<StudyBuiltinCourseResponse> {
  return invoke("cmd_study_migrate_builtin_course");
}
