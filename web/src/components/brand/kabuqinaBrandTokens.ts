// Component code: Copyright 2026 Kabuqina Contributors — Apache-2.0.
// Embedded Kabuqina brand artwork (mascot design, vector geometry, palette):
// Copyright (c) 2026 ladylydia — All Rights Reserved, NOT Apache-2.0.
// See assets/brand/LICENSE. Unbranded forks must replace the artwork.
// SPDX-License-Identifier: Apache-2.0 AND LicenseRef-Kabuqina-Brand

export const kabuqinaBrandTokens = {
  cup: {
    bodyTop: "#f7f7f7",
    bodyMid: "#e5e5e5",
    bodyBottom: "#cfcfcf",
    border: "#666b73",
    borderOpacity: 0.32,
    rimTop: "#fafafa",
    rimBottom: "#dedede",
    rimBorderOpacity: 0.24,
    handle: "#9ca3af",
    eye: "#5f6368",
    blush: "#8f949c",
    blushOpacity: 0.32,
  },
  latte: {
    center: "#d9d9d9",
    mid: "#bdbdbd",
    outer: "#9e9e9e",
    edge: "#757575",
  },
  coaster: {
    background: "#f5effa",
    line: "#8f75a8",
    lineOpacity: 0.75,
    border: "#8f75a8",
    borderOpacity: 0.77,
  },
  shadow: {
    ink: "#5a4a6a",
    deep: "#49385e",
    cupOpacity: 0.12,
    contactOpacity: 0.38,
    steamOpacity: 0.88,
  },
} as const;

export type KabuqinaBrandTokens = typeof kabuqinaBrandTokens;
