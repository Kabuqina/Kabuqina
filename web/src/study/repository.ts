// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import {
  cmdStudyActivities,
  cmdStudyArtifactDetail,
  cmdStudyArtifactSemanticReview,
  cmdStudyArtifactSourceAudit,
  cmdStudyArtifactSummaries,
  cmdStudyArtifactStatus,
  cmdStudyEvaluations,
  cmdStudyFlashcardReview,
  cmdStudyFlashcards,
  cmdStudyLearningPlans,
  cmdStudyKnowledgePoints,
  cmdStudyMigrateContext,
  cmdStudyPlanItemComplete,
  cmdStudyPlanItemSkip,
  cmdStudyPlanItems,
  cmdStudyPracticeSource,
  cmdStudyQuizGeneratePractice,
  cmdStudyQuizQuestions,
  cmdStudyQuizSubmit,
  cmdStudyQuizzes,
  cmdStudySpaces,
  cmdStudySpaceSelect,
  cmdStudyStudentState,
  cmdStudyWrongbook,
  type StudyActivitiesResponse,
  type StudyArtifactSummary,
  type StudyDraftsResponse,
  type StudyEvaluationProjection,
  type StudyFlashcard,
  type StudyKnowledgePoint,
  type StudyPlanItem,
  type StudyPracticeResponse,
  type StudyPracticeSource,
  type StudyQuizQuestion,
  type StudyQuizResult,
  type StudySpacesResponse,
  type StudySourceRef,
  type StudyStudentState,
  type StudyWrongbookResponse,
} from "../chat/study/study-api";

export type StudySpaceSummary = {
  id: string;
  title: string;
  status: string;
  isCurrent: boolean;
};

export type StudySpaces = {
  currentSpaceId: string | null;
  spaces: StudySpaceSummary[];
};

export type StudyDraftInbox = {
  total: number;
  kindCounts: Readonly<Record<string, number>>;
};

export type StudyDraftPage = {
  items: StudyArtifactSummary[];
  total: number;
  kindCounts: Readonly<Record<string, number>>;
  returned: number;
  limit: number;
  offset: number;
  truncated: boolean;
};

export type StudyM5Kind = "knowledge_base" | "resource_pack" | "tutoring_note";

export type StudyLearnHome = {
  artifacts: StudyArtifactSummary[];
  knowledgePoints: StudyKnowledgePoint[];
  unavailable?: Array<"knowledgePoints">;
  unavailableKinds?: StudyM5Kind[];
};

export type StudyArtifactDetail = {
  artifactId: string;
  kind: string;
  title: string;
  version: number;
  status: string;
  review: { mode?: string; status?: string };
  createdAt?: string;
  updatedAt?: string;
  envelope: Record<string, unknown>;
};

export type StudyFlyleafSnapshot = {
  active: StudyStudentState | null;
};

export type StudyPlanSnapshot = {
  plan: StudyArtifactSummary | null;
  items: StudyPlanItem[];
};

export type StudyEvaluationSnapshot = {
  evaluation: StudyEvaluationProjection | null;
};

export type StudyPracticeHome = {
  cards: StudyFlashcard[];
  dueCards: StudyFlashcard[];
  quizzes: StudyArtifactSummary[];
  unavailable?: Array<"cards" | "quizzes">;
};

export type StudyRepositoryErrorCode =
  | "unavailable"
  | "not-found"
  | "conflict"
  | "invalid"
  | "unknown";

export class StudyRepositoryError extends Error {
  constructor(
    public readonly code: StudyRepositoryErrorCode,
    options?: { cause?: unknown },
  ) {
    super(`study repository: ${code}`, options);
    this.name = "StudyRepositoryError";
  }
}

export interface StudyRepository {
  listSpaces(signal: AbortSignal): Promise<StudySpaces>;
  selectSpace(spaceId: string, signal: AbortSignal): Promise<StudySpaces>;
  listDrafts(spaceId: string, signal: AbortSignal): Promise<StudyDraftInbox>;
  listDraftPage(spaceId: string, limit: number, offset: number, signal: AbortSignal): Promise<StudyDraftPage>;
  loadLearnHome(spaceId: string, signal: AbortSignal): Promise<StudyLearnHome>;
  loadArtifactDetail(spaceId: string, artifactId: string, signal: AbortSignal): Promise<StudyArtifactDetail>;
  loadSourceAudit(spaceId: string, artifactId: string, signal: AbortSignal): Promise<StudySourceRef[]>;
  runSemanticReview(
    spaceId: string,
    artifactId: string,
    signal: AbortSignal,
  ): Promise<"pending" | "passed" | "failed">;
  loadFlyleaf(spaceId: string, signal: AbortSignal): Promise<StudyFlyleafSnapshot>;
  migrateLegacyContext(spaceId: string, context: unknown, signal: AbortSignal): Promise<boolean>;
  setArtifactStatus(
    spaceId: string,
    artifactId: string,
    status: "active" | "rejected" | "archived",
    signal: AbortSignal,
  ): Promise<void>;
  loadPlan(spaceId: string, signal: AbortSignal): Promise<StudyPlanSnapshot>;
  completePlanItem(spaceId: string, itemId: string, signal: AbortSignal): Promise<StudyPlanItem>;
  skipPlanItem(spaceId: string, itemId: string, signal: AbortSignal): Promise<StudyPlanItem>;
  loadWrongbook(spaceId: string, signal: AbortSignal): Promise<StudyWrongbookResponse>;
  loadLatestEvaluation(spaceId: string, signal: AbortSignal): Promise<StudyEvaluationSnapshot>;
  loadActivities(spaceId: string, signal: AbortSignal): Promise<StudyActivitiesResponse>;
  loadPracticeHome(spaceId: string, signal: AbortSignal): Promise<StudyPracticeHome>;
  loadQuizQuestions(spaceId: string, artifactId: string, signal: AbortSignal): Promise<StudyQuizQuestion[]>;
  reviewFlashcard(
    spaceId: string,
    itemId: string,
    grade: "again" | "hard" | "good" | "easy",
    signal: AbortSignal,
  ): Promise<StudyFlashcard & { grade: string }>;
  submitQuiz(
    spaceId: string,
    artifactId: string,
    responses: unknown,
    signal: AbortSignal,
  ): Promise<StudyQuizResult>;
  generatePracticeDraft(
    spaceId: string,
    artifactId: string,
    itemId: string,
    kind: "transcribe" | "variant",
    signal: AbortSignal,
  ): Promise<StudyPracticeResponse>;
  resolvePracticeSource(
    spaceId: string,
    activityId: string,
    signal: AbortSignal,
  ): Promise<StudyPracticeSource>;
}

type DeskBridgeErrorPayload = {
  status: number | null;
  code: string;
  detail: string;
};

function isDeskBridgeErrorPayload(error: unknown): error is DeskBridgeErrorPayload {
  if (!error || typeof error !== "object") return false;
  const candidate = error as Record<string, unknown>;
  return (
    (candidate.status === null || typeof candidate.status === "number") &&
    typeof candidate.code === "string" &&
    typeof candidate.detail === "string"
  );
}

type StudyCommands = {
  spaces: () => Promise<StudySpacesResponse>;
  selectSpace: (spaceId: string) => Promise<StudySpacesResponse>;
  draftSummary: (spaceId: string) => Promise<StudyDraftsResponse>;
  drafts: (spaceId: string, limit: number, offset: number) => Promise<StudyDraftsResponse>;
  activeM5Summaries: (spaceId: string, kind: StudyM5Kind) => Promise<StudyDraftsResponse>;
  artifactDetail: (spaceId: string, artifactId: string) => ReturnType<typeof cmdStudyArtifactDetail>;
  artifactStatus: typeof cmdStudyArtifactStatus;
  artifactSourceAudit: typeof cmdStudyArtifactSourceAudit;
  artifactSemanticReview: typeof cmdStudyArtifactSemanticReview;
  knowledgePoints: typeof cmdStudyKnowledgePoints;
  studentState: typeof cmdStudyStudentState;
  migrateContext: typeof cmdStudyMigrateContext;
  learningPlans: typeof cmdStudyLearningPlans;
  planItems: typeof cmdStudyPlanItems;
  completePlanItem: typeof cmdStudyPlanItemComplete;
  skipPlanItem: typeof cmdStudyPlanItemSkip;
  wrongbook: typeof cmdStudyWrongbook;
  evaluations: typeof cmdStudyEvaluations;
  activities: typeof cmdStudyActivities;
  flashcards: typeof cmdStudyFlashcards;
  flashcardReview: typeof cmdStudyFlashcardReview;
  quizzes: typeof cmdStudyQuizzes;
  quizQuestions: typeof cmdStudyQuizQuestions;
  quizSubmit: typeof cmdStudyQuizSubmit;
  quizGeneratePractice: typeof cmdStudyQuizGeneratePractice;
  practiceSource: typeof cmdStudyPracticeSource;
};

const defaultCommands: StudyCommands = {
  spaces: cmdStudySpaces,
  selectSpace: cmdStudySpaceSelect,
  draftSummary: (spaceId) => cmdStudyArtifactSummaries({
    spaceId,
    status: "draft",
    limit: 1,
  }),
  drafts: (spaceId, limit, offset) => cmdStudyArtifactSummaries({
    spaceId,
    status: "draft",
    limit,
    offset,
  }),
  activeM5Summaries: (spaceId, kind) => cmdStudyArtifactSummaries({
    spaceId,
    kind,
    status: "active",
    limit: 100,
  }),
  artifactDetail: cmdStudyArtifactDetail,
  artifactStatus: cmdStudyArtifactStatus,
  artifactSourceAudit: cmdStudyArtifactSourceAudit,
  artifactSemanticReview: cmdStudyArtifactSemanticReview,
  knowledgePoints: cmdStudyKnowledgePoints,
  studentState: cmdStudyStudentState,
  migrateContext: cmdStudyMigrateContext,
  learningPlans: cmdStudyLearningPlans,
  planItems: cmdStudyPlanItems,
  completePlanItem: cmdStudyPlanItemComplete,
  skipPlanItem: cmdStudyPlanItemSkip,
  wrongbook: cmdStudyWrongbook,
  evaluations: cmdStudyEvaluations,
  activities: cmdStudyActivities,
  flashcards: cmdStudyFlashcards,
  flashcardReview: cmdStudyFlashcardReview,
  quizzes: cmdStudyQuizzes,
  quizQuestions: cmdStudyQuizQuestions,
  quizSubmit: cmdStudyQuizSubmit,
  quizGeneratePractice: cmdStudyQuizGeneratePractice,
  practiceSource: cmdStudyPracticeSource,
};

function abortError(): DOMException {
  return new DOMException("The operation was aborted", "AbortError");
}

async function invokeWithSignal<T>(signal: AbortSignal, invoke: () => Promise<T>): Promise<T> {
  if (signal.aborted) throw abortError();
  try {
    const value = await invoke();
    if (signal.aborted) throw abortError();
    return value;
  } catch (error) {
    if (signal.aborted) throw abortError();
    throw normalizeRepositoryError(error);
  }
}

function mapSpaces(response: StudySpacesResponse): StudySpaces {
  const spaces = response.spaces.map((space) => ({
    id: space.space_id,
    title: space.title,
    status: space.status,
    isCurrent: space.is_current,
  }));
  return {
    currentSpaceId:
      response.currentSpaceId ?? spaces.find((space) => space.isCurrent)?.id ?? null,
    spaces,
  };
}

export function normalizeRepositoryError(error: unknown): StudyRepositoryError {
  if (error instanceof StudyRepositoryError) return error;
  if (isDeskBridgeErrorPayload(error)) {
    if (["desk_not_ready", "desk_auth_not_ready", "desk_transport_error"].includes(error.code)) {
      return new StudyRepositoryError("unavailable", { cause: error });
    }
    if (error.code === "study_not_found" || error.status === 404) {
      return new StudyRepositoryError("not-found", { cause: error });
    }
    if (error.code === "study_conflict" || error.status === 409) {
      return new StudyRepositoryError("conflict", { cause: error });
    }
    if (["study_invalid_request", "invalid_study_id"].includes(error.code) || error.status === 400) {
      return new StudyRepositoryError("invalid", { cause: error });
    }
    return new StudyRepositoryError("unknown", { cause: error });
  }
  const message = error instanceof Error ? error.message : String(error);
  const stablePrefix = message.split(":", 1)[0].trim().toLowerCase();

  if (
    stablePrefix === "desk_not_ready" ||
    message.startsWith("Kabuqina is not ready yet") ||
    message.startsWith("Hermes is not ready yet")
  ) {
    return new StudyRepositoryError("unavailable", { cause: error });
  }
  if (stablePrefix === "invalid study id" || stablePrefix === "invalid_study_id") {
    return new StudyRepositoryError("invalid", { cause: error });
  }
  if (stablePrefix === "study_not_found" || stablePrefix === "space_not_found") {
    return new StudyRepositoryError("not-found", { cause: error });
  }
  if (stablePrefix === "study_conflict") {
    return new StudyRepositoryError("conflict", { cause: error });
  }
  return new StudyRepositoryError("unknown", { cause: error });
}

function newestArtifact<T extends { artifact_id: string; updated_at?: string }>(items: T[]): T | null {
  return [...items].sort((a, b) =>
    `${b.updated_at ?? ""}:${b.artifact_id}`.localeCompare(
      `${a.updated_at ?? ""}:${a.artifact_id}`,
    ),
  )[0] ?? null;
}

function mapDraftPage(response: StudyDraftsResponse): StudyDraftPage {
  return {
    items: response.items,
    total: response.count,
    kindCounts: response.kind_counts,
    returned: response.returned,
    limit: response.limit,
    offset: response.offset,
    truncated: response.truncated,
  };
}

function mapArtifactDetail(response: Awaited<ReturnType<typeof cmdStudyArtifactDetail>>): StudyArtifactDetail {
  const artifact = response.artifact;
  return {
    artifactId: artifact.artifact_id,
    kind: artifact.kind,
    title: artifact.title,
    version: artifact.version,
    status: artifact.status,
    review: artifact.review ?? {},
    createdAt: artifact.created_at,
    updatedAt: artifact.updated_at,
    envelope: artifact.envelope,
  };
}

export function createStudyRepository(commands: Partial<StudyCommands> = {}): StudyRepository {
  const resolved = { ...defaultCommands, ...commands };
  return {
    async listSpaces(signal) {
      return mapSpaces(await invokeWithSignal(signal, resolved.spaces));
    },
    async selectSpace(spaceId, signal) {
      return mapSpaces(await invokeWithSignal(signal, () => resolved.selectSpace(spaceId)));
    },
    async listDrafts(spaceId, signal) {
      const response = await invokeWithSignal(signal, () => resolved.draftSummary(spaceId));
      return { total: response.count, kindCounts: response.kind_counts };
    },
    async listDraftPage(spaceId, limit, offset, signal) {
      return mapDraftPage(await invokeWithSignal(
        signal,
        () => resolved.drafts(spaceId, limit, offset),
      ));
    },
    async loadLearnHome(spaceId, signal) {
      return invokeWithSignal(signal, async () => {
        const kinds: StudyM5Kind[] = ["knowledge_base", "resource_pack", "tutoring_note"];
        const [artifactResults, knowledgePointsResult] = await Promise.all([
          Promise.allSettled(kinds.map((kind) => resolved.activeM5Summaries(spaceId, kind))),
          Promise.resolve(resolved.knowledgePoints(spaceId)).then(
            (value) => ({ status: "fulfilled" as const, value }),
            (reason) => ({ status: "rejected" as const, reason }),
          ),
        ]);
        const fulfilledArtifacts = artifactResults.filter(
          (result): result is PromiseFulfilledResult<StudyDraftsResponse> => result.status === "fulfilled",
        );
        if (!fulfilledArtifacts.length && knowledgePointsResult.status === "rejected") {
          throw artifactResults.find((result): result is PromiseRejectedResult => result.status === "rejected")?.reason
            ?? knowledgePointsResult.reason;
        }
        const unavailableKinds = kinds.filter(
          (_kind, index) => artifactResults[index].status === "rejected",
        );
        const unavailable: Array<"knowledgePoints"> = [];
        if (knowledgePointsResult.status !== "fulfilled") unavailable.push("knowledgePoints");
        return {
          artifacts: fulfilledArtifacts.flatMap((result) => result.value.items),
          knowledgePoints: knowledgePointsResult.status === "fulfilled"
            ? knowledgePointsResult.value.items
            : [],
          ...(unavailable.length ? { unavailable } : {}),
          ...(unavailableKinds.length ? { unavailableKinds } : {}),
        };
      });
    },
    async loadArtifactDetail(spaceId, artifactId, signal) {
      return mapArtifactDetail(await invokeWithSignal(
        signal,
        () => resolved.artifactDetail(spaceId, artifactId),
      ));
    },
    async loadSourceAudit(spaceId, artifactId, signal) {
      return invokeWithSignal(signal, async () => (
        (await resolved.artifactSourceAudit(spaceId, artifactId)).source_refs
      ));
    },
    async runSemanticReview(spaceId, artifactId, signal) {
      return invokeWithSignal(signal, async () => (
        (await resolved.artifactSemanticReview(spaceId, artifactId)).status
      ));
    },
    async loadFlyleaf(spaceId, signal) {
      return invokeWithSignal(signal, async () => {
        return {
          active: (await resolved.studentState(spaceId)).state,
        };
      });
    },
    async migrateLegacyContext(spaceId, context, signal) {
      const response = await invokeWithSignal(
        signal,
        () => resolved.migrateContext(spaceId, context),
      );
      return response.migrated;
    },
    async setArtifactStatus(spaceId, artifactId, status, signal) {
      await invokeWithSignal(
        signal,
        () => resolved.artifactStatus(spaceId, artifactId, status),
      );
    },
    async loadPlan(spaceId, signal) {
      return invokeWithSignal(signal, async () => {
        const response = await resolved.learningPlans(spaceId);
        const plan = newestArtifact(response.plans);
        const items = plan
          ? (await resolved.planItems(spaceId, plan.artifact_id)).items
          : [];
        return { plan, items };
      });
    },
    completePlanItem(spaceId, itemId, signal) {
      return invokeWithSignal(signal, () => resolved.completePlanItem(spaceId, itemId));
    },
    skipPlanItem(spaceId, itemId, signal) {
      return invokeWithSignal(signal, () => resolved.skipPlanItem(spaceId, itemId));
    },
    loadWrongbook(spaceId, signal) {
      return invokeWithSignal(signal, () => resolved.wrongbook(spaceId));
    },
    async loadLatestEvaluation(spaceId, signal) {
      return invokeWithSignal(signal, async () => ({
        evaluation: (await resolved.evaluations(spaceId)).evaluations[0] ?? null,
      }));
    },
    loadActivities(spaceId, signal) {
      return invokeWithSignal(signal, () => resolved.activities(spaceId));
    },
    loadPracticeHome(spaceId, signal) {
      return invokeWithSignal(signal, async () => {
        const [cardsResult, dueCardsResult, quizzesResult] = await Promise.allSettled([
          resolved.flashcards(spaceId, false),
          resolved.flashcards(spaceId, true),
          resolved.quizzes(spaceId),
        ]);
        const unavailable: Array<"cards" | "quizzes"> = [];
        if (cardsResult.status !== "fulfilled" || dueCardsResult.status !== "fulfilled") unavailable.push("cards");
        if (quizzesResult.status !== "fulfilled") unavailable.push("quizzes");
        if (unavailable.length === 2) {
          const failure = [cardsResult, dueCardsResult, quizzesResult]
            .find((result): result is PromiseRejectedResult => result.status === "rejected");
          throw failure?.reason ?? new Error("practice home unavailable");
        }
        return {
          cards: cardsResult.status === "fulfilled" ? cardsResult.value.cards : [],
          dueCards: dueCardsResult.status === "fulfilled" ? dueCardsResult.value.cards : [],
          quizzes: quizzesResult.status === "fulfilled" ? quizzesResult.value.quizzes : [],
          ...(unavailable.length ? { unavailable } : {}),
        };
      });
    },
    loadQuizQuestions(spaceId, artifactId, signal) {
      return invokeWithSignal(signal, async () => (
        (await resolved.quizQuestions(spaceId, artifactId)).questions
      ));
    },
    reviewFlashcard(spaceId, itemId, grade, signal) {
      return invokeWithSignal(signal, () => resolved.flashcardReview(spaceId, itemId, grade));
    },
    submitQuiz(spaceId, artifactId, responses, signal) {
      return invokeWithSignal(signal, () => resolved.quizSubmit(spaceId, artifactId, responses));
    },
    generatePracticeDraft(spaceId, artifactId, itemId, kind, signal) {
      return invokeWithSignal(signal, () => (
        resolved.quizGeneratePractice(spaceId, artifactId, itemId, kind)
      ));
    },
    async resolvePracticeSource(spaceId, activityId, signal) {
      return invokeWithSignal(signal, async () => (
        (await resolved.practiceSource(spaceId, activityId)).source
      ));
    },
  };
}

export const studyRepository = createStudyRepository();
