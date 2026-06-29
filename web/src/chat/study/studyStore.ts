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
};

const EMPTY_STUDY_CONTEXT: StudyContext = {
  course: "",
  goal: "",
  profileSummary: "",
  weakPoints: "",
  preferences: "",
  progressNotes: "",
  assessmentEvidence: "",
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
  };
}

function storageAvailable(): Storage | null {
  if (typeof window === "undefined" || !window.localStorage) return null;
  return window.localStorage;
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

export function saveStudyContext(context: StudyContext): StudyContext {
  const normalized = normalizeStudyContext(context);
  const storage = storageAvailable();
  if (storage) {
    try {
      storage.setItem(STUDY_CONTEXT_STORAGE_KEY, JSON.stringify(normalized));
    } catch {
      // localStorage may be unavailable or full in restricted webviews.
    }
  }
  emitStudyContextChanged();
  return normalized;
}

export function clearStudyContext(): StudyContext {
  const storage = storageAvailable();
  if (storage) {
    try {
      storage.removeItem(STUDY_CONTEXT_STORAGE_KEY);
    } catch {
      // ignore
    }
  }
  emitStudyContextChanged();
  return emptyStudyContext();
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
  ].filter(([, value]) => value);

  return [
    "以下是已保存的学习上下文，请优先使用；缺失或不确定的信息仍需追问，不要编造。",
    ...rows.map(([label, value]) => `- ${label}：${value}`),
  ].join("\n");
}
