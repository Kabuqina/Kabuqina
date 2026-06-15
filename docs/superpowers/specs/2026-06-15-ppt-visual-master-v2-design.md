# PPT Visual Master V2 Design

## Context

Kabuqina already has the student PPT content pipeline: material reading, material index, outline review, and `pptx_write`. It also has three structure templates (`course_report`, `paper_report`, `code_defense`) and a slide vocabulary shared between the planner and writer.

The remaining quality gap is visual. The current five built-in visual masters are mostly palettes plus preview metadata. The PptxGenJS renderer receives colours, but it still draws most slides through one generic geometry system. That makes the generated PPT editable and functional, but it does not feel like each master has its own design language.

This design upgrades the five built-in masters from "colour themes" into code-defined presentation design systems. It does not use the low-quality workaround of rendering template slides as bitmap backgrounds and overlaying editable text. Every generated object should remain a real PowerPoint shape, text box, table, or line wherever possible.

## Goals

1. Improve the visual match of generated decks to the selected built-in master, focused on typography and layout geometry.
2. Preserve the existing student PPT structure pipeline and `pptx_write` contract.
3. Keep PPT output editable in PowerPoint or WPS.
4. Keep generation nearly free: TypeScript layout recipes plus PptxGenJS, not image generation or expensive vision calls.
5. Make the master schema deep enough that uploaded `.pptx` template extraction can later feed the same renderer.

## Non-Goals

- Do not add more built-in visual masters in this phase.
- Do not redesign `course_report`, `paper_report`, or `code_defense` structure templates.
- Do not implement high-fidelity uploaded template reconstruction in this phase.
- Do not use bitmap slide-background screenshots as a template-matching shortcut.
- Do not make slide text uneditable for visual fidelity.

## Product Direction

The current five masters are enough for a V1 style library. The issue is not quantity; it is that each master exposes too little design information. Each master should become a small code-defined design system:

- palette;
- typography scale;
- spacing and margins;
- decoration rules;
- layout recipes per slide role.

The first target is A and B from the user discussion:

- A: colours and fonts should look intentional and master-specific;
- B: title/body positions, column ratios, and layout density should differ by master instead of sharing one generic layout.

## Architecture

### VisualMasterV2 Schema

`web/src/chat/pptx/visualMasters.ts` should expose a richer object while preserving existing fields used by the selector preview.

Recommended shape:

```ts
export interface VisualTextStyle {
  fontFace?: string;
  fontSize: number;
  bold?: boolean;
  italic?: boolean;
  color?: PaletteSlot;
  charSpacing?: number;
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
  columns?: VisualMasterLayoutBox[];
  cards?: VisualMasterLayoutBox[];
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
    rail?: "left" | "top" | "none";
    underline?: "short" | "wide" | "none";
    footer?: "brand" | "page_number" | "none";
    cardStyle?: "outline" | "filled" | "minimal";
  };
  layouts: Record<SlideLayoutId | "cover", VisualMasterLayoutRecipe>;
}
```

The implementation can start with plain TypeScript types and literal master objects. It does not need runtime validation unless tests show accidental drift.

### Renderer

`web/src/chat/pptx/renderDeck.ts` should stop hardcoding one set of coordinates for every master. The renderer should:

1. select the slide layout id using the existing `chooseLayout`;
2. load the selected master's `layouts[layoutId]`;
3. draw shared primitives using the master's typography, spacing, and decorations;
4. fall back to a default recipe when a field is missing.

This keeps the current renderer intact while gradually moving constants into master recipes.

### Built-In Masters

Each of the five masters should get a distinct geometry personality:

- `soft_editorial`: warm editorial, generous whitespace, low-density body area, soft accent rules.
- `blue_professional`: clean business, strong title grid, tight alignment, high readability.
- `signal`: dark presentation mode, bold contrast, restrained gold accent, more cinematic cover.
- `neo_grid_bold`: grid-heavy, compact, high contrast, visible structural lines.
- `editorial_forest`: organic editorial, warm background, softer title/body proportions.

The exact first implementation can use measured constants rather than extracting them from existing `.pptx` assets. The important contract is that each master owns its layout recipes.

### Uploaded Template Compatibility

Existing `_extract_pptx_theme` should remain as a palette/font override path. It should not be forced to produce full `VisualMasterV2` data in this phase.

The new schema should be shaped so a future extractor can produce partial fields:

- palette and fonts first;
- page size, margins, and common title/body boxes next;
- decoration and role mapping after that.

## Data Flow

1. Agent calls `pptx_write` with structured slides and `visual_master`.
2. Python builds a deck spec as it does today.
3. The desktop UI receives a `pptx_render` interaction.
4. `renderDeckToBase64` resolves a `VisualMasterV2`.
5. `chooseLayout` selects the per-slide layout id.
6. The renderer uses the selected master's recipe to draw editable PowerPoint objects.
7. The frontend returns base64 to Python.
8. Python writes the `.pptx` to the workspace.

## Error Handling

- Unknown visual master ids continue falling back to the default built-in master.
- Missing layout recipe fields fall back to default recipe values.
- Uploaded template theme overrides should override palette/fonts only; they should not erase built-in layout recipes.
- If a slide payload is thin, existing fallback content such as `请补充本页要点` remains acceptable.

## Testing

Add tests at the lowest useful cost:

- Every built-in master declares typography, spacing, decorations, and recipes for all current layout ids.
- `renderDeck.ts` consumes master typography and layout recipe values rather than only palette values.
- `chooseLayout` remains stable for existing slide inputs.
- The StrictMode `pptx_render` response guard remains intact.
- `npm run test:chat-ux` passes.
- `npm run build` passes.

The project currently uses source-inspection tests for chat UX. That style can remain for V1 as long as the assertions check contracts rather than brittle current data snapshots.

## Rollout

Phase 1:

- Add VisualMasterV2 types and helper defaults.
- Upgrade five built-in master definitions.
- Refactor renderer shared primitives to read recipe values.
- Add contract tests.

Phase 2:

- Tune each master visually using generated sample decks.
- Add optional HTML preview fixtures if visual regression needs more evidence.
- Extend uploaded `.pptx` extraction to emit partial layout hints.

## Acceptance Criteria

- Generated decks remain editable.
- The five existing masters still appear in the workspace selector.
- Each master produces visibly different cover, agenda, body, table, and flow pages.
- The renderer uses master-specific typography and geometry.
- The solution does not use bitmap backgrounds as the primary template-matching mechanism.
