// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { ProgressEvent } from "../chat-api";

export type AgentProgressState = {
  running: boolean;
  status: string;
  iteration: number;
  max_iterations: number;
  current_tool: string | null;
  error: string | null;
  steps: AgentStep[];
  /** Cursor: last `seq` consumed. The next poll passes this as `since`. */
  nextSeq: number;
};

export type AgentStep = {
  /** seq of the `tool.started` event (stable id for React). */
  seq: number;
  tool: string;
  preview: string | null;
  running: boolean;
  duration: number | null;
  isError: boolean;
  startedAt: number;
};

export function emptyProgress(): AgentProgressState {
  return {
    running: false,
    status: "idle",
    iteration: 0,
    max_iterations: 0,
    current_tool: null,
    error: null,
    steps: [],
    nextSeq: 0,
  };
}

export function shouldDisplayAgentProgress(
  progress: AgentProgressState | null | undefined,
): boolean {
  if (!progress?.running) {
    return false;
  }
  return progress.status === "tool" || Boolean(progress.current_tool) || progress.steps.length > 0;
}

/** Fold `tool.started` / `tool.completed` events into the running step list. */
export function applyEvents(
  steps: AgentStep[],
  events: ProgressEvent[]
): AgentStep[] {
  if (!events.length) return steps;
  const next = steps.slice();
  for (const e of events) {
    if (e.kind === "tool.started") {
      next.push({
        seq: e.seq,
        tool: e.tool,
        preview: e.preview,
        running: true,
        duration: null,
        isError: false,
        startedAt: e.ts,
      });
    } else if (e.kind === "tool.completed") {
      // Match the most recent still-running step with the same tool name.
      for (let i = next.length - 1; i >= 0; i--) {
        if (next[i].running && next[i].tool === e.tool) {
          next[i] = {
            ...next[i],
            running: false,
            duration: e.duration,
            isError: e.is_error,
          };
          break;
        }
      }
    }
  }
  return next;
}
