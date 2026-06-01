// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { HermesDeskBootState } from "./chat-api";

export type HermesReadinessSnapshot = {
  hermesReady: boolean;
  hermesWarming: boolean;
  bootErr: string | null;
};

let cachedBootState: HermesDeskBootState | null = null;
let cachedBootErr: string | null = null;

export function snapshotFromBootState(
  state: HermesDeskBootState,
  bootErr: string | null = null,
): HermesReadinessSnapshot {
  if (bootErr) {
    return { hermesReady: false, hermesWarming: false, bootErr };
  }
  if (state.port == null) {
    return { hermesReady: false, hermesWarming: false, bootErr: null };
  }
  return {
    hermesReady: true,
    hermesWarming: state.warming,
    bootErr: null,
  };
}

/** Last known boot state survives ChatPage unmount (route changes). */
export function getCachedHermesReadiness(): HermesReadinessSnapshot {
  if (cachedBootErr) {
    return { hermesReady: false, hermesWarming: false, bootErr: cachedBootErr };
  }
  if (!cachedBootState) {
    return { hermesReady: false, hermesWarming: false, bootErr: null };
  }
  return snapshotFromBootState(cachedBootState);
}

export function updateHermesReadinessCache(
  state: HermesDeskBootState | null,
  bootErr: string | null,
): HermesReadinessSnapshot {
  cachedBootErr = bootErr;
  cachedBootState = state;
  if (bootErr) {
    return { hermesReady: false, hermesWarming: false, bootErr };
  }
  if (!state || state.port == null) {
    return { hermesReady: false, hermesWarming: false, bootErr: null };
  }
  return snapshotFromBootState(state);
}
