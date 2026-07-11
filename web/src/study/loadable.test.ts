// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from "vitest";
import { RequestCoordinator, loading } from "./loadable";

describe("study loadable", () => {
  it("retains previous data while loading", () => {
    expect(loading(["space-a"])).toEqual({ status: "loading", previous: ["space-a"] });
  });

  it("rejects stale and cancelled generations", () => {
    const coordinator = new RequestCoordinator();
    const first = coordinator.begin();
    const second = coordinator.begin();
    expect(first.signal.aborted).toBe(true);
    expect(coordinator.isCurrent(first.generation)).toBe(false);
    expect(coordinator.isCurrent(second.generation)).toBe(true);
    coordinator.cancel();
    expect(coordinator.isCurrent(second.generation)).toBe(false);
  });
});
