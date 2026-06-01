// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { invoke } from "@tauri-apps/api/core";

export interface DesktopOrganizeRunResult {
  movedCount: number;
  skippedCount: number;
  arrangedIcons: boolean;
  undoAvailable: boolean;
  skippedReasons: string[];
  message: string;
}

export function runDesktopOrganize(locale: string): Promise<DesktopOrganizeRunResult> {
  return invoke("cmd_desktop_organize_run", { locale });
}
