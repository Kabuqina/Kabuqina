// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { StudyFlashcard } from "../../chat/study/study-api";
import type { CheckResult, DeskActivityRecord, DeskData } from "./types";

/**
 * Seam between the desk UI and its data source. Production supplies the Study
 * repository adapter; development fixtures live behind the DEV-only preview
 * entry so they cannot leak into the production Study chunk.
 */
export interface DeskAdapter {
  loadDesk(signal: AbortSignal): Promise<DeskData>;
  /** Persist browser recovery state synchronously before a refresh can unload the page. */
  persistDraft?(stepId: string, answer: string): void;
  saveDraft(stepId: string, answer: string, signal: AbortSignal): Promise<void>;
  checkAnswer(stepId: string, answer: string, signal: AbortSignal): Promise<CheckResult>;
  reviewCard?(
    itemId: string,
    grade: "again" | "hard" | "good" | "easy",
    signal: AbortSignal,
  ): Promise<StudyFlashcard>;
  loadActivities?(signal: AbortSignal): Promise<DeskActivityRecord[]>;
  markCurrentStep?(stepId: string): void;
}
