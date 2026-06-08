# Editorial Forest Rescue Notes

`editorial_forest` has been rebuilt from `assets\ppt\visual-masters\editorial-forest\editorial-forest__html`.

The current `template.pptx` is an HTML-background hybrid master. Each slide uses a browser-rendered PNG background from the source HTML, with transparent editable PowerPoint text boxes overlaid from DOM text-node coordinates.

The build script uses the deck-stage API to activate each slide, hides deck-stage navigation chrome before capture, applies a classroom readability floor, and rewrites text-box outlines to DrawingML `noFill` for LibreOffice and WPS compatibility.

## Design Identity

Editorial Forest is a quiet, warm, reflective presentation system:

- forest green: `#2E4A2A`;
- dusty pink: `#E89CB1`;
- warm cream: `#EFE7D4`;
- ink: `#1A1A17`;
- Source Serif 4 for the editorial voice;
- JetBrains Mono for labels and small metadata;
- large serif statements, calm grids, and restrained chart frames.

It is strongest for student research recaps, literature presentations, course reports, studio-style project updates, and reflective summaries.

It is weaker for punchy product launches, high-energy coding demos, or dense competitive analysis where stronger scanning contrast is needed.

## Source Layout Roles

| Source layout | Product role | Writer mapping |
| --- | --- | --- |
| `cover` | `cover` | cover/title |
| `agenda` | `agenda` | agenda |
| `statement` | `statement` | thesis/claim |
| `two-col` | `two_col` | image plus narrative |
| `data` | `data` | chart/data |
| `framework` | `framework` | four-step process |
| `stats` | `stats` | KPI summary |
| `summary` | `summary` | closing summary |

These roles are captured in `frame-map.json`.

## Current Status

Status remains `candidate` until the frontend and Writer consume `visual_master=editorial_forest`.
