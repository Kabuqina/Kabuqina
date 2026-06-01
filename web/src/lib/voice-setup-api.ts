// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { invoke } from "@tauri-apps/api/core";

export type VoiceSetupSection = "stt" | "tts";

export interface VoiceSetupResult {
  ok: boolean;
  section: VoiceSetupSection;
  saved_provider: boolean;
  saved_env: string[];
}

/**
 * Persist the wizard's choice for a voice section: writes the picked
 * provider to ``config.yaml`` (`<section>.provider`) and the supplied env
 * pairs to ``hermes-home/.env`` (which also refreshes ``os.environ`` so the
 * running Python process picks up the new key without a restart).
 *
 * - ``provider = null`` leaves the existing setting untouched (used when the
 *   user picks "skip" or hasn't selected anything).
 * - Empty values in ``env`` are dropped on the Python side so blanks never
 *   overwrite a previously-saved key. Keys outside an internal allow-list
 *   are silently dropped.
 */
export async function cmdSaveVoiceSetup(
  section: VoiceSetupSection,
  provider: string | null,
  env: Record<string, string>
): Promise<VoiceSetupResult> {
  return invoke<VoiceSetupResult>("cmd_save_voice_setup", {
    section,
    provider,
    env,
  });
}
