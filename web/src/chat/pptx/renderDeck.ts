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
  | "section_divider";

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

function drawPageBase(ctx: Pick<SlideCtx, "pptx" | "slide" | "p" | "master">): void {
  const { pptx, slide, p, master } = ctx;
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
  const titleColor = master.decorations.cardStyle === "filled" ? p.title : "FFFFFF";
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
  });
}

function renderTwoColumnBullets(ctx: SlideCtx): void {
  drawHeader(ctx);
  const bullets = ctx.spec.bullets ?? [];
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
  });
  ctx.slide.addText(bulletRows(bullets.slice(mid), false), {
    ...columns[1],
    ...textStyle(ctx, "body", "body"),
    valign: "top",
    lineSpacingMultiple: 1.15,
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

function renderMediaPlaceholder(ctx: SlideCtx): void {
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
    return diagramNodes(spec).length <= 4 ? "process_flow_horizontal" : "process_flow_vertical";
  }
  if (t === "screenshot_placeholder" || t === "chart_placeholder" || spec.placeholder) {
    return "media_placeholder";
  }
  if (t === "table" || (spec.table?.headers?.length ?? 0) > 0) {
    return (spec.table?.headers?.length ?? 0) === 2 ? "comparison_cards" : "data_table";
  }
  if (t === "agenda") return "section_divider";
  if (t === "closing" && bullets.length <= 3) return "hero_statement";

  // Bullet-driven pages.
  if (bullets.length <= 2 && avgLen(bullets) <= 64) return "hero_statement";
  if (bullets.length >= 6) return "two_column_bullets";
  return "standard_bullets";
}

// ---------------------------------------------------------------------------
// Cover + deck assembly
// ---------------------------------------------------------------------------

function addCover(pptx: pptxgen, deck: DeckSpec, p: Palette, master: VisualMasterV2): void {
  const slide = pptx.addSlide();
  const recipe = master.layouts.cover;
  const coverCtx: Pick<SlideCtx, "pptx" | "slide" | "p" | "master"> = { pptx, slide, p, master };
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
  if (master.decorations.footer !== "none") {
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
  const head = override?.fonts?.major || override?.fonts?.minor || master.typography.title.fontFace;
  const body = override?.fonts?.minor || override?.fonts?.major || master.typography.body.fontFace;
  if (head || body) {
    pptx.theme = { headFontFace: head, bodyFontFace: body };
  }

  addCover(pptx, deck, p, master);

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
    const slide = pptx.addSlide();
    const layoutId = chooseLayout(spec);
    const layoutRecipe = master.layouts[layoutId];
    audit.slideLayouts.push({
      slide: audit.slideLayouts.length + 2,
      title: spec.title ?? "",
      slideType: spec.slide_type,
      layout: layoutId,
    });
    const ctx: SlideCtx = { pptx, slide, spec, p, master, layoutId, layoutRecipe, pageW, pageH };
    LAYOUTS[layoutId](ctx);
    if (spec.notes) slide.addNotes(spec.notes);
  }

  const base64 = (await pptx.write({ outputType: "base64" })) as string;
  return { base64, slideCount: (deck.slides?.length ?? 0) + 1, audit };
}
