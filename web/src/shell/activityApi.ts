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

export type GlobalActivityRecord = {
  id: string;
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
