// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

const PENDING_KEY = "kabuqina.chat.study-handoff.pending.v1";
const SESSION_PREFIX = "kabuqina.chat.study-handoff.session.v1:";
const CONTEXT_SESSION_PREFIX = "kabuqina.chat.study-handoff.context-session.v1:";

export type StudyChatIntent = "explain" | "create";

export type StudyChatHandoff = {
  version: 1;
  mode: "study";
  sessionId: string;
  spaceId: string;
  spaceTitle: string;
  focusKind: "quiz_step" | "course";
  focusId: string;
  focusLabel: string;
  intent: StudyChatIntent;
  originSurface: "study_desk";
  returnTarget: {
    path: string;
    fallbackPath: string;
    focus: "answer" | "notebook";
  };
  revision: number;
  question: string;
  prompt: string;
  answer?: string;
  feedback?: string;
  deskSnapshot?: {
    activity: "ready" | "dirty" | "needs_revision" | "completed";
    answer: string;
    checkResult?: {
      verdict: "needs_revision" | "completed";
      goodLabel: string;
      good: string;
      gap: string;
      next: string;
    };
  };
  selectedSources?: Array<{ id: string; title: string; kind: string }>;
  createdAt: string;
};

export type StudyReturnState = {
  version: 1;
  stepId: string;
  focus: "answer" | "notebook";
  deskSnapshot?: StudyChatHandoff["deskSnapshot"];
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

function text(value: unknown, max: number, allowEmpty = false): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if ((!trimmed && !allowEmpty) || trimmed.length > max) return null;
  return trimmed;
}

function validStudyPath(value: unknown): value is string {
  return typeof value === "string"
    && value.length <= 512
    && /^\/study\/[^/?#]+(?:\/(?:flyleaf|plan|learn|practice|evaluate))?\/?(?:[?#].*)?$/.test(value);
}

function validSource(value: unknown): value is { id: string; title: string; kind: string } {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return Boolean(
    text(candidate.id, 256)
    && text(candidate.title, 256)
    && text(candidate.kind, 64),
  );
}

function parseDeskSnapshot(value: unknown): StudyChatHandoff["deskSnapshot"] | null {
  if (value === undefined) return undefined;
  if (!value || typeof value !== "object") return null;
  const candidate = value as Record<string, unknown>;
  if (
    candidate.activity !== "ready"
    && candidate.activity !== "dirty"
    && candidate.activity !== "needs_revision"
    && candidate.activity !== "completed"
  ) {
    return null;
  }
  const answer = text(candidate.answer, 12000, true);
  if (answer === null) return null;
  if (candidate.checkResult === undefined) return { activity: candidate.activity, answer };
  if (!candidate.checkResult || typeof candidate.checkResult !== "object") return null;
  const result = candidate.checkResult as Record<string, unknown>;
  if (result.verdict !== "needs_revision" && result.verdict !== "completed") return null;
  const goodLabel = text(result.goodLabel, 256, true);
  const good = text(result.good, 8000, true);
  const gap = text(result.gap, 8000, true);
  const next = text(result.next, 8000, true);
  if (goodLabel === null || good === null || gap === null || next === null) return null;
  return {
    activity: candidate.activity,
    answer,
    checkResult: { verdict: result.verdict, goodLabel, good, gap, next },
  };
}

export function parseStudyChatHandoff(value: unknown): StudyChatHandoff | null {
  if (!value || typeof value !== "object") return null;
  const candidate = value as Record<string, unknown>;
  const target = candidate.returnTarget;
  if (!target || typeof target !== "object") return null;
  const returnTarget = target as Record<string, unknown>;
  const selectedSources = candidate.selectedSources;
  const deskSnapshot = parseDeskSnapshot(candidate.deskSnapshot);
  if (
    candidate.version !== 1
    || candidate.mode !== "study"
    || candidate.originSurface !== "study_desk"
    || (candidate.focusKind !== "quiz_step" && candidate.focusKind !== "course")
    || (candidate.intent !== "explain" && candidate.intent !== "create")
    || (returnTarget.focus !== "answer" && returnTarget.focus !== "notebook")
    || !validStudyPath(returnTarget.path)
    || !validStudyPath(returnTarget.fallbackPath)
    || !Number.isInteger(candidate.revision)
    || (candidate.revision as number) < 1
    || (selectedSources !== undefined
      && (!Array.isArray(selectedSources)
        || selectedSources.length > 20
        || !selectedSources.every(validSource)))
    || deskSnapshot === null
  ) {
    return null;
  }
  const sessionId = text(candidate.sessionId, 256);
  const spaceId = text(candidate.spaceId, 256);
  const spaceTitle = text(candidate.spaceTitle, 256);
  const focusId = text(candidate.focusId, 256);
  const focusLabel = text(candidate.focusLabel, 256);
  const question = text(candidate.question, 4000);
  const prompt = text(candidate.prompt, 12000);
  const createdAt = text(candidate.createdAt, 64);
  const answer = candidate.answer === undefined ? undefined : text(candidate.answer, 12000, true);
  const feedback = candidate.feedback === undefined ? undefined : text(candidate.feedback, 8000, true);
  if (
    !sessionId
    || !spaceId
    || !spaceTitle
    || !focusId
    || !focusLabel
    || !question
    || !prompt
    || !createdAt
    || answer === null
    || feedback === null
  ) {
    return null;
  }
  return {
    version: 1,
    mode: "study",
    sessionId,
    spaceId,
    spaceTitle,
    focusKind: candidate.focusKind,
    focusId,
    focusLabel,
    intent: candidate.intent,
    originSurface: "study_desk",
    returnTarget: {
      path: returnTarget.path,
      fallbackPath: returnTarget.fallbackPath,
      focus: returnTarget.focus,
    },
    revision: candidate.revision as number,
    question,
    prompt,
    ...(answer !== undefined ? { answer } : {}),
    ...(feedback !== undefined ? { feedback } : {}),
    ...(deskSnapshot !== undefined ? { deskSnapshot } : {}),
    ...(Array.isArray(selectedSources)
      ? { selectedSources: selectedSources.map((source) => ({ ...source })) }
      : {}),
    createdAt,
  };
}

function read(key: string): StudyChatHandoff | null {
  const store = storage();
  if (!store) return null;
  try {
    const raw = store.getItem(key);
    return raw ? parseStudyChatHandoff(JSON.parse(raw)) : null;
  } catch {
    return null;
  }
}

function write(key: string, handoff: StudyChatHandoff): void {
  const store = storage();
  if (!store) return;
  try {
    store.setItem(key, JSON.stringify(handoff));
  } catch {
    // Recovery metadata must not make Chat unusable.
  }
}

export function persistPendingStudyHandoff(handoff: StudyChatHandoff): void {
  write(PENDING_KEY, handoff);
}

export function readPendingStudyHandoff(): StudyChatHandoff | null {
  return read(PENDING_KEY);
}

export function clearPendingStudyHandoff(): void {
  storage()?.removeItem(PENDING_KEY);
}

export function bindStudyHandoff(handoff: StudyChatHandoff): void {
  write(`${SESSION_PREFIX}${handoff.sessionId}`, handoff);
}

export function readSessionStudyHandoff(sessionId: string): StudyChatHandoff | null {
  const id = text(sessionId, 256);
  return id ? read(`${SESSION_PREFIX}${id}`) : null;
}

export function clearSessionStudyHandoff(sessionId: string): void {
  const id = text(sessionId, 256);
  if (id) storage()?.removeItem(`${SESSION_PREFIX}${id}`);
}

function randomSessionId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `study-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function resolveStudyChatSessionId(spaceId: string, focusId: string): string {
  const contextKey = `${spaceId}:${focusId}`;
  const store = storage();
  if (!store) return randomSessionId();
  const key = `${CONTEXT_SESSION_PREFIX}${contextKey}`;
  try {
    const existing = text(store.getItem(key), 256);
    if (existing) return existing;
    const created = randomSessionId();
    store.setItem(key, created);
    return created;
  } catch {
    return randomSessionId();
  }
}

export function getStudyChatHandoffFromLocation(value: unknown): StudyChatHandoff | null {
  if (!value || typeof value !== "object") return null;
  return parseStudyChatHandoff((value as { studyHandoff?: unknown }).studyHandoff);
}

export function getStudyReturnState(value: unknown): StudyReturnState | null {
  if (!value || typeof value !== "object") return null;
  const state = (value as { studyReturn?: unknown }).studyReturn;
  if (!state || typeof state !== "object") return null;
  const candidate = state as Record<string, unknown>;
  const stepId = text(candidate.stepId, 256);
  const deskSnapshot = parseDeskSnapshot(candidate.deskSnapshot);
  if (
    candidate.version !== 1
    || !stepId
    || deskSnapshot === null
    || (candidate.focus !== "answer" && candidate.focus !== "notebook")
  ) {
    return null;
  }
  return {
    version: 1,
    stepId,
    focus: candidate.focus,
    ...(deskSnapshot !== undefined ? { deskSnapshot } : {}),
  };
}

export function buildStudyChatPrompt(handoff: StudyChatHandoff): string {
  const lines = [
    "【当前学习上下文】",
    `课程：${handoff.spaceTitle}`,
    `位置：${handoff.focusLabel}`,
    `当前题目：${handoff.prompt}`,
  ];
  if (handoff.answer?.trim()) lines.push(`我的当前答案：${handoff.answer.trim()}`);
  if (handoff.feedback?.trim()) lines.push(`检查反馈：${handoff.feedback.trim()}`);
  if (handoff.selectedSources?.length) {
    lines.push(`我明确选择的材料：${handoff.selectedSources.map((source) => source.title).join("、")}`);
  }
  lines.push(`我的问题：${handoff.question}`);
  lines.push(
    handoff.intent === "explain"
      ? "请先给我一个可以自己继续尝试的提示，不要直接替我改写答案；需要完整解释时由我决定。"
      : "请先把制作目标、所选材料和输出要求整理成一份可审核请求，在我确认前不要开始生成。",
  );
  return lines.join("\n");
}
