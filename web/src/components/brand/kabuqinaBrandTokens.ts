// Component code: Copyright 2026 Kabuqina Contributors — Apache-2.0.
// Embedded Kabuqina brand artwork (mascot design, vector geometry, palette):
// Copyright (c) 2026 ladylydia — All Rights Reserved, NOT Apache-2.0.
// See assets/brand/LICENSE. Unbranded forks must replace the artwork.
// SPDX-License-Identifier: Apache-2.0 AND LicenseRef-Kabuqina-Brand

export const kabuqinaBrandTokens = {
  cup: {
    bodyTop: "#ffffff",
    bodyMid: "#f5f0eb",
    bodyBottom: "#e8ddd4",
    border: "#6b5580",
    borderOpacity: 0.32,
    rimTop: "#ffffff",
    rimBottom: "#f0e6dc",
    rimBorderOpacity: 0.24,
    handle: "#b79fcd",
    eye: "#8b7d9a",
    blush: "#c495a0",
    blushOpacity: 0.32,
  },
  latte: {
    center: "#f5e6d0",
    mid: "#e8cfa8",
    outer: "#d4b080",
    edge: "#b8926a",
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
