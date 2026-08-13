// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { invoke } from "@tauri-apps/api/core";

export type GlobalActivityStatus =
  | "running"
  | "waiting"
  | "interrupted"
  | "failed"
  | "completed"
  | "recoverable";

export type KnowledgeCoreActivitySourceStatus =
  | "queued"
  | "reading"
  | "generating"
  | "validating"
  | "draft_ready"
  | "needs_source"
  | "failed"
  | "cancelled";

export type GlobalActivityRecord = {
  id: string;
  // Studio 已从产品砍掉，但后端跨域投影契约仍作为休眠资产保留，可能返回
  // domain==="studio" 的旧记录。类型如实反映后端会投什么；产品面只显示 study
  // （ActivityPanel 过滤），不在此处收窄类型，否则运行时数据会与类型不符。
  domain: "study" | "studio";
  kind: string;
  status: GlobalActivityStatus;
  title: string;
  scopeTitle?: string;
  updatedAt: string;
  returnTarget: string;
  fallbackTarget: string;
  canResume: boolean;
  canRetry: boolean;
  targetAvailable: boolean;
  revision?: number;
  sourceStatus?: KnowledgeCoreActivitySourceStatus;
  compilationRunId?: string;
  outlineNodeId?: string;
  planItemId?: string | null;
  draftArtifactId?: string | null;
  reasonCode?: string | null;
};

export type GlobalActivityResponse = {
  items: GlobalActivityRecord[];
  count: number;
  limit: number;
};

export function cmdActivityRecords(
  statuses?: GlobalActivityStatus[],
  limit = 100,
): Promise<GlobalActivityResponse> {
  return invoke("cmd_activity_records", { statuses, limit });
}
