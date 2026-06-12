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
import { getVisualMaster } from "./visualMasters";

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

export interface DeckSpec {
  title?: string;
  template?: string;
  template_subtitle?: string;
  template_badge?: string;
  visual_master?: string;
  visual_master_name?: string;
  page_size?: { width?: number; height?: number };
  slides?: DeckSlideSpec[];
}

export interface RenderedDeck {
  base64: string;
  slideCount: number;
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
  pageW: number;
  pageH: number;
}

/** pptxgenjs wants hex colors without the leading '#'. */
function hex(color: string): string {
  return (color || "").replace(/^#/, "").toUpperCase() || "000000";
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

/** Title + accent rail + optional subtitle/kicker. Shared by most layouts. */
function drawHeader(ctx: SlideCtx): void {
  const { slide, spec, p, pptx } = ctx;
  slide.background = { color: p.bg };
  slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 0.16, h: "100%", fill: { color: p.accent } });
  const kicker = LAYOUT_LABELS[spec.slide_type] ?? "";
  if (kicker) {
    slide.addText(kicker, { x: 0.6, y: 0.32, w: 6, h: 0.3, fontSize: 11, bold: true, color: p.accent, charSpacing: 2 });
  }
  slide.addText(spec.title || "未命名页", {
    x: 0.6, y: kicker ? 0.64 : 0.42, w: 12.1, h: 0.7, fontSize: 26, bold: true, color: p.title,
  });
  if (spec.subtitle) {
    slide.addText(spec.subtitle, { x: 0.62, y: 1.34, w: 12, h: 0.38, fontSize: 14, bold: true, color: p.accent });
  }
}

function bodyTop(ctx: SlideCtx): number {
  return ctx.spec.subtitle ? 1.85 : 1.6;
}

function drawCard(
  ctx: SlideCtx,
  opts: { x: number; y: number; w: number; h: number; title: string; items: string[] },
): void {
  const { pptx, slide, p } = ctx;
  slide.addShape(pptx.ShapeType.roundRect, {
    x: opts.x, y: opts.y, w: opts.w, h: opts.h, rectRadius: 0.08,
    fill: { color: "FFFFFF" }, line: { color: p.accent, width: 1.25 },
  });
  slide.addShape(pptx.ShapeType.rect, { x: opts.x, y: opts.y, w: opts.w, h: 0.52, fill: { color: p.accent } });
  slide.addText(opts.title, {
    x: opts.x + 0.15, y: opts.y, w: opts.w - 0.3, h: 0.52, fontSize: 15, bold: true, color: "FFFFFF", valign: "middle",
  });
  slide.addText(bulletRows(opts.items, false), {
    x: opts.x + 0.2, y: opts.y + 0.62, w: opts.w - 0.4, h: opts.h - 0.74,
    fontSize: 14, color: p.body, valign: "top", lineSpacingMultiple: 1.08,
  });
}

// ---------------------------------------------------------------------------
// Layout renderers (each draws one full content slide)
// ---------------------------------------------------------------------------

function renderHeroStatement(ctx: SlideCtx): void {
  const { slide, spec, p, pptx } = ctx;
  slide.background = { color: p.bg };
  slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 0.16, h: "100%", fill: { color: p.accent } });
  if (spec.title) {
    slide.addText(spec.title, { x: 0.8, y: 0.7, w: 11.7, h: 0.4, fontSize: 14, bold: true, color: p.accent, charSpacing: 1 });
  }
  const statement = (spec.bullets && spec.bullets[0]) || spec.subtitle || spec.title || "请补充本页要点";
  slide.addText(statement, {
    x: 0.8, y: 1.9, w: 11.7, h: 2.7, fontSize: 36, bold: true, color: p.title, valign: "middle", lineSpacingMultiple: 1.05,
  });
  const support = (spec.bullets ?? []).slice(1);
  if (support.length) {
    slide.addText(support.join("      ·      "), { x: 0.85, y: 5.0, w: 11.6, h: 1.2, fontSize: 18, color: p.body });
  }
}

function renderStandardBullets(ctx: SlideCtx): void {
  drawHeader(ctx);
  ctx.slide.addText(bulletRows(ctx.spec.bullets ?? [], false), {
    x: 0.7, y: bodyTop(ctx), w: 12, h: 5.0, fontSize: 19, color: ctx.p.body, valign: "top", lineSpacingMultiple: 1.15,
  });
}

function renderTwoColumnBullets(ctx: SlideCtx): void {
  drawHeader(ctx);
  const bullets = ctx.spec.bullets ?? [];
  const mid = Math.ceil(bullets.length / 2);
  const top = bodyTop(ctx);
  ctx.slide.addText(bulletRows(bullets.slice(0, mid), false), {
    x: 0.7, y: top, w: 5.8, h: 5.0, fontSize: 17, color: ctx.p.body, valign: "top", lineSpacingMultiple: 1.15,
  });
  ctx.slide.addText(bulletRows(bullets.slice(mid), false), {
    x: 6.85, y: top, w: 5.8, h: 5.0, fontSize: 17, color: ctx.p.body, valign: "top", lineSpacingMultiple: 1.15,
  });
}

function renderSectionDivider(ctx: SlideCtx): void {
  drawHeader(ctx);
  const items = (ctx.spec.bullets ?? []).length ? ctx.spec.bullets! : ["请补充本页要点"];
  const rows: pptxgen.TextProps[] = items.slice(0, 6).map((text, i) => ({
    text: `${String(i + 1).padStart(2, "0")}   ${text}`,
    options: { paraSpaceAfter: 14, color: ctx.p.title },
  }));
  ctx.slide.addText(rows, {
    x: 0.9, y: bodyTop(ctx) + 0.2, w: 11.6, h: 4.8, fontSize: 22, valign: "top",
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
  const top = bodyTop(ctx) + 0.1;
  const h = 6.9 - top;
  drawCard(ctx, { x: 0.7, y: top, w: 5.85, h, title: sides.titles[0], items: sides.items[0] });
  drawCard(ctx, { x: 6.8, y: top, w: 5.85, h, title: sides.titles[1], items: sides.items[1] });
}

function diagramNodes(spec: DeckSlideSpec): string[] {
  return (spec.diagram?.nodes ?? spec.bullets ?? []).slice(0, 6);
}

function renderProcessFlowHorizontal(ctx: SlideCtx): void {
  drawHeader(ctx);
  const { pptx, slide, p, pageW } = ctx;
  const items = diagramNodes(ctx.spec);
  if (items.length < 2) {
    renderStandardBullets(ctx);
    return;
  }
  const boxW = 2.7, boxH = 1.15, gap = 0.4, top = 3.2;
  const totalW = items.length * boxW + (items.length - 1) * gap;
  let x = (pageW - totalW) / 2;
  items.forEach((node, i) => {
    slide.addShape(pptx.ShapeType.roundRect, {
      x, y: top, w: boxW, h: boxH, rectRadius: 0.08, fill: { color: "FFFFFF" }, line: { color: p.accent, width: 1.5 },
    });
    slide.addText(node, { x, y: top, w: boxW, h: boxH, fontSize: 14, bold: true, color: p.title, align: "center", valign: "middle" });
    if (i < items.length - 1) {
      slide.addText("→", { x: x + boxW, y: top, w: gap, h: boxH, fontSize: 20, bold: true, color: p.accent, align: "center", valign: "middle" });
    }
    x += boxW + gap;
  });
}

function renderProcessFlowVertical(ctx: SlideCtx): void {
  drawHeader(ctx);
  const { pptx, slide, p } = ctx;
  const items = diagramNodes(ctx.spec);
  if (items.length < 2) {
    renderStandardBullets(ctx);
    return;
  }
  const boxW = 7.4, boxH = 0.62, gap = 0.28, left = 2.95;
  let y = bodyTop(ctx) + 0.15;
  items.forEach((node, i) => {
    slide.addShape(pptx.ShapeType.roundRect, {
      x: left, y, w: boxW, h: boxH, rectRadius: 0.06, fill: { color: "FFFFFF" }, line: { color: p.accent, width: 1.25 },
    });
    slide.addText(node, { x: left, y, w: boxW, h: boxH, fontSize: 14, color: p.title, align: "center", valign: "middle" });
    if (i < items.length - 1) {
      slide.addText("↓", { x: left + boxW / 2 - 0.2, y: y + boxH, w: 0.4, h: gap, fontSize: 15, bold: true, color: p.accent, align: "center", valign: "middle" });
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
  const { slide, p } = ctx;
  const headerRow: pptxgen.TableRow = headers.map((h) => ({
    text: h,
    options: { bold: true, color: "FFFFFF", fill: { color: p.accent }, fontSize: 13, align: "center", valign: "middle" },
  }));
  const bodyRows: pptxgen.TableRow[] = rows.map((row) =>
    headers.map((_, c) => ({ text: row[c] ?? "", options: { color: p.body, fontSize: 12, valign: "middle" } })),
  );
  slide.addTable([headerRow, ...bodyRows], {
    x: 0.7, y: bodyTop(ctx), w: 11.9, border: { type: "solid", color: "D9D9D9", pt: 0.5 }, autoPage: false,
  });
}

function renderMediaPlaceholder(ctx: SlideCtx): void {
  drawHeader(ctx);
  const { pptx, slide, spec, p } = ctx;
  const ph = spec.placeholder || {};
  const kind = PLACEHOLDER_LABELS[spec.slide_type] || "PLACEHOLDER";
  const top = bodyTop(ctx) + 0.1;
  slide.addShape(pptx.ShapeType.roundRect, {
    x: 1.1, y: top, w: 11.1, h: 3.9, rectRadius: 0.1, fill: { color: "FFFFFF" }, line: { color: p.accent, width: 1.5, dashType: "dash" },
  });
  slide.addText(kind, { x: 1.5, y: top + 0.45, w: 10.3, h: 0.4, fontSize: 11, bold: true, color: p.accent, charSpacing: 1 });
  slide.addText(ph.label || (spec.slide_type === "chart_placeholder" ? "待补充图表" : "待补充截图"), {
    x: 1.5, y: top + 1.05, w: 10.3, h: 0.7, fontSize: 24, bold: true, color: p.title,
  });
  slide.addText(ph.caption || "请替换为真实材料后再提交。", { x: 1.5, y: top + 1.95, w: 10.3, h: 0.7, fontSize: 15, color: p.body });
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

function addCover(pptx: pptxgen, deck: DeckSpec, p: Palette): void {
  const slide = pptx.addSlide();
  slide.background = { color: p.bg };
  slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: "100%", h: 0.14, fill: { color: p.accent } });
  if (deck.template_badge) {
    slide.addText(deck.template_badge, { x: 0.6, y: 0.5, w: 4, h: 0.4, fontSize: 13, bold: true, color: p.accent, charSpacing: 1 });
  }
  slide.addText(deck.title || "学生汇报", {
    x: 0.6, y: 2.4, w: 12.1, h: 1.6, fontSize: 40, bold: true, color: p.title, valign: "middle",
  });
  slide.addText(deck.template_subtitle || deck.visual_master_name || "课程 / 论文 / 项目答辩", {
    x: 0.62, y: 4.2, w: 11, h: 0.6, fontSize: 18, color: p.body,
  });
  slide.addText("Kabuqina", { x: 0.6, y: 6.9, w: 3, h: 0.3, fontSize: 10, color: p.body });
}

export async function renderDeckToBase64(deck: DeckSpec): Promise<RenderedDeck> {
  const pptx = new pptxgen();
  const pageW = deck.page_size?.width ?? 13.333;
  const pageH = deck.page_size?.height ?? 7.5;
  pptx.defineLayout({ name: "KQ_WIDE", width: pageW, height: pageH });
  pptx.layout = "KQ_WIDE";

  const master = getVisualMaster(deck.visual_master);
  const p: Palette = {
    bg: hex(master.palette.background),
    title: hex(master.palette.title),
    body: hex(master.palette.body),
    accent: hex(master.palette.accent),
    accent2: hex(master.palette.accent2),
  };

  addCover(pptx, deck, p);

  for (const spec of deck.slides ?? []) {
    const slide = pptx.addSlide();
    const ctx: SlideCtx = { pptx, slide, spec, p, pageW, pageH };
    LAYOUTS[chooseLayout(spec)](ctx);
    if (spec.notes) slide.addNotes(spec.notes);
  }

  const base64 = (await pptx.write({ outputType: "base64" })) as string;
  return { base64, slideCount: (deck.slides?.length ?? 0) + 1 };
}
