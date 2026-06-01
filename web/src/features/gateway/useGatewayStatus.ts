// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

type GatewayPlatform = {
  state: string;
  error_message?: string;
};

type GatewayStatusPayload = {
  running: boolean;
  eligible: boolean;
  embeddedGatewayStartupSurvival: boolean;
  diskGatewayState: string | null;
  diskExitReason: string | null;
  platforms: Record<string, GatewayPlatform> | null;
};

export function useGatewayStatus() {
  const [running, setRunning] = useState(false);
  const [eligible, setEligible] = useState(false);
  const [diskState, setDiskState] = useState<string | null>(null);
  const [diskExit, setDiskExit] = useState<string | null>(null);
  const [embedSurvival, setEmbedSurvival] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [platforms, setPlatforms] = useState<Record<string, GatewayPlatform> | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const cancelledRef = useRef(false);

  const poll = useCallback(async () => {
    try {
      const p = await invoke<GatewayStatusPayload>("cmd_gateway_status");
      setRunning(p.running);
      setEligible(p.eligible);
      setDiskState(p.diskGatewayState);
      setDiskExit(p.diskExitReason);
      setEmbedSurvival(p.embeddedGatewayStartupSurvival);
      setPlatforms(p.platforms ?? null);
    } catch {
      // gateway command not available or not connected
    }
  }, []);

  useEffect(() => {
    poll();
    timerRef.current = setInterval(poll, 3000);
    return () => {
      cancelledRef.current = true;
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [poll]);

  const start = useCallback(async () => {
    setStartError(null);
    setStarting(true);
    try {
      await invoke("cmd_gateway_start");
      await poll();
    } catch (e: unknown) {
      setStartError(typeof e === "string" ? e : "Failed to start gateway");
    } finally {
      setStarting(false);
    }
  }, [poll]);

  const stop = useCallback(async () => {
    setStartError(null);
    setStarting(true);
    try {
      await invoke("cmd_gateway_stop");
      setRunning(false);
      setPlatforms(null);
    } catch {
      // ignore
    } finally {
      setStarting(false);
    }
  }, []);

  return {
    running, eligible, diskState, diskExit, embedSurvival,
    startError, starting, platforms,
    start, stop,
  };
}

export type GatewayStatus = ReturnType<typeof useGatewayStatus>;
