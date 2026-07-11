// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { KabuqinaBootState } from "./chat-api";

export type KabuqinaReadinessSnapshot = {
  kabuqinaReady: boolean;
  kabuqinaWarming: boolean;
  bootErr: string | null;
};

let cachedBootState: KabuqinaBootState | null = null;
let cachedBootErr: string | null = null;

export function snapshotFromBootState(
  state: KabuqinaBootState,
  bootErr: string | null = null,
): KabuqinaReadinessSnapshot {
  if (bootErr) {
    return { kabuqinaReady: false, kabuqinaWarming: false, bootErr };
  }
  if (state.port == null) {
    return { kabuqinaReady: false, kabuqinaWarming: false, bootErr: null };
  }
  return {
    kabuqinaReady: true,
    kabuqinaWarming: state.warming,
    bootErr: null,
  };
}

/** Last known boot state survives ChatPage unmount (route changes). */
export function getCachedKabuqinaReadiness(): KabuqinaReadinessSnapshot {
  if (cachedBootErr) {
    return { kabuqinaReady: false, kabuqinaWarming: false, bootErr: cachedBootErr };
  }
  if (!cachedBootState) {
    return { kabuqinaReady: false, kabuqinaWarming: false, bootErr: null };
  }
  return snapshotFromBootState(cachedBootState);
}

export function updateKabuqinaReadinessCache(
  state: KabuqinaBootState | null,
  bootErr: string | null,
): KabuqinaReadinessSnapshot {
  cachedBootErr = bootErr;
  cachedBootState = state;
  if (bootErr) {
    return { kabuqinaReady: false, kabuqinaWarming: false, bootErr };
  }
  if (!state || state.port == null) {
    return { kabuqinaReady: false, kabuqinaWarming: false, bootErr: null };
  }
  return snapshotFromBootState(state);
}

export function updateKabuqinaReadinessCacheFromSnapshot(
  snapshot: KabuqinaReadinessSnapshot,
): KabuqinaReadinessSnapshot {
  if (snapshot.bootErr) {
    cachedBootErr = snapshot.bootErr;
    cachedBootState = null;
    return snapshot;
  }
  cachedBootErr = null;
  cachedBootState = snapshot.kabuqinaReady
    ? { port: 1, warming: snapshot.kabuqinaWarming }
    : null;
  return snapshot;
}
