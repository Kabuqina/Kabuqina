# Soft Editorial Rescue Notes

`soft_editorial` has been rebuilt from `assets\ppt\visual-masters\soft-editorial\soft-editorial_html`.

The current `template.pptx` is an HTML-background hybrid master. Each slide uses a browser-rendered PNG background from the source HTML, with transparent editable PowerPoint text boxes overlaid from DOM text-node coordinates.

The build script uses the deck-stage API to activate each slide, hides deck-stage navigation chrome before capture, applies a classroom readability floor, and rewrites text-box outlines to DrawingML `noFill` for LibreOffice and WPS compatibility.

## Design Identity

Soft Editorial is a warm, literary, magazine-spread presentation system:

- warm cream paper: `#F2EEDF`;
- deep warm ink: `#2A241B`;
- muted ink-soft: `#5C5345`;
- dusty pink: `#E1A4C2`;
- chartreuse lemon: `#D6DD63`;
- soft peach blush: `#E8C9B6`;
- sage green: `#B7C7A8`;
- lilac: `#C9BEDC`;
- Cormorant Garamond for every headline, numeral, quote, and ornamental moment;
- Work Sans for body, eyebrows, and sub-labels;
- translucent white cards (`rgba(255,255,255,0.55)`) with generous border-radius (24–36px);
- no drop shadows — depth from translucency and rounded form only.

It is strongest for student research recaps, literature presentations, course reports, reflective summaries, and any deck that wants a Sunday-supplement warmth instead of corporate polish.

It is weaker for punchy product launches, high-energy coding demos, or dense competitive analysis where stronger scanning contrast is needed.

## Source Layout Roles

| Source layout | Product role | Writer mapping |
| --- | --- | --- |
| `s-cover` | `cover` | cover/title slide |
| `s-foreword` | `foreword` | introductory narrative |
| `s-method` | `method` | process/steps |
| `s-insights` | `insights` | three-card findings |
| `s-closer` | `closer` | full-bleed statement moment |
| `s-numbers` | `numbers` | statistical summary |
| `s-quote` | `quote` | pull-quote/testimonial |
| `s-next` | `next` | next steps/recommendations |
| `s-consult` | `consult` | dense analysis page |
| `s-chart` | `chart` | chart with narrative |
| `s-process` | `process` | five-step process diagram |
| `s-matrix` | `matrix` | comparison matrix |

These roles are captured in `frame-map.json`.

## Current Status

Status remains `candidate` until the frontend and Writer consume `visual_master=soft_editorial`.
