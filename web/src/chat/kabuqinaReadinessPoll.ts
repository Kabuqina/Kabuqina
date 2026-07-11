// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { cmdGetKabuqinaBootstrapError, cmdGetKabuqinaBootState } from "./chat-api";
import {
  type KabuqinaReadinessSnapshot,
  updateKabuqinaReadinessCache,
} from "./kabuqinaReadinessCache";

function formatBootError(detail: string, t: (key: string) => string): string {
  return `${t("chat.errHermesBootFailed")}\n\n${detail}`;
}

export function isKabuqinaUsable(snapshot: KabuqinaReadinessSnapshot): boolean {
  return snapshot.kabuqinaReady && !snapshot.kabuqinaWarming && !snapshot.bootErr;
}

/** Poll until Hermes is ready, warming finishes, or boot fails / times out. */
export async function waitForKabuqinaReadiness(
  t: (key: string) => string,
  isCancelled: () => boolean = () => false,
): Promise<KabuqinaReadinessSnapshot> {
  for (let i = 0; i < 120; i++) {
    if (isCancelled()) {
      return updateKabuqinaReadinessCache(null, null);
    }
    try {
      const bootFail = await cmdGetKabuqinaBootstrapError();
      if (bootFail) {
        return updateKabuqinaReadinessCache(null, formatBootError(bootFail, t));
      }
      const state = await cmdGetKabuqinaBootState();
      if (state.port != null) {
        const snap = updateKabuqinaReadinessCache(state, null);
        if (!state.warming) {
          return snap;
        }
        if (isCancelled()) {
          return snap;
        }
      } else {
        updateKabuqinaReadinessCache(state, null);
      }
    } catch {
      /* keep polling */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  const bootFail = await cmdGetKabuqinaBootstrapError().catch(() => null);
  const err = bootFail ? formatBootError(bootFail, t) : t("chat.errHermesTimeout");
  return updateKabuqinaReadinessCache(null, err);
}
