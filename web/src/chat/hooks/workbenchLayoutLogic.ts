// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

export const WORKBENCH_NARROW_WIDTH = 640;

export function isWorkbenchNarrow(width: number): boolean {
  return Number.isFinite(width) && width < WORKBENCH_NARROW_WIDTH;
}
