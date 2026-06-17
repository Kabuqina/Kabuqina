// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useRef, useState } from "react";
import { cmdLoadPackages, type LoadPackageStatus } from "../chat-api";

const LOAD_PACKAGE_ACTIVE_POLL_MS = 1000;
const LOAD_PACKAGE_IDLE_POLL_MS = 4000;
const LOAD_PACKAGE_FINISHED_VISIBLE_MS = 5000;

export function useLoadPackageDownloads(enabled: boolean) {
  const [downloads, setDownloads] = useState<LoadPackageStatus[]>([]);
  const knownDownloadIdsRef = useRef<Set<string>>(new Set());
  const finishedUntilRef = useRef<Map<string, number>>(new Map());

  const refresh = useCallback(async () => {
    if (!enabled) {
      setDownloads([]);
      knownDownloadIdsRef.current.clear();
      finishedUntilRef.current.clear();
      return;
    }
    try {
      const response = await cmdLoadPackages();
      const now = Date.now();
      const visible: LoadPackageStatus[] = [];
      for (const pkg of response.packages) {
        const status = pkg.job?.status;
        if (status === "running") {
          knownDownloadIdsRef.current.add(pkg.id);
          finishedUntilRef.current.delete(pkg.id);
          visible.push(pkg);
          continue;
        }

        if (status !== "done" && status !== "error") {
          finishedUntilRef.current.delete(pkg.id);
          knownDownloadIdsRef.current.delete(pkg.id);
          continue;
        }

        if (!knownDownloadIdsRef.current.has(pkg.id) && !finishedUntilRef.current.has(pkg.id)) {
          continue;
        }
        if (!finishedUntilRef.current.has(pkg.id)) {
          finishedUntilRef.current.set(pkg.id, now + LOAD_PACKAGE_FINISHED_VISIBLE_MS);
        }
        const keepUntil = finishedUntilRef.current.get(pkg.id) ?? 0;
        if (now <= keepUntil) {
          visible.push(pkg);
        } else {
          finishedUntilRef.current.delete(pkg.id);
          knownDownloadIdsRef.current.delete(pkg.id);
        }
      }
      setDownloads(visible);
    } catch {
      setDownloads([]);
    }
  }, [enabled]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!enabled) return;
    const hasRunningDownload = downloads.some((pkg) => pkg.job?.status === "running");
    const timer = window.setInterval(() => {
      void refresh();
    }, hasRunningDownload ? LOAD_PACKAGE_ACTIVE_POLL_MS : LOAD_PACKAGE_IDLE_POLL_MS);
    return () => window.clearInterval(timer);
  }, [downloads, enabled, refresh]);

  return downloads;
}
