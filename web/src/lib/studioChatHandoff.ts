// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

/**
 * Studio → Chat 的显式作用域转交。
 *
 * 与 `studyChatHandoff` 同形但**刻意更薄**：Study 的转交要带题目、答案、反馈和
 * 书桌快照，因为它要回到"这一步"；Studio 的作用域就是**项目本身**，回去的地方
 * 只有一个，所以不需要 focus/step 那一层。
 *
 * 不变量（架构 §8）：
 * - Chat 永远显示当前作用域，不猜测隐式 Project（§8.3）——所以作用域只能由这份
 *   显式转交建立，绝不从消息文本或文件名推断；
 * - 全局 Chat 默认自由会话（§8.10）——项目会话只是普通历史，用户主动选中才回到
 *   项目作用域；
 * - Studio 输出不自动修改学习状态（§8.2）——这条链只往 Chat 送，不回写 Study。
 */

const PENDING_KEY = "kabuqina.chat.studio-handoff.pending.v1";
const SESSION_PREFIX = "kabuqina.chat.studio-handoff.session.v1:";

export type StudioChatHandoff = {
  version: 1;
  mode: "studio";
  sessionId: string;
  projectId: string;
  projectTitle: string;
  /** 表达目标。小娜要知道这个项目是讲给谁的，否则只能泛泛地聊。 */
  brief: string;
  /** 已取素材的标题，只作上下文提示；正文不随转交搬运。 */
  sourceTitles: string[];
  returnTarget: { path: string; fallbackPath: string };
  createdAt: string;
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

/** 同一个项目复用同一个会话，避免每次点「问小娜」都新开一条。 */
export function resolveStudioChatSessionId(projectId: string): string {
  return `studio:${projectId}`;
}

export function parseStudioChatHandoff(value: unknown): StudioChatHandoff | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  if (raw.version !== 1 || raw.mode !== "studio") return null;
  const projectId = typeof raw.projectId === "string" ? raw.projectId : "";
  const sessionId = typeof raw.sessionId === "string" ? raw.sessionId : "";
  if (!projectId || !sessionId) return null;
  const target = raw.returnTarget as Record<string, unknown> | undefined;
  return {
    version: 1,
    mode: "studio",
    sessionId,
    projectId,
    projectTitle: typeof raw.projectTitle === "string" ? raw.projectTitle : "",
    brief: typeof raw.brief === "string" ? raw.brief : "",
    sourceTitles: Array.isArray(raw.sourceTitles)
      ? raw.sourceTitles.filter((item): item is string => typeof item === "string")
      : [],
    returnTarget: {
      path: typeof target?.path === "string" ? target.path : "/studio",
      fallbackPath: typeof target?.fallbackPath === "string" ? target.fallbackPath : "/studio",
    },
    createdAt: typeof raw.createdAt === "string" ? raw.createdAt : new Date().toISOString(),
  };
}

export function buildStudioChatHandoff(project: {
  id: string;
  title: string;
  brief: string;
  sources: Array<{ title: string }>;
}): StudioChatHandoff {
  return {
    version: 1,
    mode: "studio",
    sessionId: resolveStudioChatSessionId(project.id),
    projectId: project.id,
    projectTitle: project.title,
    brief: project.brief,
    sourceTitles: project.sources.map((source) => source.title),
    returnTarget: { path: "/studio", fallbackPath: "/studio" },
    createdAt: new Date().toISOString(),
  };
}

export function persistPendingStudioHandoff(handoff: StudioChatHandoff): void {
  storage()?.setItem(PENDING_KEY, JSON.stringify(handoff));
}

export function readPendingStudioHandoff(): StudioChatHandoff | null {
  const raw = storage()?.getItem(PENDING_KEY);
  if (!raw) return null;
  try {
    return parseStudioChatHandoff(JSON.parse(raw));
  } catch {
    return null;
  }
}

export function clearPendingStudioHandoff(): void {
  storage()?.removeItem(PENDING_KEY);
}

export function bindStudioHandoff(handoff: StudioChatHandoff): void {
  storage()?.setItem(SESSION_PREFIX + handoff.sessionId, JSON.stringify(handoff));
}

export function readSessionStudioHandoff(sessionId: string): StudioChatHandoff | null {
  const raw = storage()?.getItem(SESSION_PREFIX + sessionId);
  if (!raw) return null;
  try {
    return parseStudioChatHandoff(JSON.parse(raw));
  } catch {
    return null;
  }
}

export function clearSessionStudioHandoff(sessionId: string): void {
  storage()?.removeItem(SESSION_PREFIX + sessionId);
}

export function getStudioChatHandoffFromLocation(value: unknown): StudioChatHandoff | null {
  if (!value || typeof value !== "object") return null;
  return parseStudioChatHandoff((value as { studioHandoff?: unknown }).studioHandoff);
}

/**
 * 开场提示。**只描述项目，不替学生表达观点**——小娜是来帮他把话讲清楚的，
 * 不是来替他讲的（见"学习 agent 不能替代学习者"这条产品红线在表达侧的对应）。
 */
export function buildStudioChatPrompt(handoff: StudioChatHandoff): string {
  const lines = [`我在做一个项目：${handoff.projectTitle}`];
  if (handoff.brief) lines.push(`要讲给：${handoff.brief}`);
  if (handoff.sourceTitles.length) {
    lines.push(`已取素材：${handoff.sourceTitles.join("、")}`);
  }
  return lines.join("\n");
}
