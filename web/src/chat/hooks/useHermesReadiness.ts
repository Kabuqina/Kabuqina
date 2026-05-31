import { useEffect, useState } from "react";
import {
  getCachedHermesReadiness,
  updateHermesReadinessCacheFromSnapshot,
} from "../hermesReadinessCache";
import { waitForHermesReadiness } from "../hermesReadinessPoll";
import { useI18n } from "../../lib/i18n";

export function useHermesReadiness() {
  const { t } = useI18n();
  const cached = getCachedHermesReadiness();
  const [hermesReady, setHermesReady] = useState(cached.hermesReady);
  const [hermesWarming, setHermesWarming] = useState(cached.hermesWarming);
  const [bootErr, setBootErr] = useState<string | null>(cached.bootErr);

  useEffect(() => {
    let cancel = false;
    const bootT0 = import.meta.env.DEV ? performance.now() : 0;
    void (async () => {
      const snap = await waitForHermesReadiness(t, () => cancel);
      if (cancel) {
        return;
      }
      const cachedSnap = updateHermesReadinessCacheFromSnapshot(snap);
      setHermesReady(cachedSnap.hermesReady);
      setHermesWarming(cachedSnap.hermesWarming);
      setBootErr(cachedSnap.bootErr);
      if (import.meta.env.DEV && bootT0 > 0 && snap.hermesReady && !snap.hermesWarming) {
        console.info(`[kabuqina] hermes_ready_ms=${Math.round(performance.now() - bootT0)}`);
      }
    })();
    return () => {
      cancel = true;
    };
  }, [t]);

  return { hermesReady, hermesWarming, bootErr } as const;
}
