// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { invoke } from "@tauri-apps/api/core";

/**
 * Studio 的客户端契约。
 *
 * **后端尚未实现**（记在
 * `docs/superpowers/handoffs/2026-07-27-v0.5.0-backend-requirements-ledger.md` B-7）。
 * 前端按这份契约写，命令缺席时走 `notImplemented` 分支显示真实的"尚未接通"，
 * **不造假数据**——架构 §0.3 允许"将暂不成熟的能力降为连接验证，而不是伪装成完整中心"，
 * 假数据恰恰是被禁的那一种。
 *
 * 命名跟着领域走：Project 是 Studio 的主容器，Brief 是表达目标，
 * SourceSnapshot 是从 Study 取来的只读快照（架构 §4.2）。
 */

/** 只读来源快照。Studio 引用它，不拥有也不改写 Study 原对象。 */
export type StudioSourceSnapshot = {
  /** 稳定来源 ID */
  id: string;
  kind: "study_activity" | "study_artifact" | "chat_session" | "file";
  title: string;
  /** 来源 Course / page / activity / chat session 的可读定位 */
  origin: string;
  /** 用户当时选中的内容快照 */
  excerpt: string;
  createdAt: string;
  revision: number;
  /** 可回到的原位置；失效时用 fallback */
  returnTarget: string | null;
  fallbackTarget: string | null;
};

export type StudioProject = {
  id: string;
  title: string;
  /** 表达目标：先说清要讲给谁。空串代表还没写。 */
  brief: string;
  /** 当前阶段，供中央工作面显示"下一步"用 */
  stage: "brief" | "gathering" | "shaping" | "review";
  createdAt: string;
  updatedAt: string;
  sources: StudioSourceSnapshot[];
};

export type StudioProjects = { projects: StudioProject[] };

/** 命令未在后端注册时抛这个，让 UI 显示"尚未接通"而不是报错。 */
export class StudioNotImplementedError extends Error {
  constructor(command: string) {
    super(`studio backend command not implemented: ${command}`);
    this.name = "StudioNotImplementedError";
  }
}

function looksNotImplemented(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? "");
  // Tauri 对未注册命令回 "not allowed"/"not found"；纯浏览器下 __TAURI__ 未定义。
  return (
    /not implemented|unknown command|not found|not allowed|undefined/i.test(message) ||
    message.includes("invoke")
  );
}

async function call<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  try {
    return await invoke<T>(command, args);
  } catch (error) {
    if (looksNotImplemented(error)) throw new StudioNotImplementedError(command);
    throw error;
  }
}

export function cmdStudioProjects(): Promise<StudioProjects> {
  return call<StudioProjects>("cmd_studio_projects");
}

export function cmdStudioCreateProject(title: string): Promise<StudioProject> {
  return call<StudioProject>("cmd_studio_create_project", { title });
}

export function cmdStudioSaveBrief(projectId: string, brief: string): Promise<StudioProject> {
  return call<StudioProject>("cmd_studio_save_brief", { projectId, brief });
}
