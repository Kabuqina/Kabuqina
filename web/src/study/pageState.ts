// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { Loadable } from "./loadable";

export type StudyRequestPhase = "initial" | "loading" | "ready" | "error";

export type StudyContentState =
  | "ready-empty"
  | "ready-content"
  | "working"
  | "draft-ready"
  | "operation-failed"
  | "operation-cancelled"
  | "target-invalid";

export type StudyRequestState<T> = {
  phase: StudyRequestPhase;
  data?: T;
  refreshing: boolean;
  refreshErrorWithData: boolean;
};

/** Keep request lifecycle separate from the page's domain-content state. */
export function deriveStudyRequestState<T>(snapshot: Loadable<T>): StudyRequestState<T> {
  if (snapshot.status === "ready") {
    return {
      phase: "ready",
      data: snapshot.data,
      refreshing: false,
      refreshErrorWithData: false,
    };
  }
  if (snapshot.status === "loading") {
    return {
      phase: "loading",
      ...(snapshot.previous ? { data: snapshot.previous } : {}),
      refreshing: Boolean(snapshot.previous),
      refreshErrorWithData: false,
    };
  }
  if (snapshot.status === "error") {
    return {
      phase: "error",
      ...(snapshot.previous ? { data: snapshot.previous } : {}),
      refreshing: false,
      refreshErrorWithData: Boolean(snapshot.previous),
    };
  }
  return {
    phase: "initial",
    refreshing: false,
    refreshErrorWithData: false,
  };
}
