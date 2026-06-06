// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { cmdGetHermesBootstrapError, cmdGetHermesDeskBootState } from "./chat-api";
import {
  type HermesReadinessSnapshot,
  updateHermesReadinessCache,
} from "./hermesReadinessCache";

function formatBootError(detail: string, t: (key: string) => string): string {
  return `${t("chat.errHermesBootFailed")}\n\n${detail}`;
}

export function isHermesUsable(snapshot: HermesReadinessSnapshot): boolean {
  return snapshot.hermesReady && !snapshot.hermesWarming && !snapshot.bootErr;
}

/** Poll until Hermes is ready, warming finishes, or boot fails / times out. */
export async function waitForHermesReadiness(
  t: (key: string) => string,
  isCancelled: () => boolean = () => false,
): Promise<HermesReadinessSnapshot> {
  for (let i = 0; i < 120; i++) {
    if (isCancelled()) {
      return updateHermesReadinessCache(null, null);
    }
    try {
      const bootFail = await cmdGetHermesBootstrapError();
      if (bootFail) {
        return updateHermesReadinessCache(null, formatBootError(bootFail, t));
      }
      const state = await cmdGetHermesDeskBootState();
      if (state.port != null) {
        const snap = updateHermesReadinessCache(state, null);
        if (!state.warming) {
          return snap;
        }
        if (isCancelled()) {
          return snap;
        }
      } else {
        updateHermesReadinessCache(state, null);
      }
    } catch {
      /* keep polling */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  const bootFail = await cmdGetHermesBootstrapError().catch(() => null);
  const err = bootFail ? formatBootError(bootFail, t) : t("chat.errHermesTimeout");
  return updateHermesReadinessCache(null, err);
}
