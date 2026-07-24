// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from "vitest";
import { getOpenSessionId } from "./chatLocationState";

describe("chat location state", () => {
  it("accepts a bounded explicit session id", () => {
    expect(getOpenSessionId({ openSessionId: " session-a " })).toBe("session-a");
    expect(getOpenSessionId({ openSessionId: "" })).toBeNull();
    expect(getOpenSessionId({ openSessionId: "a".repeat(257) })).toBeNull();
  });
});
