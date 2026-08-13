// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { StudyKnowledgePoint } from "../chat/study/study-api";
import type { StudyPageSlug } from "./routeModel";

const STORAGE_PREFIX = "kabuqina.study.location.v1";
export const STUDY_LOCATION_EVENT = "kabuqina-study-location-change";

export type StudyContinuePage = "plan" | "learn" | "practice";
export type StudyContinueActivity = "ready" | "dirty" | "checking" | "needs_revision" | "completed";

export type StudyLocation = {
  version: 1;
  courseId: string;
  page: StudyContinuePage;
  knowledgeCoreId?: string;
  knowledgeCoreTitle?: string;
  outlineLabel?: string;
  outlineNodeId?: string;
  planItemId?: string;
  planItemTitle?: string;
  exerciseId?: string;
  exerciseByCore: Record<string, string>;
  activity?: StudyContinueActivity;
  updatedAt: string;
};

type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

function storage(): StorageLike | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function key(courseId: string): string {
  return `${STORAGE_PREFIX}:${courseId}`;
}

function shortText(value: unknown, max = 500): string | undefined {
  if (typeof value !== "string") return undefined;
  const trimmed = value.trim();
  return trimmed && trimmed.length <= max ? trimmed : undefined;
}

export function parseStudyLocation(value: unknown, courseId: string): StudyLocation | null {
  if (!value || typeof value !== "object") return null;
  const candidate = value as Record<string, unknown>;
  const locationCourseId = shortText(candidate.courseId, 256);
  const knowledgeCoreId = shortText(candidate.knowledgeCoreId, 256);
  const knowledgeCoreTitle = shortText(candidate.knowledgeCoreTitle);
  const updatedAt = shortText(candidate.updatedAt, 64);
  const exerciseByCore = candidate.exerciseByCore;
  const page = candidate.page;
  const hasKnowledgeCore = Boolean(knowledgeCoreId && knowledgeCoreTitle);
  if (
    candidate.version !== 1
    || locationCourseId !== courseId
    || (page !== "plan" && page !== "learn" && page !== "practice")
    || (page !== "plan" && !hasKnowledgeCore)
    || !updatedAt
    || !exerciseByCore
    || typeof exerciseByCore !== "object"
    || Array.isArray(exerciseByCore)
  ) {
    return null;
  }
  const exercises = Object.fromEntries(
    Object.entries(exerciseByCore)
      .map(([coreId, exerciseId]) => [shortText(coreId, 256), shortText(exerciseId, 256)] as const)
      .filter((entry): entry is [string, string] => Boolean(entry[0] && entry[1])),
  );
  return {
    version: 1,
    courseId,
    page,
    ...(knowledgeCoreId ? { knowledgeCoreId } : {}),
    ...(knowledgeCoreTitle ? { knowledgeCoreTitle } : {}),
    ...(shortText(candidate.outlineLabel) ? { outlineLabel: shortText(candidate.outlineLabel) } : {}),
    ...(shortText(candidate.outlineNodeId, 256) ? { outlineNodeId: shortText(candidate.outlineNodeId, 256) } : {}),
    ...(shortText(candidate.planItemId, 256) ? { planItemId: shortText(candidate.planItemId, 256) } : {}),
    ...(shortText(candidate.planItemTitle) ? { planItemTitle: shortText(candidate.planItemTitle) } : {}),
    ...(shortText(candidate.exerciseId, 256) ? { exerciseId: shortText(candidate.exerciseId, 256) } : {}),
    exerciseByCore: exercises,
    ...(candidate.activity === "ready"
      || candidate.activity === "dirty"
      || candidate.activity === "checking"
      || candidate.activity === "needs_revision"
      || candidate.activity === "completed"
      ? { activity: candidate.activity }
      : {}),
    updatedAt,
  };
}

export function readStudyLocation(courseId: string): StudyLocation | null {
  const store = storage();
  if (!store) return null;
  try {
    const raw = store.getItem(key(courseId));
    return raw ? parseStudyLocation(JSON.parse(raw), courseId) : null;
  } catch {
    return null;
  }
}

export function writeStudyLocation(location: StudyLocation): void {
  const store = storage();
  if (!store) return;
  try {
    store.setItem(key(location.courseId), JSON.stringify(location));
    window.dispatchEvent(new CustomEvent(STUDY_LOCATION_EVENT, { detail: location }));
  } catch {
    // The continue bookmark is recovery metadata. A blocked browser store must
    // never prevent canonical Study content from opening.
  }
}

export function selectKnowledgeCore(
  courseId: string,
  point: StudyKnowledgePoint,
  page: StudyContinuePage,
  options: { outlineLabel?: string; outlineNodeId?: string; planItemId?: string; exerciseId?: string } = {},
): StudyLocation {
  const current = readStudyLocation(courseId);
  const sameCore = current?.knowledgeCoreId === point.item_id;
  const exerciseId = options.exerciseId
    ?? current?.exerciseByCore[point.item_id]
    ?? (sameCore ? current?.exerciseId : undefined);
  const outlineLabel = options.outlineLabel ?? current?.outlineLabel;
  const outlineNodeId = options.outlineNodeId ?? current?.outlineNodeId;
  const planItemId = options.planItemId ?? current?.planItemId;
  const next: StudyLocation = {
    version: 1,
    courseId,
    page,
    knowledgeCoreId: point.item_id,
    knowledgeCoreTitle: point.front,
    ...(outlineLabel ? { outlineLabel } : {}),
    ...(outlineNodeId ? { outlineNodeId } : {}),
    ...(planItemId ? { planItemId } : {}),
    ...(exerciseId ? { exerciseId } : {}),
    exerciseByCore: {
      ...(current?.exerciseByCore ?? {}),
      ...(exerciseId ? { [point.item_id]: exerciseId } : {}),
    },
    ...(sameCore && current?.activity ? { activity: current.activity } : { activity: "ready" }),
    updatedAt: new Date().toISOString(),
  };
  if (
    current
    && current.page === next.page
    && current.knowledgeCoreId === next.knowledgeCoreId
    && current.knowledgeCoreTitle === next.knowledgeCoreTitle
    && current.outlineLabel === next.outlineLabel
    && current.outlineNodeId === next.outlineNodeId
    && current.planItemId === next.planItemId
    && current.exerciseId === next.exerciseId
    && current.activity === next.activity
    && JSON.stringify(current.exerciseByCore) === JSON.stringify(next.exerciseByCore)
  ) {
    return current;
  }
  writeStudyLocation(next);
  return next;
}

export function selectPlanItem(
  courseId: string,
  item: {
    itemId: string;
    title: string;
    phaseTitle?: string;
    outlineNodeId?: string;
  },
): StudyLocation {
  const current = readStudyLocation(courseId);
  const next: StudyLocation = {
    version: 1,
    courseId,
    page: "plan",
    planItemId: item.itemId,
    planItemTitle: item.title,
    ...(item.phaseTitle ? { outlineLabel: item.phaseTitle } : {}),
    ...(item.outlineNodeId ? { outlineNodeId: item.outlineNodeId } : {}),
    exerciseByCore: current?.exerciseByCore ?? {},
    updatedAt: new Date().toISOString(),
  };
  if (
    current?.page === next.page
    && current.planItemId === next.planItemId
    && current.planItemTitle === next.planItemTitle
    && current.outlineLabel === next.outlineLabel
    && current.outlineNodeId === next.outlineNodeId
    && JSON.stringify(current.exerciseByCore) === JSON.stringify(next.exerciseByCore)
  ) {
    return current;
  }
  writeStudyLocation(next);
  return next;
}

export function selectOutlineScope(
  courseId: string,
  item: { title: string; outlineNodeId: string },
): StudyLocation {
  const current = readStudyLocation(courseId);
  const next: StudyLocation = {
    version: 1,
    courseId,
    page: "plan",
    outlineLabel: item.title,
    outlineNodeId: item.outlineNodeId,
    exerciseByCore: current?.exerciseByCore ?? {},
    updatedAt: new Date().toISOString(),
  };
  if (
    current?.page === "plan"
    && !current.planItemId
    && current.outlineLabel === next.outlineLabel
    && current.outlineNodeId === next.outlineNodeId
    && JSON.stringify(current.exerciseByCore) === JSON.stringify(next.exerciseByCore)
  ) {
    return current;
  }
  writeStudyLocation(next);
  return next;
}

export function updateStudyExercise(
  courseId: string,
  point: StudyKnowledgePoint,
  exerciseId: string,
): StudyLocation {
  return selectKnowledgeCore(courseId, point, "practice", { exerciseId });
}

export function updateStudyPracticeState(
  courseId: string,
  point: StudyKnowledgePoint,
  exerciseId: string,
  activity: StudyContinueActivity,
): StudyLocation {
  const current = selectKnowledgeCore(courseId, point, "practice", { exerciseId });
  if (current.activity === activity) return current;
  const next: StudyLocation = { ...current, activity, updatedAt: new Date().toISOString() };
  writeStudyLocation(next);
  return next;
}

export function switchStudyMode(courseId: string, page: "learn" | "practice"): StudyLocation | null {
  const current = readStudyLocation(courseId);
  if (!current?.knowledgeCoreId || !current.knowledgeCoreTitle) return null;
  if (current.page === page) return current;
  const next = { ...current, page, updatedAt: new Date().toISOString() };
  writeStudyLocation(next);
  return next;
}

export function resolveKnowledgeCore(
  courseId: string,
  points: StudyKnowledgePoint[],
): { point: StudyKnowledgePoint; index: number; recovered: boolean } | null {
  const current = readStudyLocation(courseId);
  if (!points.length) {
    if (current?.knowledgeCoreId) degradeStudyLocation(courseId);
    return null;
  }
  if (!current || current.page === "plan" || !current.knowledgeCoreId) {
    return { point: points[0], index: 0, recovered: false };
  }
  const index = current
    ? points.findIndex((point) => point.item_id === current.knowledgeCoreId)
    : -1;
  if (index < 0) {
    degradeStudyLocation(courseId);
    return null;
  }
  return { point: points[index], index, recovered: true };
}

export function degradeStudyLocation(courseId: string): StudyLocation | null {
  const current = readStudyLocation(courseId);
  if (!current) return null;
  const next: StudyLocation = {
    version: 1,
    courseId,
    page: "plan",
    ...(current.outlineLabel ? { outlineLabel: current.outlineLabel } : {}),
    ...(current.outlineNodeId ? { outlineNodeId: current.outlineNodeId } : {}),
    ...(current.planItemId ? { planItemId: current.planItemId } : {}),
    ...(current.planItemTitle ? { planItemTitle: current.planItemTitle } : {}),
    exerciseByCore: current.exerciseByCore,
    updatedAt: new Date().toISOString(),
  };
  writeStudyLocation(next);
  return next;
}

export function studyContinueTitle(location: StudyLocation): string {
  if (location.page === "plan") return location.planItemTitle || location.outlineLabel || "当前学习计划";
  const title = location.knowledgeCoreTitle || "当前知识核";
  if (location.page === "learn") return title;
  if (location.activity === "needs_revision") return `${title} · 待修改`;
  if (location.activity === "dirty") return `${title} · 草稿`;
  if (location.activity === "checking") return `${title} · 检查中`;
  return title;
}

export function studyContinueMeta(location: StudyLocation): string {
  const scope = location.outlineLabel ? `${location.outlineLabel} · ` : "";
  if (location.page === "plan") return `${scope}计划`;
  if (location.page === "learn") return `${scope}学习`;
  const activity = location.activity === "needs_revision"
    ? "练习 · 待修改"
    : location.activity === "dirty"
      ? "练习 · 草稿未检查"
      : location.activity === "checking"
        ? "练习 · 检查中"
        : location.activity === "completed"
          ? "练习 · 已完成"
          : "练习";
  return `${scope}${activity}`;
}

export function isStudyContinuePage(page: StudyPageSlug): page is StudyContinuePage {
  return page === "learn" || page === "practice";
}

export function clearStudyLocation(courseId: string): void {
  storage()?.removeItem(key(courseId));
}
