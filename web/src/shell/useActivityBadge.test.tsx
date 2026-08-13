// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { STUDY_LEARNING_EVENT } from "../study/learningEvent";
import type { GlobalActivityRecord, GlobalActivityResponse } from "./activityApi";
import { useActivityBadge } from "./useActivityBadge";

function record(over: Partial<GlobalActivityRecord>): GlobalActivityRecord {
  return {
    id: "study:tutor:run", domain: "study", kind: "tutor", status: "waiting",
    title: "现场", updatedAt: "2026-07-30T08:00:00Z",
    returnTarget: "/study/x/learn", fallbackTarget: "/study",
    canResume: true, canRetry: false, targetAvailable: true,
    ...over,
  };
}

function respond(items: GlobalActivityRecord[]): GlobalActivityResponse {
  return { items, count: items.length, limit: 100 };
}

describe("useActivityBadge", () => {
  it("counts only live study work — not terminal, not Studio", async () => {
    const load = vi.fn().mockResolvedValue(respond([
      record({ id: "a", status: "waiting" }),                                   // live
      record({ id: "b", status: "running" }),                                   // live
      record({ id: "c", status: "completed" }),                                 // 终态，不算
      record({ id: "d", domain: "studio", status: "recoverable" }),             // 别的域，不算
      // 知识核草稿待采用：顶层 status 是 completed，但按 sourceStatus 判定为活。
      record({ id: "e", kind: "knowledge_core_compilation", status: "completed", sourceStatus: "draft_ready" }),
      // 已取消的编译：不算。
      record({ id: "f", kind: "knowledge_core_compilation", status: "completed", sourceStatus: "cancelled" }),
    ]));

    const { result } = renderHook(() => useActivityBadge(load));
    await waitFor(() => expect(result.current.count).toBe(3));
  });

  it("stays at zero when the projection is unavailable (browser dev, no backend)", async () => {
    const load = vi.fn().mockRejectedValue(new Error("no tauri"));
    const { result } = renderHook(() => useActivityBadge(load));
    await waitFor(() => expect(load).toHaveBeenCalled());
    expect(result.current.count).toBe(0);
  });

  it("re-counts when a learning mutation fires", async () => {
    const load = vi.fn()
      .mockResolvedValueOnce(respond([record({ id: "a" })]))
      .mockResolvedValue(respond([record({ id: "a" }), record({ id: "b" })]));

    const { result } = renderHook(() => useActivityBadge(load));
    await waitFor(() => expect(result.current.count).toBe(1));

    act(() => { window.dispatchEvent(new Event(STUDY_LEARNING_EVENT)); });
    await waitFor(() => expect(result.current.count).toBe(2));
  });
});
