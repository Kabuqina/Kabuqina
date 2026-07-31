// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type {
  StudyQuizPerQuestion,
  StudyQuizQuestion,
} from "../../chat/study/study-api";
import { STUDY_LEARNING_EVENT } from "../learningEvent";
import {
  readStudyLocation,
  resolveKnowledgeCore,
  selectKnowledgeCore,
  updateStudyExercise,
  updateStudyPracticeState,
} from "../studyLocation";
import type {
  StudyRepository,
  StudySpaceSummary,
} from "../repository";
import type { DeskAdapter } from "./deskAdapter";
import type { CheckResult, DeskData, StudyStep } from "./types";

const DRAFT_STORAGE_PREFIX = "kabuqina.study.desk-draft.v1";

type StoredDeskDraft = {
  version: 1;
  currentStepId?: string;
  answers: Record<string, string>;
  stepStates: Record<string, StoredStepState>;
  updatedAt: string;
};

type StoredStepState = {
  activity: Exclude<import("./types").StudyActivity, "checking">;
  checkResult?: CheckResult;
};

function abortError(): DOMException {
  return new DOMException("The operation was aborted", "AbortError");
}

function storageKey(spaceId: string, artifactId: string): string {
  return `${DRAFT_STORAGE_PREFIX}:${spaceId}:${artifactId}`;
}

function readStoredDraft(spaceId: string, artifactId: string): StoredDeskDraft {
  const empty: StoredDeskDraft = {
    version: 1,
    answers: {},
    stepStates: {},
    updatedAt: new Date(0).toISOString(),
  };
  if (typeof window === "undefined") return empty;
  try {
    const raw = window.localStorage.getItem(storageKey(spaceId, artifactId));
    if (!raw) return empty;
    const parsed = JSON.parse(raw) as Partial<StoredDeskDraft>;
    if (
      parsed.version !== 1
      || !parsed.answers
      || typeof parsed.answers !== "object"
      || Array.isArray(parsed.answers)
    ) {
      return empty;
    }
    return {
      version: 1,
      currentStepId: typeof parsed.currentStepId === "string"
        ? parsed.currentStepId
        : undefined,
      answers: Object.fromEntries(
        Object.entries(parsed.answers)
          .filter((entry): entry is [string, string] => typeof entry[1] === "string"),
      ),
      stepStates: readStoredStepStates(parsed.stepStates),
      updatedAt: typeof parsed.updatedAt === "string" ? parsed.updatedAt : empty.updatedAt,
    };
  } catch {
    return empty;
  }
}

function isCheckResult(value: unknown): value is CheckResult {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const candidate = value as Partial<CheckResult>;
  return (candidate.verdict === "needs_revision" || candidate.verdict === "completed")
    && (candidate.annotationKind === undefined
      || candidate.annotationKind === "confirmed"
      || candidate.annotationKind === "revision"
      || candidate.annotationKind === "next_step")
    && typeof candidate.goodLabel === "string"
    && typeof candidate.good === "string"
    && typeof candidate.gap === "string"
    && typeof candidate.next === "string";
}

function readStoredStepStates(value: unknown): Record<string, StoredStepState> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const states: Record<string, StoredStepState> = {};
  for (const [stepId, raw] of Object.entries(value)) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) continue;
    const candidate = raw as { activity?: unknown; checkResult?: unknown };
    if (!(["ready", "dirty", "needs_revision", "completed"] as unknown[]).includes(candidate.activity)) continue;
    const activity = candidate.activity as StoredStepState["activity"];
    const checkResult = isCheckResult(candidate.checkResult) ? candidate.checkResult : undefined;
    states[stepId] = {
      activity,
      ...((activity === "needs_revision" || activity === "completed") && checkResult ? { checkResult } : {}),
    };
  }
  return states;
}

function writeStoredDraft(
  spaceId: string,
  artifactId: string,
  update: (current: StoredDeskDraft) => StoredDeskDraft,
): void {
  if (typeof window === "undefined") return;
  const next = update(readStoredDraft(spaceId, artifactId));
  try {
    window.localStorage.setItem(storageKey(spaceId, artifactId), JSON.stringify(next));
  } catch (error) {
    throw new Error("study desk: draft recovery storage unavailable", { cause: error });
  }
}

function mapStep(
  question: StudyQuizQuestion,
  index: number,
  total: number,
  initialDraft: string,
  initialState?: StoredStepState,
): StudyStep {
  const topic = question.tags?.[0] || "当前练习";
  return {
    id: question.item_id,
    artifactId: question.artifact_id,
    answerKind: question.type,
    kicker: `练习 · 第 ${index + 1} / ${total} 步`,
    title: `${topic} · 第 ${index + 1} 步`,
    prompt: question.prompt,
    origin: question.origin,
    sourceLabel: questionSourceLabel(question),
    referenceHint: question.tags?.length
      ? `回想：${question.tags.join(" · ")}`
      : "从题干中的关键词开始。",
    initialDraft,
    initialActivity: initialState?.activity ?? (initialDraft ? "dirty" : "ready"),
    initialCheckResult: initialState?.checkResult ?? null,
    options: question.options,
    multiple: question.multiple,
    language: question.language,
    mode: question.mode,
    starter: question.starter,
    targetCode: question.target_code,
    check: question.check,
    derivationSteps: question.steps,
    targetSteps: question.target_steps,
  };
}

function decodeResponse(question: StudyQuizQuestion, answer: string): Record<string, unknown> {
  if (question.type === "choice") {
    try {
      const selected = JSON.parse(answer);
      return {
        selected: Array.isArray(selected)
          ? selected.filter((value): value is number => Number.isInteger(value))
          : [],
      };
    } catch {
      return { selected: [] };
    }
  }
  if (question.type === "true_false") {
    return { value: answer === "true" ? true : answer === "false" ? false : null };
  }
  if (question.type === "code") return { code: answer };
  if (question.type === "derivation") {
    try {
      const steps = JSON.parse(answer);
      return {
        steps: steps && typeof steps === "object" && !Array.isArray(steps) ? steps : {},
      };
    } catch {
      return { steps: {} };
    }
  }
  return { text: answer };
}

function mapCheckResult(grade: StudyQuizPerQuestion): CheckResult {
  if (grade.correct) {
    return {
      verdict: "completed",
      annotationKind: "confirmed",
      goodLabel: "这一点已经说明清楚",
      good: grade.explanation || "这一步的答案成立，学习证据已经保存。",
      gap: "",
      next: "",
    };
  }
  const needsHumanCheck = grade.ungraded || grade.gradable === false;
  return {
    verdict: "needs_revision",
    annotationKind: needsHumanCheck ? "next_step" : "revision",
    goodLabel: needsHumanCheck ? "答案已经保留" : "已经完成作答",
    good: needsHumanCheck
      ? "这类答案需要进一步检查，原答案仍留在纸页上。"
      : "你的原答案已保留在这本笔记本中。",
    gap: grade.failure_summary
      || (needsHumanCheck ? "暂时不能自动判断这一步。" : "这一步还没有成立。"),
    next: needsHumanCheck
      ? "保留答案并请小娜一起检查。"
      : "回到题干，检查关键概念后再试一次。",
  };
}

function mapActivities(items: Awaited<ReturnType<StudyRepository["loadActivities"]>>["items"]) {
  return items.slice(0, 20).map((item) => ({
    id: item.activity_id,
    type: item.activity_type,
    ...(item.artifact_id ? { artifactId: item.artifact_id } : {}),
    ...(item.item_id ? { itemId: item.item_id } : {}),
    createdAt: item.created_at,
  }));
}

function normalized(value: string): string {
  return value.trim().toLocaleLowerCase().replace(/\s+/g, "");
}

function questionSourceLabel(question: StudyQuizQuestion): string | undefined {
  const ref = question.source_refs?.[0];
  if (typeof ref === "string") return ref.trim().slice(0, 240) || undefined;
  if (!ref || typeof ref !== "object") return undefined;
  const text = (key: string) => {
    const value = ref[key];
    return typeof value === "string" || typeof value === "number"
      ? String(value).trim()
      : "";
  };
  const title = text("title") || text("material_title") || text("source_label");
  const section = text("section") || text("section_title");
  const locator = text("locator") || text("source_ref") || (text("page") ? `第 ${text("page")} 页` : "");
  const label = [title, section, locator].filter(Boolean).join(" · ");
  return label.slice(0, 240) || undefined;
}

function exerciseOriginRank(question: StudyQuizQuestion): number {
  return question.origin === "source"
    ? 0
    : question.origin === "adapted"
      ? 1
      : question.origin === "generated"
        ? 2
        : 3;
}

export function questionBelongsToKnowledgeCore(
  question: StudyQuizQuestion,
  title: string,
  knowledgeCoreId?: string,
): boolean {
  if (question.knowledge_core_id) {
    return Boolean(knowledgeCoreId) && question.knowledge_core_id === knowledgeCoreId;
  }
  const core = normalized(title);
  if (!core) return false;
  return (question.tags ?? []).some((tag) => {
    const value = normalized(tag);
    return value === core || (value.length >= 2 && (value.includes(core) || core.includes(value)));
  });
}

export async function resolveWrongbookPracticeTarget(
  repository: StudyRepository,
  spaceId: string,
  activityId: string,
  signal: AbortSignal,
): Promise<{
  status: "resolved";
  point: import("../../chat/study/study-api").StudyKnowledgePoint;
  exerciseId: string;
} | { status: "question_missing" | "core_missing" }> {
  const source = await repository.resolvePracticeSource(spaceId, activityId, signal);
  const [questions, home] = await Promise.all([
    repository.loadQuizQuestions(spaceId, source.artifact_id, signal),
    repository.loadLearnHome(spaceId, signal),
  ]);
  const question = source.item_ids
    .map((itemId) => questions.find((candidate) => candidate.item_id === itemId))
    .find((candidate): candidate is StudyQuizQuestion => Boolean(candidate));
  if (!question) return { status: "question_missing" };
  const point = home.knowledgePoints.find((candidate) => (
    questionBelongsToKnowledgeCore(question, candidate.front, candidate.item_id)
  ));
  if (!point) return { status: "core_missing" };
  return { status: "resolved", point, exerciseId: question.item_id };
}

export function createStudyDeskAdapter(options: {
  repository: StudyRepository;
  spaceId: string;
  spaces: StudySpaceSummary[];
}): DeskAdapter {
  const { repository, spaceId, spaces } = options;
  let artifactId = "";
  let questionsById = new Map<string, StudyQuizQuestion>();
  let activeKnowledgeCore: import("../../chat/study/study-api").StudyKnowledgePoint | null = null;

  const updateStored = (
    stepId: string,
    updater: (current: StoredDeskDraft) => StoredDeskDraft,
  ) => {
    if (!artifactId) return;
    writeStoredDraft(spaceId, artifactId, (current) => ({
      ...updater(current),
      currentStepId: stepId,
      updatedAt: new Date().toISOString(),
    }));
  };
  const storeAnswer = (stepId: string, answer: string) => {
    updateStored(stepId, (current) => ({
      ...current,
      answers: { ...current.answers, [stepId]: answer },
    }));
  };
  const storeStepState = (
    stepId: string,
    activity: import("./types").StudyActivity,
    checkResult?: CheckResult | null,
  ) => {
    const recoverableActivity = activity === "checking" ? "dirty" : activity;
    updateStored(stepId, (current) => ({
      ...current,
      stepStates: {
        ...current.stepStates,
        [stepId]: {
          activity: recoverableActivity,
          ...((recoverableActivity === "needs_revision" || recoverableActivity === "completed") && checkResult
            ? { checkResult }
            : {}),
        },
      },
    }));
  };

  return {
    async loadDesk(signal) {
      const home = await repository.loadPracticeHome(spaceId, signal);
      if (signal.aborted) throw abortError();
      const quiz = home.quizzes[0] ?? null;
      const [questionsResult, learnResult, activitiesResult] = await Promise.allSettled([
        Promise.all(home.quizzes.map((candidate) => (
          repository.loadQuizQuestions(spaceId, candidate.artifact_id, signal)
        ))).then((groups) => groups.flat()),
        repository.loadLearnHome(spaceId, signal),
        repository.loadActivities(spaceId, signal),
      ]);
      if (signal.aborted) throw abortError();
      if (questionsResult.status !== "fulfilled") throw questionsResult.reason;
      const allQuestions = questionsResult.value;
      const learn = learnResult.status === "fulfilled" && learnResult.value?.artifacts
        ? learnResult.value
        : null;
      const activities = activitiesResult.status === "fulfilled" && activitiesResult.value?.items
        ? activitiesResult.value
        : null;

      const cores = learn?.knowledgePoints ?? [];
      const resolvedCore = resolveKnowledgeCore(spaceId, cores);
      const activeCoreIndex = resolvedCore?.index ?? 0;
      const activeCore = resolvedCore?.point ?? null;
      if (activeCore) selectKnowledgeCore(spaceId, activeCore, "practice");
      activeKnowledgeCore = activeCore;
      const mapLinks = activeCore && learn?.learningMap
        ? learn.learningMap.exerciseLinks
          .filter((link) => link.knowledgeCoreId === activeCore.item_id)
          .sort((left, right) => left.order - right.order)
        : null;
      const mapOrder = new Map(mapLinks?.map((link, index) => [
        `${link.quizArtifactId}:${link.exerciseId}`,
        index,
      ]));
      const questions = activeCore
        ? allQuestions
          .filter((question) => mapLinks
            ? mapOrder.has(`${question.artifact_id}:${question.item_id}`)
            : questionBelongsToKnowledgeCore(question, activeCore.front, activeCore.item_id))
          .sort((left, right) => mapLinks
            ? (mapOrder.get(`${left.artifact_id}:${left.item_id}`) ?? Number.MAX_SAFE_INTEGER)
              - (mapOrder.get(`${right.artifact_id}:${right.item_id}`) ?? Number.MAX_SAFE_INTEGER)
            : exerciseOriginRank(left) - exerciseOriginRank(right))
        : [];

      artifactId = quiz?.artifact_id ?? "";
      questionsById = new Map(questions.map((question) => [question.item_id, question]));
      const stored = readStoredDraft(spaceId, artifactId);
      const locationExerciseId = activeCore
        ? readStudyLocation(spaceId)?.exerciseByCore[activeCore.item_id] ?? stored.currentStepId
        : undefined;
      const initialStepIndex = Math.max(
        0,
        questions.findIndex((question) => question.item_id === locationExerciseId),
      );
      const currentQuestion = questions[initialStepIndex] ?? questions[0];
      const currentTopic = activeCore?.front ?? currentQuestion?.tags?.[0] ?? currentQuestion?.prompt ?? "当前知识核";

      const data: DeskData = {
        course: {
          name: spaces.find((space) => space.id === spaceId)?.title || "我的本子",
          notebookLabel: activeCore
            ? `${activeCore.front} · ${questions.length} 题`
            : `${quiz?.title ?? "当前本子"} · 尚无知识核`,
        },
        steps: questions.map((question, index) => (
          mapStep(
            question,
            index,
            questions.length,
            stored.answers[question.item_id] ?? "",
            stored.stepStates[question.item_id],
          )
        )),
        initialStepIndex,
        overview: {
          kicker: stored.currentStepId ? "继续上次学习" : "当前知识核的练习",
          heading: currentQuestion && stored.answers[currentQuestion.item_id]
            ? `从“${currentTopic}”继续`
            : `开始“${currentTopic}”`,
          body: currentQuestion && stored.answers[currentQuestion.item_id]
            ? "你的草稿仍在原来的纸页上，可以从这里继续检查。"
            : currentQuestion
              ? "先完成当前一道题；切回学习页时仍停留在这个知识核。"
              : "这一步还没有可用练习。你可以先回学习，或请小娜基于材料拟一份待审核练习。",
          resume: currentQuestion ? [
            {
              icon: stored.answers[currentQuestion.item_id] ? "circleCheck" : "circleDot",
              text: stored.answers[currentQuestion.item_id]
                ? "已恢复上次草稿"
                : "当前步骤尚未作答",
            },
            {
              icon: "circleDot",
              text: `待完成：${currentQuestion.prompt}`,
            },
          ] : [],
        },
        bookstand: {
          title: "我的本子",
          hint: "换课就是换一本本子。",
          // 杂记本不是课程，所以不混进这一排——它单独待在书立最右端。
          books: spaces
            .filter((space) => space.kind !== "scratch")
            .map((space) => ({
              id: space.id,
              name: space.title,
              current: space.id === spaceId,
            })),
          scratch: (() => {
            const book = spaces.find((space) => space.kind === "scratch");
            return book ? { id: book.id, name: book.title, current: false } : null;
          })(),
          newBookLabel: "开新本",
        },
        materials: {
          title: "知识源",
          hint: (learn?.artifacts ?? []).some((item) => item.kind === "resource_pack")
            ? "抽一本出来看；阅读位置不会改变学习进度。"
            : "还没有知识源，可以先添加一份。",
          items: (learn?.artifacts ?? []).filter((item) => item.kind === "resource_pack").slice(0, 8).map((item) => ({
            id: item.artifact_id,
            title: item.title,
            kind: item.kind,
            status: item.status,
          })),
          unavailable: !learn,
        },
        activities: mapActivities(activities?.items ?? []),
        activitiesUnavailable: !activities,
        dueCards: home.dueCards,
        cardsUnavailable: home.unavailable?.includes("cards"),
        dueCount: home.dueCards.length,
        knowledgeCores: cores,
        activeKnowledgeCoreIndex: activeCoreIndex,
      };
      return data;
    },

    persistDraft(stepId, answer) {
      storeAnswer(stepId, answer);
    },

    async saveDraft(stepId, answer, signal) {
      if (signal.aborted) throw abortError();
      storeAnswer(stepId, answer);
    },

    async checkAnswer(stepId, answer, signal) {
      const question = questionsById.get(stepId);
      const questionArtifactId = question?.artifact_id || artifactId;
      if (!question || !questionArtifactId) throw new Error("study desk: step is not loaded");
      const result = await repository.submitQuiz(
        spaceId,
        questionArtifactId,
        { [stepId]: decodeResponse(question, answer) },
        signal,
        [stepId],
      );
      if (signal.aborted) throw abortError();
      const grade = result.perQuestion.find((item) => item.item_id === stepId);
      if (!grade) throw new Error("study desk: grader omitted the current step");
      const checkResult = mapCheckResult(grade);
      try {
        storeStepState(stepId, checkResult.verdict, checkResult);
      } catch {
        // The backend attempt is already canonical evidence. Recovery metadata
        // must never turn a successful check into a duplicate submission.
      }
      window.dispatchEvent(new Event(STUDY_LEARNING_EVENT));
      return checkResult;
    },

    async reviewCard(itemId, grade, signal) {
      const reviewed = await repository.reviewFlashcard(spaceId, itemId, grade, signal);
      if (signal.aborted) throw abortError();
      window.dispatchEvent(new Event(STUDY_LEARNING_EVENT));
      return reviewed;
    },

    async loadActivities(signal) {
      const response = await repository.loadActivities(spaceId, signal);
      if (signal.aborted) throw abortError();
      return mapActivities(response.items);
    },

    markCurrentStep(stepId) {
      try {
        updateStored(stepId, (current) => current);
        if (activeKnowledgeCore) updateStudyExercise(spaceId, activeKnowledgeCore, stepId);
      } catch {
        // A bookmark is recovery metadata only; unavailable browser storage
        // must never prevent the canonical Study exercise from opening.
      }
    },

    markPracticeState(stepId, activity, checkResult) {
      try {
        storeStepState(stepId, activity, checkResult);
        if (activeKnowledgeCore) updateStudyPracticeState(spaceId, activeKnowledgeCore, stepId, activity);
      } catch {
        // Continue metadata remains recoverable projection only. Canonical
        // answer/check state is never allowed to fail because storage is full.
      }
    },
  };
}
