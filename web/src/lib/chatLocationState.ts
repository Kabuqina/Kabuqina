// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { StudyChatHandoff } from "./studyChatHandoff";

/**
 * When navigating to `/chat` right after the setup wizard completed saving the key,
 * pass this state so `ChatPage` can skip the immediate `cmd_has_secret` gate (avoids
 * a race with keyring or bridge timing) and then strip the state for normal behavior.
 */
export const CHAT_FROM_ONBOARDING_STATE: { fromOnboarding: true } = { fromOnboarding: true };

/**
 * Survives React Strict Mode remounts (component refs do not). When the wizard lands on `/chat`
 * with {@link CHAT_FROM_ONBOARDING_STATE}, we strip location state then skip `cmd_has_secret` once
 * on the next effect pass — this pair replaces the old ref-based skip that could reset mid-flow.
 */
let pendingChatSecretGateBypass = false;

export function armPendingChatSecretGateBypass(): void {
  pendingChatSecretGateBypass = true;
}

export function takePendingChatSecretGateBypass(): boolean {
  if (!pendingChatSecretGateBypass) return false;
  pendingChatSecretGateBypass = false;
  return true;
}

let pendingOpenReminderSession = false;

/** Survives location state strip + Hermes readiness wait (toast → chat). */
export function armPendingOpenReminderSession(): void {
  pendingOpenReminderSession = true;
}

export function takePendingOpenReminderSession(): boolean {
  if (!pendingOpenReminderSession) return false;
  pendingOpenReminderSession = false;
  return true;
}

export type ChatLocationState = {
  fromOnboarding?: boolean;
  draftPrompt?: string;
  openReminderSession?: boolean;
  studyHandoff?: StudyChatHandoff;
  openSessionId?: string;
};

export function isOpenReminderSession(state: unknown): boolean {
  return (
    typeof state === "object" &&
    state !== null &&
    (state as ChatLocationState).openReminderSession === true
  );
}

export const CHAT_OPEN_REMINDER_SESSION_STATE: { openReminderSession: true } = {
  openReminderSession: true,
};

export function isFromOnboarding(state: unknown): state is { fromOnboarding: true } {
  return typeof state === "object" && state !== null && (state as ChatLocationState).fromOnboarding === true;
}

export function getDraftPrompt(state: unknown): string | null {
  if (typeof state !== "object" || state === null) return null;
  const draft = (state as ChatLocationState).draftPrompt;
  return typeof draft === "string" && draft.trim() ? draft : null;
}

export function getOpenSessionId(state: unknown): string | null {
  if (typeof state !== "object" || state === null) return null;
  const sessionId = (state as ChatLocationState).openSessionId;
  return typeof sessionId === "string" && sessionId.trim() && sessionId.length <= 256
    ? sessionId.trim()
    : null;
}
