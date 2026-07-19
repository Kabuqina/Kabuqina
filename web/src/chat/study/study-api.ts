// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { invoke } from "@tauri-apps/api/core";

import { notifyStudyLearningChanged } from "./flashcardLearningStore";

async function invokeStudyMutation<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  const result = await invoke<T>(command, args);
  notifyStudyLearningChanged({ command, result });
  return result;
}

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
  // Panel-rendered drafts carry their payload (see study_routes._artifact_ref)
  payload?: ResourcePackPayload & StudentStatePayload & LearningPlanPayload & EvaluationPayload & KnowledgeBasePayload;
};

// M1 6-dimension learning profile (rendered by ProfilePanel radar).
export type ProfileDimension = { key: string; label?: string; level?: number; summary?: string };
export type StudentStatePayload = {
  dimensions?: ProfileDimension[];
  course?: string;
  goals?: string[];
  constraints?: string[];
  preferences?: Record<string, string>;
  progress_notes?: string[];
  current_stage?: string;
  generated_resources?: string[];
  tutoring_notes?: string[];
  weak_points?: string[];
  assessment_evidence?: string[];
  evaluation_summary?: string;
  next_adjustment?: string;
};

export type StudyStudentStateResponse = {
  state: null | { artifact_id: string; status: string; payload: StudentStatePayload };
  evaluation?: null | { artifact_id: string; status: string };
};

// M3 备课组 resource_pack subtypes (rendered by ResourcePackPanel).
export type ResourceMindmapNode = { label?: string; title?: string; children?: ResourceMindmapNode[] };
export type ResourceVideoScene = { narration?: string; visual?: string; caption?: string };
export type ResourceImage = {
  src?: string;
  url?: string;
  alt?: string;
  caption?: string;
};
export type ResourcePackResource = {
  title?: string;
  purpose?: string;
  content_markdown?: string;
  credibility?: string;
  resource_type?: string;
  difficulty?: string;
  reason?: string;
  url?: string;
  outline?: ResourceMindmapNode | ResourceMindmapNode[];
  mermaid?: string;
  scenes?: ResourceVideoScene[];
  images?: Array<ResourceImage | string>;
  [key: string]: unknown;
};
export type ResourcePackPayload = {
  resource_type?: string;
  resources?: ResourcePackResource[];
};

export type KnowledgeBaseConcept = {
  term: string;
  explanation: string;
  module?: string;
  content_markdown?: string;
  source_section?: string;
  source_locator?: string;
  review_prompt?: string;
  prerequisites?: string[];
  related?: string[];
};

export type KnowledgeBasePayload = {
  specialty?: string;
  course?: string;
  concepts?: KnowledgeBaseConcept[];
};

export type KnowledgeGraphNode = {
  id: string;
  artifact_id: string;
  concept_index: number;
  label: string;
  module: string;
  summary: string;
};

export type KnowledgeGraphEdge = {
  id: string;
  source: string;
  target: string;
  kind: "prerequisite" | "related";
};

export type StudyKnowledgeGraphResponse = {
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
  courses: string[];
};

export type KnowledgeConceptDetail = {
  artifact_id: string;
  concept_index: number;
  knowledge_base_title: string;
  specialty: string;
  course: string;
  term: string;
  module: string;
  explanation: string;
  content_markdown: string;
  source_section: string;
  source_locator: string;
  review_prompt: string;
  prerequisites: string[];
  related: string[];
};

export type StudyKnowledgeConceptResponse = {
  concept: KnowledgeConceptDetail;
};

// M4 personalized learning path (rendered by LearningPathPanel).
export type LearningPlanTask = {
  title?: string;
  order?: number;
  done_when?: string;
  [key: string]: unknown;
};
export type LearningPlanPhase = {
  title?: string;
  status?: "pending" | "active" | "done" | string;
  focus?: string;
  tasks?: LearningPlanTask[];
  [key: string]: unknown;
};
export type LearningPlanPayload = {
  goals?: string[];
  phases?: LearningPlanPhase[];
};

// M6 learning-effect evaluation (rendered by EvaluationPanel).
export type EvaluationPayload = {
  observations?: unknown[];
  weak_points?: string[];
  suggestions?: string[];
  evidence_refs?: Array<Record<string, string>>;
  evaluation_summary?: string;
  assessment_evidence?: string[];
  [key: string]: unknown;
};

export type StudyEvaluationsResponse = { evaluations: StudyArtifact[] };
export type StudyEvaluationDetailResponse = { evaluation: StudyArtifact };
export type StudyLearningPlansResponse = { plans: StudyArtifact[] };

export type StudyLearningPlanItem = {
  item_id: string;
  artifact_id: string;
  phaseIndex: number;
  phaseTitle?: string;
  taskIndex: number;
  title: string;
  order?: number;
  done_when?: string;
  status: "open" | "completed" | "skipped";
  note?: string;
};

export type StudyLearningPlanItemsResponse = { items: StudyLearningPlanItem[] };

export type StudyDraftsResponse = {
  drafts: StudyArtifact[];
};

export type StudyResourceArtifact = StudyArtifact & {
  kind: "resource_pack";
  space_id: string;
  payload: ResourcePackPayload;
  source_refs: Array<string | Record<string, unknown>>;
};

export type StudyArtifactDetailResponse = {
  artifact: StudyResourceArtifact;
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
  return invokeStudyMutation<StudySpacesResponse & { space_id: string }>("cmd_study_space_create", { title });
}

export function cmdStudySpaceSelect(spaceId: string): Promise<StudySpacesResponse & { space_id: string }> {
  return invokeStudyMutation<StudySpacesResponse & { space_id: string }>("cmd_study_space_select", { spaceId });
}

export function cmdStudyDrafts(kind = "flashcard_deck"): Promise<StudyDraftsResponse> {
  return invoke("cmd_study_drafts", { kind });
}

export function cmdStudyArtifactDetail(artifactId: string): Promise<StudyArtifactDetailResponse> {
  return invoke("cmd_study_artifact_detail", { artifactId });
}

export function cmdStudyKnowledgeGraph(): Promise<StudyKnowledgeGraphResponse> {
  return invoke("cmd_study_knowledge_graph");
}

export function cmdStudyKnowledgeConcept(
  artifactId: string,
  conceptIndex: number,
): Promise<StudyKnowledgeConceptResponse> {
  return invoke("cmd_study_knowledge_concept", { artifactId, conceptIndex });
}

export function cmdStudyArtifactActivate(artifactId: string): Promise<unknown> {
  return invokeStudyMutation<unknown>("cmd_study_artifact_activate", { artifactId });
}

export function cmdStudyArtifactReject(artifactId: string): Promise<unknown> {
  return invokeStudyMutation<unknown>("cmd_study_artifact_reject", { artifactId });
}

export function cmdStudyFlashcards(dueOnly = false): Promise<StudyFlashcardsResponse> {
  return invoke("cmd_study_flashcards", { dueOnly });
}

export function cmdStudyFlashcardCapture(payload: StudyFlashcardCaptureRequest): Promise<StudyCaptureResponse> {
  return invokeStudyMutation<StudyCaptureResponse>("cmd_study_flashcard_capture", { body: payload });
}

export function cmdStudyFlashcardReview(itemId: string, grade: string): Promise<StudyFlashcard & { grade: string }> {
  return invokeStudyMutation<StudyFlashcard & { grade: string }>("cmd_study_flashcard_review", { itemId, grade });
}

export function cmdStudyMigrateFlashcards(deck: unknown): Promise<StudyMigrationResponse> {
  return invokeStudyMutation<StudyMigrationResponse>("cmd_study_migrate_flashcards", { deck });
}

export function cmdStudyQuizzes(): Promise<StudyQuizzesResponse> {
  return invoke("cmd_study_quizzes");
}

export function cmdStudyQuizQuestions(artifactId: string): Promise<StudyQuizQuestionsResponse> {
  return invoke("cmd_study_quiz_questions", { artifactId });
}

export function cmdStudyQuizSubmit(artifactId: string, responses: unknown): Promise<StudyQuizResult> {
  return invokeStudyMutation<StudyQuizResult>("cmd_study_quiz_submit", { artifactId, responses });
}

export function cmdStudyMigrateQuizzes(quiz: unknown): Promise<StudyQuizMigrationResponse> {
  return invokeStudyMutation<StudyQuizMigrationResponse>("cmd_study_migrate_quizzes", { quiz });
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
  return invokeStudyMutation<StudyBuiltinCourseResponse>("cmd_study_migrate_builtin_course");
}

export function cmdStudyStudentState(): Promise<StudyStudentStateResponse> {
  return invoke("cmd_study_student_state");
}

export function cmdStudyStudentStateSave(
  state: StudentStatePayload,
  evaluation: EvaluationPayload | null = null,
): Promise<StudyStudentStateResponse> {
  return invokeStudyMutation<StudyStudentStateResponse>("cmd_study_student_state_save", { state, evaluation });
}

export function cmdStudyMigrateContext(context: unknown): Promise<unknown> {
  return invokeStudyMutation<unknown>("cmd_study_migrate_context", { context });
}

export function cmdStudyEvaluations(): Promise<StudyEvaluationsResponse> {
  return invoke("cmd_study_evaluations");
}

export function cmdStudyEvaluationDetail(artifactId: string): Promise<StudyEvaluationDetailResponse> {
  return invoke("cmd_study_evaluation_detail", { artifactId });
}

export function cmdStudyLearningPlans(): Promise<StudyLearningPlansResponse> {
  return invoke("cmd_study_learning_plans");
}

export function cmdStudyLearningPlanItems(artifactId: string): Promise<StudyLearningPlanItemsResponse> {
  return invoke("cmd_study_learning_plan_items", { artifactId });
}

export function cmdStudyLearningPlanItemComplete(itemId: string, note = ""): Promise<StudyLearningPlanItem> {
  return invokeStudyMutation<StudyLearningPlanItem>("cmd_study_learning_plan_item_complete", { itemId, note });
}

export function cmdStudyLearningPlanItemSkip(itemId: string, note = ""): Promise<StudyLearningPlanItem> {
  return invokeStudyMutation<StudyLearningPlanItem>("cmd_study_learning_plan_item_skip", { itemId, note });
}
