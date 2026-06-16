# Generate Report PPT: Real Template Reuse Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Generate Report (PPT) from theme-based blank-slide rendering to real PowerPoint template reuse, while keeping the current visual-master renderer as the safe fallback.

**Architecture:** The current release keeps the PptxGenJS visual-master path unchanged. The next iteration adds a template-following path that imports a user-supplied `.pptx`, classifies reusable source slides, duplicates matched slides, and edits only replaceable text/data objects. The system should choose template reuse when a usable template is available and fall back to the current renderer when classification or editing is unsafe.

**Tech Stack:** `hermes_core` planner/tool contracts, `web/src/chat/pptx` renderer, `@oai/artifact-tool` for PPTX import/export/render/inspection, existing `pptx_write` interaction bridge, existing material index and outline review flow.

---

## Release Boundary

This roadmap is **post-release work**. Do not include real template reuse in the current Release unless it is a private spike that is not wired into the production `pptx_write` path.

Current Release scope:

- Keep the existing 5 visual masters.
- Keep current `pptx_write` behavior.
- Keep the JSON repair fix and component-level renderer improvements.
- Fix only release-blocking bugs.
- Describe the current PPT capability as theme-based generation, not strict school-template reuse.

## Product Direction

The current PptxGenJS route has reached the useful limit of "theme skin + reusable components." Further improvements to colors, fonts, and shape recipes will have diminishing returns.

The next meaningful quality jump is:

1. Read an existing PPT template.
2. Reuse actual slides and objects from that template.
3. Replace text/data in-place.
4. Preserve inherited typography, decoration, page chrome, footer, logo, and spatial rhythm.

## Milestone 1: Real Template Reuse MVP

**Target effort:** 2-4 development days plus 1-2 QA days.

**Goal:** Prove that copying real template slides and replacing text produces a visible quality jump over the current visual-master renderer.

**Supported template roles:**

- Cover
- Agenda
- Section divider
- Standard content
- Two-column content
- Diagram/process page
- Chart or figure placeholder
- Closing/Q&A

**MVP behavior:**

- If `template_path` is supplied and usable, import the PPTX.
- Inspect/render all source slides.
- Classify each source slide into one or more reusable roles.
- Map each generated slide spec to a source slide role.
- Duplicate the matched source slide.
- Replace obvious title/body text boxes.
- Preserve all unrelated template objects.
- Export the result.
- If anything is unsafe, fall back to the current visual-master renderer.

**MVP non-goals:**

- No general chart-data replacement.
- No automatic logo detection.
- No template library or long-term profile cache.
- No perfect object semantics.
- No complex multi-candidate scoring.

### Task 1: Template Inspection Wrapper

**Files:**

- Create: `web/src/chat/pptx/templateInspect.ts`
- Test: `web/src/chat/pptx/templateInspect.test.mjs` or extend existing source-contract tests if runtime testing is hard.

- [ ] Define `TemplateSlideSnapshot`.

```ts
export interface TemplateTextBoxSnapshot {
  id: string;
  text: string;
  x: number;
  y: number;
  w: number;
  h: number;
  fontSize?: number;
}

export interface TemplateSlideSnapshot {
  slideIndex: number;
  titleGuess?: string;
  width: number;
  height: number;
  textBoxes: TemplateTextBoxSnapshot[];
  shapeCount: number;
  imageCount: number;
  chartCount: number;
  tableCount: number;
  backgroundColor?: string;
}
```

- [ ] Add a function that converts artifact-tool layout/inspect output into `TemplateSlideSnapshot[]`.

```ts
export function snapshotsFromLayouts(layouts: unknown[]): TemplateSlideSnapshot[] {
  return layouts.map((layout, index) => {
    const root = layout as { slide?: { frame?: { width?: number; height?: number }; backgroundColor?: string }; elements?: any[] };
    const elements = Array.isArray(root.elements) ? root.elements : [];
    const textBoxes = elements
      .filter((element) => typeof element.textPreview === "string" && Array.isArray(element.bbox))
      .map((element) => ({
        id: String(element.aid || element.id || ""),
        text: String(element.textPreview || ""),
        x: Number(element.bbox[0] || 0),
        y: Number(element.bbox[1] || 0),
        w: Number(element.bbox[2] || 0),
        h: Number(element.bbox[3] || 0),
        fontSize: Number(element.resolvedFontSize || 0) || undefined,
      }));
    return {
      slideIndex: index,
      titleGuess: textBoxes.sort((a, b) => (b.fontSize || 0) - (a.fontSize || 0))[0]?.text,
      width: Number(root.slide?.frame?.width || 1280),
      height: Number(root.slide?.frame?.height || 720),
      textBoxes,
      shapeCount: elements.filter((element) => element.kind === "shape").length,
      imageCount: elements.filter((element) => element.kind === "image").length,
      chartCount: elements.filter((element) => element.kind === "chart").length,
      tableCount: elements.filter((element) => element.kind === "table").length,
      backgroundColor: root.slide?.backgroundColor,
    };
  });
}
```

- [ ] Add tests with hand-built layout JSON for title/body extraction.

Run:

```powershell
cd web
npm run test:chat-ux
npx tsc --noEmit
```

### Task 2: Slide Role Classifier

**Files:**

- Create: `web/src/chat/pptx/templateRoles.ts`
- Test: `web/src/chat/pptx/templateRoles.test.mjs` or source-contract tests.

- [ ] Define role vocabulary.

```ts
export type TemplateSlideRole =
  | "cover"
  | "agenda"
  | "section"
  | "standard_content"
  | "two_column"
  | "diagram"
  | "chart_or_figure"
  | "closing";
```

- [ ] Implement deterministic role classification from snapshot signals.

```ts
export function classifyTemplateSlide(slide: TemplateSlideSnapshot): TemplateSlideRole[] {
  const text = slide.textBoxes.map((box) => box.text).join("\n").toLowerCase();
  const roles: TemplateSlideRole[] = [];
  const largeText = slide.textBoxes.filter((box) => (box.fontSize || 0) >= 24).length;
  const hasAgendaText = /agenda|目录|大纲/.test(text);
  const hasClosingText = /thanks|thank you|谢谢|致谢|问答|q&a/.test(text);
  const hasFigureSignals = slide.imageCount > 0 || slide.chartCount > 0 || /图|chart|figure/.test(text);
  const leftBoxes = slide.textBoxes.filter((box) => box.x < slide.width * 0.45).length;
  const rightBoxes = slide.textBoxes.filter((box) => box.x > slide.width * 0.50).length;

  if (slide.slideIndex === 0 || largeText <= 2) roles.push("cover");
  if (hasAgendaText) roles.push("agenda");
  if (hasClosingText) roles.push("closing");
  if (hasFigureSignals) roles.push("chart_or_figure");
  if (leftBoxes >= 2 && rightBoxes >= 2) roles.push("two_column");
  if (slide.shapeCount >= 8 && slide.textBoxes.length >= 4) roles.push("diagram");
  if (roles.length === 0) roles.push("standard_content");
  return roles;
}
```

- [ ] Verify common Chinese labels classify correctly.

### Task 3: Slide Spec To Template Role Mapping

**Files:**

- Create: `web/src/chat/pptx/templateFrameMap.ts`
- Test: `web/src/chat/pptx/templateFrameMap.test.mjs` or source-contract tests.

- [ ] Map current deck slide types/layouts to template roles.

```ts
export function desiredTemplateRoles(spec: DeckSlideSpec, index: number): TemplateSlideRole[] {
  if (index === 0) return ["agenda", "standard_content"];
  if (spec.slide_type === "agenda") return ["agenda", "section", "standard_content"];
  if (spec.slide_type === "diagram") return ["diagram", "standard_content"];
  if (spec.slide_type === "chart_placeholder" || spec.slide_type === "screenshot_placeholder") {
    return ["chart_or_figure", "standard_content"];
  }
  if (spec.slide_type === "table" || spec.layout === "comparison_cards" || spec.layout === "two_column_bullets") {
    return ["two_column", "standard_content"];
  }
  if (spec.slide_type === "closing" || spec.slide_type === "qa_backup") return ["closing", "standard_content"];
  return ["standard_content"];
}
```

- [ ] Pick the first template slide with a matching role and enough text boxes.
- [ ] Avoid reusing cover for every content page unless no other slide exists.

### Task 4: Text Target Selection

**Files:**

- Create: `web/src/chat/pptx/templateTextTargets.ts`
- Test: `web/src/chat/pptx/templateTextTargets.test.mjs` or source-contract tests.

- [ ] Define text target roles.

```ts
export interface TemplateTextTargets {
  title?: TemplateTextBoxSnapshot;
  body?: TemplateTextBoxSnapshot;
  subtitle?: TemplateTextBoxSnapshot;
}
```

- [ ] Pick title as the largest upper-left or most prominent text box.
- [ ] Pick body as the largest remaining text area below title.
- [ ] Exclude likely decorative text: page numbers, one-character labels, footer-only boxes.

### Task 5: Template Reuse Renderer Spike

**Files:**

- Create: `web/src/chat/pptx/renderTemplateDeck.ts`
- Modify: `web/src/chat/pptx/renderDeck.ts`
- Test: source-contract tests plus manual artifact-tool render.

- [ ] Implement a non-production function first.

```ts
export async function renderTemplateDeckToBase64(deck: DeckSpec): Promise<RenderedDeck> {
  throw new Error("template reuse renderer is not wired yet");
}
```

- [ ] Add a guarded path that only activates when all required pieces are available.
- [ ] Keep the current renderer as default until the template path is proven.
- [ ] Export audit metadata:

```ts
export interface TemplateRenderAudit {
  renderer: "template_reuse";
  templatePath: string;
  mappedSlides: Array<{
    outputSlide: number;
    sourceSlide: number;
    role: string;
    replacedTextBoxes: number;
  }>;
  fallbackReason?: string;
}
```

### Task 6: Python Tool Contract

**Files:**

- Modify: `hermes_core/tools/document_tools.py`
- Test: `hermes_core/tests/tools/test_document_tools.py`

- [ ] Add a new renderer hint field to the web interaction artifact.

```python
spec["render_strategy"] = "template_reuse_if_available"
```

- [ ] Keep `template_path` validation exactly as strict as today: workspace-only.
- [ ] Return audit fields from the webview result when present.
- [ ] Ensure failure falls back or returns a clear error without corrupting the output file.

### Task 7: QA And Fallback

**Files:**

- Create: `web/src/chat/pptx/templateReuseQa.ts`
- Test: source-contract tests.

- [ ] Detect unsafe generated decks:
  - zero slides
  - unresolved text placeholders
  - no replaced text boxes
  - all output slides mapped to the same source slide except intentional simple templates
  - text count above a safe threshold in one target

- [ ] If unsafe, return fallback request to current renderer.

```ts
export interface TemplateReuseQaResult {
  ok: boolean;
  reason?: string;
}
```

### Task 8: MVP Manual QA Set

**Files:**

- Create: `docs/test-cases/ppt-template-reuse-mvp.md`

- [ ] Add at least 3 real-world templates:
  - school/academic template
  - course report template
  - code/project defense template

- [ ] For each template, test:
  - paper report
  - course report
  - code defense

- [ ] Save contact sheets for before/after visual comparison.
- [ ] Record failures with source slide number, output slide number, and screenshot.

## Milestone 2: Usable Version

**Target effort:** 1-2 weeks after MVP.

**Goal:** Make template reuse reliable enough for most course, paper, and code-defense PPT reports.

**Work items:**

- Improve slide role classifier using object geometry, not only text.
- Add object-level edit target maps.
- Add body text shrink/split behavior.
- Add per-structure mapping strategies for `paper_report`, `course_report`, and `code_defense`.
- Add visual QA checks for overflow, empty pages, low contrast, and unreplaced placeholders.
- Store a temporary template audit artifact for debugging.

**Acceptance criteria:**

- Uploaded school/course template outputs are recognizably based on the source template.
- Most decks preserve page chrome, typography, decoration, and footer.
- On bad templates, fallback is clear and non-destructive.

## Milestone 3: High-Quality Version

**Target effort:** 3-6 weeks after usable version.

**Goal:** Make generated PPTs feel manually adapted from the real template, not automatically skinned.

**Work items:**

- Template profile cache: classify a template once, reuse profile later.
- Real chart/table reuse: replace data inside existing chart/table frames when possible.
- Multi-candidate mapping: generate several slide mappings and score rendered output.
- Fine-grained revision: regenerate only selected slides after user feedback.
- Visual scoring: compare output rhythm against source template pages.

**Acceptance criteria:**

- Same template produces stable style across multiple decks.
- User can request local changes such as "第 5 页太空" or "图表页换成对比页" without full regeneration.
- Result no longer reads as "AI theme deck"; it reads as "a template-based deck someone edited."

## Risks

- **Artifact-tool API coverage:** If slide duplication or object editing is insufficient, the MVP may need a narrower scope.
- **Template diversity:** Some PPTX files have flattened images, strange placeholders, or non-editable backgrounds.
- **Text overflow:** Chinese text length can break layouts quickly.
- **False role classification:** A decorative-heavy slide can look like a diagram.
- **Release risk:** Wiring this before the current Release could destabilize a working path.

## Recommended Order

1. Release current version.
2. Build Milestone 1 behind a feature flag or hidden dev option.
3. Run manual QA against 3-5 real templates.
4. Promote to user-facing beta only after fallback and QA are stable.
5. Then invest in Milestone 2 and Milestone 3.
