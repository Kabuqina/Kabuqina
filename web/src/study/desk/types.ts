// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// Orthogonal state dimensions for the desk scene. Per the frozen prototype's
// scope-ledger, production code MUST model these as independent dimensions and
// MUST NOT copy the prototype's single phase enum.

import type { StudyQuizQuestionType } from "../../chat/study/study-api";
import type { StudyFlashcard } from "../../chat/study/study-api";

/** Spatial density of the desk. `overview` = D0 desk overview; `focused` = N0+ notebook focus. */
export type DeskDensity = "overview" | "focused";

/** Study activity / answer / grader truth for the current step. */
export type StudyActivity = "ready" | "dirty" | "checking" | "needs_revision" | "completed";

export interface DeskCourse {
  /** Notebook cover title, e.g. "高等数学 · 极限". */
  name: string;
  /** Sub-line under the cover title, e.g. "我的课程笔记本 · 最近保存 13:42". */
  notebookLabel: string;
}

export interface StudyStep {
  id: string;
  artifactId?: string;
  answerKind?: StudyQuizQuestionType;
  /** e.g. "练习 3 · 第 2 步". */
  kicker: string;
  title: string;
  /** Completion standard shown above the prompt (without the "完成标准：" prefix). */
  standard: string;
  prompt: string;
  referenceSummary: string;
  referenceHint: string;
  /** Draft restored when the student returns to this step. */
  initialDraft: string;
  options?: string[];
  multiple?: boolean;
  language?: string;
  mode?: string;
  starter?: string;
  targetCode?: string;
  check?: "normalized-match" | "numeric-equivalence";
  derivationSteps?: Array<{ expr?: string; justification?: string; cloze?: boolean }>;
  targetSteps?: Array<{ expr?: string; justification?: string }>;
}

export interface CheckResult {
  verdict: "needs_revision" | "completed";
  /** Strong lead of the good row: "已经说明清楚" or "这一点已经说明清楚". */
  goodLabel: string;
  good: string;
  /** Only rendered for needs_revision. */
  gap: string;
  /** Only rendered for needs_revision. */
  next: string;
}

export interface DeskOverview {
  kicker: string;
  heading: string;
  body: string;
  resume: { icon: "circleCheck" | "circleDot"; text: string }[];
}

export interface DeskBookstand {
  title: string;
  hint: string;
  books: { id: string; name: string; current: boolean }[];
  newBookLabel: string;
}

export interface DeskMaterials {
  title: string;
  hint: string;
  items: Array<{
    id: string;
    title: string;
    kind: string;
    status: string;
  }>;
  unavailable?: boolean;
}

export interface DeskActivityRecord {
  id: string;
  type: string;
  artifactId?: string;
  itemId?: string;
  createdAt: string;
}

export interface DeskData {
  course: DeskCourse;
  steps: StudyStep[];
  initialStepIndex?: number;
  overview: DeskOverview;
  bookstand: DeskBookstand;
  materials: DeskMaterials;
  activities: DeskActivityRecord[];
  activitiesUnavailable?: boolean;
  dueCards: StudyFlashcard[];
  cardsUnavailable?: boolean;
  dueCount: number;
}
