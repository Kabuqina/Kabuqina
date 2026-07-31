// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from "vitest";
import { deriveStudyRequestState } from "./pageState";

describe("deriveStudyRequestState", () => {
  it("does not turn an idle request into an empty state", () => {
    expect(deriveStudyRequestState({ status: "idle" })).toEqual({
      phase: "initial",
      refreshing: false,
      refreshErrorWithData: false,
    });
  });

  it("retains trusted content while refreshing", () => {
    expect(deriveStudyRequestState({ status: "loading", previous: { id: "old" } })).toEqual({
      phase: "loading",
      data: { id: "old" },
      refreshing: true,
      refreshErrorWithData: false,
    });
  });

  it("keeps refresh errors orthogonal to retained content", () => {
    expect(deriveStudyRequestState({
      status: "error",
      error: new Error("offline"),
      previous: { id: "old" },
    })).toEqual({
      phase: "error",
      data: { id: "old" },
      refreshing: false,
      refreshErrorWithData: true,
    });
  });
});
