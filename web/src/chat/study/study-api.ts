// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { invoke } from "@tauri-apps/api/core";

/** 杂记本是一本**不属于任何课程**的本子（账本 B-12）。缺省视作课程，旧库无需迁移。 */
export type StudySpaceKind = "course" | "scratch";

export type StudySpace = {
  space_id: string;
  title: string;
  status: string;
  is_current: boolean;
  kind?: StudySpaceKind;
};

/** 随手写落在杂记本里的一条。`origin` 是给学生看的来源短语，不是 session id。 */
export type StudyScratchNote = {
  id: string;
  text: string;
  origin: string;
  createdAt?: string;
};

export type StudyScratchPage = {
  pad: string;
  notes: StudyScratchNote[];
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

export type StudySourceScalar = string | number | boolean | null;
export type StudySourceRef = string | Record<string, StudySourceScalar>;

export type StudyKnowledgePoint = {
  item_id: string;
  artifact_id: string;
  front: string;
  gist: string;
  confidence?: string;
  captured: true;
};

export type StudyKnowledgePointsResponse = {
  items: StudyKnowledgePoint[];
  count: number;
  returned: number;
  limit: number;
  truncated: boolean;
};

export type StudyLearningMapOutlineNode = {
  id: string;
  parentId: string | null;
  title: string;
  order: number;
  depth: 1 | 2 | 3;
  origin: "extracted" | "inferred_confirmed";
  sourceRef: Record<string, StudySourceScalar>;
  locator: string;
};

export type StudyLearningMapCore = {
  id: string;
  itemId: string;
  artifactId: string;
  front: string;
  gist: string;
  captured: true;
  outlineNodeId: string | null;
  order: number;
  sourceRefs?: StudySourceRef[];
};

export type StudyLearningMapExercise = {
  knowledgeCoreId: string;
  quizArtifactId: string;
  exerciseId: string;
  origin: StudyExerciseOrigin;
  sourceRefs: StudyExerciseSourceRef[];
  order: number;
};

export type StudyLearningMap = {
  revision: number;
  outlineStatus: "ready" | "weak" | "missing";
  outlineNodes: StudyLearningMapOutlineNode[];
  knowledgeCores: StudyLearningMapCore[];
  exerciseLinks: StudyLearningMapExercise[];
};

export type KnowledgeCoreCompilationTrigger =
  | "plan_activated"
  | "start_learning"
  | "prefetch"
  | "retry";

export type KnowledgeCoreCompilationStatus =
  | "queued"
  | "reading"
  | "generating"
  | "validating"
  | "draft_ready"
  | "needs_source"
  | "failed"
  | "cancelled";

export type KnowledgeCoreCompilationRequest = {
  spaceId: string;
  outlineNodeId: string;
  planItemId?: string;
  trigger: KnowledgeCoreCompilationTrigger;
  expectedMapRevision: number;
  idempotencyKey: string;
  priority?: number;
};

export type KnowledgeCoreCompilationSourceWindow = {
  id: string;
  artifactId: string;
  sourceTitle: string;
  sourceRole: string;
  pageStart: number;
  pageEnd: number;
  locator: string;
  contentFingerprint: string;
};

export type KnowledgeCoreCompilationRun = {
  runId: string;
  spaceId: string;
  outlineNodeId: string;
  planItemId: string | null;
  trigger: KnowledgeCoreCompilationTrigger;
  status: KnowledgeCoreCompilationStatus;
  sourceFingerprint: string;
  policyVersion: string;
  draftArtifactId: string | null;
  reasonCode: string | null;
  sourceWindows: KnowledgeCoreCompilationSourceWindow[];
  createdAt: string;
  updatedAt: string;
};

export type KnowledgeCoreCompilationListResponse = {
  items: KnowledgeCoreCompilationRun[];
  count: number;
};

export type StudySharedLocation = {
  revision: number;
  mapRevision: number;
  page: "plan" | "learn" | "practice";
  knowledgeCoreId: string | null;
  outlineNodeId: string | null;
  planItemId: string | null;
  planOutlineNodeId: string | null;
  exerciseId: string | null;
  exerciseByCore: Record<string, string>;
  stale: boolean;
  staleReason?: string;
  updatedAt: string;
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

export type StudyStudentStatePayload = {
  course: string;
  goals: string[];
  preferences: Record<string, string>;
  constraints: string[];
  progress_notes: string[];
  current_stage: string;
  next_adjustment: string;
};

export type StudyStudentState = {
  artifact_id: string;
  status: string;
  payload: StudyStudentStatePayload;
};

export type StudyPlanItem = {
  item_id: string;
  artifact_id: string;
  phaseIndex: number;
  phaseTitle: string;
  taskIndex: number;
  title: string;
  order: number;
  done_when: string;
  mode?: "learn" | "practice" | "review";
  outlineNodeId?: string;
  status: "open" | "completed" | "skipped";
  completedAt: string;
  skippedAt: string;
  note: string;
  createdAt: string;
};

export type StudyEvaluationPayload = {
  observations: string[];
  weak_points: string[];
  suggestions: string[];
  evidence_refs?: Array<Record<string, string>>;
};

export type StudyEvaluationDetail = StudyArtifactSummary & {
  payload: StudyEvaluationPayload;
};

export type StudyEvaluationProjection = StudyEvaluationPayload & {
  artifact_id: string;
  title: string;
};

export type StudyActivitySummary = {
  activity_id: string;
  activity_type: string;
  artifact_id?: string | null;
  item_id?: string | null;
  created_at: string;
};

export type StudyActivitiesResponse = {
  items: StudyActivitySummary[];
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

export type StudyTokenUsageWindow = "week" | "month";

export type StudyTokenUsageMetrics = {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  succeededAttempts: number;
  inputMeasuredAttempts: number;
  outputMeasuredAttempts: number;
  incomplete: boolean;
};

export type StudyTokenUsageModel = StudyTokenUsageMetrics & {
  providerId: string;
  modelId: string;
};

export type StudyTokenUsageCourse = StudyTokenUsageMetrics & {
  spaceId: string;
  title: string;
  models: StudyTokenUsageModel[];
};

export type StudyTokenUsageResponse = {
  window: StudyTokenUsageWindow;
  startsAt: string;
  endsAt: string;
  totals: StudyTokenUsageMetrics;
  courses: StudyTokenUsageCourse[];
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
  queue?: StudyDailyReviewQueue | null;
};

export type StudyDailyReviewQueue = {
  date: string;
  limits: { new: number; review: number };
  completedToday: { new: number; review: number };
  remaining: { new: number; review: number };
  available: { new: number; review: number };
  shown: { new: number; review: number };
};

export type StudyImportReadMode = "auto" | "precise" | "math";

export type StudyPreferences = {
  importReadMode: StudyImportReadMode;
  dailyNewCardLimit: number;
  dailyReviewCardLimit: number;
  defaults: {
    importReadMode: StudyImportReadMode;
    dailyNewCardLimit: number;
    dailyReviewCardLimit: number;
  };
};

export type StudyMaterialReadResponse = {
  preferredMode: StudyImportReadMode;
  requestedMode: StudyImportReadMode;
  effectiveMode: StudyImportReadMode;
  limited: boolean;
  override: boolean;
  result: Record<string, unknown>;
  material?: {
    artifact_id: string;
    title: string;
    status: string;
    deduplicated: boolean;
  } | null;
};

export type StudyMaterialReaderNode = {
  id?: string;
  title: string;
  level?: number;
  page?: number;
  children?: StudyMaterialReaderNode[];
};

export type StudyMaterialReaderResponse = {
  artifactId: string;
  title: string;
  filename: string;
  suffix: string;
  totalPages: number;
  pageStart: number;
  pageEnd: number;
  content: string;
  outline: StudyMaterialReaderNode[];
  textQuality: string;
  warning: string;
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

export type StudyQuizzesResponse = {
  quizzes: StudyArtifact[];
};

export type StudyQuizQuestionType = "choice" | "true_false" | "short_answer" | "code" | "derivation";
export type StudyExerciseOrigin = "source" | "adapted" | "generated";
export type StudyExerciseSourceRef = string | Record<string, string | number | boolean | null>;

export type StudyQuizQuestion = {
  item_id: string;
  artifact_id: string;
  type: StudyQuizQuestionType;
  prompt: string;
  knowledge_core_id?: string;
  origin?: StudyExerciseOrigin;
  source_refs?: StudyExerciseSourceRef[];
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
  check?: "normalized-match" | "numeric-equivalence";
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
  explanation?: string;
  tags?: string[];
  mode?: string;
  timed_out?: boolean;
  ungraded?: boolean;
  gradable?: boolean;
  scored?: boolean;
  ungraded_steps?: number[];
  failure_kind?: string;
  failure_summary?: string;
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

export type StudyPracticeSource = {
  artifact_id: string;
  item_ids: string[];
};

export function cmdStudySpaces(): Promise<StudySpacesResponse> {
  return invoke("cmd_study_spaces");
}

// --- 杂记本（账本 B-12：后端尚未实现，命令落地即亮） ---

export function cmdStudyScratchGet(spaceId: string): Promise<StudyScratchPage> {
  return invoke("cmd_study_scratch_get", { spaceId });
}

export function cmdStudyScratchSavePad(spaceId: string, pad: string): Promise<void> {
  // 随手写就一页纸，全文覆盖，不做增量 diff。
  return invoke("cmd_study_scratch_save_pad", { spaceId, pad });
}

export function cmdStudyScratchFileNote(
  spaceId: string,
  noteId: string,
  targetSpaceId: string,
): Promise<void> {
  return invoke("cmd_study_scratch_file_note", { spaceId, noteId, targetSpaceId });
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
  spaceId: string;
  kind?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<StudyDraftsResponse> {
  return invoke("cmd_study_artifact_summaries", filters);
}

export function cmdStudyArtifactDetail(
  spaceId: string,
  artifactId: string,
): Promise<StudyArtifactDetailResponse> {
  return invoke("cmd_study_artifact_detail", { spaceId, artifactId });
}

export function cmdStudyArtifactStatus(
  spaceId: string,
  artifactId: string,
  status: "active" | "rejected" | "archived",
): Promise<{ artifact_id: string; status: string }> {
  return invoke("cmd_study_artifact_status", { spaceId, artifactId, status });
}

export function cmdStudyArtifactSourceAudit(
  spaceId: string,
  artifactId: string,
): Promise<{ artifact_id: string; source_refs: StudySourceRef[] }> {
  return invoke("cmd_study_artifact_source_audit", { spaceId, artifactId });
}

export function cmdStudyArtifactSemanticReview(
  spaceId: string,
  artifactId: string,
): Promise<{ artifact_id: string; status: "pending" | "passed" | "failed"; reviewed: boolean }> {
  return invoke("cmd_study_artifact_semantic_review", { spaceId, artifactId });
}

export function cmdStudyKnowledgePoints(
  spaceId: string,
  limit = 50,
): Promise<StudyKnowledgePointsResponse> {
  return invoke("cmd_study_knowledge_points", { spaceId, limit });
}

export function cmdStudyLearningMapGet(spaceId: string): Promise<StudyLearningMap> {
  return invoke("cmd_study_learning_map_get", { spaceId });
}

export function cmdStudyKnowledgeCoreCompilationCreate(
  body: KnowledgeCoreCompilationRequest,
): Promise<KnowledgeCoreCompilationRun> {
  return invoke("cmd_study_knowledge_core_compilation_create", { body });
}

export function cmdStudyKnowledgeCoreCompilationList(
  spaceId: string,
  outlineNodeId?: string,
): Promise<KnowledgeCoreCompilationListResponse> {
  return invoke("cmd_study_knowledge_core_compilation_list", { spaceId, outlineNodeId });
}

export function cmdStudyKnowledgeCoreCompilationGet(
  spaceId: string,
  runId: string,
): Promise<KnowledgeCoreCompilationRun> {
  return invoke("cmd_study_knowledge_core_compilation_get", { spaceId, runId });
}

export function cmdStudyKnowledgeCoreCompilationRetry(
  spaceId: string,
  runId: string,
): Promise<KnowledgeCoreCompilationRun> {
  return invoke("cmd_study_knowledge_core_compilation_retry", { spaceId, runId });
}

export function cmdStudyKnowledgeCoreCompilationCancel(
  spaceId: string,
  runId: string,
): Promise<KnowledgeCoreCompilationRun> {
  return invoke("cmd_study_knowledge_core_compilation_cancel", { spaceId, runId });
}

export function cmdStudyLocationGet(spaceId: string): Promise<StudySharedLocation | null> {
  return invoke("cmd_study_location_get", { spaceId });
}

export function cmdStudyLocationPut(input: {
  spaceId: string;
  expectedRevision: number;
  expectedMapRevision?: number;
  page: "plan" | "learn" | "practice";
  knowledgeCoreId?: string;
  exerciseId?: string;
  planItemId?: string;
}): Promise<StudySharedLocation> {
  return invoke("cmd_study_location_put", input);
}

export function cmdStudyWrongbook(spaceId: string, limit = 50): Promise<StudyWrongbookResponse> {
  return invoke("cmd_study_wrongbook", { spaceId, limit });
}

export function cmdStudyActivities(spaceId: string, limit = 50): Promise<StudyActivitiesResponse> {
  return invoke("cmd_study_activities", { spaceId, limit });
}

export function cmdStudyStudentState(spaceId: string): Promise<{ state: StudyStudentState | null }> {
  return invoke("cmd_study_student_state_get", { spaceId });
}

export function cmdStudyStudentStatePut(
  spaceId: string,
  state: StudyStudentStatePayload,
): Promise<{ state: StudyStudentState }> {
  return invoke("cmd_study_student_state_put", { spaceId, state });
}

export function cmdStudyMigrateContext(
  spaceId: string,
  context: unknown,
): Promise<{ migrated: boolean; student_state?: StudyStudentState; evaluation?: unknown }> {
  return invoke("cmd_study_migrate_context", { spaceId, context });
}

export function cmdStudyEvaluations(spaceId: string): Promise<{ evaluations: StudyEvaluationProjection[] }> {
  return invoke("cmd_study_evaluations", { spaceId });
}

export function cmdStudyEvaluationDetail(
  spaceId: string,
  artifactId: string,
): Promise<{ evaluation: StudyEvaluationDetail }> {
  return invoke("cmd_study_evaluation_detail", { spaceId, artifactId });
}

export function cmdStudyLearningPlans(spaceId: string): Promise<{ plans: StudyArtifactSummary[] }> {
  return invoke("cmd_study_learning_plans", { spaceId });
}

export function cmdStudyPlanItems(
  spaceId: string,
  artifactId: string,
): Promise<{ items: StudyPlanItem[] }> {
  return invoke("cmd_study_plan_items", { spaceId, artifactId });
}

export function cmdStudyPlanItemComplete(
  spaceId: string,
  itemId: string,
  note = "",
): Promise<StudyPlanItem> {
  return invoke("cmd_study_plan_item_complete", { spaceId, itemId, note });
}

export function cmdStudyPlanItemSkip(
  spaceId: string,
  itemId: string,
  note = "",
): Promise<StudyPlanItem> {
  return invoke("cmd_study_plan_item_skip", { spaceId, itemId, note });
}

export function cmdStudyDataExport(): Promise<{ bundle: StudyLearningBundle }> {
  return invoke("cmd_study_data_export");
}

export function cmdStudyTokenUsage(
  window: StudyTokenUsageWindow,
): Promise<StudyTokenUsageResponse> {
  return invoke("cmd_study_token_usage", { window });
}

export function cmdStudyDataImport(bundle: StudyLearningBundle): Promise<{ imported: Record<string, number> }> {
  return invoke("cmd_study_data_import", { bundle });
}

export function cmdStudyDataImportFile(pathStr: string): Promise<StudyLearningBundle> {
  return invoke("cmd_study_data_import_file", { pathStr });
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

export function cmdStudyFlashcards(
  spaceId: string,
  dueOnly = false,
): Promise<StudyFlashcardsResponse> {
  return invoke("cmd_study_flashcards", { spaceId, dueOnly });
}

export function cmdStudyPreferencesGet(): Promise<StudyPreferences> {
  return invoke("cmd_study_preferences_get");
}

export function cmdStudyPreferencesPut(
  patch: Partial<Pick<StudyPreferences, "importReadMode" | "dailyNewCardLimit" | "dailyReviewCardLimit">>,
): Promise<StudyPreferences> {
  return invoke("cmd_study_preferences_put", patch);
}

export function cmdStudyMaterialRead(input: {
  spaceId?: string;
  pathStr: string;
  requestedMode?: StudyImportReadMode;
  overrideLimit?: boolean;
  includeContent?: boolean;
  pageStart?: number;
  pageEnd?: number;
}): Promise<StudyMaterialReadResponse> {
  return invoke("cmd_study_material_read", input);
}

export function cmdStudyMaterialOpen(
  spaceId: string,
  artifactId: string,
): Promise<{ opened: true; filename: string }> {
  return invoke("cmd_study_material_open", { spaceId, artifactId });
}

export function cmdStudyMaterialReader(
  spaceId: string,
  artifactId: string,
  pageStart = 1,
  pageEnd = pageStart + 5,
): Promise<StudyMaterialReaderResponse> {
  return invoke("cmd_study_material_reader", { spaceId, artifactId, pageStart, pageEnd });
}

export function cmdStudyMaterialDelete(
  spaceId: string,
  artifactId: string,
): Promise<{ artifact_id: string; status: "deleted" }> {
  return invoke("cmd_study_material_delete", { spaceId, artifactId });
}

export function cmdStudyFlashcardCapture(payload: StudyFlashcardCaptureRequest): Promise<StudyCaptureResponse> {
  return invoke("cmd_study_flashcard_capture", { body: payload });
}

export function cmdStudyFlashcardReview(
  spaceId: string,
  itemId: string,
  grade: string,
): Promise<StudyFlashcard & { grade: string }> {
  return invoke("cmd_study_flashcard_review", { spaceId, itemId, grade });
}

export type StudyLegacyMigrationResponse = {
  migrated: boolean;
  artifact_id?: string;
  cards?: number;
  questions?: number;
  status?: string;
};

export function cmdStudyMigrateFlashcards(deck: unknown): Promise<StudyLegacyMigrationResponse> {
  return invoke("cmd_study_migrate_flashcards", { deck });
}

export function cmdStudyQuizzes(spaceId: string): Promise<StudyQuizzesResponse> {
  return invoke("cmd_study_quizzes", { spaceId });
}

export function cmdStudyQuizQuestions(
  spaceId: string,
  artifactId: string,
): Promise<StudyQuizQuestionsResponse> {
  return invoke("cmd_study_quiz_questions", { spaceId, artifactId });
}

export function cmdStudyQuizSubmit(
  spaceId: string,
  artifactId: string,
  responses: unknown,
  itemIds?: string[],
): Promise<StudyQuizResult> {
  return invoke("cmd_study_quiz_submit", {
    spaceId,
    artifactId,
    responses,
    ...(itemIds ? { itemIds } : {}),
  });
}

export function cmdStudyQuizGeneratePractice(
  spaceId: string,
  artifactId: string,
  itemId: string,
  practiceKind: "transcribe" | "variant",
): Promise<StudyPracticeResponse> {
  return invoke("cmd_study_quiz_generate_practice", { spaceId, artifactId, itemId, practiceKind });
}

export function cmdStudyPracticeSource(
  spaceId: string,
  activityId: string,
): Promise<{ source: StudyPracticeSource }> {
  return invoke("cmd_study_practice_source", { spaceId, activityId });
}

export function cmdStudyMigrateQuizzes(quiz: unknown): Promise<StudyLegacyMigrationResponse> {
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
