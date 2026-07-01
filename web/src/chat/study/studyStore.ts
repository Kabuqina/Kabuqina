// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

export const STUDY_CONTEXT_STORAGE_KEY = "kabuqina.study.context.v1";
export const STUDY_CONTEXT_EVENT = "kabuqina-study-context";
export const STUDY_CONTEXT_FIELD_LIMIT = 800;

export type StudyContext = {
  course: string;
  goal: string;
  profileSummary: string;
  weakPoints: string;
  preferences: string;
  progressNotes: string;
  assessmentEvidence: string;
  currentStage: string;
  generatedResources: string;
  tutoringNotes: string;
  evaluationSummary: string;
  nextAdjustment: string;
};

export type StudyContextStorageResult = {
  context: StudyContext;
  succeeded: boolean;
};

const EMPTY_STUDY_CONTEXT: StudyContext = {
  course: "",
  goal: "",
  profileSummary: "",
  weakPoints: "",
  preferences: "",
  progressNotes: "",
  assessmentEvidence: "",
  currentStage: "",
  generatedResources: "",
  tutoringNotes: "",
  evaluationSummary: "",
  nextAdjustment: "",
};

export function emptyStudyContext(): StudyContext {
  return { ...EMPTY_STUDY_CONTEXT };
}

function cleanField(value: unknown): string {
  if (typeof value !== "string") return "";
  return value.trim().slice(0, STUDY_CONTEXT_FIELD_LIMIT);
}

export function normalizeStudyContext(value: unknown): StudyContext {
  if (!value || typeof value !== "object") return emptyStudyContext();
  const raw = value as Partial<Record<keyof StudyContext, unknown>>;
  return {
    course: cleanField(raw.course),
    goal: cleanField(raw.goal),
    profileSummary: cleanField(raw.profileSummary),
    weakPoints: cleanField(raw.weakPoints),
    preferences: cleanField(raw.preferences),
    progressNotes: cleanField(raw.progressNotes),
    assessmentEvidence: cleanField(raw.assessmentEvidence),
    currentStage: cleanField(raw.currentStage),
    generatedResources: cleanField(raw.generatedResources),
    tutoringNotes: cleanField(raw.tutoringNotes),
    evaluationSummary: cleanField(raw.evaluationSummary),
    nextAdjustment: cleanField(raw.nextAdjustment),
  };
}

function storageAvailable(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage ?? null;
  } catch {
    return null;
  }
}

export function loadStudyContext(): StudyContext {
  const storage = storageAvailable();
  if (!storage) return emptyStudyContext();
  try {
    const raw = storage.getItem(STUDY_CONTEXT_STORAGE_KEY);
    return raw ? normalizeStudyContext(JSON.parse(raw)) : emptyStudyContext();
  } catch {
    return emptyStudyContext();
  }
}

function emitStudyContextChanged() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(STUDY_CONTEXT_EVENT));
}

export function saveStudyContext(context: StudyContext): StudyContextStorageResult {
  const normalized = normalizeStudyContext(context);
  const storage = storageAvailable();
  if (!storage) return { context: normalized, succeeded: false };
  try {
    storage.setItem(STUDY_CONTEXT_STORAGE_KEY, JSON.stringify(normalized));
  } catch {
    return { context: normalized, succeeded: false };
  }
  emitStudyContextChanged();
  return { context: normalized, succeeded: true };
}

export function clearStudyContext(): StudyContextStorageResult {
  const empty = emptyStudyContext();
  const storage = storageAvailable();
  if (!storage) return { context: empty, succeeded: false };
  try {
    storage.removeItem(STUDY_CONTEXT_STORAGE_KEY);
  } catch {
    return { context: empty, succeeded: false };
  }
  emitStudyContextChanged();
  return { context: empty, succeeded: true };
}

export function hasStudyContext(context: StudyContext): boolean {
  return Object.values(context).some((value) => value.trim().length > 0);
}

export function formatStudyContextForPrompt(context: StudyContext): string {
  const normalized = normalizeStudyContext(context);
  if (!hasStudyContext(normalized)) return "";
  const rows = [
    ["课程/专业方向", normalized.course],
    ["学习目标", normalized.goal],
    ["学习画像摘要", normalized.profileSummary],
    ["知识短板/易错点", normalized.weakPoints],
    ["学习偏好/可投入时间", normalized.preferences],
    ["学习进度/行为记录", normalized.progressNotes],
    ["练习结果/资源反馈", normalized.assessmentEvidence],
    ["当前学习阶段", normalized.currentStage],
    ["已生成/已使用资源", normalized.generatedResources],
    ["辅导记录/待解决问题", normalized.tutoringNotes],
    ["最近评估结论", normalized.evaluationSummary],
    ["下一轮调整建议", normalized.nextAdjustment],
  ].filter(([, value]) => value);

  return [
    "以下是已保存的学习闭环上下文，请优先使用；缺失或不确定的信息仍需追问，不要编造。",
    ...rows.map(([label, value]) => `- ${label}：${value}`),
  ].join("\n");
}
