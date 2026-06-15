// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// Shared visual-master design systems for student PPT generation.
//
// Single source of truth for both the WorkspacePanel selector/preview and the
// PptxGenJS renderer (renderDeck.ts). Each master now owns palette, typography,
// spacing, decorations, and layout recipes so generated decks can feel designed
// for the selected master while staying fully editable.

export type PaletteSlot = "background" | "title" | "body" | "accent" | "accent2";

export type SlideLayoutId =
  | "hero_statement"
  | "standard_bullets"
  | "two_column_bullets"
  | "comparison_cards"
  | "process_flow_horizontal"
  | "process_flow_vertical"
  | "data_table"
  | "media_placeholder"
  | "section_divider";

export type MasterLayoutId = SlideLayoutId | "cover";

export interface VisualTextStyle {
  fontFace?: string;
  fontSize: number;
  bold?: boolean;
  italic?: boolean;
  color?: PaletteSlot;
  charSpacing?: number;
}

export interface VisualMasterPalette {
  background: string;
  title: string;
  accent: string;
  accent2: string;
  muted: string;
  body: string;
  pattern: string;
  swatches: readonly string[];
}

export interface VisualMasterLayoutBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface VisualMasterLayoutRecipe {
  title: VisualMasterLayoutBox;
  subtitle?: VisualMasterLayoutBox;
  body: VisualMasterLayoutBox;
  columns?: readonly VisualMasterLayoutBox[];
  cards?: readonly VisualMasterLayoutBox[];
  table?: VisualMasterLayoutBox;
  media?: VisualMasterLayoutBox;
}

export interface VisualMasterV2 {
  id: string;
  name: string;
  note: string;
  palette: VisualMasterPalette;
  typography: {
    coverTitle: VisualTextStyle;
    title: VisualTextStyle;
    subtitle: VisualTextStyle;
    kicker: VisualTextStyle;
    body: VisualTextStyle;
    caption: VisualTextStyle;
  };
  spacing: {
    marginX: number;
    headerY: number;
    bodyTop: number;
    gutter: number;
  };
  decorations: {
    rail: "left" | "top" | "none";
    underline: "short" | "wide" | "none";
    footer: "brand" | "page_number" | "none";
    cardStyle: "outline" | "filled" | "minimal";
  };
  layouts: Record<MasterLayoutId, VisualMasterLayoutRecipe>;
}

const DEFAULT_LAYOUTS: Record<MasterLayoutId, VisualMasterLayoutRecipe> = {
  cover: {
    title: { x: 0.6, y: 2.4, w: 12.1, h: 1.6 },
    subtitle: { x: 0.62, y: 4.2, w: 11, h: 0.6 },
    body: { x: 0.62, y: 5.0, w: 11.5, h: 1.2 },
  },
  hero_statement: {
    title: { x: 0.8, y: 0.7, w: 11.7, h: 0.4 },
    body: { x: 0.8, y: 1.9, w: 11.7, h: 2.7 },
  },
  standard_bullets: {
    title: { x: 0.6, y: 0.64, w: 12.1, h: 0.7 },
    subtitle: { x: 0.62, y: 1.5, w: 12, h: 0.38 },
    body: { x: 0.7, y: 1.6, w: 12, h: 5.0 },
  },
  two_column_bullets: {
    title: { x: 0.6, y: 0.64, w: 12.1, h: 0.7 },
    subtitle: { x: 0.62, y: 1.5, w: 12, h: 0.38 },
    body: { x: 0.7, y: 1.6, w: 12, h: 5.0 },
    columns: [
      { x: 0.7, y: 1.6, w: 5.8, h: 5.0 },
      { x: 6.85, y: 1.6, w: 5.8, h: 5.0 },
    ],
  },
  comparison_cards: {
    title: { x: 0.6, y: 0.64, w: 12.1, h: 0.7 },
    subtitle: { x: 0.62, y: 1.5, w: 12, h: 0.38 },
    body: { x: 0.7, y: 1.7, w: 12, h: 5.2 },
    cards: [
      { x: 0.7, y: 1.7, w: 5.85, h: 5.2 },
      { x: 6.8, y: 1.7, w: 5.85, h: 5.2 },
    ],
  },
  process_flow_horizontal: {
    title: { x: 0.6, y: 0.64, w: 12.1, h: 0.7 },
    subtitle: { x: 0.62, y: 1.5, w: 12, h: 0.38 },
    body: { x: 0.7, y: 3.2, w: 12, h: 1.15 },
  },
  process_flow_vertical: {
    title: { x: 0.6, y: 0.64, w: 12.1, h: 0.7 },
    subtitle: { x: 0.62, y: 1.5, w: 12, h: 0.38 },
    body: { x: 2.95, y: 1.75, w: 7.4, h: 4.9 },
  },
  data_table: {
    title: { x: 0.6, y: 0.64, w: 12.1, h: 0.7 },
    subtitle: { x: 0.62, y: 1.5, w: 12, h: 0.38 },
    body: { x: 0.7, y: 1.6, w: 11.9, h: 5.2 },
    table: { x: 0.7, y: 1.6, w: 11.9, h: 5.2 },
  },
  media_placeholder: {
    title: { x: 0.6, y: 0.64, w: 12.1, h: 0.7 },
    subtitle: { x: 0.62, y: 1.5, w: 12, h: 0.38 },
    body: { x: 1.1, y: 1.7, w: 11.1, h: 3.9 },
    media: { x: 1.1, y: 1.7, w: 11.1, h: 3.9 },
  },
  section_divider: {
    title: { x: 0.6, y: 0.64, w: 12.1, h: 0.7 },
    subtitle: { x: 0.62, y: 1.5, w: 12, h: 0.38 },
    body: { x: 0.9, y: 1.8, w: 11.6, h: 4.8 },
  },
};

function withLayouts(overrides: Partial<Record<MasterLayoutId, Partial<VisualMasterLayoutRecipe>>> = {}): Record<MasterLayoutId, VisualMasterLayoutRecipe> {
  return Object.fromEntries(
    (Object.keys(DEFAULT_LAYOUTS) as MasterLayoutId[]).map((id) => [
      id,
      { ...DEFAULT_LAYOUTS[id], ...(overrides[id] ?? {}) },
    ]),
  ) as Record<MasterLayoutId, VisualMasterLayoutRecipe>;
}

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
    typography: {
      coverTitle: { fontSize: 40, bold: true, color: "title" },
      title: { fontSize: 26, bold: true, color: "title" },
      subtitle: { fontSize: 14, bold: true, color: "accent" },
      kicker: { fontSize: 11, bold: true, color: "accent", charSpacing: 2 },
      body: { fontSize: 18, color: "body" },
      caption: { fontSize: 11, italic: true, color: "body" },
    },
    spacing: { marginX: 0.7, headerY: 0.64, bodyTop: 1.74, gutter: 0.35 },
    decorations: { rail: "left", underline: "short", footer: "brand", cardStyle: "outline" },
    layouts: withLayouts({
      cover: {
        title: { x: 0.7, y: 2.25, w: 11.6, h: 1.5 },
        subtitle: { x: 0.72, y: 4.08, w: 10.8, h: 0.6 },
        body: { x: 0.72, y: 4.92, w: 10.8, h: 1.2 },
      },
      standard_bullets: {
        body: { x: 0.86, y: 1.82, w: 11.2, h: 4.8 },
      },
    }),
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
    typography: {
      coverTitle: { fontSize: 42, bold: true, color: "title" },
      title: { fontSize: 28, bold: true, color: "title" },
      subtitle: { fontSize: 13, bold: true, color: "accent" },
      kicker: { fontSize: 10, bold: true, color: "accent", charSpacing: 2 },
      body: { fontSize: 17, color: "body" },
      caption: { fontSize: 10, color: "body" },
    },
    spacing: { marginX: 0.62, headerY: 0.46, bodyTop: 1.52, gutter: 0.3 },
    decorations: { rail: "top", underline: "wide", footer: "page_number", cardStyle: "minimal" },
    layouts: withLayouts({
      cover: {
        title: { x: 0.72, y: 2.0, w: 11.8, h: 1.35 },
        subtitle: { x: 0.74, y: 3.7, w: 10.8, h: 0.5 },
        body: { x: 0.74, y: 5.2, w: 11.2, h: 0.9 },
      },
      two_column_bullets: {
        columns: [
          { x: 0.72, y: 1.62, w: 5.7, h: 5.0 },
          { x: 6.72, y: 1.62, w: 5.9, h: 5.0 },
        ],
      },
    }),
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
    typography: {
      coverTitle: { fontSize: 38, bold: true, color: "title" },
      title: { fontSize: 25, bold: true, color: "title" },
      subtitle: { fontSize: 13, color: "accent2" },
      kicker: { fontSize: 10, bold: true, color: "accent", charSpacing: 2 },
      body: { fontSize: 17, color: "body" },
      caption: { fontSize: 10, italic: true, color: "body" },
    },
    spacing: { marginX: 0.82, headerY: 0.72, bodyTop: 1.95, gutter: 0.42 },
    decorations: { rail: "left", underline: "short", footer: "brand", cardStyle: "filled" },
    layouts: withLayouts({
      cover: {
        title: { x: 0.86, y: 2.35, w: 11.4, h: 1.45 },
        subtitle: { x: 0.88, y: 4.15, w: 10.5, h: 0.55 },
        body: { x: 0.88, y: 5.05, w: 10.9, h: 1.0 },
      },
      hero_statement: {
        body: { x: 0.9, y: 1.9, w: 10.8, h: 2.9 },
      },
    }),
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
    typography: {
      coverTitle: { fontSize: 39, bold: true, color: "title" },
      title: { fontSize: 24, bold: true, color: "title" },
      subtitle: { fontSize: 12, bold: true, color: "body" },
      kicker: { fontSize: 10, bold: true, color: "title", charSpacing: 2 },
      body: { fontSize: 16, color: "body" },
      caption: { fontSize: 10, color: "body" },
    },
    spacing: { marginX: 0.56, headerY: 0.48, bodyTop: 1.45, gutter: 0.24 },
    decorations: { rail: "top", underline: "wide", footer: "page_number", cardStyle: "outline" },
    layouts: withLayouts({
      standard_bullets: {
        body: { x: 0.72, y: 1.46, w: 12.0, h: 5.25 },
      },
      process_flow_horizontal: {
        body: { x: 0.74, y: 3.0, w: 11.8, h: 1.08 },
      },
    }),
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
    typography: {
      coverTitle: { fontSize: 40, bold: true, color: "title" },
      title: { fontSize: 27, bold: true, color: "title" },
      subtitle: { fontSize: 14, color: "body" },
      kicker: { fontSize: 11, bold: true, color: "accent2", charSpacing: 1 },
      body: { fontSize: 18, color: "body" },
      caption: { fontSize: 10, italic: true, color: "body" },
    },
    spacing: { marginX: 0.78, headerY: 0.62, bodyTop: 1.82, gutter: 0.38 },
    decorations: { rail: "left", underline: "short", footer: "brand", cardStyle: "filled" },
    layouts: withLayouts({
      cover: {
        title: { x: 0.78, y: 2.18, w: 11.2, h: 1.55 },
        subtitle: { x: 0.8, y: 4.1, w: 10.7, h: 0.58 },
        body: { x: 0.8, y: 5.0, w: 10.8, h: 1.0 },
      },
      comparison_cards: {
        cards: [
          { x: 0.88, y: 1.9, w: 5.55, h: 4.95 },
          { x: 6.68, y: 1.9, w: 5.55, h: 4.95 },
        ],
      },
    }),
  },
] satisfies readonly VisualMasterV2[];

export type PptVisualMaster = VisualMasterV2;
export type PptVisualMasterId = (typeof PPT_VISUAL_MASTERS)[number]["id"];

const DEFAULT_MASTER = PPT_VISUAL_MASTERS[0];

export function getVisualMaster(id: string | undefined | null): PptVisualMaster {
  return PPT_VISUAL_MASTERS.find((m) => m.id === id) ?? DEFAULT_MASTER;
}
