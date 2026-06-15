# PPT Visual Master V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the five built-in PPT visual masters from palette-only themes into code-defined design systems that control typography, spacing, decorations, and per-layout geometry while keeping generated PPTX files editable.

**Architecture:** Keep the existing Python `pptx_write` interaction contract and frontend PptxGenJS renderer. Add a richer `VisualMasterV2` schema in the web PPT module, migrate the five built-in masters to that schema, and refactor renderer primitives so layout recipes drive coordinates and text styles.

**Tech Stack:** React/Vite TypeScript, PptxGenJS 3.12.0, Node source-inspection tests, existing Python `pptx_write` deck-spec bridge.

---

## Files And Responsibilities

- `web/src/chat/pptx/visualMasters.ts`
  - Own the `VisualMasterV2` types.
  - Define default layout recipes.
  - Export the five upgraded built-in masters.
  - Preserve `PPT_VISUAL_MASTERS`, `PptVisualMaster`, and `getVisualMaster` for current callers.

- `web/src/chat/pptx/renderDeck.ts`
  - Consume typography, spacing, decorations, and layout recipes from the selected master.
  - Keep `DeckSpec`, `DeckSlideSpec`, `chooseLayout`, and `renderDeckToBase64` public contracts stable.
  - Preserve the uploaded template palette/font override path.

- `web/src/chat/chatUx.test.mjs`
  - Lock in that visual masters expose V2 fields.
  - Lock in that `renderDeck.ts` reads V2 fields instead of hardcoding only palette values.
  - Preserve existing `pptx_render` StrictMode and visual-master selector tests.

## Task 1: Add VisualMasterV2 Contract Tests

**Files:**
- Modify: `web/src/chat/chatUx.test.mjs`
- Test: `web/src/chat/chatUx.test.mjs`

- [ ] **Step 1: Verify source reads for the PPT modules**

Confirm these source reads exist near the existing visual-master assertions. If either constant already exists, leave the existing declaration in place and use that name in the new assertions. If either constant does not exist, add the exact declaration below:

```js
const visualMastersSource = fs.readFileSync(
  new URL("./pptx/visualMasters.ts", import.meta.url),
  "utf8",
);
const renderDeckSource = fs.readFileSync(
  new URL("./pptx/renderDeck.ts", import.meta.url),
  "utf8",
);
```

- [ ] **Step 2: Add VisualMasterV2 schema assertions**

Add assertions that require the deeper master contract:

```js
assert.match(
  visualMastersSource,
  /export interface VisualMasterV2[\s\S]*typography[\s\S]*spacing[\s\S]*decorations[\s\S]*layouts/,
  "Visual masters should expose typography, spacing, decorations, and per-layout recipes.",
);

for (const layoutId of [
  "cover",
  "hero_statement",
  "standard_bullets",
  "two_column_bullets",
  "comparison_cards",
  "process_flow_horizontal",
  "process_flow_vertical",
  "data_table",
  "media_placeholder",
  "section_divider",
]) {
  assert.match(
    visualMastersSource,
    new RegExp(`${layoutId}[\\s\\S]*x[\\s\\S]*y[\\s\\S]*w[\\s\\S]*h`),
    `VisualMasterV2 should define a geometry recipe for ${layoutId}.`,
  );
}
```

- [ ] **Step 3: Add renderer-consumption assertions**

Add assertions proving the renderer reads the new fields:

```js
assert.match(
  renderDeckSource,
  /master\.typography[\s\S]*master\.spacing[\s\S]*master\.decorations[\s\S]*layoutRecipe/,
  "renderDeck should consume VisualMasterV2 typography, spacing, decorations, and layout recipes.",
);
assert.doesNotMatch(
  renderDeckSource,
  /const boxW = 2\.7, boxH = 1\.15, gap = 0\.4, top = 3\.2/,
  "Process layout geometry should come from the selected visual master, not a single hardcoded recipe.",
);
```

- [ ] **Step 4: Run the chat UX test and confirm failure**

Run:

```powershell
cd web
npm run test:chat-ux
```

Expected: FAIL because `VisualMasterV2`, layout recipe fields, and renderer consumption do not exist yet.

- [ ] **Step 5: Commit the failing tests**

Run:

```powershell
git add web/src/chat/chatUx.test.mjs
git commit -m "test: lock PPT visual master v2 contract"
```

## Task 2: Define VisualMasterV2 Types And Defaults

**Files:**
- Modify: `web/src/chat/pptx/visualMasters.ts`
- Test: `web/src/chat/chatUx.test.mjs`

- [ ] **Step 1: Add shared type aliases**

Add these exports near the top of `visualMasters.ts`:

```ts
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
```

- [ ] **Step 2: Add VisualMasterV2 interfaces**

Add these interfaces after the type aliases:

```ts
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
```

- [ ] **Step 3: Add a reusable default layout map**

Add a `DEFAULT_LAYOUTS` constant:

```ts
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
    body: { x: 0.7, y: 1.6, w: 12, h: 5.0 },
    columns: [
      { x: 0.7, y: 1.6, w: 5.8, h: 5.0 },
      { x: 6.85, y: 1.6, w: 5.8, h: 5.0 },
    ],
  },
  comparison_cards: {
    title: { x: 0.6, y: 0.64, w: 12.1, h: 0.7 },
    body: { x: 0.7, y: 1.7, w: 12, h: 5.2 },
    cards: [
      { x: 0.7, y: 1.7, w: 5.85, h: 5.2 },
      { x: 6.8, y: 1.7, w: 5.85, h: 5.2 },
    ],
  },
  process_flow_horizontal: {
    title: { x: 0.6, y: 0.64, w: 12.1, h: 0.7 },
    body: { x: 0.7, y: 3.2, w: 12, h: 1.15 },
  },
  process_flow_vertical: {
    title: { x: 0.6, y: 0.64, w: 12.1, h: 0.7 },
    body: { x: 2.95, y: 1.75, w: 7.4, h: 4.9 },
  },
  data_table: {
    title: { x: 0.6, y: 0.64, w: 12.1, h: 0.7 },
    body: { x: 0.7, y: 1.6, w: 11.9, h: 5.2 },
    table: { x: 0.7, y: 1.6, w: 11.9, h: 5.2 },
  },
  media_placeholder: {
    title: { x: 0.6, y: 0.64, w: 12.1, h: 0.7 },
    body: { x: 1.1, y: 1.7, w: 11.1, h: 3.9 },
    media: { x: 1.1, y: 1.7, w: 11.1, h: 3.9 },
  },
  section_divider: {
    title: { x: 0.6, y: 0.64, w: 12.1, h: 0.7 },
    body: { x: 0.9, y: 1.8, w: 11.6, h: 4.8 },
  },
};
```

- [ ] **Step 4: Add a merge helper for master-specific overrides**

Add this helper below `DEFAULT_LAYOUTS`:

```ts
function withLayouts(overrides: Partial<Record<MasterLayoutId, Partial<VisualMasterLayoutRecipe>>> = {}): Record<MasterLayoutId, VisualMasterLayoutRecipe> {
  return Object.fromEntries(
    (Object.keys(DEFAULT_LAYOUTS) as MasterLayoutId[]).map((id) => [
      id,
      { ...DEFAULT_LAYOUTS[id], ...(overrides[id] ?? {}) },
    ]),
  ) as Record<MasterLayoutId, VisualMasterLayoutRecipe>;
}
```

- [ ] **Step 5: Run the chat UX test**

Run:

```powershell
cd web
npm run test:chat-ux
```

Expected: still FAIL because the masters and renderer do not consume the new contract yet.

## Task 3: Upgrade The Five Built-In Masters

**Files:**
- Modify: `web/src/chat/pptx/visualMasters.ts`
- Test: `web/src/chat/chatUx.test.mjs`

- [ ] **Step 1: Type the master array as VisualMasterV2**

Change the array declaration to:

```ts
export const PPT_VISUAL_MASTERS = [
  // existing master objects, upgraded in the next steps
] satisfies readonly VisualMasterV2[];
```

- [ ] **Step 2: Add Soft Editorial design fields**

Extend the `soft_editorial` object with:

```ts
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
```

- [ ] **Step 3: Add Blue Professional design fields**

Extend the `blue_professional` object with:

```ts
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
```

- [ ] **Step 4: Add Signal design fields**

Extend the `signal` object with:

```ts
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
```

- [ ] **Step 5: Add Neo Grid Bold design fields**

Extend the `neo_grid_bold` object with:

```ts
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
```

- [ ] **Step 6: Add Editorial Forest design fields**

Extend the `editorial_forest` object with:

```ts
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
```

- [ ] **Step 7: Run TypeScript and chat UX tests**

Run:

```powershell
cd web
npm run test:chat-ux
npx tsc --noEmit
```

Expected: `tsc` passes. `test:chat-ux` may still fail until `renderDeck.ts` consumes the new fields.

- [ ] **Step 8: Commit the upgraded master definitions**

Run:

```powershell
git add web/src/chat/pptx/visualMasters.ts web/src/chat/chatUx.test.mjs
git commit -m "feat: define PPT visual master v2 schema"
```

## Task 4: Refactor Renderer Primitives To Use Master Recipes

**Files:**
- Modify: `web/src/chat/pptx/renderDeck.ts`
- Test: `web/src/chat/chatUx.test.mjs`

- [ ] **Step 1: Import shared layout types from visualMasters**

Change the import and remove duplicate local layout id definitions:

```ts
import { getVisualMaster, type MasterLayoutId, type SlideLayoutId, type VisualMasterLayoutBox, type VisualMasterV2 } from "./visualMasters";
```

Keep `SLIDE_LAYOUT_IDS` exported from `renderDeck.ts` if tests or callers rely on it, but type it with the imported `SlideLayoutId`.

- [ ] **Step 2: Add a richer SlideCtx**

Replace the `SlideCtx` interface with:

```ts
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
```

- [ ] **Step 3: Add style and recipe helpers**

Add these helpers after `hex`:

```ts
function colorFor(p: Palette, slot: keyof Palette | undefined, fallback: keyof Palette): string {
  return p[slot ?? fallback] ?? p[fallback];
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
```

- [ ] **Step 4: Update header drawing to use recipe and typography**

In `drawHeader`, replace fixed title/subtitle coordinates and fixed font sizes with:

```ts
const recipe = currentRecipe(ctx);
const titleBox = boxOr(recipe.title, { x: ctx.master.spacing.marginX, y: ctx.master.spacing.headerY, w: 12.1, h: 0.7 });
slide.addText(spec.title || "未命名页", {
  ...titleBox,
  ...textStyle(ctx, "title", "title"),
});
if (spec.subtitle && recipe.subtitle) {
  slide.addText(spec.subtitle, {
    ...recipe.subtitle,
    ...textStyle(ctx, "subtitle", "accent"),
  });
}
```

Keep the existing rail and underline behavior, but branch on `ctx.master.decorations.rail` and `ctx.master.decorations.underline`:

```ts
if (ctx.master.decorations.rail === "left") {
  slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 0.16, h: "100%", fill: { color: p.accent } });
  slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 0.16, h: 1.1, fill: { color: p.accent2 } });
}
if (ctx.master.decorations.rail === "top") {
  slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: "100%", h: 0.14, fill: { color: p.accent } });
  slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 3.2, h: 0.14, fill: { color: p.accent2 } });
}
```

- [ ] **Step 5: Update bodyTop to use master spacing**

Replace the current implementation with:

```ts
function bodyTop(ctx: SlideCtx): number {
  return currentRecipe(ctx).body?.y ?? ctx.master.spacing.bodyTop;
}
```

- [ ] **Step 6: Run the chat UX test**

Run:

```powershell
cd web
npm run test:chat-ux
```

Expected: renderer-consumption assertions are closer, but hardcoded process geometry assertion may still fail until Task 5.

## Task 5: Move Layout Renderers Onto Recipes

**Files:**
- Modify: `web/src/chat/pptx/renderDeck.ts`
- Test: `web/src/chat/chatUx.test.mjs`

- [ ] **Step 1: Update standard bullets**

Change `renderStandardBullets` to use the recipe body box and typography:

```ts
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
```

- [ ] **Step 2: Update two-column bullets**

Change `renderTwoColumnBullets` to use `recipe.columns`:

```ts
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
```

- [ ] **Step 3: Update comparison cards**

Use `recipe.cards` for positions:

```ts
const cards = currentRecipe(ctx).cards ?? [
  { x: 0.7, y: bodyTop(ctx) + 0.1, w: 5.85, h: 6.9 - bodyTop(ctx) },
  { x: 6.8, y: bodyTop(ctx) + 0.1, w: 5.85, h: 6.9 - bodyTop(ctx) },
];
drawCard(ctx, { ...cards[0], title: sides.titles[0], items: sides.items[0] });
drawCard(ctx, { ...cards[1], title: sides.titles[1], items: sides.items[1], accent: ctx.p.accent2 });
```

- [ ] **Step 4: Update process flow renderers**

Replace hardcoded `boxW`, `boxH`, `gap`, and `top` in `renderProcessFlowHorizontal` with recipe-derived values:

```ts
const body = currentRecipe(ctx).body;
const boxW = Math.max(1.7, Math.min(2.9, body.w / Math.max(items.length, 1) - 0.25));
const boxH = body.h;
const gap = Math.min(0.42, ctx.master.spacing.gutter);
const totalW = items.length * boxW + (items.length - 1) * gap;
let x = body.x + Math.max(0, (body.w - totalW) / 2);
const top = body.y;
```

Replace vertical layout constants with:

```ts
const body = currentRecipe(ctx).body;
const boxW = body.w;
const boxH = Math.max(0.52, Math.min(0.72, body.h / Math.max(items.length, 1) - 0.18));
const gap = Math.min(0.3, ctx.master.spacing.gutter);
const left = body.x;
let y = body.y;
```

- [ ] **Step 5: Update table and media layouts**

Use `recipe.table` and `recipe.media`:

```ts
const tableBox = currentRecipe(ctx).table ?? currentRecipe(ctx).body;
slide.addTable([headerRow, ...bodyRows], {
  ...tableBox,
  border: { type: "solid", color: "D9D9D9", pt: 0.5 },
  autoPage: false,
});
```

```ts
const media = currentRecipe(ctx).media ?? currentRecipe(ctx).body;
slide.addShape(pptx.ShapeType.roundRect, {
  ...media,
  rectRadius: 0.1,
  fill: { color: "FFFFFF" },
  line: { color: p.accent, width: 1.5, dashType: "dash" },
});
```

- [ ] **Step 6: Update deck assembly to pass master and recipe**

In the slide loop, compute layout id once:

```ts
for (const spec of deck.slides ?? []) {
  const slide = pptx.addSlide();
  const layoutId = chooseLayout(spec);
  const ctx: SlideCtx = {
    pptx,
    slide,
    spec,
    p,
    master,
    layoutId,
    layoutRecipe: master.layouts[layoutId],
    pageW,
    pageH,
  };
  LAYOUTS[layoutId](ctx);
  if (spec.notes) slide.addNotes(spec.notes);
}
```

- [ ] **Step 7: Run tests**

Run:

```powershell
cd web
npm run test:chat-ux
npx tsc --noEmit
```

Expected: both pass.

- [ ] **Step 8: Commit renderer recipe consumption**

Run:

```powershell
git add web/src/chat/pptx/renderDeck.ts web/src/chat/chatUx.test.mjs
git commit -m "feat: render PPT decks from visual master recipes"
```

## Task 6: Preserve Uploaded Template Theme Override

**Files:**
- Modify: `web/src/chat/pptx/renderDeck.ts`
- Test: `web/src/chat/chatUx.test.mjs`

- [ ] **Step 1: Confirm palette override remains field-by-field**

Keep this behavior in `renderDeckToBase64`:

```ts
const override = deck.visual_master_palette;
const master = getVisualMaster(deck.visual_master);
const p: Palette = {
  bg: hex(override?.background ?? master.palette.background),
  title: hex(override?.title ?? master.palette.title),
  body: hex(override?.body ?? master.palette.body),
  accent: hex(override?.accent ?? master.palette.accent),
  accent2: hex(override?.accent2 ?? master.palette.accent2),
};
```

- [ ] **Step 2: Keep layout recipes from the selected built-in master**

Do not replace `master.layouts` when `visual_master_palette` is present. The uploaded template changes palette/fonts in this phase, not layout geometry.

Add this test assertion:

```js
assert.match(
  renderDeckSource,
  /const master = getVisualMaster\(deck\.visual_master\)[\s\S]*visual_master_palette[\s\S]*master\.layouts/,
  "Uploaded template themes should override palette/fonts while keeping built-in layout recipes for VisualMasterV2.",
);
```

- [ ] **Step 3: Run tests**

Run:

```powershell
cd web
npm run test:chat-ux
npx tsc --noEmit
```

Expected: both pass.

- [ ] **Step 4: Commit override preservation**

Run:

```powershell
git add web/src/chat/pptx/renderDeck.ts web/src/chat/chatUx.test.mjs
git commit -m "test: preserve PPT template palette override path"
```

## Task 7: Final Verification

**Files:**
- No additional edits unless verification exposes a defect.

- [ ] **Step 1: Run frontend focused tests**

Run:

```powershell
cd web
npm run test:chat-ux
```

Expected: PASS.

- [ ] **Step 2: Run TypeScript and Vite build**

Run:

```powershell
cd web
npm run build
```

Expected: PASS. Existing Vite chunk-size warnings are acceptable if no new functional error appears.

- [ ] **Step 3: Run PPT writer contract tests**

Run:

```powershell
python -m pytest hermes_core\tests\tools\test_document_tools.py -q -k pptx
```

Expected: PASS with the existing PptxGenJS interaction contract tests.

- [ ] **Step 4: Review only intended diffs**

Run:

```powershell
git diff -- web/src/chat/pptx/visualMasters.ts web/src/chat/pptx/renderDeck.ts web/src/chat/chatUx.test.mjs
```

Expected: diffs only upgrade the visual master schema, renderer recipe consumption, and related tests.

- [ ] **Step 5: Commit verification fixes if any were needed**

Run only if Step 1, 2, or 3 required small corrections:

```powershell
git add web/src/chat/pptx/visualMasters.ts web/src/chat/pptx/renderDeck.ts web/src/chat/chatUx.test.mjs
git commit -m "fix: stabilize PPT visual master v2 rendering"
```

## Acceptance Criteria

- The five existing visual master ids and selector previews still work.
- Each built-in master declares typography, spacing, decorations, and layout recipes.
- `renderDeck.ts` consumes master-specific typography and geometry.
- Uploaded template palette/font override still works.
- No bitmap slide-background workaround is introduced.
- Generated PPT objects remain editable PptxGenJS text, shape, line, and table elements.
- `npm run test:chat-ux`, `npm run build`, and `python -m pytest hermes_core\tests\tools\test_document_tools.py -q -k pptx` pass.
