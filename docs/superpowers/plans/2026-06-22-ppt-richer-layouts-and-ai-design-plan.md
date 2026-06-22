# Generate PPT Quality: Richer Layouts (Track A) + AI Design Layer (Track D)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Push the *existing* PptxGenJS deck generator to its useful ceiling — visibly more "designed" decks with varied, content-appropriate layouts — while keeping output a fully editable `.pptx`. Two composable tracks:

- **Track A — Richer renderer (deterministic, free):** real PptxGenJS slide masters with background chrome, an expanded decoration vocabulary, and more layout recipes.
- **Track D — AI design layer (paid model, no extra call):** ask the *already-running* planner call for richer per-slide design intent (spotlight stat, quote, metrics, explicit layout), and have the renderer honor it.

**Explicitly out of scope:** real template reuse (Track B — separate feature, do not touch), HTML/CSS→image rendering (Track C — rejected: not editable), LibreOffice headless (Track E — not considered). See [2026-06-16-ppt-real-template-reuse-roadmap.md](2026-06-16-ppt-real-template-reuse-roadmap.md) for B.

---

## Design principles (carry into every task)

1. **Editable `.pptx` is invariant.** Everything stays native PptxGenJS shapes/text — never images of slides.
2. **Division of labor** (the project's "good quality, nearly free" rule):
   - **Structure & design system → deterministic, free** — lives in the renderer (`renderDeck.ts` / `visualMasters.ts`) and the writer's delete-only cleanup (`_normalize_deck_slides`).
   - **Content depth & design intent → the paid model** — steered by `build_deliverable_planner_prompt`. Track D must **not** add a second model call; it asks the existing planner call for richer structured output.
3. **Fallback safety.** Track A edits the one and only renderer — there is no parallel fallback. Roll out per visual master, keep `npx tsc --noEmit` and `npm run test:chat-ux` green at every step, and never break the existing 9 layouts / 5 masters while adding new ones.
4. **New planner fields must survive the writer whitelist.** Any field Track D adds must be added to `_deck_slide_spec` ([pptx_writer.py:120](../../hermes_core/tools/document/pptx_writer.py)) and the `DeckSlideSpec` TS type, or it is silently dropped before reaching the renderer.

---

## Current pipeline (grounded — read before editing)

- **Plan (LLM, paid):** `build_deliverable_planner_prompt` ([prompt_builder.py:947](../../hermes_core/agent/prompt_builder.py)) emits slides using the vocabulary in [deliverable_contract.py](../../hermes_core/tools/deliverable_contract.py) (`PPTX_SLIDE_TYPES`, `PPTX_SLIDE_LAYOUTS`, `PPTX_STRUCTURES`).
- **Write (Python, deterministic, free):** `pptx_write` → `_deck_slide_spec` (strict field whitelist) → `_normalize_deck_slides` (delete-only) → `_build_deck_spec` → `pptx_render` artifact. `template_path` only contributes a palette via `_extract_pptx_theme` (Route A).
- **Render (web/PptxGenJS, deterministic, free):** `renderDeckToBase64` ([renderDeck.ts:833](../../web/src/chat/pptx/renderDeck.ts)) → per slide `chooseLayout` ([renderDeck.ts:754](../../web/src/chat/pptx/renderDeck.ts)) → `LAYOUTS[layoutId](ctx)`.

**Key gaps this plan closes:**
- No `defineSlideMaster`. Backgrounds are a flat color + per-slide rail/underline shapes drawn in `drawPageBase` / `drawHeader`. No background motif, no logo home.
- Footer / page number is drawn **only on the cover** (`addCover`); content slides have none.
- Only 9 layouts; `chooseLayout` keys off coarse signals; no stat / quote / timeline / image+text treatments.
- The planner emits content but no *design intent* (which number to spotlight, which line is the thesis, structured metrics).

---

## Track A — Richer PptxGenJS renderer

**Target effort:** ~4–6 dev days + 1 QA day.

### Task A1: Slide masters with background chrome

**Files:** Modify `web/src/chat/pptx/renderDeck.ts`, `web/src/chat/pptx/visualMasters.ts`.

- [ ] Add a `defineDeckMasters(pptx, master, p)` step in `renderDeckToBase64` (before any `addSlide`) that registers one PptxGenJS slide master per content role using `pptx.defineSlideMaster({ title, background, objects, slideNumber })`.
- [ ] Move repeating chrome from per-slide drawing into the master `objects`: background fill, the rail/underline accents, a corner/side decorative motif, and a footer band (brand text + page number + a labeled logo placeholder rect).
- [ ] `addSlide({ masterName })` for cover vs content; keep `drawHeader`/layout renderers drawing only *content*, not chrome.
- [ ] Extend `VisualMasterV2.decorations` with a `background` motif descriptor (e.g. `"none" | "corner" | "side_band" | "grid_ghost"`) so each master picks its motif declaratively; default keeps current look.
- [ ] Roll out for **one** master first (`blue_professional`), visually QA, then port the other four.

### Task A2: Decoration vocabulary expansion

**Files:** Modify `visualMasters.ts`, `renderDeck.ts` (`drawPageBase`).

- [ ] Generalize `drawPageBase` from `rail: left|top|none` to also render the new `background` motifs as master objects (A1), keeping flat fills only (no gradients — PptxGenJS can't honor the CSS `pattern` field, which stays preview-only).
- [ ] Ensure every motif is palette-driven (uses `accent` / `accent2` / `muted`) so uploaded-template palette overrides (Route A) still recolor cleanly.

### Task A3: New layout recipes & renderers

**Files:** Modify `visualMasters.ts` (`SlideLayoutId`, `DEFAULT_LAYOUTS`), `renderDeck.ts` (`SLIDE_LAYOUT_IDS`, `LAYOUTS`, renderers), `hermes_core/tools/deliverable_contract.py` (`PPTX_SLIDE_LAYOUTS`).

- [ ] Add layouts (each = new `SlideLayoutId` + recipe boxes in `DEFAULT_LAYOUTS` + a `renderX(ctx)` + entry in `LAYOUTS`):
  - `stat_callout` — one large number + label + supporting line (results/metrics).
  - `big_number_grid` — 2–4 stat callouts in a row (KPI row).
  - `pull_quote` — highlighted thesis / contribution statement.
  - `icon_grid` — 3–4 parallel items as numbered shape "chips" + short text (modules/features; note PptxGenJS has no icon font — use shapes/numerals, not glyphs).
  - `timeline` — horizontal milestones (project/process).
  - `image_text_split` — media placeholder left/right + bullets right/left (pairs a screenshot/chart with substance, satisfying the planner's "placeholder discipline" rule).
- [ ] Mirror the new ids into `PPTX_SLIDE_LAYOUTS` so the planner may request them (keep names identical to `SlideLayoutId`).

### Task A4: Footer & page numbers on every slide

**Files:** `renderDeck.ts`.

- [ ] Render `decorations.footer` (`brand` / `page_number` / `none`) on **content** slides via the master (A1), not just the cover. Use PptxGenJS `slideNumber` for real page numbers.
- [ ] Keep the cover's existing byline/citation footer; avoid double-drawing.

### Task A5: Overflow / auto-fit guards (Chinese)

**Files:** `renderDeck.ts`.

- [ ] Apply PptxGenJS text auto-fit (`fit: "shrink"`) to title and body boxes so long Chinese strings shrink instead of overflowing.
- [ ] Add a deterministic body cap (truncate/clamp bullet count or chars per box to the recipe height) in the renderer — free, model-independent, mirrors the writer's delete-only philosophy.

### Task A6: Contract & planner sync for new layouts

**Files:** `hermes_core/agent/prompt_builder.py`, `hermes_core/tests/agent/test_prompt_builder.py`.

- [ ] In the "PPT decks" block, briefly describe when each new layout is appropriate so the model can set `layout` intentionally (e.g. "single dominant number → `stat_callout`").
- [ ] Update `test_prompt_builder` expectations for the enlarged layout vocabulary.

**Run (Track A):**

```powershell
cd web
npm run test:chat-ux
npx tsc --noEmit
npm run build
```

---

## Track D — AI design layer (paid model, no extra call)

**Target effort:** ~2–3 dev days. Depends on A3 (new layouts) being available to honor.

### Task D1: Add design-intent fields to the shared contract

**Files:** `hermes_core/tools/deliverable_contract.py`, `hermes_core/tools/document/pptx_writer.py` (`_deck_slide_spec`), `web/src/chat/pptx/renderDeck.ts` (`DeckSlideSpec`).

- [ ] Define a small, bounded design-intent vocabulary (keep it tiny — every field must earn its place):
  - `emphasis`: `{ kind: "stat" | "quote" | "none", value?: string, label?: string }` — the one spotlight element on the slide.
  - `metrics`: `Array<{ value: string; label: string }>` (cap ~4) — structured numbers for `stat_callout` / `big_number_grid`.
- [ ] Add both to `_deck_slide_spec`'s whitelist (bounded/sanitized like the existing `placeholder` block) so they survive normalization.
- [ ] Add matching optional fields to the `DeckSlideSpec` TS interface.

### Task D2: Ask the existing planner call for design intent

**Files:** `hermes_core/agent/prompt_builder.py` (PPT block), `hermes_core/tests/agent/test_prompt_builder.py`.

- [ ] Extend the "Slide content quality" guidance: when a slide has a dominant number, emit `emphasis.kind="stat"` (+ `metrics`); when it states the core thesis/contribution, emit `emphasis.kind="quote"`. This rides the existing planning call — **no new model invocation**.
- [ ] Reinforce: structured `metrics` are preferred over burying numbers in prose, extending the existing "Structured visuals" rule.

### Task D3: Renderer honors design intent

**Files:** `web/src/chat/pptx/renderDeck.ts` (`chooseLayout`, renderers).

- [ ] In `chooseLayout`: `emphasis.kind="stat"` (or non-empty `metrics`) → `stat_callout` / `big_number_grid`; `emphasis.kind="quote"` → `pull_quote`. Explicit `layout` hint still wins.
- [ ] `stat_callout` / `big_number_grid` render from `metrics`; `pull_quote` renders from `emphasis.value`.

### Task D4: Deterministic free fallback selection

**Files:** `renderDeck.ts` (`chooseLayout`), `web/src/chat/chatUx.test.mjs`.

- [ ] Add free content-signal heuristics so decks improve even when the model omits design intent: detect a single dominant numeric bullet → `stat_callout`; detect 3–4 short parallel bullets → `icon_grid`. (The free counterpart to D2; lower priority than explicit intent.)
- [ ] Add source-contract tests for the new selection paths.

**Run (Track D):**

```powershell
# Python contract + planner
py -m pytest hermes_core/tests/agent/test_prompt_builder.py hermes_core/tests/tools/test_document_tools.py
# Web selection/render contract
cd web && npm run test:chat-ux && npx tsc --noEmit
```

---

## Recommended order

1. **A1 + A4** (slide masters + footer) on `blue_professional` only — the biggest "designed" jump for the least surface area. Visual QA before going wider.
2. **A2** then port A1/A4 to the other four masters.
3. **A3** new layouts (+ A6 contract sync) — pure additions, low regression risk.
4. **A5** overflow guards.
5. **D1 → D2 → D3** the AI design layer, now that the layouts it targets exist.
6. **D4** free fallback heuristics last.

A is shippable on its own; D layers on top.

## Risks

- **Renderer regressions:** A1 relocates chrome into masters — easy to double-draw or drop the rail. Mitigate with per-master rollout + visual QA + green `tsc`/tests each step.
- **PptxGenJS master limits:** confirm background images/shapes + `slideNumber` behave across the 5 palettes (esp. dark `signal`). Spike A1 on one master first.
- **Chinese overflow:** `fit: "shrink"` helps but isn't a panacea; A5's deterministic cap is the real backstop.
- **Planner field drift:** if D1 fields aren't whitelisted in `_deck_slide_spec`, they vanish silently — assert this in `test_document_tools`.

## Acceptance criteria

- Generated decks show a consistent designed background/footer/page-number on every slide, recolored correctly by both built-in masters and uploaded-template palettes.
- Result decks use ≥4 distinct layouts across a typical report (not wall-to-wall bullet slides), including at least one stat/quote/timeline treatment when the content warrants it.
- Output opens and is fully editable in PowerPoint/WPS; no overflow off-slide on long Chinese strings.
- No new model call is introduced for Track D; `npx tsc --noEmit`, `npm run test:chat-ux`, and the Python planner/writer tests pass.

## Dev workflow reminder

- **Web edits** (`renderDeck.ts`, `visualMasters.ts`): `npm run build` in `web/`.
- **Python edits** (`prompt_builder.py`, `deliverable_contract.py`, `pptx_writer.py`): run `scripts/sync-runtime-sources.ps1` + restart Kabuqina (the app runs the bundled `python/dist/runtime`, not source).
