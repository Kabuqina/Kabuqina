// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { check, type Update } from "@tauri-apps/plugin-updater";
import { relaunch } from "@tauri-apps/plugin-process";

export type AppUpdate = Update;

export type UpdateDownloadProgress = {
  downloaded: number;
  total: number | null;
};

export async function checkForAppUpdate(): Promise<AppUpdate | null> {
  return check();
}

export async function installAppUpdate(
  update: AppUpdate,
  onProgress?: (progress: UpdateDownloadProgress) => void,
): Promise<void> {
  let downloaded = 0;
  let total: number | null = null;
  await update.downloadAndInstall((event) => {
    if (event.event === "Started") {
      total = event.data.contentLength ?? null;
      downloaded = 0;
    } else if (event.event === "Progress") {
      downloaded += event.data.chunkLength;
    }
    onProgress?.({ downloaded, total });
  });
}

export async function relaunchApp(): Promise<void> {
  await relaunch();
}

export function formatUpdateProgress(progress: UpdateDownloadProgress | null): string {
  if (!progress) return "";
  if (progress.total && progress.total > 0) {
    const pct = Math.min(100, Math.round((progress.downloaded / progress.total) * 100));
    return `${pct}%`;
  }
  if (progress.downloaded > 0) {
    const mb = progress.downloaded / (1024 * 1024);
    return `${mb.toFixed(1)} MB`;
  }
  return "";
}
