# Blue Professional Rescue Notes

`blue_professional` is being rescued from the original HTML template at `D:\PPT\beautiful-html-templates-main\templates\blue-professional`.

The current `template.pptx` has been rebuilt as an HTML-background hybrid master. Each slide uses a high-fidelity PNG rendered from the source HTML as the background, then overlays editable PowerPoint text boxes extracted from DOM text-node coordinates. The overlay text is transparent, so the screenshot carries the visual appearance and the text boxes provide selectable/editable structure.

This is intentionally not a pure native-PowerPoint rebuild. The goal is to preserve the HTML template's visual fidelity first, while still giving the Writer a usable editable text layer.

The generated PPT applies a readability override on top of the source HTML. Body, chart, card, detail, and label text is enlarged for classroom/projector viewing at roughly 3 meters; the source HTML remains unchanged. The current generated text layer has no extracted text below 16px.

## Design Identity

Blue Professional is a restrained consulting/report presentation system:

- warm cream canvas: `#FDFAE7`;
- single electric cobalt accent: `#1E2BFA`;
- near-black headlines: `#111111`;
- muted grey body: `#6B6B6B`;
- soft cobalt-tinted cards and chart tracks;
- no decorative second accent color;
- no shadows on content cards;
- a persistent report rhythm using eyebrow labels, tag pills, slide counters, and cobalt progress accents.

The style is best for professional student-facing reports that need to feel polished and authoritative: literature presentations, research summaries, data-heavy course reports, and project defense decks with analysis.

It is weaker for playful, artistic, highly informal, or image-heavy presentations.

## Source Layout Roles

The HTML template defines these reusable layout classes:

| Source layout | Product role | Writer mapping |
| --- | --- | --- |
| `layout-cover` | `title` | cover/title slide |
| `layout-agenda` | `agenda` | agenda |
| `layout-metrics` | `stats` | metric summary, key findings |
| `layout-dashboard` | `dashboard` | dense stat grid, matrix |
| `layout-split` | `two_col` | split narrative, claim + evidence |
| `layout-bars` | `chart` | ranking/bar chart or chart placeholder |
| `layout-quote` | `quote` | major insight |
| `layout-timeline` | `timeline` | process or roadmap diagram |
| `layout-detail` | `detail` | detailed analysis blocks |
| `layout-closing` | `closing` | final thanks or CTA |

These roles are captured in `frame-map.json`.

## Rebuild Requirements

If this master is later rebuilt as a true native PowerPoint template, the rebuild should:

1. Create real named layouts or a writer-native renderer for every role in `frame-map.json`.
2. Use a stable prefix such as `BP_TITLE`, `BP_AGENDA`, `BP_STATS`, `BP_DASHBOARD`, `BP_TWO_COL`, `BP_CHART`, `BP_QUOTE`, `BP_TIMELINE`, `BP_DETAIL`, and `BP_CLOSING`.
3. Preserve the cream background and single-cobalt discipline.
4. Keep main headlines near-black; cobalt is only for eyebrows, numerals, accent rules, chart fills, and CTA elements.
5. Use translucent cobalt borders for cards, never full-opacity cobalt outlines.
6. Provide generous content-safe regions for generated Chinese text.
7. Avoid private sample content and hardcoded real organizations.

## Current Status

Status remains `candidate` until the frontend and Writer consume `visual_master=blue_professional`.

The asset now has:

- `template.pptx`: HTML-background hybrid PPTX;
- `backgrounds/`: one browser-rendered PNG background per slide;
- `text-layer.json`: DOM-derived editable text box coordinates;
- `preview.png`: contact sheet built from generated PPT previews;
- `metadata.json`: corrected product metadata and design tokens;
- `frame-map.json`: interface contract between Writer slide types and source visual frames;
- `design-notes.md`: rebuild and review guidance.
