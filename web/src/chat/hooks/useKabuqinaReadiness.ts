// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useState } from "react";
import {
  getCachedKabuqinaReadiness,
  updateKabuqinaReadinessCacheFromSnapshot,
} from "../kabuqinaReadinessCache";
import { waitForKabuqinaReadiness } from "../kabuqinaReadinessPoll";
import { useI18n } from "../../lib/i18n";

export function useKabuqinaReadiness() {
  const { t } = useI18n();
  const cached = getCachedKabuqinaReadiness();
  const [kabuqinaReady, setHermesReady] = useState(cached.kabuqinaReady);
  const [kabuqinaWarming, setHermesWarming] = useState(cached.kabuqinaWarming);
  const [bootErr, setBootErr] = useState<string | null>(cached.bootErr);

  useEffect(() => {
    let cancel = false;
    const bootT0 = import.meta.env.DEV ? performance.now() : 0;
    void (async () => {
      const snap = await waitForKabuqinaReadiness(t, () => cancel);
      if (cancel) {
        return;
      }
      const cachedSnap = updateKabuqinaReadinessCacheFromSnapshot(snap);
      setHermesReady(cachedSnap.kabuqinaReady);
      setHermesWarming(cachedSnap.kabuqinaWarming);
      setBootErr(cachedSnap.bootErr);
      if (import.meta.env.DEV && bootT0 > 0 && snap.kabuqinaReady && !snap.kabuqinaWarming) {
        console.info(`[kabuqina] hermes_ready_ms=${Math.round(performance.now() - bootT0)}`);
      }
    })();
    return () => {
      cancel = true;
    };
  }, [t]);

  return { kabuqinaReady, kabuqinaWarming, bootErr } as const;
}
