// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type {
  StudyQuizPerQuestion,
  StudyQuizQuestion,
} from "../../chat/study/study-api";
import { STUDY_LEARNING_EVENT } from "../learningEvent";
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
  updatedAt: string;
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
      updatedAt: typeof parsed.updatedAt === "string" ? parsed.updatedAt : empty.updatedAt,
    };
  } catch {
    return empty;
  }
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

function stepStandard(question: StudyQuizQuestion): string {
  if (question.type === "choice") {
    return question.multiple
      ? "选出所有符合题意的答案，再检查这一步。"
      : "选出最符合题意的答案，再检查这一步。";
  }
  if (question.type === "true_false") return "判断陈述是否成立，再检查这一步。";
  if (question.type === "code") return "保留可运行的代码答案，再检查这一小步。";
  if (question.type === "derivation") return "写下缺失的推导与理由，再检查这一小步。";
  return "用自己的话写下答案，再检查这一小步。";
}

function mapStep(
  question: StudyQuizQuestion,
  index: number,
  total: number,
  initialDraft: string,
): StudyStep {
  const topic = question.tags?.[0] || "当前练习";
  return {
    id: question.item_id,
    artifactId: question.artifact_id,
    answerKind: question.type,
    kicker: `练习 · 第 ${index + 1} / ${total} 步`,
    title: `${topic} · 第 ${index + 1} 步`,
    standard: stepStandard(question),
    prompt: question.prompt,
    referenceSummary: "先独立完成当前一步；需要时再展开这张参考折页。",
    referenceHint: question.tags?.length
      ? `回想：${question.tags.join(" · ")}`
      : "从题干中的关键词开始。",
    initialDraft,
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
      goodLabel: "这一点已经说明清楚",
      good: grade.explanation || "这一步的答案成立，学习证据已经保存。",
      gap: "",
      next: "",
    };
  }
  const needsHumanCheck = grade.ungraded || grade.gradable === false;
  return {
    verdict: "needs_revision",
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

export function createStudyDeskAdapter(options: {
  repository: StudyRepository;
  spaceId: string;
  spaces: StudySpaceSummary[];
}): DeskAdapter {
  const { repository, spaceId, spaces } = options;
  let artifactId = "";
  let questionsById = new Map<string, StudyQuizQuestion>();

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
  const clearSubmittedAnswer = (stepId: string) => {
    try {
      updateStored(stepId, (current) => {
        const answers = { ...current.answers };
        delete answers[stepId];
        return { ...current, answers };
      });
    } catch {
      // The attempt is already canonical backend evidence. A recovery-cache
      // cleanup failure must not turn success into a retry that duplicates it.
    }
  };

  return {
    async loadDesk(signal) {
      const home = await repository.loadPracticeHome(spaceId, signal);
      if (signal.aborted) throw abortError();
      const quiz = home.quizzes[0];
      if (!quiz) throw new Error("study desk: no active quiz");
      const [questionsResult, learnResult, activitiesResult] = await Promise.allSettled([
        repository.loadQuizQuestions(spaceId, quiz.artifact_id, signal),
        repository.loadLearnHome(spaceId, signal),
        repository.loadActivities(spaceId, signal),
      ]);
      if (signal.aborted) throw abortError();
      if (questionsResult.status !== "fulfilled") throw questionsResult.reason;
      const questions = questionsResult.value;
      if (!questions.length) throw new Error("study desk: active quiz has no questions");
      const learn = learnResult.status === "fulfilled" && learnResult.value?.artifacts
        ? learnResult.value
        : null;
      const activities = activitiesResult.status === "fulfilled" && activitiesResult.value?.items
        ? activitiesResult.value
        : null;

      artifactId = quiz.artifact_id;
      questionsById = new Map(questions.map((question) => [question.item_id, question]));
      const stored = readStoredDraft(spaceId, artifactId);
      const initialStepIndex = Math.max(
        0,
        questions.findIndex((question) => question.item_id === stored.currentStepId),
      );
      const currentQuestion = questions[initialStepIndex] ?? questions[0];
      const currentTopic = currentQuestion.tags?.[0] || currentQuestion.prompt;

      const data: DeskData = {
        course: {
          name: spaces.find((space) => space.id === spaceId)?.title || "我的课程",
          notebookLabel: `${quiz.title} · ${questions.length} 步`,
        },
        steps: questions.map((question, index) => (
          mapStep(question, index, questions.length, stored.answers[question.item_id] ?? "")
        )),
        initialStepIndex,
        overview: {
          kicker: stored.currentStepId ? "继续上次学习" : "今天的当前练习",
          heading: stored.answers[currentQuestion.item_id]
            ? `从“${currentTopic}”继续`
            : `开始“${currentTopic}”`,
          body: stored.answers[currentQuestion.item_id]
            ? "你的草稿仍在原来的纸页上，可以从这里继续检查。"
            : "先完成当前一步；复习卡片会等到安全节点再出现。",
          resume: [
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
          ],
        },
        bookstand: {
          title: "我的课程本",
          hint: "换课就是换一本本子。",
          books: spaces.map((space) => ({
            id: space.id,
            name: space.title,
            current: space.id === spaceId,
          })),
          newBookLabel: "开新本",
        },
        materials: {
          title: "本课材料",
          hint: learn?.artifacts.length
            ? "选择材料后，可以带着明确来源请小娜协助制作。"
            : "还没有可选材料；先在学习页整理课程资料。",
          items: (learn?.artifacts ?? []).slice(0, 8).map((item) => ({
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
      if (!question || !artifactId) throw new Error("study desk: step is not loaded");
      const result = await repository.submitQuiz(
        spaceId,
        artifactId,
        { [stepId]: decodeResponse(question, answer) },
        signal,
        [stepId],
      );
      if (signal.aborted) throw abortError();
      const grade = result.perQuestion.find((item) => item.item_id === stepId);
      if (!grade) throw new Error("study desk: grader omitted the current step");
      const checkResult = mapCheckResult(grade);
      if (checkResult.verdict === "completed") clearSubmittedAnswer(stepId);
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
      } catch {
        // A bookmark is recovery metadata only; unavailable browser storage
        // must never prevent the canonical Study exercise from opening.
      }
    },
  };
}
