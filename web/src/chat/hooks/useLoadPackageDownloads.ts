// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useState } from "react";
import { activeLoadPackageDownloads } from "../../advanced/settings/loadPackageUi";
import { cmdLoadPackages, type LoadPackageStatus } from "../chat-api";

export function useLoadPackageDownloads(enabled: boolean) {
  const [downloads, setDownloads] = useState<LoadPackageStatus[]>([]);

  const refresh = useCallback(async () => {
    if (!enabled) {
      setDownloads([]);
      return;
    }
    try {
      const response = await cmdLoadPackages();
      setDownloads(activeLoadPackageDownloads(response.packages));
    } catch {
      setDownloads([]);
    }
  }, [enabled]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!enabled || downloads.length === 0) return;
    const timer = window.setInterval(() => {
      void refresh();
    }, 1000);
    return () => window.clearInterval(timer);
  }, [downloads.length, enabled, refresh]);

  return downloads;
}
