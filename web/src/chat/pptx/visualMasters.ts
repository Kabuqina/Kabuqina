// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// Shared visual-master palettes for student PPT generation.
//
// Single source of truth for both the WorkspacePanel selector/preview and the
// PptxGenJS renderer (renderDeck.ts). Each master maps to a backgrounds + text
// + accent palette; the renderer reads these to style every slide.

export const PPT_VISUAL_MASTERS = [
  {
    id: "soft_editorial",
    name: "Soft Editorial",
    note: "柔和留白 / 编辑部感",
    palette: {
      background: "#F2EEDF",
      title: "#2A241B",
      accent: "#E1A4C2",
      accent2: "#D6DD63",
      muted: "rgba(92, 83, 69, 0.36)",
      body: "#5C5345",
      pattern:
        "radial-gradient(circle at 84% 18%, rgba(225, 164, 194, 0.52), transparent 31%), radial-gradient(circle at 78% 82%, rgba(214, 221, 99, 0.46), transparent 24%)",
      swatches: ["#F2EEDF", "#E1A4C2", "#D6DD63", "#B7C7A8", "#C9BEDC"],
    },
  },
  {
    id: "blue_professional",
    name: "Blue Professional",
    note: "奶油纸底 / 电钴蓝商务",
    palette: {
      background: "#FDFAE7",
      title: "#111111",
      accent: "#1E2BFA",
      accent2: "#059669",
      muted: "rgba(107, 107, 107, 0.42)",
      body: "#4A4A4A",
      pattern:
        "linear-gradient(90deg, rgba(30, 43, 250, 0.14), transparent 56%), radial-gradient(circle at 88% 22%, rgba(30, 43, 250, 0.20), transparent 26%)",
      swatches: ["#FDFAE7", "#1E2BFA", "#111111", "#6B6B6B", "#059669"],
    },
  },
  {
    id: "signal",
    name: "Signal",
    note: "深海军蓝 / 暖金信号",
    palette: {
      background: "#1C2644",
      title: "#E2DCD0",
      accent: "#C8A870",
      accent2: "#F0ECE3",
      muted: "rgba(138, 150, 168, 0.58)",
      body: "#B8C0CE",
      pattern:
        "linear-gradient(135deg, rgba(200, 168, 112, 0.23), transparent 44%), linear-gradient(90deg, rgba(240, 236, 227, 0.08), transparent 64%)",
      swatches: ["#1C2644", "#232F55", "#C8A870", "#E2DCD0", "#8A96A8"],
    },
  },
  {
    id: "neo_grid_bold",
    name: "Neo Grid Bold",
    note: "黑白网格 / 荧光黄重音",
    palette: {
      background: "#ECECE8",
      title: "#0A0A0A",
      accent: "#E6FF3D",
      accent2: "#F5F4EF",
      muted: "rgba(10, 10, 10, 0.34)",
      body: "#33332F",
      pattern:
        "linear-gradient(90deg, rgba(10, 10, 10, 0.12) 1px, transparent 1px), linear-gradient(rgba(10, 10, 10, 0.12) 1px, transparent 1px)",
      swatches: ["#ECECE8", "#F5F4EF", "#0A0A0A", "#E6FF3D", "#8A8A85"],
    },
  },
  {
    id: "editorial_forest",
    name: "Editorial Forest",
    note: "森林绿编辑风 / 暖奶油粉",
    palette: {
      background: "#EFE7D4",
      title: "#2E4A2A",
      accent: "#E89CB1",
      accent2: "#3A5A36",
      muted: "rgba(46, 74, 42, 0.38)",
      body: "#46583F",
      pattern:
        "radial-gradient(circle at 84% 18%, rgba(232, 156, 177, 0.44), transparent 31%), linear-gradient(135deg, rgba(58, 90, 54, 0.16), transparent 62%)",
      swatches: ["#EFE7D4", "#2E4A2A", "#3A5A36", "#E89CB1", "#D27E96"],
    },
  },
] as const;

export type PptVisualMaster = (typeof PPT_VISUAL_MASTERS)[number];
export type PptVisualMasterId = PptVisualMaster["id"];

const DEFAULT_MASTER = PPT_VISUAL_MASTERS[0];

export function getVisualMaster(id: string | undefined | null): PptVisualMaster {
  return PPT_VISUAL_MASTERS.find((m) => m.id === id) ?? DEFAULT_MASTER;
}
