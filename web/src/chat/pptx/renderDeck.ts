// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// PptxGenJS renderer for student decks.
//
// The Python `pptx_write` tool emits a structured *deck spec* (see
// hermes_core/tools/document_tools.py:_build_deck_spec) as a `pptx_render`
// interaction. This module turns that spec into a .pptx entirely in the
// browser/webview and returns it base64-encoded; Python persists the bytes.
//
// Each slide goes through a reusable single-slide design flow: `chooseLayout`
// picks a layout — honoring an optional planner `layout` hint, otherwise
// selecting by the page's own content signals — and the registered layout
// renderer draws that page. Adding a new design = registering one entry.

import pptxgen from "pptxgenjs";
import {
  getVisualMaster,
  type MasterLayoutId,
  type PaletteSlot,
  type VisualMasterLayoutBox,
  type VisualMasterV2,
} from "./visualMasters";

export type DeckSlideType =
  | "agenda"
  | "claim_bullets"
  | "diagram"
  | "table"
  | "screenshot_placeholder"
  | "chart_placeholder"
  | "qa_backup"
  | "closing";

export type SlideLayoutId =
  | "hero_statement"
  | "standard_bullets"
  | "two_column_bullets"
  | "comparison_cards"
  | "process_flow_horizontal"
  | "process_flow_vertical"
  | "data_table"
  | "media_placeholder"
  | "section_divider"
  | "stat_callout"
  | "pull_quote"
  | "image_text_split"
  | "big_number_grid"
  | "icon_grid"
  | "timeline";

export const SLIDE_LAYOUT_IDS: readonly SlideLayoutId[] = [
  "hero_statement",
  "standard_bullets",
  "two_column_bullets",
  "comparison_cards",
  "process_flow_horizontal",
  "process_flow_vertical",
  "data_table",
  "media_placeholder",
  "section_divider",
  "stat_callout",
  "pull_quote",
  "image_text_split",
  "big_number_grid",
  "icon_grid",
  "timeline",
];

export interface DeckSlideSpec {
  slide_type: DeckSlideType | string;
  /** Optional planner hint; one of SLIDE_LAYOUT_IDS. Omit for content-based auto-select. */
  layout?: string;
  title?: string;
  subtitle?: string;
  bullets?: string[];
  notes?: string;
  tags?: string[];
  diagram?: { nodes?: string[] };
  table?: { headers?: string[]; rows?: string[][] };
  placeholder?: { label?: string; caption?: string; source_hint?: string };
}

export interface DeckMeta {
  author?: string;
  affiliation?: string;
  date?: string;
  citation?: string;
}

/**
 * Inline visual master derived from a student-uploaded .pptx template (route A:
 * theme extraction). When present it overrides the built-in `visual_master`
 * palette, so the generated deck matches the school's colours and fonts while
 * keeping our rich layouts. Built in Python by document_tools._extract_pptx_theme.
 */
export interface DeckThemeOverride {
  background?: string;
  title?: string;
  body?: string;
  accent?: string;
  accent2?: string;
  fonts?: { major?: string; minor?: string };
}

export interface DeckSpec {
  title?: string;
  template?: string;
  template_subtitle?: string;
  template_badge?: string;
  visual_master?: string;
  visual_master_name?: string;
  /** Inline palette/fonts from an uploaded school template; overrides visual_master. */
  visual_master_palette?: DeckThemeOverride;
  page_size?: { width?: number; height?: number };
  meta?: DeckMeta;
  slides?: DeckSlideSpec[];
}

export interface RenderedDeck {
  base64: string;
  slideCount: number;
  audit: RenderAudit;
}

export interface RenderAudit {
  visualMasterId: string;
  visualMasterName: string;
  paletteSource: "visual_master" | "uploaded_template";
  effectivePalette: {
    background: string;
    title: string;
    body: string;
    accent: string;
    accent2: string;
  };
  slideLayouts: { slide: number; title: string; slideType: string; layout: SlideLayoutId }[];
}

interface Palette {
  bg: string;
  title: string;
  body: string;
  accent: string;
  accent2: string;
}

interface SlideCtx {
  pptx: pptxgen;
  slide: pptxgen.Slide;
  spec: DeckSlideSpec;
  p: Palette;
  master: VisualMasterV2;
  layoutId: SlideLayoutId;
  layoutRecipe: VisualMasterV2["layouts"][MasterLayoutId];
  pageW: number;
  pageH: number;
  /** A1: when true, background + rail come from a PptxGenJS slide master, so per-slide drawing skips them. */
  chromeInMaster?: boolean;
}

/** pptxgenjs wants hex colors without the leading '#'. */
function hex(color: string): string {
  return (color || "").replace(/^#/, "").toUpperCase() || "000000";
}

function colorFor(p: Palette, slot: PaletteSlot | undefined, fallback: keyof Palette): string {
  const key = slot === "background" ? "bg" : slot;
  return key ? p[key as keyof Palette] ?? p[fallback] : p[fallback];
}

function boxOr(recipeBox: VisualMasterLayoutBox | undefined, fallback: VisualMasterLayoutBox): VisualMasterLayoutBox {
  return recipeBox ?? fallback;
}

function textStyle(ctx: SlideCtx, role: keyof VisualMasterV2["typography"], fallbackColor: keyof Palette) {
  const style = ctx.master.typography[role];
  return {
    fontSize: style.fontSize,
    bold: style.bold,
    italic: style.italic,
    charSpacing: style.charSpacing,
    color: colorFor(ctx.p, style.color, fallbackColor),
    fontFace: style.fontFace,
  };
}

function masterFontFaces(master: VisualMasterV2, override?: DeckThemeOverride): { head: string; body: string } {
  const head = override?.fonts?.major || override?.fonts?.minor || master.typography.title.fontFace || "Microsoft YaHei UI";
  const body = override?.fonts?.minor || override?.fonts?.major || master.typography.body.fontFace || head;
  return { head, body };
}

function currentRecipe(ctx: SlideCtx): VisualMasterV2["layouts"][MasterLayoutId] {
  return ctx.layoutRecipe;
}

function slotColor(ctx: Pick<SlideCtx, "p">, slot: PaletteSlot, fallback: keyof Palette): string {
  return colorFor(ctx.p, slot, fallback);
}

const PLACEHOLDER_LABELS: Record<string, string> = {
  screenshot_placeholder: "SCREENSHOT PLACEHOLDER",
  chart_placeholder: "CHART PLACEHOLDER",
};

const LAYOUT_LABELS: Record<string, string> = {
  agenda: "AGENDA",
  diagram: "METHOD",
  table: "EVIDENCE",
  chart_placeholder: "SIGNAL",
  screenshot_placeholder: "ARTIFACT",
  qa_backup: "BACKUP",
  closing: "SUMMARY",
};

// ---------------------------------------------------------------------------
// Shared primitives
// ---------------------------------------------------------------------------

function bulletRows(bullets: string[], numbered: boolean): pptxgen.TextProps[] {
  const items = bullets.length ? bullets : ["请补充本页要点"];
  return items.map((text, i) => ({
    text: numbered ? `${i + 1}. ${text}` : text,
    options: { bullet: numbered ? false : { code: "2022" }, paraSpaceAfter: 8 },
  }));
}

function drawPageBase(ctx: Pick<SlideCtx, "pptx" | "slide" | "p" | "master" | "chromeInMaster">): void {
  const { pptx, slide, p, master } = ctx;
  if (ctx.chromeInMaster) return; // background + rail are provided by the slide master (A1)
  slide.background = { color: p.bg };
  if (master.decorations.rail === "left") {
    slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 0.16, h: "100%", fill: { color: p.accent } });
    slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 0.16, h: 1.1, fill: { color: p.accent2 } });
  }
  if (master.decorations.rail === "top") {
    slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: "100%", h: 0.14, fill: { color: p.accent } });
    slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 3.2, h: 0.14, fill: { color: p.accent2 } });
  }
}

/** Title + two-tone rail + accent2 underline + optional subtitle/kicker. */
function drawHeader(ctx: SlideCtx): void {
  const { slide, spec, p, pptx, master } = ctx;
  const recipe = currentRecipe(ctx);
  const titleBox = boxOr(recipe.title, { x: master.spacing.marginX, y: master.spacing.headerY, w: 12.1, h: 0.7 });
  drawPageBase(ctx);
  const kicker = LAYOUT_LABELS[spec.slide_type] ?? "";
  if (kicker) {
    slide.addText(kicker, {
      x: titleBox.x,
      y: Math.max(0.28, titleBox.y - 0.32),
      w: 6,
      h: 0.3,
      ...textStyle(ctx, "kicker", "accent"),
    });
  }
  slide.addText(spec.title || "未命名页", {
    ...titleBox,
    ...textStyle(ctx, "title", "title"),
    fit: "shrink",
  });
  if (master.decorations.underline !== "none") {
    slide.addShape(pptx.ShapeType.rect, {
      x: titleBox.x + 0.02,
      y: titleBox.y + titleBox.h + 0.08,
      w: master.decorations.underline === "wide" ? 2.4 : 1.5,
      h: 0.06,
      fill: { color: p.accent2 },
    });
  }
  if (spec.subtitle && recipe.subtitle) {
    slide.addText(spec.subtitle, {
      ...recipe.subtitle,
      ...textStyle(ctx, "subtitle", "accent"),
    });
  }
}

function bodyTop(ctx: SlideCtx): number {
  return currentRecipe(ctx).body.y ?? ctx.master.spacing.bodyTop;
}

function drawCard(
  ctx: SlideCtx,
  opts: { x: number; y: number; w: number; h: number; title: string; items: string[]; accent?: string },
): void {
  const { pptx, slide, p, master } = ctx;
  const ac = opts.accent ?? p.accent;
  const fill = master.decorations.cardStyle === "filled" ? ac : "FFFFFF";
  const titleColor = master.decorations.cardStyle === "filled" ? p.title : master.decorations.cardStyle === "minimal" ? ac : "FFFFFF";
  const bodyColor = master.decorations.cardStyle === "filled" ? p.title : p.body;
  slide.addShape(pptx.ShapeType.roundRect, {
    x: opts.x, y: opts.y, w: opts.w, h: opts.h, rectRadius: 0.08,
    fill: { color: fill }, line: { color: ac, width: 1.25 },
  });
  if (master.decorations.cardStyle !== "minimal") {
    slide.addShape(pptx.ShapeType.rect, { x: opts.x, y: opts.y, w: opts.w, h: 0.52, fill: { color: ac } });
  }
  slide.addText(opts.title, {
    x: opts.x + 0.15, y: opts.y, w: opts.w - 0.3, h: 0.52, fontSize: 15, bold: true, color: titleColor, valign: "middle",
  });
  slide.addText(bulletRows(opts.items, false), {
    x: opts.x + 0.2, y: opts.y + 0.62, w: opts.w - 0.4, h: opts.h - 0.74,
    fontSize: Math.max(12, master.typography.body.fontSize - 3), color: bodyColor, valign: "top", lineSpacingMultiple: 1.08,
  });
}

// ---------------------------------------------------------------------------
// Layout renderers (each draws one full content slide)
// ---------------------------------------------------------------------------

function renderHeroStatement(ctx: SlideCtx): void {
  const { slide, spec, p, pptx, master } = ctx;
  const recipe = currentRecipe(ctx);
  const titleBox = recipe.title;
  const body = recipe.body;
  drawPageBase(ctx);
  if (spec.title) {
    slide.addText(spec.title, { ...titleBox, ...textStyle(ctx, "kicker", "accent") });
  }
  if (master.decorations.underline !== "none") {
    slide.addShape(pptx.ShapeType.rect, { x: body.x + 0.02, y: Math.max(1.15, body.y - 0.6), w: master.decorations.underline === "wide" ? 2.4 : 1.8, h: 0.07, fill: { color: p.accent2 } });
  }
  const statement = (spec.bullets && spec.bullets[0]) || spec.subtitle || spec.title || "请补充本页要点";
  slide.addText(statement, {
    ...body,
    fontSize: Math.max(30, master.typography.coverTitle.fontSize - 4),
    bold: true,
    color: p.title,
    valign: "middle",
    lineSpacingMultiple: 1.05,
  });
  const support = (spec.bullets ?? []).slice(1);
  if (support.length) {
    slide.addText(support.join("      ·      "), {
      x: body.x + 0.05,
      y: Math.min(5.25, body.y + body.h + 0.4),
      w: Math.min(11.6, body.w),
      h: 1.2,
      ...textStyle(ctx, "body", "body"),
    });
  }
}

function renderStandardBullets(ctx: SlideCtx): void {
  drawHeader(ctx);
  const body = currentRecipe(ctx).body;
  ctx.slide.addText(bulletRows(ctx.spec.bullets ?? [], false), {
    ...body,
    ...textStyle(ctx, "body", "body"),
    valign: "top",
    lineSpacingMultiple: 1.15,
    fit: "shrink",
  });
}

function evidenceTitle(spec: DeckSlideSpec, index: number): string {
  const title = spec.table?.headers?.[index];
  if (title) return title;
  if (index === 0) return "观察维度";
  return "关键证据";
}

function renderEvidenceCards(ctx: SlideCtx): void {
  drawHeader(ctx);
  const bullets = ctx.spec.bullets ?? [];
  const rows = ctx.spec.table?.rows ?? [];
  const leftItems = rows.length ? rows.map((r) => r[0] ?? "").filter(Boolean) : bullets.slice(0, Math.ceil(bullets.length / 2));
  const rightItems = rows.length ? rows.map((r) => r[1] ?? "").filter(Boolean) : bullets.slice(Math.ceil(bullets.length / 2));
  const columns = currentRecipe(ctx).columns ?? [
    { x: 0.7, y: bodyTop(ctx), w: 5.8, h: 5.0 },
    { x: 6.85, y: bodyTop(ctx), w: 5.8, h: 5.0 },
  ];
  const pairs: Array<{ box: VisualMasterLayoutBox; title: string; items: string[]; accent: string }> = [
    { box: columns[0], title: evidenceTitle(ctx.spec, 0), items: leftItems, accent: ctx.p.accent },
    { box: columns[1], title: evidenceTitle(ctx.spec, 1), items: rightItems.length ? rightItems : leftItems, accent: ctx.p.accent2 },
  ];

  pairs.forEach(({ box, title, items, accent }) => {
    ctx.slide.addShape(ctx.pptx.ShapeType.roundRect, {
      ...box,
      rectRadius: 0.08,
      fill: { color: "FFFFFF" },
      line: { color: accent, width: 1.1 },
    });
    ctx.slide.addShape(ctx.pptx.ShapeType.rect, {
      x: box.x,
      y: box.y,
      w: 0.08,
      h: box.h,
      fill: { color: accent },
      line: { color: accent, transparency: 100 },
    });
    ctx.slide.addText(title, {
      x: box.x + 0.32,
      y: box.y + 0.28,
      w: box.w - 0.64,
      h: 0.34,
      fontFace: ctx.master.typography.kicker.fontFace,
      fontSize: 11,
      bold: true,
      charSpacing: 1.2,
      color: accent,
    });
    const displayItems = (items.length ? items : ["请补充证据"]).slice(0, 7);
    ctx.slide.addText(bulletRows(displayItems, false), {
      x: box.x + 0.34,
      y: box.y + 0.88,
      w: box.w - 0.7,
      h: box.h - 1.18,
      fontFace: ctx.master.typography.body.fontFace,
      fontSize: Math.max(13, ctx.master.typography.body.fontSize - 2),
      color: ctx.p.body,
      valign: "top",
      breakLine: false,
      lineSpacingMultiple: 1.08,
    });
  });
}

function renderTwoColumnBullets(ctx: SlideCtx): void {
  const bullets = ctx.spec.bullets ?? [];
  if (ctx.master.id === "blue_professional" || ctx.spec.table?.rows?.length) {
    renderEvidenceCards(ctx);
    return;
  }
  drawHeader(ctx);
  const mid = Math.ceil(bullets.length / 2);
  const columns = currentRecipe(ctx).columns ?? [
    { x: 0.7, y: bodyTop(ctx), w: 5.8, h: 5.0 },
    { x: 6.85, y: bodyTop(ctx), w: 5.8, h: 5.0 },
  ];
  ctx.slide.addText(bulletRows(bullets.slice(0, mid), false), {
    ...columns[0],
    ...textStyle(ctx, "body", "body"),
    valign: "top",
    lineSpacingMultiple: 1.15,
    fit: "shrink",
  });
  ctx.slide.addText(bulletRows(bullets.slice(mid), false), {
    ...columns[1],
    ...textStyle(ctx, "body", "body"),
    valign: "top",
    lineSpacingMultiple: 1.15,
    fit: "shrink",
  });
}

function renderSectionDivider(ctx: SlideCtx): void {
  drawHeader(ctx);
  const items = (ctx.spec.bullets ?? []).length ? ctx.spec.bullets! : ["请补充本页要点"];
  // Two runs per line: the index in accent2 (bold), the item in the title colour.
  const rows: pptxgen.TextProps[] = [];
  items.slice(0, 6).forEach((text, i) => {
    rows.push({ text: `${String(i + 1).padStart(2, "0")}   `, options: { color: ctx.p.accent2, bold: true } });
    rows.push({ text, options: { color: ctx.p.title, breakLine: true, paraSpaceAfter: 14 } });
  });
  const body = currentRecipe(ctx).body;
  ctx.slide.addText(rows, {
    ...body,
    fontSize: Math.max(19, ctx.master.typography.title.fontSize - 4),
    valign: "top",
  });
}

function comparisonSides(spec: DeckSlideSpec): { titles: [string, string]; items: [string[], string[]] } | null {
  const headers = spec.table?.headers ?? [];
  const rows = spec.table?.rows ?? [];
  if (headers.length === 2 && rows.length) {
    return {
      titles: [headers[0], headers[1]],
      items: [rows.map((r) => r[0] ?? ""), rows.map((r) => r[1] ?? "")],
    };
  }
  // Fall back: split bullets in half into two unnamed columns.
  const bullets = spec.bullets ?? [];
  if (bullets.length >= 2) {
    const mid = Math.ceil(bullets.length / 2);
    return { titles: ["A", "B"], items: [bullets.slice(0, mid), bullets.slice(mid)] };
  }
  return null;
}

function renderComparisonCards(ctx: SlideCtx): void {
  drawHeader(ctx);
  const sides = comparisonSides(ctx.spec);
  if (!sides) {
    renderStandardBullets(ctx);
    return;
  }
  const cards = currentRecipe(ctx).cards ?? [
    { x: 0.7, y: bodyTop(ctx) + 0.1, w: 5.85, h: 6.9 - bodyTop(ctx) },
    { x: 6.8, y: bodyTop(ctx) + 0.1, w: 5.85, h: 6.9 - bodyTop(ctx) },
  ];
  drawCard(ctx, { ...cards[0], title: sides.titles[0], items: sides.items[0] });
  drawCard(ctx, { ...cards[1], title: sides.titles[1], items: sides.items[1], accent: ctx.p.accent2 });
}

function diagramNodes(spec: DeckSlideSpec): string[] {
  return (spec.diagram?.nodes ?? spec.bullets ?? []).slice(0, 6);
}

function renderProcessFlowHorizontal(ctx: SlideCtx): void {
  drawHeader(ctx);
  const { pptx, slide, p, master } = ctx;
  const flow = master.components.flow;
  const items = diagramNodes(ctx.spec);
  if (items.length < 2) {
    renderStandardBullets(ctx);
    return;
  }
  const body = currentRecipe(ctx).body;
  const gap = Math.min(0.42, master.spacing.gutter);
  const boxW = Math.max(1.7, Math.min(2.9, body.w / Math.max(items.length, 1) - 0.25));
  const boxH = body.h;
  const totalW = items.length * boxW + (items.length - 1) * gap;
  let x = body.x + Math.max(0, (body.w - totalW) / 2);
  const top = body.y;
  items.forEach((node, i) => {
    const nodeFill = slotColor(ctx, flow.nodeFill, "bg");
    const nodeLine = slotColor(ctx, flow.nodeLine, "accent");
    const nodeText = slotColor(ctx, flow.nodeText, "title");
    slide.addShape(pptx.ShapeType.roundRect, {
      x, y: top, w: boxW, h: boxH, rectRadius: 0.08, fill: { color: nodeFill }, line: { color: nodeLine, width: flow.nodeStyle === "filled" ? 0.5 : 1.5 },
    });
    if (flow.nodeStyle === "banded") {
      slide.addShape(pptx.ShapeType.rect, { x, y: top, w: boxW, h: 0.15, fill: { color: p.title } });
    }
    slide.addText(node, { x, y: top, w: boxW, h: boxH, fontSize: Math.max(12, master.typography.body.fontSize - 3), bold: true, color: nodeText, align: "center", valign: "middle" });
    if (i < items.length - 1) {
      const connector = slotColor(ctx, flow.connector, "accent2");
      if (flow.connectorStyle === "bar") {
        slide.addShape(pptx.ShapeType.rect, { x: x + boxW + 0.04, y: top + boxH / 2 - 0.02, w: Math.max(0.05, gap - 0.08), h: 0.04, fill: { color: connector } });
      } else {
        slide.addText(flow.connectorStyle === "dot" ? "•" : "→", { x: x + boxW, y: top, w: gap, h: boxH, fontSize: flow.connectorStyle === "dot" ? 24 : 20, bold: true, color: connector, align: "center", valign: "middle" });
      }
    }
    x += boxW + gap;
  });
}

function renderProcessFlowVertical(ctx: SlideCtx): void {
  drawHeader(ctx);
  const { pptx, slide, p, master } = ctx;
  const flow = master.components.flow;
  const items = diagramNodes(ctx.spec);
  if (items.length < 2) {
    renderStandardBullets(ctx);
    return;
  }
  const body = currentRecipe(ctx).body;
  const boxW = body.w;
  const boxH = Math.max(0.52, Math.min(0.72, body.h / Math.max(items.length, 1) - 0.18));
  const gap = Math.min(0.3, master.spacing.gutter);
  const left = body.x;
  let y = body.y;
  items.forEach((node, i) => {
    const nodeFill = slotColor(ctx, flow.nodeFill, "bg");
    const nodeLine = slotColor(ctx, flow.nodeLine, "accent");
    const nodeText = slotColor(ctx, flow.nodeText, "title");
    slide.addShape(pptx.ShapeType.roundRect, {
      x: left, y, w: boxW, h: boxH, rectRadius: 0.06, fill: { color: nodeFill }, line: { color: nodeLine, width: flow.nodeStyle === "filled" ? 0.5 : 1.25 },
    });
    if (flow.nodeStyle === "banded") {
      slide.addShape(pptx.ShapeType.rect, { x: left, y, w: 0.12, h: boxH, fill: { color: p.title } });
    }
    slide.addText(node, { x: left, y, w: boxW, h: boxH, fontSize: Math.max(12, master.typography.body.fontSize - 3), color: nodeText, align: "center", valign: "middle" });
    if (i < items.length - 1) {
      const connector = slotColor(ctx, flow.connector, "accent2");
      if (flow.connectorStyle === "bar") {
        slide.addShape(pptx.ShapeType.rect, { x: left + boxW / 2 - 0.02, y: y + boxH + 0.04, w: 0.04, h: Math.max(0.05, gap - 0.08), fill: { color: connector } });
      } else {
        slide.addText(flow.connectorStyle === "dot" ? "•" : "↓", { x: left + boxW / 2 - 0.2, y: y + boxH, w: 0.4, h: gap, fontSize: flow.connectorStyle === "dot" ? 18 : 15, bold: true, color: connector, align: "center", valign: "middle" });
      }
    }
    y += boxH + gap;
  });
}

function renderDataTable(ctx: SlideCtx): void {
  drawHeader(ctx);
  const headers = ctx.spec.table?.headers ?? [];
  const rows = ctx.spec.table?.rows ?? [];
  if (!headers.length || !rows.length) {
    renderStandardBullets(ctx);
    return;
  }
  const { slide, master } = ctx;
  const table = master.components.table;
  const tableBox = currentRecipe(ctx).table ?? currentRecipe(ctx).body;
  const headerRow: pptxgen.TableRow = headers.map((h) => ({
    text: h,
    options: {
      bold: true,
      color: slotColor(ctx, table.headerText, "bg"),
      fill: { color: slotColor(ctx, table.headerFill, "accent") },
      fontSize: 13,
      align: "center",
      valign: "middle",
    },
  }));
  const bodyRows: pptxgen.TableRow[] = rows.map((row, r) =>
    headers.map((_, c) => ({
      text: row[c] ?? "",
      options: {
        color: slotColor(ctx, table.bodyText, "body"),
        fill: table.zebra && r % 2 === 1 ? { color: slotColor(ctx, table.border, "accent2"), transparency: 88 } : { color: slotColor(ctx, table.bodyFill, "bg") },
        fontSize: 12,
        valign: "middle",
      },
    })),
  );
  slide.addTable([headerRow, ...bodyRows], {
    ...tableBox,
    border: { type: "solid", color: slotColor(ctx, table.border, "accent2"), pt: 0.5 },
    autoPage: false,
  });
}

function chartItems(spec: DeckSlideSpec): Array<{ label: string; value: number }> {
  const source = (spec.bullets && spec.bullets.length ? spec.bullets : [
    spec.placeholder?.label,
    spec.placeholder?.caption,
  ].filter(Boolean) as string[]).slice(0, 5);
  const fallbackValues = [38, 54, 69, 83, 92];
  return (source.length ? source : ["基线", "方案A", "方案B", "本文方法"]).map((item, i) => {
    const match = item.match(/(\d+(?:\.\d+)?)/);
    return {
      label: item.replace(/[：:]\s*\d+(?:\.\d+)?[%％]?\s*$/, "").slice(0, 18),
      value: match ? Number(match[1]) : fallbackValues[i % fallbackValues.length],
    };
  });
}

function drawMiniChart(ctx: SlideCtx, box: VisualMasterLayoutBox, items: Array<{ label: string; value: number }>): void {
  const { pptx, slide, p, master } = ctx;
  const max = Math.max(...items.map((item) => item.value), 1);
  const plot = { x: box.x + 0.58, y: box.y + 1.28, w: box.w - 1.16, h: box.h - 2.15 };
  slide.addShape(pptx.ShapeType.rect, {
    x: plot.x,
    y: plot.y + plot.h,
    w: plot.w,
    h: 0.02,
    fill: { color: p.body, transparency: 35 },
    line: { color: p.body, transparency: 100 },
  });
  const gap = 0.22;
  const barW = Math.max(0.42, (plot.w - gap * (items.length - 1)) / items.length);
  items.forEach((item, i) => {
    const h = Math.max(0.18, (item.value / max) * plot.h);
    const x = plot.x + i * (barW + gap);
    const y = plot.y + plot.h - h;
    const color = i === items.length - 1 ? p.accent2 : p.accent;
    slide.addShape(pptx.ShapeType.rect, {
      x,
      y,
      w: barW,
      h,
      fill: { color },
      line: { color, transparency: 100 },
    });
    slide.addText(String(item.value), {
      x: x - 0.04,
      y: Math.max(plot.y - 0.25, y - 0.28),
      w: barW + 0.08,
      h: 0.22,
      fontFace: master.typography.caption.fontFace,
      fontSize: 9,
      bold: true,
      color,
      align: "center",
    });
    slide.addText(item.label, {
      x: x - 0.14,
      y: plot.y + plot.h + 0.1,
      w: barW + 0.28,
      h: 0.42,
      fontFace: master.typography.caption.fontFace,
      fontSize: 8.5,
      color: p.body,
      align: "center",
      fit: "shrink",
    });
  });
}

function renderChartSignal(ctx: SlideCtx): void {
  drawHeader(ctx);
  const { pptx, slide, spec, p, master } = ctx;
  const media = currentRecipe(ctx).media ?? currentRecipe(ctx).body;
  const legacyLabel = PLACEHOLDER_LABELS.chart_placeholder;
  slide.addShape(pptx.ShapeType.roundRect, {
    ...media,
    rectRadius: 0.1,
    fill: { color: p.bg },
    line: { color: p.accent, width: 1.25 },
  });
  slide.addText("SIGNAL CHART", {
    x: media.x + 0.42,
    y: media.y + 0.42,
    w: 2.3,
    h: 0.28,
    ...textStyle(ctx, "kicker", "accent"),
    color: p.accent2,
  });
  slide.addText(spec.placeholder?.label || spec.title || legacyLabel, {
    x: media.x + 0.42,
    y: media.y + 0.72,
    w: media.w - 0.84,
    h: 0.55,
    fontFace: master.typography.title.fontFace,
    fontSize: Math.max(20, master.typography.title.fontSize - 5),
    bold: true,
    color: p.accent2,
  });
  drawMiniChart(ctx, media, chartItems(spec));
  slide.addText(spec.placeholder?.caption || "根据正文数据自动生成的可编辑示意图；有真实数据时请在源材料中给出数值。", {
    x: media.x + 0.42,
    y: media.y + media.h - 0.58,
    w: media.w - 0.84,
    h: 0.34,
    ...textStyle(ctx, "caption", "body"),
  });
}

function renderMediaPlaceholder(ctx: SlideCtx): void {
  if (ctx.spec.slide_type === "chart_placeholder") {
    renderChartSignal(ctx);
    return;
  }
  drawHeader(ctx);
  const { pptx, slide, spec, master } = ctx;
  const mediaRecipe = master.components.media;
  const ph = spec.placeholder || {};
  const kind = PLACEHOLDER_LABELS[spec.slide_type] || "PLACEHOLDER";
  const media = currentRecipe(ctx).media ?? currentRecipe(ctx).body;
  slide.addShape(pptx.ShapeType.roundRect, {
    ...media,
    rectRadius: 0.1,
    fill: { color: slotColor(ctx, mediaRecipe.fill, "bg") },
    line: { color: slotColor(ctx, mediaRecipe.border, "accent"), width: 1.5, dashType: mediaRecipe.borderStyle === "dash" ? "dash" : "solid" },
  });
  slide.addText(kind, { x: media.x + 0.4, y: media.y + 0.45, w: media.w - 0.8, h: 0.4, ...textStyle(ctx, "kicker", "accent"), color: slotColor(ctx, mediaRecipe.label, "accent") });
  slide.addText(ph.label || (spec.slide_type === "chart_placeholder" ? "待补充图表" : "待补充截图"), {
    x: media.x + 0.4, y: media.y + 1.05, w: media.w - 0.8, h: 0.7, fontSize: Math.max(21, ctx.master.typography.title.fontSize - 3), bold: true, color: slotColor(ctx, mediaRecipe.label, "title"),
  });
  slide.addText(ph.caption || "请替换为真实材料后再提交。", { x: media.x + 0.4, y: media.y + 1.95, w: media.w - 0.8, h: 0.7, ...textStyle(ctx, "body", "body") });
}

// Parse "label: number" pairs from bullets/caption. Only returns metrics that
// carry a real number (no fabrication) — the planner is already told to emit
// this shape ("样本数: 500"). Track D will later prefer a structured field.
function statMetrics(spec: DeckSlideSpec): Array<{ label: string; value: string }> {
  const src = [...(spec.bullets ?? []), spec.placeholder?.caption].filter(Boolean) as string[];
  const out: Array<{ label: string; value: string }> = [];
  for (const s of src) {
    const m = s.match(/^(.*?)[：:]\s*([+\-]?\d[\d,]*(?:\.\d+)?\s*[%％]?)\s*$/);
    if (m && m[1].trim()) out.push({ label: m[1].trim().slice(0, 18), value: m[2].replace(/\s+/g, "") });
  }
  return out;
}

// One large hero number + label, with secondary metrics or supporting bullets
// alongside. Falls back to a hero statement when no real number is present.
function renderStatCallout(ctx: SlideCtx): void {
  const metrics = statMetrics(ctx.spec);
  if (!metrics.length) {
    renderHeroStatement(ctx);
    return;
  }
  drawHeader(ctx);
  const { slide, p, master } = ctx;
  const body = currentRecipe(ctx).body;
  const hero = metrics[0];
  const numW = Math.min(5.0, body.w * 0.42);
  slide.addText(hero.value, {
    x: body.x, y: body.y + 0.1, w: numW, h: 2.1,
    fontFace: master.typography.title.fontFace, fontSize: 80, bold: true,
    color: p.accent, align: "left", valign: "middle", fit: "shrink",
  });
  slide.addText(hero.label, {
    x: body.x + 0.04, y: body.y + 2.25, w: numW, h: 0.7,
    ...textStyle(ctx, "subtitle", "accent"), color: p.title,
  });
  const supportX = body.x + numW + 0.5;
  const supportW = body.x + body.w - supportX;
  const rest = metrics.slice(1);
  if (rest.length) {
    const rows: pptxgen.TextProps[] = [];
    rest.slice(0, 5).forEach((m) => {
      rows.push({ text: `${m.value}   `, options: { color: p.accent2, bold: true } });
      rows.push({ text: m.label, options: { color: p.body, breakLine: true, paraSpaceAfter: 12 } });
    });
    slide.addText(rows, {
      x: supportX, y: body.y + 0.2, w: supportW, h: body.h - 0.4,
      fontSize: Math.max(15, master.typography.body.fontSize - 1), valign: "top",
    });
  } else {
    const nonMetric = (ctx.spec.bullets ?? []).filter((b) => !/[：:]\s*[+\-]?\d/.test(b));
    if (nonMetric.length) {
      slide.addText(bulletRows(nonMetric.slice(0, 4), false), {
        x: supportX, y: body.y + 0.2, w: supportW, h: body.h - 0.4,
        ...textStyle(ctx, "body", "body"), valign: "top", lineSpacingMultiple: 1.15,
      });
    }
  }
}

// A large centered statement for a thesis / contribution / conclusion line.
function renderPullQuote(ctx: SlideCtx): void {
  const { slide, spec, p, master } = ctx;
  drawPageBase(ctx);
  const body = currentRecipe(ctx).body;
  slide.addText("“", {
    x: body.x - 0.1, y: Math.max(0.2, body.y - 1.1), w: 2.2, h: 1.7,
    fontFace: master.typography.title.fontFace, fontSize: 120, bold: true, color: p.accent2,
  });
  const quote = spec.bullets?.[0] || spec.subtitle || spec.title || "请补充本页要点";
  slide.addText(quote, {
    ...body, fontFace: master.typography.title.fontFace,
    fontSize: Math.max(24, master.typography.coverTitle.fontSize - 8), bold: true,
    color: p.title, align: "left", valign: "middle", lineSpacingMultiple: 1.12, fit: "shrink",
  });
  const attribution = spec.bullets && spec.bullets.length > 1
    ? spec.bullets.slice(1).join("   ·   ")
    : quote !== spec.title ? spec.title ?? "" : "";
  if (attribution) {
    slide.addText(`— ${attribution}`, {
      x: body.x + 0.05, y: body.y + body.h + 0.15, w: body.w, h: 0.6,
      ...textStyle(ctx, "subtitle", "accent"),
    });
  }
}

// Media placeholder (or auto chart) on one side, supporting bullets on the
// other — pairs a screenshot/figure with the substance that explains it.
function renderImageTextSplit(ctx: SlideCtx): void {
  drawHeader(ctx);
  const { pptx, slide, spec, p, master } = ctx;
  const recipe = currentRecipe(ctx);
  const textBox = recipe.body;
  const media = recipe.media ?? { x: 7.05, y: bodyTop(ctx), w: 5.6, h: 4.9 };
  slide.addText(bulletRows(spec.bullets ?? [], false), {
    ...textBox, ...textStyle(ctx, "body", "body"), valign: "top", lineSpacingMultiple: 1.18,
  });
  const ph = spec.placeholder || {};
  if (spec.slide_type === "chart_placeholder") {
    slide.addShape(pptx.ShapeType.roundRect, {
      ...media, rectRadius: 0.1, fill: { color: p.bg }, line: { color: p.accent, width: 1.25 },
    });
    slide.addText(ph.label || spec.title || "数据示意", {
      x: media.x + 0.3, y: media.y + 0.3, w: media.w - 0.6, h: 0.4,
      ...textStyle(ctx, "kicker", "accent"), color: p.accent2,
    });
    drawMiniChart(ctx, media, chartItems(spec));
  } else {
    const mediaRecipe = master.components.media;
    slide.addShape(pptx.ShapeType.roundRect, {
      ...media, rectRadius: 0.1,
      fill: { color: slotColor(ctx, mediaRecipe.fill, "bg") },
      line: { color: slotColor(ctx, mediaRecipe.border, "accent"), width: 1.5, dashType: mediaRecipe.borderStyle === "dash" ? "dash" : "solid" },
    });
    const kind = PLACEHOLDER_LABELS[spec.slide_type] || "PLACEHOLDER";
    slide.addText(kind, {
      x: media.x + 0.3, y: media.y + 0.35, w: media.w - 0.6, h: 0.35,
      ...textStyle(ctx, "kicker", "accent"), color: slotColor(ctx, mediaRecipe.label, "accent"),
    });
    slide.addText(ph.label || "待补充截图", {
      x: media.x + 0.3, y: media.y + media.h / 2 - 0.4, w: media.w - 0.6, h: 0.9,
      fontSize: Math.max(18, master.typography.title.fontSize - 5), bold: true,
      color: slotColor(ctx, mediaRecipe.label, "title"), align: "center", valign: "middle",
    });
    if (ph.caption) {
      slide.addText(ph.caption, {
        x: media.x + 0.3, y: media.y + media.h - 0.7, w: media.w - 0.6, h: 0.5,
        ...textStyle(ctx, "caption", "body"), align: "center",
      });
    }
  }
}

// Pick black/white text for legibility on a given fill (handles e.g. neon
// accents where white would vanish). Palette colors are 6-hex without '#'.
function contrastText(hexColor: string): string {
  const h = (hexColor || "").replace(/^#/, "");
  if (h.length !== 6) return "111111";
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.6 ? "111111" : "FFFFFF";
}

// A row of equal KPI cards (2-4) from parsed metrics; falls back to a single
// hero stat when fewer than two numbers are present.
function renderBigNumberGrid(ctx: SlideCtx): void {
  const metrics = statMetrics(ctx.spec);
  if (metrics.length < 2) {
    renderStatCallout(ctx);
    return;
  }
  drawHeader(ctx);
  const { pptx, slide, p, master } = ctx;
  const body = currentRecipe(ctx).body;
  const cards = metrics.slice(0, 4);
  const n = cards.length;
  const gap = 0.4;
  const cardW = (body.w - gap * (n - 1)) / n;
  const cardH = Math.min(body.h, 3.0);
  const top = body.y + Math.max(0, (body.h - cardH) / 2);
  cards.forEach((m, i) => {
    const x = body.x + i * (cardW + gap);
    const accent = i % 2 === 0 ? p.accent : p.accent2;
    const numColor = contrastText(accent) === "111111" ? "1A1A1A" : accent;
    slide.addShape(pptx.ShapeType.roundRect, { x, y: top, w: cardW, h: cardH, rectRadius: 0.08, fill: { color: "FFFFFF" }, line: { color: accent, width: 1.1 } });
    slide.addShape(pptx.ShapeType.rect, { x, y: top, w: cardW, h: 0.1, fill: { color: accent } });
    slide.addText(m.value, { x: x + 0.1, y: top + 0.45, w: cardW - 0.2, h: cardH * 0.46, fontFace: master.typography.title.fontFace, fontSize: 52, bold: true, color: numColor, align: "center", valign: "middle", fit: "shrink" });
    slide.addText(m.label, { x: x + 0.12, y: top + cardH - 1.0, w: cardW - 0.24, h: 0.8, fontFace: master.typography.body.fontFace, fontSize: Math.max(12, master.typography.body.fontSize - 3), color: p.body, align: "center", valign: "top", fit: "shrink" });
  });
}

// 2-6 short parallel items as numbered chips (modules / features). PptxGenJS
// has no icon font, so a numbered badge stands in for an icon.
function renderIconGrid(ctx: SlideCtx): void {
  drawHeader(ctx);
  const { pptx, slide, p, master } = ctx;
  const items = (ctx.spec.bullets ?? []).slice(0, 6);
  if (items.length < 2) {
    renderStandardBullets(ctx);
    return;
  }
  const body = currentRecipe(ctx).body;
  const cols = items.length <= 4 ? 2 : 3;
  const rows = Math.ceil(items.length / cols);
  const gapX = 0.4;
  const gapY = 0.35;
  const cellW = (body.w - gapX * (cols - 1)) / cols;
  const cellH = Math.min(2.1, (body.h - gapY * (rows - 1)) / rows);
  items.forEach((text, i) => {
    const r = Math.floor(i / cols);
    const c = i % cols;
    const x = body.x + c * (cellW + gapX);
    const y = body.y + r * (cellH + gapY);
    const accent = i % 2 === 0 ? p.accent : p.accent2;
    const badge = 0.6;
    slide.addShape(pptx.ShapeType.roundRect, { x, y, w: cellW, h: cellH, rectRadius: 0.08, fill: { color: "FFFFFF" }, line: { color: accent, width: 1.0 } });
    slide.addShape(pptx.ShapeType.ellipse, { x: x + 0.24, y: y + 0.26, w: badge, h: badge, fill: { color: accent } });
    slide.addText(String(i + 1), { x: x + 0.24, y: y + 0.26, w: badge, h: badge, fontFace: master.typography.title.fontFace, fontSize: 18, bold: true, color: contrastText(accent), align: "center", valign: "middle" });
    const parts = text.split(/[：:]/);
    const head = parts[0].trim();
    const rest = parts.slice(1).join("：").trim();
    slide.addText(rest ? head : text, { x: x + 1.02, y: y + 0.26, w: cellW - 1.24, h: 0.68, fontFace: master.typography.body.fontFace, fontSize: Math.max(13, master.typography.body.fontSize - 2), bold: true, color: contrastText("FFFFFF"), valign: "middle", fit: "shrink" });
    if (rest) {
      slide.addText(rest, { x: x + 0.3, y: y + 1.0, w: cellW - 0.55, h: cellH - 1.15, fontFace: master.typography.body.fontFace, fontSize: Math.max(11, master.typography.body.fontSize - 4), color: p.body, valign: "top", lineSpacingMultiple: 1.05 });
    }
  });
}

// Horizontal milestone strip: a baseline with evenly spaced nodes and labels
// alternating above/below. For phased plans / roadmaps.
function renderTimeline(ctx: SlideCtx): void {
  drawHeader(ctx);
  const { pptx, slide, p, master } = ctx;
  const items = (ctx.spec.diagram?.nodes ?? ctx.spec.bullets ?? []).slice(0, 6);
  if (items.length < 2) {
    renderStandardBullets(ctx);
    return;
  }
  const body = currentRecipe(ctx).body;
  const midY = body.y + body.h / 2;
  slide.addShape(pptx.ShapeType.rect, { x: body.x, y: midY - 0.015, w: body.w, h: 0.03, fill: { color: p.accent } });
  const n = items.length;
  const step = body.w / n;
  items.forEach((text, i) => {
    const cx = body.x + step * (i + 0.5);
    const dot = 0.26;
    const accent = i % 2 === 0 ? p.accent : p.accent2;
    const above = i % 2 === 0;
    slide.addShape(pptx.ShapeType.ellipse, { x: cx - dot / 2, y: midY - dot / 2, w: dot, h: dot, fill: { color: accent } });
    const labelX = cx - step / 2 + 0.1;
    const labelW = step - 0.2;
    const numY = above ? midY - 1.65 : midY + 0.42;
    slide.addText(String(i + 1).padStart(2, "0"), { x: labelX, y: numY, w: labelW, h: 0.32, fontFace: master.typography.kicker.fontFace, fontSize: 11, bold: true, color: accent, align: "center", charSpacing: 1 });
    slide.addText(text, { x: labelX, y: above ? numY + 0.32 : numY + 0.34, w: labelW, h: 1.0, fontFace: master.typography.body.fontFace, fontSize: Math.max(12, master.typography.body.fontSize - 3), color: p.title, align: "center", valign: above ? "bottom" : "top", lineSpacingMultiple: 1.0, fit: "shrink" });
  });
}

const LAYOUTS: Record<SlideLayoutId, (ctx: SlideCtx) => void> = {
  hero_statement: renderHeroStatement,
  standard_bullets: renderStandardBullets,
  two_column_bullets: renderTwoColumnBullets,
  comparison_cards: renderComparisonCards,
  process_flow_horizontal: renderProcessFlowHorizontal,
  process_flow_vertical: renderProcessFlowVertical,
  data_table: renderDataTable,
  media_placeholder: renderMediaPlaceholder,
  section_divider: renderSectionDivider,
  stat_callout: renderStatCallout,
  pull_quote: renderPullQuote,
  image_text_split: renderImageTextSplit,
  big_number_grid: renderBigNumberGrid,
  icon_grid: renderIconGrid,
  timeline: renderTimeline,
};

// ---------------------------------------------------------------------------
// Layout selection: planner hint first, then content-based heuristics
// ---------------------------------------------------------------------------

function avgLen(items: string[]): number {
  if (!items.length) return 0;
  return items.reduce((sum, s) => sum + s.length, 0) / items.length;
}

export function chooseLayout(spec: DeckSlideSpec): SlideLayoutId {
  const hint = spec.layout as SlideLayoutId | undefined;
  if (hint && (SLIDE_LAYOUT_IDS as readonly string[]).includes(hint)) return hint;

  const t = spec.slide_type;
  const bullets = spec.bullets ?? [];

  if (t === "diagram" || (spec.diagram?.nodes?.length ?? 0) > 0) {
    const nodes = diagramNodes(spec);
    const text = `${spec.title ?? ""} ${nodes.join(" ")}`.toLowerCase();
    if (nodes.length >= 2 && /阶段|时间线|里程碑|路线图|timeline|roadmap/.test(text)) return "timeline";
    return nodes.length <= 4 ? "process_flow_horizontal" : "process_flow_vertical";
  }
  if (t === "screenshot_placeholder" || t === "chart_placeholder" || spec.placeholder) {
    // Pair a placeholder with real substance side-by-side when bullets exist
    // (the planner's "placeholder discipline" rule); else a full-width frame.
    return (spec.bullets?.length ?? 0) >= 2 ? "image_text_split" : "media_placeholder";
  }
  if (t === "table" || (spec.table?.headers?.length ?? 0) > 0) {
    return (spec.table?.headers?.length ?? 0) === 2 ? "comparison_cards" : "data_table";
  }
  if (t === "agenda") return "section_divider";
  if (t === "closing" && bullets.length <= 1) return "pull_quote";
  if (t === "closing" && bullets.length <= 3) return "hero_statement";

  // Bullet-driven pages.
  const metrics = statMetrics(spec);
  if (metrics.length >= 3) return "big_number_grid";
  if (metrics.length >= 2) return "stat_callout";
  if (bullets.length >= 3 && bullets.length <= 6 && avgLen(bullets) <= 24) return "icon_grid";
  if (bullets.length <= 2 && avgLen(bullets) <= 64) return "hero_statement";
  if (bullets.length >= 6) return "two_column_bullets";
  return "standard_bullets";
}

// ---------------------------------------------------------------------------
// Cover + deck assembly
// ---------------------------------------------------------------------------

const MASTER_COVER = "KQ_COVER";
const MASTER_CONTENT = "KQ_CONTENT";

type SlideMasterProps = Parameters<pptxgen["defineSlideMaster"]>[0];
type MasterObject = NonNullable<SlideMasterProps["objects"]>[number];

/** A1: a visual master opts in to real PptxGenJS slide masters (chrome lives in the master, not per slide). */
function supportsSlideMaster(master: VisualMasterV2): boolean {
  return master.decorations.useSlideMaster === true;
}

function railObjects(p: Palette, master: VisualMasterV2): MasterObject[] {
  if (master.decorations.rail === "left") {
    return [
      { rect: { x: 0, y: 0, w: 0.16, h: "100%", fill: { color: p.accent } } },
      { rect: { x: 0, y: 0, w: 0.16, h: 1.1, fill: { color: p.accent2 } } },
    ];
  }
  if (master.decorations.rail === "top") {
    return [
      { rect: { x: 0, y: 0, w: "100%", h: 0.14, fill: { color: p.accent } } },
      { rect: { x: 0, y: 0, w: 3.2, h: 0.14, fill: { color: p.accent2 } } },
    ];
  }
  return [];
}

function motifObjects(p: Palette, master: VisualMasterV2, pageW: number, pageH: number): MasterObject[] {
  switch (master.decorations.background) {
    case "side_band":
      return [{ rect: { x: pageW - 0.12, y: 0, w: 0.12, h: "100%", fill: { color: p.accent2 } } }];
    case "corner":
      return [{ rect: { x: pageW - 1.6, y: pageH - 1.6, w: 1.6, h: 1.6, fill: { color: p.accent2, transparency: 88 } } }];
    default:
      return [];
  }
}

/** Register one cover master and one content master carrying this deck's repeating chrome. */
function defineDeckMasters(
  pptx: pptxgen,
  master: VisualMasterV2,
  p: Palette,
  pageW: number,
  pageH: number,
): { cover: string; content: string } {
  const background = { color: p.bg };
  const chrome = [...motifObjects(p, master, pageW, pageH), ...railObjects(p, master)];

  // Cover: background + rail + motif only. The title slide carries its own byline/citation and no page number.
  pptx.defineSlideMaster({ title: MASTER_COVER, background, objects: chrome });

  // Content: same chrome plus an optional footer band; page number via slideNumber when configured.
  const contentObjects: MasterObject[] = [...chrome];
  if (master.decorations.footer === "brand") {
    contentObjects.push({
      text: {
        text: "Kabuqina",
        options: { x: master.spacing.marginX, y: pageH - 0.45, w: 3, h: 0.3, fontSize: 9, color: p.body, fontFace: master.typography.caption.fontFace },
      },
    });
  }
  const content: SlideMasterProps = { title: MASTER_CONTENT, background, objects: contentObjects };
  if (master.decorations.footer === "page_number") {
    content.slideNumber = { x: pageW - 0.9, y: pageH - 0.45, w: 0.6, h: 0.3, fontSize: 9, color: p.body, align: "right", fontFace: master.typography.caption.fontFace };
  }
  pptx.defineSlideMaster(content);

  return { cover: MASTER_COVER, content: MASTER_CONTENT };
}

function addCover(pptx: pptxgen, deck: DeckSpec, p: Palette, master: VisualMasterV2, coverMasterName?: string): void {
  const slide = coverMasterName ? pptx.addSlide({ masterName: coverMasterName }) : pptx.addSlide();
  const recipe = master.layouts.cover;
  const coverCtx: Pick<SlideCtx, "pptx" | "slide" | "p" | "master" | "chromeInMaster"> = { pptx, slide, p, master, chromeInMaster: !!coverMasterName };
  drawPageBase(coverCtx);
  if (deck.template_badge) {
    slide.addText(deck.template_badge, { x: recipe.title.x, y: 0.5, w: 4, h: 0.4, fontSize: 13, bold: true, color: p.accent, charSpacing: 1 });
  }
  slide.addText(deck.title || "学生汇报", {
    ...recipe.title,
    fontSize: master.typography.coverTitle.fontSize,
    bold: master.typography.coverTitle.bold,
    color: colorFor(p, master.typography.coverTitle.color, "title"),
    fontFace: master.typography.coverTitle.fontFace,
    valign: "middle",
    fit: "shrink",
  });
  if (master.decorations.underline !== "none") {
    slide.addShape(pptx.ShapeType.rect, {
      x: recipe.title.x + 0.02,
      y: recipe.title.y + recipe.title.h + 0.12,
      w: master.decorations.underline === "wide" ? 3.2 : 2.4,
      h: 0.08,
      fill: { color: p.accent2 },
    });
  }
  slide.addText(deck.template_subtitle || deck.visual_master_name || "课程 / 论文 / 项目答辩", {
    ...(recipe.subtitle ?? { x: recipe.title.x, y: recipe.title.y + recipe.title.h + 0.4, w: 11, h: 0.6 }),
    fontSize: master.typography.body.fontSize,
    color: colorFor(p, master.typography.subtitle.color, "body"),
    fontFace: master.typography.subtitle.fontFace,
  });

  // Cover metadata: byline (author · affiliation · date) and an optional source
  // citation footer. Gives presenter/source info a structural home so it never
  // has to be crammed into an agenda or content slide.
  const meta = deck.meta ?? {};
  const byline = [meta.author, meta.affiliation, meta.date].filter(Boolean).join("   ·   ");
  if (byline) {
    slide.addText(byline, { x: recipe.body.x, y: recipe.body.y, w: recipe.body.w, h: 0.45, fontSize: 14, bold: true, color: p.accent });
  }
  if (meta.citation) {
    slide.addText(meta.citation, {
      x: recipe.body.x, y: 6.45, w: recipe.body.w, h: 0.4, ...master.typography.caption, color: colorFor(p, master.typography.caption.color, "body"), valign: "bottom",
    });
  }
  if (!coverMasterName && master.decorations.footer !== "none") {
    slide.addText(master.decorations.footer === "page_number" ? "01" : "Kabuqina", { x: recipe.body.x, y: 6.9, w: 3, h: 0.3, fontSize: 10, color: p.body });
  }
}

export async function renderDeckToBase64(deck: DeckSpec): Promise<RenderedDeck> {
  const pptx = new pptxgen();
  const pageW = deck.page_size?.width ?? 13.333;
  const pageH = deck.page_size?.height ?? 7.5;
  pptx.defineLayout({ name: "KQ_WIDE", width: pageW, height: pageH });
  pptx.layout = "KQ_WIDE";

  // An uploaded school template contributes an inline palette/fonts override
  // (route A); fall back to the selected built-in visual master per field.
  const override = deck.visual_master_palette;
  const master = getVisualMaster(deck.visual_master);
  const p: Palette = {
    bg: hex(override?.background ?? master.palette.background),
    title: hex(override?.title ?? master.palette.title),
    body: hex(override?.body ?? master.palette.body),
    accent: hex(override?.accent ?? master.palette.accent),
    accent2: hex(override?.accent2 ?? master.palette.accent2),
  };
  const fonts = masterFontFaces(master, override);
  pptx.theme = { headFontFace: fonts.head, bodyFontFace: fonts.body };

  // A1: opt-in visual masters render repeating chrome (background, rail, footer,
  // page number, motif) via real PptxGenJS slide masters; other masters keep the
  // per-slide drawing path unchanged.
  const useMasters = supportsSlideMaster(master);
  const masters = useMasters ? defineDeckMasters(pptx, master, p, pageW, pageH) : null;

  addCover(pptx, deck, p, master, masters?.cover);

  const audit: RenderAudit = {
    visualMasterId: master.id,
    visualMasterName: master.name,
    paletteSource: override ? "uploaded_template" : "visual_master",
    effectivePalette: {
      background: p.bg,
      title: p.title,
      body: p.body,
      accent: p.accent,
      accent2: p.accent2,
    },
    slideLayouts: [],
  };

  for (const spec of deck.slides ?? []) {
    const slide = masters ? pptx.addSlide({ masterName: masters.content }) : pptx.addSlide();
    const layoutId = chooseLayout(spec);
    const layoutRecipe = master.layouts[layoutId];
    audit.slideLayouts.push({
      slide: audit.slideLayouts.length + 2,
      title: spec.title ?? "",
      slideType: spec.slide_type,
      layout: layoutId,
    });
    const ctx: SlideCtx = { pptx, slide, spec, p, master, layoutId, layoutRecipe, pageW, pageH, chromeInMaster: useMasters };
    LAYOUTS[layoutId](ctx);
    if (spec.notes) slide.addNotes(spec.notes);
  }

  const base64 = (await pptx.write({ outputType: "base64" })) as string;
  return { base64, slideCount: (deck.slides?.length ?? 0) + 1, audit };
}
