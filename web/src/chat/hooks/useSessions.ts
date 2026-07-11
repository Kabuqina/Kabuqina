// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useRef, useState } from "react";
import { cmdDeleteSession, cmdGetKabuqinaSessions, type SessionRow } from "../chat-api";

export type LoadSessionsOptions = { silent?: boolean };

export function useSessions({ kabuqinaReady }: { kabuqinaReady: boolean }) {
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const hasLoadedRef = useRef(false);

  const loadSessions = useCallback(async (options: LoadSessionsOptions = {}) => {
    const showLoading = !options.silent && !hasLoadedRef.current;
    if (showLoading) {
      setListLoading(true);
    }
    try {
      const r = await cmdGetKabuqinaSessions(50, 0);
      setSessions(r.sessions ?? []);
      hasLoadedRef.current = true;
    } catch (e) {
      console.error(e);
      setSessions([]);
    } finally {
      if (showLoading) {
        setListLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    if (!kabuqinaReady) {
      return;
    }
    void loadSessions();
  }, [kabuqinaReady, loadSessions]);

  const deleteSession = useCallback(async (id: string) => {
    try {
      await cmdDeleteSession(id);
    } catch (err) {
      console.error(err);
      throw err;
    }
  }, []);

  return { sessions, listLoading, loadSessions, deleteSession } as const;
}
